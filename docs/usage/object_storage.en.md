# Using Object Storage (MinIO) with RDEToolKit

## Overview

MinIOStorage is a Python interface that makes it easy to integrate with MinIO, an object storage service. You can easily use MinIO's main features such as file upload, download, and metadata retrieval.

## Prerequisites

- Python 3.9 or higher
- Access to MinIO server (endpoint URL, access key, secret key)

## Installation

Since it's provided as part of the rdetoolkit package, you can install it with the following command:

```bash
pip install rdetoolkit[minio]
```

## Basic Usage

### MinIOStorage Instantiation

```python
from rdetoolkit.storage.minio import MinIOStorage

# Method to specify authentication information directly
storage = MinIOStorage(
    endpoint="minio.example.com:9000",
    access_key="your-access-key",
    secret_key="your-secret-key",
    secure=True  # Set to True when using HTTPS
)

# Method to get authentication information from environment variables
import os
os.environ["MINIO_ACCESS_KEY"] = "your-access-key"
os.environ["MINIO_SECRET_KEY"] = "your-secret-key"

storage = MinIOStorage(
    endpoint="minio.example.com:9000",
    # Omitting access_key and secret_key will read from environment variables
)
```

### Bucket Operations

#### Create Bucket

```python
storage.make_bucket("my-bucket", location="us-east-1")
```

#### List Buckets

```python
buckets = storage.list_buckets()
for bucket in buckets:
    print(f"Bucket name: {bucket['name']}, Creation date: {bucket['creation_date']}")
```

#### Check Bucket Existence

```python
if storage.bucket_exists("my-bucket"):
    print("Bucket exists")
else:
    print("Bucket does not exist")
```

#### Remove Bucket

```python
storage.remove_bucket("my-bucket")  # Bucket must be empty
```

### Object Operations

#### Upload Object (from memory data)

```python
# Upload from string
data = "Hello, MinIO!"
storage.put_object(
    bucket_name="my-bucket",
    object_name="hello.txt",
    data=data,
    length=len(data),
    content_type="text/plain"
)

# Upload from binary data
binary_data = b"\x00\x01\x02\x03"
storage.put_object(
    bucket_name="my-bucket",
    object_name="binary-file",
    data=binary_data,
    length=len(binary_data),
    content_type="application/octet-stream"
)
```

#### Upload from File

```python
storage.fput_object(
    bucket_name="my-bucket",
    object_name="document.pdf",
    file_path="/path/to/local/document.pdf",
    content_type="application/pdf"
)
```

#### Upload with Metadata

```python
metadata = {
    "Author": "John Doe",
    "Version": "1.0",
    "Department": "Development"
}

storage.fput_object(
    bucket_name="my-bucket",
    object_name="document.pdf",
    file_path="/path/to/local/document.pdf",
    content_type="application/pdf",
    metadata=metadata
)
```

#### Download Object (to memory)

```python
response = storage.get_object(
    bucket_name="my-bucket",
    object_name="hello.txt"
)

# Read response data
data = response.read()
print(data.decode('utf-8'))  # "Hello, MinIO!"

# Release resources when done
response.close()
```

#### Download Object to File

```python
storage.fget_object(
    bucket_name="my-bucket",
    object_name="document.pdf",
    file_path="/path/to/save/document.pdf"
)
```

#### Get Object Metadata

```python
object_info = storage.stat_object(
    bucket_name="my-bucket",
    object_name="document.pdf"
)

print(f"Size: {object_info.size} bytes")
print(f"Last modified: {object_info.last_modified}")
print(f"ETag: {object_info.etag}")
print(f"Content type: {object_info.content_type}")
print(f"Metadata: {object_info.metadata}")
```

#### Remove Object

```python
storage.remove_object(
    bucket_name="my-bucket",
    object_name="document.pdf"
)
```

### Generate Presigned URLs

#### Presigned URL for Object Retrieval

```python
from datetime import timedelta

# Generate presigned URL valid for 1 hour
url = storage.presigned_get_object(
    bucket_name="my-bucket",
    object_name="private-document.pdf",
    expires=timedelta(hours=1)
)

print(f"Download from this URL: {url}")
# This URL is accessible without authentication for 1 hour only
```

#### Presigned URL for Object Upload

```python
# Generate presigned URL valid for 1 day
url = storage.presigned_put_object(
    bucket_name="my-bucket",
    object_name="upload-here.zip",
    expires=timedelta(days=1)
)

print(f"Upload to this URL: {url}")
# You can upload by sending a PUT request to this URL
```

### Secure Object Retrieval

Retrieve objects in a more secure way than regular `get_object`:

```python
response = storage.secure_get_object(
    bucket_name="my-bucket",
    object_name="sensitive-document.pdf",
    expires=timedelta(minutes=5)  # Set very short expiration time
)

# Read data
data = response.read()

# Release resources when done
response.close()
```

## Usage in Proxy Environment

When using MinIOStorage in a proxy environment, you can set environment variables or explicitly specify an HTTP client as follows.

### Set Proxy with Environment Variables

```python
import os

# Set proxy with environment variables
os.environ["HTTP_PROXY"] = "http://proxy.example.com:8080"
os.environ["HTTPS_PROXY"] = "http://proxy.example.com:8080"

# Instantiate normally
storage = MinIOStorage(
    endpoint="minio.example.com:9000",
    access_key="your-access-key",
    secret_key="your-secret-key"
)
```

### Custom HTTP Client Configuration

```python
from rdetoolkit.storage.minio import MinIOStorage

# Create custom proxy client
proxy_client = MinIOStorage.create_proxy_client(
    proxy_url="http://proxy.example.com:8080"
)

# Instantiate using proxy client
storage = MinIOStorage(
    endpoint="minio.example.com:9000",
    access_key="your-access-key",
    secret_key="your-secret-key",
    http_client=proxy_client
)
```

## Troubleshooting

### Common Errors

1. **Authentication Error**
   - Check if access key and secret key are correct
   - Check if environment variables are set correctly

2. **Connection Error**
   - Check if endpoint is correct
   - Check if MinIO server is running
   - Check network connection
   - If proxy settings are required, check if they are set correctly

3. **Permission Error**
   - Check if you have operation permissions for buckets or objects

4. **Bucket Not Found Error**
   - Check bucket name spelling
   - Check if bucket exists using `bucket_exists()`

### Log Verification

You can enable more detailed logs for troubleshooting:

```python
import logging

# Enable MinIO logs
logging.basicConfig(level=logging.DEBUG)
```

## Practical Example

### Basic File Management System

```python
from rdetoolkit.storage.minio import MinIOStorage
from datetime import timedelta
import os

# Initialize MinIOStorage
storage = MinIOStorage(
    endpoint="minio.example.com:9000",
    access_key="your-access-key",
    secret_key="your-secret-key"
)

# Create working bucket
bucket_name = "my-documents"
if not storage.bucket_exists(bucket_name):
    storage.make_bucket(bucket_name)
    print(f"Created bucket '{bucket_name}'")

# Upload file
local_file = "/path/to/important-doc.pdf"
object_name = os.path.basename(local_file)

storage.fput_object(
    bucket_name=bucket_name,
    object_name=object_name,
    file_path=local_file,
    content_type="application/pdf",
    metadata={"CreatedBy": "User123"}
)
print(f"Uploaded file '{object_name}'")

# Create temporary share link
share_url = storage.presigned_get_object(
    bucket_name=bucket_name,
    object_name=object_name,
    expires=timedelta(hours=24)
)
print(f"24-hour valid share link: {share_url}")

# Download file
download_path = f"/path/to/downloads/{object_name}"
storage.fget_object(
    bucket_name=bucket_name,
    object_name=object_name,
    file_path=download_path
)
print(f"Downloaded file to '{download_path}'")
```

## Summary

Using the MinIOStorage class makes integration with MinIO servers very easy. Main features include:

- Bucket creation, listing, and deletion
- Object (file) upload and download
- Metadata management
- Presigned URL (time-limited access link) generation
- Proxy environment support

## Next Steps

- Check detailed features in [API Reference](../rdetoolkit/storage/minio.md)
- Refer to [MinIO Python SDK Official Documentation](https://min.io/docs/minio/linux/developers/python/API.html)
- Learn how to use object storage in [Structured Processing](../user-guide/structured-processing.en.md)
