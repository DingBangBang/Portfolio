# Data Dictionary

> Auto-generated from the actual Parquet files by `scripts/build_data_dictionary.py`.

- seed: `42`
- users: `20,000`
- days: `240`
- end date: `2026-09-30`

## `bridge_campaign_user` — Campaign participation bridge

- rows: **30,000**

| column | type |
| --- | --- |
| `id` | `string` |
| `campaign_id` | `string` |
| `user_id` | `string` |
| `join_time` | `timestamp[ns]` |
| `reward_amt` | `double` |
| `is_new_user` | `int64` |

## `dim_kyc` — KYC records

- rows: **20,000**

| column | type |
| --- | --- |
| `kyc_id` | `string` |
| `user_id` | `string` |
| `kyc_type` | `string` |
| `region` | `string` |
| `status` | `string` |
| `submit_time` | `timestamp[ns]` |
| `finish_time` | `timestamp[ns]` |

## `dim_user_tags` — User tags

- rows: **143,162**

| column | type |
| --- | --- |
| `user_id` | `string` |
| `tag` | `string` |
| `tag_type` | `string` |
| `weight` | `double` |

## `dim_users` — User master table

- rows: **20,000**

| column | type |
| --- | --- |
| `user_id` | `string` |
| `register_time` | `timestamp[ns]` |
| `register_device_type` | `string` |
| `register_channel` | `string` |
| `kyc_area` | `string` |
| `kyc_type` | `string` |
| `is_robot` | `int64` |

## `fact_ab_assignments` — A/B assignments

- rows: **20,000**

| column | type |
| --- | --- |
| `test_id` | `string` |
| `user_id` | `string` |
| `variant` | `string` |
| `assigned_at` | `timestamp[ms]` |
| `converted` | `int64` |

## `fact_ads_spend` — Daily ad spend by channel

- rows: **1,920**

| column | type |
| --- | --- |
| `date` | `date32[day]` |
| `channel` | `string` |
| `ad_type` | `string` |
| `impressions` | `int64` |
| `clicks` | `int64` |
| `spend` | `double` |
| `cpc` | `double` |
| `cpa` | `double` |
| `conversions` | `int64` |

## `fact_campaigns` — Campaign / airdrop definitions

- rows: **1,200**

| column | type |
| --- | --- |
| `campaign_id` | `string` |
| `name` | `string` |
| `channel` | `string` |
| `start_time` | `timestamp[ns]` |
| `end_time` | `timestamp[ns]` |
| `budget` | `double` |
| `reward_type` | `string` |

## `fact_cta_experiments` — CTA full-factorial experiment

- rows: **20,000**

| column | type |
| --- | --- |
| `exp_id` | `string` |
| `user_id` | `string` |
| `cta_color` | `string` |
| `cta_copy` | `string` |
| `cta_size` | `string` |
| `impression` | `int64` |
| `clicked` | `int64` |
| `converted` | `int64` |

## `fact_deposit_withdraw` — Deposit / withdrawal records

- rows: **26,711**

| column | type |
| --- | --- |
| `dw_id` | `string` |
| `user_id` | `string` |
| `record_type` | `string` |
| `asset` | `string` |
| `amount` | `double` |
| `status` | `string` |
| `fail_reason` | `string` |
| `created_at` | `timestamp[ns]` |

## `fact_events` — Behavioural event stream

- rows: **107,730**

| column | type |
| --- | --- |
| `event_id` | `string` |
| `user_id` | `string` |
| `event_time` | `timestamp[ns]` |
| `event_name` | `string` |
| `page` | `string` |
| `module_id` | `string` |
| `session_id` | `string` |
| `device` | `string` |

## `fact_funnel_snapshot` — Funnel step snapshot

- rows: **1,200**

| column | type |
| --- | --- |
| `period` | `date32[day]` |
| `step` | `string` |
| `user_cnt` | `int64` |
| `prev_step_cnt` | `int64` |
| `step_cvr` | `double` |

## `fact_ltv_labels` — LTV labels

- rows: **20,000**

| column | type |
| --- | --- |
| `user_id` | `string` |
| `cohort` | `string` |
| `ltv_30d` | `double` |
| `ltv_90d` | `double` |
| `churn_90d` | `int64` |

## `fact_page_modules` — Page module impressions/clicks

- rows: **7,200**

| column | type |
| --- | --- |
| `date` | `date32[day]` |
| `page` | `string` |
| `module_id` | `string` |
| `module_area_pct` | `double` |
| `impressions` | `int64` |
| `clicks` | `int64` |

## `fact_social_metrics` — Daily social metrics

- rows: **1,200**

| column | type |
| --- | --- |
| `date` | `date32[day]` |
| `platform` | `string` |
| `followers` | `int64` |
| `engagements` | `int64` |
| `reach` | `int64` |
| `posting_cnt` | `int64` |

## `fact_touchpoints` — Attribution touchpoints

- rows: **59,571**

| column | type |
| --- | --- |
| `tp_id` | `string` |
| `user_id` | `string` |
| `touch_time` | `timestamp[ns]` |
| `channel` | `string` |
| `campaign_id` | `string` |
| `position_in_path` | `int64` |
| `converted` | `int64` |

## `fact_transactions` — Transaction detail

- rows: **58,062**

| column | type |
| --- | --- |
| `tx_id` | `string` |
| `user_id` | `string` |
| `tx_time` | `timestamp[ns]` |
| `record_type` | `string` |
| `symbol` | `string` |
| `quote_amt` | `double` |
| `is_otc` | `int64` |
| `fee` | `double` |
