###############################################################################
# Production Environment Configuration
###############################################################################

# AWS Configuration
aws_region     = "ap-northeast-2"
aws_account_id = "654654307503"
environment    = "prod"

# ECR Configuration
ecr_repository_name           = "naver-sms-automation"
ecr_image_tag_mutability      = "IMMUTABLE" # Immutable tags in production
ecr_lifecycle_max_image_count = 20          # Keep more images for rollback capability

# CloudWatch Configuration
log_retention_days               = 90 # Longer retention for production
alarm_email                      = "" # MUST set to email for production alerts
error_alarm_threshold            = 1  # Strict threshold for production
login_failure_alarm_threshold    = 3
lambda_function_name             = "naver-sms-automation-prod"
cloudwatch_namespace             = "NaverSMSAutomationProd"
comparison_namespace             = "naver-sms/comparison"
comparison_metrics_enabled       = true
discrepancy_alarm_threshold      = 0
match_percentage_alarm_threshold = 100
slack_webhook_url                = "" # Populate with production Slack webhook prior to deployment
telegram_webhook_url             = "" # Populate with production Telegram webhook prior to deployment

# IAM Role ARNs
lambda_role_arn        = "arn:aws:iam::654654307503:role/naver-sms-automation-lambda-role"
ci_deployment_role_arn = "arn:aws:iam::654654307503:role/naver-sms-automation-ci-role"

# Secrets - DO NOT COMMIT REAL VALUES
# Use environment variables: TF_VAR_naver_credentials, TF_VAR_sens_credentials, TF_VAR_telegram_credentials
naver_credentials = {
  username = "CHANGE_ME"
  password = "CHANGE_ME"
}

sens_credentials = {
  access_key = "CHANGE_ME"
  secret_key = "CHANGE_ME"
  service_id = "CHANGE_ME"
}

telegram_credentials = {
  bot_token = "CHANGE_ME"
  chat_id   = "CHANGE_ME"
}
