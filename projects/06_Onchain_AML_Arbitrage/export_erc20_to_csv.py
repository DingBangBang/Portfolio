import csv
import json

from web3 import Web3

from config_loader import load_config, require_rpc, setup_logging

log = setup_logging("export_erc20")

# === 配置 ===
CFG = load_config()
RPC_URL = require_rpc(CFG)
ERC20 = CFG["erc20"]
TOKEN_ADDRESS = ERC20["token_address"]
START_BLOCK = ERC20["start_block"]
END_BLOCK = ERC20["end_block"]

# === 连接以太坊节点 ===
w3 = Web3(Web3.HTTPProvider(RPC_URL))
if not w3.is_connected():
    raise SystemExit("节点连不上，检查 .env 里的 RPC_URL")
log.info("节点连接成功，当前区块 %s", w3.eth.block_number)

# === 从本地文件加载 ABI ===
try:
    with open(ERC20.get("abi_file", "usdt_abi.json"), "r") as f:
        token_abi = json.load(f)
    log.info("从本地文件加载 ABI 成功")
except FileNotFoundError:
    # ABI 没提交（几十 KB 的 json，也没人爱看），从 etherscan 复制一份存本地就行
    raise SystemExit("找不到 ABI 文件，去 etherscan 复制 USDT 的 ABI 存成 usdt_abi.json")

# === 创建合约对象 ===
contract = w3.eth.contract(address=TOKEN_ADDRESS, abi=token_abi)

# === 获取 Transfer 事件 ===
try:
    log.info("获取区块 %s ~ %s 的 Transfer 事件", START_BLOCK, END_BLOCK)

    transfer_topic = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

    logs = w3.eth.get_logs({
        "address": TOKEN_ADDRESS,
        "topics": [transfer_topic],
        "fromBlock": START_BLOCK,
        "toBlock": END_BLOCK,
    })
    log.info("拿到 %s 条事件记录", len(logs))

    # === 保存到 CSV 文件 ===
    nodes_out = ERC20.get("output_nodes", "usdt_addresses.csv")
    rels_out = ERC20.get("output_rels", "usdt_transfers.csv")
    nodes_file = open(nodes_out, "w", newline="", encoding="utf-8")
    rels_file = open(rels_out, "w", newline="", encoding="utf-8")

    nodes_writer = csv.writer(nodes_file)
    rels_writer = csv.writer(rels_file)

    # 表头要跟 neo4j-admin import 对齐：value 用 string（大额会超 long），块高用 int
    nodes_writer.writerow(["address:ID(Address)"])
    rels_writer.writerow([":START_ID(Address)", ":END_ID(Address)", "value:string", "block_number:int"])

    addresses = set()

    # 注意：循环变量别叫 log，之前就是叫 log，加了 logging 之后把自己坑了
    for entry in logs:
        from_addr = "0x" + entry["topics"][1].hex()[-40:] if len(entry["topics"]) > 1 else None
        to_addr = "0x" + entry["topics"][2].hex()[-40:] if len(entry["topics"]) > 2 else None
        value = int(entry["data"].hex(), 16) if entry["data"] else 0
        block_num = entry["blockNumber"]

        if not from_addr or not to_addr:
            continue

        addresses.add(from_addr)
        addresses.add(to_addr)
        rels_writer.writerow([from_addr, to_addr, value, block_num])

    for addr in addresses:
        nodes_writer.writerow([addr])

    nodes_file.close()
    rels_file.close()
    log.info("保存完成：%s（%s 个地址） / %s（%s 条转账）", nodes_out, len(addresses), rels_out, len(logs))

except Exception as e:
    log.error("获取日志失败：%s", e)
    if "query returned more than 10000 results" in str(e):
        log.error("单次查询超过 10000 条，把区块范围缩到 10~50 个再试")
    raise
