###############################################################################
# Root Terraform Module - Main Resource Instantiation
#
# This module instantiates three infrastructure modules:
# - ECR repository for container images
# - Secrets Manager for credentials
# - CloudWatch for logging and monitoring
###############################################################################

module "ecr" {
  source = "./modules/ecr"

  repository_name           = var.ecr_repository_name
  image_tag_mutability      = var.ecr_image_tag_mutability
  lifecycle_max_image_count = var.ecr_lifecycle_max_image_count
  environment               = var.environment
  aws_account_id            = var.aws_account_id
  lambda_role_arn           = var.lambda_role_arn
  deployment_role_arn       = var.ci_deployment_role_arn
}

module "secrets_manager" {
  source = "./modules/secrets-manager"

  naver_credentials      = var.naver_credentials
  sens_credentials       = var.sens_credentials
  telegram_credentials   = var.telegram_credentials
  lambda_role_arn        = var.lambda_role_arn
  ci_deployment_role_arn = var.ci_deployment_role_arn
  environment            = var.environment
}

module "cloudwatch" {
  source = "./modules/cloudwatch"

  log_retention_days               = var.log_retention_days
  alarm_email                      = var.alarm_email
  lambda_role_arn                  = var.lambda_role_arn
  environment                      = var.environment
  error_alarm_threshold            = var.error_alarm_threshold
  login_failure_alarm_threshold    = var.login_failure_alarm_threshold
  aws_region                       = var.aws_region
  lambda_function_name             = var.lambda_function_name
  cloudwatch_namespace             = var.cloudwatch_namespace
  comparison_namespace             = var.comparison_namespace
  comparison_metrics_enabled       = var.comparison_metrics_enabled
  discrepancy_alarm_threshold      = var.discrepancy_alarm_threshold
  match_percentage_alarm_threshold = var.match_percentage_alarm_threshold
  slack_webhook_url                = var.slack_webhook_url
  telegram_webhook_url             = var.telegram_webhook_url
}
