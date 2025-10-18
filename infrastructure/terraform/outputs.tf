###############################################################################
# IaC Outputs for Downstream Consumption
#
# These outputs are exported for use in Story 2.1+ and other downstream
# infrastructure configuration. Export outputs to docs/qa/infra-validation-1.5.md
# after successful sandbox deployment.
###############################################################################

###############################################################################
# ECR Outputs
###############################################################################

output "ecr_repository_uri" {
  description = "URI of the ECR repository"
  value       = module.ecr.repository_uri
}

output "ecr_registry_id" {
  description = "AWS account ID owning the ECR repository"
  value       = module.ecr.registry_id
}

output "ecr_repository_arn" {
  description = "ARN of the ECR repository"
  value       = module.ecr.repository_arn
}

###############################################################################
# Secrets Manager Outputs
###############################################################################

output "naver_credentials_secret_arn" {
  description = "ARN of the Naver credentials secret"
  value       = module.secrets_manager.naver_credentials_secret_arn
}

output "naver_credentials_secret_name" {
  description = "Name of the Naver credentials secret"
  value       = module.secrets_manager.naver_credentials_secret_name
}

output "sens_credentials_secret_arn" {
  description = "ARN of the SENS credentials secret"
  value       = module.secrets_manager.sens_credentials_secret_arn
}

output "sens_credentials_secret_name" {
  description = "Name of the SENS credentials secret"
  value       = module.secrets_manager.sens_credentials_secret_name
}

output "telegram_credentials_secret_arn" {
  description = "ARN of the Telegram credentials secret"
  value       = module.secrets_manager.telegram_credentials_secret_arn
}

output "telegram_credentials_secret_name" {
  description = "Name of the Telegram credentials secret"
  value       = module.secrets_manager.telegram_credentials_secret_name
}

###############################################################################
# CloudWatch Outputs
###############################################################################

output "cloudwatch_log_group_name" {
  description = "Name of the CloudWatch log group"
  value       = module.cloudwatch.log_group_name
}

output "cloudwatch_log_group_arn" {
  description = "ARN of the CloudWatch log group"
  value       = module.cloudwatch.log_group_arn
}

output "cloudwatch_dashboard_url" {
  description = "URL to access the CloudWatch dashboard"
  value       = module.cloudwatch.dashboard_url
}

output "cloudwatch_sns_topic_arn" {
  description = "ARN of the SNS topic for alarm notifications"
  value       = module.cloudwatch.sns_topic_arn
}

output "cloudwatch_metric_filters" {
  description = "Names of configured metric filters"
  value       = module.cloudwatch.metric_filters
}

###############################################################################
# Summary Output for Documentation
###############################################################################

output "infrastructure_summary" {
  description = "Summary of all infrastructure resources for documentation"
  value = {
    environment              = var.environment
    ecr_repository_uri       = module.ecr.repository_uri
    cloudwatch_log_group     = module.cloudwatch.log_group_name
    cloudwatch_dashboard_url = module.cloudwatch.dashboard_url
    secrets = {
      naver_credentials_name    = module.secrets_manager.naver_credentials_secret_name
      sens_credentials_name     = module.secrets_manager.sens_credentials_secret_name
      telegram_credentials_name = module.secrets_manager.telegram_credentials_secret_name
    }
  }
}
