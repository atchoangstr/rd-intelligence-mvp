# R&D Intelligence MVP — Home & Living / Decor

Ứng dụng local-first bằng Python, Streamlit, Pandas và SQLite, dành cho chủ doanh nghiệp rà soát sales nội bộ và quản lý giả thuyết R&D. Giao diện tiếng Việt; hỗ trợ Amazon US, Etsy, TikTok Shop US và eBay. Không gọi API, LLM, scraping, hay dịch vụ trả phí. Không có dữ liệu kinh doanh thật hoặc số liệu demo trong repository.

## Cài đặt và chạy

Python **3.12+**, từ thư mục repository:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Giữ terminal đang chạy app. Để dừng, nhấn Ctrl+C. Bốn dependency trực tiếp vẫn là `streamlit`, `pandas`, `openpyxl`, `pytest`; SQLite thuộc thư viện chuẩn Python. Không cần API key.

### Windows 10/11: cài đặt lần đầu

Khuyến nghị **Python 3.12, 64-bit** từ [python.org](https://www.python.org/downloads/windows/), với pip và Python Launcher (`py`). Code yêu cầu Python 3.12 trở lên; 3.12 là phiên bản đã chạy tests trong cloud. Không dùng Python 2 hoặc Python 32-bit. Cài [Git for Windows](https://git-scm.com/downloads/win) nếu muốn clone/pull bằng Git. Mở terminal mới sau khi cài; không cần chạy Administrator.

Trong Command Prompt hoặc PowerShell, mở một thư mục bạn có quyền ghi rồi lấy code:

```text
git clone https://github.com/atchoangstr/rd-intelligence-mvp.git
cd rd-intelligence-mvp
py -3.12 --version
```

Nếu đã có bản clone, mở terminal trong thư mục đó và chạy `git pull --ff-only` thay vì clone lại. Nếu Git báo có thay đổi local hoặc nhánh phân kỳ, giữ nguyên các file và xử lý trước; không dùng reset/force-pull. Có thể tải **Code → Download ZIP** từ GitHub, giải nén, rồi mở terminal trong thư mục chứa `app.py` và `requirements.txt` nếu không dùng Git.

Chọn **một** trong hai cách dưới đây. Chạy mọi lệnh từ thư mục chứa `app.py`.

**Command Prompt (cmd.exe)**

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
python -m pip check
python -m pytest -q
python -m streamlit run app.py
```

**PowerShell**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip check
python -m pytest -q
python -m streamlit run app.py
```

Nếu PowerShell chặn `Activate.ps1` vì execution policy, **không cần đổi policy**. Sau khi tạo `.venv`, gọi trực tiếp Python của virtual environment (cách này dùng được trong cả hai terminal):

```text
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Nếu `py` không được nhận diện, kiểm tra Python/Launcher đã cài và mở lại terminal. Khi `python --version` xác nhận đúng Python 3.12+, có thể dùng `python -m venv .venv` thay cho `py -3.12 -m venv .venv`. Nếu `python` mở Microsoft Store, dùng Python Launcher hoặc đường dẫn tới Python đã cài; không tiếp tục bằng interpreter chưa xác định.

Sau khi Streamlit chạy, mở địa chỉ Local URL được in trong terminal. Nếu trình duyệt không tự mở, copy địa chỉ đó vào trình duyệt. App không cần internet sau khi đã cài dependencies. Chọn **Import dữ liệu** để bắt đầu; chưa upload thì dashboard để trống. Không chuyển thư mục `.venv` từ Linux/cloud sang Windows; luôn tạo virtual environment mới trên Windows.

**Những lần chạy sau (không cần cài lại mỗi lần)**

Mở terminal trong repository rồi chạy:

```text
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Để chạy tests, dừng app bằng Ctrl+C hoặc mở terminal thứ hai trong repository:

```text
.\.venv\Scripts\python.exe -m pytest -q
```

SQLite tự tạo tại `data\intelligence.sqlite3` sau khi mở app. Giữ database, uploads, exports và backup ở máy của bạn, không commit vào Git. Xem phần backup bên dưới trước khi đổi máy hoặc cập nhật dữ liệu. Tests dùng database giả lập trong thư mục tạm, không dùng dữ liệu kinh doanh hiện có.

Các lệnh Windows ở trên được kiểm tra về đường dẫn và dependency; bộ tests được thực thi trong môi trường cloud Linux, chưa có lần chạy native Windows trong phiên làm việc này.

## Quy trình sử dụng

1. **Import dữ liệu**: chọn một hoặc nhiều CSV UTF-8 (dấu phẩy) hoặc Excel `.xlsx`. Mỗi tệp dùng một marketplace; tệp nhiều marketplace cần tách trước. Cột marketplace đã map nếu khác lựa chọn sẽ bị từ chối. Mỗi tệp có sheet, định dạng ngày và mapping riêng. Tối đa 20 MB, 100.000 dòng/tệp; Excel giải nén tối đa 100 MB. Dòng đầu là header. File macro, `.xls`, file hỏng và file rỗng không được hỗ trợ.
2. Chọn đúng **loại báo cáo**. `daily_summary`: một dòng mỗi **ngày / marketplace SKU / currency**. `order_lines`: cần **order_id và line_id ổn định**, mỗi dòng chỉ một SKU. Báo cáo tổng đơn nhiều SKU, tổng theo tháng, returns riêng hoặc net-only chưa được hỗ trợ. Không giả vờ diễn giải chúng thành order lines. Nếu không đủ định danh, chuẩn hóa rõ ràng thành daily summary trước.
3. Xem preview và sửa **map cột**. Auto-mapping chỉ là gợi ý theo tên cột; khi có hai tên cùng khớp, hệ thống để bạn quyết định. Các trường bắt buộc: date, sku, quantity, revenue, currency; order lines cần thêm order_id, line_id. Chọn định dạng ngày rõ ràng để tránh nhầm ngày/tháng.
4. **Currency** phải được map hoặc nhập mặc định do bạn xác nhận; không tự suy đoán USD. Dùng mã ba chữ cái viết hoa (ví dụ USD/EUR). Ứng dụng kiểm tra định dạng mã, chưa có danh mục xác thực đầy đủ ISO 4217. Không chuyển đổi tiền tệ.
5. Xem tổng dòng, accepted/rejected/duplicated, tải lỗi và xem trước các dòng. Tick xác nhận rồi bấm **Xác nhận import**. Các dòng hợp lệ được lưu; dòng từ chối/trùng được ghi audit, không biến mất im lặng. Kiểm tra kết quả cuối trong **Lịch sử import**, vì dữ liệu trùng được kiểm tra lại trong transaction khi ghi.
6. **Sản phẩm & SKU**: tìm/lọc và xem SKU chưa mapping. Tạo canonical product hoặc liên kết thủ công SKU khác vào cùng product. Không tự merge theo tên hoặc SKU. Sửa metadata chuẩn dùng chung (category, attributes, production method). SKU gốc và marketplace được giữ nguyên. Thêm unit cost theo ngày hiệu lực/currency khi có thông tin thật.
7. **Phân tích bán hàng**: lọc ngày, marketplace, SKU, category và một currency. Xem units, reported gross sales, ASP, top SKU, xu hướng tháng, marketplace, tập trung top 5 và các dòng cần bổ sung thông tin. Export giữ bộ lọc.
8. **Cơ hội R&D**: bấm tạo từ sales đã ghi nhận. Mở evidence snapshot và giải thích score. Lọc/sort, cập nhật concept, status, ghi chú, lý do quyết định, next action, ngày mục tiêu và kết quả sau launch. Approved for Launch / Rejected bắt buộc lý do. Mọi lần lưu giữ nội dung trước/sau trong decision history.
9. **Phát triển concept**: chỉnh template có cấu trúc và lưu brief. Các giả thuyết chưa biết được ghi rõ; đây không phải insight từ AI hay xác thực thị trường. Export brief, opportunities, score contributions, pipeline, performance, trends và audit bằng CSV hoặc Excel.

### Schema CSV mẫu (hoàn toàn giả lập)

```csv
date,sku,title,quantity,revenue,currency,category
2025-01-01,SYNTH-VASE-001,Synthetic vase,2,40.00,USD,Decor
2025-01-02,SYNTH-VASE-001,Synthetic vase,1,20.00,USD,Decor
```

Ví dụ trên là **daily_summary**, không phải dữ liệu thị trường. Số dùng dấu chấm thập phân, không `$` hoặc dấu phân cách nghìn. SKU và order/line IDs được đọc như text để giữ số 0 đầu. Nếu ID trong Excel đã bị Excel biến thành số và mất số 0 trước upload, ứng dụng không thể khôi phục chúng.

## Quy tắc tài chính và chất lượng dữ liệu

- `revenue` là **gross sales cho cả dòng, trước discounts/refunds/fees/shipping/cost**. Không map net payout vào gross sales. App không thể tự biết ngữ nghĩa từ tên cột; người import phải xác nhận đúng export.
- `discounts`, `refunds`, `fees`, `shipping`, `cost` là số tiền **không âm cho cả dòng**, cùng currency với revenue. `cost` là tổng product cost, không phải đơn giá. Số 0 chỉ hợp lệ nếu đã xác nhận thật sự không có khoản đó. Để trống = chưa biết.
- Quantity phải là số nguyên dương. Dòng âm, refund-only và điều chỉnh không hỗ trợ trong phiên bản này. Không nhập file chứa order-level shipping/fees lặp lại trên từng SKU vì sẽ tính chi phí nhiều lần.
- Product cost có thể lấy từ bảng unit cost theo SKU, cùng currency, ngày hiệu lực gần nhất không sau ngày sale. Cost ghi rõ trong sales ưu tiên hơn bảng cost. Giá trị thiếu không trở thành 0.
- Profit ước tính = gross sales − discounts − refunds − fees − shipping − product cost, **chỉ khi tất cả dòng trong bộ lọc có đủ thông tin**. Thiếu một khoản ở một dòng thì tổng profit/margin để trống. Đây chưa phải lợi nhuận kế toán: chưa có overhead, thuế hay quảng cáo ngoài export. Sales không được gọi là profit. ASP = reported gross sales / units, không phải giá niêm yết.
- Mỗi báo cáo tiền tệ có currency, không cộng hay so sánh tiền khác currency. Tính toán dùng số thực cho phân tích, không phải sổ kế toán yêu cầu độ chính xác tiền tệ tuyệt đối.
- Số active products trên dashboard là **active marketplace SKU**, không giả vờ mỗi SKU là một physical product. Canonical product mapping hiển thị trong catalog; chưa có ranking hợp nhất theo family.
- Không có bản ghi gần đây nghĩa là **chưa rõ**, không phải sales = 0. Tháng đầu/cuối có thể chưa đủ. So sánh hai cửa sổ 30 ngày hoàn tất (loại ngày hôm nay) cần ≥10 units và ≥5 ngày có sales mỗi cửa sổ, cùng lịch sử bắt đầu trước cửa sổ đầu. Phần trăm change để trống nếu thiếu bằng chứng. Vẫn cần xác nhận report coverage, hết hàng, giá và khuyến mãi trước khi kết luận tăng/giảm thực sự.

## Chống trùng, provenance và transaction

- Daily summary định danh bởi **marketplace + loại report + date + SKU + currency**. Hai dòng cùng định danh ngay trong cùng tệp bị từ chối để tránh tự gộp sai. Chuẩn hóa/aggregate nguồn trước nếu cần.
- Order line định danh bởi **marketplace + loại report + order_id + line_id**. Các order line khác nhau vẫn được giữ dù cùng SKU, ngày và tiền.
- Identity và payload chuẩn hóa được SHA-256. Cùng identity + cùng số liệu = duplicate, không thêm sale. Cùng identity + số liệu khác = conflict, từ chối và yêu cầu đối soát, không cập nhật sale cũ. Đổi tên file, định dạng `40.00` thành `40` hoặc upload lại vẫn không thêm sale. File hash được lưu cho audit, không dùng riêng tên/hash file làm chống trùng.
- Không trộn order lines và summary trong **cùng marketplace đã có sales**, vì nguồn có thể trùng khoảng thời gian. Sửa sai/reconciliation, xóa import và chuyển loại báo cáo chưa có UI; không xóa SQLite để "sửa" dữ liệu thật. Backup trước và yêu cầu công việc migration có kiểm soát.
- Toàn bộ một lần xác nhận tệp (sales hợp lệ + import log + source audit) dùng một transaction có khóa ghi và uniqueness constraints. Lỗi DB rollback toàn lần ghi; dữ liệu trước đó vẫn còn. Nhiều tệp là nhiều transaction độc lập, không phải một batch transaction.
- Lưu thời gian import (UTC của SQLite), file name đã bỏ đường dẫn, record number (bắt đầu 2), sheet/mapping/date format/default currency, raw **các cột đã map**, trạng thái/lý do và sale ID. Không lưu các cột chưa map (đặc biệt PII) hay upload gốc lên ổ đĩa. CSV có multiline cells: record number là thứ tự bản ghi, không phải số dòng vật lý.
- Tiêu đề/category sửa khác không sửa sales; catalog cần cập nhật có chủ ý. Không có tự merge canonical products. Metadata và cost editing chưa có version audit riêng; decision history áp dụng cho cơ hội.

## Opportunity engine và scoring

Quy tắc trong `intelligence/config.py`; không machine learning, không dữ liệu đối thủ:

- ≥10 units và ≥5 ngày có sales: đề xuất **nghiên cứu biến thể**, không khẳng định thiếu màu/size hoặc khách hàng muốn gì. Ít dữ liệu hơn: cơ hội **thu thập bằng chứng**, không khuyến nghị mạnh.
- Hai cửa sổ đủ điều kiện tăng ≥25% hoặc giảm ≤−25% units: review tăng trưởng hoặc điều tra suy giảm. Đây là tín hiệu quan sát, chưa loại trừ yếu tố ngoài.
- Canonical product chỉ mapping tới một marketplace và có tín hiệu đủ: rà soát mapping/năng lực ở marketplace khác. Không kết luận chưa bán ở nơi khác hoặc nhu cầu ở đó cao.
- Seasonal review cần **hai năm lịch đầy đủ liên tiếp**, mỗi tháng có ≥5 ngày có sales, cùng tháng peak ở cả hai năm, daily rate tháng peak ≥2 lần median tháng. Vẫn có thể do tồn kho/khuyến mãi/độ phủ. Không đủ lịch sử thì không phát biểu mùa vụ.
- Mỗi opportunity lưu immutable evidence snapshot và giai đoạn nguồn, currency, unknowns, next step, risk, confidence và score breakdown. Cùng SKU/currency/loại/ngày không tạo lại, không reset quyết định; ngày khác có thể tạo snapshot mới. Sales của ngày hôm nay hoặc tương lai không được dùng. Cơ hội không tự đồng bộ khi metadata/cost thay đổi; tạo snapshot ngày tiếp theo sau review nếu cần.

Priority 0–100 là weighted mean của **các yếu tố đã biết**, không chèn số 0 cho unknown. Breakdown gồm raw factor, weight, contribution và lý do. Weights mặc định:

| Factor | Weight | Rule |
| --- | ---: | --- |
| Sales signal | 20 | min(100, units / 50 × 100) |
| Consistency | 20 | min(100, active sale days / 20 × 100) |
| Differentiation | 15 | Unknown; cần nghiên cứu ngoài |
| Production fit | 15 | Unknown; có tên method chưa đủ xác nhận khả thi |
| Cost coverage | 10 | % dòng có product cost; unknown nếu không có cost nào |
| Evidence | 10 | min(100, active sale days / 30 × 100) |
| Risk readiness | 10 | 20 base +20 mỗi điều kiện: đủ observations, có một phần cost, canonical mapping, known attributes |

Confidence riêng là factor Evidence, một heuristic về độ dày quan sát, **không phải xác suất thành công**. Known-weight coverage được hiển thị cạnh score; commercial attractiveness vẫn unknown khi chưa nghiên cứu thị trường/kinh tế đơn vị. Risk readiness nói về chuẩn bị dữ liệu, không phải mức cạnh tranh. Thiếu competitor data không chứng minh cạnh tranh thấp. Score cao không bảo đảm sales. Thresholds/weights tập trung trong `config.py`; thay đổi cần review và test.

Status: New → To Research → Researching → Ready for Sampling → Sampling → Testing → Approved for Launch → Launched, với Rejected/Archived khi cần. UI cho phép đổi status thủ công, không ép tuần tự. Không tự coi generated concept là validated. Actual launch results hiện là ghi chú có kỳ đo, currency và nguồn do người dùng nhập; chưa tự liên kết SKU launch để tính uplift.

## SQLite, backup và bảo mật

Mặc định: `data/intelligence.sqlite3` trong repository (được Git ignore). Đặt biến `RD_DATABASE_PATH` trước khi start nếu muốn đường dẫn khác. Các bảng: imports, source_rows, sales, products, sku_mappings, costs, opportunities, decisions, concepts. Có foreign keys, unique identities và index theo ngày/SKU/import. Schema v1 được tạo bổ sung bằng `IF NOT EXISTS`, không drop hoặc xóa dữ liệu lúc startup. Database phiên bản mới hơn bị từ chối mở bằng code cũ. Khi đổi schema tương lai phải thêm migration có version và backup trước.

**Backup**: trong Cài đặt, bấm Chuẩn bị backup SQLite rồi tải snapshot nhất quán. Hoặc dừng app rồi copy tệp SQLite sang nơi an toàn. Khôi phục: dừng app, giữ backup của database hiện tại, copy bản backup đã xác minh về đường dẫn cấu hình, rồi start lại. Không ghi đè khi app đang chạy. Backup chứa dữ liệu nhạy cảm, không commit hay chia sẻ công khai.

Upload/export chỉ ở memory, dữ liệu import lưu local. Các cột PII không nằm trong standard mapping; vẫn cần kiểm tra title/IDs do người dùng chọn không chứa thông tin nhạy cảm. Không log business rows. Export escape text bắt đầu `= + - @` để giảm spreadsheet formula injection. Excel macro không được thực thi. Không có authentication/multi-tenant access; chạy local hoặc môi trường riêng của người dùng tin cậy, không publish công khai dữ liệu thật. `.gitignore` loại trừ database và journals, uploads, exports, dữ liệu CSV/Excel, .env, secrets và virtualenv. Kiểm tra `git status` và staged diff trước mỗi commit.

## Tests và cấu trúc

```bash
python -m pytest -q
python -m pip check
```

Tests chỉ tạo synthetic data trong thư mục tạm, không dùng database của người dùng. Có kiểm tra parser, mapping, validation, dedup/conflicts, rollback, catalog/cost, phân tích/currency/profit, rule/scoring, history/concepts, export an toàn và Streamlit navigation ở empty/populated states.

- `app.py`: UI tiếng Việt và điều hướng.
- `intelligence/config.py`: đường dẫn, giới hạn, thresholds và weights.
- `intelligence/db.py`: schema/version/transaction.
- `intelligence/imports.py`: parsing, validation, provenance, chống trùng.
- `intelligence/catalog.py`, `analytics.py`: catalog/cost và phép tính.
- `intelligence/opportunities.py`: rules, scoring, decision history, concept template; có thể thêm provider tùy chọn sau này ở service layer, không phụ thuộc LLM.
- `intelligence/exports.py`: CSV/Excel trong memory.
- `tests/`: unit, integration và Streamlit AppTest.

## Giới hạn và milestone tiếp theo

Chưa có adapter riêng cho mọi export marketplace; mapping và hiểu đúng gross sales cần người dùng kiểm tra. Chưa có FX, xử lý returns/adjustments, import net-only, reconciliation/correction UI, canonical-family ranking, audit metadata/cost revisions, automated launch attribution hoặc dữ liệu thị trường ngoài. Chưa benchmark 10.000 SKUs/3 năm; upload giới hạn mỗi tệp và app local dùng memory để phân tích; chia batch hợp lý. Seasonal rules chỉ xem observed units; cần review coverage thủ công. Rule suggestions không invent thuộc tính/sở thích hoặc chứng minh tổng nhu cầu thị trường.

Milestone tiếp theo: đối soát một export đã ẩn danh cho từng marketplace, adapter có test fixture, quy trình correction/coverage audit và báo cáo theo canonical family trước khi mở rộng research hoặc tùy chọn LLM.
