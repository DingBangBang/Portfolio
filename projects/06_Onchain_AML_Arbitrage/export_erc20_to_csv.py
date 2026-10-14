import json
import csv
from web3 import Web3

# === 配置 ===
RPC_URL = "https://mainnet.infura.io/v3/4236db2d3bc043bcb27132f759bbcb86"
TOKEN_ADDRESS = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
START_BLOCK = 25910000
END_BLOCK = 25910010

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

# === 获取 Transfer 事件 ===
try:
    print(f"📊 正在获取区块 {START_BLOCK} 到 {END_BLOCK} 的 Transfer 事件...")
    
    transfer_topic = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    
    logs = w3.eth.get_logs({
        'address': TOKEN_ADDRESS,
        'topics': [transfer_topic],
        'fromBlock': START_BLOCK,
        'toBlock': END_BLOCK
    })
    
    print(f"✅ 获取到 {len(logs)} 条事件记录")

    # === 保存到 CSV 文件 ===
    # 创建 nodes 和 relationships 两个文件
    nodes_file = open('usdt_addresses.csv', 'w', newline='', encoding='utf-8')
    rels_file = open('usdt_transfers.csv', 'w', newline='', encoding='utf-8')
    
    nodes_writer = csv.writer(nodes_file)
    rels_writer = csv.writer(rels_file)
    
    # 写入表头（符合 Neo4j 导入格式）
    nodes_writer.writerow(['address:ID(Address)'])
    rels_writer.writerow([':START_ID(Address)', ':END_ID(Address)', 'value:long', 'block_number:int'])
    
    # 用集合去重地址
    addresses = set()
    
    for log in logs:
        # 提取 from, to, value
        from_addr = '0x' + log['topics'][1].hex()[-40:] if len(log['topics']) > 1 else None
        to_addr = '0x' + log['topics'][2].hex()[-40:] if len(log['topics']) > 2 else None
        value = int(log['data'].hex(), 16) if log['data'] else 0
        block_num = log['blockNumber']
        
        # 跳过无效记录
        if not from_addr or not to_addr:
            continue
            
        # 收集地址
        addresses.add(from_addr)
        addresses.add(to_addr)
        
        # 写入关系（每一笔转账就是一条关系）
        rels_writer.writerow([from_addr, to_addr, value, block_num])
    
    # 写入所有地址节点
    for addr in addresses:
        nodes_writer.writerow([addr])
    
    # 关闭文件
    nodes_file.close()
    rels_file.close()
    
    print(f"\n✅ 数据保存成功！")
    print(f"   📁 地址文件: usdt_addresses.csv (共 {len(addresses)} 个唯一地址)")
    print(f"   📁 转账关系: usdt_transfers.csv (共 {len(logs)} 条转账记录)")
    
    # 打印前5条作为预览
    print(f"\n📋 转账记录预览（前5条）:")
    with open('usdt_transfers.csv', 'r') as f:
        lines = f.readlines()
        for i, line in enumerate(lines[:6]):  # 包含表头
            print(f"   {line.strip()}")

except Exception as e:
    print(f"❌ 获取日志失败: {e}")
    if "query returned more than 10000 results" in str(e):
        print("💡 提示：单次查询结果超过10000条，请缩小到10-50个区块再试")