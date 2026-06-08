"""
Time-based One-Time Password (TOTP) helpers — RFC 6238.

Used for 2FA: server and the user's phone share a base32 secret. From that
secret plus the current 30-second time window, both can independently
generate the same 6-digit code. The signature is "knowledge of the secret."
"""

import pyotp

from app.core.config import settings

# Issuer name shown inside Google Authenticator next to the account.
TOTP_ISSUER = "Bayern Tickets"


def generate_secret() -> str:
    """Generate a fresh base32 secret for a new user."""
    return pyotp.random_base32()


def provisioning_uri(secret: str, account_name: str) -> str:
    """
    Build the otpauth:// URL that the QR encodes.

    The phone parses this and learns: issuer, account name, secret.
    """
    return pyotp.totp.TOTP(secret).provisioning_uri(
        name=account_name, issuer_name=TOTP_ISSUER
    )


def verify_code(secret: str, code: str) -> bool:
    """
    Verify a 6-digit code against the user's secret.

    `valid_window=1` accepts the previous, current, and next 30-second window —
    that's ±30 s of clock skew, the standard practice. Without this you'd reject
    perfectly valid codes when the user's phone clock drifts by even a second.
    """
    if not secret or not code or len(code) != 6 or not code.isdigit():
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=1)
