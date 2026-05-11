"""
migrate_dept.py

This module contains core functionality for the Nexus application.
"""

import sqlite3
import json

db_path = "H:/nexus/nexus.db"

conn = sqlite3.connect(db_path)
c = conn.cursor()

try:
    c.execute("ALTER TABLE documents ADD COLUMN departments JSON NOT NULL DEFAULT '[]';")
    print("Added departments column.")
except Exception as e:
    print(f"Error adding departments: {e}")

# Migrate existing data
c.execute("SELECT id, department FROM documents;")
rows = c.fetchall()

for doc_id, dept in rows:
    dept_list = []
    if dept:
        dept_list.append(dept)
    
    # Store as JSON string
    c.execute("UPDATE documents SET departments = ? WHERE id = ?", (json.dumps(dept_list), doc_id))

print(f"Migrated {len(rows)} documents.")

conn.commit()
conn.close()
