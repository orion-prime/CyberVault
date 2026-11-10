from datetime import datetime
from pydantic import BaseModel, ConfigDict

class EvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    original_filename: str
    sha256: str
    size_bytes: int
    created_at: datetime

class VerificationOut(BaseModel):
    evidence_id: int
    filename: str
    original_sha256: str
    uploaded_sha256: str
    status: str
    message: str
