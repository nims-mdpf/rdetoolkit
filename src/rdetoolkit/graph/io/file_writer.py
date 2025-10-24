from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from matplotlib.figure import Figure

from rdetoolkit.graph.io.path_validator import PathValidator


class FileWriter:
    """File writer for graph figures with security validation.

    Handles saving matplotlib and plotly figures to disk with:
        - Path validation and security checks
        - Automatic directory creation
        - Format-specific saving logic
        - Error handling and reporting

    Example:
        >>> from matplotlib import pyplot as plt
        >>> fig, ax = plt.subplots()
        >>> ax.plot([1, 2, 3], [1, 4, 9])
        >>> writer = FileWriter()
        >>> writer.save_matplotlib(fig, Path("/output"), "plot.png")
    """

    def __init__(self, validator: PathValidator | None = None) -> None:
        """Initialize FileWriter with optional validator.

        Args:
            validator: PathValidator instance (creates default if None)
        """
        self.validator = validator if validator is not None else PathValidator()

    def save_matplotlib(
        self,
        figure: Figure,
        output_dir: Path,
        filename: str,
        dpi: int = 300,
        **kwargs: Any,
    ) -> Path:
        """Save matplotlib figure to file.

        Args:
            figure: Matplotlib Figure object to save
            output_dir: Directory where file will be saved
            filename: Output filename (e.g., "plot.png")
            dpi: Resolution in dots per inch (default: 300)
            **kwargs: Additional arguments passed to figure.savefig()

        Returns:
            Path object of saved file

        Raises:
            ValueError: If path validation fails
            PermissionError: If output directory is not writable
            OSError: If file save operation fails

        Example:
            >>> fig, ax = plt.subplots()
            >>> writer.save_matplotlib(fig, Path("/out"), "test.png", dpi=150)
        """
        output_dir = self.validator.ensure_directory(output_dir)
        output_path = self.validator.validate(output_dir, filename)
        try:
            figure.savefig(output_path, dpi=dpi, bbox_inches="tight", **kwargs)
        except (OSError, ValueError) as e:
            msg = f"Failed to save matplotlib figure to {output_path}"
            raise OSError(msg) from e

        return output_path

    def save_plotly_html(
        self,
        figure: Any,
        output_dir: Path,
        filename: str,
        **kwargs: Any,
    ) -> Path:
        """Save plotly figure to HTML file.

        Args:
            figure: Plotly Figure object to save
            output_dir: Directory where file will be saved
            filename: Output filename (e.g., "plot.html")
            **kwargs: Additional arguments passed to figure.write_html()

        Returns:
            Path object of saved file

        Raises:
            ValueError: If path validation fails
            PermissionError: If output directory is not writable
            OSError: If file save operation fails

        Example:
            >>> import plotly.graph_objs as go
            >>> fig = go.Figure(data=[go.Scatter(x=[1,2,3], y=[1,4,9])])
            >>> writer.save_plotly_html(fig, Path("/out"), "plot.html")
        """
        output_dir = self.validator.ensure_directory(output_dir)
        output_path = self.validator.validate(output_dir, filename)
        try:
            figure.write_html(output_path, **kwargs)
        except (OSError, ValueError, AttributeError) as e:
            msg = f"Failed to save plotly figure to {output_path}"
            raise OSError(msg) from e

        return output_path

    def save_figure(
        self,
        figure: Any,
        output_dir: Path,
        filename: str,
        format_type: str = "png",
        **kwargs: Any,
    ) -> Path:
        """Save figure with automatic format detection.

        Dispatches to appropriate save method based on format_type.

        Args:
            figure: Figure object (matplotlib or plotly)
            output_dir: Directory where file will be saved
            filename: Output filename
            format_type: Output format ("png", "svg", "html", etc.)
            **kwargs: Additional arguments for save method

        Returns:
            Path object of saved file

        Raises:
            ValueError: If format is not supported or path validation fails
            PermissionError: If output directory is not writable
            OSError: If file save operation fails
        """
        format_lower = format_type.lower()

        if format_lower == "html":
            return self.save_plotly_html(figure, output_dir, filename, **kwargs)
        dpi = kwargs.pop("dpi", 300)
        return self.save_matplotlib(
            figure, output_dir, filename, dpi=dpi, **kwargs,
        )
