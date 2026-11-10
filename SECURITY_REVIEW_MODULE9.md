# CyberVault Module 9 — Security Review

## Scope
Reviewed the Module 8 FastAPI + SQLite backend and React/Vite frontend. This is a prototype review, not a penetration test or production security certification.

## Findings

### High — API has no authentication or authorization
Evidence collection, listing, verification, analysis, report generation, custody history and custody verification routes are accessible without login. Anyone who can reach the API can invoke these operations. Restrict the service to a trusted local environment for demonstrations. Before deployment, add authenticated investigator accounts, role-based authorization and access logging.

### High — Custody actor is hard-coded
New custody events default to `actor="system"`. The ledger records actions but does not identify which human investigator performed them. Add authenticated identity propagation before relying on attribution.

### High — Report endpoint trusts client-supplied analysis
`POST /api/evidence/{id}/report` accepts the analysis dictionary from the browser and builds the report from that payload. A caller can submit altered classifications, scores, findings or recommendations. For stronger evidentiary reporting, persist server-generated analysis results and generate reports from a stored analysis ID; include the analysis hash in the report.

### High — Upload content validation is limited
Upload handling enforces a 25 MB size limit and checks extensions for PDF/image analysis, but does not consistently verify file signatures/content types. Add MIME sniffing and format validation. Consider decompression-bomb and resource limits for image/PDF parsing.

### Medium — Custody hash chain is not immutable
The hash chain detects accidental or partial changes, but a database administrator who can rewrite all rows and recompute the chain may defeat it. Use signed events, external timestamp/hash anchoring and append-only or WORM storage for production.

### Medium — SQLite and storage are local
The database URL is relative to the backend process working directory; storage is local to the application. Ensure backups, restrictive filesystem permissions, controlled deployment paths and recovery procedures.

### Medium — CORS and API host are development-specific
CORS allows `http://localhost:5173`, while the frontend API URL is hard-coded to `http://127.0.0.1:8000`. Configure allowed origins and API base URL through environment-specific configuration before deployment.

## Validation executed

The following integration checks passed using an isolated temporary SQLite working directory:

- Health endpoint.
- Image evidence collection.
- SHA-256 exact-match verification.
- SHA-256 mismatch verification.
- Image analysis and generation of all three visual preview data URLs.
- PDF evidence collection and semantic analysis.
- Forensic PDF report generation (valid `%PDF` response).
- Custody event retrieval and valid-chain verification.
- Unknown evidence ID returns HTTP 404.
- Custody hash-chain tampering is detected after changing a stored event's details.

The image integration test returned a trust score of 60 for the test fixture; this is a rule-based triage score, not a probability of authenticity.

## Release recommendation

**Suitable for a controlled local academic demonstration after user-side regression testing. Not ready for public or production deployment.** Complete authentication/authorization, server-side report provenance, stronger upload validation, investigator identity, immutable audit anchoring and operational backups before production use.
