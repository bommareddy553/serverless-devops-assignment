"""OpenTelemetry setup for Lambda, including traces, metrics, and logs."""
import logging
import os

_INITIALIZED = False
_TRACE_PROVIDER = None
_METER_PROVIDER = None
_LOG_PROVIDER = None


def initialize_telemetry() -> None:
    global _INITIALIZED, _TRACE_PROVIDER, _METER_PROVIDER, _LOG_PROVIDER
    if _INITIALIZED:
        return
    _INITIALIZED = True

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        logging.getLogger(__name__).info("OTLP endpoint not configured; using no-op telemetry exporters")
        return

    from opentelemetry import metrics, trace
    from opentelemetry._logs import set_logger_provider
    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import SimpleLogRecordProcessor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    resource = Resource.create({
        "service.name": os.getenv("OTEL_SERVICE_NAME", "serverless-devops-api"),
        "service.namespace": os.getenv("OTEL_SERVICE_NAMESPACE", "assignment"),
        "deployment.environment": os.getenv("DEPLOYMENT_ENVIRONMENT", "dev"),
    })
    headers = {}
    auth = os.getenv("OTEL_EXPORTER_OTLP_HEADERS", "")
    for item in auth.split(","):
        if "=" in item:
            key, value = item.split("=", 1)
            headers[key.strip()] = value.strip()

    base_endpoint = endpoint.rstrip("/")
    traces_endpoint = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", f"{base_endpoint}/v1/traces")
    metrics_endpoint = os.getenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", f"{base_endpoint}/v1/metrics")
    logs_endpoint = os.getenv("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", f"{base_endpoint}/v1/logs")

    _TRACE_PROVIDER = TracerProvider(resource=resource)
    _TRACE_PROVIDER.add_span_processor(
        SimpleSpanProcessor(OTLPSpanExporter(endpoint=traces_endpoint, headers=headers))
    )
    trace.set_tracer_provider(_TRACE_PROVIDER)

    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=metrics_endpoint, headers=headers),
        export_interval_millis=10_000,
    )
    _METER_PROVIDER = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(_METER_PROVIDER)

    _LOG_PROVIDER = LoggerProvider(resource=resource)
    _LOG_PROVIDER.add_log_record_processor(
        SimpleLogRecordProcessor(OTLPLogExporter(endpoint=logs_endpoint, headers=headers))
    )
    set_logger_provider(_LOG_PROVIDER)
    # Forward standard-library application logs to OTLP as well as Lambda stdout.
    otel_handler = LoggingHandler(level=logging.INFO, logger_provider=_LOG_PROVIDER)
    root_logger = logging.getLogger()
    if not any(getattr(h, "_otel_assignment_handler", False) for h in root_logger.handlers):
        otel_handler._otel_assignment_handler = True
        root_logger.addHandler(otel_handler)


def flush_telemetry() -> None:
    """Flush telemetry before Lambda returns, important for short-lived invocations."""
    for provider in (_TRACE_PROVIDER, _METER_PROVIDER, _LOG_PROVIDER):
        if provider is not None:
            try:
                provider.force_flush(timeout_millis=3000)
            except Exception:
                logging.getLogger(__name__).exception("Failed to flush OpenTelemetry data")


initialize_telemetry()
