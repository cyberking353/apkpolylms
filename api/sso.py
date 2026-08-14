"""
SSO JWT helpers.

The Portal signs a short-lived (60s) JWT with HMAC-SHA256 (HS256) using the
shared PORTAL_SSO_SECRET, then redirects the browser to
<LMS_FRONTEND_URL>/sso/callback?assertion=<jwt>. The LMS verifies the
signature and expiry, find-or-creates the user keyed on `sub` (portal UUID),
and creates its own session. The JWT is single-use and must NOT be reused as a
session token.

No third-party JWT library required — verification only, fixed HS256.
"""
import base64
import hashlib
import hmac
import json
import time

ALGORITHM = 'HS256'
DEFAULT_TTL_SECONDS = 60

ALLOWED_USER_TYPES = ('student', 'staff')


def _b64url_encode(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=')


def _b64url_decode(value):
    padding = b'=' * (-len(value) % 4)
    return base64.urlsafe_b64decode(value.encode('ascii') + padding)


def _hmac_sha256(message, secret):
    return hmac.new(secret.encode('utf-8'), message.encode('utf-8'),
                    hashlib.sha256).digest()


def sign_jwt(payload, secret, ttl=DEFAULT_TTL_SECONDS, now=None):
    """Build a signed JWT (used in tests / manual replay). Returns a string."""
    now = int(now if now is not None else time.time())
    header = {'alg': ALGORITHM, 'typ': 'JWT'}
    claims = dict(payload)
    claims.setdefault('iat', now)
    claims.setdefault('exp', now + ttl)

    header_seg = _b64url_encode(
        json.dumps(header, separators=(',', ':')).encode('utf-8')).decode()
    payload_seg = _b64url_encode(
        json.dumps(claims, separators=(',', ':')).encode('utf-8')).decode()
    signing_input = f'{header_seg}.{payload_seg}'
    signature = _b64url_encode(_hmac_sha256(signing_input, secret)).decode()
    return f'{signing_input}.{signature}'


def verify_jwt(token, secret):
    """
    Verify a JWT's HS256 signature and expiry against the shared secret.

    Returns (payload, None) on success or (None, error_code) on failure where
    error_code is one of 'malformed', 'invalid', or 'expired'.
    """
    try:
        header_seg, payload_seg, signature_seg = token.split('.')
    except (ValueError, AttributeError):
        return None, 'malformed'

    try:
        signature = _b64url_decode(signature_seg)
        payload_bytes = _b64url_decode(payload_seg)
    except Exception:
        return None, 'malformed'

    expected = _hmac_sha256(f'{header_seg}.{payload_seg}', secret)
    if not hmac.compare_digest(signature, expected):
        return None, 'invalid'

    try:
        payload = json.loads(payload_bytes.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return None, 'malformed'

    if not isinstance(payload, dict):
        return None, 'malformed'

    exp = payload.get('exp')
    if exp is not None and int(exp) < time.time():
        return None, 'expired'

    return payload, None
