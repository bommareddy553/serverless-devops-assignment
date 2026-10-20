import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)

from app import lambda_handler  # noqa: E402


def test_hello_world_response():
    event = {
        "requestContext": {"http": {"method": "GET"}},
        "rawPath": "/hello",
    }
    response = lambda_handler(event, SimpleNamespace(aws_request_id="test-request"))
    assert response["statusCode"] == 200
    assert response["headers"]["Content-Type"] == "application/json"
    assert json.loads(response["body"]) == {
        "message": "Hello World!",
        "status": "success",
    }


def test_hello_world_works_with_empty_event():
    response = lambda_handler({}, SimpleNamespace())
    assert response["statusCode"] == 200
    assert json.loads(response["body"])["message"] == "Hello World!"
