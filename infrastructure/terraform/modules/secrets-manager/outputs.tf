###############################################################################
# Secrets Manager Module Outputs
###############################################################################

output "naver_credentials_secret_arn" {
  description = "ARN of the Naver credentials secret"
  value       = aws_secretsmanager_secret.secrets["naver-credentials"].arn
}

output "naver_credentials_secret_name" {
  description = "Name of the Naver credentials secret"
  value       = aws_secretsmanager_secret.secrets["naver-credentials"].name
}

output "sens_credentials_secret_arn" {
  description = "ARN of the SENS credentials secret"
  value       = aws_secretsmanager_secret.secrets["sens-credentials"].arn
}

output "sens_credentials_secret_name" {
  description = "Name of the SENS credentials secret"
  value       = aws_secretsmanager_secret.secrets["sens-credentials"].name
}

output "telegram_credentials_secret_arn" {
  description = "ARN of the Telegram credentials secret"
  value       = aws_secretsmanager_secret.secrets["telegram-credentials"].arn
}

output "telegram_credentials_secret_name" {
  description = "Name of the Telegram credentials secret"
  value       = aws_secretsmanager_secret.secrets["telegram-credentials"].name
}

output "all_secret_arns" {
  description = "Map of all secret ARNs"
  value = {
    naver_credentials    = aws_secretsmanager_secret.secrets["naver-credentials"].arn
    sens_credentials     = aws_secretsmanager_secret.secrets["sens-credentials"].arn
    telegram_credentials = aws_secretsmanager_secret.secrets["telegram-credentials"].arn
  }
}
