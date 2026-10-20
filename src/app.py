"""Minimal Hello World API with OpenTelemetry instrumentation."""
import json
import logging
import os
import time

import telemetry  # noqa: F401 - initialize OpenTelemetry providers first
from telemetry import flush_telemetry
from opentelemetry import metrics, trace
from opentelemetry.trace import Status, StatusCode

logger = logging.getLogger()
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))

tracer = trace.get_tracer("hello-world-api")
meter = metrics.get_meter("hello-world-api")
request_counter = meter.create_counter("app_http_requests", description="Hello World API requests")
error_counter = meter.create_counter("app_http_errors", description="Hello World API errors")
duration_histogram = meter.create_histogram(
    "app_http_request_duration_ms", unit="ms", description="Hello World API request duration"
)


def lambda_handler(event, context):
    """Return a simple Hello World JSON response."""
    started = time.perf_counter()
    status_code = 200
    method = (
        event.get("requestContext", {}).get("http", {}).get("method")
        or event.get("httpMethod")
        or "GET"
    )
    path = event.get("rawPath") or event.get("path") or "/hello"

    with tracer.start_as_current_span("hello-world.request") as span:
        span.set_attribute("http.request.method", method)
        span.set_attribute("url.path", path)
        span.set_attribute("http.response.status_code", status_code)
        try:
            logger.info(json.dumps({
                "event": "hello_world_request",
                "message": "Hello World API invoked",
                "aws_request_id": getattr(context, "aws_request_id", None),
            }))
            return {
                "statusCode": status_code,
                "headers": {
                    "Content-Type": "application/json",
                    "Cache-Control": "no-store",
                },
                "body": json.dumps({
                    "message": "Hello World!",
                    "status": "success",
                }),
            }
        except Exception:
            status_code = 500
            span.set_status(Status(StatusCode.ERROR, "Unhandled exception"))
            logger.exception("Hello World API failed")
            return {
                "statusCode": status_code,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"message": "Internal server error"}),
            }
        finally:
            attrs = {
                "http.request.method": method,
                "http.route": "/hello",
                "http.response.status_code": status_code,
            }
            request_counter.add(1, attrs)
            if status_code >= 400:
                error_counter.add(1, attrs)
            duration_histogram.record((time.perf_counter() - started) * 1000, attrs)
            flush_telemetry()
