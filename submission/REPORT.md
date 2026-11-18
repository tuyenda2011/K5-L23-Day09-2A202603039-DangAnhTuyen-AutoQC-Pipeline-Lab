# Day 09 Lab — Đặng Anh Tuyền: 2A202603039 - Đặng Anh Tuyền
## 1. Kết luận trước

Kết quả của lần chạy chính là **Hold**. Pipeline nhận 193 trong 224 ảnh đầu vào và loại 31 ảnh. Sau khi duyệt 80 ảnh, không còn lỗi bắt buộc, nhưng vẫn có 34/193 ảnh chưa được duyệt hết cảnh báo (17,62%). Tỷ lệ này vượt ngưỡng 10%, nên 193 ảnh chỉ được xuất thành bản nháp `clean_v1` để thử nghiệm. [Tóm tắt lần chạy](reports/08_summary.json) · [Manifest bản xuất](export/clean_v1/manifest.json)

## 2. Lỗi và phân việc

Ở khâu nhận ảnh, máy lọc trên cả 224 ảnh. Vòng kiểm tra nhãn sau đó chỉ xét 193 ảnh được nhận và ghi 36 lỗi bắt buộc cùng 149 cảnh báo. Bảng dưới đếm số lần từng mã xuất hiện trước khi sửa. Một ảnh hoặc dòng nhãn có thể xuất hiện ở nhiều mã. [Danh sách lỗi lần 1](reports/02_error_list_v1.csv)

| Mã lỗi và số lần xuất hiện | Cách xử lý |
|---|---|
| `CORRUPT_IMAGE` 2, `BAD_SIZE` 3, `DUP_IMAGE_EXACT` 8, `DUP_IMAGE_NEAR` 7, `LEAK_TEST` 11 | Máy loại ảnh hỏng, ảnh quá nhỏ, ảnh trùng và ảnh có nguy cơ rò rỉ sang tập đánh giá. |
| `BAD_FORMAT` 3, `BAD_CLASS_ID` 6, `BOX_ZERO` 4, `DUP_BOX` 7, `BOX_OUT_OF_IMAGE` 8 | Máy bỏ dòng lỗi hoặc trùng. Nếu box tràn nhưng vẫn còn diện tích trong ảnh, máy cắt box về đúng biên. |
| `BAD_CLASS_NAME` 2 | Máy sửa danh sách tên lớp trong `data.yaml` một lần cho cả hai lỗi. |
| `MISSING_LABEL_FILE` 6 | Máy đưa ảnh vào hàng đợi để người duyệt gán nhãn. |
| `EMPTY_LABEL` 11, `BOX_TINY` 6, `BOX_HUGE` 3, `CLASS_RARE` 4 | Người xem lại ngữ cảnh của ảnh hoặc số lượng nhãn theo lớp. |
| `POSSIBLE_MISSING` 53, `POSSIBLE_WRONG_CLASS` 17, `POSSIBLE_LOOSE_BOX` 27, `POSSIBLE_FALSE_POS` 28 | Người đối chiếu ảnh với nhãn để xác nhận các trường hợp mô hình nghi ngờ. |

Nhật ký ghi 35 hành động: bỏ 20 dòng, cắt 8 box, sửa danh sách lớp một lần và chuyển 6 ảnh cho người gán nhãn. Trong hàng đợi 121 ảnh, `img_0020` đứng đầu với 11,524 điểm vì ảnh này vừa có dòng bị bỏ, vừa bị nghi thiếu box và sai lớp. Sáu ảnh chưa có file nhãn đứng ngay sau, mỗi ảnh 10 điểm. [Nhật ký sửa](reports/03_fixes.csv) · [Hàng đợi](reports/05_review_queue.csv)

Trong 80 ảnh được duyệt mô phỏng, có 74 ảnh mang cảnh báo về nội dung nhãn. Như vậy lượt duyệt đã xem **94/120 cảnh báo** thuộc nhóm này, trên **74/100 ảnh** có ít nhất một cảnh báo. Một cảnh báo chỉ cho biết vị trí cần xem lại. Muốn biết đó có phải lỗi thật hay không thì phải đối chiếu với ảnh và nhãn người. [QC lần 2](reports/04_error_list_v2.csv) · [Nhật ký duyệt](reports/06_review_log.csv)

## 3. Chọn hai ngưỡng

| Tham số | Cũ → mới | Precision / Recall trước → sau |
|---|---|---|
| `duplicates.phash_dist` | 2 → 16 | Ảnh gần trùng: 1,00 / 0,50 → 1,00 / 0,83 |
| `second_opinion.conf` | 0,25 → 0,60 | Thiếu box: 0,50 / 1,00 → 0,57 / 1,00. Sai lớp: 0,56 / 0,83 → 0,62 / 0,83. Box lỏng: 0,29 / 0,40 → 0,20 / 0,20. |

Mình chọn khoảng cách pHash 16 vì trên bộ calibration, số ca gần trùng phát hiện được tăng từ 3/6 lên 5/6 mà vẫn chưa có cảnh báo sai. Cả hai ngưỡng đều phát hiện đủ 3/3 ca trùng chính xác. Với ngưỡng tin cậy 0,60, cảnh báo sai ở nhóm thiếu box giảm từ 8 xuống 6 và ở nhóm sai lớp giảm từ 4 xuống 3. Hai nhóm này vẫn bắt được cùng số lỗi thật. Phần phải đánh đổi là box lỏng chỉ còn bắt được 1/5 ca, so với 2/5 ở ngưỡng cũ.

Bộ calibration có đúng 6 ca gần trùng. Chỉ cần bắt thêm hoặc bỏ sót một ca là recall thay đổi khoảng 16,7 điểm phần trăm. Vì vậy, precision 1,00 ở ngưỡng 16 mới cho thấy kết quả trên bộ mẫu này. [Bảng thử ngưỡng](calibration/calibration_report.md) · [Số đếm chi tiết](calibration/calibration.json)

## 4. Cửa chặn và điểm mù

Mình chạy lại với `--budget 0` để xem chuyện gì xảy ra khi không ai duyệt nhãn. Sau vòng kiểm tra cuối, 6 ảnh vẫn thiếu file nhãn (`MISSING_LABEL_FILE`). Gate trả về **Rework**, mã thoát **20**. Báo cáo `work/rep_nb/08_summary.json` ghi `exported: null`. Kiểm tra thư mục thử cũng không thấy `work/exp_nb/manifest.json`.

Calibration cho thấy hai điểm mù ở các ngưỡng đã chọn:

- **Box lỏng:** Nhãn vẫn có thể đúng lớp và đúng cú pháp dù box bao vật quá rộng. Ở ngưỡng 0,60, kiểm tra bỏ sót 4/5 ca box lỏng đã chèn.
- **Ảnh gần trùng:** Kiểm tra bằng pHash với khoảng cách tối đa 16 vẫn bỏ sót 1/6 ca gần trùng đã chèn. [Kết quả calibration](calibration/calibration.json)

## 5. So sánh huấn luyện raw và clean

Mình dùng `yolo26n.pt` cho cả hai bộ dữ liệu, với 20 epoch, batch 16 và kích thước ảnh 640. Mỗi bộ chạy hai lần với seed 0 và 1. Bộ `clean` dùng bản nháp `clean_v1` có trạng thái Hold. Bảng ghi trung bình ± độ lệch chuẩn giữa hai seed. [Số liệu train](results/comparison.json)

<https://colab.research.google.com/drive/1A7XJfAipwj4bMA7YW_nAUcHEbyK6NFNH?usp=sharing>

| Biến thể | Ảnh train | mAP50 | mAP50–95 | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| raw | 224 | 0,7258 ± 0,0002 | 0,5117 ± 0,0038 | 0,7635 ± 0,0612 | 0,6490 ± 0,0281 |
| clean | 193 | 0,7294 ± 0,0024 | 0,4996 ± 0,0003 | 0,7936 ± 0,0285 | 0,6193 ± 0,0047 |

Bộ clean tăng **0,0036 mAP50**. Mức tăng này lớn hơn độ lệch chuẩn quan sát được ở cả hai bộ (0,0002 với raw và 0,0024 với clean), nhưng hai seed vẫn là quá ít để biết mức chênh có ổn định hay không. Trong khi đó, mAP50–95 của clean giảm **0,0121** và recall cũng giảm. Với kết quả hiện tại, mình chưa thể kết luận clean tốt hơn tổng thể.

Có hai khả năng mình muốn kiểm tra thêm:

- Khâu nhận ảnh gắn cờ 11 ảnh trùng với kho test/val. Để xem việc trùng ảnh có ảnh hưởng đến điểm raw không, có thể đánh giá lại cả hai mô hình trên cùng một tập giữ lại đã xác minh không trùng với hai tập train. [Báo cáo nhận ảnh](reports/01_intake.csv)
- Bản clean còn 34 ảnh có cảnh báo chưa duyệt. Có thể xem lại một mẫu nhãn để tìm box lệch hoặc thiếu box, rồi đối chiếu dự đoán ở IoU 0,50 và 0,75 để xem lỗi định vị có đi kèm mức giảm mAP50–95 hay không. [Danh sách lỗi cuối](reports/07_error_list_v3.csv)

## 6. Quyết định và ghi chú AI

Mình giữ quyết định **Hold** và ưu tiên xem lại các ảnh bị nghi thiếu box hoặc sai lớp. Với 193 ảnh, để xuống dưới ngưỡng 10% thì chỉ được còn tối đa 19 ảnh có cảnh báo chưa duyệt. Nếu không phát sinh cảnh báo mới, cần xử lý thêm ít nhất 15 trong 34 ảnh đang chờ, sau đó chạy lại QC và gate để xác nhận vẫn còn 0 lỗi bắt buộc. [Danh sách lỗi cuối](reports/07_error_list_v3.csv)

### 6.1. Cách sử dụng AI

Mình dùng Codex để làm lần lượt bốn module theo mô tả và ca kiểm thử của bài: kiểm tra định dạng nhãn, quyết định trạng thái phát hành, tự sửa lỗi và đối chiếu nhãn với dự đoán của mô hình.

**Prompt sử dụng (tóm tắt)**

>Viết bốn phần của AutoQC theo các test có sẵn. Khi đọc nhãn YOLO, báo đúng số dòng bị lỗi và lấy ngưỡng từ YAML. Nếu cần sửa nhãn, chỉ sửa bản làm việc và ghi lại trước và sau khi sửa. Dùng IoU để so nhãn với dự đoán đã lưu, rồi cảnh báo những chỗ cần người xem lại. Cuối cùng, dùng số lỗi bắt buộc và tỷ lệ ảnh còn cảnh báo để quyết định Release, Hold hay Rework. Giữ nguyên dữ liệu gốc và bộ test.

Mình kiểm tra từng module rồi chạy cả bộ test trong môi trường Day08, kết quả là **79 test qua**. Sau đó, mình đối chiếu số liệu calibration và tự chạy pipeline ở hai mức ngân sách để xác nhận **Hold** với 80 ảnh và **Rework** với 0 ảnh.
