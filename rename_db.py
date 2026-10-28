"""One-time rebrand of an existing database: Brilliant -> Brillianz.

1. Moves every table from the old `brilliant_fm` database into the new one (Config.DB_NAME, `brillianz_fm`)
   and drops the old, now empty, database. Data, ids and passwords are kept as they are.
2. Rewrites the brand name in every text column (company name, testimonials, login emails, ...).
   Only the name is replaced; the plain word "brilliant" in lower case is left alone.

Safe to run more than once. Run it with the website stopped:  python rename_db.py
"""
import pymysql

try:
    from config import Config  # local, git-ignored settings
except ImportError:
    from config_example import Config

OLD_DB = "brilliant_fm"
REPLACEMENTS = [
    ("brilliantfm.com", "brillianzfm.com"),
    ("Brilliant", "Brillianz"),
    ("BRILLIANT", "BRILLIANZ"),
    ("بريليانت", "بريليانز"),
]
TEXT_TYPES = ("char", "varchar", "tinytext", "text", "mediumtext", "longtext")


def tables_in(cur, db_name):
    cur.execute("SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = %s AND table_type = 'BASE TABLE'", (db_name,))
    return [row[0] for row in cur.fetchall()]


def move_tables(cur, new_db):
    old_tables = tables_in(cur, OLD_DB)
    if not old_tables:
        print(f"Nothing to move: `{OLD_DB}` is missing or empty.")
        return
    if tables_in(cur, new_db):
        raise SystemExit(f"Both `{OLD_DB}` and `{new_db}` hold tables. Remove one of them by hand, then run again.")

    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{new_db}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    cur.execute("RENAME TABLE " + ", ".join(f"`{OLD_DB}`.`{t}` TO `{new_db}`.`{t}`" for t in old_tables))
    cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    print(f"Moved {len(old_tables)} tables from `{OLD_DB}` to `{new_db}`.")

    if not tables_in(cur, OLD_DB):
        cur.execute(f"DROP DATABASE `{OLD_DB}`")
        print(f"Dropped the empty `{OLD_DB}` database.")


def rename_brand(cur, db_name):
    cur.execute("SELECT table_name, column_name FROM information_schema.columns "
                "WHERE table_schema = %s AND data_type IN %s", (db_name, TEXT_TYPES))
    total = 0
    for table, column in cur.fetchall():
        expr, matches, params = f"`{column}`", [], []
        for old, new in REPLACEMENTS:
            expr = f"REPLACE({expr}, %s, %s)"
            params += [old, new]
            matches.append(f"BINARY `{column}` LIKE %s")
        params += [f"%{old}%" for old, _ in REPLACEMENTS]
        changed = cur.execute(f"UPDATE `{db_name}`.`{table}` SET `{column}` = {expr} WHERE " + " OR ".join(matches),
                              params)
        if changed:
            print(f"  {table}.{column}: {changed} row(s)")
            total += changed
    print(f"Renamed the brand in {total} value(s)." if total else "No old brand name left in the data.")


def main():
    cfg = Config
    conn = pymysql.connect(host=cfg.DB_HOST, port=cfg.DB_PORT, user=cfg.DB_USER, password=cfg.DB_PASSWORD,
                           charset="utf8mb4", autocommit=True)
    try:
        with conn.cursor() as cur:
            move_tables(cur, cfg.DB_NAME)
            rename_brand(cur, cfg.DB_NAME)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
