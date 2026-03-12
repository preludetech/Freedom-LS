import base64
import hashlib
import hmac


def sign_webhook(
    body: str,
    secret: str,
    webhook_id: str,
    timestamp: int,
) -> str:
    """
    Compute Standard Webhooks signature.
    Returns 'v1,{base64-encoded HMAC-SHA256}'.
    """
    message = f"{webhook_id}.{timestamp}.{body}"
    signature = hmac.new(secret.encode(), message.encode(), hashlib.sha256)
    return f"v1,{base64.b64encode(signature.digest()).decode()}"
