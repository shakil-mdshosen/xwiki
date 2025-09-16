import os
import pymysql

def get_connection():
    host = os.getenv("TOOLSDB_HOST", "tools.db.svc.wikimedia.cloud")
    dbname = os.getenv("TOOLSDB_DATABASE")
    if not dbname:
        raise RuntimeError("Set TOOLSDB_DATABASE in environment (e.g., xwiki__events)")
    cnf = os.getenv("MYSQL_CNF_PATH", os.path.expanduser("~/.my.cnf"))

    return pymysql.connect(
        host=host,
        database=dbname,
        read_default_file=cnf,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )