#!/usr/bin/env python3
"""Persist every modelling output as dashboard-ready CSV/JSON artefacts."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"


def save_reports(results: dict, kpis: dict, insights: list[dict], out: Path = REPORTS) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    res = out / "results"
    res.mkdir(exist_ok=True)

    (out / "kpi_summary.json").write_text(json.dumps(kpis, ensure_ascii=False, indent=2))
    (res / "kpi_summary.json").write_text(json.dumps(kpis, ensure_ascii=False, indent=2))
    pd.DataFrame([kpis]).to_csv(out / "kpi_summary.csv", index=False)

    lines = ["# 自动生成的核心洞察", "", f"生成时间：{pd.Timestamp.now():%Y-%m-%d %H:%M:%S}", ""]
    for i, ins in enumerate(insights, 1):
        lines.append(f"## {i}. {ins['title']}（{ins['status']}）")
        lines.append(f"- 发现：{ins['finding']}")
        lines.append(f"- 建议：{ins['suggestion']}")
        lines.append("")
    (out / "insights.md").write_text("\n".join(lines), encoding="utf-8")

    def save(df, name):
        if isinstance(df, pd.DataFrame) and len(df):
            df.to_csv(res / name, index=False)

    def save_json(obj, name):
        (res / name).write_text(
            json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )

    f = results.get("funnel")
    if f:
        for key in ["daily", "last_day", "by_channel", "by_device"]:
            save(f.get(key), f"funnel_{key}.csv")

    fa = results.get("funnel_attr")
    if fa:
        save(fa["table"], "funnel_attribution.csv")
        save_json(
            {k: fa[k] for k in ["overall_current", "overall_previous", "delta_pp", "window_days"]},
            "funnel_attribution_meta.json",
        )

    rfm = results.get("rfm")
    if rfm:
        save(rfm["assignments"], "rfm_assignments.csv")
        save(rfm["personas"], "rfm_personas.csv")
        save_json({k: rfm[k] for k in ["k", "silhouette", "explained_var"]}, "rfm_metrics.json")

    save(results.get("behaviour"), "behaviour_tests.csv")
    save(results.get("behaviour_validation"), "behaviour_validation.csv")

    flow = results.get("flow")
    if flow:
        save(flow["edges"], "flow_edges.csv")
        save(flow["top_paths"], "flow_top_paths.csv")

    attr = results.get("attribution")
    if attr:
        save(attr["table"], "attribution_comparison.csv")
        save_json(
            {
                "base_conversion_rate": attr["base_conversion_rate"],
                "n_users": attr["n_users"],
                "n_touchpoints": attr["n_touchpoints"],
                "recommended": attr["recommended"],
            },
            "attribution_meta.json",
        )

    save(results.get("shapley"), "channel_shapley.csv")

    ltv = results.get("ltv")
    if ltv:
        save(ltv["metrics"], "ltv_metrics.csv")
        save(ltv.get("predictions"), "ltv_predictions.csv")
        save(ltv.get("feature_importance"), "ltv_feature_importance.csv")
        save(ltv.get("p_alive"), "ltv_p_alive.csv")
        save_json({"cutoff": ltv["cutoff"]}, "ltv_meta.json")

    km = results.get("km")
    if km:
        save(km["curves"], "kaplan_meier_curves.csv")
        save(km["median"], "kaplan_meier_median.csv")
        save_json({"overall_median_days": km["overall_median_days"]}, "kaplan_meier_meta.json")

    save(results.get("survival"), "cox_hazard_ratios.csv")

    roi = results.get("roi_waterfall")
    if roi:
        save(roi["waterfall"], "roi_waterfall.csv")
        save(roi.get("anova"), "roi_anova.csv")
        save(roi.get("manova"), "roi_manova.csv")
        save_json({"overall_roi": roi["overall_roi"]}, "roi_meta.json")

    camp = results.get("campaign")
    if camp:
        save(camp["table"], "campaign_incremental_roi.csv")

    ads = results.get("ads_social")
    if ads:
        save(ads["matrix"], "ads_social_matrix.csv")
        save(ads["lag_table"], "ads_social_lag.csv")

    mod = results.get("modules")
    if mod:
        save(mod["table"], "module_efficiency.csv")

    cta = results.get("cta")
    if cta:
        save(cta["main_effects"], "cta_main_effects.csv")
        save(cta["interaction"], "cta_interaction.csv")
        save(cta["importance"], "cta_feature_importance.csv")
        save(cta.get("anova"), "cta_anova.csv")

    save(results.get("logistic"), "logistic_terms.csv")

    churn = results.get("churn")
    if churn:
        save(churn["metrics"], "churn_metrics.csv")
        save(churn["roc"], "churn_roc.csv")
        save(churn["importance"], "churn_importance.csv")
        save_json({"cutoff": churn["cutoff"]}, "churn_meta.json")

    ab = results.get("ab")
    if ab:
        save(ab["table"], "ab_table.csv")
        save_json(
            {
                k: ab[k]
                for k in ["abs_lift", "rel_lift_pct", "z", "p_value", "ci95", "srm_p_value", "mde_pp"]
            },
            "ab_meta.json",
        )

    vip = results.get("vip")
    if vip:
        save(vip["distribution"], "vip_distribution.csv")
        save(vip["benefits"], "vip_benefits.csv")
        save_json(vip["stability"], "vip_stability.json")

    tags = results.get("tags")
    if tags:
        save(tags["coverage"], "tag_coverage.csv")
        save(tags["top_tags"], "tag_top.csv")
        save(tags["persona_cards"], "tag_personas.csv")

    save(results.get("ops"), "ops_matrix.csv")

    budget = results.get("budget")
    if budget:
        save(budget["params"], "budget_elasticity.csv")
        save(budget["decomposition"], "budget_decomposition.csv")
        save_json({"method": budget["method"]}, "budget_meta.json")

    okr = results.get("okr")
    if okr is not None:
        save(okr.reset_index(), "okr_attribution.csv")

    return {
        "report_dir": str(out),
        "results_dir": str(res),
        "files": sorted(p.name for p in res.glob("*")),
    }
