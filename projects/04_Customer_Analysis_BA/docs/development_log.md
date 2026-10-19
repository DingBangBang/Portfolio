# 开发过程记录（Development Log）

> 记录本项目从 0 到 1 落地过程中的技术决策、遇到的问题与修复，便于复现与接手。

## 0. 环境

- 独立 conda 环境：`customer_analysis_ba`（Python 3.10.22），与全局 Python 3.14 隔离；
- 所有命令均通过 `conda run -n customer_analysis_ba ...` 执行，不污染全局；
- 本地数据栈：**DuckDB 1.5.6 + dbt-duckdb 1.11.0**，不依赖云端数仓。

## 1. 技术决策

| # | 决策 | 原因 |
| --- | --- | --- |
| 1 | 用 DuckDB 模拟数仓（`warehouse.duckdb`） | 本地无法直连 BigQuery/Snowflake；DuckDB 单文件、零运维、可直接读 Parquet |
| 2 | dbt 分层 staging → intermediate → marts | 与 README 第 7 节一致，口径与特征工程集中在 SQL 层 |
| 3 | 数据规模取 20,000 用户 / 240 天 | README 标注 ~250K 用户是为生产设计；本地复现取 1/12 规模，保证每张表仍 ≥1,000 行且全链路可在分钟级跑完，可通过 `--n-users` 放大 |
| 4 | 归因的“转化”定义为**首次入金** | 若以“注册”为转化，所有触点用户都已注册，没有未转化样本，马尔可夫/归因退化；以首次入金为转化可同时得到转化与未转化路径，且不破坏外键完整性 |
| 5 | 马尔可夫移除效应采用“删除渠道后行归一化” | 标准做法；移除某渠道后重新归一化剩余转移概率，再比较整体转化概率的下降幅度 |
| 6 | Shapley 用精确枚举（8 个渠道 = 2^8 个联盟） | 渠道数少，精确解可算且无采样误差 |
| 7 | 预算弹性用 `log(spend)` 回归 + STL 分解 | Prophet 需额外 cmdstan、安装重；STL 能完成“趋势+季节+残差”拆解，接口与结论一致。Prophet 作为可选升级（`requirements-optional.txt`） |
| 8 | Docker 镜像只装看板运行依赖 | “除核心算法外一键启动”：镜像体积/构建时间可控；算法在宿主机 conda 环境运行 |
| 9 | Redis 缓存 TTL = 300s | 高频 LTV/渠道查询缓存 5 分钟，与需求一致；Redis 不可用时自动回退直查 DuckDB |
| 10 | 未配置 SMTP 时写本地 `reports/email_preview.html` | 不伪造发信成功；配置 `SMTP_*` 后自动真实发送 |

## 2. 问题与修复

### Bug 1 · `ValueError: cannot add indices of unequal length`

- **现象**：首次运行 `scripts/generate_mock_data.py` 在 `build_users` 报错；
- **原因**：`pd.Series(base)` 生成长度为 1、索引为 `RangeIndex(1)` 的 Series，与长度为 N 的 `TimedeltaIndex` 相加时索引长度不一致；
- **修复**：改为 `pd.Series(pd.Timestamp(base) + pd.to_timedelta(seconds, unit="s"))`，先生成 DatetimeIndex 再包成 Series；
- **验证**：重跑后 16 张表全部生成成功。

### Bug 2 · `KeyError: 'event_time'`

- **现象**：`behavioural_sequences` 在建模烟测中报错；
- **原因**：SQL 只 `select e.user_id, e.event_name, u.register_time`，后续却使用 `event_time` 计算“注册后 1 小时”；
- **修复**：SQL 补上 `e.event_time`。

### Bug 3 · scipy 二进制不兼容（macOS 27 / arm64）

- **现象**：`ImportError: dlopen(.../_spropack...so): section '__DATA/__thread_bss' has a zero-fill section type`，导致所有依赖 scipy 的模块（RFM、生存分析、LTV、ANOVA、DEA、A/B）失败；
- **原因**：pip 安装的 scipy 1.15.3 wheel 与当前 macOS 27.0.1 的链接器/加载器不兼容；
- **修复**：降级到 `scipy==1.13.1`（`--force-reinstall --no-deps`）；
- **验证**：修复后重跑烟测，所有模块通过（见第 4 节）。

## 3. 数据与数仓结果

### 3.1 数据规模（seed=42）

| 表 | 行数 | 表 | 行数 |
| --- | ---: | --- | ---: |
| dim_users | 20,000 | fact_campaigns | 1,200 |
| dim_kyc | 20,000 | bridge_campaign_user | 30,000 |
| fact_transactions | 58,062 | fact_ads_spend | 1,920 |
| fact_deposit_withdraw | 26,711 | fact_social_metrics | 1,200 |
| fact_events | 107,730 | fact_touchpoints | 59,844 |
| fact_page_modules | 7,200 | fact_cta_experiments | 20,000 |
| fact_ab_assignments | 20,000 | dim_user_tags | 143,162 |
| fact_ltv_labels | 20,000 | fact_funnel_snapshot | 1,200 |

- 漏斗末态：`visit 32,176 ≥ register 20,000 ≥ kyc 14,152 ≥ deposit 8,428 ≥ trade 7,608`（单调，校验通过）；
- 全量 GMV：`$78,755,325.65`。

### 3.2 dbt

- `dbt run`：27 个模型全部成功（8 张 table + 19 个 view）；
- `dbt test`：30 个测试全部 PASS（唯一性/非空/枚举/外键关系 + 4 个单测：漏斗单调、交易不早于注册、入金先于交易、金额非负）。

## 4. 运行验证

- 数据生成：✅；
- DuckDB 装载 16 张 raw 视图：✅；
- dbt run/test：✅ 27 / 30；
- 建模模块：✅（scipy 修复后全部通过，见 `reports/latest_run.json`）；
- Streamlit 看板 + Playwright 截图：见 `reports/dashboard_screenshot.png`；
- 三源通知：macOS 通知 ✅、浏览器打开 ✅、邮件（未配置 SMTP 时输出 `reports/email_preview.html`）。

## 5. 已知边界 / TODO

- 数据为合成数据，结论用于验证方法链路，不代表真实业务；
- 未接入真实广告平台/链上 API（可用 `scripts/generate_mock_data.py` 的接口替换为真实抓取）；
- Prophet 升级、UMAP 降维为可选依赖，当前分别用 STL 与 PCA 替代；
- DockerHub 推送需要 `docker login` 凭据。

## 6. 补充问题（联调阶段）

### Bug 4 · 马尔可夫归因退化

- **现象**：首版实现中 8 个渠道只有 1 个渠道份额非 0，其余全为 0；
- **原因**：移除渠道时把流入该渠道的转移概率“按行归一化改道”到其他渠道，等于让流量绕开被删渠道继续转化，移除效应趋近 0；
- **修复**：删除渠道时，把所有流入该渠道的转移改导向 `NULL`，并把该渠道自身出边也指向 `NULL`，再计算从 `START` 到 `CONVERSION` 的吸收概率；
- **验证**：8 个渠道份额均非 0，`markov_vs_last_pct` 出现合理的正负差异（affiliate +56.24%、organic -18.58%），5 折稳定性标准差 0.004~0.009。

### Bug 5 · BG/NBD 的 CLV 与 LTV 口径不一致

- **现象**：BG/NBD 的 MAE 达 25,735，远大于 LTV 均值；
- **原因**：Gamma-Gamma 的 `customer_lifetime_value` 输出的是用户**交易额**，而本项目的 LTV 定义为**手续费收入**；
- **修复**：将预测 CLV 乘以 0.1% 费率后再与 `ltv_90d` 比较；修复后 MAE 18.16、Spearman 0.73；
- **结论**：机器学习的点预测更准（MAE 1.75、Spearman 0.99），BG/NBD 保留用于 `P(alive)` 与期望购买次数。

### Bug 6 · LightGBM 缺 libomp

- **现象**：`OSError: Library not loaded: @rpath/libomp.dylib`，自动回退到 HistGradientBoosting；
- **修复**：`brew install libomp` 后 LightGBM 正常加载；代码仍保留 HistGradientBoosting 作为兜底。

### Bug 7 · 触点与转化不相关导致归因无信号

- **现象**：首版合成数据中触点渠道与用户是否入金相互独立，任何归因模型都只能得到噪声；
- **修复**：生成触点时以 65% / 50% 的概率把首/末触点设为用户实际注册渠道，使路径与转化相关；
- **验证**：归因模型出现可解释的渠道差异。

## 7. 最终验证结果

| 项目 | 结果 |
| --- | --- |
| 数据生成 | 16 张表，全部 ≥1,000 行 |
| 漏斗单调性 | visit 32,199 ≥ register 20,000 ≥ kyc 14,152 ≥ deposit 8,428 ≥ trade 7,608 |
| dbt run | 27/27 成功 |
| dbt test | 30/30 通过 |
| 建模模块 | 17/17 无异常（`errors: {}`） |
| 报表 | 15 个 CSV/JSON/MD 产物 |
| Streamlit | health OK，Playwright 截图 1440×2200 |
| macOS 通知 | 成功 |
| 浏览器打开 | 成功 |
| 邮件 | SMTP 未配置，已写本地预览 `reports/email_preview.html` |
| Docker | **未完成**：本机 Docker daemon 无法启动（重试 2 次仍失败），需人工处理 |

## 8. 看板重构阶段的问题与修复

### Bug 8 · 看板 6.1 崩溃（Plotly 索引长度不一致）

- **现象**：页面渲染到 6.1 就出现 `narwhals.exceptions.ShapeError: Expected object of length 7612, got length: 6000`；
- **原因**：`px.scatter(rfm.sample(6000), ..., color=rfm["cluster"])` 把「抽样后的 data_frame」和「全量 Series」混用；
- **修复**：先抽样并 `copy()`，再用列名字符串 `color="cluster"`。

### Bug 9 · Cox 导出列名不一致

- **现象**：6.7 报 `Value of 'y' is not the name of a column ... received: feature`；
- **原因**：`cph.summary` 的索引名是 `covariate`，`reset_index()` 不会生成 `index` 列，原来的 `rename(columns={"index":"feature"})` 无效；
- **修复**：显式把首列重命名为 `feature`，看板同时兼容 `feature` / `covariate`。

### Bug 10 · 流失模型标签泄漏（AUC=1.0）

- **现象**：首版 churn 模型 AUC 接近 1.0，明显不可信；
- **原因**：标签 `churn_90d` 由「距上次交易天数」定义，而特征里又包含 `recency_days` 与 `ltv_90d`，属于直接泄漏；
- **修复**：改为**未来 30 天流失**：以 `anchor-30d` 为 cutoff，特征只用 cutoff 之前的数据，标签为 cutoff 之后是否交易；
- **结果**：Logistic AUC 0.7889、LightGBM 0.7558，churn rate 15.6%，可信。

### Bug 11 · VIP 分层稳定性失真

- **现象**：等级不变率只有 13.75%，降级 16,287 人；
- **原因**：上一期用 `rank(pct=True)` 分层，而绝大多数用户上一期交易额为 0，并列排名被算成 1.0，直接落到 VIP3；
- **修复**：改用当前 90 天交易额的绝对分位数阈值（P50/P80/P95），两期使用同一组阈值；
- **结果**：不变率 78.75%，升级 3,830、降级 420，符合业务直觉。

### Bug 12 · KM 中位数 Infinity / NaN

- **现象**：整体首充率不足 50%，KM 中位生存时间为 `inf`，JSON 里出现 `Infinity`/`NaN`；
- **修复**：中位数/分位数统一做 `isfinite` 检查，非有限值转为 `null`，并补充 25% 分位时间；
- **结果**：整体 50% 首充在观察期内未达到，25% 用户在 1 天内完成首充。

### Bug 13 · Playwright 截图只截到视口

- **现象**：`dashboard_screenshot.png` 始终是 1440×2200，没有覆盖 20 个区块；
- **原因**：Streamlit 的滚动发生在 `section[data-testid="stMain"]` 内部，`full_page=True` 只按 document 高度截图；
- **修复**：截图前注入 CSS，把 `stMain` / `stAppViewContainer` / `body` 的 `height` 设为 `auto`、`overflow` 设为 `visible`，再 `full_page=True`；
- **结果**：截图为完整长图（高度随内容增长）。

## 9. 看板交互验证（Playwright）

- 20/20 锚点存在（`overview` + `s61`…`s619`）；
- 点击侧边栏「6.19 OKR 归因剥离」后，`section[data-testid="stMain"]` 的 `scrollTop` 从 0 变为 **21,884**，目标元素顶部约 60px，验证平滑滚动生效；
- 页面正文长度约 **13,500** 字符，19 个模块全部渲染；
- Docker 容器内同样 20/20 锚点、正文约 **13,500** 字符，验证镜像与挂载数据一致。
