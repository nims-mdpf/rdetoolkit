# MinIO Integration API

## Purpose

This module provides MinIO object storage integration for RDEToolKit. It handles file upload, download, and management operations with MinIO storage systems, enabling cloud-based data storage and retrieval.

## Key Features

### MinIO Operations
- File upload and download operations
- Bucket management and configuration
- Authentication and connection handling

### Storage Integration
- Integration with structured processing workflows
- Batch operations support
- Error handling and retry mechanisms

---

::: src.rdetoolkit.storage.minio

---

## Practical Usage

### Basic MinIO Operations

```python title="minio_operations.py"
from rdetoolkit.storage.minio import MinIOClient
from pathlib import Path

# Initialize MinIO client
client = MinIOClient(
    endpoint="localhost:9000",
    access_key="minioadmin",
    secret_key="minioadmin",
    secure=False
)

# Upload file
local_file = Path("data/sample.json")
bucket_name = "rdetoolkit-data"
object_name = "experiments/sample.json"

result = client.upload_file(local_file, bucket_name, object_name)
print(f"Upload result: {result}")

# Download file
download_path = Path("data/downloaded/sample.json")
result = client.download_file(bucket_name, object_name, download_path)
print(f"Download result: {result}")
```
