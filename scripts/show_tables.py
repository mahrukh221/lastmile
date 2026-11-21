import sqlite3

con = sqlite3.connect("lastmile.db")
for (name,) in con.execute(
    "select name from sqlite_master where type='table' order by name"
):
    print(name)
    for col in con.execute(f"pragma table_info({name})"):
        print("    ", col[1], col[2])
        