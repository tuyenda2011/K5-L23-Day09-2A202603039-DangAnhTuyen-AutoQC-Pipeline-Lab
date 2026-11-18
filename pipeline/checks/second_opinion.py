"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).   ★★★ (khó nhất, đáng điểm nhất)

Test:  pytest tests/test_second_opinion.py -q

Máy kiểm quy tắc, người kiểm ý nghĩa (slide). Các lỗi như thiếu nhãn / gán nhầm lớp hợp lệ / box lỏng
KHÔNG bắt được bằng quy tắc cú pháp. Ta nhờ một model mạnh hơn "nhìn lại" và CHỈ CẢNH BÁO (model cũng có thể sai):
những ảnh bị cờ sẽ vào hàng đợi cho NGƯỜI duyệt.

`preds[stem]` = list `[id_lớp, conf, cx, cy, w, h]` của model (lấy qua `get_preds(ds, cfg, "checker")` nếu preds=None).
`L = ds.valid_boxes(stem)` = list `(id_lớp, cx, cy, w, h)` của nhãn (đã bỏ dòng hỏng).
Ngưỡng ở `cfg["second_opinion"]`: conf, min_area_px, fp_conf, iou_missing, iou_match, iou_loose.

Thuật toán gợi ý, với từng ảnh (bỏ qua ảnh không có trong preds hoặc không có file nhãn):
  P = dự đoán có conf >= conf  VÀ diện tích px (w*W * h*H) >= min_area_px
  Với mỗi dự đoán r trong P: lấy các nhãn có IoU(r, nhãn) >= iou_missing  (cands)
   - không có cands                            -> POSSIBLE_MISSING     (model thấy vật mà nhãn không có box)
   - có cands cùng lớp, tốt nhất IoU < iou_loose -> POSSIBLE_LOOSE_BOX  (đúng vật, box lỏng/lệch)
   - không có cands cùng lớp, nhưng cands tốt nhất IoU >= iou_match (khác lớp) -> POSSIBLE_WRONG_CLASS
  Với mỗi dòng nhãn hợp lệ: nếu IoU với MỌI dự đoán (conf >= fp_conf, không lọc diện tích) đều < iou_missing
                                             -> POSSIBLE_FALSE_POS  (box nhãn không khớp vật nào model thấy; Issue.line = số dòng)

Chi tiết các ca biên (test kiểm đúng các ca này)
- `cands` gồm nhãn MỌI lớp có IoU >= iou_missing; "tốt nhất cùng lớp" = cands cùng lớp có IoU lớn nhất; "tốt nhất khác lớp" tương tự với cands khác lớp.
- Thứ tự quyết định cho mỗi dự đoán: (1) cands rỗng -> MISSING. (2) có cands cùng lớp: IoU tốt nhất < iou_loose -> LOOSE_BOX, ngược lại KHÔNG cờ
  (nhãn đúng lớp đã phủ vật này, kể cả khi còn nhãn khác lớp chồng lên). (3) không có cands cùng lớp: nếu IoU tốt nhất khác lớp >= iou_match -> WRONG_CLASS;
  nếu chỉ có khác lớp với IoU trong [iou_missing, iou_match) -> không cờ gì (mơ hồ: để cho FALSE_POS / lần duyệt khác).
- Một dự đoán sinh tối đa MỘT issue (MISSING / LOOSE_BOX / WRONG_CLASS); một ảnh có thể có nhiều issue.
- Thứ tự issue: theo `ds.image_files()` rồi theo thứ tự dự đoán trong `preds[stem]`, cuối cùng là các FALSE_POS theo số dòng; `Issue.image` = stem, `Issue.line` chỉ đặt cho FALSE_POS.

Lưu ý số dòng: dùng `ds.read_label_lines(stem)` (giữ số dòng gốc, kể cả dòng hỏng/trống) để lấy `Issue.line`; `valid_boxes` KHÔNG giữ số dòng.

Tất cả severity WARN; `Issue.extra` nên có {"conf": ...} hoặc {"iou": ...} (hàng đợi duyệt dùng conf để xếp ưu tiên).

Gợi ý
- `iou_xywh` có sẵn. Dòng nhãn hỏng không được làm script chết (dùng `ds.valid_boxes` và `parse_yolo_line` trong try).
- Kết quả phụ thuộc mạnh vào ngưỡng: calibrate chúng ở Bước 3 thay vì đoán.
"""
from ..common import WARN, Issue, iou_xywh, parse_yolo_line
from ..model_cache import get_preds


def _valid_labels(lines, class_count):
    labels = []
    for line, text in lines:
        try:
            class_id, *box = parse_yolo_line(text)
        except (ValueError, OverflowError):
            continue
        if 0 <= class_id < class_count:
            labels.append((line, class_id, box))
    return labels


def run(ds, cfg, preds=None):
    if preds is None:
        preds = get_preds(ds, cfg, "checker")

    thresholds = cfg["second_opinion"]
    conf_threshold = thresholds["conf"]
    min_area_px = thresholds["min_area_px"]
    fp_conf = thresholds["fp_conf"]
    iou_missing = thresholds["iou_missing"]
    iou_match = thresholds["iou_match"]
    iou_loose = thresholds["iou_loose"]
    class_count = len(ds.classes)
    issues = []

    for image in ds.image_files():
        stem = image.stem
        if stem not in preds:
            continue
        lines = ds.read_label_lines(stem)
        if lines is None:
            continue

        labels = _valid_labels(lines, class_count)
        size = ds.image_size(stem)
        best_fp_ious = {}

        for class_id, conf, cx, cy, width, height in preds[stem]:
            check_prediction = (
                conf >= conf_threshold
                and size is not None
                and (width * size[0]) * (height * size[1]) >= min_area_px
            )
            check_label_overlap = conf >= fp_conf
            if not check_prediction and not check_label_overlap:
                continue

            box = (cx, cy, width, height)
            best_overlap = best_same_class = -1.0
            # Use the same IoU for both checks, which have separate filters.
            for line, label_class, label_box in labels:
                overlap = iou_xywh(box, label_box)
                if check_label_overlap and overlap > best_fp_ious.get(line, -1.0):
                    best_fp_ious[line] = overlap
                if check_prediction and overlap >= iou_missing:
                    best_overlap = max(best_overlap, overlap)
                    if label_class == class_id:
                        best_same_class = max(best_same_class, overlap)

            if not check_prediction:
                continue
            if best_overlap < 0:
                issue = Issue("second_opinion", WARN, "POSSIBLE_MISSING", stem,
                              "Model thấy vật nhưng không có box nhãn khớp", extra={"conf": conf})
            elif best_same_class >= 0:
                if best_same_class >= iou_loose:
                    continue
                issue = Issue("second_opinion", WARN, "POSSIBLE_LOOSE_BOX", stem,
                              "Box cùng lớp có IoU thấp", extra={"conf": conf, "iou": best_same_class})
            elif best_overlap >= iou_match:
                issue = Issue("second_opinion", WARN, "POSSIBLE_WRONG_CLASS", stem,
                              "Box khớp vị trí nhưng khác lớp với model", extra={"conf": conf, "iou": best_overlap})
            else:
                continue
            issues.append(issue)

        for line, _, _ in labels:
            best_overlap = best_fp_ious.get(line, -1.0)
            if best_overlap < iou_missing:
                issues.append(Issue("second_opinion", WARN, "POSSIBLE_FALSE_POS", stem,
                                    "Box nhãn không khớp dự đoán nào", line, extra={"iou": max(0.0, best_overlap)}))

    return issues
