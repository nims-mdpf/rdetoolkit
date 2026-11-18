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
        full_path = self.resolve_within(output_dir, filename)
        output_dir = output_dir.resolve()

        if not output_dir.exists():
            msg = f"Output directory does not exist: {output_dir}"
            raise ValueError(msg)

        if not output_dir.is_dir():
            msg = f"Output path is not a directory: {output_dir}"
            raise ValueError(msg)

        return full_path

    def resolve_within(self, output_dir: Path, filename: str) -> Path:
        """Resolve ``filename`` inside ``output_dir`` and prove it stays there.

        Containment is decided on path components (``Path.relative_to``), never on a
        string prefix: ``/out2/x`` is outside ``/out`` although its text starts with
        ``/out``, which matters when a symlink inside the directory points to a
        sibling. The directory does not have to exist, so every destination of a
        run can be checked before anything is written.

        Args:
            output_dir: Directory the file must stay in.
            filename: Name of the file (without directory).

        Returns:
            The fully resolved destination (symlinks followed).

        Raises:
            ValueError: If the name contains a separator or ``..``, or the resolved
                destination is outside the resolved directory.
        """
        output_dir = output_dir.resolve()

        if ".." in filename or "/" in filename or "\\" in filename:
            msg = (
                "Invalid filename "
                f"{filename!r}: contains path separators or '..' sequence"
            )
            raise ValueError(msg)

        full_path = (output_dir / filename).resolve()

        try:
            full_path.relative_to(output_dir)
        except ValueError:
            msg = (
                "Security violation: "
                f"{filename!r} would write outside output directory"
            )
            raise ValueError(msg) from None

        return full_path

    def ensure_directory(self, directory: Path) -> Path:
        """Ensure directory exists, create if needed.

        Args:
            directory: Directory path to ensure

        Returns:
            Resolved absolute Path object

        Raises:
            ValueError: If path exists and is not a directory
            PermissionError: If directory creation fails due to permissions
            OSError: If directory creation fails for other reasons
        """
        directory = directory.resolve()

        if directory.exists() and not directory.is_dir():
            msg = f"Output path is not a directory: {directory}"
            raise ValueError(msg)

        if not directory.exists():
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except (PermissionError, OSError) as e:
                msg = f"Failed to create directory: {directory}"
                raise PermissionError(msg) from e

        return directory
