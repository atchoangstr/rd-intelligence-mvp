"""Versioned, additive SQLite schema. No destructive startup migrations."""
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from .config import DB_PATH

SCHEMA = '''
CREATE TABLE IF NOT EXISTS imports (
 id INTEGER PRIMARY KEY, imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 marketplace TEXT NOT NULL, filename TEXT NOT NULL, file_hash TEXT NOT NULL,
 mapping_json TEXT NOT NULL, mode TEXT NOT NULL, total INTEGER NOT NULL,
 accepted INTEGER NOT NULL, rejected INTEGER NOT NULL, duplicated INTEGER NOT NULL,
 status TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS products (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL DEFAULT '',
 attributes TEXT NOT NULL DEFAULT '', production_method TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS sku_mappings (
 id INTEGER PRIMARY KEY, marketplace TEXT NOT NULL, sku TEXT NOT NULL,
 title TEXT NOT NULL DEFAULT '', category TEXT NOT NULL DEFAULT '',
 product_id INTEGER REFERENCES products(id), UNIQUE(marketplace,sku));
CREATE TABLE IF NOT EXISTS costs (
 id INTEGER PRIMARY KEY, mapping_id INTEGER NOT NULL REFERENCES sku_mappings(id),
 effective_date TEXT NOT NULL, currency TEXT NOT NULL, unit_cost REAL NOT NULL CHECK(unit_cost>=0),
 UNIQUE(mapping_id,effective_date,currency));
CREATE TABLE IF NOT EXISTS sales (
 id INTEGER PRIMARY KEY, import_id INTEGER NOT NULL REFERENCES imports(id),
 mapping_id INTEGER NOT NULL REFERENCES sku_mappings(id), date TEXT NOT NULL,
 currency TEXT NOT NULL, quantity REAL NOT NULL, revenue REAL NOT NULL,
 discounts REAL, refunds REAL, fees REAL, shipping REAL, cost REAL,
 order_id TEXT, line_id TEXT, identity_key TEXT NOT NULL UNIQUE, payload_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS source_rows (
 id INTEGER PRIMARY KEY, import_id INTEGER NOT NULL REFERENCES imports(id),
 source_row INTEGER NOT NULL, raw_json TEXT NOT NULL, status TEXT NOT NULL,
 error TEXT NOT NULL DEFAULT '', sale_id INTEGER REFERENCES sales(id));
CREATE TABLE IF NOT EXISTS opportunities (
 id INTEGER PRIMARY KEY, opportunity_key TEXT NOT NULL UNIQUE,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, mapping_id INTEGER NOT NULL REFERENCES sku_mappings(id),
 type TEXT NOT NULL, concept TEXT NOT NULL, evidence_json TEXT NOT NULL,
 assumptions TEXT NOT NULL, next_action TEXT NOT NULL, upside TEXT NOT NULL,
 risk TEXT NOT NULL, confidence REAL NOT NULL, score REAL,
 score_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'New', notes TEXT NOT NULL DEFAULT '',
 target_date TEXT, actual_results TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS decisions (
 id INTEGER PRIMARY KEY, opportunity_id INTEGER NOT NULL REFERENCES opportunities(id),
 changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, previous_status TEXT NOT NULL,
 new_status TEXT NOT NULL, reason TEXT NOT NULL, details_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS concepts (
 opportunity_id INTEGER PRIMARY KEY REFERENCES opportunities(id),
 brief_json TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS sales_date_idx ON sales(date,currency);
CREATE INDEX IF NOT EXISTS sales_mapping_idx ON sales(mapping_id,date);
CREATE INDEX IF NOT EXISTS source_import_idx ON source_rows(import_id);
CREATE INDEX IF NOT EXISTS decisions_opportunity_idx ON decisions(opportunity_id);
'''

@contextmanager
def connect(path=DB_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys=ON')
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

def initialize(path=DB_PATH):
    with connect(path) as db:
        version = db.execute('PRAGMA user_version').fetchone()[0]
        if version > 1:
            raise ValueError('Database version is newer than this application. Use the matching application version.')
        db.executescript(SCHEMA)
        db.execute('PRAGMA user_version=1')
