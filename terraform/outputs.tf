# ============================================================
# Outputs — printed after `terraform apply`
# ============================================================

output "dynamodb_tables" {
  description = "DynamoDB tables — one per former MySQL table (PAY_PER_REQUEST)"
  value       = { for k, t in aws_dynamodb_table.hospital : k => t.name }
}

output "api_gateway_url" {
  description = "API Gateway invoke URL — set as API_GATEWAY_URL"
  value       = aws_api_gateway_stage.prod.invoke_url
}

output "s3_website_url" {
  description = "S3 static website endpoint"
  value       = "${aws_s3_bucket.frontend.id}.s3-website.${var.aws_region}.amazonaws.com"
}



output "lambda_function_names" {
  description = "Names of the deployed Lambda functions"
  value       = aws_lambda_function.service[*].function_name
}

output "configuration_reminder" {
  description = "Next steps to wire the app to the infra"
  value       = <<EOF
  ─────────────────────────────────────────────
  1. Data is seeded automatically:
     The hospital-db-init-service Lambda runs once after `terraform
     apply` and loads the sample data (5 patients, 5 doctors, 5
     bills, 12 lab tests, 12 medicines, ...) into the DynamoDB
     tables. No SQL, no EC2, no manual step. Re-running it is safe.

  2. Set API URL in frontend/js/api.js:
     API_BASE_URL = "${aws_api_gateway_stage.prod.invoke_url}"

  3. Upload frontend to S3:
     aws s3 sync frontend/ s3://${aws_s3_bucket.frontend.id}/

  4. SES: verify your sender email + request production access.

  5. Open: http://${aws_s3_bucket.frontend.id}.s3-website.${var.aws_region}.amazonaws.com
     
  ─────────────────────────────────────────────
EOF
}
