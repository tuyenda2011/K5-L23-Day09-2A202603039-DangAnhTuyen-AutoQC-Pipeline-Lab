"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from collections import defaultdict

from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line


def run(ds, cfg):
    thresholds = cfg["label_format"]
    overflow_tol = thresholds["overflow_tol"]
    dup_box_iou = thresholds["dup_box_iou"]
    min_box_px = thresholds["min_box_px"]
    max_box_frac = thresholds["max_box_frac"]
    class_count = len(ds.classes)
    issues = []

    for label in ds.label_files():
        stem = label.stem
        lines = ds.read_label_lines(stem)
        if not lines:
            continue
        size = ds.image_size(stem)
        boxes_by_class = defaultdict(list)

        for line, text in lines:
            try:
                class_id, cx, cy, width, height = parse_yolo_line(text)
            except (ValueError, OverflowError) as exc:
                issues.append(Issue("label_format", ERROR, "BAD_FORMAT", stem, str(exc), line))
                continue
            if not 0 <= class_id < class_count:
                issues.append(Issue("label_format", ERROR, "BAD_CLASS_ID", stem, f"ID lớp ngoài phạm vi: {class_id}", line))
                continue
            if width <= 0 or height <= 0:
                issues.append(Issue("label_format", ERROR, "BOX_ZERO", stem, "chiều rộng hoặc chiều cao không dương", line))
                continue

            left, right = cx - width / 2, cx + width / 2
            top, bottom = cy - height / 2, cy + height / 2
            if min(left, top) < -overflow_tol or max(right, bottom) > 1 + overflow_tol:
                overflow = max(-left, -top, right - 1, bottom - 1)
                issues.append(Issue("label_format", ERROR, "BOX_OUT_OF_IMAGE", stem,
                                    "box vượt biên ảnh", line, extra={"overflow": overflow}))

            box = (cx, cy, width, height)
            previous_boxes = boxes_by_class[class_id]
            if any(iou_xywh(box, previous) > dup_box_iou for previous in previous_boxes):
                issues.append(Issue("label_format", ERROR, "DUP_BOX", stem, "box trùng dòng trước cùng lớp", line))
            previous_boxes.append(box)

            if size is not None:
                image_width, image_height = size
                if min(width * image_width, height * image_height) < min_box_px:
                    issues.append(Issue("label_format", WARN, "BOX_TINY", stem, "cạnh ngắn của box dưới ngưỡng", line))
            if width * height > max_box_frac:
                issues.append(Issue("label_format", WARN, "BOX_HUGE", stem, "diện tích box vượt ngưỡng", line))

    return issues
