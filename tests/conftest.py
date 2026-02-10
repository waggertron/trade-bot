import pytest


@pytest.fixture
def settings():
    """Load test settings."""
    from src.core.config import Settings
    return Settings.for_testing()
