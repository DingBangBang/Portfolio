from neo4j import GraphDatabase

# 数据库连接信息 (请根据你的实际设置修改)
URI = "bolt://localhost:7687"  # 本地连接地址
USERNAME = "neo4j"
PASSWORD = "your_password"  # 替换成你自己的密码

# 创建驱动实例，这是连接数据库的“钥匙”
driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))

# 定义一个执行查询的函数
def execute_query(query, parameters=None):
    """
    这个函数就像你的“传话筒”，帮你把 Cypher 问题和参数传给数据库，
    然后把结果原样带回来给你。
    """
    with driver.session() as session:
        result = session.run(query, parameters)
        return [record.data() for record in result]

# 测试一下连接：查询数据库版本
print(execute_query("RETURN 'Connection successful!' as message"))

# 使用完毕后别忘了关闭“钥匙”，这是个好习惯
# driver.close()
