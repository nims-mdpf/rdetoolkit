from __future__ import annotations

from pathlib import Path


class PathValidator:
    """Validator for file path security and existence checks.

    This class provides security validation to prevent:
        - Path traversal attacks (../)
        - Writing outside designated directories
        - Invalid/unsafe filenames
        - Permission issues

    Example:
        >>> validator = PathValidator()
        >>> output_dir = Path("/safe/output/dir")
        >>> filename = "plot_data.png"
        >>> validator.validate(output_dir, filename)
        PosixPath('/safe/output/dir/plot_data.png')
    """

    def validate(self, output_dir: Path, filename: str) -> Path:
        """Validate output path for security and accessibility.

        Args:
            output_dir: Directory where file will be saved
            filename: Name of file to save (without directory)

        Returns:
            Validated absolute Path object

        Raises:
            ValueError: If path validation fails (security/existence)
            PermissionError: If output_dir is not writable

        Security:
            - Prevents path traversal (../ sequences)
            - Ensures output stays within output_dir
            - Validates directory existence and permissions
        """
        output_dir = output_dir.resolve()

        if ".." in filename or "/" in filename or "\\" in filename:
            msg = (
                "Invalid filename "
                f"{filename!r}: contains path separators or '..' sequence"
            )
            raise ValueError(msg)

        full_path = (output_dir / filename).resolve()

        if not str(full_path).startswith(str(output_dir)):
            msg = (
                "Security violation: "
                f"{filename!r} would write outside output directory"
            )
            raise ValueError(msg)

        if not output_dir.exists():
            msg = f"Output directory does not exist: {output_dir}"
            raise ValueError(msg)

        if not output_dir.is_dir():
            msg = f"Output path is not a directory: {output_dir}"
            raise ValueError(msg)

        return full_path

    def ensure_directory(self, directory: Path) -> Path:
        """Ensure directory exists, create if needed.

        Args:
            directory: Directory path to ensure

        Returns:
            Resolved absolute Path object

        Raises:
            PermissionError: If directory creation fails due to permissions
            OSError: If directory creation fails for other reasons
        """
        directory = directory.resolve()

        if not directory.exists():
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except (PermissionError, OSError) as e:
                msg = f"Failed to create directory: {directory}"
                raise PermissionError(msg) from e

        return directory
