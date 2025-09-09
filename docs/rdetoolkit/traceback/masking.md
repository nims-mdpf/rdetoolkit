# Masking API

## Purpose

The masking module provides security functionality for automatically detecting and masking sensitive information in traceback output. It protects credentials, API keys, passwords, and other sensitive data from being exposed in error logs while maintaining the usefulness of traceback information for debugging and AI analysis.

## Key Features

### Automatic Detection
- Built-in patterns for common sensitive data types
- Configurable custom patterns for organization-specific secrets
- Case-insensitive pattern matching for robust detection

### Flexible Masking
- Configurable replacement text (default: `***`)
- Size limits to prevent excessive output
- Preserves data structure while hiding sensitive values

### Security by Default
- Comprehensive built-in patterns covering passwords, tokens, keys
- Safe handling of large data structures
- No false negatives for critical security patterns

---

## Core Classes

::: src.rdetoolkit.traceback.masking.SecretsSanitizer

---

## Practical Usage

### Basic Masking

```python title="basic_masking.py"
from rdetoolkit.traceback.masking import SecretsSanitizer

def demonstrate_basic_masking():
    """Demonstrate basic sensitive data masking."""

    masker = SecretsSanitizer()

    # Test data with various sensitive information
    test_data = {
        "username": "john_doe",
        "password": "secret123",
        "api_key": "sk-1234567890abcdef",
        "user_token": "eyJhbGciOiJIUzI1NiIs...",
        "database_password": "db_secret_456",
        "secret_config": "confidential_value",
        "normal_data": "this_is_safe",
        "email": "user@example.com"
    }

    print("=== Original Data ===")
    for key, value in test_data.items():
        print(f"{key}: {value}")

    print("\n=== Masked Data ===")
    for key, value in test_data.items():
        masked_value = masker.mask_sensitive_value(key, str(value))
        print(f"{key}: {masked_value}")

# Run demonstration
demonstrate_basic_masking()
```

### Custom Patterns

```python title="custom_patterns.py"
from rdetoolkit.traceback.masking import SecretsSanitizer

def demonstrate_custom_patterns():
    """Demonstrate custom sensitive patterns."""

    # Add organization-specific patterns
    custom_patterns = [
        "company_id",
        "internal_key",
        "private_config",
        "wallet_address",
        "encryption_key"
    ]

    masker = SecretsSanitizer(additional_patterns=custom_patterns)

    # Test data with custom sensitive patterns
    test_data = {
        "company_id": "COMP-12345-SECRET",
        "internal_key": "internal_secret_key_789",
        "private_config": "private_configuration_data",
        "wallet_address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
        "encryption_key": "AES-256-KEY-ABCDEF123456",
        "public_info": "this_is_safe_to_show",
        "user_preferences": {"theme": "dark", "lang": "en"}
    }

    print("=== Custom Pattern Masking ===")
    for key, value in test_data.items():
        masked_value = masker.mask_sensitive_value(key, str(value))
        status = "MASKED" if masked_value == "***" else "SAFE"
        print(f"{key:20}: {masked_value:30} [{status}]")

# Run demonstration
demonstrate_custom_patterns()
```

### Size Limit Handling

```python title="size_limit_handling.py"
from rdetoolkit.traceback.masking import SecretsSanitizer

def demonstrate_size_limits():
    """Demonstrate size limit functionality."""

    # Create masker with small size limit
    small_limit_masker = SecretsSanitizer(max_size=50)

    # Create masker with larger size limit
    large_limit_masker = SecretsSanitizer(max_size=200)

    # Test with large data structure
    large_data = {
        "user_data": {
            "id": 12345,
            "name": "John Doe",
            "email": "john@example.com",
            "preferences": {
                "theme": "dark",
                "notifications": True,
                "privacy_settings": {
                    "show_email": False,
                    "show_phone": False
                }
            },
            "metadata": {
                "created_at": "2023-01-01T00:00:00Z",
                "last_login": "2023-12-01T10:00:00Z",
                "login_count": 150
            }
        }
    }

    data_str = str(large_data)
    print(f"Original data size: {len(data_str)} characters")
    print(f"Original: {data_str[:100]}...")

    # Test with small limit
    masked_small = small_limit_masker.mask_sensitive_value("user_data", data_str)
    print(f"\nWith 50-char limit: {masked_small}")

    # Test with large limit
    masked_large = large_limit_masker.mask_sensitive_value("user_data", data_str)
    print(f"\nWith 200-char limit: {masked_large[:100]}...")

# Run demonstration
demonstrate_size_limits()
```

### Advanced Masking Scenarios

```python title="advanced_masking.py"
from rdetoolkit.traceback.masking import SecretsSanitizer

class AdvancedMasker(SecretsSanitizer):
    """Advanced masker with custom logic."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Add context-aware patterns
        self.context_patterns = {
            "database": ["connection_string", "db_url", "jdbc_url"],
            "aws": ["access_key", "secret_key", "session_token"],
            "crypto": ["private_key", "mnemonic", "seed_phrase"]
        }

    def mask_with_context(self, context: str, variable_name: str, value: str) -> str:
        """Mask with awareness of context."""

        # Check context-specific patterns
        if context in self.context_patterns:
            for pattern in self.context_patterns[context]:
                if pattern.lower() in variable_name.lower():
                    return f"***{context.upper()}_REDACTED***"

        # Fall back to standard masking
        return self.mask_sensitive_value(variable_name, value)

def demonstrate_advanced_masking():
    """Demonstrate advanced masking scenarios."""

    masker = AdvancedMasker(max_size=100)

    # Simulate different contexts
    test_scenarios = [
        ("database", "connection_string", "postgresql://user:pass@host:5432/db"),
        ("database", "db_password", "secret_db_pass"),
        ("aws", "access_key", "AKIAIOSFODNN7EXAMPLE"),
        ("aws", "secret_key", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"),
        ("crypto", "private_key", "-----BEGIN PRIVATE KEY-----"),
        ("crypto", "mnemonic", "abandon ability able about above..."),
        ("general", "user_email", "user@example.com"),
        ("general", "password", "user_password_123")
    ]

    print("=== Advanced Context-Aware Masking ===")
    for context, var_name, value in test_scenarios:
        masked = masker.mask_with_context(context, var_name, value)
        print(f"{context:10} | {var_name:20} | {masked}")

# Run demonstration
demonstrate_advanced_masking()
```

### Integration with Local Variables

```python title="locals_integration.py"
from rdetoolkit.traceback.masking import SecretsSanitizer
import inspect

def demonstrate_locals_masking():
    """Demonstrate masking of local variables from a function."""

    masker = SecretsSanitizer(max_size=256)

    # Simulate a function with mixed safe/sensitive locals
    simulate_function_with_locals()

def simulate_function_with_locals():
    """Function with various local variables for masking demo."""

    masker = SecretsSanitizer(max_size=256)

    # Safe variables
    user_id = 12345
    username = "john_doe"
    email = "john@example.com"
    timestamp = "2023-12-01T10:00:00Z"

    # Sensitive variables (will be masked)
    password = "user_secret_password"
    api_key = "sk-1234567890abcdef"
    auth_token = "Bearer eyJhbGciOiJIUzI1NiIs..."
    database_password = "db_secret_123"

    # Complex data structures
    user_config = {
        "theme": "dark",
        "api_key": "secret_api_key_456",  # Nested sensitive data
        "preferences": {
            "notifications": True,
            "privacy": "high"
        }
    }

    # Get current local variables
    current_locals = locals()

    print("=== Local Variables Masking ===")
    for var_name, var_value in current_locals.items():
        if var_name == 'masker':  # Skip the masker itself
            continue

        # Convert to string and mask
        var_str = str(var_value)
        masked_value = masker.mask_sensitive_value(var_name, var_str)

        # Show original vs masked
        is_masked = masked_value == "***"
        status = "MASKED" if is_masked else "SAFE"

        print(f"{var_name:20}: {masked_value:40} [{status}]")

# Run demonstration
demonstrate_locals_masking()
```

### Performance Testing

```python title="performance_testing.py"
from rdetoolkit.traceback.masking import SecretsSanitizer
import time

def benchmark_masking_performance():
    """Benchmark masking performance with different data sizes."""

    masker = SecretsSanitizer(max_size=1024)

    # Test data of different sizes
    test_cases = [
        ("small", "password", "secret123"),
        ("medium", "config", "x" * 100 + "password=secret" + "y" * 100),
        ("large", "data", "z" * 1000 + "api_key=secret_key" + "w" * 1000),
        ("huge", "payload", "a" * 10000 + "token=secret_token" + "b" * 10000)
    ]

    print("=== Masking Performance Benchmark ===")

    for size_name, var_name, test_data in test_cases:
        iterations = 1000

        start_time = time.time()

        for _ in range(iterations):
            masker.mask_sensitive_value(var_name, test_data)

        end_time = time.time()

        avg_time_ms = (end_time - start_time) / iterations * 1000
        data_size = len(test_data)

        print(f"{size_name:6} ({data_size:6} chars): {avg_time_ms:.3f}ms per mask")

# Run benchmark
benchmark_masking_performance()
```

### Custom Replacement Strategies

```python title="custom_replacement.py"
from rdetoolkit.traceback.masking import SecretsSanitizer

class CustomReplacementMasker(SecretsSanitizer):
    """Masker with custom replacement strategies."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Define custom replacement strategies
        self.replacement_strategies = {
            "password": "***PASSWORD_HIDDEN***",
            "key": "***KEY_REDACTED***",
            "token": "***TOKEN_MASKED***",
            "secret": "***SECRET_PROTECTED***"
        }

    def mask_sensitive_value(self, variable_name: str, value: str) -> str:
        """Mask with custom replacement text."""

        if self._is_sensitive(variable_name):
            # Use custom replacement based on variable type
            for pattern, replacement in self.replacement_strategies.items():
                if pattern.lower() in variable_name.lower():
                    return replacement

            # Default custom replacement
            return "***SENSITIVE_DATA_REDACTED***"

        # Apply size limit to non-sensitive data
        if len(value) > self.max_size:
            return f"{value[:self.max_size]}...[TRUNCATED]"

        return value

def demonstrate_custom_replacement():
    """Demonstrate custom replacement strategies."""

    masker = CustomReplacementMasker(max_size=100)

    test_variables = [
        ("user_password", "secret123"),
        ("api_key", "sk-1234567890abcdef"),
        ("auth_token", "Bearer eyJhbGciOiJIUzI1NiIs..."),
        ("database_secret", "db_secret_456"),
        ("normal_data", "this_is_normal_data"),
        ("large_data", "x" * 200)  # Will be truncated
    ]

    print("=== Custom Replacement Strategies ===")
    for var_name, value in test_variables:
        masked = masker.mask_sensitive_value(var_name, value)
        print(f"{var_name:20}: {masked}")

# Run demonstration
demonstrate_custom_replacement()
```

### Integration Best Practices

```python title="integration_best_practices.py"
from rdetoolkit.traceback.masking import SecretsSanitizer
from rdetoolkit.models.config import TracebackSettings

class ProductionSafeMasker(SecretsSanitizer):
    """Production-safe masker with comprehensive security."""

    def __init__(self, environment="production"):
        # Production environments get stricter settings
        if environment == "production":
            max_size = 256  # Smaller limit
            additional_patterns = [
                # Add all possible sensitive patterns
                "connection", "credential", "auth", "session",
                "private", "confidential", "internal", "secure"
            ]
        else:
            max_size = 1024  # Development can be more verbose
            additional_patterns = []

        super().__init__(
            additional_patterns=additional_patterns,
            max_size=max_size
        )

        self.environment = environment

    def mask_sensitive_value(self, variable_name: str, value: str) -> str:
        """Production-safe masking with extra paranoia."""

        # In production, be extra cautious
        if self.environment == "production":
            # Mask anything that looks remotely sensitive
            suspicious_patterns = ["id", "url", "path", "config"]
            for pattern in suspicious_patterns:
                if pattern in variable_name.lower() and len(value) > 50:
                    return "***PROD_SAFETY_MASKED***"

        return super().mask_sensitive_value(variable_name, value)

def demonstrate_production_integration():
    """Demonstrate production-safe masking integration."""

    # Different maskers for different environments
    dev_masker = ProductionSafeMasker("development")
    prod_masker = ProductionSafeMasker("production")

    test_data = [
        ("database_url", "postgresql://user:pass@prod-db:5432/app"),
        ("config_path", "/etc/app/secret_config.json"),
        ("user_id", "12345"),
        ("internal_key", "internal_secret_value"),
        ("debug_info", "x" * 100)  # Long debug string
    ]

    print("=== Environment-Specific Masking ===")
    print(f"{'Variable':20} | {'Development':30} | {'Production':30}")
    print("-" * 85)

    for var_name, value in test_data:
        dev_masked = dev_masker.mask_sensitive_value(var_name, value)
        prod_masked = prod_masker.mask_sensitive_value(var_name, value)

        print(f"{var_name:20} | {dev_masked[:28]:28} | {prod_masked[:28]:28}")

# Run demonstration
demonstrate_production_integration()
```
