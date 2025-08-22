# Developer Guide

## Purpose

This section explains how to contribute to the RDEToolKit project and set up a development environment. We welcome various forms of contribution, including bug fixes, new feature additions, and documentation improvements.

## Types of Contributions

### Code Contributions

- **Bug Fixes**: Resolving existing issues
- **New Feature Development**: Adding and extending functionality
- **Performance Improvements**: Optimizing processing speed and memory usage
- **Test Additions**: Improving coverage

### Documentation Contributions

- **Documentation Improvements**: Enhancing quality of existing documentation
- **Translation**: Expanding multilingual support
- **Tutorial Creation**: Enriching learning resources

### Community Contributions

- **Bug Reports**: Finding and reporting issues
- **Feature Requests**: Proposing new features
- **Answering Questions**: Community support

## Development Environment Setup

### Prerequisites

- **Python**: 3.9 or higher
- **Git**: Version control
- **Rye**: Package management tool

### Setup Steps

1. **Clone Repository**
   ```bash title="terminal"
   git clone https://github.com/nims-mdpf/rdetoolkit.git
   cd rdetoolkit
   ```

2. **Install Rye**
   ```bash title="terminal"
   curl -sSf https://rye-up.com/get | bash
   source ~/.rye/env
   ```

3. **Install Dependencies**
   ```bash title="terminal"
   rye sync
   ```

4. **Activate Development Environment**
   ```bash title="terminal"
   source .venv/bin/activate
   ```

5. **Setup pre-commit**
   ```bash title="terminal"
   pre-commit install
   ```

## Development Workflow

### Branch Strategy

- **main**: Stable main branch
- **feature/**: New feature development branches
- **bugfix/**: Bug fix branches
- **docs/**: Documentation update branches

### Development Process

1. **Create or Check Issue**
   - Clarify work content in GitHub Issues
   - Check if existing Issue exists

2. **Create Branch**
   ```bash title="terminal"
   git checkout -b feature/your-feature-name
   ```

3. **Development and Testing**
   ```bash title="terminal"
   # Make code changes
   # Run tests
   rye test

   # Lint check
   rye lint

   # Format
   rye fmt
   ```

4. **Commit and Push**
   ```bash title="terminal"
   git add .
   git commit -m "feat: add new feature description"
   git push origin feature/your-feature-name
   ```

5. **Create Pull Request**
   - Create pull request on GitHub
   - Include detailed description and test results

## Coding Standards

### Python Style

- **PEP 8**: Comply with Python standard style guide
- **Type Hints**: Add type annotations to all functions
- **docstring**: Use Google-style docstrings

```python title="example_function.py"
def process_data(
    input_data: List[Dict[str, Any]],
    config: Optional[Config] = None
) -> ProcessResult:
    """
    Function to process data

    Args:
        input_data: List of data to be processed
        config: Processing configuration (optional)

    Returns:
        ProcessResult object containing processing results

    Raises:
        ValueError: When input data is invalid
        ProcessingError: When error occurs during processing

    Example:
        >>> data = [{"key": "value"}]
        >>> result = process_data(data)
        >>> print(result.status)
        'success'
    """
    if not input_data:
        raise ValueError("Input data cannot be empty")

    # Processing logic
    return ProcessResult(status="success")
```

### Writing Tests

```python title="test_example.py"
import pytest
from rdetoolkit.processing import process_data

class TestProcessData:
    def test_valid_input(self):
        """Test with valid input data"""
        data = [{"key": "value"}]
        result = process_data(data)
        assert result.status == "success"

    def test_empty_input(self):
        """Test with empty input data"""
        with pytest.raises(ValueError):
            process_data([])

    def test_invalid_input(self):
        """Test with invalid input data"""
        with pytest.raises(TypeError):
            process_data("invalid")
```

## Quality Assurance

### Automated Checks

- **pre-commit**: Automatic checks before commit
- **GitHub Actions**: CI/CD pipeline
- **codecov**: Test coverage measurement

### Check Items

- **Lint**: flake8, pylint
- **Format**: black, isort
- **Type Check**: mypy
- **Test**: pytest
- **Security**: bandit

## Release Process

### Versioning

Adopts Semantic Versioning (SemVer):

- **MAJOR**: Breaking changes
- **MINOR**: Backward-compatible feature additions
- **PATCH**: Backward-compatible bug fixes

### Release Steps

1. **Update Changelog**
2. **Update Version Number**
3. **Create Tag**
4. **Publish to PyPI**
5. **Create GitHub Release**

## Community Guidelines

### Communication

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Questions and discussions
- **Pull Request**: Code review and discussion

### Code of Conduct

- **Respect**: Respect all participants
- **Constructive**: Provide constructive feedback
- **Collaborative**: Value teamwork
- **Inclusive**: Welcome diversity

## Next Steps

To participate in development:

1. [Contributing](contributing.en.md) - Detailed contribution guidelines
2. [Documentation Creation](docs.en.md) - How to create documentation
3. [GitHub Issues](https://github.com/nims-mdpf/rdetoolkit/issues) - Check available tasks

!!! tip "For First-time Contributors"
    If you're contributing for the first time, we recommend starting with Issues labeled "good first issue".
