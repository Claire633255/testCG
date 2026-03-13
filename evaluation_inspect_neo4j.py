from neo4j import GraphDatabase
import networkx as nx


# ========= 修改为你的服务器信息 =========
URI = "bolt://172.16.167.35:7687"
USERNAME = "neo4j"
PASSWORD = "kame_pwd"
# =======================================


class Neo4jInspector:

    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def run_query(self, query, **params):
        with self.driver.session() as session:
            return list(session.run(query, **params))

    # =========================
    # 基本数据库信息
    # =========================
    def inspect(self):
        print("\n====== 基本数据库信息 ======\n")

        # 所有标签
        labels = self.run_query("CALL db.labels()")
        print("节点标签:")
        for record in labels:
            print(" -", record[0])

        # 所有关系类型
        rels = self.run_query("CALL db.relationshipTypes()")
        print("\n关系类型:")
        for record in rels:
            print(" -", record[0])

        # 节点总数
        node_count = self.run_query("MATCH (n) RETURN count(n) AS cnt")
        print("\n节点总数:", node_count[0]["cnt"])

        # 关系总数
        rel_count = self.run_query("MATCH ()-[r]->() RETURN count(r) AS cnt")
        print("关系总数:", rel_count[0]["cnt"])

    # =========================
    # Project 统计
    # =========================
    def count_projects(self):
        print("\n====== Project 统计 ======\n")

        result = self.run_query("MATCH (p:Project) RETURN count(p) AS cnt")
        if not result:
            print("⚠ 未找到 Project 标签")
            return 0

        count = result[0]["cnt"]
        print("Project 总数:", count)

        projects = self.run_query(
            "MATCH (p:Project) RETURN p.name AS name"
        )

        print("\nProject 列表:")
        for record in projects:
            print(" -", record["name"])

        return count

    # =========================
    # 导出单个 Project Call Graph
    # =========================
    def export_single_project_callgraph(self, project_name):
        print(f"\n正在导出 Project: {project_name}")

        query = """
        MATCH (p:Project {name: $name})-[:CONTAINS]->(f:Function)
        WITH collect(f) AS funcs
        MATCH (f1:Function)-[:CALLS]->(f2:Function)
        WHERE f1 IN funcs AND f2 IN funcs
        RETURN f1.name AS from, f2.name AS to
        """

        records = self.run_query(query, name=project_name)

        G = nx.DiGraph()

        for record in records:
            G.add_edge(record["from"], record["to"])

        if G.number_of_nodes() == 0:
            print("⚠ 该 Project 没有 CALLS 关系")
            return

        filename = f"{project_name}_callgraph.graphml"
        nx.write_graphml(G, filename)

        print(f"导出完成: {filename}")
        print(f"节点数: {G.number_of_nodes()}")
        print(f"边数: {G.number_of_edges()}")

    # =========================
    # 导出所有 Project
    # =========================
    def export_all_projects_callgraphs(self):
        print("\n====== 导出所有 Project Call Graph ======\n")

        projects = self.run_query(
            "MATCH (p:Project) RETURN p.name AS name"
        )

        if not projects:
            print("⚠ 未找到任何 Project")
            return

        for record in projects:
            self.export_single_project_callgraph(record["name"])


# =========================
# 主程序
# =========================
if __name__ == "__main__":

    inspector = Neo4jInspector(URI, USERNAME, PASSWORD)

    # 1️⃣ 查看数据库基本情况
    inspector.inspect()

    # 2️⃣ 统计 project
    inspector.count_projects()

    # # 3️⃣ 导出所有 project 的 call graph
    # inspector.export_all_projects_callgraphs()

    inspector.close()
