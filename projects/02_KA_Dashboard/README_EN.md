# 02 · VIP(KA) Tiering & Dashboard (KA_Dashboard)

> 中文版 → [README.md](./README.md)

**_SQL-defined KA (key-account / high-net-worth VIP) tiering, plus a dashboard across transactions, activity, retention and RFM, delivered in Grafana._**

- Language: `SQL` (MySQL / TiDB dialect)
- Core file: [ka_dashboard_sql.sql](./ka_dashboard_sql.sql)

## 1. Background

The operations team needed a stable "identify big clients + tiered operations" mechanism. I owned describing *who counts as a big client, which tier they get, and how often tiers are recomputed* in data terms, and turning the result into a live dashboard. Two core requirements:

1. **Tiering must be explainable and reproducible** — no hand-waving;
2. **The new rules must be sandboxed before launch** — to avoid mass downgrades and complaints.

## 2. Stack

| Stage | Tools |
| --- | --- |
| Warehouse / query | `MySQL`, `TiDB` (MySQL-compatible) |
| Scheduling & storage | Scheduled jobs writing snapshot tables such as `ba_user_active_snap` |
| Visualisation | `Grafana` |
| Sandboxing | `Python` (`pandas` + `plotly`) |

## 3. Key findings / design notes

**Tiering design**

- Score with both `last_30d_trade_val` (30-day trading volume) and `total_auc` (available + frozen + financial), splitting users into `ka1 / ka2 / ka3`;
- Tiering follows the **Pareto principle**: higher tier → fewer users → more concentrated assets, shown as a funnel of headcount and balance.

**Stability (reshuffle)**

- Take **10 time points** as samples and count how often the same users move tiers (upgrade/downgrade) under the new vs. old rules;
- Comparing reshuffle counts, tier distributions and balance distributions makes this a pre-launch **sandbox** rather than an after-the-fact fix.

**Activity & retention**

- Separate `DAU / MAU`, and split activity by behaviour — login, trading (`BUY/SELL`), card usage — reporting KA share under each definition;
- Results are written into `ba_user_active_snap` for Grafana to consume directly.

## 4. Layout

```
02_KA_Dashboard/
├── ka_dashboard_sql.sql               # Core SQL (tiering rules + metric definitions + snapshot writes)
├── pretest_hirarchyV2.ipynb           # Pre-launch sandbox for the new rules
├── Grafana_VIP_Dashboard_v2_Structure.png  # Dashboard structure
└── VIP_hirarchy_system.png            # Tier system illustration
```

## 5. How to run

1. Prepare the base tables in your target DB (`ofp_ka_info`, `ofp_user`, `ofp_user_action_log`, …);
2. Run the queries in `ka_dashboard_sql.sql` section by section to produce tiering results and activity snapshots;
3. Sandbox: run `pretest_hirarchyV2.ipynb` to inspect reshuffle counts and distribution differences between old and new rules;
4. Connect the resulting tables in Grafana and build panels following the structure image.

> Note: DB and table names in the SQL are anonymised business names; replace them with your own when reproducing.
