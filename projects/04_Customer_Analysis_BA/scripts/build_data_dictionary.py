#!/usr/bin/env python3
"""Generate markdown data dictionaries from the generated parquet files."""
from __future__ import annotations

import json
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DOCS = ROOT / "docs"

DESC = {
    "dim_users": ("用户主表", "User master table"),
    "dim_kyc": ("实名认证记录", "KYC records"),
    "fact_transactions": ("交易明细", "Transaction detail"),
    "fact_deposit_withdraw": ("充提记录", "Deposit / withdrawal records"),
    "fact_events": ("行为埋点流", "Behavioural event stream"),
    "fact_campaigns": ("活动 / 空投定义", "Campaign / airdrop definitions"),
    "bridge_campaign_user": ("活动参与明细", "Campaign participation bridge"),
    "fact_ads_spend": ("分渠道每日广告花费", "Daily ad spend by channel"),
    "fact_social_metrics": ("社媒每日指标", "Daily social metrics"),
    "fact_touchpoints": ("归因触点序列", "Attribution touchpoints"),
    "fact_page_modules": ("页面模块曝光/点击", "Page module impressions/clicks"),
    "fact_cta_experiments": ("CTA 全因子实验", "CTA full-factorial experiment"),
    "fact_ab_assignments": ("A/B 分流", "A/B assignments"),
    "dim_user_tags": ("用户标签", "User tags"),
    "fact_ltv_labels": ("LTV 标签", "LTV labels"),
    "fact_funnel_snapshot": ("漏斗步骤快照", "Funnel step snapshot"),
}


def build(lang: str = "zh") -> str:
    title = "# 数据字典" if lang == "zh" else "# Data Dictionary"
    note = ("由 `scripts/build_data_dictionary.py` 从实际 Parquet 文件自动生成。" if lang == "zh"
            else "Auto-generated from the actual Parquet files by `scripts/build_data_dictionary.py`.")
    lines = [title, "", f"> {note}", ""]
    manifest = json.loads((RAW / "_manifest.json").read_text())
    lines += [f"- seed: `{manifest['seed']}`", f"- users: `{manifest['n_users']:,}`",
              f"- days: `{manifest['days']}`", f"- end date: `{manifest['end_date']}`", ""]
    for f in sorted(RAW.glob("*.parquet")):
        name = f.stem
        schema = pq.read_schema(f)
        rows = pq.ParquetFile(f).metadata.num_rows
        zh, en = DESC.get(name, (name, name))
        lines += [f"## `{name}` — {zh if lang == 'zh' else en}", "",
                  f"- rows: **{rows:,}**", "",
                  "| column | type |" if lang == "zh" else "| column | type |",
                  "| --- | --- |"]
        for field in schema:
            lines.append(f"| `{field.name}` | `{field.type}` |")
        lines.append("")
    return "\n".join(lines)


def main():
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "data_dictionary.md").write_text(build("zh"), encoding="utf-8")
    (DOCS / "data_dictionary_EN.md").write_text(build("en"), encoding="utf-8")
    print("wrote docs/data_dictionary.md and docs/data_dictionary_EN.md")


if __name__ == "__main__":
    main()
