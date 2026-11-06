# -*- coding: utf-8 -*-
"""周报自动化：取数 → 汇总 → 渲染 HTML → 导出 Excel →（可选）发邮件。

原版是一个两千行的 notebook：SQL 写死在 cell 里，渲染、截图、发信也都在 cell 里，
改个副标题都要从头跑一遍，跑一次两分多钟，还经常卡在发信那步。
这里拆成几步，每步都能单独跑，出错了好定位 —— 也方便我把 template 反复改。

用法：
    python src/report_pipeline.py                # 样例数据 + 只落 HTML/Excel
    python src/report_pipeline.py --send         # 加上发邮件（config 里也要 enabled）
    python src/report_pipeline.py --date 2023-06-05
"""

import argparse
import logging
import os
import smtplib
from datetime import date, datetime
from email.message import EmailMessage
from pathlib import Path

import pandas as pd
import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("weekly")

BASE_DIR = Path(__file__).resolve().parent.parent


def load_config(path=None):
    cfg_path = Path(path or os.getenv("REPORT_CONFIG", BASE_DIR / "config.yaml"))
    if not cfg_path.exists():
        cfg_path = BASE_DIR / "config.example.yaml"

    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    try:
        from dotenv import load_dotenv

        load_dotenv(BASE_DIR / ".env")
    except ImportError:
        pass

    # 配置里的路径都是相对项目根目录写的，这里统一转成绝对路径，免得 cwd 一变就找不到
    for key in ("sample_csv", "template", "output_dir", "sql_file"):
        if cfg.get(key):
            cfg[key] = str(BASE_DIR / cfg[key])
    return cfg


def load_from_sample(cfg):
    """样例数据：用来看流程通不通，数据是我照着真实报表结构造的一小份。"""
    df = pd.read_csv(cfg["sample_csv"])
    log.info("样例数据 %s 行，周期 %s", len(df), ",".join(sorted(df["period"].unique())))
    return df


def load_from_trino(cfg, sql_path):
    """连 Trino 跑 SQL 文件。

    这段本地没法测（要连公司内网），所以写得很朴素，只做最基本的分号切分。
    真遇到注释里带分号的 SQL 就崩，认了 —— sql 文件是我自己维护的，注意点就行。
    """
    from trino.dbapi import connect

    t = cfg["trino"]
    conn = connect(host=t["host"], port=t["port"], user=t["user"], catalog=t["catalog"], schema=t["schema"])
    sql_text = Path(sql_path).read_text(encoding="utf-8")

    frames = []
    for i, stmt in enumerate(s.strip() for s in sql_text.split(";") if s.strip()):
        if stmt.startswith("--") and "\n" not in stmt:  # 纯注释行，跳过
            continue
        log.info("跑第 %s 段 SQL（%s 字符）", i + 1, len(stmt))
        frames.append(pd.read_sql(stmt, conn))

    if not frames:
        raise SystemExit("SQL 文件里没解析出任何语句：%s" % sql_path)
    return pd.concat(frames, ignore_index=True)


def build_tables(df, current_period):
    """把明细摊成报表要的几张表。

    口径提一下：周不是自然周，是「周一到周日」，跟公司周会时间对齐；
    对比列取上一周，做环比。
    """
    periods = sorted(df["period"].unique())
    if current_period not in periods:
        current_period = periods[-1]
    idx = periods.index(current_period)
    prev_period = periods[idx - 1] if idx > 0 else None

    cur = df[df["period"] == current_period]
    prev = df[df["period"] == prev_period] if prev_period else cur.iloc[0:0]

    def _pivot(frame):
        return frame.groupby("market_source").agg(
            tx_case_cnt=("tx_case_cnt", "sum"),
            tx_customer_cnt=("tx_customer_cnt", "sum"),
            tx_amount=("tx_amount", "sum"),
            new_user_cnt=("new_user_cnt", "sum"),
        )

    cur_p, prev_p = _pivot(cur), _pivot(prev)

    # join(lsuffix/rsuffix) 在新版 pandas 里要废弃，改用 merge，兼容老版本
    channels = (
        cur_p.reset_index()
        .merge(prev_p.reset_index(), on="market_source", how="outer", suffixes=("_cur", "_prev"))
        .fillna(0)
    )
    channels["tx_amount_wow"] = channels.apply(
        lambda r: 0.0 if r["tx_amount_prev"] == 0 else round(r["tx_amount_cur"] / r["tx_amount_prev"] - 1, 4), axis=1
    )

    # 首充转化率：按渠道算完 merge 回去，别用 .values 硬塞 ——
    # 之前那么写，渠道顺序一变就串行了，查了半天才发现
    dep = (
        cur.groupby("market_source")["first_deposit_user_cnt"].sum()
        / cur.groupby("market_source")["new_user_cnt"].sum().replace(0, pd.NA)
    ).fillna(0).round(4).rename("first_deposit_rate").reset_index()
    channels = channels.merge(dep, on="market_source", how="left").fillna({"first_deposit_rate": 0})

    overview = {
        "period": current_period,
        "prev_period": prev_period,
        "tx_amount": round(float(cur["tx_amount"].sum()), 2),
        "tx_cases": int(cur["tx_case_cnt"].sum()),
        "tx_users": int(cur["tx_customer_cnt"].sum()),
        "new_users": int(cur["new_user_cnt"].sum()),
        "kyc_success_rate": round(float(cur["kyc_success_rate"].mean()), 4),
        "tx_amount_wow": round(
            float(cur["tx_amount"].sum() / prev["tx_amount"].sum() - 1), 4
        ) if prev["tx_amount"].sum() else 0.0,
    }
    return overview, channels


def render_html(cfg, overview, channels, rows):
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    env = Environment(
        loader=FileSystemLoader(str(Path(cfg["template"]).parent)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template(Path(cfg["template"]).name)

    # 金额单位换成万，表格才不会挤成一坨
    def _wan(v):
        return "{:,.1f}".format(v / 10000.0)

    def _pct(v):
        return "{:.2%}".format(v)

    html = template.render(
        overview=overview,
        channels=channels.to_dict("records"),
        rows=rows.to_dict("records"),
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        wan=_wan,
        pct=_pct,
    )
    return html


def export_excel(path, overview, channels, rows):
    """一个 sheet 塞三段，中间空两行。简单粗暴，运营能在 Excel 里直接复制。

    样式只做了列宽，数字格式没有精雕细琢 —— 曾经花半小时调边框，
    后来发现没人看，就删了。
    """
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        s = 0
        pd.DataFrame([overview]).T.reset_index().rename(columns={"index": "metric", 0: "value"}).to_excel(
            writer, sheet_name="weekly", startrow=s, index=False
        )
        s += len(overview) + 3
        channels.to_excel(writer, sheet_name="weekly", startrow=s, index=False)
        s += len(channels) + 3
        rows.to_excel(writer, sheet_name="weekly", startrow=s, index=False)

        ws = writer.sheets["weekly"]
        for col, width in zip("ABCDEFG", (26, 18, 18, 18, 18, 18, 18)):
            ws.column_dimensions[col].width = width


def send_email(cfg, subject, html, attachment):
    """发 HTML 邮件 + Excel 附件。

    用公司 SMTP，465 走 SSL。密码从 .env 的 SMTP_PASSWORD 读 ——
    之前写在代码里，差点提交上去，现在宁可多一步。
    """
    email_cfg = cfg.get("email", {})
    password = os.getenv("SMTP_PASSWORD")
    if not password:
        raise SystemExit("没找到 SMTP_PASSWORD，先写到 .env 里再发邮件")

    msg = EmailMessage()
    msg["Subject"] = "%s %s" % (email_cfg.get("subject_prefix", ""), subject)
    msg["From"] = email_cfg["sender"]
    msg["To"] = ", ".join(email_cfg["recipients"])
    msg.set_content("这是一封 HTML 邮件，用支持 HTML 的客户端打开。")
    msg.add_alternative(html, subtype="html")

    if attachment and Path(attachment).exists():
        msg.add_attachment(
            Path(attachment).read_bytes(),
            maintype="application",
            subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=Path(attachment).name,
        )

    log.info("发送到 %s ...", email_cfg["recipients"])
    with smtplib.SMTP_SSL(email_cfg["smtp_host"], email_cfg["smtp_port"], timeout=20) as smtp:
        smtp.login(email_cfg["sender"], password)
        smtp.send_message(msg)
    log.info("邮件发出去了")


def main():
    cfg = load_config()
    parser = argparse.ArgumentParser(description="周报自动化")
    parser.add_argument("--date", default=None, help="报表周期（周一日期），默认取最新一期")
    parser.add_argument("--send", action="store_true", help="真的发邮件，不加这个只落本地文件")
    parser.add_argument("--no-email", action="store_true", help="显式不发（Docker 默认用这个）")
    args = parser.parse_args()

    # 1) 取数
    if cfg.get("data_source") == "trino":
        df = load_from_trino(cfg, cfg["sql_file"])
    else:
        df = load_from_sample(cfg)

    # 2) 汇总
    overview, channels = build_tables(df, args.date)
    rows = df[df["period"] == overview["period"]].sort_values("tx_amount", ascending=False)

    # 3) 渲染 + 导出
    out_dir = Path(cfg["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = overview["period"].replace("-", "")
    html_path = out_dir / ("%s_%s.html" % (cfg.get("report_name", "weekly"), stamp))
    xlsx_path = out_dir / ("%s_%s.xlsx" % (cfg.get("report_name", "weekly"), stamp))

    html = render_html(cfg, overview, channels, rows)
    html_path.write_text(html, encoding="utf-8")
    export_excel(xlsx_path, overview, channels, rows)
    log.info("本期 %s，交易额 %.2f，环比 %s", overview["period"], overview["tx_amount"], overview["tx_amount_wow"])
    log.info("写好：%s / %s", html_path.name, xlsx_path.name)

    # 4) 发信（默认不发，得显式 --send 且 config 里 enabled=true）
    if args.send and not args.no_email and cfg.get("email", {}).get("enabled"):
        send_email(cfg, "运营周报 %s" % overview["period"], html, xlsx_path)
    else:
        log.info("这次不发邮件（加 --send 且 email.enabled=true 才发）")


if __name__ == "__main__":
    main()
