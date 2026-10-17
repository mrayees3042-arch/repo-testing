import sqlite3
import os
import json
import logging

logger = logging.getLogger(__name__)

DB_PATH = "repogen.db"

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        cursor = self.conn.cursor()
        
        # Tag Tables
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS tag_tables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT
        )
        ''')
        
        # Tags
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_id INTEGER,
            name TEXT NOT NULL,
            area TEXT NOT NULL,
            db_number INTEGER,
            address TEXT NOT NULL,
            data_type TEXT NOT NULL,
            access_mode TEXT NOT NULL,
            description TEXT,
            FOREIGN KEY(table_id) REFERENCES tag_tables(id) ON DELETE CASCADE
        )
        ''')
        
        self.conn.commit()

    # --- Tag Tables ---
    def get_all_tables(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM tag_tables")
        return [dict(row) for row in cursor.fetchall()]

    def create_table(self, name, description=""):
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO tag_tables (name, description) VALUES (?, ?)", (name, description))
        self.conn.commit()
        return cursor.lastrowid

    def update_table(self, table_id, name, description=""):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE tag_tables SET name=?, description=? WHERE id=?", (name, description, table_id))
        self.conn.commit()

    def delete_table(self, table_id):
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("DELETE FROM tag_tables WHERE id=?", (table_id,))
        self.conn.commit()

    # --- Tags ---
    def get_tags_for_table(self, table_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM tags WHERE table_id=?", (table_id,))
        return [dict(row) for row in cursor.fetchall()]

    def create_tag(self, table_id, name, area, db_number, address, data_type, access_mode, description=""):
        cursor = self.conn.cursor()
        cursor.execute('''
        INSERT INTO tags (table_id, name, area, db_number, address, data_type, access_mode, description) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (table_id, name, area, db_number, address, data_type, access_mode, description))
        self.conn.commit()
        return cursor.lastrowid

    def update_tag(self, tag_id, name, area, db_number, address, data_type, access_mode, description=""):
        cursor = self.conn.cursor()
        cursor.execute('''
        UPDATE tags SET name=?, area=?, db_number=?, address=?, data_type=?, access_mode=?, description=? 
        WHERE id=?
        ''', (name, area, db_number, address, data_type, access_mode, description, tag_id))
        self.conn.commit()

    def delete_tag(self, tag_id):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM tags WHERE id=?", (tag_id,))
        self.conn.commit()

    def get_tag(self, tag_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM tags WHERE id=?", (tag_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
