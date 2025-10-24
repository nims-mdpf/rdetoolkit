# API Documentation

## Purpose

This section provides comprehensive API documentation for RDEToolKit modules. The documentation combines auto-generated content from Python docstrings with manual explanations and practical usage examples.

## Core Modules

- [workflows](./workflows.md): Module for defining and managing workflows in structured data processing.
- [config](./config.md): Module for loading and managing configuration files.
- [fileops](./fileops.md): Module providing RDE-related file operations.
- [rde2util](./rde2util.md): Module providing RDE-related utility functions.
- [invoicefile](./invoicefile.md): Module for processing invoice files.
- [validation](./validation.md): Module for data validation and verification.
- [modeproc](./modeproc.md): Module for mode processing operations.
- [img2thumb](./img2thumb.md): Module for converting images to thumbnails.
- [rdelogger](./rdelogger.md): Module providing logging functionality.
- [exceptions](./exceptions.md): Module for exception handling.
- [errors](./errors.md): Module for error handling and exception management.
- [traceback](./traceback/index.md): Module for LLM/AI-friendly stacktrace formatting.
- [core](./core.md): Core functionality module.

## Data Models

- [config](./models/config.md): Configuration file loading and management models.
- [invoice_schema](./models/invoice_schema.md): Invoice schema definition models.
- [invoice](./models/invoice.md): Invoice and Excel invoice information models.
- [metadata](./models/metadata.md): Metadata management models.
- [rde2types](./models/rde2types.md): RDE-related type definitions.
- [result](./models/result.md): Processing result management models.

## Implementation

- [compressed_controller](./impl/compressed_controller.md): Compressed file management implementation.
- [input_controller](./impl/input_controller.md): Input mode management implementation.

## Interfaces

- [filechecker](./interface/filechecker.md): File checking interface definitions.

## Commands

- [command](./cmd/command.md): Base command implementations.
- [gen_config](./cmd/gen_config.md): CLI for generating validated configuration templates.

## Storage & Artifacts

- [minio](./storage/minio.md): MinIO object storage integration.
- [report](./artifact/report.md): Report generation functionality.

---

## Getting Started

Each module documentation includes:

- **Purpose**: Overview of the module's functionality
- **Key Features**: Main capabilities and features
- **Auto-generated API**: Complete function and class documentation from docstrings
- **Practical Usage**: Code examples and real-world usage patterns

Navigate to any module above to explore its detailed API documentation.
