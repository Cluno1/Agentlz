import os
import sys
from contextlib import closing

from agentlz.repositories.pgvector_repository import _get_pg_conn


'''测试 pgvector 连接  测试命令：python -m test.sql.pgvector_connection_test'''



def main():
    try:
        a = _get_pg_conn()
        print(a)
        with closing(_get_pg_conn()) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version()")
                ver = cur.fetchone()
                cur.execute("SELECT extname FROM pg_extension WHERE extname='vector'")
                ext = cur.fetchone()
                cur.execute("SELECT '[1,2,3]'::vector <-> '[1,2,4]'::vector")
                dist = cur.fetchone()
            print("postgres_version:", ver[0])
            print("pgvector_extension:", bool(ext))
            print("vector_l2_distance:", float(dist[0]))
        sys.exit(0)
    except Exception as e:
        print("error:", str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()