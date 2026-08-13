"""Shared pytest fixtures for aioindiallsky tests."""
import pytest
from aioindiallsky import IndiAllSkyClient


@pytest.fixture
def sample_host():
    return "127.0.0.1"


@pytest.fixture
def client(sample_host):
    return IndiAllSkyClient(host=sample_host, port=8080, api_key="test_api_key")
