import sqlite3

# Replace with your real database filename if different
db_path = 'database.db'

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Add the missing column
try:
    cursor.execute('ALTER TABLE unfinished_operations ADD COLUMN message_id INTEGER;')
    print("✅ Column 'message_id' added successfully.")
except sqlite3.OperationalError as e:
    print(f"⚠️ Error: {e}")

conn.commit()
conn.close()
