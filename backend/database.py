import sqlite3
import os
import sys
import json
import logging
import threading

logger = logging.getLogger(__name__)

# Preserve the portable app's database beside its executable, or fallback to %LOCALAPPDATA%
# if the executable directory is read-only (e.g. installed under C:\Program Files\).
_data_dir = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
             else os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def _resolve_db_path():
    candidate = os.path.join(_data_dir, "repogen.db")
    try:
        # Test write permission in candidate directory
        if not os.path.exists(_data_dir) or not os.access(_data_dir, os.W_OK):
            raise PermissionError("Directory not writable")
        with open(candidate, "a"):
            pass
        return candidate
    except Exception:
        appdata = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or os.path.expanduser("~")
        fallback_dir = os.path.join(appdata, "RepoGen")
        os.makedirs(fallback_dir, exist_ok=True)
        return os.path.join(fallback_dir, "repogen.db")

DB_PATH = _resolve_db_path()

class Database:
    def __init__(self):
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        with self._lock:
            self.conn.execute("PRAGMA foreign_keys = ON")
            self._init_db()

    def _init_db(self):
        with self._lock:
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
            
            self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS tag_groups (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS group_members (
                group_id INTEGER REFERENCES tag_groups(id) ON DELETE CASCADE,
                tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
                PRIMARY KEY(group_id, tag_id));
            CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """)
            self.conn.commit()

    def get_groups(self):
        with self._lock:
            return [dict(r) for r in self.conn.execute("SELECT * FROM tag_groups ORDER BY name")]

    def get_group_tags(self, group_id):
        with self._lock:
            return [dict(r) for r in self.conn.execute("SELECT t.* FROM tags t JOIN group_members m ON t.id=m.tag_id WHERE m.group_id=? ORDER BY t.name", (group_id,))]

    def save_group(self, group_id, name, tag_ids):
        name = str(name).strip()
        if not name or len(name) > 80:
            raise ValueError("Use a group name between 1 and 80 characters.")
        ids = list(dict.fromkeys(int(i) for i in tag_ids))
        with self._lock:
            with self.conn:
                if group_id is None:
                    group_id = self.conn.execute("INSERT INTO tag_groups(name) VALUES(?)", (name,)).lastrowid
                elif self.conn.execute("UPDATE tag_groups SET name=? WHERE id=?", (name, group_id)).rowcount != 1:
                    raise ValueError("This group no longer exists.")
                self.conn.execute("DELETE FROM group_members WHERE group_id=?", (group_id,))
                self.conn.executemany("INSERT INTO group_members VALUES(?, ?)", [(group_id, i) for i in ids])
            return group_id

    def delete_group(self, group_id):
        with self._lock:
            with self.conn:
                self.conn.execute("DELETE FROM tag_groups WHERE id=?", (group_id,))

    # --- Tag Tables ---
    def get_all_tables(self):
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM tag_tables")
            return [dict(row) for row in cursor.fetchall()]

    def create_table(self, name, description=""):
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("INSERT INTO tag_tables (name, description) VALUES (?, ?)", (name, description))
            self.conn.commit()
            return cursor.lastrowid

    def update_table(self, table_id, name, description=""):
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("UPDATE tag_tables SET name=?, description=? WHERE id=?", (name, description, table_id))
            self.conn.commit()

    def delete_table(self, table_id):
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.execute("DELETE FROM tag_tables WHERE id=?", (table_id,))
            self.conn.commit()

    # --- Tags ---
    def get_tags_for_table(self, table_id):
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM tags WHERE table_id=?", (table_id,))
            return [dict(row) for row in cursor.fetchall()]

    def create_tag(self, table_id, name, area, db_number, address, data_type, access_mode, description=""):
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute('''
            INSERT INTO tags (table_id, name, area, db_number, address, data_type, access_mode, description) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (table_id, name, area, db_number, address, data_type, access_mode, description))
            self.conn.commit()
            return cursor.lastrowid

    def update_tag(self, tag_id, name, area, db_number, address, data_type, access_mode, description=""):
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute('''
            UPDATE tags SET name=?, area=?, db_number=?, address=?, data_type=?, access_mode=?, description=? 
            WHERE id=?
            ''', (name, area, db_number, address, data_type, access_mode, description, tag_id))
            self.conn.commit()

    def delete_tag(self, tag_id):
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM tags WHERE id=?", (tag_id,))
            self.conn.commit()

    def get_tag(self, tag_id):
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM tags WHERE id=?", (tag_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
