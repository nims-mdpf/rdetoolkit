from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any
from datetime import datetime, timedelta

import urllib3
from urllib3 import ProxyManager, PoolManager
try:
    from urllib3.response import BaseHTTPResponse  # type: ignore[attr-defined]
except ImportError:
    from urllib3.response import HTTPResponse as BaseHTTPResponse

try:
    from minio import Minio
    from minio.sse import SseCustomerKey
    from minio.commonconfig import Tags
    from minio.retention import Retention
    HAS_MINIO = True
except ImportError:
    HAS_MINIO = False


class MinIOStorage:
    """Handles file operations on MinIO.

    Attributes:
        access_key (str): MinIO access key.
        secret_key (str): MinIO secret key.
        client (Minio): MinIO client instance.
    """

    def __init__(
        self,
        endpoint: str,
        access_key: str | None = None,
        secret_key: str | None = None,
        secure: bool = True,
        region: str | None = None,
        http_client: urllib3.PoolManager | None = None,
    ):
        """Initializes the MinIOStorage.

        Args:
            endpoint (str): MinIO endpoint.
            access_key (str | None): Access key value. Defaults to environment variable.
            secret_key (str | None): Secret key value. Defaults to environment variable.
            secure (bool): Whether SSL is required.
            region (str | None): Region of the bucket.
            http_client (urllib3.PoolManager | None): HTTP client for the Minio instance.

        Raises:
            ValueError: If access_key or secret_key is not provided.
        """
        if not HAS_MINIO:
            import_err_msg = "Minio is not installed. Please install it using 'pip install rdetoolkit[minio]'."
            raise ImportError(import_err_msg)

        self.access_key = access_key if access_key else os.environ.get("MINIO_ACCESS_KEY")
        self.secret_key = secret_key if secret_key else os.environ.get("MINIO_SECRET_KEY")

        if not self.access_key or not self.secret_key:
            emsg = "Access key and secret key are required."
            raise ValueError(emsg)

        if http_client is None:
            http_client = self.create_default_http_client()

        self.client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
            region=region,
            http_client=http_client,
        )

    @staticmethod
    def create_default_http_client() -> ProxyManager | PoolManager:
        """Creates a default HTTP client with optional proxy.

        Returns:
            ProxyManager | PoolManager: Configured proxy or pool manager.
        """
        proxy_url = (
            os.environ.get("HTTP_PROXY")
            or os.environ.get("HTTPS_PROXY")
            or os.environ.get("http_proxy")
            or os.environ.get("https_proxy")
        )

        if proxy_url:
            return ProxyManager(
                proxy_url,
                timeout=urllib3.Timeout.DEFAULT_TIMEOUT,
                cert_reqs="CERT_REQUIRED",
                retries=urllib3.Retry(
                    3,
                    backoff_factor=0.5,
                    status_forcelist=[500, 502, 503, 504],
                ),
            )

        return PoolManager(
            timeout=urllib3.Timeout.DEFAULT_TIMEOUT,
            cert_reqs="CERT_REQUIRED",
            retries=urllib3.Retry(
                3,
                backoff_factor=0.5,
                status_forcelist=[500, 502, 503, 504],
            ),
        )

    @staticmethod
    def create_proxy_client(
        proxy_url: str,
        timeout: Any = urllib3.Timeout.DEFAULT_TIMEOUT,
        cert_reqs: str = "CERT_REQUIRED",
        ca_certs: str | None = None,
        retries: Any = None,
    ) -> ProxyManager:
        """Creates a proxy client with specified settings.

        Args:
            proxy_url (str): The proxy URL.
            timeout (Any): Timeout object or setting.
            cert_reqs (str): Certificate requirement level.
            ca_certs (str | None): Path to CA bundle file.
            retries (Any): Retry settings.

        Returns:
            ProxyManager: A configured proxy manager instance.
        """
        if retries is None:
            retries = urllib3.Retry(
                total=5,
                backoff_factor=0.5,
                status_forcelist=[500, 502, 503, 504],
            )

        return ProxyManager(
            proxy_url=proxy_url,
            timeout=timeout,
            cert_reqs=cert_reqs,
            ca_certs=ca_certs,
            retries=retries,
        )

    def make_bucket(self, backet_name: str, location: str = 'us-east-1', object_lock: bool = False) -> None:
        """Creates a new bucket in MinIO.

        Args:
            backet_name (str): Name of the bucket.
            location (str): Region for the bucket.
            object_lock (bool): Whether to enable object lock.
        """
        self.client.make_bucket(bucket_name=backet_name, location=location, object_lock=object_lock)

    def list_buckets(self) -> list[dict[str, Any]]:
        """Lists all existing buckets.

        Returns:
            list[dict[str, Any]]: List of bucket information.
        """
        buckets = self.client.list_buckets()
        return [
            {
                "name": bucket.name,
                "creation_date": bucket.creation_date,
            }
            for bucket in buckets
        ]

    def bucket_exists(self, bucket_name: str) -> bool:
        """Checks if a bucket exists.

        Args:
            bucket_name (str): Name of the bucket.

        Returns:
            bool: True if bucket exists, else False.
        """
        return self.client.bucket_exists(bucket_name=bucket_name)

    def remove_bucket(self, bucket_name: str) -> None:
        """Removes an existing bucket.

        Args:
            bucket_name (str): Name of the bucket.

        Raises:
            ValueError: If bucket does not exist.
        """
        if self.client.bucket_exists(bucket_name):
            self.client.remove_bucket(bucket_name)
        else:
            emsg = f"Bucket {bucket_name} does not exist."
            raise ValueError(emsg)

    def put_object(
        self,
        bucket_name: str,
        object_name: str,
        data: bytes | str,
        length: int,
        *,
        content_type: str = "application/octet-stream",
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        """Uploads data as an object to a bucket.

        Args:
            bucket_name (str): Name of the bucket.
            object_name (str): Object name in the bucket.
            data (bytes | str): Data to upload.
            length (int): Size of the data.
            content_type (str): MIME type of the object.
            metadata (dict[str, Any] | None): Additional metadata.

        Returns:
            Any: Information about the upload result.
        """
        if isinstance(data, bytes):
            _data = io.BytesIO(data)
        elif isinstance(data, str):
            _data = io.BytesIO(data.encode("utf-8"))
        else:
            emsg = "Data must be bytes or string."
            raise ValueError(emsg)

        return self.client.put_object(
            bucket_name=bucket_name,
            object_name=object_name,
            data=_data,
            length=length,
            content_type=content_type,
            metadata=metadata,
        )

    def fput_object(
        self,
        bucket_name: str,
        object_name: str,
        file_path: str | Path,
        content_type: str = "application/octet-stream",
        metadata: dict[str, Any] | None = None,
        sse: SseCustomerKey | None = None,
        part_size: int = 0,
        num_parallel_uploads: int = 3,
        tags: Tags | None = None,
        retention: Retention | None = None,
        legal_hold: bool = False,
    ) -> Any:
        """Uploads a file from local storage to a bucket.

        Args:
            bucket_name (str): Name of the bucket.
            object_name (str): Object name in the bucket.
            file_path (str | Path): Path to source file.
            content_type (str): MIME type of the file.
            metadata (dict[str, Any] | None): Additional metadata.
            sse (SseCustomerKey | None): Server-side encryption.
            part_size (int): Part size for multipart upload.
            num_parallel_uploads (int): Number of parallel uploads.
            tags (Tags | None): Key-value tags for the object.
            retention (Retention | None): Retention configuration.
            legal_hold (bool): Whether to enable legal hold.

        Returns:
            Any: Information about the upload result.
        """
        _file_path = str(file_path) if isinstance(file_path, Path) else file_path
        self.client.fput_object(
            bucket_name=bucket_name,
            object_name=object_name,
            file_path=_file_path,
            content_type=content_type,
            metadata=metadata,
            sse=sse,
            part_size=part_size,
            num_parallel_uploads=num_parallel_uploads,
            tags=tags,
            retention=retention,
            legal_hold=legal_hold,
        )

    def get_object(
        self,
        bucket_name: str,
        object_name: str,
        offset: int = 0,
        length: int = 0,
        ssec: SseCustomerKey | None = None,
        version_id: str | None = None,
        extra_query_params: dict[str, Any] | None = None,
    ) -> BaseHTTPResponse:
        """Retrieves an object from a bucket.

        Args:
            bucket_name (str): Name of the bucket.
            object_name (str): Object name in the bucket.
            offset (int): Start byte of the requested range.
            length (int): Number of bytes to read.
            ssec (SseCustomerKey | None): Server-side encryption key.
            version_id (str | None): Specific version of the object.
            extra_query_params (Any): Extra query parameters.

        Returns:
            BaseHTTPResponse: The retrieved object data response.
        """
        return self.client.get_object(
            bucket_name=bucket_name,
            object_name=object_name,
            offset=offset,
            length=length,
            ssec=ssec,
            version_id=version_id,
            extra_query_params=extra_query_params,
        )

    def fget_object(
        self,
        bucket_name: str,
        object_name: str,
        file_path: str,
        request_headers: dict[str, Any] | None = None,
        ssec: SseCustomerKey | None = None,
        version_id: str | None = None,
        extra_query_params: dict[str, Any] | None = None,
        tmp_file_path: str | None = None,
    ) -> BaseHTTPResponse:
        """Downloads an object to a file.

        Args:
            bucket_name (str): Name of the bucket.
            object_name (str): Object name in the bucket.
            file_path (str): Destination path for the downloaded file.
            request_headers (dict[str, Any] | None): Extra request headers.
            ssec (SseCustomerKey | None): Encryption key.
            version_id (str | None): Specific version of the object.
            extra_query_params (dict[str, Any] | None): Extra query parameters.
            tmp_file_path (str | None): Temporary file path.

        Returns:
            BaseHTTPResponse: The downloaded file response.
        """
        return self.client.fget_object(
            bucket_name=bucket_name,
            object_name=object_name,
            file_path=file_path,
            request_headers=request_headers,
            ssec=ssec,
            version_id=version_id,
            extra_query_params=extra_query_params,
            tmp_file_path=tmp_file_path,
        )

    def stat_object(
        self,
        bucket_name: str,
        object_name: str,
        ssec: SseCustomerKey | None = None,
        version_id: str | None = None,
        extra_headers: dict[str, Any] | None = None,
    ) -> Any:
        """Fetches metadata of an object in a bucket.

        Args:
            bucket_name (str): Name of the bucket.
            object_name (str): Object name in the bucket.
            ssec (SseCustomerKey | None): Encryption key.
            version_id (str | None): Specific version of the object.
            extra_headers (dict[str, Any] | None): Additional headers.

        Returns:
            Any: Metadata of the requested object.
        """
        return self.client.stat_object(
            bucket_name,
            object_name,
            ssec=ssec,
            version_id=version_id,
            extra_headers=extra_headers,
        )

    def remove_object(self, bucket_name: str, object_name: str, version_id: str | None = None) -> None:
        """Removes an object from a bucket.

        Args:
            bucket_name (str): Name of the bucket.
            object_name (str): Object name in the bucket.
            version_id (str | None): Specific version of the object.
        """
        return self.client.remove_object(bucket_name, object_name, version_id)

    def presigned_get_object(
        self,
        bucket_name: str,
        object_name: str,
        expires: timedelta = timedelta(days=7),
        response_headers: dict[str, Any] | None = None,
        request_date: datetime | None = None,
        version_id: str | None = None,
        extra_query_params: dict[str, Any] | None = None,
    ) -> str:
        """Generates a presigned GET URL.

        Args:
            bucket_name (str): Name of the bucket.
            object_name (str): Object name in the bucket.
            expires (timedelta): URL expiration time.
            response_headers (dict[str, Any] | None): Custom response headers.
            request_date (datetime | None): A specific request date.
            version_id (str | None): Specific version of the object.
            extra_query_params (dict[str, Any] | None): Extra parameters.

        Returns:
            str: The presigned URL.
        """
        return self.client.presigned_get_object(
            bucket_name,
            object_name,
            expires=expires,
            response_headers=response_headers,
            request_date=request_date,
            version_id=version_id,
            extra_query_params=extra_query_params,
        )

    def presigned_put_object(
        self,
        bucket_name: str,
        object_name: str,
        expires: timedelta = timedelta(days=7),
    ) -> str:
        """Generates a presigned PUT URL.

        Args:
            bucket_name (str): Name of the bucket.
            object_name (str): Object name in the bucket.
            expires (timedelta): URL expiration time.

        Returns:
            str: The presigned URL.
        """
        return self.client.presigned_put_object(bucket_name, object_name, expires)

    def secure_get_object(
        self,
        bucket_name: str,
        object_name: str,
        *,
        expires: timedelta = timedelta(minutes=15),
        ssec: SseCustomerKey | None = None,
        version_id: str | None = None,
        use_ssl: bool = True,
    ) -> BaseHTTPResponse:
        """Recommended method for securely retrieving objects.

        Generates a short-lived presigned URL and accesses it with a dedicated client.

        Args:
            bucket_name (str): Name of the bucket.
            object_name (str): Name of the object to retrieve.
            expires (timedelta): Expiration time for the URL (default: 15 minutes).
            ssec (SseCustomerKey | None): Server-side encryption key.
            version_id (str | None): Specific version of the object.
            use_ssl (bool): Whether to use SSL connection.

        Returns:
            BaseHTTPResponse: HTTP response containing object data.

        Notes:
            This method is recommended over the traditional get_object method.
            The expiration time is intentionally short for improved security.
        """
        response_headers = {}
        if ssec:
            response_headers.update(ssec.headers())

        presigned_url = self.presigned_get_object(
            bucket_name=bucket_name,
            object_name=object_name,
            expires=expires,
            response_headers=response_headers,
            version_id=version_id,
        )

        http_client = PoolManager(
            timeout=urllib3.Timeout(connect=5, read=30),
            cert_reqs="CERT_REQUIRED" if use_ssl else "CERT_NONE",
            retries=urllib3.Retry(
                total=3,
                backoff_factor=0.5,
                status_forcelist=[500, 502, 503, 504],
            ),
        )

        return http_client.request(
            "GET",
            presigned_url,
            preload_content=False,
        )
