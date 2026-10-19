"""Explicit catalog linking and dated cost records."""
import pandas as pd
from .db import connect
from .imports import number

def catalog(path):
    with connect(path) as db:
        return pd.read_sql_query('''SELECT m.*,p.name AS canonical_name,p.category AS canonical_category,
        p.attributes,p.production_method FROM sku_mappings m LEFT JOIN products p ON p.id=m.product_id''', db)

def link_product(path, mapping_id, product_id=None, name='', category='', attributes='', production_method=''):
    with connect(path) as db:
        if db.execute('SELECT id FROM sku_mappings WHERE id=?', (mapping_id,)).fetchone() is None:
            raise ValueError('SKU không tồn tại.')
        if product_id is None:
            if not name.strip():
                raise ValueError('Cần tên sản phẩm chuẩn.')
            product_id = db.execute('INSERT INTO products(name,category,attributes,production_method) VALUES(?,?,?,?)', (name.strip(), category, attributes, production_method)).lastrowid
        elif db.execute('SELECT id FROM products WHERE id=?', (product_id,)).fetchone() is None:
            raise ValueError('Sản phẩm chuẩn không tồn tại.')
        db.execute('UPDATE sku_mappings SET product_id=? WHERE id=?', (product_id, mapping_id))
    return product_id

def update_product(path, product_id, name, category, attributes, production_method):
    if not name.strip():
        raise ValueError('Cần tên sản phẩm.')
    with connect(path) as db:
        db.execute('UPDATE products SET name=?,category=?,attributes=?,production_method=? WHERE id=?', (name.strip(), category, attributes, production_method, product_id))

def set_cost(path, mapping_id, effective_date, currency, unit_cost):
    date = pd.Timestamp(effective_date).date().isoformat()
    if len(currency) != 3 or not currency.isalpha():
        raise ValueError('Cần mã currency 3 chữ cái.')
    cost = number(unit_cost, 'unit_cost')
    with connect(path) as db:
        db.execute('INSERT INTO costs(mapping_id,effective_date,currency,unit_cost) VALUES(?,?,?,?) ON CONFLICT(mapping_id,effective_date,currency) DO UPDATE SET unit_cost=excluded.unit_cost', (mapping_id, date, currency.upper(), cost))
