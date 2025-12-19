import mysql.connector
import os
import config

DB_HOST = config.DB_HOST
DB_NAME = config.DB_NAME
DB_USER = config.DB_USER
DB_PASSWORD = config.DB_PASSWORD
DB_PORT = int(config.DB_PORT)

conn = mysql.connector.connect(
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASSWORD,
    database=DB_NAME,
    port=DB_PORT
)

cursor = conn.cursor()

cursor.execute("SHOW TABLES")
tables = cursor.fetchall()

for table in tables:
    table_name = table[0]
    print(f"Table: {table_name}")
    
    cursor.execute(f"DESCRIBE {table_name}")
    columns = cursor.fetchall()
    print("Columns:")
    for col in columns:
        print(f"  {col[0]}: {col[1]}")
    
    cursor.execute(f"SELECT * FROM {table_name} LIMIT 5")
    rows = cursor.fetchall()
    print("First 5 rows:")
    for row in rows:
        # Truncate each column value to 100 characters
        truncated_row = []
        for value in row:
            if value is not None:
                str_value = str(value)
                if len(str_value) > 100:
                    truncated_row.append(str_value[:50] + "...")
                else:
                    truncated_row.append(str_value)
            else:
                truncated_row.append(None)
        print(f"  {tuple(truncated_row)}")
    print()

cursor.close()
conn.close()