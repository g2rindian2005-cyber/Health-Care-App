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

output "cloudfront_url" {
  description = "CloudFront HTTPS URL for the frontend — use this, not the S3 website URL"
  value       = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}

output "cloudfront_domain" {
  description = "CloudFront distribution domain name"
  value       = aws_cloudfront_distribution.frontend.domain_name
}



output "lambda_function_names" {
  description = "Names of the deployed Lambda functions"
  value       = aws_lambda_function.service[*].function_name
}

output "cognito_user_pool_id" {
  description = "Cognito User Pool id — sign-in for the whole app runs against this pool"
  value       = aws_cognito_user_pool.hospital.id
}

output "cognito_client_id" {
  description = "Cognito User Pool client id (browser sign-in)"
  value       = aws_cognito_user_pool_client.hospital.id
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

  2. API URL + Cognito ids are wired automatically:
     Terraform writes js/config.js to S3 on every apply with the
     live API URL and the Cognito user pool + client ids (see
     aws_s3_object.frontend_config_js), so the site connects and
     signs in without any manual step. If the API URL ever
     changes, invalidate the CloudFront cache (/*) or wait up to
     an hour for the cached copy to expire.

  3. Upload frontend to S3:
     aws s3 sync frontend/ s3://${aws_s3_bucket.frontend.id}/

  4. Old users keep working — no re-registration:
     on their first Cognito sign-in the migration Lambda checks
     their existing password in the hospital-users table and
     Cognito creates the account for them, same password.

  5. Admin sign-in (no more username "admin"):
     the admin signs in with the admin EMAIL (${var.ses_from_email})
     and the auth_admin_password, and lands in the Admins group.
     Nothing to create: the first sign-in migrates the admin
     automatically. To make a second admin, create the user in
     the Cognito console and add them to the Admins group.

  6. SES is no longer needed for login: Cognito sends the
     verification emails itself.

  7. Open: http://${aws_s3_bucket.frontend.id}.s3-website.${var.aws_region}.amazonaws.com
     
  ─────────────────────────────────────────────
EOF
}
