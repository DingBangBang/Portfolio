#!/usr/bin/env python3
"""Three-source notification: macOS banner, browser open, HTML email."""
from __future__ import annotations

import base64
import html
import json
import mimetypes
import os
import smtplib
import subprocess
import sys
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from config import settings  # noqa: E402


# ----------------------------------------------------------------
# macOS notification
# ----------------------------------------------------------------
def mac_notify(title: str, message: str, subtitle: str = "") -> dict:
    if sys.platform != "darwin":
        return {"ok": False, "reason": "not macOS"}
    script = f'display notification {json.dumps(message)} with title {json.dumps(title)} subtitle {json.dumps(subtitle)}'
    try:
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "reason": str(exc)}


# ----------------------------------------------------------------
# Open browser
# ----------------------------------------------------------------
def open_browser(url: str) -> dict:
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", url])
        else:
            import webbrowser
            webbrowser.open(url)
        return {"ok": True, "url": url}
    except Exception as exc:
        return {"ok": False, "reason": str(exc)}


# ----------------------------------------------------------------
# Playwright screenshot
# ----------------------------------------------------------------
def capture_screenshot(url: str, out_path: Path, timeout_ms: int = 30000) -> dict:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return {"ok": False, "reason": f"playwright import failed: {exc}"}
    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
            except Exception:
                # fall back to the locally installed Google Chrome
                browser = p.chromium.launch(headless=True, channel="chrome")
            page = browser.new_page(viewport={"width": 1440, "height": 2200})
            page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            page.wait_for_timeout(2500)
            page.screenshot(path=str(out_path), full_page=True)
            browser.close()
        return {"ok": True, "path": str(out_path), "bytes": out_path.stat().st_size}
    except Exception as exc:
        return {"ok": False, "reason": str(exc)}


# ----------------------------------------------------------------
# HTML email body
# ----------------------------------------------------------------
def _badge(status: str) -> str:
    color = {"ok": "#1a7f37", "alert": "#cf222e", "info": "#0969da"}.get(status, "#57606a")
    bg = {"ok": "#dafbe1", "alert": "#ffebe9", "info": "#ddf4ff"}.get(status, "#f6f8fa")
    return f'<span style="background:{bg};color:{color};padding:2px 8px;border-radius:10px;font-size:12px">{status.upper()}</span>'


def build_html(run_ok: bool, kpis: dict, insights: list, errors: dict,
               tables: dict | None = None, screenshot: Path | None = None) -> str:
    status_color = "#1a7f37" if run_ok else "#cf222e"
    status_text = "✅ Pipeline succeeded" if run_ok else "❌ Pipeline failed"
    parts = [
        "<html><body style='font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#1f2328'>",
        f"<h1 style='color:{status_color};font-size:22px'>{status_text}</h1>",
        f"<p style='color:#57606a'>Generated at {pd_now()}</p>",
        "<h2 style='font-size:17px'>Core KPIs</h2>",
        "<table style='border-collapse:collapse;font-size:14px'>",
    ]
    from src.analysis import THRESHOLDS
    for key, label in [("users", "Registered users"), ("deposit_rate", "Deposit conversion"),
                       ("trade_rate", "Trading conversion"), ("gmv", "GMV"),
                       ("revenue", "Fee revenue"), ("avg_ltv_90d", "Avg LTV 90d"),
                       ("churn_rate", "90d churn")]:
        val = kpis.get(key)
        if val is None:
            continue
        shown = f"{val:.1%}" if isinstance(val, float) and key.endswith("rate") else (
            f"${val:,.2f}" if key in ("gmv", "revenue", "avg_ltv_90d") else f"{val:,}")
        status = "info"
        if key in THRESHOLDS:
            t = THRESHOLDS[key]
            if "warn_below" in t and val < t["warn_below"]:
                status = "alert"
            elif "warn_above" in t and val > t["warn_above"]:
                status = "alert"
            else:
                status = "ok"
        parts.append(f"<tr><td style='padding:6px 14px 6px 0;color:#57606a'>{label}</td>"
                     f"<td style='padding:6px 14px 6px 0'><b style='font-size:16px'>{shown}</b></td>"
                     f"<td>{_badge(status)}</td></tr>")
    parts.append("</table>")

    parts.append("<h2 style='font-size:17px'>Insights & data-driven suggestions</h2><ol style='font-size:14px'>")
    for ins in insights:
        parts.append(f"<li><b>{html.escape(ins['title'])}</b> — {html.escape(ins['finding'])}<br>"
                     f"<span style='color:#57606a'>建议：{html.escape(ins['suggestion'])}</span></li>")
    parts.append("</ol>")

    if screenshot and Path(screenshot).exists():
        b64 = base64.b64encode(Path(screenshot).read_bytes()).decode()
        parts.append("<h2 style='font-size:17px'>Live dashboard</h2>")
        parts.append(f"<img src='data:image/png;base64,{b64}' style='max-width:100%;border:1px solid #d0d7de;border-radius:8px'/>")

    if tables:
        for title, df in tables.items():
            if df is None or len(df) == 0:
                continue
            parts.append(f"<h2 style='font-size:17px'>{html.escape(title)}</h2>")
            parts.append(df.head(10).to_html(index=False, border=0,
                                             classes="tbl", justify="left"))
    if errors:
        parts.append("<h2 style='font-size:17px;color:#cf222e'>Errors</h2><ul style='font-size:13px'>")
        for k, v in errors.items():
            parts.append(f"<li><b>{html.escape(k)}</b>: {html.escape(str(v))}</li>")
        parts.append("</ul>")
    parts.append("</body></html>")
    return "\n".join(parts)


def pd_now() -> str:
    import pandas as pd
    return pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")


# ----------------------------------------------------------------
# Email
# ----------------------------------------------------------------
def send_email(subject: str, html_body: str, to: str | None = None,
               screenshot: Path | None = None) -> dict:
    to = to or settings.MAIL_TO
    out = settings.REPORTS_DIR / "email_preview.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_body, encoding="utf-8")
    result = {"ok": False, "preview": str(out), "to": to}
    if not settings.SMTP_HOST or not settings.SMTP_USER:
        result["reason"] = "SMTP not configured; wrote local preview only"
        return result
    msg = MIMEMultipart("related")
    msg["Subject"] = subject
    msg["From"] = settings.MAIL_FROM
    msg["To"] = to
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    if screenshot and Path(screenshot).exists():
        img = MIMEImage(Path(screenshot).read_bytes(), _subtype="png")
        img.add_header("Content-ID", "<dashboard>")
        msg.attach(img)
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.MAIL_FROM, [to], msg.as_string())
        result.update({"ok": True, "reason": "sent"})
    except Exception as exc:
        result["reason"] = str(exc)
    return result
