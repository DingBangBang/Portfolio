from neo4j import GraphDatabase

# 数据库连接配置（请改成你自己的密码）
URI = "bolt://localhost:7687"
USERNAME = "neo4j"
PASSWORD = "your_password"  # 替换成你的密码

# 创建数据库连接的"钥匙"
driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))

def run_query(query, parameters=None):
    """
    这个函数的作用：把要执行的Cypher查询和参数发给数据库，把返回的结果转换成Python能用的格式。
    通俗理解：这就是你和数据库之间的"传话员"。
    """
    with driver.session() as session:
        result = session.run(query, parameters)
        # 把每条记录转成字典，方便后续处理
        return [record.data() for record in result]

def analyze_suspicious_address(suspect_address):
    """
    核心分析函数：对给定的可疑地址，自动完成三个维度的分析
    """
    print(f"🔍 开始分析可疑地址: {suspect_address}")
    print("=" * 50)
    
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
        print(f"💰 资金进出总览:")
        print(f"   - 总转出: {data['total_sent'] or 0} USDT")
        print(f"   - 总转入: {data['total_received'] or 0} USDT")
    
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
    print(f"\n⚠️ 拆分转账风险地址 (转出给 >1 个接收方):")
    if result2:
        for row in result2:
            print(f"   - 地址 {row['middle_address']} 转给了 {row['fan_out_count']} 个不同地址")
    else:
        print("   ✅ 未发现明显拆分行为")
    
    # ===== 分析3：完整资金路径（可视化用） =====
    query3 = """
    MATCH path = (s:Address {address: $addr})
                  -[:SENT]->(:Transaction)-[:TO]->(:Address)
                  -[:SENT]->(:Transaction)-[:TO]->(r:Address)
    RETURN r.address as final_receiver
    """
    result3 = run_query(query3, {"addr": suspect_address})
    receivers = [row['final_receiver'] for row in result3]
    print(f"\n📊 资金最终流向汇总 (共 {len(set(receivers))} 个不同接收地址):")
    print(f"   {', '.join(set(receivers))}")
    
    print("\n" + "=" * 50)
    print("✅ 分析完成！")

if __name__ == "__main__":
    # 对模拟数据中的可疑地址执行分析
    analyze_suspicious_address("0xSuspicious001")
    
    # 关闭数据库连接
    driver.close()
