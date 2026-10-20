output "api_base_url" {
  description = "Base URL for the HTTP API."
  value       = aws_apigatewayv2_api.http.api_endpoint
}

output "lambda_function_name" {
  description = "Deployed Lambda function name."
  value       = aws_lambda_function.api.function_name
}

output "cloudwatch_log_group" {
  description = "Lambda CloudWatch log group."
  value       = aws_cloudwatch_log_group.lambda.name
}
