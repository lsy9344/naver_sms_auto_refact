###############################################################################
# CloudWatch Module Variables
###############################################################################

variable "lambda_function_name" {
  description = "Name of the Lambda function for which to create logs and monitoring"
  type        = string
  default     = "naver-sms-automation"
}

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
  description = "Email address for alarm notifications (optional, leave empty to skip)"
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

variable "lambda_role_arn" {
  description = "ARN of the Lambda execution role (for IAM policy attachment reference)"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "aws_region" {
  description = "AWS region for CloudWatch resources"
  type        = string
  default     = "ap-northeast-2"
}

variable "cloudwatch_namespace" {
  description = "CloudWatch namespace for custom metrics"
  type        = string
  default     = "NaverSMSAutomation"
}
