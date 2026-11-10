import hashlib
from pathlib import Path
from uuid import uuid4

STORAGE_DIR = Path(__file__).resolve().parent.parent / "storage"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def save_upload(content: bytes, original_filename: str):
    suffix = Path(original_filename).suffix[:20]
    name = f"{uuid4().hex}{suffix}"
    path = STORAGE_DIR / name
    path.write_bytes(content)
    return name, path
