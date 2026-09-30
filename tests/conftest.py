import os

os.environ["LLM_BACKEND"] = "extractive"

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app


@pytest.fixture
def client(tmp_path):
    settings = get_settings().with_overrides(
        llm_backend="extractive",
        feedback_path=tmp_path / "feedback.jsonl",
        audit_path=tmp_path / "audit.jsonl",
    )
    application = create_app(settings)
    with TestClient(application) as test_client:
        yield test_client
