import sys
from agentlz.core.database import get_pg_engine, get_mysql_engine

"""
检查 .env 配置下的 MCP 数据是否与部署 SQL 一致（PG/向量、MySQL/关键词）

运行：
  python -m test.sql.check_mcp_data_consistency
输出：
  - PG mcp_agents_vec 总数、embedding 非空数量、示例ID存在性（34: exa_remote）
  - MySQL mcp_agents 关键词 '代码' 匹配数量与示例行
"""


def main():
    try:
        # PostgreSQL 检查
        pg = get_pg_engine()
        with pg.connect() as conn:
            total = conn.exec_driver_sql("SELECT COUNT(*) FROM mcp_agents_vec").scalar() or 0
            nonnull = conn.exec_driver_sql("SELECT COUNT(*) FROM mcp_agents_vec WHERE embedding IS NOT NULL").scalar() or 0
            has_34 = conn.exec_driver_sql("SELECT COUNT(*) FROM mcp_agents_vec WHERE id=34").scalar() or 0
            has_34_emb = conn.exec_driver_sql("SELECT COUNT(*) FROM mcp_agents_vec WHERE id=34 AND embedding IS NOT NULL").scalar() or 0
        print(f"PG mcp_agents_vec total={int(total)} nonnull_embedding={int(nonnull)} id34_exists={int(has_34)} id34_has_embedding={int(has_34_emb)}")

        # MySQL 检查（关键词 '代码'）
        my = get_mysql_engine()
        with my.connect() as conn:
            rs = conn.exec_driver_sql(
                "SELECT id,name,transport,command,description,trust_score FROM mcp_agents WHERE name LIKE CONCAT('%%',%s,'%%') OR description LIKE CONCAT('%%',%s,'%%') ORDER BY trust_score DESC LIMIT 5",
                ("代码", "代码"),
            ).mappings().all()
        print("MySQL keyword '代码' rows:", [dict(r) for r in rs])
        print(f"MySQL keyword count={len(rs)}")

        # 结论提示
        if int(nonnull) == 0:
            print("结论：PG 向量 embedding 为空（或未批量生成），混合检索将返回空。请先运行离线向量化任务或使用 create_mcp_agent_service 插入含 embedding 的样本。")
        if len(rs) == 0:
            print("结论：MySQL 关键字 '代码' 无匹配记录。关键词检索工具将返回空。")

        sys.exit(0)
    except Exception as e:
        print("error:", str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()

