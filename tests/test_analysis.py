import json
from datetime import date
import pandas as pd
import pytest
from intelligence.db import connect
from intelligence.catalog import catalog, link_product, update_product, set_cost
from intelligence.analytics import load_sales, metrics, performance, filter_sales, compare_periods, trends, concentration
from intelligence.opportunities import generate, score_factors, list_opportunities, update_opportunity, concept_template, save_brief
from intelligence.exports import export_csv, export_excel
from conftest import add_sales


def test_currency_separation_and_sku_namespaces(database, sale_frame):
    add_sales(database, sale_frame)
    add_sales(database, sale_frame, marketplace='Amazon US')
    euro = sale_frame.copy()
    euro['currency'] = 'EUR'
    add_sales(database, euro)
    sales = load_sales(database)
    totals = metrics(sales).set_index('currency')
    assert totals.loc['USD', 'reported_revenue'] == 80
    assert totals.loc['EUR', 'reported_revenue'] == 40
    assert len(catalog(database)) == 2
    assert sales.profit.isna().all()
    assert totals.profit.isna().all()
    assert len(filter_sales(sales, currency='EUR')) == 1
    assert len(filter_sales(sales, marketplaces=[])) == 0
    assert len(trends(sales)) == 2
    assert len(concentration(sales)) == 2


def test_catalog_links_and_dated_costs(database, sale_frame):
    add_sales(database, sale_frame)
    add_sales(database, sale_frame, marketplace='eBay')
    mappings = catalog(database)
    first, second = mappings.id.tolist()
    product = link_product(database, first, name='Synthetic family', attributes='ceramic', production_method='printing')
    link_product(database, second, product_id=product)
    assert catalog(database).product_id.nunique() == 1
    update_product(database, product, 'Synthetic family', 'Decor', 'white ceramic', 'printing')
    set_cost(database, first, '2025-01-02', 'USD', '8')
    assert load_sales(database).effective_cost.isna().all()
    set_cost(database, first, '2024-12-01', 'EUR', '3')
    assert load_sales(database).effective_cost.isna().all()
    set_cost(database, first, '2024-12-01', 'USD', '5')
    sales = load_sales(database)
    assert sales[sales.mapping_id == first].effective_cost.iloc[0] == 10
    assert sales.profit.isna().all()  # missing fees/shipping/etc still unknown


def test_profit_only_with_complete_financials(database, sale_frame):
    for field, value in {'discounts': '1', 'refunds': '0', 'fees': '3', 'shipping': '4', 'cost': '10'}.items():
        sale_frame[field] = value
    add_sales(database, sale_frame)
    sales = load_sales(database)
    assert sales.profit.iloc[0] == 22
    assert metrics(sales).margin_percent.iloc[0] == 55
    assert metrics(sales).average_selling_price.iloc[0] == 20
    assert metrics(sales).active_skus.iloc[0] == 1


def rich_frame():
    records = []
    for day in pd.date_range('2025-01-01', '2025-03-01'):
        records.append({'date': day.date().isoformat(), 'sku': 'SYNTHETIC', 'quantity': '4' if day >= pd.Timestamp('2025-01-31') else '2', 'revenue': '80' if day >= pd.Timestamp('2025-01-31') else '40', 'currency': 'USD'})
    return pd.DataFrame(records)


def test_trends_require_comparable_evidence(database):
    add_sales(database, rich_frame())
    sales = load_sales(database)
    comparisons = compare_periods(sales, '2025-03-02')
    assert comparisons.change.iloc[0] == 1
    assert comparisons.recent_units.iloc[0] == 120
    # A single late order must not produce a growth claim.
    thin = sales.iloc[[0, -1]]
    assert pd.isna(compare_periods(thin, '2025-03-02').change.iloc[0])
    absent = compare_periods(sales, '2026-03-02')
    assert pd.isna(absent.recent_units.iloc[0])
    assert pd.isna(absent.change.iloc[0])


def test_scoring_unknown_is_not_zero():
    score = score_factors({'sales_signal': 80}, {'sales_signal': 50, 'production_fit': 50})
    assert score['priority'] == 80
    assert score['known_weight_percent'] == 50
    assert score['factors'][1]['value'] is None
    assert score['factors'][1]['contribution'] is None
    assert score_factors({})['priority'] is None
    with pytest.raises(ValueError):
        score_factors({'sales_signal': 101})


def test_opportunities_persist_and_regenerate_safely(database):
    add_sales(database, rich_frame())
    frame = load_sales(database)
    assert generate(database, frame, '2025-03-02') == 2
    opportunities = list_opportunities(database)
    assert set(opportunities.type) == {'variation_research', 'growth_review'}
    row = opportunities.iloc[0]
    evidence = json.loads(row.evidence_json)
    assert evidence['units'] == frame.quantity.sum()
    assert evidence['currency'] == 'USD'
    assert evidence['known_attributes'] == 'Chưa có'
    assert row.status == 'New'
    scored = json.loads(row.score_json)
    assert next(f for f in scored['factors'] if f['factor'] == 'production_fit')['value'] is None
    with pytest.raises(ValueError, match='lý do'):
        update_opportunity(database, int(row.id), concept='Changed', status='Rejected', notes='', reason='', next_action='Research')
    update_opportunity(database, int(row.id), concept='Custom concept', status='Researching', notes='Synthetic note', reason='Need evidence', next_action='Interview', target_date='2025-03-10')
    assert generate(database, frame, '2025-03-02') == 0
    updated = list_opportunities(database).set_index('id').loc[row.id]
    assert updated.concept == 'Custom concept'
    brief = concept_template(updated)
    save_brief(database, int(row.id), brief)
    with connect(database) as db:
        assert db.execute('SELECT COUNT(*) FROM concepts').fetchone()[0] == 1
        assert db.execute('SELECT previous_status FROM decisions').fetchone()[0] == 'New'
        assert 'before' in json.loads(db.execute('SELECT details_json FROM decisions').fetchone()[0])
    assert 'Chưa rõ' in brief['Giả thuyết khách hàng']


def test_insufficient_and_empty_data(database, sale_frame):
    assert generate(database, load_sales(database)) == 0
    add_sales(database, sale_frame)
    assert generate(database, load_sales(database), '2025-01-02') == 1
    assert list_opportunities(database).type.iloc[0] == 'insufficient_evidence'


def test_exports_are_readable_and_escape_formulas():
    from io import BytesIO
    frame = pd.DataFrame({'Concept': ['=HYPERLINK("bad")', 'Normal'], 'units': [1, 2]})
    csv = export_csv(frame).decode('utf-8-sig')
    assert "'=HYPERLINK" in csv
    excel = pd.read_excel(BytesIO(export_excel(frame)))
    assert excel.units.tolist() == [1, 2]
    assert excel.Concept.iloc[0].startswith("'=")


def test_seasonal_signal_needs_two_complete_years_with_matching_peak(database):
    from intelligence.opportunities import seasonal_signal
    records = []
    for day in pd.date_range('2023-01-01', '2024-12-31'):
        records.append({'date': day.date().isoformat(), 'sku': 'SYNTH-SEASON',
                        'quantity': '10' if day.month == 12 else '1',
                        'revenue': '100' if day.month == 12 else '10', 'currency': 'USD'})
    add_sales(database, pd.DataFrame(records))
    sales = load_sales(database)
    assert seasonal_signal(sales, pd.Timestamp('2025-01-01')) == [12, 2023, 2024]
    assert seasonal_signal(sales[sales.date.dt.year == 2024], pd.Timestamp('2025-01-01')) is None
    assert seasonal_signal(sales[sales.date.dt.month != 6], pd.Timestamp('2025-01-01')) is None
    generate(database, sales, '2025-01-01')
    assert 'seasonal_review' in list_opportunities(database).type.tolist()


def test_marketplace_review_requires_explicit_canonical_link(database):
    add_sales(database, rich_frame())
    mapping_id = int(catalog(database).id.iloc[0])
    link_product(database, mapping_id, name='Synthetic physical product')
    generate(database, load_sales(database), '2025-03-02')
    assert 'marketplace_review' in list_opportunities(database).type.tolist()


def test_dated_cost_does_not_override_explicit_source_cost(database, sale_frame):
    sale_frame['cost'] = '7'
    add_sales(database, sale_frame)
    mapping_id = int(catalog(database).id.iloc[0])
    set_cost(database, mapping_id, '2024-01-01', 'USD', '99')
    assert load_sales(database).effective_cost.iloc[0] == 7


def test_launched_result_and_decision_snapshot(database, sale_frame):
    add_sales(database, sale_frame)
    generate(database, load_sales(database), '2025-01-02')
    opportunity = list_opportunities(database).iloc[0]
    update_opportunity(database, int(opportunity.id), concept=opportunity.concept, status='Launched', notes='Synthetic launch', reason='Small test only', next_action='Review after 30 days', actual_results='Synthetic result: 2 units, 40 USD, 2025-01')
    row = list_opportunities(database).iloc[0]
    assert row.status == 'Launched'
    assert '40 USD' in row.actual_results
    with connect(database) as db:
        assert '40 USD' in db.execute('SELECT details_json FROM decisions').fetchone()[0]
