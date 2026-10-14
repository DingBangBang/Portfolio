import json
from web3 import Web3

# === 配置 ===
RPC_URL = "https://mainnet.infura.io/v3/4236db2d3bc043bcb27132f759bbcb86"
TOKEN_ADDRESS = "0xdAC17F958D2ee523a2206206994597C13D831ec7"

# === 连接以太坊节点 ===
w3 = Web3(Web3.HTTPProvider(RPC_URL))
if not w3.is_connected():
    print("❌ 节点连接失败")
    exit()
print(f"✅ 节点连接成功，当前区块: {w3.eth.block_number}")

# === 从本地文件加载 ABI ===
try:
    with open('usdt_abi.json', 'r') as f:
        token_abi = json.load(f)
    print("✅ 从本地文件加载 ABI 成功")
except FileNotFoundError:
    print("❌ 找不到 usdt_abi.json 文件")
    exit()

# === 创建合约对象 ===
contract = w3.eth.contract(address=TOKEN_ADDRESS, abi=token_abi)

# === 修正后的调用方式 ===
try:
    print("📊 正在获取区块 25910000 到 25910010 的 Transfer 事件...")
    
    # 方法1：使用 w3.eth.get_logs() 直接查询（最稳定）
    transfer_topic = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    
    logs = w3.eth.get_logs({
        'address': TOKEN_ADDRESS,
        'topics': [transfer_topic],
        'fromBlock': 25910000,
        'toBlock': 25910010
    })
    
    print(f"✅ 获取到 {len(logs)} 条事件记录")
    
    # 解析日志数据（从 topics 和 data 中提取信息）
    for i, log in enumerate(logs[:5]):
        # 从 topics 中提取索引参数
        from_addr = '0x' + log['topics'][1].hex()[-40:] if len(log['topics']) > 1 else '0x0'
        to_addr = '0x' + log['topics'][2].hex()[-40:] if len(log['topics']) > 2 else '0x0'
        value = int(log['data'].hex(), 16) if log['data'] else 0
        
        print(f"  事件 {i+1}: from={from_addr[:10]}..., to={to_addr[:10]}..., value={value}")
        
except Exception as e:
    print(f"❌ 获取日志失败: {e}")
    if "query returned more than 10000 results" in str(e):
        print("💡 提示：单次查询结果超过10000条，请缩小到10-50个区块再试")
    if "block range" in str(e).lower():
        print("💡 提示：区块范围可能超出节点限制，尝试缩小范围到10个区块以内")




'''
import json
from web3 import Web3

# === 配置 ===
RPC_URL = "https://mainnet.infura.io/v3/4236db2d3bc043bcb27132f759bbcb86"
TOKEN_ADDRESS = "0xdAC17F958D2ee523a2206206994597C13D831ec7"

# === 连接以太坊节点 ===
w3 = Web3(Web3.HTTPProvider(RPC_URL))
if not w3.is_connected():
    print("❌ 节点连接失败")
    exit()
print(f"✅ 节点连接成功，当前区块: {w3.eth.block_number}")

# === 从本地文件加载 ABI（跳过 Etherscan API）===
try:
    with open('usdt_abi.json', 'r') as f:
        token_abi = json.load(f)
    print("✅ 从本地文件加载 ABI 成功")
except FileNotFoundError:
    print("❌ 找不到 usdt_abi.json 文件，请确保它和脚本在同一目录")
    exit()

# === 创建合约对象 ===
contract = w3.eth.contract(address=TOKEN_ADDRESS, abi=token_abi)

# === 获取 Transfer 事件（只查10个区块，避免超限）===
try:
    print("📊 正在获取区块 25910000 到 25910010 的 Transfer 事件...")
    events = contract.events.Transfer().get_logs(
        fromBlock=25910000,
        toBlock=25910010
    )
    print(f"✅ 获取到 {len(events)} 条事件记录")
    
    for i, event in enumerate(events[:5]):
        print(f"  事件 {i+1}: from={event.args.src}, to={event.args.dst}, value={event.args.wad}")
        
except Exception as e:
    print(f"❌ 获取日志失败: {e}")
    if "query returned more than 10000 results" in str(e):
        print("💡 提示：单次查询结果超过10000条，请缩小到10-50个区块再试")
'''


'''
import requests
import json  
# 注意：你的代码中缺少了 import json，必须加上
from web3 import Web3

# 注意：这里是你连接以太坊节点的 RPC 地址（Infura 等），保持不变
w3 = Web3(Web3.HTTPProvider("https://mainnet.infura.io/v3/4236db2d3bc043bcb27132f759bbcb86"))

token_address = "0xdAC17F958D2ee523a2206206994597C13D831ec7"

# 从 Etherscan API 获取 ABI
# 将这里替换为你刚刚在 Etherscan 复制到的那串字符
api_key = "16VS1J8FBC2Y26B5JV15AKSINZYMI3D5BM"  

url = f"https://api.etherscan.io/api?module=contract&action=getabi&address={token_address}&apikey={api_key}"
response = requests.get(url)

# 检查是否获取成功
if response.json()['status'] == '1':
    token_abi = json.loads(response.json()['result'])
else:
    print("获取ABI失败，请检查 API Key 是否正确或网络限制。")
    print(response.text)
    exit()

contract = w3.eth.contract(address=token_address, abi=token_abi)

# 后续代码相同
try:
    events = contract.events.Transfer().get_logs(
        fromBlock=19000000,
        toBlock=19001000
    )
    for event in events:
        print(event.args)
except Exception as e:
    print(f"获取日志失败: {e}")
'''



'''
import requests
import json
from web3 import Web3

# === 配置 ===
RPC_URL = "https://mainnet.infura.io/v3/4236db2d3bc043bcb27132f759bbcb86"
ETHERSCAN_API_KEY = "16VS1J8FBC2Y26B5JV15AKSINZYMI3D5BM"
TOKEN_ADDRESS = "0xdAC17F958D2ee523a2206206994597C13D831ec7"

# === 连接以太坊节点 ===
w3 = Web3(Web3.HTTPProvider(RPC_URL))
if not w3.is_connected():
    print("❌ 节点连接失败，请检查 RPC URL")
    exit()

print(f"✅ 节点连接成功，当前区块: {w3.eth.block_number}")

# === 使用 Etherscan API V2 获取 ABI ===
# V2 的新格式：module+action 合并为 /api/v2/
url = f"https://api.etherscan.io/v2/api/contract/{TOKEN_ADDRESS}/abi?apikey={ETHERSCAN_API_KEY}"

print(f"📡 正在从 Etherscan 获取 ABI...")
response = requests.get(url)

if response.status_code != 200:
    print(f"❌ HTTP 请求失败，状态码: {response.status_code}")
    print(response.text)
    exit()

data = response.json()
if data.get('status') == '1':
    token_abi = json.loads(data['result'])
    print(f"✅ ABI 获取成功！")
else:
    print(f"❌ 获取 ABI 失败: {data.get('message', '未知错误')}")
    print(f"完整响应: {data}")
    exit()

# === 创建合约对象 ===
contract = w3.eth.contract(address=TOKEN_ADDRESS, abi=token_abi)

# === 获取 Transfer 事件 ===
try:
    print(f"📊 正在获取区块 19000000 到 19001000 的 Transfer 事件...")
    events = contract.events.Transfer().get_logs(
        fromBlock=19000000,
        toBlock=19001000
    )
    print(f"✅ 获取到 {len(events)} 条事件记录")
    
    # 打印前5条示例
    for i, event in enumerate(events[:5]):
        print(f"  事件 {i+1}: from={event.args.src}, to={event.args.dst}, value={event.args.wad}")
        
except Exception as e:
    print(f"❌ 获取日志失败: {e}")
    # 常见错误：区块范围太大，建议缩小范围再试
    if "query returned more than 10000 results" in str(e):
        print("💡 提示：单次查询结果超过10000条，请缩小区块范围 (如只查10个区块)")
'''