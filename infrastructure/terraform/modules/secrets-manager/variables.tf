###############################################################################
# Secrets Manager Module Variables
###############################################################################

variable "naver_credentials" {
  description = "Naver login credentials (sensitive)"
  type = object({
    username = string
    password = string
  })
  sensitive = true
}

variable "sens_credentials" {
  description = "Naver Cloud SENS API credentials (sensitive)"
  type = object({
    access_key = string
    secret_key = string
    service_id = string
  })
  sensitive = true
}

variable "telegram_credentials" {
  description = "Telegram bot credentials (sensitive)"
  type = object({
    bot_token = string
    chat_id   = string
  })
  sensitive = true
}

variable "lambda_role_arn" {
  description = "ARN of the Lambda execution role allowed to read secrets"
  type        = string
}

variable "ci_deployment_role_arn" {
  description = "ARN of the CI deployment role allowed to manage secrets"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod, sandbox)"
  type        = string
}

variable "secret_recovery_window_days" {
  description = "Number of days for secret recovery window before permanent deletion"
  type        = number
  default     = 7
  validation {
    condition     = var.secret_recovery_window_days >= 7 && var.secret_recovery_window_days <= 30
    error_message = "Recovery window must be between 7 and 30 days."
  }
}

variable "tags" {
  description = "Common tags to apply to resources"
  type        = map(string)
  default     = {}
}