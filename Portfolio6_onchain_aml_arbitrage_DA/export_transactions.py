import csv
from web3 import Web3, HTTPProvider
from tqdm import tqdm  # 进度条，可选安装: pip install tqdm

# === 配置 ===
RPC_URL = "https://mainnet.infura.io/v3/4236db2d3bc043bcb27132f759bbcb86"  # 换成你的节点地址
START_BLOCK = 19000000  # 起始区块号，建议从当前最新区块往前倒推
END_BLOCK = 19001000    # 结束区块号，先导1000个区块测试

# === 连接节点 ===
w3 = Web3(HTTPProvider(RPC_URL))
if not w3.is_connected():
    raise Exception("节点连接失败，请检查 RPC URL")

print(f"✅ 连接成功，当前区块: {w3.eth.block_number}")

# === 创建 CSV 文件 ===
# 节点文件: 地址节点（去重存储用集合）
addresses = set()
nodes_file = open('nodes_addresses.csv', 'w', newline='')
nodes_writer = csv.writer(nodes_file)
nodes_writer.writerow(['address:ID(Address)'])  # 符合 Neo4j 导入格式

# 关系文件: 交易记录
rels_file = open('transactions.csv', 'w', newline='')
rels_writer = csv.writer(rels_file)
# 原本是：
rels_writer.writerow([':START_ID(Address)', ':END_ID(Address)', 'value:long', 'hash'])
# 改成
# rels_writer.writerow([':START_ID(Address)', ':END_ID(Address)', 'value:string', 'hash'])

# === 遍历区块导出数据 ===
print(f"📊 开始扫描区块 {START_BLOCK} 到 {END_BLOCK}...")

for block_num in tqdm(range(START_BLOCK, END_BLOCK + 1)):
    try:
        block = w3.eth.get_block(block_num, full_transactions=True)
        if block is None or not block.transactions:
            continue
            
        for tx in block.transactions:
            from_addr = tx['from']
            to_addr = tx['to'] if tx['to'] else '0x0000000000000000000000000000000000000000'
            
            # 只记录成功发送到有效地址的交易（value > 0）
            if to_addr != '0x0000000000000000000000000000000000000000' and tx.value > 0:
                # 收集地址（后续写入节点文件）
                addresses.add(from_addr)
                addresses.add(to_addr)
                
                # 写入关系：from -> to，value 单位是 Wei（整数）
                rels_writer.writerow([from_addr, to_addr, str(tx.value), tx.hash.hex()])
                
        # 每100个区块 flush 一次，避免内存过大
        if block_num % 100 == 0:
            rels_file.flush()
            
    except Exception as e:
        print(f"⚠️ 区块 {block_num} 处理失败: {e}")
        continue

# === 写入所有地址节点 ===
print(f"📝 写入 {len(addresses)} 个唯一地址...")
for addr in addresses:
    nodes_writer.writerow([addr])

# === 关闭文件 ===
nodes_file.close()
rels_file.close()

print(f"✅ 导出完成！地址文件: nodes_addresses.csv，交易文件: transactions.csv")
print(f"   - 共 {len(addresses)} 个唯一地址")
print(f"   - 交易数量请查看 transactions.csv 行数")
