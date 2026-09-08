# 这个py脚本主要是实现：
# 1.连接以太坊主网
# 2.从 Uniswap V2 Factory 读取所有交易对地址：Uniswap V2 Factory 的 allPairsLength() 方法返回所有已创建的流动性池数量（目前2000-4000个左右）
# 3.遍历每个交易对，读取储备金并计算汇率：reserve0 = 池子中 Token0 的数量（如 WBTC）；reserve1 = 池子中 Token1 的数量（如 WETH）。Token0 的价格（以 Token1 计价） = reserve1 / reserve0，例如，WBTC-WETH 池子里有 10,732,455,184 WBTC（带小数位）和 2,056,841,643,098,872,275,548 WETH（带小数位），通过这两个储备量的比值就能计算出实时汇率。
# 4.生成符合 Neo4j 导入格式的 CSV 文件：和【案例一：反洗钱（AML）资金追踪——找出“拆分转账”的可疑地址】用函数neo4j_import()即可

# # ====================================================== 版本二：聚焦核心高流动性池子。这会从"漫无目的地扫全链"变成"精准打击核心交易对"，速度从几周缩短到几分钟(fetch_core_pairs.py)。 ==============
import csv
import time
from web3 import Web3, HTTPProvider
from tqdm import tqdm

# === 配置 ===
RPC_URL = "https://mainnet.infura.io/v3/4236db2d3bc043bcb27132f759bbcb86"  # 替换为你的 RPC

# === 核心池子列表 ===
CORE_PAIRS = [
     {"name": "WETH-USDC", "address": "0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc"},
    {"name": "WETH-USDT", "address": "0x0d4a11d5EEaaC28EC3F61d100daF4d40471f1852"},
    {"name": "WETH-DAI", "address": "0xA478c2975Ab1Ea89e8196811F51A7B7Ade33eB11"},
    {"name": "WETH-WBTC", "address": "0xBb2b8038a1640196FbE3e38816F3e67Cba72D940"},
    {"name": "USDC-USDT", "address": "0x3041CbD36888bECc7bbCBc0045E3B1f144466f5f"},
    {"name": "USDC-DAI", "address": "0xAE461cA67B15dc8dc81CE7615e0320dA1A9aB8D5"},
    {"name": "USDT-DAI", "address": "0xeAF1Ac8E89EA0aE13E0f03634A4FF23502527024"},  # ✅ 修正后
    {"name": "WETH-UNI", "address": "0xd3D2E2692501A5c9Ca623199D03426eC77F033f7"},   # ✅ 修正后
    {"name": "WETH-LINK", "address": "0x6b5A2219D3DF748a1C3Af2E2B7C16358dF2b636b"}, # ✅ 修正后
    {"name": "WETH-AAVE", "address": "0x6C8c6b02E7b6be4F1D2C94aeEa5d3693bbF14E7E"}, # ✅ 修正后
]

# === Uniswap V2 Pair 合约 ABI ===
PAIR_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "getReserves",
        "outputs": [
            {"name": "reserve0", "type": "uint112"},
            {"name": "reserve1", "type": "uint112"},
            {"name": "blockTimestampLast", "type": "uint32"}
        ],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "token0",
        "outputs": [{"name": "", "type": "address"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "token1",
        "outputs": [{"name": "", "type": "address"}],
        "type": "function"
    }
]

ERC20_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function"
    }
]

# === 连接 ===
w3 = Web3(HTTPProvider(RPC_URL))
if not w3.is_connected():
    raise Exception("❌ 节点连接失败，请检查 RPC URL")
print(f"✅ 连接成功，当前区块: {w3.eth.block_number}")

# === 准备 CSV 文件 ===
nodes_file = open('assets_core.csv', 'w', newline='')
nodes_writer = csv.writer(nodes_file)
nodes_writer.writerow(['assetId:ID(Asset)', 'symbol', 'decimals:int'])

rels_file = open('trading_pairs_core.csv', 'w', newline='')
rels_writer = csv.writer(rels_file)
rels_writer.writerow([':START_ID(Asset)', ':END_ID(Asset)', 'rate:float', 'pair_address'])

seen_tokens = set()

# === 遍历核心池子 ===
print(f"🔍 开始扫描 {len(CORE_PAIRS)} 个核心交易对...")

for pair_info in tqdm(CORE_PAIRS):
    try:
        pair_address = pair_info["address"]
        pair_name = pair_info["name"]
        
        pair = w3.eth.contract(address=pair_address, abi=PAIR_ABI)
        
        # 读取储备金
        reserves = pair.functions.getReserves().call()
        reserve0 = reserves[0]
        reserve1 = reserves[1]
        
        if reserve0 == 0 or reserve1 == 0:
            print(f"⚠️ {pair_name} 流动性为0，跳过")
            continue
        
        # 读取两个代币地址
        token0_addr = pair.functions.token0().call()
        token1_addr = pair.functions.token1().call()
        
        # 读取代币信息
        token0_contract = w3.eth.contract(address=token0_addr, abi=ERC20_ABI)
        token1_contract = w3.eth.contract(address=token1_addr, abi=ERC20_ABI)
        
        try:
            decimals0 = token0_contract.functions.decimals().call()
            decimals1 = token1_contract.functions.decimals().call()
            symbol0 = token0_contract.functions.symbol().call()
            symbol1 = token1_contract.functions.symbol().call()
        except Exception:
            decimals0 = 18
            decimals1 = 18
            symbol0 = token0_addr[:8]
            symbol1 = token1_addr[:8]
        
        # 计算可读单位的储备量
        readable_reserve0 = reserve0 / (10 ** decimals0)
        readable_reserve1 = reserve1 / (10 ** decimals1)
        
        # 计算汇率
        rate = readable_reserve1 / readable_reserve0
        
        # 记录代币到节点文件
        if token0_addr not in seen_tokens:
            nodes_writer.writerow([token0_addr, symbol0, decimals0])
            seen_tokens.add(token0_addr)
        
        if token1_addr not in seen_tokens:
            nodes_writer.writerow([token1_addr, symbol1, decimals1])
            seen_tokens.add(token1_addr)
        
        # 记录交易对到关系文件（双向）
        rels_writer.writerow([token0_addr, token1_addr, rate, pair_address])
        rels_writer.writerow([token1_addr, token0_addr, 1/rate, pair_address])
        
        print(f"✅ {pair_name}: 1 {symbol0} = {rate:.6f} {symbol1}")
        
        # 每处理一个池子 flush 一次
        rels_file.flush()
        nodes_file.flush()
        
        # 小延迟，避免 RPC 限流
        time.sleep(0.2)
        
    except Exception as e:
        print(f"⚠️ {pair_name} 处理失败: {e}")
        continue

# === 关闭文件 ===
nodes_file.close()
rels_file.close()

print(f"\n✅ 导出完成！")
print(f"   - 资产节点: {len(seen_tokens)} 个")
print(f"   - 交易对关系: {len(CORE_PAIRS) * 2} 条（含双向）")


# # ====================================================== 版本一：调用 Factory 合约，有一个超过50d的全量扫描的时间。 ======================================================
# 这个版本的话脚本是一个区块一个区块、一个交易对一个交易对地串行调用RPC，每次调用都要等待网络往返，再加上 time.sleep(0.05) 的延迟，所以非常非常慢。但其实也可以用多线程
# import csv
# import time
# from web3 import Web3, HTTPProvider
# from tqdm import tqdm
# # import os
# # import requests

# # === 输出文件的保存位置 ===
# # import os

# # # 在脚本开头定义导入目录
# # IMPORT_DIR = os.path.expanduser("~/neo4j_import")

# # # 确保目录存在
# # os.makedirs(IMPORT_DIR, exist_ok=True)

# # # 创建文件
# # nodes_file = open(os.path.join(IMPORT_DIR, 'assets.csv'), 'w', newline='')
# # rels_file = open(os.path.join(IMPORT_DIR, 'trading_pairs.csv'), 'w', newline='')


# # === 配置 ===
# RPC_URL = "https://mainnet.infura.io/v3/4236db2d3bc043bcb27132f759bbcb86"  # 我的RPC节点url
# FACTORY_ADDRESS = "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f"  # Uniswap V2 Factory

# # === ABI 定义 ===
# # Uniswap V2 Factory 的 ABI（只包含我们需要的方法）
# FACTORY_ABI = [
#     {
#         "constant": True,
#         "inputs": [{"name": "", "type": "uint256"}],
#         "name": "allPairs",
#         "outputs": [{"name": "", "type": "address"}],
#         "type": "function"
#     },
#     {
#         "constant": True,
#         "inputs": [],
#         "name": "allPairsLength",
#         "outputs": [{"name": "", "type": "uint256"}],
#         "type": "function"
#     },
#     {
#         "constant": True,
#         "inputs": [{"name": "tokenA", "type": "address"}, {"name": "tokenB", "type": "address"}],
#         "name": "getPair",
#         "outputs": [{"name": "pair", "type": "address"}],
#         "type": "function"
#     }
# ]

# # Uniswap V2 Pair 合约的 ABI（读取储备金和代币地址）
# PAIR_ABI = [
#     {
#         "constant": True,
#         "inputs": [],
#         "name": "getReserves",
#         "outputs": [
#             {"name": "reserve0", "type": "uint112"},
#             {"name": "reserve1", "type": "uint112"},
#             {"name": "blockTimestampLast", "type": "uint32"}
#         ],
#         "type": "function"
#     },
#     {
#         "constant": True,
#         "inputs": [],
#         "name": "token0",
#         "outputs": [{"name": "", "type": "address"}],
#         "type": "function"
#     },
#     {
#         "constant": True,
#         "inputs": [],
#         "name": "token1",
#         "outputs": [{"name": "", "type": "address"}],
#         "type": "function"
#     }
# ]

# # ERC-20 代币的 ABI（读取小数位）
# ERC20_ABI = [
#     {
#         "constant": True,
#         "inputs": [],
#         "name": "decimals",
#         "outputs": [{"name": "", "type": "uint8"}],
#         "type": "function"
#     },
#     {
#         "constant": True,
#         "inputs": [],
#         "name": "symbol",
#         "outputs": [{"name": "", "type": "string"}],
#         "type": "function"
#     }
# ]

# # === 连接 ===
# w3 = Web3(HTTPProvider(RPC_URL))
# if not w3.is_connected():
#     raise Exception("❌ 节点连接失败，请检查 RPC URL")
# print(f"✅ 连接成功，当前区块: {w3.eth.block_number}")


# # # === 连接 ===
# # # === 代理配置 ===第二个版本
# # # 根据你的 VPN 类型填写代理地址
# # # Clash/Surge 默认 HTTP 代理端口是 7890（HTTP）和 7891（HTTPS）
# # # 如果你用的是其他端口，请修改下面的值
# # PROXY_URL = "http://127.0.0.1:7890"  # Clash 默认 HTTP 代理端口
# # # 或者如果你用的是 Shadowsocks，可能是 http://127.0.0.1:1087

# # # 创建带代理的 Session
# # session = requests.Session()
# # session.proxies = {
# #     'http': PROXY_URL,
# #     'https': PROXY_URL,
# # }
# # # 不要信任系统环境变量，避免冲突
# # session.trust_env = False

# # # RPC URL（不变）
# # RPC_URL = "https://mainnet.infura.io/v3/你的API_KEY"

# # # 使用自定义 session 创建 provider
# # provider = HTTPProvider(RPC_URL, session=session)
# # w3 = Web3(provider)

# # # 验证连接
# # if not w3.is_connected():
# #     raise Exception("❌ 节点连接失败，请检查 RPC URL 和代理配置")
# # print(f"✅ 连接成功，当前区块: {w3.eth.block_number}")


# # === 获取 Factory 合约 ===
# factory = w3.eth.contract(address=FACTORY_ADDRESS, abi=FACTORY_ABI)

# # === 获取所有交易对数量 ===
# pair_count = factory.functions.allPairsLength().call()
# print(f"📊 Uniswap V2 共有 {pair_count} 个交易对")

# # 先只取前 50 个交易对，观察运行时间，再把 LIMIT 改成 pair_count跑全量池子！！！
# # LIMIT = min(50, pair_count)
# LIMIT = min(pair_count, pair_count)

# # === 准备 CSV 文件 ===
# # 节点 CSV：存储所有资产（代币）
# nodes_file = open('assets.csv', 'w', newline='')
# nodes_writer = csv.writer(nodes_file)
# nodes_writer.writerow(['assetId:ID(Asset)', 'symbol', 'decimals:int'])

# # 关系 CSV：存储交易对及汇率
# rels_file = open('trading_pairs.csv', 'w', newline='')
# rels_writer = csv.writer(rels_file)
# rels_writer.writerow([':START_ID(Asset)', ':END_ID(Asset)', 'rate:float', 'pair_address'])

# # 缓存已见过的代币地址，避免重复写入节点
# seen_tokens = set()

# # === 遍历交易对 ===
# print(f"🔍 开始扫描前 {LIMIT} 个交易对...")

# for i in tqdm(range(LIMIT)):
#     try:
#         # 获取第 i 个交易对的地址
#         pair_address = factory.functions.allPairs(i).call()
        
#         # 实例化 Pair 合约
#         pair = w3.eth.contract(address=pair_address, abi=PAIR_ABI)
        
#         # 读取储备金
#         reserves = pair.functions.getReserves().call()
#         reserve0 = reserves[0]  # Token0 的储备量（原始单位）
#         reserve1 = reserves[1]  # Token1 的储备量（原始单位）
        
#         # 如果任何一个储备量为 0，跳过（流动性为 0 的池子）
#         if reserve0 == 0 or reserve1 == 0:
#             continue
        
#         # 读取两个代币的地址
#         token0_addr = pair.functions.token0().call()
#         token1_addr = pair.functions.token1().call()
        
#         # 读取代币的小数位（用于将原始单位转换为可读单位）
#         token0_contract = w3.eth.contract(address=token0_addr, abi=ERC20_ABI)
#         token1_contract = w3.eth.contract(address=token1_addr, abi=ERC20_ABI)
        
#         try:
#             decimals0 = token0_contract.functions.decimals().call()
#             decimals1 = token1_contract.functions.decimals().call()
#             symbol0 = token0_contract.functions.symbol().call()
#             symbol1 = token1_contract.functions.symbol().call()
#         except Exception:
#             # 某些代币可能不支持 decimals/symbol，使用默认值
#             decimals0 = 18
#             decimals1 = 18
#             symbol0 = token0_addr[:8]
#             symbol1 = token1_addr[:8]
        
#         # 计算可读单位的储备量
#         readable_reserve0 = reserve0 / (10 ** decimals0)
#         readable_reserve1 = reserve1 / (10 ** decimals1)
        
#         # 计算汇率：Token0 的价格（以 Token1 计价）
#         # 即 1 个 Token0 能换多少个 Token1
#         rate = readable_reserve1 / readable_reserve0
        
#         # 记录代币到节点 CSV
#         if token0_addr not in seen_tokens:
#             nodes_writer.writerow([token0_addr, symbol0, decimals0])
#             seen_tokens.add(token0_addr)
        
#         if token1_addr not in seen_tokens:
#             nodes_writer.writerow([token1_addr, symbol1, decimals1])
#             seen_tokens.add(token1_addr)
        
#         # 记录交易对到关系 CSV（双向关系）
#         # 方向：Token0 -> Token1（1个Token0能换 rate 个Token1）
#         rels_writer.writerow([token0_addr, token1_addr, rate, pair_address])
#         # 反向：Token1 -> Token0（1个Token1能换 1/rate 个Token0）
#         rels_writer.writerow([token1_addr, token0_addr, 1/rate, pair_address])
        
#         # 每 50 个池子 flush 一次，避免内存过大
#         if i % 50 == 0:
#             rels_file.flush()
#             nodes_file.flush()
            
#         # 加一个小延迟，避免 RPC 限流
#         time.sleep(0.05)
        
#     except Exception as e:
#         print(f"⚠️ 交易对 {i} 处理失败: {e}")
#         continue

# # === 关闭文件 ===
# nodes_file.close()
# rels_file.close()

# print(f"✅ 导出完成！")
# print(f"   - 资产节点: {len(seen_tokens)} 个")
# print(f"   - 交易对关系: 请查看 trading_pairs.csv 行数")



