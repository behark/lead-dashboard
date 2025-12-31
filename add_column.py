#!/usr/bin/env python3
import sqlite3

def add_default_column():
    conn = sqlite3.connect('leads.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('ALTER TABLE message_templates ADD COLUMN is_default BOOLEAN DEFAULT 0')
        conn.commit()
        print("✅ is_default column added successfully!")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("✅ is_default column already exists!")
        else:
            print(f"Error: {e}")
    
    conn.close()

if __name__ == '__main__':
    add_default_column()