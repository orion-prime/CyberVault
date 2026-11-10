from io import BytesIO
from datetime import datetime, timezone
import base64
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Flowable, PageBreak, KeepTogether
)


class CachedImage(Flowable):
    """A ReportLab flowable that draws a cached ImageReader reliably."""
    def __init__(self, image_reader, max_width, max_height):
        super().__init__()
        self.image_reader = image_reader
        source_width, source_height = image_reader.getSize()
        scale = min(max_width / source_width, max_height / source_height)
        self.width = source_width * scale
        self.height = source_height * scale

    def draw(self):
        self.canv.drawImage(
            self.image_reader, 0, 0,
            width=self.width, height=self.height,
            preserveAspectRatio=True, anchor="c", mask="auto"
        )



def _decode_data_url(value):
    if not isinstance(value, str):
        return None
    match = re.match(r"^data:image/(?:png|jpeg|jpg|webp);base64,(.+)$", value, re.I | re.S)
    if not match:
        return None
    try:
        return BytesIO(base64.b64decode(match.group(1), validate=True))
    except Exception:
        return None


def _is_image_analysis(analysis):
    return (
        analysis.get("similarity_ssim") is not None
        or str(analysis.get("classification", "")).startswith("IMAGE_")
    )


def _image_limitations():
    return [
        "Pixel-level differences may result from editing, resizing, recompression, rotation, colour adjustment or other routine processing.",
        "EXIF metadata may be absent, stripped or modified and should be treated as a provenance clue rather than proof of editing.",
        "Error Level Analysis (ELA) is a JPEG-specific investigative heuristic and can produce misleading patterns.",
        "The visual previews are aligned for comparison; resizing or interpolation can introduce additional pixel differences.",
        "Automated image indicators do not independently establish intent, authenticity or fraud. Human review and source verification are required."
    ]


def _pdf_limitations():
    return [
        "The current PDF checks cover extractable text, numeric tokens, available metadata and page count.",
        "Embedded images, OCR-only content, rendered visual layout, digital signatures and external source verification may not be assessed.",
        "Automated indicators do not independently establish intent, authenticity or fraud. Human review and source verification are required."
    ]


def build_forensic_pdf(evidence: dict, analysis: dict) -> bytes:
    """Generate a modality-aware report with compact, paginated visual exhibits."""
    is_image = _is_image_analysis(analysis)
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=16*mm, leftMargin=16*mm,
        topMargin=15*mm, bottomMargin=18*mm,
        title="CyberVault Forensic Investigation Report", author="CyberVault"
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="CVTitle", parent=styles["Title"], textColor=colors.HexColor("#24366f"),
        alignment=TA_CENTER, fontSize=19, leading=23, spaceAfter=4
    ))
    styles.add(ParagraphStyle(
        name="CVSub", parent=styles["Normal"], textColor=colors.HexColor("#687696"),
        alignment=TA_CENTER, fontSize=8, leading=11, spaceAfter=10
    ))
    styles.add(ParagraphStyle(
        name="CVHead", parent=styles["Heading2"], textColor=colors.HexColor("#293b78"),
        fontSize=10.5, leading=13, spaceBefore=9, spaceAfter=5, keepWithNext=True
    ))
    styles.add(ParagraphStyle(
        name="CVBody", parent=styles["BodyText"], fontSize=8.5, leading=11.5, spaceAfter=3
    ))
    styles.add(ParagraphStyle(
        name="CVSmall", parent=styles["BodyText"], fontSize=7, leading=9,
        textColor=colors.HexColor("#687696"), spaceAfter=2
    ))
    styles.add(ParagraphStyle(
        name="CVCaption", parent=styles["BodyText"], fontSize=6.8, leading=8,
        textColor=colors.HexColor("#687696"), alignment=TA_CENTER, spaceBefore=2, spaceAfter=2
    ))
    styles.add(ParagraphStyle(
        name="CVConclusion", parent=styles["BodyText"], fontSize=8.5, leading=12,
        textColor=colors.HexColor("#293b78"), backColor=colors.HexColor("#eef2fa"),
        borderColor=colors.HexColor("#dce2ef"), borderWidth=0.5, borderPadding=7,
        spaceBefore=3, spaceAfter=5
    ))

    def safe(value):
        text = str(value if value is not None else "Not available")
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def make_table(rows, widths, first_col_shaded=True):
        table = Table(rows, colWidths=widths, repeatRows=0, hAlign="LEFT")
        commands = [
            ("GRID", (0,0), (-1,-1), 0.35, colors.HexColor("#dce2ef")),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING", (0,0), (-1,-1), 5),
            ("RIGHTPADDING", (0,0), (-1,-1), 5),
            ("TOPPADDING", (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ]
        if first_col_shaded:
            commands.append(("BACKGROUND", (0,0), (0,-1), colors.HexColor("#eef2fa")))
        table.setStyle(TableStyle(commands))
        return table

    def page_footer(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#dce2ef"))
        canvas.line(16*mm, 13*mm, A4[0]-16*mm, 13*mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#78839b"))
        canvas.drawString(16*mm, 8*mm, "CYBERVAULT  |  INVESTIGATIVE TRIAGE REPORT")
        canvas.drawRightString(A4[0]-16*mm, 8*mm, f"Page {document.page}")
        canvas.restoreState()

    explanation = analysis.get("forensic_explanation") or {}
    classification = analysis.get("classification", analysis.get("status", "Not assessed"))
    severity = analysis.get("severity", "Not assessed")
    risk_band = analysis.get("risk_band", "Not assessed")
    score = analysis.get("trust_score")
    summary = explanation.get("summary", analysis.get("explanation", "No explanation supplied."))

    story = [
        Paragraph("CYBERVAULT", styles["CVTitle"]),
        Paragraph("DIGITAL FORENSIC INVESTIGATION REPORT", styles["CVSub"]),
        Paragraph("Report generated: " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), styles["CVSmall"]),
        Paragraph("1. Evidence details", styles["CVHead"]),
    ]
    evidence_rows = [
        ["Evidence ID", f"EV-{int(evidence.get('id', 0)):04d}"],
        ["Original filename", safe(evidence.get("original_filename"))],
        ["SHA-256 baseline", safe(evidence.get("sha256"))],
        ["File size (bytes)", safe(evidence.get("size_bytes"))],
        ["Candidate filename", safe(analysis.get("filename"))],
    ]
    story.append(make_table(
        [[Paragraph(safe(a), styles["CVSmall"]), Paragraph(safe(b), styles["CVSmall"])] for a,b in evidence_rows],
        [40*mm, 126*mm]
    ))

    story.append(Paragraph("2. Analysis outcome", styles["CVHead"]))
    outcome_rows = [
        ["Analysis type", "Image comparison" if is_image else "PDF semantic comparison"],
        ["Classification", safe(classification)],
        ["Severity", safe(severity)],
        ["Trust score", safe(f"{score}/100" if score is not None else "Not calculated")],
        ["Risk band", safe(risk_band)],
    ]
    story.append(make_table(
        [[Paragraph(safe(a), styles["CVSmall"]), Paragraph(safe(b), styles["CVBody"])] for a,b in outcome_rows],
        [40*mm, 126*mm]
    ))

    story.append(Paragraph("3. Forensic explanation", styles["CVHead"]))
    story.append(Paragraph(safe(summary), styles["CVBody"]))
    for finding in explanation.get("findings", []):
        story.append(Paragraph("<b>Finding:</b> " + safe(finding.get("type", "Finding")).replace("_", " "), styles["CVBody"]))
        if finding.get("meaning"):
            story.append(Paragraph(safe(finding.get("meaning")), styles["CVBody"]))
        if finding.get("original_value") is not None or finding.get("uploaded_value") is not None:
            story.append(Paragraph("<b>Values:</b> " + safe(finding.get("original_value")) + " → " + safe(finding.get("uploaded_value")), styles["CVBody"]))
        if finding.get("changed_fields"):
            story.append(Paragraph("<b>Changed metadata fields:</b> " + safe(", ".join(map(str, finding["changed_fields"]))), styles["CVBody"]))

    if is_image:
        story.append(Paragraph("4. Image comparison metrics", styles["CVHead"]))
        dimensions = analysis.get("dimensions") or {}
        formats = analysis.get("formats") or {}
        metrics = [
            ["SSIM similarity", safe(analysis.get("similarity_ssim"))],
            ["Changed pixel ratio", safe(f"{float(analysis.get('changed_pixel_ratio', 0))*100:.2f}%")],
            ["Mean absolute pixel difference", safe(analysis.get("mean_absolute_pixel_difference"))],
            ["Original dimensions", safe(dimensions.get("original"))],
            ["Uploaded dimensions", safe(dimensions.get("uploaded"))],
            ["Original / uploaded format", safe(str(formats.get("original")) + " / " + str(formats.get("uploaded")))],
            ["JPEG ELA mean (original / uploaded)", safe(str(analysis.get("ela_mean_original")) + " / " + str(analysis.get("ela_mean_uploaded")))],
        ]
        story.append(make_table(
            [[Paragraph(safe(a), styles["CVSmall"]), Paragraph(safe(b), styles["CVBody"])] for a,b in metrics],
            [58*mm, 108*mm]
        ))
    else:
        story.append(Paragraph("4. PDF content comparison", styles["CVHead"]))
        number_changes = analysis.get("number_changes") or []
        if number_changes:
            rows = [["Position", "Original value", "Uploaded value"]]
            for item in number_changes[:25]:
                rows.append([safe(item.get("position")), safe(item.get("original")), safe(item.get("uploaded"))])
            story.append(make_table(
                [[Paragraph(str(cell), styles["CVSmall"]) for cell in row] for row in rows],
                [34*mm, 66*mm, 66*mm]
            ))
        for line in (analysis.get("text_diff") or [])[:25]:
            story.append(Paragraph(safe(line), styles["CVSmall"]))

    recommendations = explanation.get("recommendations", [])
    section_num = 5
    if is_image:
        visual = analysis.get("visual_comparison") or {}
        exhibits = [
            ("side_by_side_data_url", "Exhibit A — Original (left) and candidate (right)"),
            ("heatmap_data_url", "Exhibit B — Pixel difference heatmap"),
            ("overlay_data_url", "Exhibit C — 50/50 blended overlay"),
        ]
        valid = []
        for key, caption in exhibits:
            stream = _decode_data_url(visual.get(key))
            if stream:
                try:
                    # ImageReader eagerly reads/caches the decoded bytes. This avoids
                    # file-like streams being left at EOF between table layout and draw.
                    stream.seek(0)
                    image_reader = ImageReader(stream)
                    img = CachedImage(image_reader, max_width=52*mm, max_height=31*mm)
                    img.hAlign = "CENTER"
                    valid.append((img, Paragraph(safe(caption), styles["CVCaption"])))
                except Exception:
                    continue
        if valid:
            story.append(PageBreak())
            story.append(Paragraph("5. Visual evidence exhibits", styles["CVHead"]))
            story.append(Paragraph(
                "Comparison previews are aligned for inspection. Heatmap intensity represents pixel differences, "
                "not a manipulation verdict. Alignment or resizing may introduce additional differences.",
                styles["CVSmall"]
            ))
            # Three compact columns keep all exhibits together on one report page.
            cells = []
            for image, caption in valid:
                cells.append([image, caption])
            while len(cells) < 3:
                cells.append(["", ""])
            grid_rows = [
                [cells[0][0], cells[1][0], cells[2][0]],
                [cells[0][1], cells[1][1], cells[2][1]],
            ]
            grid = Table(grid_rows, colWidths=[55.3*mm, 55.3*mm, 55.3*mm], hAlign="LEFT")
            grid.setStyle(TableStyle([
                ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                ("ALIGN", (0,0), (-1,-1), "CENTER"),
                ("LEFTPADDING", (0,0), (-1,-1), 1),
                ("RIGHTPADDING", (0,0), (-1,-1), 1),
                ("TOPPADDING", (0,0), (-1,-1), 3),
                ("BOTTOMPADDING", (0,0), (-1,-1), 3),
            ]))
            story.append(grid)
        section_num = 6

    if recommendations:
        story.append(Paragraph(f"{section_num}. Recommended investigator actions", styles["CVHead"]))
        for idx, item in enumerate(recommendations, 1):
            story.append(Paragraph(f"{idx}. {safe(item)}", styles["CVBody"]))

    story.append(Paragraph("Investigator conclusion", styles["CVHead"]))
    conclusion = (
        "The automated checks identified differences that warrant the review priority shown in this report. "
        "The results describe observed technical differences only. An investigator should validate the source, "
        "context and handling history before reaching any conclusion about alteration or authenticity."
    )
    story.append(Paragraph(safe(conclusion), styles["CVConclusion"]))

    # Do not reuse generic explanation limitations across modalities.
    limitations = _image_limitations() if is_image else _pdf_limitations()
    story.append(Paragraph("Important limitations", styles["CVHead"]))
    for item in limitations:
        story.append(Paragraph("• " + safe(item), styles["CVSmall"]))

    story.append(Spacer(1, 5))
    story.append(Paragraph(
        "This report summarizes the supplied evidence record and current automated analysis response. "
        "Preserve original files, maintain documented chain of custody, and independently verify provenance. "
        "This report is an investigative aid, not a signed expert opinion or legal conclusion.",
        styles["CVSmall"]
    ))

    doc.build(story, onFirstPage=page_footer, onLaterPages=page_footer)
    return buffer.getvalue()
