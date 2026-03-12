import base64
import hashlib
import hmac

from freedom_ls.webhooks.signing import sign_webhook


class TestSignWebhook:
    def test_returns_v1_prefixed_signature(self) -> None:
        result = sign_webhook(
            body='{"test": true}',
            secret="my-secret",  # pragma: allowlist secret
            webhook_id="msg_abc123",
            timestamp=1234567890,
        )
        assert result.startswith("v1,")

    def test_signature_is_base64_encoded(self) -> None:
        result = sign_webhook(
            body='{"test": true}',
            secret="my-secret",  # pragma: allowlist secret
            webhook_id="msg_abc123",
            timestamp=1234567890,
        )
        # Extract the base64 part after "v1,"
        b64_part = result[3:]
        # Should decode without error
        decoded = base64.b64decode(b64_part)
        # SHA-256 digest is 32 bytes
        assert len(decoded) == 32

    def test_known_signature(self) -> None:
        """Verify against a manually computed HMAC-SHA256 signature."""
        body = '{"user_id": "abc-123"}'
        secret = "whsec_test_secret"  # noqa: S105  # pragma: allowlist secret
        webhook_id = "msg_001"
        timestamp = 1700000000

        message = f"{webhook_id}.{timestamp}.{body}"
        expected_digest = hmac.new(
            secret.encode(), message.encode(), hashlib.sha256
        ).digest()
        expected = f"v1,{base64.b64encode(expected_digest).decode()}"

        result = sign_webhook(
            body=body,
            secret=secret,
            webhook_id=webhook_id,
            timestamp=timestamp,
        )
        assert result == expected

    def test_different_bodies_produce_different_signatures(self) -> None:
        common = {
            "secret": "my-secret",  # pragma: allowlist secret
            "webhook_id": "msg_001",
            "timestamp": 1234567890,
        }
        sig1 = sign_webhook(body='{"a": 1}', **common)
        sig2 = sign_webhook(body='{"b": 2}', **common)
        assert sig1 != sig2

    def test_different_secrets_produce_different_signatures(self) -> None:
        common = {
            "body": '{"test": true}',
            "webhook_id": "msg_001",
            "timestamp": 1234567890,
        }
        sig1 = sign_webhook(secret="secret-one", **common)
        sig2 = sign_webhook(secret="secret-two", **common)
        assert sig1 != sig2

    def test_different_webhook_ids_produce_different_signatures(self) -> None:
        common = {
            "body": '{"test": true}',
            "secret": "my-secret",  # pragma: allowlist secret
            "timestamp": 1234567890,
        }
        sig1 = sign_webhook(webhook_id="msg_001", **common)
        sig2 = sign_webhook(webhook_id="msg_002", **common)
        assert sig1 != sig2

    def test_different_timestamps_produce_different_signatures(self) -> None:
        common = {
            "body": '{"test": true}',
            "secret": "my-secret",  # pragma: allowlist secret
            "webhook_id": "msg_001",
        }
        sig1 = sign_webhook(timestamp=1000000000, **common)
        sig2 = sign_webhook(timestamp=2000000000, **common)
        assert sig1 != sig2
