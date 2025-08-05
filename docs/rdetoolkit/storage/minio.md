# MinIO Storage API

## Purpose

This module defines integration processing with MinIO object storage in RDEToolKit. It provides functionality for file upload, download, and object management.

## Key Features

### Object Storage Operations
- File upload and download
- Object listing and deletion
- Bucket management and access control

### Data Management
- Efficient transfer of large files
- Metadata management
- Version control and backup

---

::: src.rdetoolkit.storage.minio.MinIOStorage

---

## Practical Usage

### Basic MinIO Operations

```python title="basic_minio_operations.py"
from rdetoolkit.storage.minio import MinIOStorage
from pathlib import Path

# Create MinIO storage
storage = MinIOStorage(
    endpoint="localhost:9000",
    access_key="minioadmin",
    secret_key="minioadmin",
    secure=False
)

# Bucket name
bucket_name = "rde-experiments"

try:
    # Create bucket
    if not storage.bucket_exists(bucket_name):
        storage.make_bucket(bucket_name)
        print(f"✓ Bucket created: {bucket_name}")
    
    # Upload file
    local_file = Path("data/experiment_001.csv")
    object_name = "experiments/2024/experiment_001.csv"
    
    if local_file.exists():
        upload_result = storage.fput_object(
            bucket_name=bucket_name,
            object_name=object_name,
            file_path=str(local_file)
        )
        print(f"✓ Upload completed: {upload_result}")
    
    # Get object information
    object_stat = storage.stat_object(bucket_name, object_name)
    print(f"Object information: {object_stat}")
    
    # Download file
    download_path = Path("downloads/experiment_001.csv")
    download_path.parent.mkdir(parents=True, exist_ok=True)
    
    storage.fget_object(
        bucket_name=bucket_name,
        object_name=object_name,
        file_path=str(download_path)
    )
    print(f"✓ Download completed: {download_path}")

except Exception as e:
    print(f"✗ MinIO operation error: {e}")
```

### Batch Experimental Data Management

```python title="experiment_data_management.py"
from rdetoolkit.storage.minio import MinIOStorage
from pathlib import Path
from typing import List, Dict
import json
from datetime import datetime

class ExperimentDataManager:
    """Experimental data management system"""
    
    def __init__(self, storage: MinIOStorage, bucket_name: str):
        self.storage = storage
        self.bucket_name = bucket_name
        
        # Create bucket
        if not self.storage.bucket_exists(bucket_name):
            self.storage.make_bucket(bucket_name)
    
    def upload_experiment(self, experiment_id: str, data_dir: Path) -> Dict:
        """Batch upload of experimental data"""
        
        if not data_dir.exists():
            raise ValueError(f"Data directory does not exist: {data_dir}")
        
        upload_results = {
            "experiment_id": experiment_id,
            "upload_time": datetime.now().isoformat(),
            "uploaded_files": [],
            "failed_files": [],
            "total_size": 0
        }
        
        # Get all files in data directory
        all_files = []
        for pattern in ["**/*.csv", "**/*.json", "**/*.xlsx", "**/*.jpg", "**/*.png"]:
            all_files.extend(data_dir.glob(pattern))
        
        print(f"Starting upload for experiment {experiment_id}: {len(all_files)} files")
        
        for file_path in all_files:
            if file_path.is_file():
                try:
                    # Generate object name
                    relative_path = file_path.relative_to(data_dir)
                    object_name = f"experiments/{experiment_id}/{relative_path}"
                    
                    # Get file size
                    file_size = file_path.stat().st_size
                    
                    # Execute upload
                    result = self.storage.fput_object(
                        bucket_name=self.bucket_name,
                        object_name=object_name,
                        file_path=str(file_path)
                    )
                    
                    upload_results["uploaded_files"].append({
                        "local_path": str(file_path),
                        "object_name": object_name,
                        "size": file_size,
                        "etag": result.etag if hasattr(result, 'etag') else None
                    })
                    
                    upload_results["total_size"] += file_size
                    print(f"✓ Uploaded: {relative_path}")
                    
                except Exception as e:
                    upload_results["failed_files"].append({
                        "local_path": str(file_path),
                        "error": str(e)
                    })
                    print(f"✗ Upload failed: {file_path} - {e}")
        
        return upload_results

# Usage example
storage = MinIOStorage(
    endpoint="localhost:9000",
    access_key="minioadmin",
    secret_key="minioadmin"
)

manager = ExperimentDataManager(storage, "rde-experiments")
result = manager.upload_experiment("EXP001", Path("data/experiment_001"))
print(f"Upload result: {result}")
```
