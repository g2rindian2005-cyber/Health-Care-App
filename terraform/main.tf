# ============================================================
# AWS Hospital Management System — Infrastructure as Code
# Provisions: VPC, DynamoDB tables, 6 data Lambdas + db-init +
# Cognito migration Lambda, Cognito User Pool, API Gateway, S3,
# EC2, IAM. Auth is AWS Cognito (User Pool): sign-up, email
# verification and sign-in happen against Cognito directly — there
# is no auth Lambda any more. Old users keep working through the
# User Migration trigger (see backend/cognito-migration-lambda).
# Databases are DynamoDB (PAY_PER_REQUEST) — no RDS instances, no VPC
# needed for the Lambdas, no SQL to run.
# ============================================================

terraform {
  required_version = ">= 1.3.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Tag everything for easy identification
locals {
  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
  # DynamoDB tables — one per former MySQL table.
  # key -> { table name, partition key, GSIs (index name -> key attribute) }
  tables = {
    patients = {
      name = "hospital-patients"
      pk   = "patient_id"
      gsis = {}
    }
    doctors = {
      name = "hospital-doctors"
      pk   = "doctor_id"
      gsis = {}
    }
    assignments = {
      name = "hospital-doctor-assignments"
      pk   = "assignment_id"
      gsis = {
        "patient_id-index" = "patient_id"
        "doctor_id-index"  = "doctor_id"
      }
    }
    diseases = {
      name = "hospital-diseases"
      pk   = "disease_id"
      gsis = { "patient_id-index" = "patient_id" }
    }
    bills = {
      name = "hospital-bills"
      pk   = "bill_id"
      gsis = { "patient_id-index" = "patient_id" }
    }
    payments = {
      name = "hospital-payments"
      pk   = "payment_id"
      gsis = {
        "bill_id-index"    = "bill_id"
        "patient_id-index" = "patient_id"
      }
    }
    lab_tests = {
      name = "hospital-lab-tests"
      pk   = "test_id"
      gsis = {}
    }
    lab_orders = {
      name = "hospital-lab-orders"
      pk   = "order_id"
      gsis = { "patient_id-index" = "patient_id" }
    }
    medicines = {
      name = "hospital-medicines"
      pk   = "medicine_id"
      gsis = {}
    }
    prescriptions = {
      name = "hospital-prescriptions"
      pk   = "prescription_id"
      gsis = { "patient_id-index" = "patient_id" }
    }
    counters = {
      name    = "hospital-id-counters"
      pk      = "table_name"
      pk_type = "S"
      gsis    = {}
    }
    # Kept for the Cognito User Migration trigger: on an old user's
    # first Cognito sign-in the migration Lambda reads this table to
    # check their existing PBKDF2 password. Read-only now — nothing
    # writes new rows here. Once every old user has signed in once
    # through Cognito, this table can be removed.
    users = {
      name    = "hospital-users"
      pk      = "email"
      pk_type = "S"
      gsis    = {}
    }
  }
  common_env = {
    PATIENTS_TABLE      = "hospital-patients"
    DOCTORS_TABLE       = "hospital-doctors"
    ASSIGNMENTS_TABLE   = "hospital-doctor-assignments"
    DISEASES_TABLE      = "hospital-diseases"
    BILLS_TABLE         = "hospital-bills"
    PAYMENTS_TABLE      = "hospital-payments"
    LAB_TESTS_TABLE     = "hospital-lab-tests"
    LAB_ORDERS_TABLE    = "hospital-lab-orders"
    MEDICINES_TABLE     = "hospital-medicines"
    PRESCRIPTIONS_TABLE = "hospital-prescriptions"
    COUNTERS_TABLE      = "hospital-id-counters"
    USERS_TABLE         = "hospital-users"
    # Cognito (set from the resources below — the doctor Lambda
    # verifies tokens against this pool, the migration Lambda reads
    # it to put users in their group).
    COGNITO_USER_POOL_ID = aws_cognito_user_pool.hospital.id
    COGNITO_CLIENT_ID    = aws_cognito_user_pool_client.hospital.id
    # Built-in admin, for the migration Lambda only: the admin signs
    # in with the admin EMAIL now (Cognito usernames are emails) and
    # the same password as before.
    AUTH_EMAIL    = var.ses_from_email
    AUTH_PASSWORD = var.auth_admin_password
    # SMTP values are unused by sign-in since Cognito sends its own
    # verification emails. Left in place (harmless) so existing
    # tfvars files keep working.
    SMTP_HOST       = var.smtp_host != "" ? var.smtp_host : "email-smtp.${var.aws_region}.amazonaws.com"
    SMTP_PORT       = var.smtp_port
    SMTP_USERNAME   = var.smtp_username != "" ? var.smtp_username : var.ses_smtp_username
    SMTP_PASSWORD   = var.smtp_password != "" ? var.smtp_password : var.ses_smtp_password
    SMTP_FROM_EMAIL = var.smtp_from_email != "" ? var.smtp_from_email : var.ses_from_email
  }
  # Env for the Cognito migration Lambda ONLY. It deliberately leaves
  # out COGNITO_USER_POOL_ID / COGNITO_CLIENT_ID: the user pool's
  # lambda_config points at this Lambda, so if its env referenced
  # the pool, Terraform would see a cycle (pool -> Lambda -> pool).
  # The post-auth handler reads the pool id from the trigger event
  # (event.userPoolId) instead.
  migration_env = {
    USERS_TABLE   = "hospital-users"
    AUTH_EMAIL    = var.ses_from_email
    AUTH_PASSWORD = var.auth_admin_password
  }
}

# ============================================================
# VPC
# ============================================================
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = merge(local.tags, { Name = "${var.project_name}-vpc" })
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id
  tags   = merge(local.tags, { Name = "${var.project_name}-igw" })
}

# Public subnets (EC2)
resource "aws_subnet" "public" {
  count                   = length(var.availability_zones)
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index)
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true
  tags                    = merge(local.tags, { Name = "${var.project_name}-public-${count.index}" })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }
  tags = merge(local.tags, { Name = "${var.project_name}-rt-public" })
}

resource "aws_route_table_association" "public" {
  count          = length(aws_subnet.public)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# ============================================================
# Security Groups
# ============================================================
resource "aws_security_group" "ec2" {
  name        = "${var.project_name}-ec2-sg"
  description = "Allow HTTP/SSH to EC2"
  vpc_id      = aws_vpc.main.id
  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = local.tags
}

# ============================================================
# DynamoDB tables (PAY_PER_REQUEST — no instances, no capacity plan)
# One table per former MySQL table; GSIs serve the foreign-key
# lookups (bills/payments/orders by patient_id, etc.)
# ============================================================
resource "aws_dynamodb_table" "hospital" {
  for_each                    = local.tables
  name                        = each.value.name
  billing_mode                = "PAY_PER_REQUEST"
  hash_key                    = each.value.pk
  deletion_protection_enabled = false

  attribute {
    name = each.value.pk
    # Numeric IDs everywhere except the String-keyed tables
    # (counters, users) — declared per table via pk_type.
    type = lookup(each.value, "pk_type", "N")
  }

  dynamic "attribute" {
    for_each = each.value.gsis
    content {
      name = attribute.value
      type = "N"
    }
  }

  dynamic "global_secondary_index" {
    for_each = each.value.gsis
    content {
      name            = global_secondary_index.key
      hash_key        = global_secondary_index.value
      projection_type = "ALL"
    }
  }

  tags = merge(local.tags, { Table = each.value.name })
}

# ============================================================
# IAM — Lambda execution role
# ============================================================
data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${var.project_name}-lambda-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
  tags               = local.tags
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_extras" {
  name = "${var.project_name}-lambda-extras"
  role = aws_iam_role.lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"], Resource = "*" },
      { Effect = "Allow", Action = ["ses:SendEmail", "ses:SendRawEmail"], Resource = "*" },
      # DynamoDB tables (incl. GSIs) — the data layer for all services
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem",
          "dynamodb:DeleteItem", "dynamodb:Query", "dynamodb:Scan",
          "dynamodb:BatchGetItem", "dynamodb:BatchWriteItem",
        ]
        Resource = concat(
          [for t in aws_dynamodb_table.hospital : t.arn],
          [for t in aws_dynamodb_table.hospital : "${t.arn}/index/*"],
        )
      },
      # Cognito: the migration Lambda puts a freshly signed-in user
      # in their group (Admins / Patients) via the post-auth trigger.
      {
        Effect   = "Allow"
        Action   = ["cognito-idp:AdminAddUserToGroup"]
        Resource = aws_cognito_user_pool.hospital.arn
      },
    ]
  })
}

# ============================================================
# Lambda packages (archive_file builds the zip from source)
# ============================================================
locals {
  lambda_services = [
    { name = "patient", source = "../backend/patient-lambda" },
    { name = "billing", source = "../backend/billing-lambda" },
    { name = "disease", source = "../backend/disease-lambda" },
    { name = "doctor", source = "../backend/doctor-lambda" },
    { name = "lab", source = "../backend/lab-lambda" },
    { name = "pharmacy", source = "../backend/pharmacy-lambda" },
  ]
  # NOTE: the auth Lambda is gone — sign-in is AWS Cognito now (see
  # the Cognito section below). Its old routes /auth/* are removed
  # from route_map as well. The Cognito migration Lambda is a
  # separate resource (aws_lambda_function.cognito_migration), not
  # part of this list: it is not an API Lambda.
}

# Install deps + zip each lambda directory
resource "archive_file" "lambda_zip" {
  count       = length(local.lambda_services)
  type        = "zip"
  source_dir  = local.lambda_services[count.index].source
  output_path = "${path.module}/build/${local.lambda_services[count.index].name}.zip"
}

# Build the dependency layer zip automatically, so a fresh clone can run
# `terraform plan/apply` directly — no manual build step. build_layer.py
# downloads Lambda-compatible wheels (manylinux/CPython 3.11) on any OS
# and zips them as build/deps-layer.zip.
resource "null_resource" "build_deps_layer" {
  triggers = {
    requirements = filebase64sha256("${path.module}/../backend/patient-lambda/requirements.txt")
    builder      = filebase64sha256("${path.module}/build_layer.py")
  }

  provisioner "local-exec" {
    command = "python3 ${path.module}/build_layer.py"
  }
}

# Shared dependencies layer (cryptography from requirements.txt;
# boto3 is already in the Lambda Python runtime).
# archive_file above only zips source code, so without this layer the
# doctor function fails with "No module named 'cryptography'" — it
# uses it to verify Cognito JWT signatures (RS256, see
# backend/doctor-lambda/cognito_auth.py).
resource "aws_lambda_layer_version" "deps" {
  filename            = "${path.module}/build/deps-layer.zip"
  layer_name          = "${var.project_name}-deps"
  compatible_runtimes = ["python3.11"]
  # Hash the requirements instead of the zip: the zip is generated during
  # apply, so it cannot be read at plan time on a fresh clone.
  source_code_hash = null_resource.build_deps_layer.triggers["requirements"]
  description      = "cryptography for hospital Lambda services"
  depends_on       = [null_resource.build_deps_layer]
}

# ============================================================
# db-init Lambda — seeds the DynamoDB tables with the sample data
# (backend/db-init-lambda/seed/*.json). Runs automatically once
# after the tables exist, and re-runs when the code or a seed file
# changes. Idempotent: existing items are left untouched.
# ============================================================
resource "archive_file" "db_init_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../backend/db-init-lambda"
  output_path = "${path.module}/build/db-init.zip"
  excludes    = ["__pycache__", "*.pyc"]
}

resource "aws_lambda_function" "db_init" {
  function_name    = "${var.project_name}-db-init-service"
  runtime          = "python3.11"
  handler          = "lambda_function.lambda_handler"
  role             = aws_iam_role.lambda.arn
  filename         = archive_file.db_init_zip.output_path
  source_code_hash = archive_file.db_init_zip.output_base64sha256
  memory_size      = var.lambda_memory
  timeout          = 300

  environment {
    variables = local.common_env
  }
  tags       = local.tags
  depends_on = [aws_dynamodb_table.hospital]
}

resource "aws_lambda_invocation" "db_init" {
  function_name = aws_lambda_function.db_init.function_name
  input         = jsonencode({ "seed" = "initial" })
  triggers = {
    code_hash = archive_file.db_init_zip.output_base64sha256
  }
  depends_on = [aws_dynamodb_table.hospital]
}

# ============================================================
# Lambda functions (no VPC — DynamoDB is reached via the AWS API,
# so the functions have internet access by default and no NAT
# gateway is needed)
# ============================================================
resource "aws_lambda_function" "service" {
  count            = length(local.lambda_services)
  function_name    = "${var.project_name}-${local.lambda_services[count.index].name}-service"
  runtime          = "python3.11"
  handler          = "lambda_function.lambda_handler"
  role             = aws_iam_role.lambda.arn
  filename         = archive_file.lambda_zip[count.index].output_path
  source_code_hash = archive_file.lambda_zip[count.index].output_base64sha256
  layers           = [aws_lambda_layer_version.deps.arn]
  memory_size      = var.lambda_memory
  timeout          = var.lambda_timeout

  environment {
    variables = local.common_env
  }
  tags = local.tags
}

# ============================================================
# AWS Cognito — authentication (replaces the old auth Lambda)
# Sign-up, email verification and sign-in happen against this user
# pool directly from the browser (embedded SDK flow, no hosted UI).
# Old users keep working: the User Migration trigger checks their
# existing PBKDF2 password in hospital-users on their first
# Cognito sign-in and Cognito creates the account for them.
# Role = Cognito group (Admins / Patients), read from the token's
# cognito:groups claim (custom:role claim as fallback — see the
# migration Lambda). New sign-ups are patients by default; admins
# are created by hand (see outputs / the README section on this).
# ============================================================
resource "aws_cognito_user_pool" "hospital" {
  name                     = "${var.project_name}-user-pool"
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]
  mfa_configuration        = "OFF"

  admin_create_user_config {
    allow_admin_create_user_only = false
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  # Same rule the old register page enforced: at least 6 characters,
  # no complexity requirements — Cognito defaults would demand 8+
  # with upper/lower/number/symbol.
  password_policy {
    minimum_length                   = 6
    require_lowercase                = false
    require_numbers                  = false
    require_symbols                  = false
    require_uppercase                = false
    temporary_password_validity_days = 7
  }

  # Standard attributes. The string constraints stop Terraform from
  # planning a perpetual diff on these blocks.
  schema {
    name                = "email"
    attribute_data_type = "String"
    required            = true
    mutable             = true
    string_attribute_constraints {
      min_length = 1
      max_length = 2048
    }
  }
  schema {
    name                = "name"
    attribute_data_type = "String"
    required            = true
    mutable             = true
    string_attribute_constraints {
      min_length = 1
      max_length = 100
    }
  }
  # Custom attribute, set by the migration Lambda for migrated users
  # (and read by the frontend + doctor Lambda as a fallback role).
  # Custom attribute names carry the "custom:" prefix in Terraform.
  schema {
    name                = "custom:role"
    attribute_data_type = "String"
    required            = false
    mutable             = true
    string_attribute_constraints {
      min_length = 1
      max_length = 20
    }
  }

  lambda_config {
    user_migration      = aws_lambda_function.cognito_migration.arn
    post_authentication = aws_lambda_function.cognito_migration.arn
  }

  tags = local.tags
}

resource "aws_cognito_user_group" "admins" {
  name         = "Admins"
  user_pool_id = aws_cognito_user_pool.hospital.id
  description  = "Hospital administrators — full dashboard access"
  precedence   = 1
}

resource "aws_cognito_user_group" "patients" {
  name         = "Patients"
  user_pool_id = aws_cognito_user_pool.hospital.id
  description  = "Registered patients — own panel and appointments only"
  precedence   = 2
}

resource "aws_cognito_user_pool_client" "hospital" {
  name                          = "${var.project_name}-client"
  user_pool_id                  = aws_cognito_user_pool.hospital.id
  generate_secret               = false
  explicit_auth_flows           = ["ALLOW_USER_SRP_AUTH", "ALLOW_REFRESH_TOKEN_AUTH", "ALLOW_USER_PASSWORD_AUTH"]
  prevent_user_existence_errors = "ENABLED"
  supported_identity_providers  = ["COGNITO"]
  # ID tokens last 8h, like the old session JWTs; the SDK refreshes
  # them automatically with the 30-day refresh token.
  access_token_validity  = 1
  id_token_validity      = 8
  refresh_token_validity = 30
  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }
}

# Cognito migration Lambda — User Migration + Post Authentication
# triggers (backend/cognito-migration-lambda). It is NOT an API
# Lambda: it has its own zip + function resource and is not in
# local.lambda_services. Its env (local.migration_env) deliberately
# leaves out the pool id — the pool's lambda_config points here, so
# an env reference to the pool would be a Terraform cycle.
resource "archive_file" "cognito_migration_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../backend/cognito-migration-lambda"
  output_path = "${path.module}/build/cognito-migration.zip"
  excludes    = ["__pycache__", "*.pyc"]
}

resource "aws_lambda_function" "cognito_migration" {
  function_name    = "${var.project_name}-cognito-migration-service"
  runtime          = "python3.11"
  handler          = "lambda_function.lambda_handler"
  role             = aws_iam_role.lambda.arn
  filename         = archive_file.cognito_migration_zip.output_path
  source_code_hash = archive_file.cognito_migration_zip.output_base64sha256
  memory_size      = var.lambda_memory
  timeout          = var.lambda_timeout

  environment {
    variables = local.migration_env
  }
  tags = local.tags
}

resource "aws_lambda_permission" "cognito_migration" {
  statement_id  = "AllowCognitoInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cognito_migration.function_name
  principal     = "cognito-idp.amazonaws.com"
  source_arn    = aws_cognito_user_pool.hospital.arn
}

# ============================================================
# API Gateway — REST API with per-base-path proxy routes
# Each base path (patients, bills, payments, dues, diseases,
# doctors, assignments) gets its own resource + {proxy+} child,
# each routing to the correct Lambda via AWS_PROXY.
# ============================================================
locals {
  route_map = {
    patients    = 0 # -> patient-lambda
    bills       = 1 # -> billing-lambda
    payments    = 1 # -> billing-lambda
    dues        = 1 # -> billing-lambda
    diseases    = 2 # -> disease-lambda
    doctors     = 3 # -> doctor-lambda
    assignments = 3 # -> doctor-lambda
    lab         = 4 # -> lab-lambda
    pharmacy    = 5 # -> pharmacy-lambda
    # NOTE: no auth route any more — /auth/login, /auth/verify-otp
    # and /auth/register are retired; Cognito handles sign-in.
  }
}

resource "aws_api_gateway_rest_api" "hospital" {
  name        = "${var.project_name}-api"
  description = "Hospital Management System API"
  tags        = local.tags
}

# Top-level resource per base path: /patients, /bills, ...
resource "aws_api_gateway_resource" "base" {
  for_each    = local.route_map
  rest_api_id = aws_api_gateway_rest_api.hospital.id
  parent_id   = aws_api_gateway_rest_api.hospital.root_resource_id
  path_part   = each.key
}

# Child proxy resource: /patients/{proxy+}, /bills/{proxy+}, ...
resource "aws_api_gateway_resource" "proxy" {
  for_each    = local.route_map
  rest_api_id = aws_api_gateway_rest_api.hospital.id
  parent_id   = aws_api_gateway_resource.base[each.key].id
  path_part   = "{proxy+}"
}

# ANY method on the base resource (handles GET /patients)
resource "aws_api_gateway_method" "base_any" {
  for_each      = local.route_map
  rest_api_id   = aws_api_gateway_rest_api.hospital.id
  resource_id   = aws_api_gateway_resource.base[each.key].id
  http_method   = "ANY"
  authorization = "NONE"
}

# ANY method on the proxy child (handles /patients/123, /bills/patient/1)
resource "aws_api_gateway_method" "proxy_any" {
  for_each      = local.route_map
  rest_api_id   = aws_api_gateway_rest_api.hospital.id
  resource_id   = aws_api_gateway_resource.proxy[each.key].id
  http_method   = "ANY"
  authorization = "NONE"
}

# Integration: base resource -> correct Lambda
resource "aws_api_gateway_integration" "base" {
  for_each                = local.route_map
  rest_api_id             = aws_api_gateway_rest_api.hospital.id
  resource_id             = aws_api_gateway_resource.base[each.key].id
  http_method             = aws_api_gateway_method.base_any[each.key].http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.service[local.route_map[each.key]].invoke_arn
}

# Integration: proxy child -> correct Lambda
resource "aws_api_gateway_integration" "proxy" {
  for_each                = local.route_map
  rest_api_id             = aws_api_gateway_rest_api.hospital.id
  resource_id             = aws_api_gateway_resource.proxy[each.key].id
  http_method             = aws_api_gateway_method.proxy_any[each.key].http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.service[local.route_map[each.key]].invoke_arn
}

# CORS: OPTIONS on base + proxy for each base path
resource "aws_api_gateway_method" "base_options" {
  for_each      = local.route_map
  rest_api_id   = aws_api_gateway_rest_api.hospital.id
  resource_id   = aws_api_gateway_resource.base[each.key].id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_method" "proxy_options" {
  for_each      = local.route_map
  rest_api_id   = aws_api_gateway_rest_api.hospital.id
  resource_id   = aws_api_gateway_resource.proxy[each.key].id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "cors_base" {
  for_each    = local.route_map
  rest_api_id = aws_api_gateway_rest_api.hospital.id
  resource_id = aws_api_gateway_resource.base[each.key].id
  http_method = aws_api_gateway_method.base_options[each.key].http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_integration" "cors_proxy" {
  for_each    = local.route_map
  rest_api_id = aws_api_gateway_rest_api.hospital.id
  resource_id = aws_api_gateway_resource.proxy[each.key].id
  http_method = aws_api_gateway_method.proxy_options[each.key].http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "cors_base" {
  for_each    = local.route_map
  rest_api_id = aws_api_gateway_rest_api.hospital.id
  resource_id = aws_api_gateway_resource.base[each.key].id
  http_method = aws_api_gateway_method.base_options[each.key].http_method
  status_code = "200"
  response_models = {
    "application/json" = "Empty"
  }
  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin"  = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Headers" = true
  }
  depends_on = [aws_api_gateway_integration.cors_base]
}

resource "aws_api_gateway_method_response" "cors_proxy" {
  for_each    = local.route_map
  rest_api_id = aws_api_gateway_rest_api.hospital.id
  resource_id = aws_api_gateway_resource.proxy[each.key].id
  http_method = aws_api_gateway_method.proxy_options[each.key].http_method
  status_code = "200"
  response_models = {
    "application/json" = "Empty"
  }
  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin"  = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Headers" = true
  }
  depends_on = [aws_api_gateway_integration.cors_proxy]
}

# Integration responses that set the actual CORS header values
resource "aws_api_gateway_integration_response" "cors_base" {
  for_each    = local.route_map
  rest_api_id = aws_api_gateway_rest_api.hospital.id
  resource_id = aws_api_gateway_resource.base[each.key].id
  http_method = aws_api_gateway_method.base_options[each.key].http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,POST,PUT,DELETE,OPTIONS'"
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
  }
  depends_on = [aws_api_gateway_method_response.cors_base]
}

resource "aws_api_gateway_integration_response" "cors_proxy" {
  for_each    = local.route_map
  rest_api_id = aws_api_gateway_rest_api.hospital.id
  resource_id = aws_api_gateway_resource.proxy[each.key].id
  http_method = aws_api_gateway_method.proxy_options[each.key].http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,POST,PUT,DELETE,OPTIONS'"
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
  }
  depends_on = [aws_api_gateway_method_response.cors_proxy]
}

# Permissions for API Gateway to invoke each Lambda
resource "aws_lambda_permission" "apigw" {
  count         = length(local.lambda_services)
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.service[count.index].function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.hospital.execution_arn}/*/*"
}

resource "aws_api_gateway_deployment" "hospital" {
  rest_api_id = aws_api_gateway_rest_api.hospital.id
  depends_on = [
    aws_api_gateway_integration.base,
    aws_api_gateway_integration.proxy,
    aws_api_gateway_integration.cors_base,
    aws_api_gateway_integration.cors_proxy,
  ]
  triggers = {
    redeployment = sha1(jsonencode([
      keys(aws_api_gateway_resource.base),
      keys(aws_api_gateway_resource.proxy),
    ]))
  }
  lifecycle { create_before_destroy = true }
}

resource "aws_api_gateway_stage" "prod" {
  rest_api_id   = aws_api_gateway_rest_api.hospital.id
  stage_name    = var.environment
  deployment_id = aws_api_gateway_deployment.hospital.id
  tags          = local.tags
}

# ============================================================
# S3 — static website hosting for the frontend
# ============================================================
resource "aws_s3_bucket" "frontend" {
  bucket = "${var.project_name}-management-frontend-bucket"
  tags   = local.tags
}

resource "aws_s3_bucket_versioning" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket                  = aws_s3_bucket.frontend.id
  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_website_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  index_document { suffix = "index.html" }
  error_document { key = "index.html" }
}

resource "aws_s3_bucket_policy" "frontend_public_read" {
  bucket = aws_s3_bucket.frontend.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "PublicReadGetObject"
      Effect    = "Allow"
      Principal = "*"
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.frontend.arn}/*"
    }]
  })
  depends_on = [aws_s3_bucket_public_access_block.frontend]
}

# Frontend API config — written by Terraform on every apply, so the
# site always points at THIS deployment's API Gateway. The frontend
# reads js/config.js before api.js; without this file the pages fall
# back to a hardcoded (dead) API URL and show "Unable to reach the
# server". No manual upload is needed: apply rewrites this file
# whenever the API URL changes (the etag tracks the content, so a
# changed URL forces an update). Note: CloudFront may keep serving
# a cached copy for up to an hour after a change — invalidate /*
# once if the new URL must take effect immediately.
# The file also carries the Cognito pool id + client id, so the
# login/register pages can sign in against this deployment's user
# pool without any manual step.
resource "aws_s3_object" "frontend_config_js" {
  bucket       = aws_s3_bucket.frontend.id
  key          = "js/config.js"
  content      = "window.HMS_CONFIG = { apiBase: \"${aws_api_gateway_stage.prod.invoke_url}\", cognitoUserPoolId: \"${aws_cognito_user_pool.hospital.id}\", cognitoClientId: \"${aws_cognito_user_pool_client.hospital.id}\" };\n"
  content_type = "application/javascript"
  etag         = md5("window.HMS_CONFIG = { apiBase: \"${aws_api_gateway_stage.prod.invoke_url}\", cognitoUserPoolId: \"${aws_cognito_user_pool.hospital.id}\", cognitoClientId: \"${aws_cognito_user_pool_client.hospital.id}\" };\n")

  depends_on = [aws_s3_bucket_policy.frontend_public_read]
}

# ============================================================
# CloudFront — HTTPS front door for the S3 website.
# The plain S3 website URL is HTTP on a shared amazonaws.com
# host, which browsers flag ("Not secure" / Safe Browsing).
# CloudFront serves the same site over HTTPS on its own
# *.cloudfront.net domain with a free certificate.
# Note: after syncing new frontend files, invalidate the
# cache (`aws cloudfront create-invalidation`) or wait up
# to an hour for the cached copy to expire.
# ============================================================
resource "aws_cloudfront_distribution" "frontend" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "HealtheCare frontend"
  default_root_object = "index.html"
  price_class         = "PriceClass_200"

  origin {
    domain_name = aws_s3_bucket_website_configuration.frontend.website_endpoint
    origin_id   = "s3-website"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    target_origin_id       = "s3-website"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    forwarded_values {
      query_string = false
      cookies { forward = "none" }
    }

    min_ttl     = 0
    default_ttl = 3600
    max_ttl     = 86400
  }

  restrictions {
    geo_restriction { restriction_type = "none" }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = local.tags
}

# ============================================================
# EC2 — Nginx serving the frontend (production front)
# ============================================================





# Stable public address for the EC2 mirror: without this, every instance
# replacement changes the IP (it changed twice during the first deploy).

