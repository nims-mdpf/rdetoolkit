# How to Contribute

## Purpose

This guide explains specific procedures and methods for effectively contributing to the RDEToolKit project. We provide detailed information so that everyone from first-time contributors to experienced developers can contribute smoothly.

## Prerequisites

Before starting to contribute, please ensure the following:

- **GitHub Account**: Required for creating pull requests
- **Basic Git Knowledge**: Branch operations, commits, pushes
- **Python Development Experience**: Basic Python knowledge
- **Development Environment**: [Development environment setup](index.en.md#development-environment-setup) completed

## Steps

### 1. Decide What to Contribute

#### Check Issues

Select work from existing Issues or create a new Issue:

```bash title="terminal"
# Get latest repository state
git fetch origin
git checkout main
git pull origin main
```

#### Types of Contributions

| Type | Description | Label |
|------|-------------|-------|
| Bug Fix | Resolving issues with existing features | `bug` |
| New Feature | Adding or extending functionality | `enhancement` |
| Documentation | Improving documentation | `documentation` |
| Testing | Adding or improving tests | `testing` |

!!! tip "For First-time Contributors"
    We recommend starting with Issues labeled `good first issue`.

### 2. Create Development Branch

#### Branch Naming Convention

```bash title="terminal"
# For feature addition
git checkout -b feature/issue-123-add-new-validator

# For bug fix
git checkout -b bugfix/issue-456-fix-config-parsing

# For documentation update
git checkout -b docs/issue-789-update-api-reference
```

#### Branch Name Components

- **Prefix**: `feature/`, `bugfix/`, `docs/`
- **Issue Number**: `issue-123`
- **Brief Description**: `add-new-validator`

### 3. Execute Development

#### Code Changes

```python title="example_contribution.py"
from typing import List, Optional
from rdetoolkit.models.rde2types import RdeInputDirPaths

def validate_input_files(srcpaths: RdeInputDirPaths) -> List[str]:
    """
    Validate input files
    
    Args:
        srcpaths: Input file path information
    
    Returns:
        List of validation errors (empty if valid)
    
    Example:
        >>> errors = validate_input_files(srcpaths)
        >>> if not errors:
        ...     print("All files are valid")
    """
    errors = []
    
    # Check input directory existence
    if not srcpaths.inputdata.exists():
        errors.append("Input data directory does not exist")
    
    # Check file count
    if srcpaths.inputdata.exists():
        files = list(srcpaths.inputdata.glob("*"))
        if len(files) == 0:
            errors.append("No input files found")
    
    return errors
```

#### Add Tests

```python title="test_contribution.py"
import pytest
from pathlib import Path
from rdetoolkit.validation import validate_input_files
from rdetoolkit.models.rde2types import RdeInputDirPaths

class TestValidateInputFiles:
    def test_valid_directory_with_files(self, tmp_path):
        """Test valid directory with files"""
        # Prepare test data
        input_dir = tmp_path / "inputdata"
        input_dir.mkdir()
        (input_dir / "test_file.txt").write_text("test content")
        
        srcpaths = RdeInputDirPaths(inputdata=input_dir)
        
        # Execute test
        errors = validate_input_files(srcpaths)
        
        # Verify
        assert errors == []
    
    def test_missing_directory(self, tmp_path):
        """Test non-existent directory"""
        input_dir = tmp_path / "nonexistent"
        srcpaths = RdeInputDirPaths(inputdata=input_dir)
        
        errors = validate_input_files(srcpaths)
        
        assert "Input data directory does not exist" in errors
    
    def test_empty_directory(self, tmp_path):
        """Test empty directory"""
        input_dir = tmp_path / "inputdata"
        input_dir.mkdir()
        
        srcpaths = RdeInputDirPaths(inputdata=input_dir)
        
        errors = validate_input_files(srcpaths)
        
        assert "No input files found" in errors
```

### 4. Execute Quality Checks

#### Run Automated Checks

```bash title="terminal"
# Run all checks
rye test
rye lint
rye fmt

# Individual checks
pytest tests/test_contribution.py -v
mypy src/rdetoolkit/validation.py
black src/rdetoolkit/validation.py
```

#### Run pre-commit

```bash title="terminal"
# Manual execution of pre-commit hooks
pre-commit run --all-files

# Run specific hooks only
pre-commit run black --all-files
pre-commit run mypy --all-files
```

### 5. Commit and Push

#### Commit Message Rules

```bash title="terminal"
# Feature addition
git commit -m "feat: add input file validation function

- Add validate_input_files function to check directory existence
- Add comprehensive test cases for validation scenarios
- Update documentation with usage examples

Closes #123"

# Bug fix
git commit -m "fix: resolve config parsing error for YAML files

- Fix YAML parsing issue when file contains special characters
- Add error handling for malformed YAML files
- Update tests to cover edge cases

Fixes #456"
```

#### Commit Message Structure

- **Type**: `feat`, `fix`, `docs`, `test`, `refactor`
- **Description**: Brief description of changes
- **Details**: Detailed description if necessary
- **Issue Reference**: `Closes #123`, `Fixes #456`

### 6. Create Pull Request

#### Pull Request Template

```markdown title="pull_request_template.md"
## Overview
Please briefly describe the purpose and content of this change.

## Changes
- [ ] New feature addition
- [ ] Bug fix
- [ ] Documentation update
- [ ] Test addition
- [ ] Refactoring

## Testing
- [ ] All existing tests pass
- [ ] Added new tests
- [ ] Executed manual testing

## Checklist
- [ ] Code complies with project style guide
- [ ] Executed self-review
- [ ] Updated documentation as needed
- [ ] Changes do not include breaking changes

## Related Issue
Closes #123
```

#### Review Process

1. **Automated Checks**: Pass CI/CD pipeline
2. **Code Review**: Review by maintainers
3. **Address Fixes**: Fixes based on feedback
4. **Merge**: Merge after approval

## Verification

### Check CI/CD

```bash title="terminal"
# Check GitHub Actions status
gh pr checks

# Check details of specific check
gh run view --log
```

### Respond to Review Feedback

```bash title="terminal"
# Fixes based on feedback
git add .
git commit -m "fix: address review feedback

- Update function documentation
- Add missing type hints
- Fix test assertion logic"

git push origin feature/issue-123-add-new-validator
```

## Troubleshooting

### Common Issues and Solutions

#### Test Failures

```bash title="terminal"
# Check detailed test results
pytest -v --tb=long

# Run specific test only
pytest tests/test_contribution.py::TestValidateInputFiles::test_valid_directory_with_files -v
```

#### Lint Errors

```bash title="terminal"
# Fix automatically correctable errors
black src/
isort src/

# Check errors requiring manual fixes
flake8 src/
pylint src/
```

#### Merge Conflicts

```bash title="terminal"
# Get latest main branch
git fetch origin
git checkout main
git pull origin main

# Merge to feature branch
git checkout feature/issue-123-add-new-validator
git merge main

# After resolving conflicts
git add .
git commit -m "resolve merge conflicts with main"
git push origin feature/issue-123-add-new-validator
```

## Related Information

Detailed information about contributions:

- [Developer Guide](index.en.md) - Development environment setup
- [Documentation Creation](docs.en.md) - How to contribute to documentation
- [GitHub Issues](https://github.com/nims-mdpf/rdetoolkit/issues) - Available tasks

!!! note "Community Support"
    If you have questions or need help, feel free to ask on [GitHub Discussions](https://github.com/nims-mdpf/rdetoolkit/discussions).
