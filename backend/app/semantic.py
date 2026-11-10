import re
from difflib import unified_diff
from pathlib import Path
import fitz


def extract_pdf(path: Path):
    try:
        with fitz.open(path) as doc:
            return {
                "text": "\n".join(page.get_text("text") for page in doc),
                "page_count": len(doc),
                "metadata": {k: v for k, v in (doc.metadata or {}).items() if v},
            }
    except Exception as exc:
        raise ValueError(f"Could not read PDF: {exc}") from exc


def clean_lines(text):
    return [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]


def numeric_tokens(text):
    return re.findall(
        r"(?<![A-Za-z])(?:[$€£₹]\s*)?-?\d[\d,]*(?:\.\d{1,2})?(?![A-Za-z])",
        text,
    )


def compare_pdfs(original_path: Path, candidate_path: Path):
    old, new = extract_pdf(original_path), extract_pdf(candidate_path)
    old_lines, new_lines = clean_lines(old["text"]), clean_lines(new["text"])
    diff = list(unified_diff(old_lines, new_lines, fromfile="collected", tofile="uploaded", lineterm=""))

    old_nums, new_nums = numeric_tokens(old["text"]), numeric_tokens(new["text"])
    changes = []
    for i, (a, b) in enumerate(zip(old_nums, new_nums)):
        if a != b:
            changes.append({"position": i + 1, "original": a, "uploaded": b})
    if len(old_nums) != len(new_nums):
        changes.append({
            "note": "Numeric token count differs; inspect text diff.",
            "original_count": len(old_nums),
            "uploaded_count": len(new_nums),
        })

    metadata_changes = [
        {"field": key, "original": old["metadata"].get(key), "uploaded": new["metadata"].get(key)}
        for key in sorted(set(old["metadata"]) | set(new["metadata"]))
        if old["metadata"].get(key) != new["metadata"].get(key)
    ]
    text_changed = old_lines != new_lines

    if changes:
        classification, severity = "SUSPICIOUS_CONTENT_CHANGE", "HIGH"
        explanation = "Numeric tokens differ. Review surrounding text and source evidence; this is not proof of fraud."
    elif text_changed:
        classification, severity = "CONTENT_CHANGE_REVIEW", "MEDIUM"
        explanation = "Extracted PDF text differs. Review the line-level diff to determine its meaning."
    elif metadata_changes or old["page_count"] != new["page_count"]:
        classification, severity = "METADATA_OR_STRUCTURE_ONLY", "LOW"
        explanation = "Extracted text is unchanged, but metadata or page count differs; this may be routine re-saving."
    else:
        classification, severity = "NO_SEMANTIC_CHANGE_DETECTED", "LOW"
        explanation = "No difference detected in extracted text, page count or available metadata."

    return {
        "classification": classification,
        "severity": severity,
        "explanation": explanation,
        "page_count": {"original": old["page_count"], "uploaded": new["page_count"]},
        "text_changed": text_changed,
        "number_changes": changes,
        "metadata_changes": metadata_changes,
        "text_diff": diff[:100],
        "limitations": [
            "This prototype compares extractable PDF text and metadata; it does not yet compare rendered pixels, embedded images, signatures or OCR-only content.",
            "Numeric token pairing is positional and may be noisy if content is inserted or removed.",
            "This is an investigative triage aid, not a fraud finding or legal conclusion.",
        ],
    }
