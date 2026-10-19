"""Vietnamese, local-first R&D workspace. Run: streamlit run app.py."""
from datetime import date
import json
import sqlite3
import pandas as pd
import streamlit as st
from intelligence.config import DB_PATH, MARKETPLACES, STATUSES, WEIGHTS
from intelligence.db import initialize, connect
from intelligence.imports import (FIELDS, auto_mapping, parse_file, excel_sheets, validate,
                                  preview_import, counts, import_rows, row_report)
from intelligence.catalog import catalog, link_product, update_product, set_cost
from intelligence.analytics import load_sales, filter_sales, metrics, performance, trends, compare_periods, concentration
from intelligence.opportunities import (generate, list_opportunities, update_opportunity,
                                       concept_template, save_brief, BRIEF_FIELDS)
from intelligence.exports import export_csv, export_excel


def downloads(frame, label, key):
    if frame.empty:
        return
    left, right = st.columns(2)
    left.download_button(f'{label} · CSV', export_csv(frame), file_name=f'{key}.csv', mime='text/csv', key=f'{key}_csv')
    right.download_button(f'{label} · Excel', export_excel(frame), file_name=f'{key}.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', key=f'{key}_xlsx')


def empty():
    st.info('Chưa có dữ liệu. Vào Import dữ liệu để tải CSV hoặc Excel và xác nhận các dòng hợp lệ. Không có số liệu demo.')


def import_page():
    st.header('Import dữ liệu')
    st.write('CSV UTF-8 hoặc .xlsx, tối đa 20 MB / 100.000 dòng mỗi tệp. Hàng đầu tiên là tên cột. Không tải thông tin cá nhân khách hàng.')
    st.warning('Revenue phải là gross sales trước các khoản trừ, cho cả dòng; cost và shipping là tổng chi phí của dòng (không phải đơn giá). Báo cáo net revenue, nhiều tiền tệ trong một dòng, refund-only hoặc tổng theo tháng chưa được hỗ trợ. Hãy chuẩn hóa trước khi import.')
    uploads = st.file_uploader('Chọn một hoặc nhiều tệp', type=['csv', 'xlsx'], accept_multiple_files=True)
    if not uploads:
        st.caption('Daily summary: một dòng cho mỗi ngày/SKU/currency. Order lines: cần order_id và line_id ổn định. Không trộn hai loại cho cùng marketplace.')
        return
    for index, upload in enumerate(uploads):
        prefix = f'upload_{index}_{upload.name}'
        with st.expander(f'Tệp {index+1}: {upload.name}', expanded=True):
            try:
                content = upload.getvalue()
                sheet = 0
                if upload.name.lower().endswith('.xlsx'):
                    sheet = st.selectbox('Trang Excel', excel_sheets(content), key=prefix+'sheet')
                frame = parse_file(content, upload.name, sheet)
                st.dataframe(frame.head(20), hide_index=True)
                marketplace = st.selectbox('Marketplace của tệp', MARKETPLACES, key=prefix+'market')
                mode = st.selectbox('Loại báo cáo', ['daily_summary', 'order_lines'], key=prefix+'mode', format_func=lambda v: {'daily_summary': 'Tổng hợp ngày / SKU / currency', 'order_lines': 'Dòng đơn hàng (cần order_id + line_id)'}[v])
                date_format = st.selectbox('Định dạng ngày', ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y-%m-%d %H:%M:%S'], key=prefix+'format')
                default_currency = st.text_input('Currency mặc định nếu cột thiếu / trống (do bạn xác nhận, ví dụ USD)', key=prefix+'currency').strip().upper()
                suggested = auto_mapping(frame.columns)
                mapping = {}
                with st.expander('Map cột nguồn → trường chuẩn', expanded=True):
                    st.caption('Không tự suy đoán currency. Không map cùng cột vào hai trường. Chi phí trống là chưa biết; nhập 0 chỉ khi đã xác nhận không có chi phí đó.')
                    for field in FIELDS:
                        options = ['—'] + list(frame.columns)
                        choice = st.selectbox(field, options, index=options.index(suggested[field]) if field in suggested else 0, key=prefix+field)
                        if choice != '—':
                            mapping[field] = choice
                rows = validate(frame, mapping, marketplace, mode, upload.name, default_currency, date_format)
                classified = preview_import(DB_PATH, rows, marketplace, mode)
                count = counts(classified)
                st.write(f"Tổng: {count['total']} · Hợp lệ: {count['accepted']} · Từ chối: {count['rejected']} · Trùng: {count['duplicated']}")
                report = row_report(classified)
                st.dataframe(report.head(100), hide_index=True)
                downloads(report[report.status != 'accepted'], 'Dòng từ chối / trùng và lý do', prefix+'errors')
                st.caption('Xem trước tối đa 100 dòng; tệp export chứa toàn bộ dòng từ chối/trùng. Chỉ giá trị của các cột đã map được lưu. Dòng nguồn bắt đầu từ 2, theo thứ tự bản ghi (CSV có nhiều dòng trong ô vẫn là một bản ghi).')
                confirmed = st.checkbox('Tôi xác nhận loại báo cáo, mapping và gross sales; đồng ý chỉ import dòng hợp lệ. Các dòng từ chối / trùng sẽ có nhật ký.', key=prefix+'confirm')
                if st.button('Xác nhận import', key=prefix+'save', disabled=not confirmed):
                    audit_mapping = {'columns': mapping, 'default_currency': default_currency, 'date_format': date_format, 'sheet': sheet}
                    with st.spinner('Đang lưu trong transaction…'):
                        import_id, saved = import_rows(DB_PATH, rows, marketplace, mode, upload.name, content, audit_mapping)
                    st.success(f"Import #{import_id}: đã lưu {saved['accepted']}, từ chối {saved['rejected']}, trùng {saved['duplicated']}. Xem Lịch sử import để đối soát.")
            except (ValueError, sqlite3.Error) as exc:
                st.error(str(exc) if isinstance(exc, ValueError) else 'Không ghi/đọc được dữ liệu. Import chưa hoàn tất đã được rollback; kiểm tra quyền và dung lượng ổ đĩa.')


def product_page():
    st.header('Sản phẩm & SKU')
    frame = catalog(DB_PATH)
    if frame.empty:
        empty()
        return
    query = st.text_input('Tìm SKU / tiêu đề / sản phẩm chuẩn')
    markets = st.multiselect('Marketplace', MARKETPLACES, default=MARKETPLACES, key='catalog_markets')
    only_unmapped = st.checkbox('Chỉ SKU chưa liên kết sản phẩm chuẩn')
    shown = frame[frame.marketplace.isin(markets)]
    if query:
        shown = shown[shown[['sku', 'title', 'canonical_name']].fillna('').apply(lambda col: col.str.contains(query, case=False, regex=False)).any(axis=1)]
    if only_unmapped:
        shown = shown[shown.product_id.isna()]
    st.dataframe(shown, hide_index=True)
    downloads(shown, 'Catalog đang lọc', 'catalog')
    downloads(shown[shown.product_id.isna()], 'SKU chưa mapping', 'unmapped')
    if shown.empty:
        return
    selected = st.selectbox('SKU cần cập nhật', shown.id.tolist(), format_func=lambda i: f"{frame.loc[frame.id == i, 'marketplace'].iloc[0]} / {frame.loc[frame.id == i, 'sku'].iloc[0]}")
    st.caption('SKU marketplace được giữ nguyên. Chỉ liên kết khi bạn đã xác nhận cùng sản phẩm vật lý; hệ thống không tự gộp.')
    with connect(DB_PATH) as db:
        products = pd.read_sql_query('SELECT * FROM products', db)
    with st.form('link_sku'):
        target = st.selectbox('Liên kết sản phẩm chuẩn', [None] + products.id.tolist(), format_func=lambda i: 'Tạo sản phẩm chuẩn mới' if i is None else f"#{i} · {products.loc[products.id == i, 'name'].iloc[0]}")
        name = st.text_input('Tên sản phẩm mới (nếu tạo mới)')
        category = st.text_input('Category mới')
        attributes = st.text_area('Attributes đã biết (màu, chất liệu, design… không suy đoán)')
        method = st.text_input('Phương pháp sản xuất đã biết')
        if st.form_submit_button('Lưu liên kết SKU'):
            link_product(DB_PATH, selected, target, name, category, attributes, method)
            st.success('Đã lưu liên kết. Thay đổi áp dụng vào lần xem tiếp theo.')
    linked = frame.loc[frame.id == selected, 'product_id'].iloc[0]
    if pd.notna(linked) and not products.empty:
        product = products[products.id == int(linked)].iloc[0]
        with st.form(f'metadata_{int(linked)}'):
            st.write('Metadata dùng chung cho mọi SKU đã liên kết')
            name = st.text_input('Tên chuẩn', product['name'])
            category = st.text_input('Category', product.category)
            attributes = st.text_area('Attributes', product.attributes)
            method = st.text_input('Production method', product.production_method)
            if st.form_submit_button('Lưu metadata'):
                update_product(DB_PATH, int(linked), name, category, attributes, method)
                st.success('Đã lưu.')
    with st.form('dated_cost'):
        st.write('Chi phí đơn vị theo SKU và ngày hiệu lực; không sửa sales gốc')
        effective = st.date_input('Hiệu lực từ', value=date.today())
        currency = st.text_input('Currency chi phí', 'USD')
        cost = st.text_input('Unit cost (để trống nếu chưa biết)')
        if st.form_submit_button('Lưu cost đã xác nhận'):
            set_cost(DB_PATH, selected, effective, currency, cost)
            st.success('Đã lưu. Cùng SKU/ngày/currency sẽ cập nhật bản ghi cost hiện có.')
    with connect(DB_PATH) as db:
        st.dataframe(pd.read_sql_query('SELECT effective_date,currency,unit_cost FROM costs WHERE mapping_id=? ORDER BY effective_date', db, params=[selected]), hide_index=True)


def dashboard(overview=False):
    st.header('Tổng quan' if overview else 'Phân tích bán hàng')
    frame = load_sales(DB_PATH)
    if frame.empty:
        empty()
        return
    st.warning('Sales nội bộ không chứng minh tổng nhu cầu thị trường. Ngày không có bản ghi là chưa rõ, không phải doanh số 0. Báo cáo chưa được xác nhận đầy đủ; xu hướng chỉ là tín hiệu để kiểm tra.')
    selected_range = st.date_input('Khoảng ngày', value=(frame.date.min().date(), frame.date.max().date()))
    if len(selected_range) != 2:
        st.info('Chọn đủ ngày bắt đầu và kết thúc.')
        return
    start, end = selected_range
    markets = st.multiselect('Marketplace', sorted(frame.marketplace.unique()), default=sorted(frame.marketplace.unique()))
    categories = st.multiselect('Category', sorted(frame.category.unique()), default=sorted(frame.category.unique()))
    ids = sorted(frame.mapping_id.unique().tolist())
    mappings = st.multiselect('Sản phẩm / SKU', ids, default=ids, format_func=lambda i: f"{frame.loc[frame.mapping_id == i, 'marketplace'].iloc[0]} / {frame.loc[frame.mapping_id == i, 'sku'].iloc[0]}")
    currency = st.selectbox('Currency (không quy đổi)', sorted(frame.currency.unique()))
    filtered = filter_sales(frame, start, end, markets, mappings, categories, currency)
    if filtered.empty:
        st.info('Không có bản ghi khớp bộ lọc; không kết luận doanh số bằng 0.')
        return
    summary = metrics(filtered)
    st.subheader('Chỉ số theo currency')
    st.dataframe(summary, hide_index=True)
    st.caption('reported_revenue = tổng gross sales đã báo cáo; ASP = gross sales / units. Active SKU = SKU có bản ghi bán. Profit chỉ có khi mọi dòng có đủ discounts, refunds, fees, shipping và product cost. Không bao gồm overhead, thuế và quảng cáo ngoài export.')
    perf = performance(filtered)
    st.subheader('Top SKU theo reported revenue')
    st.dataframe(perf.sort_values('reported_revenue', ascending=False).head(20), hide_index=True)
    st.subheader('Top SKU theo units')
    st.dataframe(perf.sort_values('units', ascending=False).head(20), hide_index=True)
    series = trends(filtered)
    st.subheader('Xu hướng tháng (tháng đầu/cuối có thể chưa đủ)')
    st.line_chart(series.set_index('month')[['reported_revenue']])
    st.subheader('Theo marketplace')
    st.dataframe(filtered.groupby(['marketplace', 'currency'], as_index=False).agg(units=('quantity', 'sum'), reported_revenue=('revenue', 'sum')), hide_index=True)
    st.subheader('Tập trung doanh số')
    st.dataframe(concentration(filtered), hide_index=True)
    st.subheader('So sánh hai cửa sổ 30 ngày đã kết thúc')
    cutoff = min(pd.Timestamp(end) + pd.Timedelta(days=1), pd.Timestamp(date.today()))
    compared = compare_periods(filtered, cutoff)
    st.dataframe(compared, hide_index=True)
    st.subheader('Ít hoặc chưa có bản ghi gần đây — cần kiểm tra độ phủ')
    st.dataframe(compared[compared.recent_units.isna() | (compared.recent_units < 10)], hide_index=True)
    st.caption('Loại ngày hôm nay; mỗi cửa sổ cần ≥10 units, ≥5 ngày có sales và dữ liệu bắt đầu trước cửa sổ đầu để tính change. Không có dữ liệu gần đây ≠ không có sales. change là tỷ lệ units, chưa loại ảnh hưởng hết hàng / khuyến mãi / thiếu export.')
    st.subheader('Cần kiểm tra dữ liệu')
    questionable = filtered[filtered.effective_cost.isna() | ~filtered.complete_financials | filtered.product_id.isna()]
    st.dataframe(questionable[['marketplace', 'sku', 'date', 'currency', 'effective_cost', 'complete_financials', 'product_id']].head(100), hide_index=True)
    downloads(perf, 'Product performance', 'performance')
    downloads(series, 'Sales trends', 'trends')
    downloads(compared, 'Period comparison', 'comparison')


def opportunity_page():
    st.header('Cơ hội R&D')
    st.write('Quy tắc minh bạch từ dữ liệu đã import; mọi cơ hội bắt đầu ở New và chưa được xác thực thị trường.')
    if st.button('Tạo cơ hội từ dữ liệu hiện có'):
        with st.spinner('Đang kiểm tra tín hiệu…'):
            added = generate(DB_PATH, load_sales(DB_PATH))
        st.success(f'Tạo {added} cơ hội mới. Cùng SKU/currency/loại/ngày không tạo lại; snapshot cũ và quyết định được giữ nguyên.')
    frame = list_opportunities(DB_PATH)
    if frame.empty:
        st.info('Import dữ liệu rồi bấm Tạo cơ hội. Nếu chỉ có dữ liệu hôm nay, chờ ngày hoàn tất trước khi tạo.')
        return
    statuses = st.multiselect('Trạng thái', STATUSES, default=STATUSES)
    types = st.multiselect('Loại cơ hội', sorted(frame.type.unique()), default=sorted(frame.type.unique()))
    markets = st.multiselect('Marketplace cơ hội', MARKETPLACES, default=MARKETPLACES)
    shown = frame[frame.status.isin(statuses) & frame.type.isin(types) & frame.marketplace.isin(markets)]
    sort = st.selectbox('Sắp xếp', ['score', 'confidence', 'created_at'])
    shown = shown.sort_values(sort, ascending=False)
    st.dataframe(shown[['id', 'created_at', 'marketplace', 'sku', 'type', 'concept', 'score', 'confidence', 'risk', 'status']], hide_index=True)
    downloads(shown, 'Opportunities / pipeline', 'opportunities')
    scores = pd.DataFrame([{'opportunity_id': r.id, 'score': r.score, **factor} for _, r in shown.iterrows() for factor in json.loads(r.score_json)['factors']])
    downloads(scores, 'Score explanations', 'scores')
    if shown.empty:
        return
    selected = st.selectbox('Mở cơ hội', shown.id.tolist())
    row = shown[shown.id == selected].iloc[0]
    st.subheader(f"#{selected}: {row['type']}")
    st.json(json.loads(row.evidence_json))
    st.write('Giả định / unknowns:', row.assumptions)
    st.write('Potential upside:', row.upside)
    scored = json.loads(row.score_json)
    st.dataframe(pd.DataFrame(scored['factors']), hide_index=True)
    st.caption(f"Priority = trung bình trọng số của yếu tố đã biết; trọng số có dữ liệu: {scored['known_weight_percent']}%. Confidence {row.confidence:.1f}/100 là độ dày bằng chứng quan sát, không phải xác suất thành công. Commercial attractiveness, differentiated demand và production fit chưa rõ. Score cao không bảo đảm sales.")
    with st.form(f'edit_opportunity_{selected}'):
        concept = st.text_area('Concept đề xuất', row.concept)
        status = st.selectbox('Status', STATUSES, index=STATUSES.index(row.status))
        notes = st.text_area('Ghi chú', row.notes)
        reason = st.text_area('Lý do quyết định (bắt buộc khi Approved for Launch / Rejected)')
        action = st.text_area('Bước tiếp theo', row.next_action)
        use_target = st.checkbox('Có ngày mục tiêu', value=bool(row.target_date))
        target = st.date_input('Ngày mục tiêu', value=pd.Timestamp(row.target_date).date() if row.target_date else date.today())
        results = st.text_area('Kết quả thực tế sau launch (kỳ đo, units/revenue/currency, nguồn dữ liệu; nhập thủ công)', row.actual_results)
        if st.form_submit_button('Lưu quyết định và lịch sử'):
            update_opportunity(DB_PATH, selected, concept=concept, status=status, notes=notes, reason=reason, next_action=action, target_date=target if use_target else None, actual_results=results)
            st.success('Đã lưu. Lịch sử giữ cả nội dung trước và sau thay đổi.')
    with connect(DB_PATH) as db:
        history = pd.read_sql_query('SELECT changed_at,previous_status,new_status,reason,details_json FROM decisions WHERE opportunity_id=? ORDER BY id DESC', db, params=[selected])
    st.dataframe(history, hide_index=True)


def concept_page():
    st.header('Phát triển concept')
    frame = list_opportunities(DB_PATH)
    if frame.empty:
        st.info('Tạo một cơ hội trước khi phát triển concept.')
        return
    selected = st.selectbox('Cơ hội', frame.id.tolist(), format_func=lambda i: f"#{i} · {frame.loc[frame.id == i, 'sku'].iloc[0]}")
    opportunity = frame[frame.id == selected].iloc[0]
    with connect(DB_PATH) as db:
        saved = db.execute('SELECT brief_json FROM concepts WHERE opportunity_id=?', (selected,)).fetchone()
    brief = json.loads(saved['brief_json']) if saved else concept_template(opportunity)
    st.caption('Template quy tắc dựa trên snapshot evidence, không phải AI insight đã kiểm chứng. Mọi giả thuyết cần nghiên cứu hoặc thử nghiệm.')
    with st.form(f'brief_{selected}'):
        edited = {field: st.text_area(field, brief.get(field, ''), key=f'brief_{selected}_{field}') for field in BRIEF_FIELDS}
        if st.form_submit_button('Lưu concept brief'):
            save_brief(DB_PATH, selected, edited)
            st.success('Đã lưu brief.')
    downloads(pd.DataFrame([{'opportunity_id': selected, **edited}]), 'Concept brief hiện tại', 'brief')
    with connect(DB_PATH) as db:
        all_briefs = db.execute('SELECT opportunity_id,brief_json FROM concepts').fetchall()
    downloads(pd.DataFrame([{'opportunity_id': b['opportunity_id'], **json.loads(b['brief_json'])} for b in all_briefs]), 'Tất cả brief đã lưu', 'all_briefs')


def history_page():
    st.header('Lịch sử import')
    with connect(DB_PATH) as db:
        history = pd.read_sql_query('SELECT * FROM imports ORDER BY id DESC', db)
    st.dataframe(history, hide_index=True)
    downloads(history, 'Import history', 'imports')
    if history.empty:
        return
    selected = st.selectbox('Xem provenance của import', history.id.tolist())
    with connect(DB_PATH) as db:
        audit = pd.read_sql_query('SELECT source_row,status,error,sale_id,raw_json FROM source_rows WHERE import_id=? ORDER BY source_row', db, params=[selected])
    st.dataframe(audit.head(100), hide_index=True)
    downloads(audit, 'Source audit / import errors', 'audit')


def settings_page():
    st.header('Cài đặt')
    st.write('SQLite local mặc định: thư mục data, tệp intelligence.sqlite3. Có thể đặt RD_DATABASE_PATH trước khi khởi động. Không cần API key hay marketplace integration.')
    st.write('Đóng app trước khi copy file SQLite để backup, hoặc dùng nút backup snapshot nhất quán dưới đây. Backup chứa dữ liệu kinh doanh; lưu an toàn, không commit vào Git.')
    if st.button('Chuẩn bị backup SQLite'):
        with connect(DB_PATH) as db:
            backup = sqlite3.connect(':memory:')
            try:
                db.backup(backup)
                payload = backup.serialize()
            finally:
                backup.close()
        st.download_button('Tải backup', payload, file_name='intelligence-backup.sqlite3', mime='application/octet-stream')
    st.subheader('Scoring weights')
    st.json(WEIGHTS)
    st.caption('Ngưỡng và weights tập trung trong intelligence/config.py. Yếu tố chưa biết giữ None; điểm normalize theo weights đã biết. Thay đổi quy tắc chỉ áp dụng vào snapshot cơ hội tạo tiếp theo. Không tự cập nhật quyết định cũ.')
    st.warning('Local-first, một người dùng tin cậy. Không có đăng nhập hoặc phân quyền; không mở app công khai với dữ liệu kinh doanh. Chưa có quy trình xóa / phục hồi dữ liệu tự động.')


def main():
    st.set_page_config(page_title='R&D Intelligence', page_icon='🔬', layout='wide')
    st.title('R&D Intelligence MVP')
    st.markdown('Không gian R&D Home & Living / Decor: từ sales nội bộ đến giả thuyết sản phẩm có bằng chứng. Không cần API key; không gọi LLM hay thu thập dữ liệu đối thủ.')
    try:
        initialize(DB_PATH)
        page = st.sidebar.radio('Điều hướng', ['Tổng quan', 'Import dữ liệu', 'Sản phẩm & SKU', 'Phân tích bán hàng', 'Cơ hội R&D', 'Phát triển concept', 'Lịch sử import', 'Cài đặt'])
        pages = {'Tổng quan': lambda: dashboard(True), 'Import dữ liệu': import_page,
                 'Sản phẩm & SKU': product_page, 'Phân tích bán hàng': dashboard,
                 'Cơ hội R&D': opportunity_page, 'Phát triển concept': concept_page,
                 'Lịch sử import': history_page, 'Cài đặt': settings_page}
        pages[page]()
    except ValueError as exc:
        st.error(str(exc))
    except sqlite3.Error:
        st.error('Không truy cập được SQLite. Kiểm tra quyền, dung lượng hoặc backup; dữ liệu chưa commit đã được rollback.')


if __name__ == '__main__':
    main()
