###############################################################################
# Global variables for multi-environment support
###############################################################################

variable "aws_region" {
  description = "AWS region for resource provisioning"
  type        = string
  default     = "ap-northeast-2"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod", "sandbox"], var.environment)
    error_message = "Environment must be dev, staging, prod, or sandbox."
  }
}

variable "aws_account_id" {
  description = "AWS account ID"
  type        = string
}

###############################################################################
# ECR variables
###############################################################################

variable "ecr_repository_name" {
  description = "Name of the ECR repository"
  type        = string
  default     = "naver-sms-automation"
}

variable "ecr_image_tag_mutability" {
  description = "Image tag mutability setting (MUTABLE or IMMUTABLE)"
  type        = string
  default     = "MUTABLE"
  validation {
    condition     = contains(["MUTABLE", "IMMUTABLE"], var.ecr_image_tag_mutability)
    error_message = "Must be MUTABLE or IMMUTABLE."
  }
}

variable "ecr_lifecycle_max_image_count" {
  description = "Maximum number of images to keep in ECR before expiring"
  type        = number
  default     = 5
}

###############################################################################
# Secrets Manager variables
###############################################################################

variable "naver_credentials" {
  description = "Naver login credentials (sensitive)"
  type = object({
    username = string
    password = string
  })
  sensitive = true
  default = {
    username = "CHANGE_ME"
    password = "CHANGE_ME"
  }
}

variable "sens_credentials" {
  description = "Naver Cloud SENS API credentials (sensitive)"
  type = object({
    access_key = string
    secret_key = string
    service_id = string
  })
  sensitive = true
  default = {
    access_key = "CHANGE_ME"
    secret_key = "CHANGE_ME"
    service_id = "CHANGE_ME"
  }
}

variable "telegram_credentials" {
  description = "Telegram bot credentials (sensitive)"
  type = object({
    bot_token = string
    chat_id   = string
  })
  sensitive = true
  default = {
    bot_token = "CHANGE_ME"
    chat_id   = "CHANGE_ME"
  }
}

variable "lambda_role_arn" {
  description = "ARN of the Lambda execution role allowed to read secrets"
  type        = string
}

variable "ci_deployment_role_arn" {
  description = "ARN of the CI deployment role allowed to manage secrets"
  type        = string
}

###############################################################################
# CloudWatch variables
###############################################################################

variable "log_retention_days" {
  description = "CloudWatch log retention period in days"
  type        = number
  default     = 90
  validation {
    condition     = var.log_retention_days > 0
    error_message = "Log retention days must be positive."
  }
}

variable "alarm_email" {
  description = "Email address for alarm notifications (optional)"
  type        = string
  default     = ""
}

variable "error_alarm_threshold" {
  description = "Threshold for Lambda error alarm (errors per 5 minutes)"
  type        = number
  default     = 1
}

variable "login_failure_alarm_threshold" {
  description = "Threshold for login failure alarm (failures per 30 minutes)"
  type        = number
  default     = 3
}

variable "lambda_function_name" {
  description = "Name of the Lambda function monitored by CloudWatch resources"
  type        = string
  default     = "naver-sms-automation"
}

variable "cloudwatch_namespace" {
  description = "CloudWatch namespace for custom metrics emitted by the Lambda function"
  type        = string
  default     = "NaverSMSAutomation"
}
