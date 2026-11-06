# -*- coding: utf-8 -*-
"""可疑地址三连分析：资金进出 / 拆分转账 / 最终流向。

就是个把三条 Cypher 串起来的脚本，没做成库 —— 每次都是临时换个地址跑一下，
包装成类反而更啰嗦。
"""

from neo4j import GraphDatabase

from config_loader import load_config, setup_logging

log = setup_logging("aml")

CFG = load_config()
NEO = CFG["neo4j"]

# 密码从 .env 的 NEO4J_PASSWORD 读；原来写死 "your_password"，
# 后来换成真密码，push 前差点连密码一起提交
driver = GraphDatabase.driver(NEO["uri"], auth=(NEO["user"], NEO["password"]))


def run_query(query, parameters=None):
    """把 Cypher 和参数丢给数据库，结果转成 list[dict] 方便处理。"""
    with driver.session() as session:
        result = session.run(query, parameters)
        return [record.data() for record in result]


def analyze_suspicious_address(suspect_address):
    """对给定地址做三个维度的分析。"""
    log.info("开始分析 %s", suspect_address)

    # ===== 分析1：资金进出总览 =====
    query1 = """
    MATCH (s:Address {address: $addr})
    OPTIONAL MATCH (s)-[:SENT]->(t:Transaction)
    WITH s, sum(t.amount) as total_sent
    OPTIONAL MATCH (s)<-[:TO]-(t2:Transaction)
    RETURN s.address, total_sent, sum(t2.amount) as total_received
    """
    result1 = run_query(query1, {"addr": suspect_address})
    if result1:
        data = result1[0]
        log.info("总转出 %s USDT，总转入 %s USDT", data["total_sent"] or 0, data["total_received"] or 0)

    # ===== 分析2：识别拆分转账的中间地址 =====
    query2 = """
    MATCH (s:Address {address: $addr})-[:SENT]->(t1:Transaction)-[:TO]->(m:Address)
    WITH DISTINCT m
    MATCH (m)-[:SENT]->(t2:Transaction)-[:TO]->(recv:Address)
    WITH m, count(DISTINCT recv) as fan_out_count
    WHERE fan_out_count > 1
    RETURN m.address as middle_address, fan_out_count
    ORDER BY fan_out_count DESC
    """
    result2 = run_query(query2, {"addr": suspect_address})
    if result2:
        for row in result2:
            log.warning("地址 %s 转给了 %s 个不同接收方", row["middle_address"], row["fan_out_count"])
    else:
        log.info("没发现明显拆分行为")

    # ===== 分析3：两跳之后的资金路径 =====
    query3 = """
    MATCH path = (s:Address {address: $addr})
                  -[:SENT]->(:Transaction)-[:TO]->(:Address)
                  -[:SENT]->(:Transaction)-[:TO]->(r:Address)
    RETURN r.address as final_receiver
    """
    receivers = {row["final_receiver"] for row in run_query(query3, {"addr": suspect_address})}
    log.info("资金最终流向：%s 个不同地址", len(receivers))
    log.info("%s", ", ".join(sorted(receivers)) if receivers else "-")


if __name__ == "__main__":
    analyze_suspicious_address(CFG.get("suspect_address", "0xSuspicious001"))
    driver.close()
