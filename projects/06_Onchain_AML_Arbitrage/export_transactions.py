# -*- coding: utf-8 -*-
"""导出原生 ETH 转账：区块 → CSV（Neo4j 导入格式）。

改动记录：RPC 地址和区块范围原来写死在文件里，现在分别走 .env 和 config.yaml。
逻辑没动，就是把 print 换成 logging，另外加了 flush 的频率注释。
"""

import csv

from tqdm import tqdm  # 进度条，可选安装: pip install tqdm
from web3 import HTTPProvider, Web3

from config_loader import load_config, require_rpc, setup_logging

log = setup_logging("export_tx")

# === 配置 ===
CFG = load_config()
RPC_URL = require_rpc(CFG)
START_BLOCK = CFG["export"]["start_block"]
END_BLOCK = CFG["export"]["end_block"]
NODES_OUT = CFG["export"].get("output_nodes", "nodes_addresses.csv")
RELS_OUT = CFG["export"].get("output_rels", "transactions.csv")

# === 连接节点 ===
w3 = Web3(HTTPProvider(RPC_URL))
if not w3.is_connected():
    raise SystemExit("节点连不上，检查 .env 里的 RPC_URL")

log.info("连接成功，当前区块 %s", w3.eth.block_number)

# === 创建 CSV 文件 ===
# 节点文件：地址去重，用一个 set 顶着；500 万地址以内内存扛得住
addresses = set()
nodes_file = open(NODES_OUT, "w", newline="")
nodes_writer = csv.writer(nodes_file)
nodes_writer.writerow(["address:ID(Address)"])  # 符合 neo4j-admin import 格式

# 关系文件：一条转账一行
rels_file = open(RELS_OUT, "w", newline="")
rels_writer = csv.writer(rels_file)
# value 一开始写成 :long，结果大额转账超了 Java long 的范围，导入直接失败；
# 改成 :string 之后就没事了
erls_header = [":START_ID(Address)", ":END_ID(Address)", "value:string", "hash"]
rels_writer.writerow(rels_header)

# === 遍历区块导出数据 ===
log.info("扫描区块 %s ~ %s", START_BLOCK, END_BLOCK)

for block_num in tqdm(range(START_BLOCK, END_BLOCK + 1)):
    try:
        block = w3.eth.get_block(block_num, full_transactions=True)
        if block is None or not block.transactions:
            continue

        for tx in block.transactions:
            from_addr = tx["from"]
            to_addr = tx["to"] if tx["to"] else "0x0000000000000000000000000000000000000000"

            # 只记到有效地址且金额 > 0 的；合约创建交易（to 为空）混进来会把图搞乱
            if to_addr != "0x0000000000000000000000000000000000000000" and tx.value > 0:
                addresses.add(from_addr)
                addresses.add(to_addr)
                rels_writer.writerow([from_addr, to_addr, str(tx.value), tx.hash.hex()])

        # 每 100 个区块 flush 一次。之前漏了这行，跑到第 8 万个区块时中断，文件全丢
        if block_num % 100 == 0:
            rels_file.flush()

    except Exception as e:
        # 单块失败不中断，区块是幂等的，回头补导就行
        log.warning("区块 %s 处理失败：%s", block_num, e)
        continue

# === 写入所有地址节点 ===
log.info("写入 %s 个唯一地址", len(addresses))
for addr in addresses:
    nodes_writer.writerow([addr])

nodes_file.close()
rels_file.close()
log.info("导出完成：%s / %s", NODES_OUT, RELS_OUT)
