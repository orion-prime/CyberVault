# CyberVault Phase 2
FastAPI + React/Vite prototype with SHA-256 collection/verification and PDF semantic comparison.

## Backend
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

## Frontend (second terminal)
cd frontend
npm install
npm run dev

Open http://localhost:5173. API docs: http://127.0.0.1:8000/docs

Phase 2 compares extractable PDF text, numeric tokens, metadata and page count. It is a
transparent rule-based prototype, not an AI fraud verdict. OCR, visual comparison, calibrated
Trust Score and tamper-resistant forensic audit storage are future work. Numeric token pairing
is positional and must be reviewed alongside the text diff.

## Module 3: Trust Score Engine
The semantic PDF endpoint returns a transparent rule-based score:
- Suspicious numeric content change: 22/100 (78-point deduction).
- Metadata/structure-only change: 91/100 (9-point deduction).
- Other extracted content change: 65/100 (35-point deduction).
- No detected semantic change: 100/100.

These prototype rules are calibrated to the case-study examples, not statistically validated.
Scores are triage indicators, not probabilities or automated fraud decisions. Human review is required.

## Module 4: Forensic explanation
The PDF analysis response now includes `forensic_explanation`: a structured, evidence-grounded
summary, findings, review priority, recommended investigator actions and limitations. This is
deterministic rule-based explainability, not an LLM. It avoids asserting fraud or intent. The
dashboard renders the explanation alongside the Trust Score and underlying comparison results.

## Module 5: Image tamper analysis
Install the added dependencies with `python -m pip install -r requirements.txt`.
Collect a JPG/PNG/TIFF/BMP/WEBP image, then select a candidate and click Analyze Image.
The endpoint compares decoded pixels using SSIM and mean absolute pixel difference,
reports changed-pixel ratio, image dimensions, formats, available EXIF differences, and
JPEG-only ELA summary values. Results are triage indicators only. Resizing, compression,
rotation and colour changes can trigger pixel differences; ELA is not proof of manipulation.

## Module 6: Visual forensic comparison
Image analysis now returns browser-renderable visual previews: original/candidate side-by-side,
a contrast-enhanced pixel-difference heatmap, and a 50/50 overlay. Candidate images are resized
to the original dimensions for alignment; this can introduce interpolation differences. The
heatmap is a visualization aid, not a manipulation verdict. Previews are downscaled and embedded
in the analysis API response, so very large source images should still be handled cautiously.

## Module 7: Downloadable forensic report
Install the added `reportlab` dependency. After running PDF or image analysis, use
**Download forensic PDF report** in the result panel. The report includes evidence ID,
original filename and SHA-256 baseline, analysis classification/severity/score, explanation,
findings, relevant image metrics, recommendations and limitations. The report is generated
from the current analysis response; it is not digitally signed and does not replace chain-of-custody
controls or an investigator's signed report.

## Module 8: Audit history and chain-of-custody integrity
Module 8 adds a per-evidence custody ledger backed by a SHA-256 hash chain. Collection,
hash verification, PDF analysis, image analysis and report generation append custody events.
The dashboard can display the ledger and request an integrity verification. Existing
`evidence_events` rows are backfilled once at startup and labelled `legacy-event-log`;
their historical contents are preserved, but the new hashes are created during migration
and do not independently prove the old records were untampered before migration.

API:
- `GET /api/evidence/{id}/custody` — ordered custody events and hashes.
- `GET /api/evidence/{id}/custody/verify` — recompute the event chain and report integrity.

Security note: this is an application-level tamper-evident hash chain, not immutable storage.
A privileged attacker who can rewrite the database and recompute every hash may defeat it.
For production use, add authenticated identities, signed events, restricted append-only
storage, external timestamping or periodic hash anchoring, backups and formal retention controls.


## Module 9: Final integration validation
Automated integration smoke tests passed for collection, hash match/mismatch, image and PDF analysis, report generation, custody history, chain verification and tamper detection. See `MODULE9_TEST_RESULTS.md` and `SECURITY_REVIEW_MODULE9.md`. This build is intended for a controlled local academic demonstration, not public/production deployment without the listed security controls.


## Module 10 — Cloud foundation and investigator login
Module 10 adds a simple investigator login, salted scrypt password hashing, short-lived
HMAC bearer tokens, API protection, authenticated custody actor attribution, environment-
driven PostgreSQL configuration, Docker Compose, backend/frontend container builds and
deployment documentation. See `MODULE10_AUTHENTICATION.md` and `.env.example`.

For a local Docker-based launch, copy `.env.example` to `.env`, replace all placeholders
with strong unique values, then run `docker compose up --build`. Open
`http://localhost:8080`. Do not commit `.env` or deploy with placeholder secrets.
