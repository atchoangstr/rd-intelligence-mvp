"""Explicit report semantics, validation, and transactional deduplication."""
from collections import Counter
from io import BytesIO
from pathlib import Path
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import re
import zipfile
import pandas as pd
from .config import MAX_UPLOAD_BYTES, MAX_ROWS, MARKETPLACES
from .db import connect

FIELDS = ['marketplace', 'date', 'sku', 'title', 'quantity', 'revenue', 'currency', 'order_id', 'line_id', 'discounts', 'refunds', 'fees', 'shipping', 'cost', 'category']
REQUIRED = ['date', 'sku', 'quantity', 'revenue', 'currency']
EXPENSES = ['discounts', 'refunds', 'fees', 'shipping', 'cost']
ALIASES = {
 'marketplace': ['marketplace', 'sales channel'],
 'date': ['date', 'order date', 'sales date', 'purchase date'],
 'sku': ['sku', 'marketplace sku', 'seller sku', 'seller-sku'],
 'title': ['title', 'product title', 'product name', 'item name'],
 'quantity': ['quantity', 'quantity sold', 'units', 'units sold'],
 'revenue': ['revenue', 'gross sales', 'sales'],
 'currency': ['currency', 'currency code'],
 'order_id': ['order id', 'amazon order id', 'order number'],
 'line_id': ['line id', 'order item id', 'order line id'],
 'category': ['category', 'product type'],
 **{f: [f] for f in EXPENSES},
}

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)

def auto_mapping(columns):
    normalize = lambda s: re.sub(r'[^a-z0-9]', '', str(s).lower())
    result = {}
    for field, aliases in ALIASES.items():
        matches = [c for c in columns if normalize(c) in {normalize(a) for a in aliases}]
        if len(matches) == 1:
            result[field] = matches[0]
    return result

def parse_file(content, filename, sheet=0):
    if not content or len(content) > MAX_UPLOAD_BYTES:
        raise ValueError('Tệp rỗng hoặc vượt giới hạn 20 MB.')
    extension = Path(filename).suffix.lower()
    try:
        if extension == '.csv':
            df = pd.read_csv(BytesIO(content), dtype=str, keep_default_na=False, encoding='utf-8-sig', nrows=MAX_ROWS + 1)
        elif extension == '.xlsx':
            with zipfile.ZipFile(BytesIO(content)) as archive:
                if sum(i.file_size for i in archive.infolist()) > 100 * 1024 * 1024:
                    raise ValueError('Excel giải nén vượt giới hạn 100 MB.')
            df = pd.read_excel(BytesIO(content), sheet_name=sheet, dtype=str, keep_default_na=False, engine='openpyxl', nrows=MAX_ROWS + 1)
        else:
            raise ValueError('Chỉ hỗ trợ CSV UTF-8 hoặc Excel .xlsx; không hỗ trợ macro hay .xls.')
    except Exception as exc:
        if isinstance(exc, ValueError) and str(exc).startswith(('Chỉ hỗ trợ', 'Excel giải')):
            raise
        raise ValueError('Không đọc được tệp. Kiểm tra định dạng, encoding UTF-8, dấu phẩy và trang Excel.') from exc
    if df.empty or len(df) > MAX_ROWS:
        raise ValueError('Tệp cần 1–100.000 dòng dữ liệu.')
    return df

def excel_sheets(content):
    # Apply ZIP and file limits before pandas opens workbook metadata.
    parse_file(content, 'workbook.xlsx')
    return pd.ExcelFile(BytesIO(content), engine='openpyxl').sheet_names

def text(value):
    return '' if pd.isna(value) else str(value).strip()

def number(value, field):
    raw = text(value)
    if not raw:
        raise ValueError(f'{field}: thiếu số; không được tự coi là 0.')
    try:
        result = Decimal(raw)
    except InvalidOperation:
        raise ValueError(f'{field}: số không hợp lệ; dùng dấu chấm thập phân, không ký hiệu tiền tệ/phân cách nghìn.') from None
    if not result.is_finite() or result < 0 or not math.isfinite(float(result)):
        raise ValueError(f'{field}: cần số hữu hạn không âm.')
    return float(result)

def validate(df, mapping, marketplace, mode, filename, default_currency='', date_format='%Y-%m-%d'):
    if marketplace not in MARKETPLACES or mode not in ('daily_summary', 'order_lines'):
        raise ValueError('Chọn marketplace và loại báo cáo được hỗ trợ.')
    required = REQUIRED + (['order_id', 'line_id'] if mode == 'order_lines' else [])
    missing = [f for f in required if not mapping.get(f) and not (f == 'currency' and default_currency)]
    if missing:
        raise ValueError('Chưa map cột bắt buộc: ' + ', '.join(missing))
    selected = [v for v in mapping.values() if v]
    if len(selected) != len(set(selected)) or any(v not in df.columns for v in selected):
        raise ValueError('Mỗi cột nguồn chỉ được map một lần và phải tồn tại.')
    rows = []
    for position, (_, source) in enumerate(df.iterrows(), 2):
        raw = {f: text(source[c]) for f, c in mapping.items() if c and f in FIELDS}
        item = {f: raw.get(f, '') for f in FIELDS}
        errors = []
        source_market = item['marketplace']
        aliases = {'amazon': 'Amazon US', 'amazon.com': 'Amazon US', 'tiktok shop': 'TikTok Shop US'}
        source_market = aliases.get(source_market.lower(), source_market)
        if source_market and source_market.casefold() != marketplace.casefold():
            errors.append('Marketplace trong dòng khác marketplace đã chọn. Tách tệp theo marketplace trước khi import.')
        item['marketplace'] = marketplace
        for field in ['sku'] + (['order_id', 'line_id'] if mode == 'order_lines' else []):
            if not item[field]:
                errors.append(f'{field}: không được để trống.')
        try:
            parsed = pd.to_datetime(item['date'], format=date_format, errors='raise')
            if pd.isna(parsed):
                raise ValueError()
            item['date'] = parsed.date().isoformat()
        except (ValueError, TypeError, OverflowError):
            errors.append('Ngày không hợp lệ hoặc không đúng định dạng đã chọn.')
        item['currency'] = (item['currency'] or default_currency).upper().strip()
        if not re.fullmatch('[A-Z]{3}', item['currency']):
            errors.append('Currency: cần mã 3 chữ cái; không suy đoán tiền tệ.')
        for field in ['quantity', 'revenue'] + EXPENSES:
            if field in EXPENSES and not item[field]:
                item[field] = None
                continue
            try:
                item[field] = number(item[field], field)
                if field == 'quantity' and (item[field] <= 0 or not item[field].is_integer()):
                    errors.append('Quantity: cần số nguyên dương. Báo cáo trả hàng tách riêng chưa được hỗ trợ.')
            except ValueError as exc:
                errors.append(str(exc))
        if not errors:
            identity = [marketplace, mode, item['order_id'], item['line_id']] if mode == 'order_lines' else [marketplace, mode, item['date'], item['sku'], item['currency']]
            item['identity_key'] = digest(encode(identity))
            item['payload_hash'] = digest(encode({f: item[f] for f in FIELDS if f not in ('title', 'category')}))
        rows.append({'row': position, 'raw': raw, 'item': item, 'error': ' '.join(errors), 'filename': Path(filename).name})
    # A summary is one row per day/SKU/currency. Repeated keys within it are ambiguous.
    if mode == 'daily_summary':
        keys = [r['item'].get('identity_key') for r in rows if not r['error']]
        repeated = {k for k, n in Counter(keys).items() if n > 1}
        for row in rows:
            if row['item'].get('identity_key') in repeated:
                row['error'] = 'Nhiều dòng cùng ngày/SKU/currency: tổng hợp rõ ràng trước khi import summary.'
    return rows

def classify(db, rows, marketplace, mode):
    existing_mode = db.execute('SELECT DISTINCT mode FROM imports WHERE marketplace=? AND accepted>0', (marketplace,)).fetchall()
    if any(r['mode'] != mode for r in existing_mode):
        raise ValueError('Marketplace này đã dùng loại báo cáo khác. Không trộn summary và order lines vì có thể đếm đôi.')
    seen = {}
    classified = []
    for row in rows:
        row = dict(row)
        row['status'] = 'rejected' if row['error'] else 'accepted'
        row['sale_id'] = None
        if not row['error']:
            item = row['item']
            existing = db.execute('SELECT id,payload_hash FROM sales WHERE identity_key=?', (item['identity_key'],)).fetchone()
            prior_hash = existing['payload_hash'] if existing else seen.get(item['identity_key'])
            if prior_hash is not None:
                if prior_hash == item['payload_hash']:
                    row['status'] = 'duplicated'
                    row['error'] = 'Định danh và số liệu đã tồn tại; không thêm sales lần nữa.'
                    row['sale_id'] = existing['id'] if existing else None
                else:
                    row['status'] = 'rejected'
                    row['error'] = 'Cùng định danh nhưng số liệu khác: cần đối soát, không ghi đè dữ liệu cũ.'
            else:
                seen[item['identity_key']] = item['payload_hash']
        classified.append(row)
    return classified

def preview_import(path, rows, marketplace, mode):
    with connect(path) as db:
        return classify(db, rows, marketplace, mode)

def counts(rows):
    return {'total': len(rows), **{s: sum(r['status'] == s for r in rows) for s in ['accepted', 'rejected', 'duplicated']}}

def import_rows(path, rows, marketplace, mode, filename, content, mapping):
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        classified = classify(db, rows, marketplace, mode)
        count = counts(classified)
        status = 'partial' if count['rejected'] else ('duplicate' if count['duplicated'] == count['total'] else 'completed')
        cursor = db.execute('INSERT INTO imports(marketplace,filename,file_hash,mapping_json,mode,total,accepted,rejected,duplicated,status) VALUES(?,?,?,?,?,?,?,?,?,?)', (marketplace, Path(filename).name, hashlib.sha256(content).hexdigest(), encode(mapping), mode, *[count[k] for k in ['total', 'accepted', 'rejected', 'duplicated']], status))
        import_id = cursor.lastrowid
        for row in classified:
            item = row['item']
            sale_id = row['sale_id']
            if row['status'] == 'accepted':
                db.execute('INSERT INTO sku_mappings(marketplace,sku,title,category) VALUES(?,?,?,?) ON CONFLICT(marketplace,sku) DO NOTHING', (marketplace, item['sku'], item['title'], item['category']))
                mapping_id = db.execute('SELECT id FROM sku_mappings WHERE marketplace=? AND sku=?', (marketplace, item['sku'])).fetchone()['id']
                fields = ['date', 'currency', 'quantity', 'revenue', *EXPENSES, 'order_id', 'line_id', 'identity_key', 'payload_hash']
                sale_id = db.execute(f'INSERT INTO sales(import_id,mapping_id,{",".join(fields)}) VALUES({",".join("?" for _ in range(len(fields)+2))})', (import_id, mapping_id, *[item[f] for f in fields])).lastrowid
            elif row['status'] == 'duplicated' and sale_id is None:
                sale_id = db.execute('SELECT id FROM sales WHERE identity_key=?', (item['identity_key'],)).fetchone()['id']
            db.execute('INSERT INTO source_rows(import_id,source_row,raw_json,status,error,sale_id) VALUES(?,?,?,?,?,?)', (import_id, row['row'], encode(row['raw']), row['status'], row['error'], sale_id))
    return import_id, count

def row_report(rows):
    return pd.DataFrame([{'source_file': r['filename'], 'source_row': r['row'], 'status': r['status'], 'error': r['error'], **r['raw']} for r in rows])
