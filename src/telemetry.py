```python
"""OpenTelemetry setup for AWS Lambda: traces, metrics, and logs."""

import logging
import os

_INITIALIZED = False
_TRACE_PROVIDER = None
_METER_PROVIDER = None
_LOG_PROVIDER = None


def initialize_telemetry() -> None:
    """Initialize OpenTelemetry exporters once per Lambda execution environment."""
    global _INITIALIZED, _TRACE_PROVIDER, _METER_PROVIDER, _LOG_PROVIDER

    if _INITIALIZED:
        return

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        logging.getLogger(__name__).info(
            "OTLP endpoint not configured; telemetry exporters are disabled."
        )
        _INITIALIZED = True
        return

    from opentelemetry import metrics, trace
    from opentelemetry._logs import set_logger_provider
    from opentelemetry.exporter.otlp.proto.http._log_exporter import (
        OTLPLogExporter,
    )
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
        OTLPMetricExporter,
    )
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter,
    )
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import SimpleLogRecordProcessor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    resource = Resource.create(
        {
            "service.name": os.getenv(
                "OTEL_SERVICE_NAME", "serverless-devops-api"
            ),
            "service.namespace": os.getenv(
                "OTEL_SERVICE_NAMESPACE", "assignment"
            ),
            "deployment.environment": os.getenv(
                "DEPLOYMENT_ENVIRONMENT", "dev"
            ),
        }
    )

    # Parse OTLP headers, for example:
    # Authorization=Basic <base64-encoded-credentials>
    headers = {}
    raw_headers = os.getenv("OTEL_EXPORTER_OTLP_HEADERS", "")

    for item in raw_headers.split(","):
        key, separator, value = item.partition("=")
        if separator and key.strip() and value.strip():
            headers[key.strip()] = value.strip()

    base_endpoint = endpoint.rstrip("/")
    traces_endpoint = os.getenv(
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
        f"{base_endpoint}/v1/traces",
    )
    metrics_endpoint = os.getenv(
        "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
        f"{base_endpoint}/v1/metrics",
    )
    logs_endpoint = os.getenv(
        "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT",
        f"{base_endpoint}/v1/logs",
    )

    # Traces
    _TRACE_PROVIDER = TracerProvider(resource=resource)
    _TRACE_PROVIDER.add_span_processor(
        SimpleSpanProcessor(
            OTLPSpanExporter(
                endpoint=traces_endpoint,
                headers=headers,
                timeout=5,
            )
        )
    )
    trace.set_tracer_provider(_TRACE_PROVIDER)

    # Metrics
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(
            endpoint=metrics_endpoint,
            headers=headers,
            timeout=5,
        ),
        export_interval_millis=10_000,
    )
    _METER_PROVIDER = MeterProvider(
        resource=resource,
        metric_readers=[metric_reader],
    )
    metrics.set_meter_provider(_METER_PROVIDER)

    # Logs
    _LOG_PROVIDER = LoggerProvider(resource=resource)
    _LOG_PROVIDER.add_log_record_processor(
        SimpleLogRecordProcessor(
            OTLPLogExporter(
                endpoint=logs_endpoint,
                headers=headers,
                timeout=5,
            )
        )
    )
    set_logger_provider(_LOG_PROVIDER)

    # IMPORTANT:
    # Do not attach the OpenTelemetry handler to the root logger.
    # Exporter/SDK warnings can otherwise be re-exported recursively.
    # Application code should log through "hello_world_app".
    app_logger = logging.getLogger("hello_world_app")
    app_logger.setLevel(logging.INFO)
    app_logger.propagate = True

    if not any(
        getattr(handler, "_otel_assignment_handler", False)
        for handler in app_logger.handlers
    ):
        otel_handler = LoggingHandler(
            level=logging.INFO,
            logger_provider=_LOG_PROVIDER,
        )
        otel_handler._otel_assignment_handler = True
        app_logger.addHandler(otel_handler)

    _INITIALIZED = True


def flush_telemetry() -> None:
    """Flush pending telemetry before the Lambda invocation returns."""
    for provider in (_TRACE_PROVIDER, _METER_PROVIDER, _LOG_PROVIDER):
        if provider is None:
            continue

        try:
            provider.force_flush(timeout_millis=3000)
        except Exception:
            # Do not log exporter failures through the same telemetry pipeline.
            # This avoids another possible logging recursion.
            pass


initialize_telemetry()
```
