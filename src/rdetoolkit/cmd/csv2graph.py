"""Command for generating graphs from CSV files."""

from __future__ import annotations

import pathlib
from typing import Literal

import click

from rdetoolkit.graph.api.csv2graph import csv2graph as api_csv2graph
from rdetoolkit.rdelogger import get_logger

logger = get_logger(__name__)


class Csv2GraphCommand:
    """Command to generate graphs from CSV files using the graph API."""

    def __init__(
        self,
        csv_path: pathlib.Path,
        output_dir: pathlib.Path | None = None,
        main_image_dir: pathlib.Path | None = None,
        csv_format: Literal["standard", "transpose", "noheader"] = "standard",
        logy: bool = False,
        logx: bool = False,
        html: bool = False,
        mode: Literal["overlay", "individual"] = "overlay",
        x_col: list[int | str] | None = None,
        y_cols: list[int | str] | None = None,
        direction_cols: list[int | str] | None = None,
        direction_filter: list[str] | None = None,
        direction_colors: dict[str, str] | None = None,
        title: str | None = None,
        legend_info: str | None = None,
        legend_loc: str | None = None,
        xlim: tuple[float, float] | None = None,
        ylim: tuple[float, float] | None = None,
        grid: bool = False,
        invert_x: bool = False,
        invert_y: bool = False,
        no_individual: bool = False,
        max_legend_items: int | None = None,
    ) -> None:
        """Initialize Csv2GraphCommand.

        Args:
            csv_path: Path to CSV file
            output_dir: Output directory for plots
            main_image_dir: Directory to write combined plots (if provided)
            csv_format: CSV format type
            logy: Use log scale for y-axis
            logx: Use log scale for x-axis
            html: Generate HTML output
            mode: Plotting mode
            x_col: X-axis column specification
            y_cols: Y-axis column specifications
            direction_cols: Direction column specifications
            direction_filter: Direction filter list
            direction_colors: Direction color mapping
            title: Plot title
            legend_info: Legend information
            legend_loc: Legend location
            xlim: X-axis limits
            ylim: Y-axis limits
            grid: Show grid
            invert_x: Invert x-axis
            invert_y: Invert y-axis
            no_individual: Skip individual plots
            max_legend_items: Maximum legend items
        """
        self.csv_path = csv_path
        self.output_dir = output_dir
        self.main_image_dir = main_image_dir
        self.csv_format = csv_format
        self.logy = logy
        self.logx = logx
        self.html = html
        self.mode = mode
        self.x_col = x_col
        self.y_cols = y_cols
        self.direction_cols = direction_cols
        self.direction_filter = direction_filter
        self.direction_colors = direction_colors
        self.title = title
        self.legend_info = legend_info
        self.legend_loc = legend_loc
        self.xlim = xlim
        self.ylim = ylim
        self.grid = grid
        self.invert_x = invert_x
        self.invert_y = invert_y
        self.no_individual = no_individual
        self.max_legend_items = max_legend_items

    def invoke(self) -> None:
        """Execute the csv2graph command.

        Raises:
            click.Abort: If an error occurs during graph generation
        """
        click.echo("📊 Generating graphs from CSV...")
        click.echo(f"- CSV file: {self.csv_path}")
        click.echo(f"- Output: {self.output_dir or 'same as CSV directory'}")
        if self.main_image_dir:
            click.echo(f"- Main images: {self.main_image_dir}")
        click.echo(f"- Mode: {self.mode}")

        try:
            if not self.csv_path.exists():
                emsg = f"CSV file not found: {self.csv_path}"
                raise FileNotFoundError(emsg)

            api_csv2graph(
                csv_path=self.csv_path,
                output_dir=self.output_dir,
                main_image_dir=self.main_image_dir,
                csv_format=self.csv_format,
                logy=self.logy,
                logx=self.logx,
                html=self.html,
                mode=self.mode,
                x_col=self.x_col,
                y_cols=self.y_cols,
                direction_cols=self.direction_cols,
                direction_filter=self.direction_filter,
                direction_colors=self.direction_colors,
                title=self.title,
                legend_info=self.legend_info,
                legend_loc=self.legend_loc,
                xlim=self.xlim,
                ylim=self.ylim,
                grid=self.grid,
                invert_x=self.invert_x,
                invert_y=self.invert_y,
                no_individual=self.no_individual,
                max_legend_items=self.max_legend_items,
            )

            output_location = self.output_dir if self.output_dir else self.csv_path.parent
            click.echo(click.style(f"✨ Graphs generated successfully in: {output_location}", fg="green"))

        except FileNotFoundError as e:
            logger.error(f"File error: {e}")
            click.echo(click.style(f"🔥 File Error: {e}", fg="red"))
            raise click.Abort from e
        except ValueError as e:
            logger.error(f"Value error: {e}")
            click.echo(click.style(f"🔥 Value Error: {e}", fg="red"))
            raise click.Abort from e
        except Exception as e:
            logger.exception(e)
            click.echo(click.style(f"🔥 Unexpected error: {e}", fg="red"))
            raise click.Abort from e
