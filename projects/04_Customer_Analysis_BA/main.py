#!/usr/bin/env python3
"""
End-to-end pipeline: data -> DuckDB -> dbt -> modelling -> reports -> notify.

Usage::
    python main.py                 # full run (uses existing data if present)
    python main.py --regenerate    # rebuild synthetic data first
    python main.py --skip-dbt      # reuse existing marts
    python main.py --no-email --no-browser
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from config import settings  # noqa: E402
from notifications import notifier  # noqa: E402
from src import analysis, modeling  # noqa: E402


def _run(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> dict:
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env,
                          capture_output=True, text=True)
    return {"cmd": " ".join(cmd), "returncode": proc.returncode,
            "stdout": proc.stdout[-4000:], "stderr": proc.stderr[-4000:],
            "seconds": round(time.time() - t0, 2)}


def ensure_data(regenerate: bool) -> dict:
    raw = ROOT / "data" / "raw"
    need = regenerate or not list(raw.glob("*.parquet"))
    steps = {}
    if need:
        steps["generate"] = _run([sys.executable, "scripts/generate_mock_data.py"], cwd=ROOT)
    steps["load_raw"] = _run([sys.executable, "scripts/load_raw_to_duckdb.py"], cwd=ROOT)
    return steps


def run_dbt(run_tests: bool = True) -> dict:
    dbt = shutil.which("dbt")
    if not dbt:
        return {"error": "dbt executable not found; activate customer_analysis_ba first"}
    env = {**dict(__import__("os").environ), "DUCKDB_PATH": "../warehouse.duckdb"}
    steps = {"dbt_run": _run([dbt, "run", "--profiles-dir", ".", "--project-dir", "."],
                             cwd=ROOT / "dbt_project", env=env)}
    if run_tests:
        steps["dbt_test"] = _run([dbt, "test", "--profiles-dir", ".", "--project-dir", "."],
                                 cwd=ROOT / "dbt_project", env=env)
    return steps


def start_streamlit(port: int = 8501) -> subprocess.Popen | None:
    url = f"http://localhost:{port}/_stcore/health"
    try:
        if requests.get(url, timeout=1).status_code == 200:
            return None  # already running
    except Exception:
        pass
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "dashboards/app.py",
         "--server.port", str(port), "--server.headless", "true",
         "--browser.gatherUsageStats", "false"],
        cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return proc


def wait_health(port: int, timeout: int = 60) -> bool:
    url = f"http://localhost:{port}/_stcore/health"
    for _ in range(timeout):
        try:
            if requests.get(url, timeout=2).status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--regenerate", action="store_true")
    parser.add_argument("--skip-dbt", action="store_true")
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--no-email", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--no-notify", action="store_true")
    parser.add_argument("--no-lark", action="store_true")
    parser.add_argument("--port", type=int, default=8501)
    args = parser.parse_args()

    status = {"started_at": datetime.now().isoformat(timespec="seconds"),
              "steps": {}, "errors": {}}
    kpis, insights, results = {}, [], {}
    run_ok = True

    # 1) data
    try:
        status["steps"]["data"] = ensure_data(args.regenerate)
        for name, r in status["steps"]["data"].items():
            if r["returncode"] != 0:
                raise RuntimeError(f"{name} failed: {r['stderr'][:500]}")
    except Exception as exc:
        status["errors"]["data"] = str(exc); run_ok = False

    # 2) dbt
    if run_ok and not args.skip_dbt:
        try:
            dbt_steps = run_dbt(not args.skip_tests)
            status["steps"]["dbt"] = dbt_steps
            if dbt_steps.get("dbt_run", {}).get("returncode", 0) != 0:
                raise RuntimeError("dbt run failed: " + dbt_steps["dbt_run"]["stderr"][:500])
            if dbt_steps.get("dbt_test", {}).get("returncode", 0) != 0:
                status["errors"]["dbt_tests"] = dbt_steps["dbt_test"]["stdout"][-1500:]
        except Exception as exc:
            status["errors"]["dbt"] = str(exc); run_ok = False

    # 3) modelling + analysis
    if run_ok:
        try:
            con = duckdb.connect(settings.DUCKDB_PATH, read_only=True)
            results, model_errors = modeling.run_all(con)
            status["errors"].update({f"model:{k}": v for k, v in model_errors.items()})
            kpis = analysis.compute_kpis(con)
            insights = analysis.build_insights(kpis, results)
            status["steps"]["reports"] = analysis.save_reports(results, kpis, insights)
            con.close()
        except Exception as exc:
            status["errors"]["modelling"] = str(exc); run_ok = False

    # 4) dashboard + three-source notification
    proc = start_streamlit(args.port)
    healthy = wait_health(args.port)
    status["steps"]["dashboard"] = {"healthy": healthy, "url": settings.DASHBOARD_URL}

    shot_zh = {"ok": False, "reason": "dashboard unhealthy"}
    shot_en = {"ok": False, "reason": "dashboard unhealthy"}
    if healthy:
        shot_zh = notifier.capture_screenshot(settings.DASHBOARD_URL_ZH, settings.SCREENSHOT_PATH)
        shot_en = notifier.capture_screenshot(settings.DASHBOARD_URL_EN, settings.SCREENSHOT_PATH_EN)
        if shot_zh.get("ok"):
            import shutil as _shutil
            _shutil.copyfile(settings.SCREENSHOT_PATH, settings.SCREENSHOT_LEGACY)
    status["steps"]["screenshot"] = {"zh": shot_zh, "en": shot_en}

    links = {"zh": settings.DASHBOARD_URL_ZH, "en": settings.DASHBOARD_URL_EN}
    subject = ("[CEX Analytics] " + ("SUCCESS" if run_ok else "FAILED") +
               f" · {datetime.now():%Y-%m-%d}")
    html_body = notifier.build_html(run_ok, kpis, insights, status["errors"],
                                    tables={"Attribution": (results.get("attribution") or {}).get("table") if results.get("attribution") else None,
                                            "Channel performance": results.get("shapley") if isinstance(results.get("shapley"), pd.DataFrame) else None,
                                            "A/B test": (results.get("ab") or {}).get("table") if results.get("ab") else None},
                                    screenshot=settings.SCREENSHOT_PATH if shot_zh.get("ok") else None,
                                    screenshot_en=settings.SCREENSHOT_PATH_EN if shot_en.get("ok") else None,
                                    links=links)
    summary = notifier.build_summary(run_ok, kpis, insights)
    status["summary"] = summary
    if not args.no_notify:
        status["steps"]["mac_notify"] = notifier.mac_notify(
            "CEX Analytics pipeline", "Succeeded" if run_ok else "Failed",
            "daily run", summary=summary, links=links)
    if not args.no_lark:
        status["steps"]["lark"] = notifier.lark_notify(summary, run_ok, kpis, insights, links=links)
    if healthy and not args.no_browser:
        status["steps"]["browser"] = notifier.open_browser(links["zh"])
    if not args.no_email:
        status["steps"]["email"] = notifier.send_email(
            subject, html_body, screenshot=settings.SCREENSHOT_PATH,
            screenshot_en=settings.SCREENSHOT_PATH_EN)

    status["finished_at"] = datetime.now().isoformat(timespec="seconds")
    status["ok"] = run_ok
    status["kpis"] = kpis
    status["insights"] = insights
    settings.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (settings.REPORTS_DIR / "latest_run.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    print(json.dumps({"ok": run_ok, "kpis": kpis, "errors": status["errors"],
                      "screenshot": {"zh": shot_zh.get("ok"), "en": shot_en.get("ok")},
                      "email": status["steps"].get("email", {})}, ensure_ascii=False, indent=2))
    return 0 if run_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
