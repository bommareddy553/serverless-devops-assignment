# Serverless DevOps Assignment

Python AWS Lambda + API Gateway, Terraform, GitHub Actions OIDC, pytest, OpenTelemetry, and Grafana Cloud.

## API

- `GET /hello` — returns `{"message":"Hello World!","status":"success"}`.

## Architecture

Client → API Gateway HTTP API (`GET /hello`) → Lambda → structured application log and OpenTelemetry instrumentation.
Lambda execution logs and native invocation/error/duration metrics are available in CloudWatch. Application logs, application metrics, and traces are exported to Grafana Cloud over OTLP/HTTP when configured.

## Prerequisites

- AWS account and permissions to create Lambda, API Gateway, IAM role/policy attachment, and CloudWatch log group.
- Terraform >= 1.6 and AWS CLI configured locally for first-time bootstrap.
- Grafana Cloud stack with OTLP endpoint and an access policy/token that can write telemetry.
- GitHub repository and an AWS IAM OIDC provider/role for GitHub Actions.

## Local validation

`requirements.txt` contains development/test tools. The deployable Lambda package uses `requirements-lambda.txt` so pytest and Ruff are not shipped to AWS.

```bash
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell:
# .venv\Scripts\Activate.ps1
pip install -r requirements.txt
ruff check src tests
pytest -q
```

## Grafana Cloud OTLP configuration

In Grafana Cloud, open the OpenTelemetry/OTLP setup instructions for your stack and copy the exact OTLP base endpoint. Create an access policy/token with the minimum write permissions required for telemetry. The header value is normally `Authorization=Basic <base64(instance-id:token)>`; follow the endpoint's own instructions and do not commit the token.

The app reads:
- `OTEL_EXPORTER_OTLP_ENDPOINT` (base endpoint, ending in `/otlp`)
- `OTEL_EXPORTER_OTLP_HEADERS` (comma-separated key=value headers)
- `OTEL_SERVICE_NAME`, `OTEL_SERVICE_NAMESPACE`, `DEPLOYMENT_ENVIRONMENT`

The code exports application logs, spans, and application metrics using OTLP/HTTP and attempts a flush before each Lambda invocation returns. Lambda's native Invocations, Errors, and Duration remain available in CloudWatch; connect CloudWatch metrics to Grafana or use Grafana Cloud's AWS integration to view them alongside application telemetry. Verify telemetry delivery in Grafana after deployment.

## First deployment and remote Terraform state

For repeatable CI/CD, use a remote S3 backend with DynamoDB state locking. Do not run shared deployments from ephemeral GitHub-hosted runners with local state.

1. Confirm your AWS identity and region:
   ```bash
   aws sts get-caller-identity
   aws configure get region
   ```
2. Create a dedicated S3 bucket for Terraform state in your chosen region. Bucket names must be globally unique. Enable versioning and block all public access:
   ```bash
   aws s3api create-bucket --bucket YOUR_UNIQUE_STATE_BUCKET --region us-east-1
   aws s3api put-public-access-block --bucket YOUR_UNIQUE_STATE_BUCKET \
     --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
   aws s3api put-bucket-versioning --bucket YOUR_UNIQUE_STATE_BUCKET \
     --versioning-configuration Status=Enabled
   aws s3api put-bucket-encryption --bucket YOUR_UNIQUE_STATE_BUCKET \
     --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
   ```
   Create the DynamoDB lock table:
   ```bash
   aws dynamodb create-table --table-name YOUR_STATE_LOCK_TABLE \
     --attribute-definitions AttributeName=LockID,AttributeType=S \
     --key-schema AttributeName=LockID,KeyType=HASH \
     --billing-mode PAY_PER_REQUEST --region us-east-1
   ```
   Wait for the table to become active before running Terraform. These commands are examples for `us-east-1`; use the same region for the state bucket, lock table, and backend.
3. Package the Lambda runtime dependencies:
   ```bash
   python scripts/package_lambda.py
   ```
4. Set the Grafana OTLP values in your shell. Use the exact endpoint from your Grafana Cloud stack and keep the authorization value secret:
   ```bash
   export TF_VAR_grafana_otlp_endpoint='https://otlp-gateway-prod-REGION.grafana.net/otlp'
   export TF_VAR_grafana_otlp_headers='Authorization=Basic YOUR_BASE64_VALUE'
   ```
   PowerShell:
   ```powershell
   $env:TF_VAR_grafana_otlp_endpoint = "https://otlp-gateway-prod-REGION.grafana.net/otlp"
   $env:TF_VAR_grafana_otlp_headers = "Authorization=Basic YOUR_BASE64_VALUE"
   ```
5. Initialize Terraform with your remote backend and deploy:
   ```bash
   cd infrastructure
   terraform init \
     -backend-config="bucket=YOUR_UNIQUE_STATE_BUCKET" \
     -backend-config="key=serverless-devops/dev/terraform.tfstate" \
     -backend-config="region=us-east-1" \
     -backend-config="encrypt=true" \
     -backend-config="dynamodb_table=YOUR_STATE_LOCK_TABLE"
   terraform fmt -recursive
   terraform validate
   terraform plan
   terraform apply
   terraform output -raw api_base_url
   ```
6. Test the API:
   ```bash
   API_URL="$(terraform output -raw api_base_url)"
   curl "$API_URL/health"
   curl -X POST "$API_URL/echo" -H 'content-type: application/json' -d '{"assignment":"devops"}'
   ```

## GitHub Actions OIDC setup

1. Create an IAM OIDC provider for `token.actions.githubusercontent.com` if your AWS account does not already have one.
2. Create an IAM role trusted only for your repository and `ref:refs/heads/main` (and the GitHub environment if using environment-bound deployment).
3. Grant the role least-privilege permissions for the resources Terraform manages, plus the state bucket's required `s3:ListBucket`, `s3:GetObject`, `s3:PutObject`, and `s3:DeleteObject` access to the specific state key and DynamoDB lock-table actions. Terraform also needs create/read/update/delete permissions for the Lambda, API Gateway, IAM role/policy attachment, and CloudWatch log group in this project. Avoid permanent `AdministratorAccess`.
4. In GitHub repository **Settings → Secrets and variables → Actions**, add:
   - Secret `AWS_ROLE_TO_ASSUME`: full IAM role ARN.
   - Variable `AWS_REGION`: `us-east-1`.
   - Variable `TF_STATE_BUCKET`: dedicated state bucket name.
   - Variable `TF_STATE_KEY`: `serverless-devops/dev/terraform.tfstate`.
   - Variable `TF_STATE_LOCK_TABLE`: DynamoDB lock table name.
   - Variable `GRAFANA_OTLP_ENDPOINT`: your exact Grafana Cloud OTLP endpoint.
   - Secret `GRAFANA_OTLP_HEADERS`: the authorization header value in OTLP format.
5. Create a GitHub Environment named `dev` if you want environment protections.
6. Push to `main`; the CI workflow validates code and the deployment workflow applies Terraform and smoke-tests the endpoint.

### Terraform state security

The S3 backend is configured as a partial backend, so `terraform init` must receive bucket, key, region, and DynamoDB lock table settings. Restrict access to the state bucket and lock table, enable versioning and encryption, and never commit state files. Terraform state can contain sensitive values.

## Observability checklist

- [ ] Logs visible in Grafana Cloud through the configured OTLP log exporter; also verify the Lambda CloudWatch log group.
- [ ] Metrics: confirm `app_http_requests`, `app_http_errors`, and `app_http_request_duration_ms` in Grafana Cloud; use CloudWatch for native Lambda Invocations, Errors, and Duration.
- [ ] Traces: call the API several times and verify spans for `http.request` in Grafana Cloud.
- [ ] Dashboard: build/save panels for request rate, error count/rate, latency, Lambda invocations/errors/duration, and trace exploration.
- [ ] Capture screenshots only after the signals are visible and label them with the deployment environment.

## Security and operational follow-ups

- Keep Grafana tokens in GitHub Secrets / protected runtime configuration.
- Use GitHub OIDC; do not store AWS access keys in repository secrets.
- Add API throttling, alarms, log retention review, and a rollback/versioning strategy before production.
- For production, use separate AWS accounts or isolated environments and a remote Terraform backend.
- Review dependency updates and pin third-party GitHub Actions to full commit SHAs for a hardened supply chain.
