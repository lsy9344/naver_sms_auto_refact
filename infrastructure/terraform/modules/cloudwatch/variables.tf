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

# Story 5.4: Comparison Monitoring Configuration
variable "comparison_namespace" {
  description = "CloudWatch namespace for comparison metrics (Story 5.4)"
  type        = string
  default     = "naver-sms/comparison"
}

variable "comparison_metrics_enabled" {
  description = "Enable comparison metrics and alarms (Story 5.4)"
  type        = bool
  default     = true
}

variable "discrepancy_alarm_threshold" {
  description = "Alert threshold for discrepancies found during comparison (Story 5.4)"
  type        = number
  default     = 0
}

variable "match_percentage_alarm_threshold" {
  description = "Alert threshold for match percentage during comparison (Story 5.4)"
  type        = number
  default     = 100
}

# Story 5.4: Notification Webhook URLs
variable "slack_webhook_url" {
  description = "Slack webhook URL for alarm notifications (optional)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "telegram_webhook_url" {
  description = "Telegram webhook URL for alarm notifications (optional)"
  type        = string
  default     = ""
  sensitive   = true
}
