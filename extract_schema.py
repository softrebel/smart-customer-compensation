
import sqlite3
import json

conn = sqlite3.connect("crm.db")
conn.row_factory = sqlite3.Row

tables = conn.execute("""
    SELECT name
    FROM sqlite_master
    WHERE type = 'table'
      AND name NOT LIKE 'sqlite_%'
    ORDER BY name;
""").fetchall()

schema = {}

for row in tables:
    table = row["name"]

    columns = conn.execute(
        f'PRAGMA table_info("{table.replace(chr(34), chr(34)*2)}")'
    ).fetchall()

    schema[table] = [
        {
            "name": col["name"],
            "type": col["type"],
            "not_null": bool(col["notnull"]),
            "primary_key_position": col["pk"],
            "default": col["dflt_value"],
        }
        for col in columns
    ]

with open("schema.json", "w", encoding="utf-8") as f:
    json.dump(schema, f, ensure_ascii=False, indent=2)

conn.close()
print("Schema exported to schema.json")
