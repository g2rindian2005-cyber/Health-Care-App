# ============================================================
# Input variables — override in terraform.tfvars
# ============================================================

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project prefix used in resource names"
  type        = string
  default     = "hospital"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "prod"
}

# ---- Networking ----
variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "AZs to spread resources across"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

# ---- EC2 ----
variable "ec2_instance_type" {
  description = "EC2 instance type for Nginx frontend"
  type        = string
  default     = "t3.micro"
}

variable "ssh_key_name" {
  description = "Name of the EC2 key pair for SSH access"
  type        = string
  default     = "hospital-key"
}

# ---- SES SMTP ----
variable "ses_smtp_username" {
  description = "SES SMTP username"
  type        = string
  default     = ""
}

variable "ses_smtp_password" {
  description = "SES SMTP password"
  type        = string
  sensitive   = true
  default     = ""
}

variable "ses_from_email" {
  description = "Verified SES sender email. Also the built-in admin's email (AUTH_EMAIL): the admin signs in to Cognito with this email."
  type        = string
  default     = "gokul9356782322@gmail.com"
}

# ---- Outgoing mail (SMTP) ----
# Unused by sign-in since the Cognito migration — Cognito sends its
# own verification emails, so there is no OTP mail any more. Left in
# place (harmless) so existing tfvars files keep working.
variable "smtp_host" {
  description = "SMTP host for OTP mail. Empty = SES endpoint for this region."
  type        = string
  default     = ""
}

variable "smtp_port" {
  description = "SMTP port for OTP mail"
  type        = string
  default     = "587"
}

variable "smtp_username" {
  description = "SMTP username for OTP mail. Empty = SES SMTP username."
  type        = string
  default     = ""
}

variable "smtp_password" {
  description = "SMTP password for OTP mail (Gmail App Password when using Gmail SMTP). Empty = SES SMTP password."
  type        = string
  sensitive   = true
  default     = ""
}

variable "smtp_from_email" {
  description = "Sender address for OTP mail. Empty = SES sender email."
  type        = string
  default     = ""
}

# ---- Lambda ----
variable "lambda_memory" {
  description = "Memory allocated to each Lambda (MB)"
  type        = number
  default     = 256
}

variable "lambda_timeout" {
  description = "Lambda timeout in seconds"
  type        = number
  default     = 30
}

# ---- Auth (Cognito) ----
# Sign-in is AWS Cognito now. These values are used only by the
# Cognito User Migration Lambda (old users signing in for the first
# time) — there is no auth Lambda and no JWT_SECRET any more. The
# declarations stay so existing terraform.tfvars files keep parsing.
variable "auth_admin_username" {
  description = "UNUSED since the Cognito migration (Cognito usernames are emails; the admin signs in with ses_from_email). Kept so existing tfvars files still parse."
  type        = string
  default     = "admin"
}

variable "auth_admin_password" {
  description = "Built-in admin password. Used only by the Cognito migration Lambda: the admin signs in with ses_from_email + this password, and lands in the Admins group."
  type        = string
  sensitive   = true
  default     = "admin123"
}

variable "jwt_secret" {
  description = "UNUSED since the Cognito migration (tokens are Cognito RS256 JWTs verified against the pool JWKS). Kept so existing tfvars files still parse."
  type        = string
  sensitive   = true
  default     = ""
}
