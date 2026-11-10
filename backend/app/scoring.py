def calculate_trust_score(analysis: dict) -> dict:
    """Rule-based prototype calibrated to the two case-study examples; not a probability."""
    classification = analysis.get("classification")
    if classification == "SUSPICIOUS_CONTENT_CHANGE":
        deductions = {"suspicious_numeric_change": 78}
    elif classification == "CONTENT_CHANGE_REVIEW":
        deductions = {"unclassified_content_change": 35}
    elif classification == "METADATA_OR_STRUCTURE_ONLY":
        deductions = {"metadata_or_structure_change": 9}
    elif classification == "NO_SEMANTIC_CHANGE_DETECTED" or classification == "IMAGE_NO_DIFFERENCE_DETECTED":
        deductions = {}
    elif classification == "IMAGE_CONTENT_DIFFERENCE":
        deductions = {"image_pixel_difference_requires_review": 40}
    elif classification == "IMAGE_METADATA_ONLY":
        deductions = {"image_metadata_or_format_change": 9}
    else:
        deductions = {"unclassified_or_unavailable_analysis": 50}

    total = sum(deductions.values())
    score = max(0, min(100, 100 - total))
    band = "HIGH" if score <= 39 else "MEDIUM" if score <= 69 else "LOW"
    return {
        "trust_score": score,
        "risk_band": band,
        "score_breakdown": {
            "starting_score": 100,
            "deductions": deductions,
            "total_deduction": total,
            "method": "Rule-based prototype; PDF reference scores are calibrated to case-study examples, image scores are provisional triage rules.",
            "interpretation": "Triage indicator only; not a probability of authenticity or legal conclusion."
        }
    }
