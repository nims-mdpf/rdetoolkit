import io
import os
import pytest
from datetime import timedelta
from unittest.mock import patch, MagicMock
from pathlib import Path

import urllib3

from rdetoolkit.storage.minio import MinIOStorage


@pytest.fixture
def mock_minio_client():
    """Mock MinIO client"""
    with patch('rdetoolkit.storage.minio.Minio') as mock_minio:
        mock_client = MagicMock()
        mock_minio.return_value = mock_client
        yield mock_client


@pytest.fixture
def storage(mock_minio_client):
    """Storage instance for testing"""
    # Setting environment variables
    os.environ["MINIO_ACCESS_KEY"] = "test_access_key"
    os.environ["MINIO_SECRET_KEY"] = "test_secret_key"

    storage = MinIOStorage(
        endpoint="test.minio.local",
        secure=True,
        region="us-east-1",
    )
    return storage


@pytest.fixture
def test_bucket():
    """Test bucket name"""
    return "test-bucket"


@pytest.fixture
def test_object_data():
    """Test object data"""
    return b"test object content"


@pytest.fixture
def test_file_path(tmp_path):
    """Path for test file"""
    test_file = tmp_path / "test_file.txt"
    test_file.write_text("test file content")
    return str(test_file)


class TestMinIOStorageInit:
    """Initialization tests"""

    def test_init_with_credentials(self, mock_minio_client):
        """Test initialization with direct credentials"""
        storage = MinIOStorage(
            endpoint="minio.example.com",
            access_key="my_access_key",
            secret_key="my_secret_key",
        )

        assert storage.access_key == "my_access_key"
        assert storage.secret_key == "my_secret_key"
        assert mock_minio_client is storage.client

    def test_init_from_env_vars(self, mock_minio_client):
        """Test initialization from environment variables"""
        os.environ["MINIO_ACCESS_KEY"] = "env_access_key"
        os.environ["MINIO_SECRET_KEY"] = "env_secret_key"

        storage = MinIOStorage(endpoint="minio.example.com")

        assert storage.access_key == "env_access_key"
        assert storage.secret_key == "env_secret_key"

    def test_init_with_custom_http_client(self, mock_minio_client):
        """Test initialization with a custom HTTP client"""
        custom_client = urllib3.PoolManager()
        storage = MinIOStorage(
            endpoint="minio.example.com",
            access_key="my_key",
            secret_key="my_secret",
            http_client=custom_client,
        )
        assert storage.client is mock_minio_client

    def test_init_missing_credentials(self):
        """Test error when credentials are missing"""
        os.environ.pop("MINIO_ACCESS_KEY", None)
        os.environ.pop("MINIO_SECRET_KEY", None)

        with pytest.raises(ValueError) as excinfo:
            MinIOStorage(endpoint="minio.example.com")

        assert "Access key and secret key are required" in str(excinfo.value)


class TestBucketOperations:
    """Bucket operation tests"""

    def test_make_bucket(self, storage, mock_minio_client, test_bucket):
        """Test bucket creation"""
        storage.make_bucket(test_bucket, "us-west-1", True)

        mock_minio_client.make_bucket.assert_called_once_with(
            bucket_name=test_bucket,
            location="us-west-1",
            object_lock=True,
        )

    def test_list_buckets(self, storage, mock_minio_client):
        """Test listing buckets"""
        bucket1 = MagicMock()
        bucket1.name = "bucket1"
        bucket1.creation_date = "2023-01-01"

        bucket2 = MagicMock()
        bucket2.name = "bucket2"
        bucket2.creation_date = "2023-01-02"

        mock_minio_client.list_buckets.return_value = [bucket1, bucket2]

        buckets = storage.list_buckets()

        assert len(buckets) == 2
        assert buckets[0]["name"] == "bucket1"
        assert buckets[1]["name"] == "bucket2"
        assert buckets[0]["creation_date"] == "2023-01-01"
        assert buckets[1]["creation_date"] == "2023-01-02"

    def test_bucket_exists(self, storage, mock_minio_client, test_bucket):
        """Test checking if bucket exists"""
        mock_minio_client.bucket_exists.return_value = True

        exists = storage.bucket_exists(test_bucket)

        assert exists is True
        mock_minio_client.bucket_exists.assert_called_once_with(
            bucket_name=test_bucket,
        )

    def test_remove_bucket(self, storage, mock_minio_client, test_bucket):
        """Test removing bucket"""
        mock_minio_client.bucket_exists.return_value = True

        storage.remove_bucket(test_bucket)

        mock_minio_client.remove_bucket.assert_called_once_with(test_bucket)

    def test_remove_non_existent_bucket(self, storage, mock_minio_client, test_bucket):
        """Test removing a non-existent bucket"""
        mock_minio_client.bucket_exists.return_value = False

        with pytest.raises(ValueError) as excinfo:
            storage.remove_bucket(test_bucket)

        assert f"Bucket {test_bucket} does not exist" in str(excinfo.value)


class TestObjectOperations:
    """Object operation tests"""

    def test_put_object_bytes(self, storage, mock_minio_client, test_bucket, test_object_data):
        """Test uploading byte data"""
        storage.put_object(
            bucket_name=test_bucket,
            object_name="test.txt",
            data=test_object_data,
            length=len(test_object_data),
            content_type="text/plain",
            metadata={"key": "value"},
        )

        mock_minio_client.put_object.assert_called_once()
        args, kwargs = mock_minio_client.put_object.call_args
        assert kwargs["bucket_name"] == test_bucket
        assert kwargs["object_name"] == "test.txt"
        assert isinstance(kwargs["data"], io.BytesIO)
        assert kwargs["length"] == len(test_object_data)
        assert kwargs["content_type"] == "text/plain"
        assert kwargs["metadata"] == {"key": "value"}

    def test_put_object_str(self, storage, mock_minio_client, test_bucket):
        """Test uploading string data"""
        test_str = "テストデータ"

        storage.put_object(
            bucket_name=test_bucket,
            object_name="test.txt",
            data=test_str,
            length=len(test_str.encode("utf-8")),
            content_type="text/plain",
        )

        mock_minio_client.put_object.assert_called_once()
        args, kwargs = mock_minio_client.put_object.call_args
        assert kwargs["bucket_name"] == test_bucket
        assert kwargs["object_name"] == "test.txt"
        assert isinstance(kwargs["data"], io.BytesIO)

    def test_put_object_invalid_data(self, storage, test_bucket):
        """Test uploading invalid data type"""
        with pytest.raises(ValueError) as excinfo:
            storage.put_object(
                bucket_name=test_bucket,
                object_name="test.txt",
                data=123,
                length=10,
            )

        assert "Data must be bytes or string" in str(excinfo.value)

    def test_fput_object(self, storage, mock_minio_client, test_bucket, test_file_path):
        """Test uploading a file"""
        storage.fput_object(
            bucket_name=test_bucket,
            object_name="uploaded.txt",
            file_path=test_file_path,
            content_type="text/plain",
        )

        mock_minio_client.fput_object.assert_called_once()
        kwargs = mock_minio_client.fput_object.call_args.kwargs
        assert kwargs["bucket_name"] == test_bucket
        assert kwargs["object_name"] == "uploaded.txt"
        assert kwargs["file_path"] == test_file_path
        assert kwargs["content_type"] == "text/plain"

    def test_fput_object_with_path(self, storage, mock_minio_client, test_bucket, test_file_path):
        """Test uploading a file using a Path object"""
        path_obj = Path(test_file_path)

        storage.fput_object(
            bucket_name=test_bucket,
            object_name="uploaded.txt",
            file_path=path_obj,
        )

        mock_minio_client.fput_object.assert_called_once()
        kwargs = mock_minio_client.fput_object.call_args.kwargs
        assert kwargs["file_path"] == test_file_path

    def test_get_object(self, storage, mock_minio_client, test_bucket):
        """Test retrieving an object"""
        mock_response = MagicMock()
        mock_minio_client.get_object.return_value = mock_response

        response = storage.get_object(
            bucket_name=test_bucket,
            object_name="test.txt",
            offset=10,
            length=100,
        )

        assert response == mock_response
        mock_minio_client.get_object.assert_called_once_with(
            bucket_name=test_bucket,
            object_name="test.txt",
            offset=10,
            length=100,
            ssec=None,
            version_id=None,
            extra_query_params=None,
        )

    def test_secure_get_object(self, storage, mock_minio_client, test_bucket):
        """Test retrieving an object securely"""
        mock_minio_client.presigned_get_object.return_value = "https://secure-url.com/test.txt"

        mock_response = MagicMock()
        with patch('rdetoolkit.storage.minio.PoolManager') as mock_pool_mgr:
            mock_pool_instance = MagicMock()
            mock_pool_mgr.return_value = mock_pool_instance
            mock_pool_instance.request.return_value = mock_response

            response = storage.secure_get_object(
                bucket_name=test_bucket,
                object_name="test.txt",
                expires=timedelta(minutes=5),
            )

            assert response == mock_response
            mock_minio_client.presigned_get_object.assert_called_once()
            mock_pool_instance.request.assert_called_once_with(
                "GET",
                "https://secure-url.com/test.txt",
                preload_content=False,
            )

    def test_stat_object(self, storage, mock_minio_client, test_bucket):
        """Test retrieving object metadata"""
        mock_stat = MagicMock()
        mock_stat.etag = "etag123"
        mock_stat.size = 100
        mock_stat.last_modified = "2023-01-01"
        mock_stat.content_type = "text/plain"
        mock_stat.metadata = {"key": "value"}

        mock_minio_client.stat_object.return_value = mock_stat

        result = storage.stat_object(
            bucket_name=test_bucket,
            object_name="test.txt",
        )

        mock_minio_client.stat_object.assert_called_once()
        assert result == mock_stat

    def test_remove_object(self, storage, mock_minio_client, test_bucket):
        """Test removing an object"""
        storage.remove_object(test_bucket, "test.txt")

        mock_minio_client.remove_object.assert_called_once_with(
            test_bucket, "test.txt", None,
        )


class TestPresignedURLs:
    """Tests for presigned URLs"""

    def test_presigned_get_object(self, storage, mock_minio_client, test_bucket):
        """Test generating a presigned GET URL"""
        mock_minio_client.presigned_get_object.return_value = "https://presigned-url.com/get"

        expires = timedelta(hours=2)
        url = storage.presigned_get_object(
            bucket_name=test_bucket,
            object_name="test.txt",
            expires=expires,
        )

        assert url == "https://presigned-url.com/get"
        mock_minio_client.presigned_get_object.assert_called_once_with(
            test_bucket,
            "test.txt",
            expires=expires,
            response_headers=None,
            request_date=None,
            version_id=None,
            extra_query_params=None,
        )

    def test_presigned_put_object(self, storage, mock_minio_client, test_bucket):
        """Test generating a presigned PUT URL"""
        mock_minio_client.presigned_put_object.return_value = "https://presigned-url.com/put"

        expires = timedelta(hours=1)
        url = storage.presigned_put_object(
            bucket_name=test_bucket,
            object_name="upload.txt",
            expires=expires,
        )

        assert url == "https://presigned-url.com/put"
        mock_minio_client.presigned_put_object.assert_called_once_with(
            test_bucket, "upload.txt", expires,
        )


@pytest.mark.skipif(
    not (os.environ.get("INTEGRATION_TEST") and
        os.environ.get("MINIO_ENDPOINT") and
        os.environ.get("MINIO_ACCESS_KEY") and
        os.environ.get("MINIO_SECRET_KEY")),
    reason="Integration tests require environment variables",
)
class TestMinIOIntegration:
    """Integration tests using a real MinIO server"""

    @pytest.fixture
    def real_storage(self):
        """Storage instance for real MinIO server"""
        storage = MinIOStorage(
            endpoint=os.environ.get("MINIO_ENDPOINT"),
            access_key=os.environ.get("MINIO_ACCESS_KEY"),
            secret_key=os.environ.get("MINIO_SECRET_KEY"),
            secure=os.environ.get("MINIO_SECURE", "true").lower() == "true",
        )
        return storage

    @pytest.fixture
    def integration_bucket(self):
        """Unique integration test bucket"""
        import uuid
        return f"pytest-integration-{uuid.uuid4()}"

    @pytest.fixture
    def cleanup_bucket(self, real_storage, integration_bucket):
        """Remove bucket after tests"""
        yield
        try:
            objects = real_storage.client.list_objects(integration_bucket, recursive=True)
            for obj in objects:
                real_storage.remove_object(integration_bucket, obj.object_name)
            real_storage.remove_bucket(integration_bucket)
        except Exception:
            pass

    def test_full_integration_flow(self, real_storage, integration_bucket, cleanup_bucket, tmp_path):
        """Full integration test with a real MinIO server"""
        real_storage.make_bucket(integration_bucket)

        assert real_storage.bucket_exists(integration_bucket)

        test_content = b"Integration test content"
        real_storage.put_object(
            bucket_name=integration_bucket,
            object_name="test-obj.txt",
            data=test_content,
            length=len(test_content),
            content_type="text/plain",
            metadata={"source": "pytest"},
        )

        stat = real_storage.stat_object(integration_bucket, "test-obj.txt")
        assert stat["size"] == len(test_content)
        assert stat["content_type"] == "text/plain"
        assert stat["metadata"].get("source") == "pytest"

        response = real_storage.secure_get_object(
            bucket_name=integration_bucket,
            object_name="test-obj.txt",
        )
        try:
            content = response.read()
            assert content == test_content
        finally:
            response.close()
            response.release_conn()

        download_path = tmp_path / "download.txt"
        real_storage.fget_object(
            bucket_name=integration_bucket,
            object_name="test-obj.txt",
            file_path=str(download_path),
        )
        assert download_path.read_bytes() == test_content
