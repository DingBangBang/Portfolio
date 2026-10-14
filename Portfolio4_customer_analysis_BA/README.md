# Portfolio_customer_action_ana

* RFM user segmentation（+Advanced Dimensionality Reduction）
* CEX conversion funnel
* user behavioral science and psychology analysis
* user flow path graph
* user LTV prediction(使用BG/NBD模型还是机器学习回归的技术决策)
* ROI波动归因瀑布图（MANOVA/ANOVA识别主要影响维度“贡献度算法”，漏斗归因（Attribution in Funnel） + 生存分析（Cox回归） 衡量各步骤的“流失风险系数”。对比活动期与活动前4周的新客LTV和老客复购率，计算增量ROI（剔除自然增长基线）。对比活动期与活动前4周的新客LTV和老客复购率，计算增量ROI（剔除自然增长基线）。）
* campaign+airdrop ROI/CAC/CPA prediction（还有Causal Inference & Strategy Evaluation，针对某个新推出的活动，究竟带来了多少净新增交易量，而不是把本来就会交易的用户算进去）
* comprehensive analysis of all ads + traffic channels + social media（+渠道质量分级与Shapley归因，识别注水渠道）
* use Multiple Logistic Regression + Interaction Effect + inference causasion + feature engineer + 
* do a real AB Test or simulation here
* structure a user profiling system
* implement refined operation framework
* develop a user tag system and a complete VIP mechanism
* 衡量不同的流量归因模型产生的差距和区别以及怎么定义误差，生成最终的优于末次归触点因模型的最佳方案（只对比三个：首次归因、末次归因、markov chain）
* 季度预算弹性测算与自动化（Prophet拆出趋势和季节性，再叠加一个简单的弹性回归模型——每多花1美元在不同的渠道，边际回报的可视化；最好还能设计一个傻瓜操作的模型操作接口，直接简单粗暴的让管理层输入她的假设，直接输出在该假设下下季度OKR核心KPI会如何变化，会产生什么影响和变化）
* 揪出数据中的一个esignup_cvr作为示例，先横向对比，再用户group by不同的维度下钻去归因，然后用分群T检验追踪“注册后1小时内”的行为序列（是否查看教程、是否点击首次任务），找出高流失群体用户们共同的先行前兆行为。最后外部验证。在漏斗归因（Attribution in Funnel） + 生存分析（Cox回归） 衡量各步骤的“流失风险系数”。最后漏斗归因（Attribution in Funnel） + 生存分析（Cox回归） 衡量各步骤的“流失风险系数”。
* 广告成本与社交媒体绩效的相关性分析：* Step 2 滞后相关性（Lag Correlation）：检验“高互动”是否提前于“低成本”出现（即优质内容先火，后导致成本下降），反之亦然。* Step 3 混淆变量控制：引入“预算突增”作为控制变量（预算越大通常CPC越高，同时人为加热也推高互动），使用偏相关分析剥离预算影响。* Step 4 细分场景：分别计算“品牌词”与“通用词”广告下的相关度差异。输出类似“互动率每提升1%，CPC平均下降$4.74，但这个相关性结论只会在自然互动的情况下下成立”的结论矩阵。
* 不同页面模块注册效率的比较分析（消除位置偏差：计算 Relative Clickability（模块曝光面积占比 vs 点击占比，判断是否“名不副实”；Hotjar（热力图验证点击分布）、SQL（CTE递归计算用户路径）。A/B测试分流对比（历史同期相同流量下模块替换效果）；DEA数据包络分析评估多投入（曝光）多产出（注册+留存）的综合效率）
* CTA组件转化率属性的调查（全因子实验设计（Full Factorial Design） 分析主效应与交互效应；随机森林特征重要性排序各属性对CVR的贡献度。）
