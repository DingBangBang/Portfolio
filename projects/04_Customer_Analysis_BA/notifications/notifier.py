#!/usr/bin/env python3
"""Three-source notification: macOS banner, browser open, HTML email."""
from __future__ import annotations

import base64
import html
import json
import mimetypes
import os
import shutil
import smtplib
import subprocess
import sys
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from config import settings  # noqa: E402


# ----------------------------------------------------------------
# macOS notification
# ----------------------------------------------------------------
def mac_notify(title: str, message: str, subtitle: str = "", summary: str = "", links: dict | None = None) -> dict:
    """Prefer terminal-notifier (rich banner); fall back to osascript."""
    if sys.platform != "darwin":
        return {"ok": False, "reason": "not macOS"}
    links = links or {"zh": settings.DASHBOARD_URL_ZH, "en": settings.DASHBOARD_URL_EN}
    detail = f"{message} · {summary}" if summary else message
    detail = detail + chr(10) + "中文: " + links["zh"] + chr(10) + "EN: " + links["en"]
    tn = shutil.which("terminal-notifier")
    if tn:
        try:
            subprocess.run([tn, "-title", title, "-subtitle", subtitle,
                            "-message", detail, "-sound", "Glass",
                            "-group", "cex-analytics", "-open", links["zh"]],
                           check=True, capture_output=True)
            return {"ok": True, "channel": "terminal-notifier"}
        except Exception:
            pass
    script = f'display notification {json.dumps(detail)} with title {json.dumps(title)} subtitle {json.dumps(subtitle)}'
    try:
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
        return {"ok": True, "channel": "osascript"}
    except Exception as exc:
        return {"ok": False, "reason": str(exc)}


def build_summary(run_ok: bool, kpis: dict, insights: list | None = None) -> str:
    """One-line business summary used by every notification channel."""
    if not run_ok:
        return "Pipeline failed — check the error details"
    if not kpis:
        return "Pipeline succeeded"
    parts = [f"{kpis.get('users', 0):,} users",
             f"deposit {kpis.get('deposit_rate', 0):.1%}",
             f"GMV ${kpis.get('gmv', 0)/1e6:.1f}M"]
    if kpis.get("churn_rate") is not None:
        parts.append(f"90d churn {kpis['churn_rate']:.1%}")
    head = " | ".join(parts)
    if insights:
        alert = next((i for i in insights if i.get("status") == "alert"), None)
        if alert:
            head += f" | ⚠ {alert['title']}: {alert['finding']}"
    return head


def lark_notify(summary: str, run_ok: bool, kpis: dict | None = None,
                insights: list | None = None, webhook: str | None = None,
                links: dict | None = None) -> dict:
    webhook = webhook or settings.LARK_WEBHOOK
    if not webhook:
        return {"ok": False, "reason": "LARK_WEBHOOK not configured"}
    links = links or {"zh": settings.DASHBOARD_URL_ZH, "en": settings.DASHBOARD_URL_EN}
    fields = []
    if kpis:
        for name, value in [
            ("👥 Users", f"{kpis.get('users', 0):,}"),
            ("💳 Deposit CVR", f"{kpis.get('deposit_rate', 0)*100:.2f}%"),
            ("📈 GMV", f"${kpis.get('gmv', 0)/1e6:.2f}M"),
            ("💰 Fee revenue", f"${kpis.get('revenue', 0):,.2f}"),
            ("📉 90d churn", f"{kpis.get('churn_rate', 0)*100:.2f}%"),
            ("🛡 KYC rate", f"{kpis.get('kyc_rate', 0)*100:.2f}%"),
        ]:
            fields.append({"is_short": True,
                           "text": {"tag": "lark_md", "content": f"**{name}**\n{value}"}})
    insights_md = "\n".join(
        f"- **{ins['title']}**: {ins['finding']}" for ins in (insights or [])[:6]
    ) or "No insights"
    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "green" if run_ok else "red",
            "title": {"tag": "plain_text",
                      "content": f"CEX Analytics · {'SUCCESS' if run_ok else 'FAILED'}"},
        },
        "elements": [
            {"tag": "div",
             "text": {"tag": "lark_md", "content": f"**One-line summary**\n{summary}"}},
            {"tag": "hr"},
            {"tag": "div", "fields": fields},
            {"tag": "hr"},
            {"tag": "div",
             "text": {"tag": "lark_md", "content": f"**Insights**\n{insights_md}"}},
            {"tag": "hr"},
            {"tag": "action",
             "actions": [
                 {"tag": "button", "type": "primary",
                  "text": {"tag": "plain_text", "content": "中文看板"},
                  "url": links["zh"]},
                 {"tag": "button", "type": "default",
                  "text": {"tag": "plain_text", "content": "English dashboard"},
                  "url": links["en"]},
             ]},
        ],
    }
    try:
        resp = requests.post(webhook, json={"msg_type": "interactive", "card": card}, timeout=15)
        return {"ok": resp.ok, "status_code": resp.status_code, "response": resp.text[:300]}
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
# Playwright screenshot (scroll and stitch)
# ----------------------------------------------------------------
def capture_screenshot(url: str, out_path: Path, timeout_ms: int = 60000) -> dict:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return {"ok": False, "reason": f"playwright import failed: {exc}"}
    try:
        import io
        from PIL import Image

        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
            except Exception:
                browser = p.chromium.launch(headless=True, channel="chrome")
            page = browser.new_page(viewport={"width": 1440, "height": 2000})
            page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            page.wait_for_timeout(5000)
            page.add_style_tag(content="""
                [data-testid="stSidebar"] {display: none !important;}
                section[data-testid=stMain] {margin-left: 0 !important; width: 100% !important;}
            """)
            page.wait_for_timeout(1500)
            metrics = page.evaluate("""() => {
                const el = document.querySelector('section[data-testid=stMain]');
                return {h: el.scrollHeight, c: el.clientHeight};
            }""")
            total, client = int(metrics["h"]), int(metrics["c"])
            if total <= client + 50:
                page.screenshot(path=str(out_path), full_page=True)
            else:
                imgs = []
                for off in range(0, total, client):
                    page.evaluate(
                        "(y) => { const el = document.querySelector('section[data-testid=stMain]'); el.scrollTop = y; }",
                        off)
                    page.wait_for_timeout(500)
                    buf = page.screenshot(full_page=False)
                    imgs.append(Image.open(io.BytesIO(buf)).convert("RGB"))
                width = imgs[0].width
                stitched = Image.new("RGB", (width, client * len(imgs)), "white")
                for i, im in enumerate(imgs):
                    stitched.paste(im, (0, i * client))
                stitched = stitched.crop((0, 0, width, min(total, stitched.height)))
                stitched.save(out_path)
            browser.close()
        return {"ok": True, "path": str(out_path), "bytes": out_path.stat().st_size,
                "height": int(total)}
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
               tables: dict | None = None, screenshot: Path | None = None,
               links: dict | None = None, screenshot_en: Path | None = None) -> str:
    status_color = "#1a7f37" if run_ok else "#cf222e"
    status_text = "✅ Pipeline succeeded" if run_ok else "❌ Pipeline failed"
    parts = [
        "<html><body style='font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#1f2328'>",
        f"<h1 style='color:{status_color};font-size:22px'>{status_text}</h1>",
        f"<p style='color:#57606a'>Generated at {pd_now()}</p>",
        (f"<p><a href='{links['zh']}' style='background:#2563eb;color:#fff;padding:9px 16px;"
         f"border-radius:8px;text-decoration:none;margin-right:10px'>中文看板</a>"
         f"<a href='{links['en']}' style='background:#0f172a;color:#fff;padding:9px 16px;"
         f"border-radius:8px;text-decoration:none'>English dashboard</a></p>") if links else "",
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
        parts.append("<h2 style='font-size:17px'>中文看板 / Chinese dashboard</h2>")
        parts.append("<img src='cid:dashboard_zh' style='max-width:100%;border:1px solid #d0d7de;border-radius:8px'/>")
    if screenshot_en and Path(screenshot_en).exists():
        parts.append("<h2 style='font-size:17px'>English dashboard</h2>")
        parts.append("<img src='cid:dashboard_en' style='max-width:100%;border:1px solid #d0d7de;border-radius:8px'/>")

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
               screenshot: Path | None = None, screenshot_en: Path | None = None) -> dict:
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
    def _attach(path, cid):
        try:
            import io as _io
            from PIL import Image
            im = Image.open(path)
            im.thumbnail((1200, 20000))
            buf = _io.BytesIO()
            im.convert("RGB").save(buf, format="JPEG", quality=80, optimize=True)
            img = MIMEImage(buf.getvalue(), _subtype="jpeg")
        except Exception:
            img = MIMEImage(Path(path).read_bytes(), _subtype="png")
        img.add_header("Content-ID", f"<{cid}>")
        msg.attach(img)

    if screenshot and Path(screenshot).exists():
        _attach(screenshot, "dashboard_zh")
    if screenshot_en and Path(screenshot_en).exists():
        _attach(screenshot_en, "dashboard_en")
    try:
        if settings.SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=25)
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=25)
            server.starttls()
        try:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.MAIL_FROM, [to], msg.as_string())
        finally:
            server.quit()
        result.update({"ok": True, "reason": "sent"})
    except Exception as exc:
        result["reason"] = str(exc)
    return result
