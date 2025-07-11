"""Test fixtures for ProcessingContext."""

from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Generator
from unittest.mock import MagicMock

import pytest

from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath
from rdetoolkit.processing.context import ProcessingContext
from rdetoolkit.models.rde2types import create_default_config


@pytest.fixture
def rde_input_paths():
    """Create a real RdeInputDirPaths object."""

    config = create_default_config()

    yield RdeInputDirPaths(
        inputdata=Path("data/inputdata"),
        invoice=Path("data/invoice"),
        tasksupport=Path("data/tasksupport"),
        config=config
    )


@pytest.fixture
def rde_output_paths():
    """Create a real RdeOutputResourcePath object."""
    return RdeOutputResourcePath(
        raw=Path("data/raw"),
        nonshared_raw=Path("data/nonshared_raw"),
        main_image=Path("data/main_image"),
        other_image=Path("data/other_image"),
        thumbnail=Path("data/thumbnail"),
        meta=Path("data/meta"),
        struct=Path("data/structured"),
        logs=Path("data/logs"),
        invoice=Path("data/invoice"),
        invoice_schema_json=Path("data/tasksupport/invoice.schema.json"),
        rawfiles=(
            Path("data", "inputdata", "test_single.txt"),
        ),
        invoice_org=Path("data/invoice/invoice.json"),
    )


@pytest.fixture
def rde_output_paths_rdeformat():
    """Create a real RdeOutputResourcePath object."""
    context = RdeOutputResourcePath(
        raw=Path("data/raw"),
        nonshared_raw=Path("data/nonshared_raw"),
        main_image=Path("data/main_image"),
        other_image=Path("data/other_image"),
        thumbnail=Path("data/thumbnail"),
        meta=Path("data/meta"),
        struct=Path("data/structured"),
        logs=Path("data/logs"),
        invoice=Path("data/invoice"),
        invoice_schema_json=Path("data/tasksupport/invoice.schema.json"),
        rawfiles=(
            Path("data", "temp", "inputdata", "test_child1.txt"),
            Path("data", "temp", "structured", "test.csv"),
            Path("data", "temp", "raw", "test_child1.txt")
        ),
        invoice_org=Path("data/invoice/invoice.json"),
    )
    return context


@pytest.fixture
def mock_datasets_function():
    """Create a mock datasets function."""
    return MagicMock()


@pytest.fixture
def basic_processing_context(rde_input_paths, rde_output_paths, mock_datasets_function):
    """Create a basic ProcessingContext for testing."""
    return ProcessingContext(
        index="0001",
        srcpaths=rde_input_paths,
        resource_paths=rde_output_paths,
        datasets_function=mock_datasets_function,
        mode_name="test_mode"
    )


@pytest.fixture
def rdeformat_processing_context(rde_input_paths, rde_output_paths_rdeformat, mock_datasets_function):
    """Create a ProcessingContext for RDEFormat mode testing."""
    return ProcessingContext(
        index="0001",
        srcpaths=rde_input_paths,
        resource_paths=rde_output_paths_rdeformat,
        datasets_function=mock_datasets_function,
        mode_name="rdeformat"
    )


@pytest.fixture
def multifile_processing_context(rde_input_paths, rde_output_paths, mock_datasets_function):
    """Create a ProcessingContext for MultiFile mode testing."""
    return ProcessingContext(
        index="0001",
        srcpaths=rde_input_paths,
        resource_paths=rde_output_paths,
        datasets_function=mock_datasets_function,
        mode_name="MultiDataTile"
    )


@pytest.fixture
def excel_processing_context(rde_input_paths, rde_output_paths, mock_datasets_function):
    """Create a ProcessingContext for ExcelInvoice mode testing."""
    return ProcessingContext(
        index="0001",
        srcpaths=rde_input_paths,
        resource_paths=rde_output_paths,
        datasets_function=mock_datasets_function,
        mode_name="Excelinvoice",
        excel_file=Path("data/inputdata/test_excel_invoice.xlsx")
    )


@pytest.fixture
def invoice_processing_context(rde_input_paths, rde_output_paths, mock_datasets_function):
    """Create a ProcessingContext for Invoice mode testing."""
    return ProcessingContext(
        index="0001",
        srcpaths=rde_input_paths,
        resource_paths=rde_output_paths,
        datasets_function=mock_datasets_function,
        mode_name="invoice"
    )


@pytest.fixture
def processing_context_no_rawfiles(rde_input_paths, rde_output_paths, mock_datasets_function):
    """Create a ProcessingContext with no raw files."""
    rde_output_paths.rawfiles = ()
    return ProcessingContext(
        index="0001",
        srcpaths=rde_input_paths,
        resource_paths=rde_output_paths,
        datasets_function=mock_datasets_function,
        mode_name="test_mode"
    )


@pytest.fixture
def processing_context_disabled_features(rde_input_paths, rde_output_paths, mock_datasets_function):
    """Create a ProcessingContext with disabled features."""
    rde_input_paths.config.system.save_raw = False
    rde_input_paths.config.system.save_nonshared_raw = False
    rde_input_paths.config.system.magic_variable = False
    rde_input_paths.config.system.save_thumbnail_image = False

    return ProcessingContext(
        index="0001",
        srcpaths=rde_input_paths,
        resource_paths=rde_output_paths,
        datasets_function=mock_datasets_function,
        mode_name="test_mode"
    )


@pytest.fixture
def test_processing_context_mapping(rde_input_paths, rde_output_paths_rdeformat, mock_datasets_function) -> Generator[ProcessingContext, None, None]:
    """テスト用のProcessingContextを作成（一時ディレクトリ付きかつ、マッピングテスト用）"""
    with tempfile.TemporaryDirectory() as temp_dir:
        base_path = Path(temp_dir)
        context = ProcessingContext(
            index="0001",
            srcpaths=rde_input_paths,
            resource_paths=rde_output_paths_rdeformat,
            datasets_function=mock_datasets_function,
            mode_name="rdeformat"
        )

        context.resource_paths.raw = base_path / "raw"
        context.resource_paths.main_image = base_path / "main_image"
        context.resource_paths.other_image = base_path / "other_image"
        context.resource_paths.meta = base_path / "meta"
        context.resource_paths.struct = base_path / "structured"
        context.resource_paths.logs = base_path / "logs"
        context.resource_paths.nonshared_raw = base_path / "nonshared_raw"

        for path in [context.resource_paths.raw, context.resource_paths.main_image, context.resource_paths.other_image, context.resource_paths.meta, context.resource_paths.struct, context.resource_paths.logs, context.resource_paths.nonshared_raw]:
            path.mkdir(parents=True, exist_ok=True)

        yield context


@pytest.fixture
def isolated_processing_context(rde_input_paths, mock_datasets_function) -> Generator[ProcessingContext, None, None]:
    """Create an isolated ProcessingContext with temporary directories for testing.
    
    This fixture creates a completely isolated context with temporary directories
    to prevent test interference and ensure cleanup.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        base_path = Path(temp_dir)
        
        # Create isolated output paths in temp directory
        rde_output_paths = RdeOutputResourcePath(
            raw=base_path / "raw",
            nonshared_raw=base_path / "nonshared_raw",
            main_image=base_path / "main_image",
            other_image=base_path / "other_image",
            thumbnail=base_path / "thumbnail",
            meta=base_path / "meta",
            struct=base_path / "structured",
            logs=base_path / "logs",
            invoice=base_path / "invoice",
            invoice_schema_json=base_path / "tasksupport" / "invoice.schema.json",
            rawfiles=(
                base_path / "inputdata" / "test_single.txt",
            ),
            invoice_org=base_path / "invoice" / "invoice.json",
        )
        
        # Create necessary directories
        for path in [rde_output_paths.raw, rde_output_paths.nonshared_raw, 
                    rde_output_paths.main_image, rde_output_paths.other_image,
                    rde_output_paths.thumbnail, rde_output_paths.meta, 
                    rde_output_paths.struct, rde_output_paths.logs, 
                    rde_output_paths.invoice, base_path / "tasksupport",
                    base_path / "inputdata"]:
            path.mkdir(parents=True, exist_ok=True)
        
        # Create a test file for rawfiles
        (base_path / "inputdata" / "test_single.txt").write_text("test content")
        
        context = ProcessingContext(
            index="0001",
            srcpaths=rde_input_paths,
            resource_paths=rde_output_paths,
            datasets_function=mock_datasets_function,
            mode_name="test_mode"
        )
        
        yield context
