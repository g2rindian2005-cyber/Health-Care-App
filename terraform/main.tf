# ============================================================
# AWS Hospital Management System — Infrastructure as Code
# Provisions: VPC, DynamoDB tables, 7 Lambdas + db-init, API Gateway, S3, EC2, IAM
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
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
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
      name = "hospital-id-counters"
      pk   = "table_name"
      gsis = {}
    }
    users = {
      name = "hospital-users"
      pk   = "email"
      gsis = {}
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
    SMTP_HOST           = "email-smtp.${var.aws_region}.amazonaws.com"
    SMTP_PORT           = "587"
    AUTH_USERNAME       = var.auth_admin_username
    AUTH_EMAIL          = var.ses_from_email
    AUTH_PASSWORD       = var.auth_admin_password
    JWT_SECRET          = local.jwt_secret
    SMTP_USERNAME       = var.ses_smtp_username
    SMTP_PASSWORD       = var.ses_smtp_password
    SMTP_FROM_EMAIL     = var.ses_from_email
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
    type = each.key == "counters" ? "S" : "N"
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
    { name = "auth", source = "../backend/auth-lambda" },
    { name = "lab", source = "../backend/lab-lambda" },
    { name = "pharmacy", source = "../backend/pharmacy-lambda" },
  ]
}

# Install deps + zip each lambda directory
resource "archive_file" "lambda_zip" {
  count       = length(local.lambda_services)
  type        = "zip"
  source_dir  = local.lambda_services[count.index].source
  output_path = "${path.module}/build/${local.lambda_services[count.index].name}.zip"
}

# Generated only when var.jwt_secret is empty (e.g. a fresh clone with
# no tfvars): keeps `terraform plan` prompt-free without committing a
# real secret to git. The value lives only in Terraform state.
resource "random_password" "jwt_secret" {
  count   = var.jwt_secret == "" ? 1 : 0
  length  = 48
  special = false
}

locals {
  jwt_secret = var.jwt_secret != "" ? var.jwt_secret : random_password.jwt_secret[0].result
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
# auth function fails with "No module named 'cryptography'".
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
    auth        = 4 # -> auth-lambda
    lab         = 5 # -> lab-lambda
    pharmacy    = 6 # -> pharmacy-lambda
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

# ============================================================
# EC2 — Nginx serving the frontend (production front)
# ============================================================





# Stable public address for the EC2 mirror: without this, every instance
# replacement changes the IP (it changed twice during the first deploy).

