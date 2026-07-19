import hashlib

from app.ids import uuid7
from app.security import issue_session, phone_hash, read_session


def test_phone_hash_is_hmac_not_plain_sha256():
    h = phone_hash("+919999999999")
    assert h != hashlib.sha256(b"+919999999999").hexdigest()
    assert phone_hash("+919999999999") == h  # deterministic


def test_session_roundtrip_and_tamper():
    oid = uuid7()
    tok = issue_session(oid)
    assert read_session(tok) == oid
    assert read_session(tok[:-2] + "xx") is None
    assert read_session("garbage") is None
