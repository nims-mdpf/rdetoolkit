import pytest

from rdetoolkit.traceback.masking import SecretsSanitizer


class TestSecretsSanitizer:
    def test_default_patterns(self):
        sanitizer = SecretsSanitizer()

        assert sanitizer.check_mask('password') is True
        assert sanitizer.check_mask('PASSWORD') is True
        assert sanitizer.check_mask('api_key') is True
        assert sanitizer.check_mask('token') is True
        assert sanitizer.check_mask('secret_key') is True
        assert sanitizer.check_mask('auth_token') is True

        assert sanitizer.check_mask('username') is False
        assert sanitizer.check_mask('data') is False
        assert sanitizer.check_mask('result') is False

    def test_custom_pattern(self):
        custom = [r'(?i)my_custom_secret', r'(?i)special_key']
        sanitizer = SecretsSanitizer(custom_patterns=custom)

        assert sanitizer.check_mask("password") is True

        assert sanitizer.check_mask("my_custom_secret") is True
        assert sanitizer.check_mask("MY_CUSTOM_SECRET") is True
        assert sanitizer.check_mask("special_key") is True

    def test_mask_value(self):
        sanitizer = SecretsSanitizer()

        assert sanitizer.mask_value("password", "secret123") == "***"
        assert sanitizer.mask_value("api_key", "abc-123-def") == "***"
        assert sanitizer.mask_value("token", {"value": "xyz"}) == "***"

        assert sanitizer.mask_value("username", "john") == "'john'"
        assert sanitizer.mask_value("count", 42) == "42"
        assert sanitizer.mask_value("data", [1, 2, 3]) == "[1, 2, 3]"

    def test_mask_dict(self):
        sanitizer = SecretsSanitizer()

        data = {
            "username": "alice",
            "password": "secret123",
            "api_key": "key-456",
            "count": 100,
            "items": ["a", "b", "c"]
        }

        result = sanitizer.mask_dict(data)

        assert result["username"] == "'alice'"
        assert result["password"] == "***"
        assert result["api_key"] == "***"
        assert result["count"] == 100
        assert result["items"] == ["a", "b", "c"]

    def test_truncate_value(self):
        sanitizer = SecretsSanitizer()

        short_str = "Hello"
        assert sanitizer.truncate_value(short_str, 100) == "Hello"

        long_str = "A" * 100
        truncated = sanitizer.truncate_value(long_str, 10)
        assert truncated.endswith("...")
        assert len(truncated.encode('utf-8')) <= 10

        jp_str = "こんにちは世界" * 10
        truncated_jp = sanitizer.truncate_value(jp_str, 20)
        assert truncated_jp.endswith("...")
        assert len(truncated_jp.encode('utf-8')) <= 20

        assert sanitizer.truncate_value("test", 0) == "..."
        assert sanitizer.truncate_value("test", 3) == "..."
        assert sanitizer.truncate_value("test", 4) == "test"


    def test_process_locals(self):
        sanitizer = SecretsSanitizer()

        frame_locals = {
            "__name__": "__main__",
            "user": "bob",
            "password": "secret",
            "data": {"key": "value" * 100},
            "api_token": "token-123",
            "count": 42
        }

        result = sanitizer.process_locals(frame_locals)
        assert result["user"] == "'bob'"
        assert result["password"] == "***"
        assert result["api_token"] == "***"
        assert result["count"] == "42"

        assert len(result["data"].encode("utf-8")) <= 50
        assert result["data"].endswith("...")

    def test_unprintable_fallback(self):
        class BadObject:
            def __str__(self):
                raise Exception("Can't repr")
            def __repr__(self):
                raise Exception("Can't repr")

        sanitizer = SecretsSanitizer()
        result = sanitizer.mask_value("obj", BadObject())
        assert result == "<unprintable>"
