"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict

import yaml

from ..common import ERROR, ROOT, parse_yolo_line


DROP_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
REMOVE_CODES = {"LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}


def _change(image, line, action, before, after):
    return dict(image=image, line=line, action=action, before=before, after=after)


def _clip_box(text):
    try:
        class_id, cx, cy, width, height = parse_yolo_line(text)
    except (ValueError, OverflowError):
        return None

    left, right = cx - width / 2, cx + width / 2
    top, bottom = cy - height / 2, cy + height / 2
    if width <= 0 or height <= 0:
        return None
    if 0 <= left and right <= 1 and 0 <= top and bottom <= 1:
        return text

    left, right = max(0, left), min(1, right)
    top, bottom = max(0, top), min(1, bottom)
    if left >= right or top >= bottom:
        return None
    return f"{class_id} {(left + right) / 2} {(top + bottom) / 2} {right - left} {bottom - top}"


def _fix_lines(path, actions):
    with path.open(encoding="utf-8", errors="surrogateescape", newline="") as label:
        original = label.readlines()

    changes, updated = [], []
    for line, raw in enumerate(original, 1):
        action = actions.get(line)
        if not action or not raw.strip():
            updated.append(raw)
            continue

        before = raw.rstrip("\r\n")
        after = _clip_box(before) if action == "clip_box" else None
        if after is None:
            changes.append(_change(path.stem, line, "drop_line", before, ""))
        elif before == after:
            updated.append(raw)
        else:
            updated.append(after + raw[len(before):])
            changes.append(_change(path.stem, line, "clip_box", before, after))

    if changes:
        with path.open("w", encoding="utf-8", errors="surrogateescape", newline="") as label:
            label.writelines(updated)
        # The audit CSV uses UTF-8 and must also handle malformed label bytes.
        for change in changes:
            change["before"] = change["before"].encode("utf-8", "surrogateescape").decode("utf-8", "replace")
    return changes


def _rename_classes(path, classes):
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None
    if data is None:
        data = {}
    before = data.get("names")
    if before == classes or before == dict(enumerate(classes)):
        return None
    data["names"] = classes
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return _change(path.name, None, "rename_classes", str(before), str(classes))


def fix(ds, issues, cfg):
    if ds.root.resolve().is_relative_to((ROOT / "data" / "raw").resolve()):
        raise ValueError("Autofix chỉ được chạy trên bản làm việc của dataset")

    removals, missing_labels = set(), set()
    line_actions = defaultdict(dict)
    rename_classes = False
    for issue in issues:
        if issue.severity != ERROR:
            continue
        stem, code, line = issue.image, issue.code, issue.line
        if code in REMOVE_CODES or code.startswith("DUP_IMAGE_"):
            removals.add(stem)
        elif code == "MISSING_LABEL_FILE":
            missing_labels.add(stem)
        elif code == "BAD_CLASS_NAME":
            rename_classes = True
        elif line is not None:
            if code in DROP_CODES:
                line_actions[stem][line] = "drop_line"
            elif code == "BOX_OUT_OF_IMAGE":
                line_actions[stem].setdefault(line, "clip_box")

    changes = []
    if removals or missing_labels or line_actions:
        labels = {path.stem: path for path in ds.label_files()}
    if removals or missing_labels:
        images = defaultdict(list)
        for path in ds.image_files():
            images[path.stem].append(path)
        for stem in sorted(removals):
            paths = images.pop(stem, [])
            if stem in labels:
                paths.append(labels.pop(stem))
            if paths:
                for path in paths:
                    path.unlink()
                changes.append(_change(stem, None, "remove_image", ", ".join(path.name for path in paths), ""))
        for stem in sorted(missing_labels - removals):
            if stem in images and stem not in labels:
                changes.append(_change(stem, None, "needs_label", "(không có file)", "chuyển người gán"))

    for stem in sorted(line_actions.keys() - removals):
        if stem in labels:
            changes.extend(_fix_lines(labels[stem], line_actions[stem]))

    if rename_classes:
        change = _rename_classes(ds.yaml_path, cfg["classes"])
        if change is not None:
            changes.append(change)
    return changes
