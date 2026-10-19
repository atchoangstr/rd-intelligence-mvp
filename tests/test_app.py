"""Render every navigation page with isolated synthetic SQLite data."""
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
from intelligence import config
from intelligence.analytics import load_sales
from intelligence.opportunities import generate
from conftest import add_sales

PAGES = ['Tổng quan', 'Import dữ liệu', 'Sản phẩm & SKU', 'Phân tích bán hàng', 'Cơ hội R&D', 'Phát triển concept', 'Lịch sử import', 'Cài đặt']


@pytest.mark.parametrize('populated', [False, True])
def test_navigation_pages(database, sale_frame, monkeypatch, populated):
    monkeypatch.setattr(config, 'DB_PATH', database)
    if populated:
        add_sales(database, sale_frame)
        generate(database, load_sales(database), '2025-01-02')
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / 'app.py', default_timeout=20).run()
    assert not app.exception
    assert app.title[0].value == 'R&D Intelligence MVP'
    for page in PAGES:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception, f'Failed page: {page}'
        assert not app.error, f'Unexpected UI error: {page}'


def test_opportunity_edit_concept_and_backup(database, sale_frame, monkeypatch):
    monkeypatch.setattr(config, 'DB_PATH', database)
    add_sales(database, sale_frame)
    generate(database, load_sales(database), '2025-01-02')
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / 'app.py', default_timeout=20).run()
    app.sidebar.radio[0].set_value('Cơ hội R&D').run()
    app.text_area[0].set_value('Synthetic custom concept')
    app.text_area[1].set_value('Synthetic notes')
    app.button[-1].click().run()
    assert not app.exception
    from intelligence.opportunities import list_opportunities
    assert list_opportunities(database).concept.iloc[0] == 'Synthetic custom concept'
    app.sidebar.radio[0].set_value('Phát triển concept').run()
    app.button[0].click().run()
    assert not app.exception
    app.sidebar.radio[0].set_value('Cài đặt').run()
    app.button[0].click().run()
    assert not app.exception
    assert not app.error
