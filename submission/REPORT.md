# Báo cáo Day 09 — Đặng Anh Tuyền, 2A202603039

## 1. Kết luận trước

**Hold.** Trong 224 ảnh đầu vào, pipeline nhận 193 ảnh và loại 31 ảnh. Sau khi duyệt 80 ảnh, còn 0 lỗi bắt buộc nhưng 34/193 ảnh (17,62%) vẫn có cảnh báo chưa được duyệt, vượt ngưỡng 10%. Pipeline xuất 193 ảnh dưới dạng bản nháp `clean_v1`. [Tóm tắt](reports/08_summary.json) · [Manifest bản xuất](export/clean_v1/manifest.json)

## 2. Lỗi và phân việc

Bảng đếm số lần từng mã xuất hiện trước khi sửa. Khâu nhận ảnh xét 224 ảnh, phần QC xét 193 ảnh được nhận. Một ảnh hoặc một dòng nhãn có thể có nhiều mã. [Danh sách lỗi lần 1](reports/02_error_list_v1.csv)

| Mã lỗi và số cờ | Phân việc và lý do |
|---|---|
| `CORRUPT_IMAGE` 2, `BAD_SIZE` 3, `DUP_IMAGE_EXACT` 8, `DUP_IMAGE_NEAR` 7, `LEAK_TEST` 11 | Máy loại ở khâu nhận ảnh để loại ảnh hỏng, nhỏ, trùng hoặc rò rỉ sang tập đánh giá. |
| `BAD_FORMAT` 3, `BAD_CLASS_ID` 6, `BOX_ZERO` 4, `DUP_BOX` 7, `BOX_OUT_OF_IMAGE` 8 | Máy bỏ dòng sai hoặc trùng và cắt box tràn còn diện tích. |
| `BAD_CLASS_NAME` 2 | Máy chuẩn hóa danh sách tên lớp trong `data.yaml` một lần. |
| `MISSING_LABEL_FILE` 6 | Người gán nhãn. Máy ghi nhận và đưa ảnh vào hàng đợi. |
| `EMPTY_LABEL` 11, `BOX_TINY` 6, `BOX_HUGE` 3, `CLASS_RARE` 4 | Người kiểm tra ngữ cảnh ảnh hoặc độ phủ của lớp. |
| `POSSIBLE_MISSING` 53, `POSSIBLE_WRONG_CLASS` 17, `POSSIBLE_LOOSE_BOX` 27, `POSSIBLE_FALSE_POS` 28 | Người đối chiếu ảnh và nhãn vì dự đoán của model chỉ là tín hiệu nghi vấn. |

QC lần 1 có 36 lỗi bắt buộc và 149 cảnh báo. Nhật ký ghi 35 hành động gồm 20 lần bỏ dòng, 8 lần cắt box, 1 lần chuẩn hóa tên lớp và 6 yêu cầu gán nhãn. [Nhật ký sửa](reports/03_fixes.csv)

Hàng đợi có 121 ảnh. `img_0020` đứng đầu với 11,524 điểm do cộng điểm của dòng đã bỏ, nghi thiếu box và nghi sai lớp. Sáu ảnh chưa có file nhãn đứng ngay sau, mỗi ảnh 10 điểm. Với ngân sách 80 ảnh, lượt duyệt mô phỏng bao phủ **94/120 cờ ngữ nghĩa** sau sửa tự động, trên **74/100 ảnh có cờ ngữ nghĩa**. Đó là số cờ được xem, còn số lỗi thật cần được xác nhận bằng nhãn người. [QC lần 2](reports/04_error_list_v2.csv) · [Hàng đợi](reports/05_review_queue.csv) · [Nhật ký duyệt](reports/06_review_log.csv)

## 3. Calibration hai ngưỡng

| Tham số | Cũ → mới | Precision / Recall trước → sau | Lý do |
|---|---|---|---|
| `duplicates.phash_dist` | 2 → 16 | Gần trùng 1,00 / 0,50 → 1,00 / 0,83 | Bắt thêm 2 ca, từ 3/6 lên 5/6, với 0 cờ sai trên bộ calibration. Trùng chính xác vẫn bắt đủ 3/3. |
| `second_opinion.conf` | 0,25 → 0,60 | Thiếu box 0,50 / 1,00 → 0,57 / 1,00. Sai lớp 0,56 / 0,83 → 0,62 / 0,83. Box lỏng 0,29 / 0,40 → 0,20 / 0,20. | Giảm từ 8 xuống 6 cờ sai ở nhóm thiếu box và từ 4 xuống 3 ở nhóm sai lớp, giữ nguyên số ca đúng của hai nhóm. Đánh đổi là bắt được 1/5 ca box lỏng thay vì 2/5. |

Bộ calibration chỉ gồm 6 ca gần trùng nên thêm hoặc bớt một ca đã thay đổi recall khoảng 16,7 điểm phần trăm. Precision 1,00 ở ngưỡng 16 chỉ phản ánh bộ mẫu này. [Bảng sweep](calibration/calibration_report.md) · [Số đếm TP, FP, FN](calibration/calibration.json)

## 4. Cửa chặn và điểm mù

**Bằng chứng chạy với ngân sách 0 đang chờ xác nhận.** QC lần 2 ghi nhận 6 ảnh chưa có file nhãn. Vì lỗi này bắt buộc, lượt chạy `--budget 0` dự kiến trả **Rework**, mã **20** và không tạo manifest ở thư mục xuất thử. Kết quả thực tế sẽ được bổ sung từ `work/rep_nb/08_summary.json` và kiểm tra `work/exp_nb/manifest.json`. [Danh sách lỗi trước duyệt](reports/04_error_list_v2.csv)

Hai điểm mù đã thấy trên bộ calibration ở cấu hình đã chọn:

- **Box lỏng có thể lọt qua.** Nhãn có thể đúng lớp, đúng cú pháp và vẫn bao vật kém. Cờ `POSSIBLE_LOOSE_BOX` bỏ sót 4/5 ca chèn.
- **Ảnh gần trùng có thể lọt qua.** Với khoảng cách pHash tối đa 16, cờ `DUP_IMAGE_NEAR` bỏ sót 1/6 ca chèn. [Số đếm ở hai ngưỡng đã chọn](calibration/calibration.json)

## 5. Train raw và clean

**Chưa chạy.** Sẽ bổ sung sau khi hoàn tất train cả hai biến thể với hai seed mỗi biến thể và có `submission/results/comparison.md`. Hiện chưa có số liệu để kết luận raw hay clean tốt hơn.

## 6. Quyết định và ghi chú AI

Giữ **Hold**. Để Release với cùng 193 ảnh, cần xử lý hoặc xác nhận đủ cảnh báo để còn tối đa 19 ảnh có cảnh báo chưa duyệt, đồng thời duy trì 0 lỗi bắt buộc. Nếu không phát sinh cảnh báo mới, cần xử lý thêm ít nhất 15 trong 34 ảnh đang còn cảnh báo. Ưu tiên kiểm tra thiếu box và sai lớp, rồi chạy lại QC và gate. [Danh sách lỗi cuối](reports/07_error_list_v3.csv)

- **Yêu cầu AI:** Hỗ trợ triển khai bốn module kiểm định, tự sửa, ra quyết định và đối chiếu dự đoán theo yêu cầu của lab.
- **Cách kiểm:** Chạy từng bộ test và toàn bộ pytest trong môi trường Day08. Kết quả người làm ghi nhận là 79 test qua. Đối chiếu thêm báo cáo calibration và kết quả pipeline.
- **Một lỗi của AI:** Lần ghi đầu của `label_format.py` làm một số thông báo tiếng Việt thành dấu hỏi do mã hóa terminal. Đã phát hiện khi xem diff, sửa sang UTF-8 và kiểm tra lại.
