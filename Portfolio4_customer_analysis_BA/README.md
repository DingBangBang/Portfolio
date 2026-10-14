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
* 衡量不同的流量归因模型产生的差距和区别以及怎么定义误差，生成最终的优于末次归触点因模型的最佳方案（只对比三个：首次归因、位置归因、markov chain：算每个渠道在用户转化路径中的移除效应（Removal Effect））
* 季度预算弹性测算与自动化（Prophet拆出趋势和季节性，再叠加一个简单的弹性回归模型——每多花1美元在不同的渠道，边际回报的可视化；最好还能设计一个傻瓜操作的模型操作接口，直接简单粗暴的让管理层输入她的假设，直接输出在该假设下下季度OKR核心KPI会如何变化，会产生什么影响和变化）
* 揪出数据中的一个esignup_cvr作为示例，先横向对比，再用户group by不同的维度下钻去归因，然后用分群T检验追踪“注册后1小时内”的行为序列（是否查看教程、是否点击首次任务），找出高流失群体用户们共同的先行前兆行为。最后外部验证。在漏斗归因（Attribution in Funnel） + 生存分析（Cox回归） 衡量各步骤的“流失风险系数”。最后漏斗归因（Attribution in Funnel） + 生存分析（Cox回归） 衡量各步骤的“流失风险系数”。
* 广告成本与社交媒体绩效的相关性分析：* Step 2 滞后相关性（Lag Correlation）：检验“高互动”是否提前于“低成本”出现（即优质内容先火，后导致成本下降），反之亦然。* Step 3 混淆变量控制：引入“预算突增”作为控制变量（预算越大通常CPC越高，同时人为加热也推高互动），使用偏相关分析剥离预算影响。* Step 4 细分场景：分别计算“品牌词”与“通用词”广告下的相关度差异。输出类似“互动率每提升1%，CPC平均下降$4.74，但这个相关性结论只会在自然互动的情况下下成立”的结论矩阵。
* 不同页面模块注册效率的比较分析（消除位置偏差：计算 Relative Clickability（模块曝光面积占比 vs 点击占比，判断是否“名不副实”；Hotjar（热力图验证点击分布）、SQL（CTE递归计算用户路径）。A/B测试分流对比（历史同期相同流量下模块替换效果）；DEA数据包络分析评估多投入（曝光）多产出（注册+留存）的综合效率）
* CTA组件转化率属性的调查（全因子实验设计（Full Factorial Design） 分析主效应与交互效应；随机森林特征重要性排序各属性对CVR的贡献度。）
* 某个改动/某个特定的因素对核心OKR核心KPI（流量到注册的转化，或者注册到首次入金的转化）的变动部分具体有多少贡献：归因剥离与量化助攻价值计算（归因剥离 = 反事实模拟 = 模拟“如果没有这个渠道，转化率会掉多少”，构建转移矩阵——统计“从A渠道走到B渠道”的概率；计算整体转化率；计算移除效应——逐个渠道“拿掉”再算转化率；归一化——把移除效应转化为百分比贡献度；得出类似“品牌词和Twitter的助攻价值比末次点击模型高出40%”这个结论，就是这样算出来的：马尔可夫链的贡献度减去末次点击的贡献度，再除以末次点击的贡献度。的结果；和Shapley值有什么区别？：马尔可夫回答“没有它行不行”，Shapley回答“有了它平均好多少”）
