import base64
import hashlib
import hmac
import json
import os
import time

TOKEN_SECRET = os.getenv("CYBERVAULT_TOKEN_SECRET", "")
TOKEN_TTL_SECONDS = int(os.getenv("CYBERVAULT_TOKEN_TTL_SECONDS", "3600"))

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return "scrypt$" + _b64(salt) + "$" + _b64(digest)

def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, salt_text, digest_text = encoded.split("$", 2)
        if scheme != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(salt_text + "=" * (-len(salt_text) % 4))
        expected = base64.urlsafe_b64decode(digest_text + "=" * (-len(digest_text) % 4))
        actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False

def create_access_token(user_id: int, username: str) -> str:
    if not TOKEN_SECRET or len(TOKEN_SECRET) < 32:
        raise RuntimeError("CYBERVAULT_TOKEN_SECRET must be configured with at least 32 characters.")
    now = int(time.time())
    header = _b64(json.dumps({"alg":"HS256","typ":"JWT"}, separators=(",",":")).encode())
    payload = _b64(json.dumps({"sub":str(user_id),"username":username,"iat":now,"exp":now+TOKEN_TTL_SECONDS}, separators=(",",":")).encode())
    message = f"{header}.{payload}".encode("ascii")
    signature = hmac.new(TOKEN_SECRET.encode(), message, hashlib.sha256).digest()
    return f"{header}.{payload}.{_b64(signature)}"

def decode_access_token(token: str) -> dict:
    if not TOKEN_SECRET or len(TOKEN_SECRET) < 32:
        raise ValueError("Token signing secret is not configured.")
    try:
        header, payload, signature = token.split(".")
        message = f"{header}.{payload}".encode("ascii")
        expected = _b64(hmac.new(TOKEN_SECRET.encode(), message, hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid token signature.")
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if int(data["exp"]) <= int(time.time()):
            raise ValueError("Access token expired.")
        return data
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid access token.") from exc
