import pytest


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Set up test environment for processing tests."""
    # This fixture runs automatically for all tests in this directory
    # Can be used to set up common test environment
    yield
    # Cleanup after test if needed
