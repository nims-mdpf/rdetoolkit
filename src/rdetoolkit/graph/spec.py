"""Versioned, backend-neutral graph specification types (GE-03).

A ``GraphSpec`` says WHAT to plot (columns, labels, units, axes, legend, layout); an
``OutputSpec`` says WHERE the artifacts go. Neither knows about Matplotlib, Plotly or a
file format beyond its name, so the same spec can be planned, snapshotted and rendered
by any backend.

Every spec type is a frozen value: incoming mappings are copied into read-only
proxies and sequences into tuples, so a spec cannot change after it was validated.
Invalid values raise ``PlotRequestError(reason="invalid_spec")`` at construction,
before anything is planned, rendered or written.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from numbers import Integral
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final, Literal

from rdetoolkit.graph.exceptions import PlotRequestError
from rdetoolkit.graph.legend_policy import VALID_LEGEND_POLICIES

if TYPE_CHECKING:
    from rdetoolkit.graph.outputs import ArtifactSink

SPEC_VERSION: Final = 1
ColumnRef = int | str
AxisLimits = tuple[float | None, float | None]
Origin = Literal["explicit", "default", "derived"]

INVALID_SPEC: Final = "invalid_spec"
_LAYOUTS: Final = ("auto", "overlay", "individual", "both")
_MARKS: Final = ("line", "scatter")
_X_DEFAULTS: Final = ("first_column", "index")
_LABEL_STYLES: Final = ("humanized", "header", "raw")
_UNIT_POLICIES: Final = ("error", "split", "warn", "allow")
_SCALES: Final = ("linear", "log")
_TICK_FORMATS: Final = ("auto", "plain", "sci", "eng")
_ON_EXISTING: Final = ("overwrite", "error")


def _check_choice(value: object, choices: Iterable[str], name: str) -> None:
    """Reject a value outside its Literal choices (static typing does not reach callers)."""
    allowed = tuple(choices)
    if not isinstance(value, str) or value not in allowed:
        msg = f"Invalid {name}: {value!r}. Choose from {list(allowed)}"
        raise PlotRequestError(msg, reason=INVALID_SPEC)


def _check_column_ref(instance: object, field_name: str, name: str, *, optional: bool) -> None:
    """Reject a column reference that is neither a position (integer) nor a label (str).

    Any ``numbers.Integral`` (``np.int64`` from a NumPy computation, for example) is a
    position and is stored as a plain ``int``. ``bool`` is rejected explicitly: it is
    an ``int`` subclass, so ``True`` would otherwise silently address column 1.
    """
    value = getattr(instance, field_name)
    if value is None and optional:
        return
    if isinstance(value, str):
        return
    if isinstance(value, bool) or not isinstance(value, Integral):
        msg = f"{name} must be a column position (int) or label (str), got {value!r}"
        raise TypeError(msg)
    object.__setattr__(instance, field_name, int(value))


def _freeze_mapping(instance: object, name: str, value: Mapping[Any, Any]) -> None:
    """Replace a mapping field by a read-only copy so the frozen value stays frozen."""
    if not isinstance(value, Mapping):
        msg = f"{name} must be a mapping, got {type(value).__name__}"
        raise PlotRequestError(msg, reason=INVALID_SPEC)
    object.__setattr__(instance, name, MappingProxyType(dict(value)))


def _normalize_formats(formats: Iterable[object]) -> tuple[str, ...]:
    """Lower-case and de-duplicate output formats, keeping their first-seen order."""
    normalized: list[str] = []
    for fmt in tuple(formats):
        if not isinstance(fmt, str) or not fmt.strip():
            msg = f"formats must be non-empty strings, got {fmt!r}"
            raise PlotRequestError(msg, reason=INVALID_SPEC)
        value = fmt.strip().lower()
        if value not in normalized:
            normalized.append(value)
    if not normalized:
        msg = "OutputSpec.formats must name at least one format"
        raise PlotRequestError(msg, reason=INVALID_SPEC)
    return tuple(normalized)


@dataclass(frozen=True, slots=True)
class SeriesSpec:
    """One y series to plot.

    Attributes:
        y: Column of the y values (0-based position or label).
        x: Column of the x values; ``None`` uses ``GraphSpec.x``.
        direction: Optional column whose values split the series into segments.
        label: Explicit legend label; ``None`` derives it from the header.
        unit: Explicit unit; overrides the unit parsed from the header.
    """

    y: ColumnRef
    x: ColumnRef | None = None
    direction: ColumnRef | None = None
    label: str | None = None
    unit: str | None = None

    def __post_init__(self) -> None:
        """Validate the column references."""
        _check_column_ref(self, "y", "SeriesSpec.y", optional=False)
        _check_column_ref(self, "x", "SeriesSpec.x", optional=True)
        _check_column_ref(self, "direction", "SeriesSpec.direction", optional=True)


@dataclass(frozen=True, slots=True)
class AxisSpec:
    """Axis settings shared by every figure of a plan.

    Attributes:
        label: Explicit axis label; ``None`` derives it from the header.
        scale: ``"linear"`` or ``"log"``.
        limits: ``(min, max)``; a ``None`` side stays automatic.
        grid: Whether grid lines are drawn for this axis.
        invert: Whether the axis direction is inverted.
        tick_format: Tick label formatter (``"auto"``, ``"plain"``, ``"sci"``, ``"eng"``).
    """

    label: str | None = None
    scale: Literal["linear", "log"] = "linear"
    limits: AxisLimits | None = None
    grid: bool = False
    invert: bool = False
    tick_format: Literal["auto", "plain", "sci", "eng"] = "auto"

    def __post_init__(self) -> None:
        """Validate the choice fields and normalize ``limits`` to a tuple."""
        _check_choice(self.scale, _SCALES, "scale")
        _check_choice(self.tick_format, _TICK_FORMATS, "tick_format")
        if self.limits is not None:
            limits = tuple(self.limits)
            if len(limits) != 2:  # noqa: PLR2004 - (min, max) pair
                msg = f"limits must be a (min, max) pair, got {self.limits!r}"
                raise PlotRequestError(msg, reason=INVALID_SPEC)
            object.__setattr__(self, "limits", limits)


@dataclass(frozen=True, slots=True)
class LegendSpec:
    """Legend settings; field names are identical to ``LegendConfig``.

    Attributes:
        max_items: Hide the legend above this many entries (``None`` = no limit).
        info: Extra text drawn next to the legend.
        loc: Matplotlib legend location.
        policy: Placement policy (see ``LegendConfig.policy``).
        outside_threshold: Entry count above which ``"auto"`` moves the legend outside.
        bottom_threshold: Entry count at which ``"auto"`` moves the legend below.
        ncol: Column count of an outside-bottom legend.
    """

    max_items: int | None = 20
    info: str | None = None
    loc: str | int | None = None
    policy: Literal["legacy", "auto", "inside", "outside_right", "outside_bottom", "hide"] = "legacy"
    outside_threshold: int = 8
    bottom_threshold: int | None = 21
    ncol: int | None = None

    def __post_init__(self) -> None:
        """Validate the policy with the legacy message text."""
        if self.policy not in VALID_LEGEND_POLICIES:
            msg = f"Invalid legend policy: {self.policy!r}. Choose from {list(VALID_LEGEND_POLICIES)}"
            raise PlotRequestError(msg, reason=INVALID_SPEC)


@dataclass(frozen=True, slots=True)
class StyleSpec:
    """Figure size and Matplotlib style overrides.

    Attributes:
        figure_size: ``(width, height)`` in inches; ``None`` uses the engine default.
        rc_params: Matplotlib rcParams applied over the engine defaults.
    """

    figure_size: tuple[float, float] | None = None
    rc_params: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Freeze ``rc_params`` and normalize ``figure_size`` to a tuple."""
        _freeze_mapping(self, "rc_params", self.rc_params)
        if self.figure_size is not None:
            size = tuple(self.figure_size)
            if len(size) != 2:  # noqa: PLR2004 - (width, height) pair
                msg = f"figure_size must be a (width, height) pair, got {self.figure_size!r}"
                raise PlotRequestError(msg, reason=INVALID_SPEC)
            object.__setattr__(self, "figure_size", size)


@dataclass(frozen=True, slots=True)
class GraphSpec:
    """What to plot, independent of any backend or output format.

    ``layout`` replaces the legacy ``mode`` x ``no_individual`` pair so that a
    combination producing no figure cannot be written: ``auto`` = overlay plus one
    figure per series when there is more than one series; ``overlay`` = overlay
    only; ``individual`` = one figure per series only; ``both`` = both.

    Attributes:
        version: Spec schema version; must equal ``SPEC_VERSION``.
        x: Default x column for every series.
        x_default: Meaning of ``x=None``: the first column or the frame index.
        series: Series to plot; ``()`` plots every column except the x column.
        layout: Which figures to produce.
        mark: ``"line"`` or ``"scatter"``.
        title: Figure title; ``None`` draws no overlay title.
        x_axis: X axis settings.
        y_axis: Y axis settings.
        legend: Legend settings.
        direction_filter: Direction values to draw (``()`` = all).
        direction_colors: Colour per direction value.
        label_style: ``humanized`` (header humanized), ``header`` (header as
            written, unit stripped) or ``raw`` (``str(column)``).
        unit_policy: What to do with mixed units in one overlay.
        style: Figure size and rcParams overrides.
    """

    version: int = SPEC_VERSION
    x: ColumnRef | None = None
    x_default: Literal["first_column", "index"] = "first_column"
    series: tuple[SeriesSpec, ...] = ()
    layout: Literal["auto", "overlay", "individual", "both"] = "auto"
    mark: Literal["line", "scatter"] = "line"
    title: str | None = None
    x_axis: AxisSpec = AxisSpec()
    y_axis: AxisSpec = AxisSpec()
    legend: LegendSpec = LegendSpec()
    direction_filter: tuple[str, ...] = ()
    direction_colors: Mapping[str, str] = field(default_factory=dict)
    label_style: Literal["humanized", "header", "raw"] = "humanized"
    unit_policy: Literal["error", "split", "warn", "allow"] = "error"
    style: StyleSpec = StyleSpec()

    def __post_init__(self) -> None:
        """Validate the spec and freeze its containers.

        Raises:
            PlotRequestError: ``reason="invalid_spec"`` for an unsupported version or
                choice value; ``reason="contradictory_switches"`` for an explicit
                ``x`` combined with ``x_default="index"``.
            TypeError: If ``x`` or a series entry has the wrong type.
        """
        if isinstance(self.version, bool) or self.version != SPEC_VERSION:
            msg = f"Unsupported GraphSpec version {self.version!r}; this release supports {SPEC_VERSION}"
            raise PlotRequestError(msg, reason=INVALID_SPEC)
        _check_column_ref(self, "x", "GraphSpec.x", optional=True)
        self._check_choices()
        if self.x is not None and self.x_default == "index":
            msg = "GraphSpec.x and x_default='index' contradict each other; drop one of them"
            raise PlotRequestError(msg, reason="contradictory_switches")
        self._freeze_containers()

    def _check_choices(self) -> None:
        _check_choice(self.x_default, _X_DEFAULTS, "x_default")
        _check_choice(self.layout, _LAYOUTS, "layout")
        _check_choice(self.mark, _MARKS, "mark")
        _check_choice(self.label_style, _LABEL_STYLES, "label_style")
        _check_choice(self.unit_policy, _UNIT_POLICIES, "unit_policy")

    def _freeze_containers(self) -> None:
        series = tuple(self.series)
        for entry in series:
            if not isinstance(entry, SeriesSpec):
                msg = f"GraphSpec.series entries must be SeriesSpec, got {type(entry).__name__}"
                raise TypeError(msg)
        object.__setattr__(self, "series", series)
        object.__setattr__(self, "direction_filter", tuple(str(value) for value in self.direction_filter))
        _freeze_mapping(self, "direction_colors", self.direction_colors)


@dataclass(frozen=True, slots=True)
class OutputSpec:
    """Where and how the artifacts of a plan are written.

    Attributes:
        sink: Destination of the artifact bytes (for example a ``DirectorySink``).
        formats: File formats per figure, in output order (lower-cased, de-duplicated).
        base_name: Base file name; the overlay stem and the prefix of every
            individual stem.
        on_existing: ``"overwrite"`` (recorded in the result) or ``"error"`` (fail
            before anything is rendered when a destination already exists).
        dpi: Raster resolution.
    """

    sink: ArtifactSink
    formats: tuple[str, ...] = ("png",)
    base_name: str = "plot"
    on_existing: Literal["overwrite", "error"] = "overwrite"
    dpi: int = 300

    def __post_init__(self) -> None:
        """Validate and normalize the output settings.

        Raises:
            PlotRequestError: ``reason="invalid_spec"`` for no formats, a non-string
                format, an empty base name, a non-positive dpi or an unknown
                ``on_existing`` value.
        """
        object.__setattr__(self, "formats", _normalize_formats(self.formats))
        if not isinstance(self.base_name, str) or not self.base_name:
            msg = f"base_name must be a non-empty string, got {self.base_name!r}"
            raise PlotRequestError(msg, reason=INVALID_SPEC)
        if isinstance(self.dpi, bool) or not isinstance(self.dpi, int) or self.dpi <= 0:
            msg = f"dpi must be a positive int, got {self.dpi!r}"
            raise PlotRequestError(msg, reason=INVALID_SPEC)
        _check_choice(self.on_existing, _ON_EXISTING, "on_existing")
