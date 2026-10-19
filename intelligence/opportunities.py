"""Deterministic evidence-first rules; no external market demand claims."""
import json
import calendar
import math
from datetime import date
import pandas as pd
from .config import WEIGHTS, MIN_UNITS, MIN_ACTIVE_DAYS, GROWTH_THRESHOLD, DECLINE_THRESHOLD, STATUSES, SIGNAL_FULL_UNITS, CONSISTENCY_FULL_DAYS, CONFIDENCE_FULL_DAYS, SEASONAL_PEAK_RATIO, SEASONAL_MIN_DAYS_PER_MONTH
from .db import connect
from .analytics import performance, compare_periods
from .imports import encode


def score_factors(factors, weights=None):
    weights = WEIGHTS if weights is None else weights
    if any(v < 0 for v in weights.values()) or sum(weights.values()) <= 0:
        raise ValueError('Weights must be nonnegative with a positive total.')
    known_weight = sum(weight for key, weight in weights.items() if factors.get(key) is not None)
    parts = []
    for key, weight in weights.items():
        value = factors.get(key)
        if value is not None and (not math.isfinite(value) or not 0 <= value <= 100):
            raise ValueError('Factor values must be 0–100 or unknown.')
        parts.append({'factor': key, 'weight': weight, 'value': value,
                      'contribution': value * weight / known_weight if value is not None and known_weight else None,
                      'reason': REASONS.get(key, 'Configured factor')})
    score = sum(p['contribution'] for p in parts if p['contribution'] is not None) if known_weight else None
    return {'priority': round(score, 1) if score is not None else None,
            'known_weight_percent': round(100 * known_weight / sum(weights.values()), 1), 'factors': parts}


REASONS = {
 'sales_signal': 'Observed units relative to configured unit threshold; internal sales only.',
 'consistency': 'Active sale days relative to configured consistency threshold; missing dates are unknown.',
 'differentiation': 'Unknown until external research demonstrates a differentiated variation.',
 'production_fit': 'Unknown until feasibility and capacity are reviewed; method metadata alone is insufficient.',
 'cost_coverage': 'Percentage of observed sales rows with known product cost (not complete profit).',
 'evidence': 'Observed sale-day coverage relative to configured confidence threshold; does not prove market demand.',
 'risk_readiness': 'Data readiness: 20 base + 20 each for sufficient observations, some known costs, canonical mapping, known attributes. This is not a market or competitor risk estimate.',
}


def seasonal_signal(group, as_of):
    """Require two completed years with observations in all twelve months."""
    observed = group.assign(year=group.date.dt.year, month=group.date.dt.month)
    candidates = []
    for year, rows in observed.groupby('year'):
        if year >= as_of.year:
            continue
        by_month = rows.groupby('month').agg(units=('quantity', 'sum'), days=('date', 'nunique'))
        if len(by_month) != 12 or (by_month.days < SEASONAL_MIN_DAYS_PER_MONTH).any():
            continue
        # Compare daily rates so month length alone cannot create a peak.
        rates = pd.Series({int(m): r.units / calendar.monthrange(int(year), int(m))[1] for m, r in by_month.iterrows()})
        if rates.max() >= rates.median() * SEASONAL_PEAK_RATIO:
            candidates.append((int(year), int(rates.idxmax())))
    if len(candidates) >= 2 and candidates[-1][0] - candidates[-2][0] == 1 and candidates[-1][1] == candidates[-2][1]:
        return [candidates[-1][1], candidates[-2][0], candidates[-1][0]]
    return None


def generate(path, frame, as_of=None):
    if frame.empty:
        return 0
    as_of = pd.Timestamp(as_of or date.today()).normalize()
    frame = frame[frame.date < as_of]
    if frame.empty:
        return 0
    table = performance(frame)
    comparisons = compare_periods(frame, as_of)
    added = 0
    with connect(path) as db:
        for _, product in table.iterrows():
            group = frame[(frame.mapping_id == product.mapping_id) & (frame.currency == product.currency)]
            info = group.iloc[0]
            comparison = comparisons[(comparisons.mapping_id == product.mapping_id) & (comparisons.currency == product.currency)].iloc[0]
            types = []
            strong = product.units >= MIN_UNITS and product.active_days >= MIN_ACTIVE_DAYS
            if strong:
                types.append(('variation_research', 'Nghiên cứu biến thể cho SKU có nhiều ngày bán được ghi nhận.'))
            else:
                types.append(('insufficient_evidence', 'Thu thập thêm bằng chứng trước khi phát triển biến thể.'))
            if pd.notna(comparison.change):
                if comparison.change >= GROWTH_THRESHOLD:
                    types.append(('growth_review', 'Kiểm tra tăng trưởng quan sát được trước khi thử biến thể.'))
                elif comparison.change <= DECLINE_THRESHOLD:
                    types.append(('decline_investigation', 'Điều tra suy giảm: tồn kho, độ phủ báo cáo, listing và giá.'))
            if pd.notna(info.product_id):
                markets = db.execute('SELECT DISTINCT marketplace FROM sku_mappings WHERE product_id=?', (int(info.product_id),)).fetchall()
                if len(markets) == 1 and strong:
                    types.append(('marketplace_review', 'Rà soát mapping và tính phù hợp của marketplace khác; chưa có bằng chứng nhu cầu tại đó.'))
            seasonal = seasonal_signal(group, as_of)
            if seasonal:
                types.append(('seasonal_review', f'Nghiên cứu tín hiệu mùa vụ quan sát tháng {seasonal[0]}; cần kiểm tra độ phủ, tồn kho và khuyến mãi.'))
            factors = {'sales_signal': min(100, float(product.units) / SIGNAL_FULL_UNITS * 100),
                       'consistency': min(100, float(product.active_days) / CONSISTENCY_FULL_DAYS * 100),
                       'differentiation': None, 'production_fit': None,
                       'cost_coverage': float(group.effective_cost.notna().mean() * 100) if group.effective_cost.notna().any() else None,
                       'evidence': min(100, float(product.active_days) / CONFIDENCE_FULL_DAYS * 100),
                       'risk_readiness': float(20 + 20 * strong + 20 * group.effective_cost.notna().any() + 20 * pd.notna(info.product_id) + 20 * bool(pd.notna(info.attributes) and info.attributes))}
            scored = score_factors(factors)
            evidence = {'marketplace': info.marketplace, 'sku': info.sku, 'currency': info.currency,
                        'units': float(product.units), 'reported_revenue': float(product.reported_revenue),
                        'active_days': int(product.active_days), 'start': product.first_sale.date().isoformat(),
                        'end': product.last_sale.date().isoformat(),
                        'period_comparison': {k: (None if pd.isna(v) else (v.item() if hasattr(v, 'item') else v)) for k, v in comparison.to_dict().items()},
                        'known_attributes': str(info.attributes) if pd.notna(info.attributes) and info.attributes else 'Chưa có',
                        'production_method': str(info.production_method) if pd.notna(info.production_method) and info.production_method else 'Chưa rõ',
                        'seasonal_signal': seasonal,
                        'commercial_attractiveness': 'Chưa rõ: cần nghiên cứu thị trường, khác biệt và kinh tế đơn vị.'}
            for kind, concept in types:
                key = f'{int(product.mapping_id)}:{product.currency}:{kind}:{as_of.date()}'
                # Deliberately immutable evidence snapshot; do not overwrite user decisions on regeneration.
                result = db.execute('''INSERT INTO opportunities(opportunity_key,mapping_id,type,concept,evidence_json,assumptions,next_action,upside,risk,confidence,score,score_json)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(opportunity_key) DO NOTHING''',
                    (key, int(product.mapping_id), kind, concept, encode(evidence),
                     'Chưa biết độ phủ báo cáo, màu/chất liệu/occasion nếu chưa khai báo; chưa có dữ liệu đối thủ, sở thích khách hàng hay nhu cầu toàn thị trường. Không suy ra cạnh tranh thấp. Chi phí thiếu không phải 0.',
                     'Xác nhận dữ liệu đầy đủ; bổ sung attributes, nghiên cứu khác biệt và khách hàng, kiểm tra công suất/chi phí trước khi thử mẫu.',
                     'Có thể đáng thử nhỏ sau nghiên cứu; chưa ước lượng doanh số tăng thêm.',
                     'High' if not strong else 'Medium', factors['evidence'], scored['priority'], encode(scored)))
                added += result.rowcount
    return added


def list_opportunities(path):
    with connect(path) as db:
        return pd.read_sql_query('''SELECT o.*,m.marketplace,m.sku,p.name AS product_name
        FROM opportunities o JOIN sku_mappings m ON m.id=o.mapping_id
        LEFT JOIN products p ON p.id=m.product_id ORDER BY o.score DESC,o.id''', db)


def update_opportunity(path, opportunity_id, *, concept, status, notes, reason, next_action, target_date=None, actual_results=''):
    if status not in STATUSES or not concept.strip():
        raise ValueError('Trạng thái không hợp lệ hoặc concept trống.')
    if status in ('Rejected', 'Approved for Launch') and not reason.strip():
        raise ValueError('Cần lý do phê duyệt / từ chối.')
    if target_date:
        target_date = pd.Timestamp(target_date).date().isoformat()
    details = dict(concept=concept, notes=notes, next_action=next_action, target_date=target_date, actual_results=actual_results)
    with connect(path) as db:
        old = db.execute('SELECT * FROM opportunities WHERE id=?', (opportunity_id,)).fetchone()
        if old is None:
            raise ValueError('Cơ hội không tồn tại.')
        db.execute('UPDATE opportunities SET concept=?,status=?,notes=?,next_action=?,target_date=?,actual_results=? WHERE id=?', (concept, status, notes, next_action, target_date, actual_results, opportunity_id))
        db.execute('INSERT INTO decisions(opportunity_id,previous_status,new_status,reason,details_json) VALUES(?,?,?,?,?)', (opportunity_id, old['status'], status, reason, encode({'before': {k: old[k] for k in details}, 'after': details})))


BRIEF_FIELDS = ['Tên sản phẩm dự kiến', 'Giả thuyết khách hàng', 'Vấn đề / mục đích sử dụng', 'Concept', 'Hướng thiết kế', 'Tùy chọn cá nhân hóa', 'Occasion / use case', 'Giả thuyết giá & currency', 'Phương pháp sản xuất', 'Chi phí ước tính & currency', 'Rủi ro / giới hạn', 'Bằng chứng', 'Câu hỏi nghiên cứu ngoài', 'Thử nghiệm chi phí thấp']


def concept_template(opportunity):
    evidence = json.loads(opportunity['evidence_json'])
    values = [f"Concept – {evidence['sku']}", 'Chưa rõ — cần phỏng vấn/nghiên cứu', 'Chưa rõ — không suy từ sales',
              opportunity['concept'], 'Nghiên cứu biến thể dựa trên attributes đã xác nhận: ' + evidence['known_attributes'],
              'Chưa rõ — xác nhận nhu cầu và năng lực', 'Chưa rõ — cần nghiên cứu', 'Chưa xác định',
              evidence['production_method'], 'Chưa xác định', opportunity['assumptions'],
              json.dumps(evidence, ensure_ascii=False), 'Ai cần sản phẩm? Khác biệt gì? Chi phí và cạnh tranh? Quyền sử dụng thiết kế?',
              'Làm một mockup/mẫu nhỏ; đặt trước tiêu chí, ngân sách và thời hạn; thu phản hồi trước khi sản xuất lớn.']
    return dict(zip(BRIEF_FIELDS, values))


def save_brief(path, opportunity_id, brief):
    if set(brief) != set(BRIEF_FIELDS):
        raise ValueError('Thiếu trường concept brief.')
    with connect(path) as db:
        db.execute('INSERT INTO concepts(opportunity_id,brief_json) VALUES(?,?) ON CONFLICT(opportunity_id) DO UPDATE SET brief_json=excluded.brief_json,updated_at=CURRENT_TIMESTAMP', (opportunity_id, encode(brief)))
