variable "aws_region" {
  description = "AWS region for the application."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Short project identifier used in resource names."
  type        = string
  default     = "serverless-devops"
}

variable "environment" {
  description = "Deployment environment."
  type        = string
  default     = "dev"
  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "environment must be dev or prod."
  }
}

variable "lambda_memory_size" {
  description = "Lambda memory in MB."
  type        = number
  default     = 256
}

variable "lambda_timeout" {
  description = "Lambda timeout in seconds."
  type        = number
  default     = 10
}

variable "grafana_otlp_endpoint" {
  description = "Grafana Cloud OTLP base endpoint, e.g. https://otlp-gateway-prod-us-east-0.grafana.net/otlp."
  type        = string
  default     = ""
}

variable "grafana_otlp_headers" {
  description = "OTLP headers in OpenTelemetry format, e.g. Authorization=Basic BASE64_VALUE. Keep sensitive."
  type        = string
  sensitive   = true
  default     = ""
}
