# 04 · 交易所用户全生命周期分析（Customer_Analysis_BA）

> English version → [README_EN.md](./README_EN.md)

**_面向中心化交易所（CEX）的用户全生命周期分析蓝图：从注册转化漏斗、RFM 细分、流失生存分析，到 LTV 预测、营销归因与增量 ROI 测算。_**

- 主要语言：`Python` `SQL`
- 状态：**规划中**。本 README 是完整实现蓝图（背景 / 思路 / 数据 / 步骤 / 开发文档 / 交付物），代码与数据将按本文逐步落地。

---

## 1. 项目背景

交易所的增长团队里普遍存在三个「说不清」：

1. **说不清用户卡在哪**——注册量上去了，但真正入金的人很少，没人知道每一步到底漏掉多少人；
2. **说不清钱花得值不值**——广告、渠道、社媒、活动一起上，最后只能看「末次点击」，无法回答「这个渠道到底贡献了多少净新增」；
3. **说不清下个季度怎么花**——预算分配靠经验，管理层问「多花 10 万美金到某渠道，OKR 会怎样」，没人能给数字。

这个项目就是要用一套**可复现、可解释、能落地的分析体系**把这三点讲清楚，并把结论沉淀成工具（看板 / 模拟器 / 标签体系），而不是一次性报告。

目标读者：增长负责人、运营、市场投放与管理层。

## 2. 分析框架与实现思路

我按「**先看清 → 再归因 → 再预测 → 再决策**」四层递进来组织全案，避免一上来就堆模型：

```
第 0 层  数据底座      建表 / 埋点 / 口径统一 / 数据质量
   │
第 1 层  看清现状      指标体系 + 漏斗 + 用户分层(RFM) + 行为心理学 + 用户路径图
   │
第 2 层  解释归因     漏斗归因 + 生存分析(Cox) + 多归因模型对比 + 渠道质量(Shapley)
   │
第 3 层  预测         LTV 预测(BG/NBD vs 机器学习) + CAC/CPA/ROI 预测 + 因果推断(增量)
   │
第 4 层  决策落地      标签体系 + VIP 机制 + 精细化运营框架 + 预算弹性模拟器 + OKR 归因
```

贯穿全案的三条原则：

- **口径先行**：任何分析开始前先写清楚指标定义（分子/分母/时间窗/去重规则），所有结论共用一套口径；
- **相关 ≠ 因果**：凡是「A 导致了 B」的结论，必须经过反事实/随机实验/断点回归等因果方法验证；
- **服务于决策**：每个分析都要有一个「所以然后呢」的行动建议，否则不进交付物。

## 3. 数据设计

### 3.1 数据来源策略

我不直接依赖某一份现成数据，而是**「公开数据集打底 + 合成补齐」**：

- **公开数据集**（用于行为流、交易、归因的分布校准）：
  - Kaggle *eCommerce events history*（行为漏斗、品类、价格分布）；
  - Criteo / Marketing funnel 类归因数据集（多渠道触点顺序）；
  - 公开的加密交易所交易与充提样例（币种、金额、时间分布）。
- **合成补齐**（用于 CEX 特有字段与内部表）：用 `numpy`/`Faker` 按真实分布生成用户、交易、活动、广告花费、社媒指标等，保证**表间键一致、时间线合理、指标可推导**（例如 `GMV` 必须等于交易表聚合结果）。

> 所有生成脚本会固定随机种子（`random_state`），确保任何人复现得到同一份数据。

### 3.2 数据表（数据字典）

下表为 16 张核心表，**每张表 ≥ 1,000 行**，可直接支撑本文所有分析步骤。

| # | 表名 | 说明 | 关键字段 | 规模 | 主要用途 |
| --- | --- | --- | --- | --- | --- |
| 1 | `dim_users` | 用户主表 | `user_id, register_time, register_device_type, register_channel, kyc_area, kyc_type, is_robot, vip_level` | ~250K | 一切分析的起点 |
| 2 | `fact_events` | 行为埋点流（点击流） | `event_id, user_id, event_time, event_name(view/cart/…), page, module_id, session_id, device` | ~50M | 漏斗 / 路径图 / 行为序列 |
| 3 | `fact_transactions` | 交易明细 | `tx_id, user_id, tx_time, record_type(BUY/SELL/DEPOSIT/…), symbol, quote_amt, is_otc, fee` | ~8M | 交易 / GMV / 复购 |
| 4 | `fact_deposit_withdraw` | 充提记录 | `dw_id, user_id, record_type(DEPOSIT/COIN_IN/COIN_OUT/WITHDRAW), asset, amount, status, fail_reason, created_at` | ~3M | 首充转化 / 资金留存 |
| 5 | `dim_kyc` | 实名认证记录 | `kyc_id, user_id, kyc_type, region, status, submit_time, finish_time` | ~250K | 转化漏斗 / 合规口径 |
| 6 | `fact_campaigns` | 活动 / 空投定义 | `campaign_id, name, channel, start_time, end_time, budget, reward_type` | ~2K | 活动 ROI / 空投 |
| 7 | `bridge_campaign_user` | 活动参与明细 | `campaign_id, user_id, join_time, reward_amt, is_new_user` | ~5M | 增量 ROI / CAC / CPA |
| 8 | `fact_ads_spend` | 分渠道每日广告花费 | `date, channel, ad_type(brand/generic), impressions, clicks, spend, cpc, cpa` | ~50K | 渠道效率 / 预算弹性 |
| 9 | `fact_social_metrics` | 社媒每日指标 | `date, platform, followers, engagements, reach, posting_cnt` | ~20K | 社媒绩效 / 滞后相关 |
| 10 | `fact_touchpoints` | 归因触点序列 | `tp_id, user_id, touch_time, channel, campaign_id, position_in_path` | ~30M | 多归因模型 / 马尔可夫 |
| 11 | `fact_page_modules` | 页面模块曝光/点击 | `date, page, module_id, module_area_pct, impressions, clicks` | ~10M | 模块效率 / 相对可点击率 / DEA |
| 12 | `fact_cta_experiments` | CTA 全因子实验 | `exp_id, user_id, cta_color, cta_copy, cta_size, impression, clicked, converted` | ~200K | 全因子分析 / 随机森林 |
| 13 | `fact_ab_assignments` | A/B 分流 | `test_id, user_id, variant(control/treat), assigned_at, converted` | ~200K | A/B 检验 / 因果 |
| 14 | `dim_user_tags` | 用户标签 | `user_id, tag, tag_type, weight, updated_at` | ~1M | 标签体系 / 画像 |
| 15 | `fact_ltv_labels` | LTV 标签 | `user_id, cohort, ltv_30d, ltv_90d, churn_90d` | ~250K | LTV / 流失建模 |
| 16 | `fact_funnel_snapshot` | 漏斗步骤快照 | `period, step, user_cnt, prev_step_cnt, step_cvr` | ~5K | 漏斗监控 / 归因下钻 |

### 3.3 表关系（简化 ER）

```
dim_users (user_id) 1───∞ fact_events
                    1───∞ fact_transactions
                    1───∞ fact_deposit_withdraw
                    1───1  dim_kyc
                    1───∞ bridge_campaign_user ∞───1 fact_campaigns
                    1───∞ fact_touchpoints
                    1───∞ dim_user_tags
                    1───1  fact_ltv_labels
fact_ads_spend / fact_social_metrics / fact_page_modules  —— 按「日期(+渠道/模块)」聚合的独立事实表
fact_cta_experiments / fact_ab_assignments                —— 实验级事实表
```

### 3.4 数据质量校验（上线前必做）

- **一致性**：`GMV(fact_transactions)` 必须等于报表 GMV；漏斗各级人数必须单调递减；
- **完整性**：`user_id` 外键命中率 ≥ 99.9%；时间戳无未来值；
- **合理性**：金额 > 0、手续费 ≥ 0、`vip_level` 与交易额分布相符；
- **去重**：埋点与触点按 `event_id / tp_id` 去重，避免重复计数放大结论。

## 4. 指标体系

| 层级 | 指标 | 定义要点 |
| --- | --- | --- |
| 拉新 | 注册数、CAC、各渠道注册成本 | CAC = 渠道花费 / 该渠道带来注册数 |
| 激活 | 首充率、首充时效、KYC 成功率 | 首充 = 注册后首次 `DEPOSIT/COIN_IN` 成功 |
| 交易 | 交易人数、笔数、GMV、ARPU、ARPPU、AOV | 时间窗与去重规则统一 |
| 留存 | 次日/7日/30日留存、复购率 | 以自然日/自然周为窗 |
| 价值 | LTV、P99 用户贡献、RFM 分 | LTV 区分 30d/90d |
| 流失 | Churn rate、存活概率、流失风险系数 | 结合生存分析 |
| 营销 | ROI、增量 ROI、iCAC、CPA | 增量口径需剔除自然增长基线 |

## 5. 实现步骤（分阶段落地）

> 每个阶段都以「可交付结果」为验收标准，做完一阶段就能产生一次业务价值，而不是憋到最后。

**Phase 0 · 数据底座**
1. 生成 / 接入 16 张核心表，跑通数据质量校验（见 3.4）；
2. 用 SQL 落一个 `dws` 层宽表（用户级 + 日级指标），冻结指标口径；
3. 产出《指标口径说明》与《数据字典》。

**Phase 1 · 看清现状**
4. 注册转化漏斗：注册 → KYC → 首充 → 首笔交易，逐级拆 CVR 与流失；
5. RFM 分层 + 降维细分（PCA/UMAP + K-Means），输出用户分群；
6. 用户路径图（桑基/图）与行为心理学分析（首次 1 小时关键动作）；
7. 产出：漏斗看板 + 分群报告。

**Phase 2 · 解释归因**
8. 漏斗归因 + Cox 生存分析，量化每一步的「流失风险系数」；
9. 多归因模型对比（首次 / 位置 / 马尔可夫），定义误差并选出优于末次点击的方案；
10. 渠道质量分级 + Shapley 归因，识别注水渠道；
11. 产出：《增长归因报告》。

**Phase 3 · 预测**
12. LTV 预测：BG/NBD + Gamma-Gamma vs 机器学习回归（含技术选型对比）；
13. CAC / CPA / ROI 预测与预算弹性模型（Prophet 拆趋势+季节，叠加弹性回归）；
14. 产出：LTV 分层清单 + 预算弹性曲线。

**Phase 4 · 实验与因果**
15. CTA 全因子实验 + 随机森林特征重要性；页面模块效率（相对可点击率 / DEA）；
16. A/B 测试（真实分流或模拟）+ 多元 Logistic 回归（含交互效应）；
17. 因果推断：活动 / 空投的增量 ROI（反事实 / DID / 倾向得分）；
18. 产出：《实验与因果结论集》。

**Phase 5 · 标签与运营体系**
19. 搭建用户标签体系与画像系统；
20. 设计完整 VIP 机制（分层规则 + 权益 + 升降级稳定性校验）；
21. 落地精细化运营框架（分群 → 策略 → 触达 → 复盘闭环）。

**Phase 6 · 决策工具**
22. 管理层「假设模拟器」：输入渠道预算假设，输出下季度核心 OKR 预测；
23. OKR 归因剥离与助攻价值量化（Markov vs 末次点击 vs Shapley）。

**Phase 7 · 可视化与交付**
24. 汇总为看板 + 报告 + 可复用代码库，并沉淀方法论文档。

## 6. 关键分析方法与技术决策

### 6.1 用户细分：RFM + 高级降维

- **基础 RFM**：按 `Recency / Frequency / Monetary` 分箱打分，映射到 8 类人群（champions / loyal / at_risk / hibernating / almost_lost …）；
- **降维细分**：对用户行为向量（交易偏好、活跃时段、资产结构、品类偏好）做标准化后 `PCA / UMAP` 降维，再用 `K-Means`（以轮廓系数 + 业务解释性选 K），得到「行为分群」，与 RFM 交叉验证；
- **产出**：分群画像卡（人群规模、资产贡献、行为特征、运营建议）。

### 6.2 注册转化漏斗（CEX Conversion Funnel）

- 定义四级漏斗：`访问 → 注册 → 完成 KYC → 首次入金 → 首笔交易`；
- 分维度下钻：设备类型、地区（`kyc_area`）、渠道、注册时段；
- 关键对比：**横向对比**各维度 CVR，再由外向内下钻定位异常维度；
- 产出：漏斗监控表 `fact_funnel_snapshot` + 异常告警规则。

### 6.3 用户行为科学与心理学分析

- **行为序列**：追踪「注册后 1 小时内」的动作序列（是否查看教程、是否点击首次任务、是否绑定安全项），用**分群 T 检验**对比高流失 vs 高留存群体，找出**先行前兆行为**；
- **心理学视角**：把摩擦点映射到损失厌恶 / 即时反馈 / 社会证明等机制，给出可测试的干预假设；
- **外部验证**：用另一时段/另一地区数据复现结论，避免单批数据过拟合。

### 6.4 用户路径图（User Flow Path Graph）

- 用 SQL 的 `CTE` 递归或 Python 构图，还原 `session` 内的页面/模块跳转序列；
- 输出桑基图 / 图网络，定位「高频但低转化」与「低频但高转化」的路径；
- 与漏斗结合：漏斗告诉你「漏多少」，路径图告诉你「从哪漏」。

### 6.5 LTV 预测：BG/NBD 还是机器学习？（技术决策）

这是本项目一个明确的技术选型问题，我用「**先概率模型打底，再机器学习补强**」的策略：

| 维度 | BG/NBD + Gamma-Gamma | 机器学习回归（GBDT/LightGBM） |
| --- | --- | --- |
| 适合场景 | 重复购买、数据稀疏、需要「存活概率」 | 特征丰富、非线性、需要高精度点预测 |
| 优点 | 可解释、能给出 `P(alive)` 与期望购买次数 | 拟合能力强、可纳入大量行为特征 |
| 缺点 | 假设较硬（泊松/独立） | 黑箱、易过拟合、对冷启动不友好 |
| 本项目定位 | 基准线 + 流失判定 | 主预测器（用 BG/NBD 输出做特征） |

- 评估用 **时间外样本**（按时间切分，而非随机切分），指标用 MAE / RMSE / Spearman 排序相关；
- 产出：`ltv_30d / ltv_90d` 预测 + 分层清单，指导投放与运营资源分配。

### 6.6 ROI 波动归因瀑布图（MANOVA / ANOVA + 贡献度算法）

- 用 **ANOVA / MANOVA** 检验哪些维度（渠道、地区、活动、设备）对 ROI 波动有显著影响；
- 基于方差解释度或 Shapley 思路计算各维度**贡献度**，画成瀑布图，回答「这周 ROI 掉了 3%，是哪个维度拖累的、各自贡献多少」。

### 6.7 漏斗归因 + 生存分析（Cox 回归）

- **漏斗归因（Attribution in Funnel）**：把整体 CVR 变化拆解到每一步，量化各步骤对最终结果的贡献；
- **Cox 比例风险模型**：把「多久没走到下一步」作为生存时间，输出各步骤 / 各人群的**流失风险系数（hazard ratio）**；
- 产出：每一步的「流失风险排行榜」，优先修风险系数最高的环节。

### 6.8 活动 / 空投增量 ROI（因果推断与策略评估）

- **核心问题**：一次活动到底带来多少**净新增**交易量，而不是把「本来就会交易的人」也算进去；
- 方法：倾向得分匹配 / 双重差分（DID）/ 断点回归（视数据条件选择），构建反事实基线；
- **增量 ROI** = (活动期指标 − 反事实基线) 对应的收益 / 活动成本；
- 同时对比「活动期 vs 活动前 4 周」的新客 LTV 与老客复购率，剔除自然增长。

### 6.9 流量归因模型对比（首次 vs 位置 vs 马尔可夫）

只对比三个模型，并给出「误差」定义与选型结论：

1. **首次归因（First-touch）**：只奖励第一个触点，偏向拉新渠道；
2. **位置归因（Position-based）**：首尾各 40%、中间 20%，兼顾拉新与转化；
3. **马尔可夫链 / 移除效应（Removal Effect）**：把用户转化路径建成转移矩阵，逐个渠道「拿掉」后重算整体转化率，下降幅度即该渠道贡献；

- **误差定义**：以「留出真实转化样本的预测/回算 CVR 与实际 CVR 的偏差」以及「渠道贡献度的方差/稳定性」来衡量；
- **结论目标**：选出比末次点击更合理的主归因方案，并给出「品牌词 / 社媒助攻价值高估或低估多少」的量化结论（例：`(马尔可夫贡献 − 末次点击贡献) / 末次点击贡献`）。
- **三者区别一句话说清**：马尔可夫回答「**没有它行不行**」，Shapley 回答「**有了它平均好多少**」，末次点击只回答「**最后是谁**」。

### 6.10 渠道质量分级与 Shapley 归因（识别注水渠道）

- 对全部广告 / 流量渠道 / 社媒做**统一的渠道画像**：获客成本、首充率、留存、LTV、ROI 一览；
- **Shapley 归因**：把「渠道组合的联合收益」公平分摊到各渠道（边际贡献的平均），识别「看起来量大、其实注水」的渠道；
- 分级：S/A/B/C 四档，配套「加投 / 维持 / 观察 / 削减」建议。

### 6.11 广告成本与社媒绩效的相关性分析（四步法）

1. **Step 1 基础相关**：`engagement` 与 `CPC` 的相关性方向；
2. **Step 2 滞后相关（Lag Correlation）**：检验「高互动」是否先于「低成本」出现（好内容先火 → 后拉低成本），反之亦然；
3. **Step 3 混淆变量控制**：引入「预算突增」作为控制变量（预算越大通常 CPC 越高、互动也被人为推高），用**偏相关（Partial Correlation）**剥离预算影响；
4. **Step 4 细分场景**：分别计算「品牌词」与「通用词」广告下的相关差异。

- 输出**结论矩阵**（形如：「互动率每提升 1%，CPC 平均下降 X，但该结论仅在自然互动场景下成立」），并标注置信区间与样本量。

### 6.12 不同页面模块注册效率比较

- **消除位置偏差**：计算**相对可点击率（Relative Clickability）** = 点击占比 / 曝光面积占比，判断模块是否「名不副实」；
- 多源验证：`Hotjar` 热力图验证点击分布；SQL `CTE` 递归还原用户路径以理解模块顺序效应；
- 实验佐证：A/B 分流对比「历史同期相同流量下的模块替换效果」；
- **DEA 数据包络分析**：把模块视为「多投入（曝光/面积）→ 多产出（注册+留存）」的决策单元，评估综合效率而非单一 CVR。

### 6.13 CTA 组件转化率属性调查

- **全因子实验设计（Full Factorial Design）**：对 CTA 的 `颜色 × 文案 × 尺寸` 做全因子组合，估计**主效应与交互效应**；
- **随机森林特征重要性**：对 CTA 各属性做重要性排序，量化「哪个属性对 CVR 贡献最大」，与全因子结论互相印证。

### 6.14 多元 Logistic 回归 + 交互效应 + 因果推断

- 以「是否转化 / 是否流失」为因变量做**多元 Logistic 回归**，做特征工程（分箱、WOE、频次/时间特征）；
- 显式建模**交互效应**（如 `渠道 × 设备`、`新客 × 首充方式`），避免把交互误读成主效应；
- 结论以**因果**为目标：结合实验或准实验设计，把「相关项」升级为「可行动的因果项」。

### 6.15 A/B 测试（真实实验或模拟）

- 若无法真实分流，则用**模拟实验**：按真实分布生成对照组与实验组，注入预设效应量，再走完整检验流程；
- 流程：样本量与 MDE 预估 → 分流与 SRM 检查 → 主指标 + 护栏指标 → `p 值 / 置信区间 / 效应量` → 决策；
- 明确**护栏指标**（如风险/客诉/延迟）避免「涨了转化、伤了体验」。

### 6.16 用户画像系统 + 标签体系 + VIP 机制

- **标签体系**：分为事实标签（注册渠道、设备）、统计标签（RFM、LTV 分层）、模型标签（分群、流失概率）、规则标签（活动参与）四类，落到 `dim_user_tags`，支持按 `tag_type` 增量更新；
- **画像系统**：以 `user_id` 为主键，合并标签 + 关键指标，供运营自助圈人；
- **VIP 机制**：分层规则（交易额 + 资产 + 活跃）→ 权益设计 → 升降级稳定性校验（避免大客户抖动），与项目 02 的看板口径保持一致。

### 6.17 精细化运营框架

```
识别（标签/分群） → 策略（人群×动作×权益） → 触达（站内/推送/邮件） → 复盘（A/B + 增量 ROI） → 迭代
```

- 每个策略都要定义**目标指标 + 护栏指标 + 复盘周期**；
- 用「人群 × 策略」矩阵管理，避免重复打扰同一用户。

### 6.18 季度预算弹性测算与自动化

- **拆解**：用 `Prophet` 把核心 KPI 拆成趋势 + 季节性 + 残差；
- **弹性回归**：对每个渠道建立「花费 → 边际回报」回归，得到「每多花 1 美元在不同渠道的边际回报」；
- **可视化**：边际回报曲线（含拐点，识别边际递减）；
- **管理层模拟器**：提供一个傻瓜接口——输入各渠道预算假设，直接输出下季度核心 OKR KPI 的变化与影响（含置信区间），让管理层可自助推演。

### 6.19 OKR 归因剥离与量化助攻价值

- **归因剥离 = 反事实模拟**：模拟「如果没有这个渠道，转化率会掉多少」；
- **转移矩阵 + 移除效应**：统计「从 A 渠道走到 B 渠道」的概率 → 算整体转化率 → 逐个渠道移除重算 → 归一化为**百分比贡献度**；
- **助攻价值**：`(马尔可夫贡献度 − 末次点击贡献度) / 末次点击贡献度`，输出形如「品牌词与某社媒的助攻价值比末次点击模型高 X%」的结论；
- **方法论提醒**：Markov 与 Shapley 回答的是不同问题（见 6.9），汇报时务必写清用的是哪一种、误差如何定义。

## 7. 开发文档（工程结构 / 环境 / 运行）

### 7.1 规划目录结构

```
04_Customer_Analysis_BA/
├── README.md / README_EN.md      # 本蓝图（中/英）
├── data/
│   ├── schema.sql                # 建表 DDL
│   ├── generate_data.py          # 固定随机种子的合成数据脚本
│   └── sample/                   # 小体量样例（原数据大文件 gitignore）
├── sql/
│   ├── dws_user_wide.sql         # 用户级宽表
│   └── metrics_dict.sql          # 指标口径
├── src/
│   ├── funnel/                   # 转化漏斗（6.2）
│   ├── segmentation/             # RFM + 降维分群（6.1）
│   ├── attribution/              # 多归因模型 + Shapley（6.9 / 6.10）
│   ├── survival/                 # Cox 生存分析（6.7）
│   ├── ltv/                      # BG/NBD 与机器学习（6.5）
│   ├── experiment/               # 全因子 / A/B（6.13 / 6.15）
│   └── budget/                   # 预算弹性与模拟器（6.18）
├── notebooks/                    # 探索与报告
├── reports/                      # 交付产物（图表 / 报告）
└── requirements.txt
```

### 7.2 环境与依赖

- Python ≥ 3.10；依赖：`pandas` `numpy` `scipy` `scikit-learn` `statsmodels` `lifelines`（Cox）`lifetimes`（BG/NBD）`lightgbm` `prophet` `markovchain`/自实现 `umap-learn` `matplotlib` `plotly` `openpyxl`；
- 数据库：本地 `MySQL` / `PostgreSQL`（用 `sql/` 下的 DDL 建表）。

### 7.3 运行方式（规划）

```bash
# 1. 建表并生成数据
mysql -u <user> -p < data/schema.sql
python data/generate_data.py --seed 42

# 2. 各模块
python src/funnel/run.py
python src/segmentation/run.py
python src/attribution/run.py
python src/survival/run.py
python src/ltv/run.py
python src/budget/simulator.py
```

> 说明：以上为规划接口，实际文件将随 Phase 0~7 逐步补齐；未完成处会以 `TODO` 标注。

## 8. 预期 Insights（示例结论位）

> 以下为模板与待填项，正式执行后回填真实数字。

- 漏斗最大漏损点：`TODO`（预计在「注册 → 完成 KYC」或「KYC → 首次入金」）；
- 高流失人群的先行前兆行为：`TODO`（预计与「未查看教程 / 未点击首次任务」相关）；
- LTV 最高的分群与占比：`TODO`；
- 被末次点击低估的渠道：`TODO`（预计品牌词与社媒助攻被低估）；
- 疑似注水渠道：`TODO`；
- 预算最优分配建议：`TODO`（预计受边际递减约束）。

## 9. 风险、边界与 TODO

- **数据边界**：合成数据能验证方法链路，但不能替代真实业务结论；正式使用需接入真实数仓并重新校准分布；
- **因果边界**：无真实随机实验时，准实验结论需标注假设（平行趋势等），避免过度解读；
- **归因边界**：多归因模型对「路径缺失 / 跨设备」敏感，需先评估数据完整度；
- **TODO**：`[ ]` 待补真实数据集、`[ ]` 待补代码、`[ ]` 待补看板与报告产物。

## 10. 交付物清单

| 类别 | 产物 | 状态 |
| --- | --- | --- |
| 文档 | 本 README（中/英）、数据字典、指标口径说明 | ✅ 蓝图完成 |
| 数据 | 16 张核心表 + 合成脚本（固定种子） | ⏳ TODO |
| 代码 | `src/` 下 7 大分析模块 | ⏳ TODO |
| 报告 | 增长归因报告、实验与因果结论集、LTV 分层清单 | ⏳ TODO |
| 看板 | 漏斗 / 分群 / 渠道 / 预算弹性看板 | ⏳ TODO |
| 工具 | 管理层「假设模拟器」 | ⏳ TODO |

## 11. 参考数据集与延伸阅读

- Kaggle：*eCommerce events history in cosmetics shop*（行为流分布参考）；
- Criteo / 公开多渠道归因数据集（触点序列参考）；
- 公开的加密交易所交易 / 充提样例数据（金额与时间分布参考）；
- 方法参考：BG/NBD（*Counting Your Customers the Easy Way*）、Cox 比例风险模型、Shapley 值归因、Markov 移除效应、Prophet 时间序列分解。

---

> 备注：本项目的分析框架同样适用于其它「拉新 → 激活 → 交易 → 留存 → 复购」型业务，替换 `dim_users` 与事实表口径即可复用。

---

## 12. 快速开始（Clone 后逐步复现）

> 以下命令全部在 `projects/04_Customer_Analysis_BA/` 目录下执行；环境已隔离为 `customer_analysis_ba`，不会污染全局 Python。

### 12.1 一次性环境准备

```bash
cd projects/04_Customer_Analysis_BA
conda create -n customer_analysis_ba python=3.10 -y
conda activate customer_analysis_ba
pip install -r requirements.txt

# macOS 若出现 scipy dlopen 报错（__thread_bss），降级到兼容版本：
# pip install --force-reinstall --no-deps scipy==1.13.1

# 可选：LightGBM 在 macOS 需要 libomp；没有则自动回退到 HistGradientBoosting
# brew install libomp

# 可选：看板截图用 Playwright + 本机 Chrome
pip install playwright   # 已安装 Chrome 时无需再下载 chromium
```

### 12.2 生成数据 → 装载 DuckDB → dbt

```bash
python scripts/generate_mock_data.py          # 16 张表 → data/raw/*.parquet（seed=42）
python scripts/load_raw_to_duckdb.py          # 建 raw schema 视图 → warehouse.duckdb

cd dbt_project
DUCKDB_PATH=../warehouse.duckdb dbt run  --profiles-dir .
DUCKDB_PATH=../warehouse.duckdb dbt test --profiles-dir .
cd ..
```

### 12.3 一键跑完整流水线（数据 → dbt → 建模 → 报表 → 通知）

```bash
python main.py                 # 完整运行（复用已有数据）
python main.py --regenerate    # 重新生成数据
python main.py --no-email      # 不发邮件，只写本地预览
python main.py --skip-dbt      # 复用已构建的 marts
```

产出：`reports/`（KPI、归因、渠道、LTV、生存分析、实验、预算弹性、data dictionary 链接）、`reports/dashboard_screenshot.png`、`reports/email_preview.html`、`reports/latest_run.json`。

### 12.4 启动看板

```bash
streamlit run dashboards/app.py
# http://localhost:8501
```

### 12.5 Docker 一键启动（看板 + Redis）

```bash
docker compose up -d --build
# 看板 http://localhost:8501 ，Redis localhost:6379
```

> 注意：Docker 镜像只包含看板运行依赖（见 `requirements-docker.txt`），核心算法仍在宿主机 conda 环境运行；`warehouse.duckdb` 通过 volume 挂载。

---

## 13. 工程实现（真实目录）

```
04_Customer_Analysis_BA/
├── main.py                     # 端到端编排器
├── requirements.txt            # 全量依赖
├── requirements-docker.txt     # 镜像依赖
├── docker-compose.yml          # Redis + Streamlit
├── Dockerfile                  # 看板镜像
├── scripts/
│   ├── generate_mock_data.py   # 16 张表合成（固定 seed）
│   ├── load_raw_to_duckdb.py   # Parquet → DuckDB raw 视图
│   ├── build_data_dictionary.py
│   └── run_daily.sh            # 手动触发的日更脚本
├── dbt_project/
│   ├── models/staging/         # 16 个 stg_* 模型
│   ├── models/intermediate/    # int_user_funnel / int_user_rfm / int_channel_performance
│   ├── models/marts/           # 8 个 mart_* 模型
│   ├── tests/                  # 4 个数据质量单测
│   └── profiles.yml            # dbt-duckdb
├── src/
│   ├── modeling.py             # README 第 6 节全部算法
│   └── analysis.py             # KPI / insights / 报表导出
├── dashboards/app.py           # Streamlit（Mart + Redis）
├── notifications/notifier.py   # macOS 通知 / 浏览器 / HTML 邮件 / 截图
├── config/settings.py
├── docs/
│   ├── development_log.md      # 开发过程记录
│   ├── data_dictionary.md / _EN.md
│   └── scheduling.md           # cron / launchd（默认手动触发）
├── data/raw/                   # 生成数据（gitignore）
├── warehouse.duckdb            # 本地数仓（gitignore）
└── reports/                    # 所有产物
```

---

## 14. 运行结果与核心 Insights（seed=42，20,000 用户 / 240 天）

> 数据为**合成数据**，用于验证方法与工程链路；结论口径与真实业务一致，但数值不代表真实经营结果。

### 14.1 数据与数仓

| 表 | 行数 | 表 | 行数 |
| --- | ---: | --- | ---: |
| `dim_users` | 20,000 | `fact_campaigns` | 1,200 |
| `dim_kyc` | 20,000 | `bridge_campaign_user` | 30,000 |
| `fact_transactions` | 58,062 | `fact_ads_spend` | 1,920 |
| `fact_deposit_withdraw` | 26,711 | `fact_social_metrics` | 1,200 |
| `fact_events` | 107,730 | `fact_touchpoints` | 59,844 |
| `fact_page_modules` | 7,200 | `fact_cta_experiments` | 20,000 |
| `fact_ab_assignments` | 20,000 | `dim_user_tags` | 143,162 |
| `fact_ltv_labels` | 20,000 | `fact_funnel_snapshot` | 1,200 |

- `dbt run`：**27/27** 模型成功；`dbt test`：**30/30** 通过（唯一性、非空、枚举、外键 + 4 个业务单测）；
- 全量 GMV：**$78,755,325.65**；手续费收入：**$78,755.33**。

### 14.2 核心 KPI（自动写入 `reports/kpi_summary.json`）

| 指标 | 数值 | 指标 | 数值 |
| --- | ---: | --- | ---: |
| 注册用户 | 20,000 | KYC 完成率 | 70.78% |
| 首次入金转化率 | **42.14%** | 入金→首笔交易 | **90.32%** |
| 交易用户 | 7,612 | ARPU / ARPPU | $3.94 / $10.35 |
| 平均 LTV(90d) | $3.23 | 90 天流失率 | **62.21%** |
| AOV | $1,356.40 | 人均 GMV（交易用户） | $10,346.21 |

### 14.3 转化漏斗（最后一天快照）

| 步骤 | 人数 | 相对上一步 CVR |
| --- | ---: | ---: |
| visit | 32,199 | — |
| register | 20,000 | 62.11% |
| kyc | 14,152 | 70.76% |
| deposit | 8,428 | **59.55%** |
| trade | 7,608 | 90.27% |

> **最大漏损在 KYC → 首次入金**：流失 **5,724 人**。这是最值得优先优化的环节。

### 14.4 RFM + 降维分群

- K-Means 自动选 `k=3`（轮廓系数 **0.3746**，PCA 两维解释 **84.72%** 方差）；
- 三个行为分群：

| cluster | 用户数 | 平均累计交易额 | 平均 LTV(90d) | 解读 |
| ---: | ---: | ---: | ---: | --- |
| 0 | 806 | $6,772.92 | $4.71 | 低频高额，需激活频次 |
| 1 | 4,294 | $6,932.41 | $5.80 | 主力大众人群 |
| 2 | 2,512 | $17,328.26 | $14.26 | 高价值核心人群，重点维护 |

### 14.5 四归因模型对比（首次 / 末次 / 位置 / 马尔可夫）

| 渠道 | 首次归因 | 末次归因 | 位置归因 | 马尔可夫 | 马尔可夫 vs 末次 |
| --- | ---: | ---: | ---: | ---: | ---: |
| organic | 28.18% | 26.85% | 27.09% | 21.86% | **-18.58%** |
| referral | 17.55% | 16.67% | 16.74% | 14.99% | -10.11% |
| google_ads | 14.81% | 15.14% | 15.05% | 15.43% | +1.88% |
| brand_search | 12.06% | 11.81% | 11.79% | 11.39% | -3.52% |
| twitter | 9.58% | 10.56% | 10.32% | 11.89% | +12.64% |
| telegram | 7.45% | 7.81% | 7.73% | 9.25% | +18.45% |
| kol | 6.72% | 7.27% | 7.21% | 9.11% | +25.28% |
| affiliate | 3.67% | 3.89% | 4.08% | 6.08% | **+56.24%** |

- **误差定义**：5 折重采样的渠道份额标准差（`stability_std`，均在 0.004~0.009，稳定）+ 折均值与全量份额的平均绝对偏差（`reconstruction_error`，均 < 0.0002）；
- **结论**：末次点击显著低估 affiliate / kol / telegram 的“助攻价值”，同时高估 organic / referral；因此主归因采用**马尔可夫移除效应**，末次点击只作为对照基线。

### 14.6 渠道质量分级与 Shapley 归因

| 渠道 | Shapley 份额 | ROI | CPA | 分级 | 注水标记 |
| --- | ---: | ---: | ---: | :---: | :---: |
| organic | 26.52% | 7.96% | $129.09 | **S** |  |
| referral | 17.14% | 5.14% | $207.32 | **S** |  |
| google_ads | 14.57% | 2.92% | $279.32 | A |  |
| brand_search | 11.23% | 2.62% | $314.88 | A |  |
| twitter | 10.12% | 1.94% | $424.66 | B | ✅ |
| kol | 7.87% | 1.25% | $706.32 | B | ✅ |
| telegram | 7.74% | 1.35% | $605.75 | C | ✅ |
| affiliate | 4.81% | 0.49% | $1,679.76 | C | ✅ |

> Shapley 回答「有了它平均好多少」，马尔可夫回答「没有它行不行」；这里两者交叉验证，指向同一批高价值渠道（organic / referral）与高 CPA 渠道（affiliate / kol / telegram）。

### 14.7 LTV 预测：LightGBM vs BG/NBD

| 模型 | MAE | RMSE | Spearman | 训练 / 测试 |
| --- | ---: | ---: | ---: | ---: |
| **LightGBM** | **1.7451** | **2.4277** | **0.9914** | 6,106 / 1,506 |
| BG/NBD + Gamma-Gamma | 18.1617 | 51.3077 | 0.7319 | 7,612 / 7,586 |

- 采用**时间外样本**切分（按注册日期 80/20），不是随机切分；
- **技术结论**：点预测用 LightGBM；BG/NBD 的价值在 `P(alive)` 与「期望购买次数」，用于流失判定与冷启动兜底，而不是直接拼 MAE。

### 14.8 生存分析（Cox 比例风险）

> 事件 = 首次入金；`hazard_ratio > 1` 表示相对基准渠道（affiliate）更快完成入金。

| 协变量 | Hazard Ratio | p 值 |
| --- | ---: | ---: |
| register_channel = referral | 3.133 | <0.001 |
| register_channel = organic | 2.810 | <0.001 |
| register_channel = brand_search | 2.739 | <0.001 |
| register_channel = google_ads | 1.721 | <0.001 |
| register_channel = twitter | 1.342 | <0.001 |
| register_channel = telegram | 1.331 | <0.001 |
| register_device_type = ios | 1.200 | <0.001 |
| register_channel = kol | 1.098 | 0.147（不显著） |

### 14.9 实验与因果

**A/B 测试（注册 CTA）**

| 变体 | 样本 | 转化 | CVR |
| --- | ---: | ---: | ---: |
| control | 9,942 | 976 | 9.82% |
| treat | 10,058 | 1,350 | **13.42%** |

- 绝对提升 **+3.61pp**，相对提升 **+36.72%**，`z=7.952`，`p≈1.78e-15`，95% CI **[+2.72pp, +4.49pp]**；
- SRM 检查 `p=1.0`（分流均衡），可全量。

**CTA 全因子实验（18 个组合）**

| 因子 | 最优水平 | CVR | 最差水平 | CVR |
| --- | --- | ---: | --- | ---: |
| 颜色 | green | **5.09%** | red | 4.24% |
| 文案 | claim_bonus | **5.03%** | start_trading | 4.39% |
| 尺寸 | large | **5.14%** | small | 4.32% |

- 随机森林重要性排序：`cta_color_red` 0.174、`cta_color_green` 0.154、`cta_copy_claim_bonus` 0.134；
- **注意**：重要性高 ≠ 边际 CVR 高（树模型会捕捉交互与不平衡），两者需结合看。

### 14.10 季度预算弹性

- 方法：`conversions ~ log(spend)` 分渠道回归 + STL 分解（趋势/季节/残差）；
- 当前每日边际转化/美元：affiliate **0.2386**、twitter 0.2310、telegram 0.2133、kol 0.2100、organic 0.2078、referral 0.1914、brand_search 0.1885、google_ads 0.1872；
- **关键提醒**：affiliate 边际转化最高，但 ROI 最低（0.49%）、CPA 最高（$1,680）——说明它带来的是“便宜但低价值”的转化，**不能只用边际转化做预算决策**，必须结合 LTV/ROI。

### 14.11 活动 / 空投增量 ROI（DID）

| 活动 | 参与人数 | 增量收入 | 增量 ROI |
| --- | ---: | ---: | ---: |
| google_ads_campaign_0739 | 38 | +$5,613.99 | **+5.19** |
| google_ads_campaign_0916 | 38 | -$408.01 | -0.56 |
| organic_campaign_0534 | 39 | -$2,858.27 | -2.58 |
| organic_campaign_1059 | 39 | -$5,222.67 | -3.69 |
| organic_campaign_0645 | 45 | -$19,614.27 | -13.00 |

> 方法：参与者 vs 同渠道非参与者，比较活动前/后 4 周人均交易额，做双重差分（DID）；结果表明多数活动**没有跑赢自然增长基线**，只有少数渠道活动有正增量——这正是“看总收益会高估活动效果”的例证。

### 14.12 核心洞察汇总（data-driven）

1. **最大漏损在 KYC → 首次入金（流失 5,724 人，CVR 59.55%）**：优先做首充奖励、简化入金流程、对已 KYC 未入金人群定向触达；
2. **90 天流失率 62.21%**：需要建立沉默用户召回机制（按 RFM 的 at_risk / hibernating 分层）；
3. **末次点击低估助攻渠道**：affiliate +56.24%、kol +25.28%、telegram +18.45%，预算评审应改用马尔可夫/Shapley；
4. **渠道注水**：twitter / kol / telegram / affiliate 的 Shapley 份额与 ROI 双低，建议降级/削减并做反作弊核验；
5. **LTV 选型**：LightGBM 点预测最优（MAE 1.75、Spearman 0.99），BG/NBD 负责 `P(alive)`；
6. **A/B 可全量**：注册 CTA 实验相对提升 36.72%，p 值远小于 0.05；
7. **预算不能唯边际转化**：affiliate 边际转化最高但 ROI 最低，应按「边际回报 × LTV」联合决策。

---

## 15. 开发文档与过程记录

| 文档 | 内容 |
| --- | --- |
| [docs/development_log.md](./docs/development_log.md) | 技术决策、Bug 发现与修复（索引长度、缺失字段、scipy 二进制、BG/NBD 收敛、Markov 退化等） |
| [docs/data_dictionary.md](./docs/data_dictionary.md) / [EN](./docs/data_dictionary_EN.md) | 16 张表的字段与类型（从实际 Parquet 自动生成） |
| [docs/scheduling.md](./docs/scheduling.md) | cron / launchd 配置（默认保持手动触发） |
| [reports/insights.md](./reports/insights.md) | 每次运行自动生成的洞察与建议 |
| [reports/latest_run.json](./reports/latest_run.json) | 最近一次运行的步骤、错误、KPI、通知状态 |

### 15.1 关键 Bug 与修复（摘要）

1. **`ValueError: cannot add indices of unequal length`**：`pd.Series(base)` 长度为 1，与 N 长度 timedelta 相加失败 → 改为先生成 DatetimeIndex 再包 Series；
2. **`KeyError: event_time`**：行为序列 SQL 漏选 `event_time` → 补字段；
3. **scipy `__thread_bss` dlopen 失败**（macOS 27 / arm64）：scipy 1.15.3 wheel 不兼容 → 降级 `scipy==1.13.1`；
4. **BG/NBD 不收敛**：penalizer 过小 → 改为 0.5/1.0/2.0 自动重试；
5. **马尔可夫归因退化**（七成渠道为 0）：原实现把流量“改道”而非“切断” → 改为删除渠道后将其流入/流出全部导向 NULL，再算吸收概率；
6. **BG/NBD 的 CLV 与 LTV 口径不一致**：Gamma-Gamma 输出的是交易额，而 LTV 定义是手续费 → 乘 0.1% 费率后再比较；
7. **LightGBM 缺 libomp**：`brew install libomp` 后恢复；同时保留 `HistGradientBoosting` 作为无 libomp 的兜底。

---

## 16. 交付物清单（实际产出）

| 类别 | 产物 | 状态 |
| --- | --- | :---: |
| 环境 | `customer_analysis_ba`（Python 3.10.22） | ✅ |
| 数据 | `scripts/generate_mock_data.py` + 16 张 Parquet（seed=42） | ✅ |
| 数仓 | `warehouse.duckdb` + raw/staging/intermediate/marts | ✅ |
| dbt | 27 个模型 + 30 个测试 | ✅ 全部通过 |
| 算法 | `src/modeling.py`（§6 全部方法，含 4 归因模型） | ✅ |
| 分析 | `src/analysis.py`（KPI / insights / 报表导出） | ✅ |
| 编排 | `main.py`（数据→dbt→建模→报表→通知） | ✅ |
| 看板 | `dashboards/app.py`（Streamlit + Redis 缓存） | ✅ |
| 通知 | macOS 通知 / 浏览器 / HTML 邮件 / Playwright 截图 | ✅（邮件待配 SMTP） |
| 报表 | `reports/` 15 个 CSV/JSON/MD + 看板截图 | ✅ |
| 文档 | README 中英、开发日志、数据字典中英、定时任务说明 | ✅ |
| Docker | `Dockerfile` + `docker-compose.yml` | ✅ |
| 调度 | `scripts/run_daily.sh` + `docs/scheduling.md` | ✅（手动触发） |

---

## 17. 看板截图

> 由 Playwright 自动截取本次运行成功的 Streamlit 实时看板（1440×2200）：

![Streamlit dashboard](./reports/dashboard_screenshot.png)

---

## 18. 已知边界与后续计划

- 数据为合成数据，结论用于验证方法与工程链路；接真实数仓时只需替换 `data/raw` 与 `raw` 层视图，dbt 与算法无需改动；
- 邮件发送需配置 `.env` 中的 `SMTP_HOST / SMTP_USER / SMTP_PASSWORD`；未配置时自动写 `reports/email_preview.html`；
- DockerHub 推送需先 `docker login`；
- 可选升级：Prophet（替代 STL）、UMAP（替代 PCA）、真实广告/链上 API 抓取。
