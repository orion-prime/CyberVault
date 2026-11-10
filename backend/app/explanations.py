from datetime import datetime, timezone


def generate_forensic_explanation(analysis: dict) -> dict:
    classification = analysis.get("classification", "UNCLASSIFIED")
    severity = analysis.get("severity", "UNKNOWN")
    number_changes = analysis.get("number_changes") or []
    metadata_changes = analysis.get("metadata_changes") or []
    text_diff = analysis.get("text_diff") or []

    findings = []
    recommendations = []

    if classification == "IMAGE_CONTENT_DIFFERENCE":
        findings.append({
            "type": "image_pixel_difference",
            "location": "Image pixels after common-size comparison",
            "ssim": analysis.get("similarity_ssim"),
            "changed_pixel_ratio": analysis.get("changed_pixel_ratio"),
            "mean_absolute_pixel_difference": analysis.get("mean_absolute_pixel_difference"),
            "meaning": "The candidate image differs visually from the collected image. Editing is one possible cause, but resizing, recompression, rotation or colour changes can also cause differences."
        })
        recommendations.extend([
            "Have an investigator compare the original and candidate images side by side.",
            "Inspect the changed regions and verify the image against the source camera or original CCTV export.",
            "Check the capture chain and any known export, resize or compression steps before drawing conclusions."
        ])
        summary = "The uploaded image differs at the pixel level from the collected image. The difference requires visual and source-level review; it does not establish manipulation."
    elif classification == "IMAGE_METADATA_ONLY":
        findings.append({
            "type": "image_metadata_difference",
            "location": "Image EXIF metadata or file format",
            "changed_fields": [item.get("field") for item in analysis.get("exif_changes", [])],
            "meaning": "The decoded pixels are highly similar, while available metadata or format differs."
        })
        recommendations.extend([
            "Treat metadata differences as provenance clues, not proof of image editing.",
            "Retain both files and compare capture details with the source device or CCTV system.",
            "Document any known export or conversion process."
        ])
        summary = "The image pixels are highly similar, but available metadata or format differs. This may result from routine export or conversion."
    elif classification == "IMAGE_NO_DIFFERENCE_DETECTED":
        findings.append({
            "type": "no_image_difference_detected",
            "location": "Decoded pixels and available EXIF metadata",
            "meaning": "No material difference was detected by the current image checks."
        })
        recommendations.extend([
            "Retain the result with the evidence record.",
            "For high-assurance review, verify source-device provenance and inspect any embedded or associated evidence."
        ])
        summary = "No material pixel or available EXIF metadata difference was detected by this prototype."
    elif number_changes:
        for change in number_changes:
            original = change.get("original", "not available")
            uploaded = change.get("uploaded", "not available")
            position = change.get("position")
            findings.append({
                "type": "numeric_difference",
                "location": f"Numeric token position {position}" if position else "Numeric content",
                "original_value": original,
                "uploaded_value": uploaded,
                "meaning": "A numeric value differs between the collected PDF and the uploaded PDF."
            })
        recommendations.extend([
            "Pause automated claim approval until the discrepancy is reviewed.",
            "Compare the changed amount with the original vendor invoice and supporting purchase records.",
            "Contact the document issuer through a verified channel if the amount cannot be independently confirmed."
        ])
        summary = (
            f"The uploaded PDF contains {len(number_changes)} detected numeric difference(s). "
            "At least one numeric value changed; the surrounding text should be reviewed to confirm "
            "which business field the value represents."
        )
    elif classification == "METADATA_OR_STRUCTURE_ONLY":
        findings.append({
            "type": "metadata_or_structure_difference",
            "location": "PDF metadata or page structure",
            "changed_fields": [item.get("field") for item in metadata_changes],
            "meaning": "Extracted text is unchanged, while available metadata or page count differs."
        })
        recommendations.extend([
            "Treat this as a low-priority handling difference unless other evidence indicates content alteration.",
            "If provenance matters, retain both files and compare their rendered pages and digital signatures.",
            "Record the re-save or conversion process if it is known."
        ])
        summary = (
            "The extracted PDF text is unchanged. The detected differences are limited to available "
            "metadata or page structure and may be consistent with routine re-saving or conversion."
        )
    elif classification == "CONTENT_CHANGE_REVIEW":
        findings.append({
            "type": "text_difference",
            "location": "Extracted PDF text",
            "changed_line_count": len([line for line in text_diff if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))]),
            "meaning": "Extracted text differs; the business significance has not been established."
        })
        recommendations.extend([
            "Review each added and removed text line against the original source document.",
            "Check whether the change affects claim facts, amounts, dates, parties, or policy terms.",
            "Request issuer confirmation for material changes."
        ])
        summary = "The uploaded PDF contains extracted text changes. Their meaning requires investigator review."
    else:
        findings.append({
            "type": "no_semantic_difference_detected",
            "location": "Extracted text, available metadata and page count",
            "meaning": "No semantic difference was detected by the current PDF comparison checks."
        })
        recommendations.extend([
            "Retain the verification result with the evidence record.",
            "For high-assurance review, inspect embedded images, OCR-only content, signatures and rendered pages."
        ])
        summary = "No semantic difference was detected by the current PDF comparison checks."

    if severity == "HIGH":
        priority = "URGENT_REVIEW"
    elif severity == "MEDIUM":
        priority = "INVESTIGATOR_REVIEW"
    else:
        priority = "ROUTINE_REVIEW"

    return {
        "report_title": "CyberVault Forensic Explanation",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "classification": classification,
        "severity": severity,
        "review_priority": priority,
        "summary": summary,
        "findings": findings,
        "recommendations": recommendations,
        "limitations": [
            "This explanation is generated from the comparison output and does not independently establish intent, authenticity or fraud.",
            "The current PDF engine examines extractable text, numeric tokens, available metadata and page count.",
            "Embedded images, OCR-only text, visual layout, digital signatures and external source verification are not covered by this module."
        ]
    }
