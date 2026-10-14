# 04 · Exchange User Full-Lifecycle Analytics (Customer_Analysis_BA)

> 中文版 → [README.md](./README.md)

**_A blueprint for full-lifecycle analytics on a centralised exchange (CEX): from the sign-up conversion funnel and RFM segmentation, through churn survival analysis, to LTV prediction, marketing attribution and incremental-ROI measurement._**

- Language: `Python` `SQL`
- Status: **planned**. This README is the full implementation blueprint (background / approach / data / steps / dev docs / deliverables); code and data will be built out following it.

---

## 1. Background

Growth teams at exchanges suffer from three things they cannot articulate:

1. **Where users get stuck** — sign-ups go up but deposits do not, and nobody knows the drop-off at each step;
2. **Whether spend is worth it** — ads, channels, social and campaigns all run at once, yet only last-touch is visible; the question "how much net-new did this channel contribute" goes unanswered;
3. **How to spend next quarter** — budget allocation is gut-feel; when management asks "if we add $100k to channel X, what happens to OKRs", no one can give a number.

This project builds a **reproducible, explainable, actionable** analytics system to answer all three — and lands the results as tools (dashboards / a simulator / a tag system) rather than a one-off report.

Audience: growth leads, operations, marketing and management.

## 2. Framework & Approach

I structure the whole thing as four progressive layers — **see it → attribute it → predict it → decide it** — so the work never starts by piling on models:

```
Layer 0  Data foundation   tables / tracking / metric definitions / data quality
   │
Layer 1  Describe         metrics + funnel + RFM segmentation + behavioural psychology + flow graph
   │
Layer 2  Attribute        funnel attribution + survival (Cox) + multi-model attribution + channel quality (Shapley)
   │
Layer 3  Predict          LTV (BG/NBD vs ML) + CAC/CPA/ROI + causal inference (incrementality)
   │
Layer 4  Decide           tag system + VIP mechanism + refined-ops framework + budget simulator + OKR attribution
```

Three principles run throughout:

- **Definitions first** — write down numerator/denominator/window/dedup rules before any analysis; every conclusion shares one definition set;
- **Correlation ≠ causation** — any "A caused B" claim must survive a counterfactual / randomised experiment / regression discontinuity;
- **Built for decisions** — every analysis ends with a "so what next" action, otherwise it does not ship.

## 3. Data Design

### 3.1 Sourcing strategy

Rather than depending on one ready dataset, I use **"public datasets as a base + synthetic augmentation"**:

- **Public datasets** (to calibrate distributions for behaviour, transactions, attribution):
  - Kaggle *eCommerce events history* (funnel, category, price distributions);
  - Criteo / marketing-funnel style attribution datasets (multi-channel touchpoint order);
  - public crypto trading / deposit-withdrawal samples (asset, amount, time distributions).
- **Synthetic augmentation** (for CEX-specific and internal tables): `numpy`/`Faker` generate users, transactions, campaigns, ad spend and social metrics following realistic distributions, with **consistent keys across tables and a coherent timeline** (e.g. `GMV` must equal the aggregate of the transaction table).

> All generation scripts fix a random seed (`random_state`), so anyone reproduces the same dataset.

### 3.2 Tables (data dictionary)

The 16 core tables below, **each with ≥ 1,000 rows**, directly support every analysis step in this document.

| # | Table | Description | Key columns | Scale | Used by |
| --- | --- | --- | --- | --- | --- |
| 1 | `dim_users` | User master | `user_id, register_time, register_device_type, register_channel, kyc_area, kyc_type, is_robot, vip_level` | ~250K | Everything |
| 2 | `fact_events` | Behavioural event stream | `event_id, user_id, event_time, event_name, page, module_id, session_id, device` | ~50M | Funnel / flow graph / sequences |
| 3 | `fact_transactions` | Transaction detail | `tx_id, user_id, tx_time, record_type, symbol, quote_amt, is_otc, fee` | ~8M | Trading / GMV / repurchase |
| 4 | `fact_deposit_withdraw` | Deposits / withdrawals | `dw_id, user_id, record_type, asset, amount, status, fail_reason, created_at` | ~3M | First-deposit conversion |
| 5 | `dim_kyc` | KYC records | `kyc_id, user_id, kyc_type, region, status, submit_time, finish_time` | ~250K | Funnel / compliance |
| 6 | `fact_campaigns` | Campaign / airdrop definitions | `campaign_id, name, channel, start_time, end_time, budget, reward_type` | ~2K | Campaign ROI / airdrops |
| 7 | `bridge_campaign_user` | Campaign participation | `campaign_id, user_id, join_time, reward_amt, is_new_user` | ~5M | Incremental ROI / CAC / CPA |
| 8 | `fact_ads_spend` | Daily ad spend by channel | `date, channel, ad_type, impressions, clicks, spend, cpc, cpa` | ~50K | Channel efficiency / budget |
| 9 | `fact_social_metrics` | Daily social metrics | `date, platform, followers, engagements, reach, posting_cnt` | ~20K | Social performance |
| 10 | `fact_touchpoints` | Attribution touchpoint paths | `tp_id, user_id, touch_time, channel, campaign_id, position_in_path` | ~30M | Multi-model attribution / Markov |
| 11 | `fact_page_modules` | Page module impressions/clicks | `date, page, module_id, module_area_pct, impressions, clicks` | ~10M | Module efficiency / clickability / DEA |
| 12 | `fact_cta_experiments` | Full-factorial CTA experiment | `exp_id, user_id, cta_color, cta_copy, cta_size, impression, clicked, converted` | ~200K | Factorial design / random forest |
| 13 | `fact_ab_assignments` | A/B assignment | `test_id, user_id, variant, assigned_at, converted` | ~200K | A/B testing / causal |
| 14 | `dim_user_tags` | User tags | `user_id, tag, tag_type, weight, updated_at` | ~1M | Tag system / profiling |
| 15 | `fact_ltv_labels` | LTV labels | `user_id, cohort, ltv_30d, ltv_90d, churn_90d` | ~250K | LTV / churn modelling |
| 16 | `fact_funnel_snapshot` | Funnel step snapshot | `period, step, user_cnt, prev_step_cnt, step_cvr` | ~5K | Funnel monitoring / drill-down |

### 3.3 Relationships (simplified ER)

```
dim_users (user_id) 1───∞ fact_events
                    1───∞ fact_transactions
                    1───∞ fact_deposit_withdraw
                    1───1  dim_kyc
                    1───∞ bridge_campaign_user ∞───1 fact_campaigns
                    1───∞ fact_touchpoints
                    1───∞ dim_user_tags
                    1───1  fact_ltv_labels
fact_ads_spend / fact_social_metrics / fact_page_modules  —— independent facts aggregated by date(+channel/module)
fact_cta_experiments / fact_ab_assignments                —— experiment-level facts
```

### 3.4 Data-quality checks (mandatory before use)

- **Consistency**: `GMV(fact_transactions)` must equal reported GMV; funnel counts must be monotonically decreasing;
- **Completeness**: `user_id` foreign-key hit rate ≥ 99.9%; no future timestamps;
- **Sanity**: amounts > 0, fees ≥ 0, `vip_level` matches trading-volume distribution;
- **Dedup**: dedupe events/touchpoints by `event_id / tp_id` so repetition does not inflate conclusions.

## 4. Metric System

| Layer | Metrics | Notes |
| --- | --- | --- |
| Acquisition | sign-ups, CAC, per-channel cost | CAC = channel spend / sign-ups from that channel |
| Activation | first-deposit rate, time-to-first-deposit, KYC success | first deposit = first successful `DEPOSIT/COIN_IN` |
| Trading | traders, trades, GMV, ARPU, ARPPU, AOV | window & dedup rules fixed |
| Retention | D1/D7/D30 retention, repurchase rate | calendar day/week windows |
| Value | LTV, top-contributor share, RFM | LTV split into 30d/90d |
| Churn | churn rate, survival probability, hazard | with survival analysis |
| Marketing | ROI, incremental ROI, iCAC, CPA | incremental needs a natural-growth baseline removed |

## 5. Implementation Plan

> Each phase is accepted by a **deliverable**, so value lands every phase instead of at the very end.

**Phase 0 · Data foundation**
1. Generate/ingest the 16 core tables and pass the data-quality checks (3.4);
2. Build a `dws` wide table (user-level + daily metrics) in SQL and freeze metric definitions;
3. Produce the *Metric Definitions* and *Data Dictionary* docs.

**Phase 1 · Describe**
4. Sign-up funnel: visit → register → KYC → first deposit → first trade, with per-step CVR and drop-off;
5. RFM segmentation + dimensionality reduction (PCA/UMAP + K-Means);
6. User flow graph (Sankey/graph) and behavioural-psychology analysis (key first-hour actions);
7. Deliverables: funnel dashboard + segmentation report.

**Phase 2 · Attribute**
8. Funnel attribution + Cox survival analysis to quantify each step's *hazard*;
9. Multi-model attribution comparison (first-touch / position / Markov), define error and pick a better-than-last-touch option;
10. Channel quality grading + Shapley attribution to flag inflated channels;
11. Deliverable: *Growth Attribution Report*.

**Phase 3 · Predict**
12. LTV: BG/NBD + Gamma-Gamma vs ML regression (with a technical selection note);
13. CAC/CPA/ROI forecasting and budget-elasticity model (Prophet trend+seasonality + elasticity regression);
14. Deliverables: LTV tier list + budget-elasticity curves.

**Phase 4 · Experiment & causal**
15. Full-factorial CTA experiment + random-forest feature importance; page-module efficiency (relative clickability / DEA);
16. A/B test (real split or simulation) + multiple logistic regression (with interactions);
17. Causal inference: incremental ROI for campaigns/airdrops (counterfactual / DID / propensity score);
18. Deliverable: *Experiments & Causal Findings*.

**Phase 5 · Tags & ops system**
19. Build the user tag system and profiling;
20. Design a complete VIP mechanism (tiering + benefits + reshuffle-stability check);
21. Land a refined-ops framework (segment → strategy → reach-out → review loop).

**Phase 6 · Decision tools**
22. A management *assumption simulator*: input channel-budget assumptions, output next-quarter OKR forecasts;
23. OKR attribution stripping and assist-value quantification (Markov vs last-touch vs Shapley).

**Phase 7 · Visualise & deliver**
24. Consolidate into dashboards + reports + a reusable codebase, and write up the methodology.

## 6. Key Methods & Technical Decisions

### 6.1 Segmentation: RFM + advanced dimensionality reduction

- **Base RFM**: bin and score `Recency / Frequency / Monetary`, map to 8 personas (champions / loyal / at_risk / hibernating / almost_lost …);
- **Dimensionality reduction**: standardise behavioural vectors (trading preference, active hours, asset mix, category preference), reduce with `PCA / UMAP`, cluster with `K-Means` (choose K via silhouette + business interpretability) to get *behavioural segments*, cross-checked against RFM;
- **Output**: persona cards (size, asset contribution, behaviour, ops advice).

### 6.2 Sign-up conversion funnel (CEX)

- Define four steps: `visit → register → KYC done → first deposit → first trade`;
- Drill down by device, region (`kyc_area`), channel and registration hour;
- Key move: **compare horizontally** across dimensions, then drill inward to locate the anomalous dimension;
- Output: `fact_funnel_snapshot` monitoring + alert rules.

### 6.3 Behavioural science & psychology

- **Behavioural sequence**: trace the *first hour after registration* (viewed the tutorial? clicked the first task? enabled security?), and use **subgroup t-tests** to compare high-churn vs high-retention users, surfacing **leading-indicator behaviours**;
- **Psychology lens**: map friction points to loss aversion / instant feedback / social proof, producing testable intervention hypotheses;
- **External validation**: reproduce conclusions on another period/region to avoid overfitting one batch.

### 6.4 User flow path graph

- Reconstruct in-session page/module transition sequences via recursive SQL `CTE` or a Python graph;
- Output Sankey/graph views to locate "high-frequency but low-conversion" and "low-frequency but high-conversion" paths;
- Combined with the funnel: the funnel says *how much* leaks, the flow graph says *from where*.

### 6.5 LTV prediction: BG/NBD or machine learning? (decision)

A clear technical selection problem; my strategy is **"probabilistic model as the base, ML for uplift"**:

| Dimension | BG/NBD + Gamma-Gamma | ML regression (GBDT/LightGBM) |
| --- | --- | --- |
| Best for | repeat purchase, sparse data, need `P(alive)` | rich features, non-linearity, high point accuracy |
| Pros | explainable; `P(alive)` + expected purchases | strong fit; absorbs many behavioural features |
| Cons | hard assumptions (Poisson/independence) | black-box, overfit risk, cold-start issues |
| Role here | baseline + churn detection | main predictor (BG/NBD outputs as features) |

- Evaluate on **out-of-time samples** (time-based split, not random) with MAE / RMSE / Spearman rank correlation;
- Output: `ltv_30d / ltv_90d` predictions + tier lists guiding spend and ops allocation.

### 6.6 ROI-variation attribution waterfall (MANOVA / ANOVA + contribution)

- Use **ANOVA / MANOVA** to test which dimensions (channel, region, campaign, device) significantly affect ROI variation;
- Turn variance explained (or a Shapley-style split) into each dimension's **contribution**, rendered as a waterfall — answering "ROI fell 3% this week; which dimension dragged it and by how much".

### 6.7 Funnel attribution + survival analysis (Cox regression)

- **Attribution in Funnel**: decompose the overall CVR change to each step and quantify each step's contribution to the end result;
- **Cox proportional hazards**: treat "time to reach the next step" as survival time and output the **hazard ratio** per step/persona;
- Output: a *hazard ranking* per step, so the highest-risk step gets fixed first.

### 6.8 Campaign / airdrop incremental ROI (causal inference & strategy evaluation)

- **Core question**: how much **net-new** volume did a campaign create, without counting users who would have traded anyway;
- Methods: propensity-score matching / difference-in-differences / regression discontinuity (chosen by data conditions) to build a counterfactual baseline;
- **Incremental ROI** = (campaign-period metric − counterfactual baseline) value / campaign cost;
- Also compare new-user LTV and existing-user repurchase in the campaign window vs the prior 4 weeks, removing natural growth.

### 6.9 Traffic attribution model comparison (first vs position vs Markov)

Only three models are compared, with an explicit error definition and a selection conclusion:

1. **First-touch**: rewards only the first touchpoint; biased toward acquisition;
2. **Position-based**: 40% first, 40% last, 20% middle;
3. **Markov chain / Removal Effect**: build a transition matrix over conversion paths, remove each channel one at a time and recompute overall CVR — the drop is that channel's contribution;

- **Error definition**: measure by (a) the deviation between recomputed CVR on a held-out sample and actual CVR, and (b) the variance/stability of channel contributions;
- **Goal**: pick a more reasonable primary attribution than last-touch and quantify how much brand-word / social assist value is under- or over-stated (e.g. `(Markov contribution − last-touch contribution) / last-touch contribution`);
- **One-line distinction**: Markov answers "**does it work without it**", Shapley answers "**how much better on average with it**", last-touch only answers "**who was last**".

### 6.10 Channel quality grading and Shapley attribution (flagging inflated channels)

- Build a **uniform channel profile** across all ads/traffic/social: CAC, first-deposit rate, retention, LTV, ROI;
- **Shapley attribution**: fairly split a channel portfolio's joint payoff across channels (average marginal contribution) to flag channels that look big but are inflated;
- Grade S/A/B/C with *scale up / hold / watch / cut* advice.

### 6.11 Ad cost vs social performance correlation (four steps)

1. **Step 1 base correlation**: sign of the `engagement` vs `CPC` relationship;
2. **Step 2 lag correlation**: does high engagement precede lower cost (good content goes viral → cost drops), or vice versa;
3. **Step 3 confounder control**: introduce "budget spike" as a control (higher budget → higher CPC, and artificially pushed engagement), using **partial correlation** to strip the budget effect;
4. **Step 4 segmentation**: compute the relationship separately for brand keywords vs generic keywords.

- Output a **conclusion matrix** (e.g. "a 1% lift in engagement lowers CPC by X on average, but only under organic engagement"), with confidence intervals and sample sizes.

### 6.12 Comparing registration efficiency across page modules

- **Remove position bias**: compute **Relative Clickability** = click share / impression-area share to test whether a module "punches its weight";
- Triangulate: `Hotjar` heatmaps; SQL `CTE` recursion to reconstruct user paths and account for ordering effects;
- Experiment support: A/B split comparing a module replacement under the same traffic as the historical period;
- **DEA**: treat each module as a decision unit with multiple inputs (impressions/area) and multiple outputs (registration + retention) to score overall efficiency rather than a single CVR.

### 6.13 CTA component conversion-attribute study

- **Full Factorial Design** over `colour × copy × size` to estimate **main and interaction effects**;
- **Random-forest feature importance** to rank attribute contribution to CVR, cross-validating the factorial results.

### 6.14 Multiple logistic regression + interactions + causal inference

- Model "converted / churned" with **multiple logistic regression**, with feature engineering (binning, WOE, frequency/time features);
- Explicitly model **interactions** (e.g. `channel × device`, `new-user × first-deposit method`) to avoid misreading interactions as main effects;
- Aim at **causation**: combine experiments or quasi-experimental designs to promote correlated terms into actionable causal ones.

### 6.15 A/B testing (real or simulated)

- If real splitting is impossible, run a **simulated experiment** by generating control/treatment from real distributions with an injected effect size, then run the full test procedure;
- Flow: sample-size & MDE estimate → assignment & SRM check → primary + guardrail metrics → `p-value / CI / effect size` → decision;
- Define **guardrail metrics** (risk, complaints, latency) so conversion wins do not damage experience.

### 6.16 User profiling + tag system + VIP mechanism

- **Tag system** with four types — factual (channel, device), statistical (RFM, LTV tier), model (segment, churn probability), rule-based (campaign participation) — stored in `dim_user_tags` with incremental updates by `tag_type`;
- **Profiling system** keyed on `user_id`, merging tags + key metrics for self-serve audience building;
- **VIP mechanism**: tiering (volume + assets + activity) → benefits → reshuffle-stability check, aligned with the dashboard definitions in project 02.

### 6.17 Refined-operations framework

```
Identify (tags/segments) → Strategy (segment × action × benefit) → Reach (in-app/push/email) → Review (A/B + incremental ROI) → Iterate
```

- Each strategy defines **target metric + guardrail metric + review cadence**;
- Manage via a segment × strategy matrix to avoid over-contacting the same user.

### 6.18 Quarterly budget elasticity & automation

- **Decompose**: `Prophet` splits each core KPI into trend + seasonality + residual;
- **Elasticity regression**: fit a "spend → marginal return" regression per channel to get the marginal return of each extra dollar;
- **Visualise**: marginal-return curves (with inflection points showing diminishing returns);
- **Management simulator**: a fool-proof interface — input channel-budget assumptions, output next-quarter core OKR KPIs (with confidence intervals) so management can self-serve scenario planning.

### 6.19 OKR attribution stripping and assist-value quantification

- **Attribution stripping = counterfactual simulation**: simulate "how much would CVR drop without this channel";
- **Transition matrix + removal effect**: estimate P(moving from channel A to B) → overall CVR → remove each channel and recompute → normalise into **percentage contribution**;
- **Assist value**: `(Markov contribution − last-touch contribution) / last-touch contribution`, producing conclusions like "brand words and a given social channel have X% higher assist value than the last-touch model suggests";
- **Methodological note**: Markov and Shapley answer different questions (see 6.9) — always state which one is used and how error is defined.

## 7. Development Docs (structure / env / run)

### 7.1 Planned layout

```
04_Customer_Analysis_BA/
├── README.md / README_EN.md      # This blueprint (zh / en)
├── data/
│   ├── schema.sql                # DDL
│   ├── generate_data.py          # seeded synthetic-data generator
│   └── sample/                   # small samples (large raw files gitignored)
├── sql/
│   ├── dws_user_wide.sql         # user-level wide table
│   └── metrics_dict.sql          # metric definitions
├── src/
│   ├── funnel/                   # conversion funnel (6.2)
│   ├── segmentation/             # RFM + dimensionality reduction (6.1)
│   ├── attribution/              # multi-model attribution + Shapley (6.9 / 6.10)
│   ├── survival/                 # Cox survival (6.7)
│   ├── ltv/                      # BG/NBD & ML (6.5)
│   ├── experiment/               # factorial / A/B (6.13 / 6.15)
│   └── budget/                   # budget elasticity & simulator (6.18)
├── notebooks/                    # exploration & reports
├── reports/                      # deliverables (charts / reports)
└── requirements.txt
```

### 7.2 Environment & dependencies

- Python ≥ 3.10; deps: `pandas` `numpy` `scipy` `scikit-learn` `statsmodels` `lifelines` (Cox) `lifetimes` (BG/NBD) `lightgbm` `prophet` `markovchain`/custom `umap-learn` `matplotlib` `plotly` `openpyxl`;
- Database: local `MySQL` / `PostgreSQL` (create tables from `sql/`).

### 7.3 How to run (planned)

```bash
# 1. create tables and generate data
mysql -u <user> -p < data/schema.sql
python data/generate_data.py --seed 42

# 2. run modules
python src/funnel/run.py
python src/segmentation/run.py
python src/attribution/run.py
python src/survival/run.py
python src/ltv/run.py
python src/budget/simulator.py
```

> The interfaces above are planned; files will be added across Phase 0–7, with unfinished parts marked `TODO`.

## 8. Expected Insights (placeholders)

> Templates to be filled with real numbers once executed.

- Biggest funnel leak: `TODO` (expected around "register → KYC" or "KYC → first deposit");
- Leading-indicator behaviour of high-churn users: `TODO` (likely related to not viewing the tutorial / not clicking the first task);
- Highest-LTV segment and its share: `TODO`;
- Channels under-valued by last-touch: `TODO` (brand words and social assist likely under-stated);
- Suspected inflated channels: `TODO`;
- Optimal budget allocation: `TODO` (likely constrained by diminishing marginal returns).

## 9. Risks, Boundaries & TODO

- **Data boundary**: synthetic data validates the methodology, not real business conclusions; production use must connect to the real warehouse and recalibrate distributions;
- **Causal boundary**: without real randomisation, quasi-experimental results must state assumptions (e.g. parallel trends) and avoid over-interpretation;
- **Attribution boundary**: multi-model attribution is sensitive to missing paths / cross-device gaps — assess data completeness first;
- **TODO**: `[ ]` real datasets, `[ ]` code, `[ ]` dashboard and report artefacts.

## 10. Deliverables

| Category | Artefact | Status |
| --- | --- | --- |
| Docs | this README (zh/en), data dictionary, metric definitions | ✅ blueprint done |
| Data | 16 core tables + seeded generator | ⏳ TODO |
| Code | 7 analysis modules under `src/` | ⏳ TODO |
| Reports | growth-attribution report, experiments & causal findings, LTV tiers | ⏳ TODO |
| Dashboards | funnel / segmentation / channel / budget-elasticity dashboards | ⏳ TODO |
| Tool | management assumption simulator | ⏳ TODO |

## 11. Reference Datasets & Further Reading

- Kaggle: *eCommerce events history in cosmetics shop* (behaviour distribution reference);
- Criteo / public multi-channel attribution datasets (touchpoint-sequence reference);
- public crypto exchange trading / deposit-withdrawal samples (amount & time distribution reference);
- Methods: BG/NBD (*Counting Your Customers the Easy Way*), Cox proportional hazards, Shapley-value attribution, Markov removal effect, Prophet decomposition.

---

> Note: this framework also applies to any "acquire → activate → trade → retain → repurchase" business — swap `dim_users` and the fact-table definitions to reuse it.
