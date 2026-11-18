"""BƯỚC 4 — Cửa chặn: quyết định Release / Hold / Rework.   ★

Test:  pytest tests/test_gate.py -q

Cây quyết định Day 07 (slide Day 09: "Lỗi bắt buộc chặn pipeline; lỗi cảnh báo chuyển người xem"):

  còn ≥ 1 lỗi bắt buộc (severity ERROR)                          -> "Rework"
  không còn lỗi bắt buộc, nhưng tỉ lệ ẢNH còn cảnh báo
      >= cfg["gate"]["warn_ratio_hold"]                          -> "Hold"
  còn lại                                                        -> "Release"

Tỉ lệ cảnh báo = (số ẢNH khác nhau có ≥ 1 cảnh báo) / (tổng số ảnh).  Chú ý:
- chỉ đếm issue có `image` nằm trong `image_stems` (bỏ "<dataset>", "data.yaml");
- bỏ qua ảnh nằm trong `reviewed` (người đã xem, cảnh báo của ảnh đó coi như đã xử lý) — nhưng LỖI BẮT BUỘC thì không bao giờ được bỏ qua;
- mẫu số là số ảnh, không phải số issue.

Trả về dict: decision, n_errors, n_warn_images, n_images, warn_ratio (làm tròn 4 chữ số), reasons (list[str], giải thích bằng tiếng Việt, có số liệu).
"""
from ..common import ERROR, WARN


def decide(issues, image_stems, cfg, reviewed=frozenset()):
    stems = set(image_stems)
    threshold = cfg["gate"]["warn_ratio_hold"]
    n_errors = 0
    warned_stems = set()

    for issue in issues:
        if issue.severity == ERROR:
            n_errors += 1
        elif issue.severity == WARN and issue.image in stems:
            warned_stems.add(issue.image)

    warned_stems.difference_update(reviewed)
    n_images = len(stems)
    n_warn_images = len(warned_stems)
    warn_ratio = n_warn_images / n_images if n_images else 0.0
    warning_summary = f"{n_warn_images}/{n_images} ảnh còn cảnh báo ({warn_ratio:.4%})"

    if n_errors:
        decision = "Rework"
        reason = f"Còn {n_errors} lỗi bắt buộc."
    elif warn_ratio >= threshold:
        decision = "Hold"
        reason = f"{warning_summary}, đạt hoặc vượt ngưỡng {threshold:.4%}."
    else:
        decision = "Release"
        reason = f"Có 0 lỗi bắt buộc và {warning_summary}, dưới ngưỡng {threshold:.4%}."

    return {
        "decision": decision,
        "n_errors": n_errors,
        "n_warn_images": n_warn_images,
        "n_images": n_images,
        "warn_ratio": round(warn_ratio, 4),
        "reasons": [reason],
    }
