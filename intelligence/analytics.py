"""Currency-isolated analytics. Unknown expenses never become zero."""
from datetime import date
import pandas as pd
from .db import connect
from .config import TREND_WINDOW_DAYS, MIN_UNITS, MIN_ACTIVE_DAYS


def load_sales(path):
    with connect(path) as db:
        frame = pd.read_sql_query('''SELECT s.*,m.marketplace,m.sku,m.title,m.product_id,
        COALESCE(p.name,m.title) AS product_name,COALESCE(NULLIF(p.category,''),m.category) AS category,
        p.attributes,p.production_method,
        (SELECT c.unit_cost FROM costs c WHERE c.mapping_id=s.mapping_id AND c.currency=s.currency
         AND c.effective_date<=s.date ORDER BY c.effective_date DESC LIMIT 1) AS dated_unit_cost
        FROM sales s JOIN sku_mappings m ON s.mapping_id=m.id LEFT JOIN products p ON p.id=m.product_id''', db)
    if frame.empty:
        return frame
    frame['date'] = pd.to_datetime(frame['date'])
    frame['effective_cost'] = frame['cost'].where(frame['cost'].notna(), frame['dated_unit_cost'] * frame['quantity'])
    required = ['discounts', 'refunds', 'fees', 'shipping', 'effective_cost']
    complete = frame[required].notna().all(axis=1)
    frame['profit'] = (frame['revenue'] - frame[required].sum(axis=1)).where(complete)
    frame['complete_financials'] = complete
    return frame


def filter_sales(frame, start=None, end=None, marketplaces=None, mappings=None, categories=None, currency=None):
    if frame.empty:
        return frame.copy()
    result = frame.copy()
    if start is not None:
        result = result[result.date >= pd.Timestamp(start)]
    if end is not None:
        result = result[result.date <= pd.Timestamp(end)]
    for values, column in [(marketplaces, 'marketplace'), (mappings, 'mapping_id'), (categories, 'category')]:
        if values is not None:
            result = result[result[column].isin(values)]
    if currency:
        result = result[result.currency == currency]
    return result


def metrics(frame):
    """Return one row per currency, including explicit financial coverage."""
    results = []
    for currency, group in frame.groupby('currency'):
        revenue = group.revenue.sum()
        units = group.quantity.sum()
        covered = int(group.complete_financials.sum())
        profit = float(group.profit.sum()) if covered == len(group) else None
        results.append({'currency': currency, 'units': units, 'reported_revenue': revenue,
                        'active_skus': group.mapping_id.nunique(),
                        'average_selling_price': revenue / units if units else None,
                        'profit': profit, 'margin_percent': 100 * profit / revenue if profit is not None and revenue else None,
                        'rows': len(group), 'complete_financial_rows': covered})
    return pd.DataFrame(results)


def performance(frame):
    if frame.empty:
        return pd.DataFrame()
    return frame.groupby(['mapping_id', 'marketplace', 'sku', 'currency'], dropna=False).agg(
        units=('quantity', 'sum'), reported_revenue=('revenue', 'sum'),
        active_days=('date', 'nunique'), first_sale=('date', 'min'), last_sale=('date', 'max'),
        rows=('id', 'count'), financial_coverage=('complete_financials', 'mean')).reset_index()


def trends(frame):
    if frame.empty:
        return pd.DataFrame()
    return frame.assign(month=frame.date.dt.to_period('M').astype(str)).groupby(['month', 'currency'], as_index=False).agg(units=('quantity', 'sum'), reported_revenue=('revenue', 'sum'))


def compare_periods(frame, as_of=None):
    """Two completed 30-day windows, excluding as_of day. Missing != zero."""
    if frame.empty:
        return pd.DataFrame()
    end = pd.Timestamp(as_of or date.today()).normalize()
    current_start = end - pd.Timedelta(days=TREND_WINDOW_DAYS)
    previous_start = current_start - pd.Timedelta(days=TREND_WINDOW_DAYS)
    rows = []
    for (mapping_id, currency), group in frame.groupby(['mapping_id', 'currency']):
        previous = group[(group.date >= previous_start) & (group.date < current_start)]
        current = group[(group.date >= current_start) & (group.date < end)]
        adequate = (not previous.empty and not current.empty and group.date.min() <= previous_start
                    and previous.quantity.sum() >= MIN_UNITS and current.quantity.sum() >= MIN_UNITS
                    and previous.date.nunique() >= MIN_ACTIVE_DAYS and current.date.nunique() >= MIN_ACTIVE_DAYS)
        change = float(current.quantity.sum() / previous.quantity.sum() - 1) if adequate else None
        rows.append({'mapping_id': mapping_id, 'currency': currency,
                     'previous_units': float(previous.quantity.sum()) if not previous.empty else None,
                     'recent_units': float(current.quantity.sum()) if not current.empty else None,
                     'change': change, 'sufficient_evidence': adequate,
                     'period_start': previous_start.date().isoformat(), 'period_end_exclusive': end.date().isoformat(),
                     'last_observed_sale': group.date.max().date().isoformat(),
                     'limitation': 'Quan sát nội bộ; ngày không có dòng là chưa rõ, không chứng minh doanh số bằng 0. Cần xác nhận độ phủ báo cáo.'})
    return pd.DataFrame(rows)


def concentration(frame):
    table = performance(frame)
    if table.empty:
        return pd.DataFrame()
    return pd.DataFrame([{'currency': c, 'top_5_share_percent': 100 * g.nlargest(5, 'reported_revenue').reported_revenue.sum() / g.reported_revenue.sum() if g.reported_revenue.sum() else None} for c, g in table.groupby('currency')])
