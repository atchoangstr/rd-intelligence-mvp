from io import BytesIO
import pandas as pd
import pytest
from intelligence.db import initialize
from intelligence.imports import auto_mapping, validate, import_rows


@pytest.fixture
def database(tmp_path):
    path = tmp_path / 'test.sqlite3'
    initialize(path)
    return path


@pytest.fixture
def sale_frame():
    return pd.DataFrame([{'date': '2025-01-01', 'sku': 'DECOR-01', 'title': 'Synthetic vase',
                          'quantity': '2', 'revenue': '40.00', 'currency': 'USD'}])


def add_sales(path, frame, marketplace='Etsy', mode='daily_summary', filename='synthetic.csv'):
    mapping = auto_mapping(frame.columns)
    rows = validate(frame, mapping, marketplace, mode, filename)
    return import_rows(path, rows, marketplace, mode, filename, frame.to_csv(index=False).encode(), mapping)
