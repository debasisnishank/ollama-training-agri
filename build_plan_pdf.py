from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    PageBreak,
    Table,
    TableStyle,
    KeepTogether,
    Flowable,
)
from reportlab.pdfbase.pdfmetrics import stringWidth


ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "output" / "pdf"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT = OUT_DIR / "agriculture_rag_plan_and_procedure.pdf"


NAVY = colors.HexColor("#163A5F")
BLUE = colors.HexColor("#2D6A9F")
TEAL = colors.HexColor("#197C7C")
ORANGE = colors.HexColor("#D9782A")
PALE_BLUE = colors.HexColor("#EAF2F8")
PALE_TEAL = colors.HexColor("#E8F5F3")
PALE_ORANGE = colors.HexColor("#FFF1E5")
LIGHT_GRAY = colors.HexColor("#F3F5F7")
MID_GRAY = colors.HexColor("#D7DEE5")
TEXT = colors.HexColor("#263238")
MUTED = colors.HexColor("#5F6B73")


styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    name="CoverTitle", parent=styles["Title"], fontName="Helvetica-Bold",
    fontSize=25, leading=30, textColor=NAVY, alignment=TA_LEFT,
    spaceAfter=10,
))
styles.add(ParagraphStyle(
    name="CoverSubtitle", parent=styles["Normal"], fontName="Helvetica",
    fontSize=12, leading=18, textColor=MUTED, alignment=TA_LEFT,
    spaceAfter=5,
))
styles.add(ParagraphStyle(
    name="Section", parent=styles["Heading1"], fontName="Helvetica-Bold",
    fontSize=16, leading=21, textColor=NAVY, spaceBefore=4, spaceAfter=9,
))
styles.add(ParagraphStyle(
    name="Subsection", parent=styles["Heading2"], fontName="Helvetica-Bold",
    fontSize=11.5, leading=15, textColor=BLUE, spaceBefore=8, spaceAfter=5,
))
styles.add(ParagraphStyle(
    name="Body2", parent=styles["BodyText"], fontName="Helvetica",
    fontSize=9.6, leading=14, textColor=TEXT, spaceAfter=6,
))
styles.add(ParagraphStyle(
    name="Small", parent=styles["BodyText"], fontName="Helvetica",
    fontSize=8.3, leading=11, textColor=MUTED, spaceAfter=4,
))
styles.add(ParagraphStyle(
    name="Bullet2", parent=styles["BodyText"], fontName="Helvetica",
    fontSize=9.4, leading=13.5, leftIndent=13, firstLineIndent=-8,
    bulletIndent=0, textColor=TEXT, spaceAfter=3,
))
styles.add(ParagraphStyle(
    name="Callout", parent=styles["BodyText"], fontName="Helvetica-Bold",
    fontSize=10.2, leading=14, textColor=NAVY, spaceAfter=0,
))
styles.add(ParagraphStyle(
    name="TableHead", parent=styles["BodyText"], fontName="Helvetica-Bold",
    fontSize=8.2, leading=10, textColor=colors.white,
))
styles.add(ParagraphStyle(
    name="TableBody", parent=styles["BodyText"], fontName="Helvetica",
    fontSize=7.8, leading=10, textColor=TEXT,
))
styles.add(ParagraphStyle(
    name="TableBodySmall", parent=styles["BodyText"], fontName="Helvetica",
    fontSize=7.2, leading=9, textColor=TEXT,
))


def P(text, style="Body2"):
    return Paragraph(text, styles[style])


def bullet(text):
    return Paragraph("- " + text, styles["Bullet2"])


def table(data, widths, header=True, small=False, zebra=True):
    converted = []
    body_style = "TableBodySmall" if small else "TableBody"
    for r, row in enumerate(data):
        converted.append([
            Paragraph(str(cell), styles["TableHead" if header and r == 0 else body_style])
            for cell in row
        ])
    ts = [
        ("GRID", (0, 0), (-1, -1), 0.35, MID_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        ts.append(("BACKGROUND", (0, 0), (-1, 0), NAVY))
    if zebra:
        start = 1 if header else 0
        for r in range(start, len(data)):
            if (r - start) % 2 == 1:
                ts.append(("BACKGROUND", (0, r), (-1, r), LIGHT_GRAY))
    t = Table(converted, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    t.setStyle(TableStyle(ts))
    return t


class ArchitectureDiagram(Flowable):
    def __init__(self, width=170 * mm, height=56 * mm):
        super().__init__()
        self.width = width
        self.height = height

    def draw_box(self, c, x, y, w, h, title, lines, fill, stroke):
        c.setFillColor(fill)
        c.setStrokeColor(stroke)
        c.roundRect(x, y, w, h, 6, stroke=1, fill=1)
        c.setFillColor(stroke)
        c.setFont("Helvetica-Bold", 8.3)
        c.drawString(x + 7, y + h - 14, title)
        c.setFillColor(TEXT)
        c.setFont("Helvetica", 7.2)
        for i, line in enumerate(lines):
            c.drawString(x + 7, y + h - 27 - (i * 10), line)

    def arrow(self, c, x1, y1, x2, y2):
        c.setStrokeColor(MUTED)
        c.setLineWidth(1.1)
        c.line(x1, y1, x2, y2)
        c.line(x2, y2, x2 - 4, y2 + 2.5)
        c.line(x2, y2, x2 - 4, y2 - 2.5)

    def draw(self):
        c = self.canv
        w = 41 * mm
        h = 28 * mm
        gap = 7 * mm
        y = 18 * mm
        x1 = 2 * mm
        x2 = x1 + w + gap
        x3 = x2 + w + gap
        x4 = x3 + w + gap
        self.draw_box(c, x1, y, w, h, "Sources", ["PMFBY", "ICRISAT", "APEDA", "Local files"], PALE_ORANGE, ORANGE)
        self.draw_box(c, x2, y, w, h, "Ingestion", ["HTML / API", "XLSX / DOCX", "Snapshots", "Provenance"], PALE_BLUE, BLUE)
        self.draw_box(c, x3, y, w, h, "Knowledge stores", ["DuckDB / Parquet", "Vector index", "Metadata", "Quality flags"], PALE_TEAL, TEAL)
        self.draw_box(c, x4, y, w, h, "Ollama", ["Question router", "SQL tool", "RAG tool", "Cited answer"], PALE_BLUE, NAVY)
        mid = y + h / 2
        self.arrow(c, x1 + w, mid, x2, mid)
        self.arrow(c, x2 + w, mid, x3, mid)
        self.arrow(c, x3 + w, mid, x4, mid)


class NumberedStep(Flowable):
    def __init__(self, number, title, body, width=170 * mm):
        super().__init__()
        self.number = str(number)
        self.title = title
        self.body = body
        self.width = width
        self.height = 19 * mm

    def draw(self):
        c = self.canv
        c.setFillColor(PALE_BLUE)
        c.setStrokeColor(MID_GRAY)
        c.roundRect(0, 0, self.width, self.height, 5, stroke=1, fill=1)
        c.setFillColor(NAVY)
        c.circle(10 * mm, self.height - 9.5 * mm, 5.5 * mm, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(10 * mm, self.height - 12 * mm, self.number)
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 9.2)
        c.drawString(19 * mm, self.height - 8 * mm, self.title)
        body = Paragraph(self.body, styles["TableBodySmall"])
        body.wrapOn(c, self.width - 25 * mm, self.height - 15 * mm)
        body.drawOn(c, 19 * mm, 2 * mm)


class PlanDocTemplate(BaseDocTemplate):
    def __init__(self, filename, **kwargs):
        super().__init__(filename, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                         topMargin=18 * mm, bottomMargin=17 * mm, **kwargs)
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height,
                      id="normal", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates([PageTemplate(id="main", frames=frame, onPage=self.draw_page)])

    def draw_page(self, canvas, doc):
        canvas.saveState()
        if doc.page > 1:
            canvas.setStrokeColor(MID_GRAY)
            canvas.setLineWidth(0.5)
            canvas.line(doc.leftMargin, A4[1] - 12 * mm, A4[0] - doc.rightMargin, A4[1] - 12 * mm)
            canvas.setFillColor(MUTED)
            canvas.setFont("Helvetica", 7.5)
            canvas.drawString(doc.leftMargin, A4[1] - 9 * mm, "Agriculture RAG and Local Model Plan")
        canvas.setStrokeColor(MID_GRAY)
        canvas.setLineWidth(0.5)
        canvas.line(doc.leftMargin, 11 * mm, A4[0] - doc.rightMargin, 11 * mm)
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(doc.leftMargin, 7 * mm, "Prepared 29 October 2026")
        canvas.drawRightString(A4[0] - doc.rightMargin, 7 * mm, f"Page {doc.page}")
        canvas.restoreState()


story = []

# Cover
story.append(Spacer(1, 18 * mm))
story.append(P("Agriculture RAG and Local Model Plan", "CoverTitle"))
story.append(P("Plan and operating procedure for building a local agriculture knowledge base with Ollama or LM Studio", "CoverSubtitle"))
story.append(Spacer(1, 9 * mm))
cover_table = Table([
    [P("Objective", "Callout"), P("Create a source-backed agricultural assistant that answers exact numerical questions through structured queries and explains schemes, agronomy and data definitions through retrieval-augmented generation.", "Body2")],
    [P("Primary hardware", "Callout"), P("DGX Spark-class system with 128 GB unified memory and approximately 2 TB storage for larger local models and fine-tuning; the MacBook Air M5 with 32 GB memory remains suitable for 7B to 14B model development and inference.", "Body2")],
    [P("Initial scope", "Callout"), P("PMFBY, ICRISAT, APEDA, the Dharwad and Madurai workbooks, and the local agriculture source assessment.", "Body2")],
], colWidths=[34 * mm, 126 * mm])
cover_table.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (0, -1), PALE_BLUE),
    ("BACKGROUND", (1, 0), (1, -1), colors.white),
    ("BOX", (0, 0), (-1, -1), 0.6, MID_GRAY),
    ("INNERGRID", (0, 0), (-1, -1), 0.35, MID_GRAY),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("LEFTPADDING", (0, 0), (-1, -1), 7),
    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ("TOPPADDING", (0, 0), (-1, -1), 7),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
]))
story.append(cover_table)
story.append(Spacer(1, 14 * mm))
story.append(P("Decision", "Section"))
story.append(P("Start with a hybrid RAG system. Keep changing agricultural statistics in a structured database, keep policies and explanations in a vector index, and use the local model to route questions and explain retrieved evidence. Fine-tuning is a later optimization, not the first ingestion step.", "Body2"))
story.append(Spacer(1, 5 * mm))
story.append(P("This procedure is designed for a local-first deployment. It can run on the Mac during development and move to the DGX Spark-class system for larger models, fine-tuning and shared access.", "Small"))
story.append(PageBreak())

# 1
story.append(P("1. Goals and boundaries", "Section"))
story.append(P("The first release should answer agricultural questions with traceable evidence. It should distinguish facts from interpretations and should never invent a numerical value when the source is missing or ambiguous.", "Body2"))
story.append(P("In scope", "Subsection"))
for t in [
    "Village, taluk, district and state-level agriculture records.",
    "NDVI, rainfall, soil moisture, acreage, production and crop-health categories.",
    "PMFBY scheme, insurance-unit, notification and historical-yield information where officially accessible.",
    "ICRISAT data catalogues, district-level data and linked datasets.",
    "APEDA India production and crop-category data.",
    "Source citations, retrieval timestamps, units and quality flags.",
]:
    story.append(bullet(t))
story.append(P("Out of scope for the first release", "Subsection"))
for t in [
    "Full pretraining of a language model from scratch.",
    "Treating vector similarity as the authority for exact historical numbers.",
    "All-India ingestion before the first state and district workflows are validated.",
    "Unsupervised fine-tuning directly on raw spreadsheets or scraped HTML.",
]:
    story.append(bullet(t))

story.append(P("Current assets", "Subsection"))
assets = [
    ["Asset", "Role in the project", "Observed scope"],
    ["Dharwad workbook", "Historical analytical records", "12 sheets; 2017-2022 NDVI, rainfall, village acreage and stressed-village views"],
    ["Madurai workbook", "Current crop-health and weather records", "29 sheets; village paddy acreage, NDVI health, rainfall and soil moisture"],
    ["Source assessment DOCX", "Architecture and source hierarchy", "Recommends structured storage for numerical records and vector RAG for narrative knowledge"],
]
story.append(table(assets, [38 * mm, 48 * mm, 74 * mm], small=True))
story.append(PageBreak())

# 2
story.append(P("2. Target architecture", "Section"))
story.append(P("The architecture separates deterministic numerical retrieval from semantic document retrieval. This is the central design decision for accuracy.", "Body2"))
story.append(ArchitectureDiagram())
story.append(Spacer(1, 3 * mm))
story.append(P("Question routing rules", "Subsection"))
rules = [
    ["Question type", "Primary tool", "Expected answer behavior"],
    ["Exact value or comparison", "SQL / DuckDB", "Return value, unit, geography, period and source"],
    ["Policy or scheme explanation", "Vector RAG", "Retrieve authoritative passages and explain them"],
    ["Trend or diagnosis", "SQL plus RAG", "Calculate the trend, then use definitions to explain it"],
    ["Missing or conflicting evidence", "Validation path", "State the limitation and request a narrower question"],
]
story.append(table(rules, [38 * mm, 43 * mm, 79 * mm], small=True))
story.append(P("Recommended local components", "Subsection"))
for t in [
    "Model runtime: Ollama or LM Studio during Mac development; a CUDA-capable runtime on the DGX for larger models.",
    "Structured store: DuckDB and Parquet for the proof of concept; PostgreSQL when concurrent users and permissions are required.",
    "Vector store: Chroma or Qdrant for a local proof of concept; pgvector when structured and vector data should share one service.",
    "Application layer: a small Python service that handles ingestion, routing, retrieval, citations and evaluation.",
]:
    story.append(bullet(t))
story.append(PageBreak())

# 3
story.append(P("3. Source ingestion procedure", "Section"))
story.append(P("Each source must be captured as a versioned snapshot before it is transformed. Never overwrite the raw copy. Use a manifest that records URL, retrieval time, source title, checksum, file type, authority and processing status.", "Body2"))
source_rows = [
    ["Source", "Ingestion method", "Important control"],
    ["PMFBY dashboard", "Capture official API responses or downloadable reports behind the JavaScript dashboard", "Record session requirements, endpoint, parameters, season and retrieval date"],
    ["ICRISAT data resources", "Follow the linked DataVerse, GIS, forecast and district-level data resources", "Store dataset metadata, licence or access notes and original download links"],
    ["APEDA production", "Capture the India Production catalogue and product detail responses", "Preserve product category, crop name, code, year, unit and detail-page URL"],
    ["Local Excel files", "Parse each worksheet into raw tabular extracts", "Preserve workbook name, sheet name, cell range, formulas and source notes"],
    ["Local DOCX", "Extract paragraphs and tables", "Preserve headings, references and the source hierarchy"],
]
story.append(table(source_rows, [34 * mm, 83 * mm, 43 * mm], small=True))
story.append(P("Raw-data directory layout", "Subsection"))
for t in [
    "data/raw/web/pmfby/YYYY-MM-DD/",
    "data/raw/web/icrisat/YYYY-MM-DD/",
    "data/raw/web/apeda/YYYY-MM-DD/",
    "data/raw/local/workbooks/",
    "data/raw/local/documents/",
    "data/manifests/",
]:
    story.append(bullet(t))
story.append(P("Do not embed raw HTML tables as the only representation of numbers. Convert them into canonical records and retain the source page as provenance.", "Small"))
story.append(PageBreak())

# 4
story.append(P("4. Data normalization and quality control", "Section"))
story.append(P("The normalization stage converts different source layouts into one canonical model while retaining original labels and source context.", "Body2"))
schema = [
    ["Field group", "Minimum fields"],
    ["Geography", "state, district, taluk_or_tehsil, village, geography_level, source_code"],
    ["Agriculture", "crop, crop_standard_name, season, year, date"],
    ["Observation", "metric, value, unit, aggregation, estimate_type"],
    ["Provenance", "source_id, source_url, source_file, worksheet, cell_range, retrieved_at"],
    ["Quality", "revision_status, validation_status, missing_reason, confidence_note"],
]
story.append(table(schema, [38 * mm, 122 * mm], small=True))
story.append(P("Required validation checks", "Subsection"))
checks = [
    ["Check", "Procedure", "Failure action"],
    ["Blank versus zero", "Keep missing, zero and not-applicable as different states", "Do not silently convert blanks to zero"],
    ["Units", "Normalize acres, hectares, millimetres and yield units", "Store original unit and converted unit"],
    ["Dates", "Convert Excel serial dates and text dates to ISO dates", "Flag ambiguous dates for review"],
    ["Geography", "Build crosswalks for current and historical administrative names", "Prevent false trends caused by boundary changes"],
    ["Duplicates", "Check repeated village-crop-period keys", "Retain revision information and resolve precedence"],
    ["Workbook labels", "Compare sheet titles with data content", "Flag mismatches, such as district-name inconsistencies"],
]
story.append(table(checks, [33 * mm, 75 * mm, 52 * mm], small=True))
story.append(P("Quality gates", "Subsection"))
for t in [
    "No record enters the production index without a source identifier.",
    "Every numerical answer must be traceable to source, geography, period and unit.",
    "Conflicting records remain visible as revisions or conflicts; they are not silently averaged.",
    "The original value and any transformed value are both retained.",
]:
    story.append(bullet(t))
story.append(PageBreak())

# 5
story.append(P("5. Indexing and retrieval procedure", "Section"))
story.append(P("Use separate pipelines for structured facts and narrative documents.", "Body2"))
story.append(P("Structured fact pipeline", "Subsection"))
for t in [
    "Load normalized records into DuckDB or PostgreSQL.",
    "Create indexes on state, district, taluk, village, crop, season, year and metric.",
    "Expose safe parameterized query functions rather than unrestricted SQL generation.",
    "Return a compact evidence table to the model with the source metadata attached.",
]:
    story.append(bullet(t))
story.append(P("Document RAG pipeline", "Subsection"))
for t in [
    "Convert source pages, policy documents, scheme guidelines and definitions into clean text.",
    "Chunk by heading and semantic section rather than arbitrary spreadsheet row count.",
    "Attach metadata for source, authority, crop, scheme, geography, language and effective date.",
    "Create embeddings locally and store the text chunk plus source citation.",
    "Use retrieval filters before similarity search when the question names a crop, state, year or scheme.",
]:
    story.append(bullet(t))
story.append(P("Answer format", "Subsection"))
answer = [
    ["Answer component", "Required content"],
    ["Direct answer", "A concise sentence or calculated result"],
    ["Evidence", "Rows or passages used to support the answer"],
    ["Context", "Definition, comparison or interpretation when needed"],
    ["Citation", "Source name, URL or local file, period, geography and unit"],
    ["Limitation", "Missing data, conflicting revisions or unsupported inference"],
]
story.append(table(answer, [38 * mm, 122 * mm], small=True))
story.append(PageBreak())

# 6
story.append(P("6. Local model procedure", "Section"))
story.append(P("The MacBook Air M5 with 32 GB unified memory is sufficient for the first development cycle. Use a quantized 7B or 8B model for fast iteration and test a 14B model for stronger reasoning. The DGX Spark-class device can host larger models and fine-tuning workloads.", "Body2"))
models = [
    ["Workload", "MacBook Air M5, 32 GB", "DGX Spark-class, 128 GB"],
    ["7B or 8B quantized inference", "Comfortable", "Comfortable"],
    ["14B quantized inference", "Feasible; slower with long context", "Comfortable"],
    ["32B quantized inference", "Not the first target", "Practical target"],
    ["LoRA fine-tuning", "Start with 7B; 14B is constrained", "7B-70B depending on setup"],
    ["Full pretraining", "Not practical", "Not the initial objective"],
]
story.append(table(models, [49 * mm, 56 * mm, 55 * mm], small=True))
story.append(P("Runtime setup procedure", "Subsection"))
for t in [
    "Choose one primary runtime for reproducibility. Use Ollama for a simple local API or LM Studio for a desktop-first workflow.",
    "Download one instruct model and one embedding model. Keep model names and quantization in the project manifest.",
    "Set the model context length conservatively during the first evaluation.",
    "Start the RAG service locally and test retrieval before testing answer quality.",
    "Move the same ingestion and evaluation code to the DGX rather than rebuilding the project there.",
]:
    story.append(bullet(t))
story.append(P("Operational note", "Subsection"))
story.append(P("The Mac currently has LM Studio installed, while the Ollama command was not detected during the initial device check. The plan can proceed with LM Studio first or with Ollama after installation.", "Body2"))
story.append(PageBreak())

# 7
story.append(P("7. Fine-tuning procedure", "Section"))
story.append(P("Fine-tuning should be considered only after the RAG system has a measured failure pattern. It is appropriate for behavior and formatting, not for storing constantly changing agricultural facts.", "Body2"))
fine = [
    ["Step", "Procedure", "Exit condition"],
    ["1. Collect failures", "Save questions where routing, retrieval or answer formatting failed", "At least 50 labelled failures"],
    ["2. Write examples", "Create instruction, evidence, answer and citation examples", "Examples reviewed for numeric correctness"],
    ["3. Split data", "Use train, validation and held-out test sets by question family", "No leakage between near-duplicate questions"],
    ["4. Train adapter", "Run LoRA/QLoRA on the DGX; start with a small model", "Validation loss and answer quality improve"],
    ["5. Compare", "Compare base model plus RAG against tuned model plus RAG", "Held-out accuracy improves without citation loss"],
    ["6. Deploy", "Keep the adapter, base model, prompt and dataset versioned", "Rollback path is tested"],
]
story.append(table(fine, [25 * mm, 91 * mm, 44 * mm], small=True))
story.append(P("Do not fine-tune yet if", "Subsection"))
for t in [
    "The main problem is missing data connectors.",
    "The answer contains the wrong number because the database schema is incomplete.",
    "The model has no source citation because the retrieval response does not include provenance.",
    "The source itself is inconsistent or not authoritative.",
]:
    story.append(bullet(t))
story.append(PageBreak())

# 8
story.append(P("8. Evaluation procedure", "Section"))
story.append(P("Evaluation must test both retrieval and answer correctness. A fluent response is not a successful response if the number, unit, year or geography is wrong.", "Body2"))
eval_rows = [
    ["Evaluation area", "Example measure", "Pass condition"],
    ["Structured accuracy", "Acreage, rainfall, NDVI, soil moisture", "Exact or tolerance-based match to the source record"],
    ["Retrieval recall", "Relevant policy or definition passage", "Required source appears in top-k results"],
    ["Citation completeness", "Source, period, geography and unit", "All required metadata is present"],
    ["Abstention", "Unsupported question", "Model says evidence is unavailable"],
    ["Boundary handling", "Historical versus current district", "Correct geography version is identified"],
    ["Regression", "Previously passing questions", "No degradation after ingestion or model changes"],
]
story.append(table(eval_rows, [41 * mm, 68 * mm, 51 * mm], small=True))
story.append(P("Initial golden test set", "Subsection"))
for t in [
    "10 exact numerical queries from the Dharwad workbook.",
    "10 exact numerical queries from the Madurai workbook.",
    "10 source-definition questions about NDVI, rainfall and soil moisture.",
    "10 PMFBY policy and scheme questions.",
    "10 APEDA and ICRISAT source-navigation questions.",
    "10 deliberately unsupported or ambiguous questions.",
]:
    story.append(bullet(t))
story.append(P("The first acceptance target is 90 percent exactness on the structured numerical set, with zero fabricated citations on unsupported questions.", "Callout"))
story.append(PageBreak())

# 9
story.append(P("9. Implementation schedule", "Section"))
schedule = [
    ["Stage", "Work", "Deliverable"],
    ["Stage 0", "Freeze scope, define questions and create the source manifest", "Project specification and golden-question list"],
    ["Stage 1", "Extract local workbooks and DOCX", "Raw snapshots and normalized tables"],
    ["Stage 2", "Implement PMFBY, ICRISAT and APEDA connectors", "Repeatable source ingestion jobs"],
    ["Stage 3", "Build DuckDB and vector indexes", "Local knowledge base"],
    ["Stage 4", "Add question router and citation-aware answer prompt", "Working local RAG assistant"],
    ["Stage 5", "Run evaluation and repair schema or retrieval issues", "Evaluation report and corrections"],
    ["Stage 6", "Move to DGX and test larger models", "Local service for larger-model inference"],
    ["Stage 7", "Optional LoRA fine-tuning", "Versioned adapter only if justified by failures"],
]
story.append(table(schedule, [27 * mm, 86 * mm, 47 * mm], small=True))
story.append(P("Recommended first milestone", "Subsection"))
story.append(P("Complete one end-to-end workflow for Madurai: ask a village or taluk question, retrieve an exact row from DuckDB, add the relevant NDVI definition from the document index, and return a cited answer. Once that works, repeat the pattern for Dharwad and then add the external sources.", "Body2"))

story.append(P("10. Operational checklist", "Section"))
checklist = [
    ["Before ingestion", "Source URL or file recorded; authority known; retrieval date recorded; raw copy preserved"],
    ["Before indexing", "Schema mapped; units checked; blanks and zeros separated; geography reviewed; duplicates flagged"],
    ["Before answering", "Question type routed; source filters applied; evidence returned with metadata"],
    ["Before release", "Golden set passes; citations render correctly; unsupported questions abstain; rollback tested"],
]
story.append(table(checklist, [39 * mm, 121 * mm], header=False, small=True, zebra=True))
story.append(Spacer(1, 6 * mm))
story.append(P("Final operating principle", "Subsection"))
story.append(P("The model explains the evidence. The database owns the number. The source manifest owns the provenance. The evaluation set owns the release decision.", "Callout"))
story.append(PageBreak())

# 11
story.append(P("11. Best-practice data onboarding SOP", "Section"))
story.append(P("Every new document or dataset should pass through the same controlled lifecycle. The goal is to make ingestion repeatable, auditable and reversible while preserving the source exactly as received.", "Body2"))
lifecycle = [
    ["Layer", "What is stored", "Rule"],
    ["Intake", "Source request, owner, authority, licence, intended use", "Reject unknown provenance or unclear usage rights"],
    ["Bronze", "Immutable original file, HTML, JSON, PDF or API response", "Never edit; record checksum and retrieval time"],
    ["Silver", "Parsed tables, cleaned text and normalized dates", "Keep original fields beside transformed fields"],
    ["Gold", "Validated canonical records with geography, crop, period and units", "Only quality-approved records enter production queries"],
    ["Index", "DuckDB facts, document chunks and embeddings", "Version the index against the gold data release"],
]
story.append(table(lifecycle, [29 * mm, 78 * mm, 53 * mm], small=True))
story.append(P("Standard procedure", "Subsection"))
for i, (title, body) in enumerate([
    ("Register", "Create a source manifest entry with source ID, owner, authority, URL or file name, access date, licence note, checksum, expected geography and expected metrics."),
    ("Preserve", "Copy the source into the raw layer. Store API payloads, downloaded files and the original document. Do not clean in place."),
    ("Profile", "Measure file type, sheet or page count, row counts, columns, null rates, date ranges, units, duplicate keys and candidate geographic levels."),
    ("Extract", "Parse tables, paragraphs and API responses into a staging representation. Keep sheet name, page number, row number or API parameters as location evidence."),
    ("Normalize", "Map column names to the canonical schema, standardize crop and geography names, convert dates and units, and preserve the source value."),
    ("Validate", "Run schema, range, uniqueness, referential, unit and reconciliation checks. Produce a machine-readable error report."),
    ("Publish", "Write only approved records to the gold tables and document chunks. Rebuild the vector index from the same release."),
    ("Evaluate", "Run the golden-question set, compare against the previous release, review failures and publish a release note."),
], start=1):
    story.append(NumberedStep(i, title, body))
story.append(PageBreak())

# 12
story.append(P("12. Format-specific cleaning rules", "Section"))
story.append(P("Different source formats fail in different ways. Use format-specific handling before applying common schema and quality checks.", "Body2"))
format_rows = [
    ["Format", "Clean and extract", "Common failure to prevent"],
    ["XLSX / XLS", "Detect header rows; resolve merged cells; preserve formulas and displayed values; convert Excel dates; separate notes from data tables", "Treating a dashboard layout or subtotal row as ordinary observations"],
    ["CSV / TSV", "Detect encoding and delimiter; validate column count; preserve leading zeros in codes; normalize null markers", "Dropping village or LGD codes because they look numeric"],
    ["DOCX / PDF", "Extract headings, paragraphs, tables and page references; OCR only when necessary; retain page or table location", "Embedding a long document without section metadata"],
    ["HTML", "Capture visible text, tables, links and retrieval timestamp; save the original HTML; record JavaScript/API dependencies", "Assuming static HTML contains dynamic dashboard data"],
    ["JSON / API", "Store raw response and request parameters; validate response schema; preserve pagination and status codes", "Mixing revisions or dropping API filters from provenance"],
    ["Geo files", "Validate CRS, geometry validity and administrative codes; keep geometry version", "Joining current boundaries to historical records without a crosswalk"],
]
story.append(table(format_rows, [28 * mm, 83 * mm, 49 * mm], small=True))
story.append(P("Canonical data contract", "Subsection"))
contract = [
    ["Field", "Required behavior"],
    ["source_id", "Stable identifier for the source snapshot or release"],
    ["geography_level", "Explicit value such as village, taluk, district or state"],
    ["geography_name and code", "Store display name and source code; never use name alone for joins"],
    ["crop_standard_name", "Controlled vocabulary plus original crop label"],
    ["period", "Year, season and exact date where available"],
    ["metric, value, unit", "Typed value, normalized unit and original unit"],
    ["estimate_type", "Observed, administrative, remote-sensing, modelled or reported"],
    ["revision_status", "Original, revised, superseded or conflicting"],
    ["evidence_location", "Worksheet and row, page and table, URL, API parameters or cell range"],
]
story.append(table(contract, [45 * mm, 115 * mm], small=True))
story.append(PageBreak())

# 13
story.append(P("13. Quality gates and release policy", "Section"))
story.append(P("A dataset is ready for the knowledge base only when it passes the gates below. Failed records remain available in quarantine for review but are excluded from production answers.", "Body2"))
gates = [
    ["Gate", "Required check", "Release decision"],
    ["Provenance", "Source, authority, retrieval date and checksum exist", "Block if missing"],
    ["Schema", "Required fields exist and types are valid", "Quarantine invalid rows"],
    ["Units", "Metric units are known and conversions are documented", "Block unknown units for numeric answers"],
    ["Geography", "Names and codes resolve through a versioned crosswalk", "Flag unresolved or changed boundaries"],
    ["Time", "Year, season and date are consistent with source scope", "Quarantine impossible or ambiguous periods"],
    ["Duplicates", "Duplicate keys are resolved by revision or explicitly retained as conflicts", "Do not silently average"],
    ["Reconciliation", "Totals agree with source control totals within defined tolerance", "Block material mismatches"],
    ["Retrieval", "Expected questions return the intended record or passage", "Block if recall or ranking regresses"],
]
story.append(table(gates, [29 * mm, 83 * mm, 48 * mm], small=True))
story.append(P("Recommended dataset release package", "Subsection"))
for t in [
    "Raw snapshot or immutable source reference.",
    "Normalized data export and schema version.",
    "Source manifest with checksum and licence note.",
    "Validation report listing passed, failed and quarantined records.",
    "Gold table or document-chunk count and index version.",
    "Golden-question evaluation results and known limitations.",
    "Release note describing additions, corrections and superseded records.",
]:
    story.append(bullet(t))
story.append(P("Do not publish a source as trusted merely because parsing succeeded. Parsing success is a technical status; authority, completeness and reconciliation are data-quality decisions.", "Callout"))
story.append(PageBreak())

# References
story.append(P("References and source notes", "Section"))
refs = [
    ["Source", "Use in this plan"],
    ["PMFBY administrator statistics dashboard - https://pmfby.gov.in/adminStatistics/dashboard", "Source for scheme and insurance statistics ingestion"],
    ["ICRISAT data resources - https://icrisat.org/resources/data/comparative-map-homepage", "Source for linked DataVerse, GIS and district-level resources"],
    ["APEDA India Production - https://agriexchange.apeda.gov.in/Production/India/Index", "Source for India production and crop catalogue ingestion"],
    ["DHARWAD_District_Historical_Analysis_2017-2022_NDVI_RAINFALL.xlsx", "Local NDVI, rainfall, acreage and stressed-village data"],
    ["Madurai_Paddy_Crop_Acreages_NDVI_Health_01-15Oct-2026_Weather_NDVI_SM.xlsx", "Local paddy acreage, NDVI health, rainfall and soil-moisture data"],
    ["India_Agriculture_Data_Sources_for_Ollama.docx", "Local source assessment and hybrid architecture recommendations"],
    ["NVIDIA DGX Spark hardware guide - https://docs.nvidia.com/dgx/dgx-spark/hardware.html", "Hardware capability reference for local inference and fine-tuning"],
]
story.append(table(refs, [78 * mm, 82 * mm], small=True))
story.append(Spacer(1, 10 * mm))
story.append(P("Prepared for the initial agriculture knowledge-base and local-model project. Review access permissions, source terms and redistribution conditions before publishing downloaded data.", "Small"))


doc = PlanDocTemplate(str(OUTPUT), title="Agriculture RAG and Local Model Plan", author="OpenAI")
doc.build(story)
print(OUTPUT)

