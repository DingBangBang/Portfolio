# -*- coding: utf-8 -*-
"""Neo4j 连接测试。

当初就是想知道 bolt 通不通，留着当 smoke test 用：
    python aml_tracing.py
"""

from neo4j import GraphDatabase

from config_loader import load_config, setup_logging

log = setup_logging("tracing")

CFG = load_config()
NEO = CFG["neo4j"]

driver = GraphDatabase.driver(NEO["uri"], auth=(NEO["user"], NEO["password"]))


def execute_query(query, parameters=None):
    with driver.session() as session:
        result = session.run(query, parameters)
        return [record.data() for record in result]


try:
    log.info("连上了：%s", execute_query("RETURN 'Connection successful!' as message"))
except Exception as e:
    # 连不上最常见的原因是 Neo4j 没起，或者密码还是 changeme
    log.error("连不上 Neo4j：%s", e)
finally:
    driver.close()
