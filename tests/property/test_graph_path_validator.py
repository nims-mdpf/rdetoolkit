"""Property-based tests for rdetoolkit.graph.io.path_validator.

This module tests PathValidator using property-based testing to verify
security properties and validation behavior across a wide range of inputs.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from rdetoolkit.graph.io.path_validator import PathValidator


# =============================================================================
# Custom Strategies
# =============================================================================


@st.composite
def safe_filename_strategy(draw: st.DrawFn) -> str:
    """Generate safe filenames without path separators or '..' sequences.

    Returns:
        Safe filename string that should pass validation.
    """
    # Use alphanumeric, underscore, hyphen, dot (but not "..")
    # Exclude path separators and ".." sequence
    base_chars = st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"),
        whitelist_characters="_-.",
    )

    filename = draw(st.text(alphabet=base_chars, min_size=1, max_size=100))

    # Ensure doesn't contain ".." sequence or start with ".."
    assume(".." not in filename)
    assume("/" not in filename)
    assume("\\" not in filename)
    # Ensure not empty and doesn't start with just dots
    assume(not filename.startswith(".."))

    return filename


@st.composite
def unsafe_filename_strategy(draw: st.DrawFn) -> str:
    """Generate filenames containing dangerous patterns.

    Returns:
        Unsafe filename that should fail validation.
    """
    return draw(
        st.sampled_from(
            [
                "..",  # Path traversal
                "../",
                "/..",
                "../..",
                "/etc/passwd",  # Absolute path
                "\\windows\\system32",  # Windows path
                "file/../other",  # Embedded traversal
                "..\\file",  # Windows traversal
            ],
        ),
    )


@st.composite
def filename_with_extensions(draw: st.DrawFn) -> str:
    """Generate safe filenames with various extensions.

    Returns:
        Filename with extension.
    """
    base = draw(safe_filename_strategy())
    ext = draw(st.sampled_from([".txt", ".csv", ".json", ".png", ".pdf", ""]))
    filename = base + ext

    # Ensure the resulting filename doesn't contain ".."
    assume(".." not in filename)

    return filename


# =============================================================================
# PathValidator.validate() Property Tests
# =============================================================================


@pytest.mark.property
class TestPathValidatorValidateProperties:
    """Property-based tests for PathValidator.validate()."""

    @given(filename=unsafe_filename_strategy())
    def test_dangerous_filenames_always_rejected(self, filename: str) -> None:
        r"""Property: Dangerous filenames always raise ValueError.

        Given: A filename containing "..", "/", or "\\"
        When: Validating the filename
        Then: ValueError is always raised
        """
        validator = PathValidator()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # When: Validating dangerous filename
            # Then: Must raise ValueError
            with pytest.raises(ValueError, match="Invalid filename|Security violation"):
                validator.validate(output_dir, filename)

    @given(filename=safe_filename_strategy())
    def test_safe_filenames_stay_within_output_dir(self, filename: str) -> None:
        r"""Property: Safe filenames resolve to paths within output_dir.

        Given: A safe filename (no "..", "/", "\\")
        When: Validating the filename
        Then: Resolved path starts with output_dir
        """
        validator = PathValidator()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir).resolve()

            # When: Validating safe filename
            result = validator.validate(output_dir, filename)

            # Then: Resolved path is within output_dir
            assert str(result).startswith(str(output_dir))
            assert result.parent == output_dir

    @given(filename=safe_filename_strategy())
    def test_validation_is_idempotent(self, filename: str) -> None:
        """Property: Validating the same filename twice yields same result.

        Given: A safe filename
        When: Validating twice with same inputs
        Then: Both results are identical
        """
        validator = PathValidator()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # When: Validating twice
            result1 = validator.validate(output_dir, filename)
            result2 = validator.validate(output_dir, filename)

            # Then: Results are identical
            assert result1 == result2

    @given(filename=filename_with_extensions())
    def test_extensions_are_preserved(self, filename: str) -> None:
        """Property: File extensions are preserved in validated paths.

        Given: A filename with an extension
        When: Validating the filename
        Then: Extension is preserved in the result
        """
        validator = PathValidator()
        expected_ext = Path(filename).suffix

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # When: Validating filename with extension
            result = validator.validate(output_dir, filename)

            # Then: Extension is preserved
            assert result.suffix == expected_ext

    @given(
        filename1=safe_filename_strategy(),
        filename2=safe_filename_strategy(),
    )
    def test_different_filenames_yield_different_paths(
        self,
        filename1: str,
        filename2: str,
    ) -> None:
        """Property: Different filenames produce different validated paths.

        Given: Two different safe filenames
        When: Validating both in the same output_dir
        Then: The resulting paths are different
        """
        # Given: Two different filenames
        assume(filename1 != filename2)

        validator = PathValidator()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # When: Validating both filenames
            result1 = validator.validate(output_dir, filename1)
            result2 = validator.validate(output_dir, filename2)

            # Then: Paths are different
            assert result1 != result2

    @given(filename=safe_filename_strategy())
    def test_validated_path_is_absolute(self, filename: str) -> None:
        """Property: Validated paths are always absolute.

        Given: Any safe filename
        When: Validating the filename
        Then: Result is an absolute path
        """
        validator = PathValidator()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # When: Validating filename
            result = validator.validate(output_dir, filename)

            # Then: Path is absolute
            assert result.is_absolute()

    @given(filename=safe_filename_strategy())
    def test_nonexistent_directory_raises_error(self, filename: str) -> None:
        """Property: Validation fails for nonexistent directories.

        Given: A safe filename and a nonexistent directory
        When: Validating the filename
        Then: ValueError is raised
        """
        validator = PathValidator()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a path that doesn't exist
            nonexistent_dir = Path(tmpdir) / "does_not_exist"

            # When/Then: Validation raises ValueError
            with pytest.raises(ValueError, match="does not exist"):
                validator.validate(nonexistent_dir, filename)

    @given(filename=safe_filename_strategy())
    def test_file_instead_of_directory_raises_error(self, filename: str) -> None:
        """Property: Validation fails when output_dir is a file.

        Given: A safe filename and a file path (not directory)
        When: Validating the filename
        Then: ValueError is raised
        """
        validator = PathValidator()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file instead of directory
            file_path = Path(tmpdir) / "file.txt"
            file_path.write_text("test")

            # When/Then: Validation raises ValueError
            with pytest.raises(ValueError, match="not a directory"):
                validator.validate(file_path, filename)


# =============================================================================
# PathValidator.ensure_directory() Property Tests
# =============================================================================


@pytest.mark.property
class TestPathValidatorEnsureDirectoryProperties:
    """Property-based tests for PathValidator.ensure_directory()."""

    @given(
        dirname=st.text(
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
            min_size=1,
            max_size=50,
        ),
    )
    def test_ensure_directory_creates_directory(self, dirname: str) -> None:
        """Property: ensure_directory creates directories if they don't exist.

        Given: A directory name
        When: Calling ensure_directory
        Then: Directory exists after the call
        """
        validator = PathValidator()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_dir = Path(tmpdir) / dirname

            # When: Ensuring directory exists
            result = validator.ensure_directory(target_dir)

            # Then: Directory exists and is a directory
            assert result.exists()
            assert result.is_dir()
            assert result == target_dir.resolve()

    @given(
        dirname=st.text(
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
            min_size=1,
            max_size=50,
        ),
    )
    def test_ensure_directory_is_idempotent(self, dirname: str) -> None:
        """Property: ensure_directory can be called multiple times safely.

        Given: A directory path
        When: Calling ensure_directory multiple times
        Then: All calls succeed and return the same path
        """
        validator = PathValidator()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_dir = Path(tmpdir) / dirname

            # When: Calling ensure_directory multiple times
            result1 = validator.ensure_directory(target_dir)
            result2 = validator.ensure_directory(target_dir)
            result3 = validator.ensure_directory(target_dir)

            # Then: All results are the same
            assert result1 == result2 == result3
            assert target_dir.exists()

    @given(
        components=st.lists(
            st.text(
                alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
                min_size=1,
                max_size=20,
            ),
            min_size=1,
            max_size=5,
        ),
    )
    def test_ensure_directory_creates_nested_paths(self, components: list[str]) -> None:
        """Property: ensure_directory creates nested directory hierarchies.

        Given: A list of directory name components
        When: Ensuring a nested directory path
        Then: All parent directories are created
        """
        validator = PathValidator()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Build nested path
            nested_path = Path(tmpdir)
            for component in components:
                nested_path = nested_path / component

            # When: Ensuring nested directory exists
            result = validator.ensure_directory(nested_path)

            # Then: All levels exist
            assert result.exists()
            assert result.is_dir()

            # Verify all parent directories were created
            current = result
            for _ in range(len(components)):
                assert current.exists()
                assert current.is_dir()
                current = current.parent

    @given(
        dirname=st.text(
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
            min_size=1,
            max_size=50,
        ),
    )
    def test_ensure_directory_returns_absolute_path(self, dirname: str) -> None:
        """Property: ensure_directory always returns absolute path.

        Given: Any directory name
        When: Calling ensure_directory
        Then: Result is an absolute path
        """
        validator = PathValidator()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_dir = Path(tmpdir) / dirname

            # When: Ensuring directory exists
            result = validator.ensure_directory(target_dir)

            # Then: Result is absolute
            assert result.is_absolute()

    @given(
        dirname=st.text(
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
            min_size=1,
            max_size=50,
        ),
    )
    def test_ensure_directory_fails_if_file_exists(self, dirname: str) -> None:
        """Property: ensure_directory fails if path exists as a file.

        Given: A file path (not directory)
        When: Calling ensure_directory
        Then: ValueError is raised
        """
        validator = PathValidator()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file at the target path
            file_path = Path(tmpdir) / dirname
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("test")

            # When/Then: ensure_directory raises ValueError
            with pytest.raises(ValueError, match="not a directory"):
                validator.ensure_directory(file_path)
