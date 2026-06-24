# check_db.py

import sqlite3
import pandas as pd

DB_PATH = "kait.db"

conn = sqlite3.connect(DB_PATH)

tables = [
    "nifty_candles",
    "features_log",
    "option_chain_snapshots",
    "paper_trades"
]

print("\n" + "=" * 60)
print("KAIT DATABASE EXPLORER")
print("=" * 60)

for i, table in enumerate(tables, start=1):

    count = pd.read_sql(
        f"SELECT COUNT(*) as cnt FROM {table}",
        conn
    )

    rows = count.iloc[0]["cnt"]

    print(f"{i}. {table:<25} ({rows} rows)")

print("\n0. Exit")

choice = input(
    "\nSelect a table number to view data: "
).strip()

if choice == "0":
    print("Exiting...")
    conn.close()
    exit()

try:
    choice = int(choice)

    if choice < 1 or choice > len(tables):
        raise ValueError

    selected_table = tables[choice - 1]

    print("\n" + "=" * 60)
    print(f"TABLE: {selected_table}")
    print("=" * 60)

    df = pd.read_sql(
        f"SELECT * FROM {selected_table}",
        conn
    )

    if df.empty:
        print("\nNo rows found.")
    else:

        pd.set_option("display.max_columns", None)
        pd.set_option("display.width", 2000)
        pd.set_option("display.max_rows", None)

        print(df)

        print("\n" + "=" * 60)
        print(f"Total Rows: {len(df)}")
        print("=" * 60)

except ValueError:
    print("\n❌ Invalid selection")

conn.close()