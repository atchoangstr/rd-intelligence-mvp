from io import BytesIO
import sqlite3
import pandas as pd
import pytest
from intelligence.db import connect, initialize
from intelligence.imports import (parse_file, auto_mapping, validate, preview_import, import_rows, counts,
                                  excel_sheets, row_report)
from intelligence.analytics import load_sales
from conftest import add_sales


def test_mapping_is_conservative():
    mapping = auto_mapping(['Order Date', 'Seller-SKU', 'Units Sold', 'Gross Sales', 'Currency'])
    assert mapping == {'date': 'Order Date', 'sku': 'Seller-SKU', 'quantity': 'Units Sold', 'revenue': 'Gross Sales', 'currency': 'Currency'}
    assert 'date' not in auto_mapping(['Order Date', 'Sales Date'])
    assert 'cost' not in auto_mapping(['Unknown'])


def test_parse_csv_and_excel(sale_frame):
    csv = parse_file(sale_frame.to_csv(index=False).encode(), 'synthetic.csv')
    assert csv.sku.iloc[0] == 'DECOR-01'
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        sale_frame.to_excel(writer, index=False, sheet_name='Sales')
    content = output.getvalue()
    assert excel_sheets(content) == ['Sales']
    assert parse_file(content, 'synthetic.xlsx', 'Sales').quantity.iloc[0] == '2'


@pytest.mark.parametrize('content,name', [(b'', 'a.csv'), (b'not excel', 'a.xlsx'), (b'abc', 'a.exe')])
def test_malformed_files(content, name):
    with pytest.raises(ValueError):
        parse_file(content, name)


def test_missing_cost_stays_unknown_and_currency_required(sale_frame):
    rows = validate(sale_frame, auto_mapping(sale_frame.columns), 'Etsy', 'daily_summary', 'a.csv')
    assert rows[0]['item']['cost'] is None
    sale_frame['currency'] = ''
    rows = validate(sale_frame, auto_mapping(sale_frame.columns), 'Etsy', 'daily_summary', 'a.csv')
    assert 'Currency' in rows[0]['error']
    rows = validate(sale_frame, auto_mapping(sale_frame.columns), 'Etsy', 'daily_summary', 'a.csv', default_currency='USD')
    assert not rows[0]['error']


@pytest.mark.parametrize('column,value', [('date', '2025-02-30'), ('sku', ''), ('quantity', '-1'), ('quantity', '1.5'), ('quantity', 'NaN'), ('revenue', ''), ('revenue', 'inf'), ('revenue', '$40'), ('fees', '-2')])
def test_invalid_data(sale_frame, column, value):
    sale_frame[column] = value
    rows = validate(sale_frame, auto_mapping(sale_frame.columns), 'Etsy', 'daily_summary', 'a.csv')
    assert rows[0]['error']


def test_mapping_must_not_reuse_columns(sale_frame):
    mapping = auto_mapping(sale_frame.columns)
    mapping['cost'] = 'revenue'
    with pytest.raises(ValueError, match='một lần'):
        validate(sale_frame, mapping, 'Etsy', 'daily_summary', 'a.csv')


def test_orders_require_stable_line_identity(sale_frame):
    with pytest.raises(ValueError, match='order_id'):
        validate(sale_frame, auto_mapping(sale_frame.columns), 'Etsy', 'order_lines', 'a.csv')


def test_summary_repeated_keys_are_rejected(sale_frame):
    frame = pd.concat([sale_frame, sale_frame], ignore_index=True)
    rows = validate(frame, auto_mapping(frame.columns), 'Etsy', 'daily_summary', 'a.csv')
    assert all(r['error'] for r in rows)


def test_repeated_and_renamed_files_do_not_duplicate(database, sale_frame):
    assert add_sales(database, sale_frame)[1]['accepted'] == 1
    assert add_sales(database, sale_frame, filename='renamed.csv')[1]['duplicated'] == 1
    sale_frame['revenue'] = '41'
    assert add_sales(database, sale_frame)[1]['rejected'] == 1
    with connect(database) as db:
        assert db.execute('SELECT COUNT(*) FROM sales').fetchone()[0] == 1
        assert db.execute('SELECT COUNT(*) FROM imports').fetchone()[0] == 3
        assert db.execute('SELECT COUNT(*) FROM source_rows').fetchone()[0] == 3
        assert db.execute('SELECT revenue FROM sales').fetchone()[0] == 40


def test_duplicate_order_lines_keep_provenance(database, sale_frame):
    sale_frame['order_id'] = 'ORDER-001'
    sale_frame['line_id'] = '001'
    frame = pd.concat([sale_frame, sale_frame], ignore_index=True)
    _, result = add_sales(database, frame, mode='order_lines')
    assert result == {'total': 2, 'accepted': 1, 'rejected': 0, 'duplicated': 1}
    with connect(database) as db:
        ids = [r[0] for r in db.execute('SELECT sale_id FROM source_rows')]
        assert ids[0] == ids[1]


def test_report_types_cannot_overlap(database, sale_frame):
    add_sales(database, sale_frame)
    sale_frame['order_id'] = 'o'
    sale_frame['line_id'] = 'l'
    with pytest.raises(ValueError, match='loại báo cáo khác'):
        add_sales(database, sale_frame, mode='order_lines')


def test_transaction_rolls_back_on_database_failure(database, sale_frame):
    add_sales(database, sale_frame)
    with connect(database) as db:
        db.execute("CREATE TRIGGER simulate_disk_error BEFORE INSERT ON source_rows BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
    sale_frame['date'] = '2025-01-02'
    with pytest.raises(sqlite3.IntegrityError):
        add_sales(database, sale_frame)
    with connect(database) as db:
        assert db.execute('SELECT COUNT(*) FROM sales').fetchone()[0] == 1
        assert db.execute('SELECT COUNT(*) FROM imports').fetchone()[0] == 1


def test_rejected_rows_are_auditable(database, sale_frame):
    invalid = sale_frame.copy()
    invalid['sku'] = ''
    frame = pd.concat([sale_frame, invalid], ignore_index=True)
    _, result = add_sales(database, frame)
    assert result['accepted'] == result['rejected'] == 1
    with connect(database) as db:
        rejected = db.execute("SELECT * FROM source_rows WHERE status='rejected'").fetchone()
        assert rejected['source_row'] == 3
        assert 'sku' in rejected['error']
        assert db.execute('SELECT status FROM imports').fetchone()[0] == 'partial'
    initialize(database)
    assert len(load_sales(database)) == 1


def test_csv_leading_zero_identifiers():
    data = b'date,sku,quantity,revenue,currency\n2025-01-01,000123,1,20,USD\n'
    assert parse_file(data, 'a.csv').sku.iloc[0] == '000123'


def test_size_and_row_limits(monkeypatch):
    from intelligence import imports
    monkeypatch.setattr(imports, 'MAX_UPLOAD_BYTES', 4)
    with pytest.raises(ValueError, match='20 MB'):
        parse_file(b'012345', 'a.csv')
    monkeypatch.setattr(imports, 'MAX_UPLOAD_BYTES', 1000)
    monkeypatch.setattr(imports, 'MAX_ROWS', 1)
    with pytest.raises(ValueError, match='100.000'):
        parse_file(b'sku\na\nb\n', 'a.csv')


def test_explicit_date_format_and_missing_mapping(sale_frame):
    sale_frame['date'] = '01/02/2025'
    mapping = auto_mapping(sale_frame.columns)
    rows = validate(sale_frame, mapping, 'Etsy', 'daily_summary', 'a.csv', date_format='%d/%m/%Y')
    assert rows[0]['item']['date'] == '2025-02-01'
    del mapping['quantity']
    with pytest.raises(ValueError, match='quantity'):
        validate(sale_frame, mapping, 'Etsy', 'daily_summary', 'a.csv')


def test_foreign_keys_and_newer_schema_guard(database):
    with connect(database) as db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO concepts VALUES(999,'{}',CURRENT_TIMESTAMP)")
        db.execute('PRAGMA user_version=2')
    with pytest.raises(ValueError, match='newer'):
        initialize(database)


def test_unmapped_personal_data_is_not_persisted(database, sale_frame):
    sale_frame['customer_email'] = 'synthetic@example.invalid'
    add_sales(database, sale_frame)
    with connect(database) as db:
        assert 'customer_email' not in db.execute('SELECT raw_json FROM source_rows').fetchone()[0]


def test_csv_to_preview_import_analysis_and_export(database):
    from intelligence.analytics import metrics
    from intelligence.exports import export_excel
    content = ('Sales Date,Seller SKU,Units Sold,Gross Sales,Currency\n'
               '2025-01-01,001,2,40,USD\n'
               'bad-date,002,1,20,USD\n').encode()
    frame = parse_file(content, 'synthetic.csv')
    mapping = auto_mapping(frame.columns)
    rows = validate(frame, mapping, 'Amazon US', 'daily_summary', 'synthetic.csv')
    preview = preview_import(database, rows, 'Amazon US', 'daily_summary')
    assert counts(preview) == {'total': 2, 'accepted': 1, 'rejected': 1, 'duplicated': 0}
    rejected = row_report(preview)
    assert rejected.loc[1, 'source_row'] == 3
    assert rejected.loc[1, 'error']
    import_rows(database, rows, 'Amazon US', 'daily_summary', 'synthetic.csv', content, mapping)
    summary = metrics(load_sales(database))
    assert summary.reported_revenue.iloc[0] == 40
    roundtrip = pd.read_excel(BytesIO(export_excel(summary)))
    assert roundtrip.currency.iloc[0] == 'USD'
    assert roundtrip.reported_revenue.iloc[0] == 40
    assert counts(preview_import(database, rows, 'Amazon US', 'daily_summary'))['duplicated'] == 1


def test_mixed_marketplace_rows_are_not_silently_reassigned(sale_frame):
    sale_frame['marketplace'] = 'Amazon US'
    mapping = auto_mapping(sale_frame.columns)
    rows = validate(sale_frame, mapping, 'Etsy', 'daily_summary', 'a.csv')
    assert 'Marketplace' in rows[0]['error']
    rows = validate(sale_frame, mapping, 'Amazon US', 'daily_summary', 'a.csv')
    assert not rows[0]['error']
