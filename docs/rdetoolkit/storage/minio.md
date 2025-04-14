# MinIO Storage

MinIO is a high-performance, S3-compatible object storage service. It is designed for large-scale data storage and retrieval, making it an ideal choice for applications that require fast access to large datasets.

## MinIOStorage

::: src.rdetoolkit.storage.minio.MinIOStorage
    handler: python
    options:
        members:
            - __init__
            - create_default_http_client
            - create_proxy_client
            - make_bucket
            - list_buckets
            - bucket_exists
            - remove_bucket
            - put_object
            - fput_object
            - get_object
            - fget_object
            - stat_object
            - remove_object
            - presigned_get_object
            - presigned_put_object
            - secure_get_object
