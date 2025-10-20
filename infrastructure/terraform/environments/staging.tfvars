###############################################################################
# Staging Environment Configuration
###############################################################################

# AWS Configuration
aws_region     = "ap-northeast-2"
aws_account_id = "654654307503"
environment    = "staging"

# ECR Configuration
ecr_repository_name           = "naver-sms-automation"
ecr_image_tag_mutability      = "MUTABLE"
ecr_lifecycle_max_image_count = 10 # Keep more images in staging

# CloudWatch Configuration
log_retention_days               = 60 # Medium retention for staging
alarm_email                      = "" # Set to email if needed
error_alarm_threshold            = 1
login_failure_alarm_threshold    = 3
lambda_function_name             = "naver-sms-automation-staging"
cloudwatch_namespace             = "NaverSMSAutomationStaging"
comparison_namespace             = "naver-sms/comparison"
comparison_metrics_enabled       = true
discrepancy_alarm_threshold      = 0
match_percentage_alarm_threshold = 100
slack_webhook_url                = "" # Provide staging Slack webhook URL when available
telegram_webhook_url             = "" # Provide staging Telegram webhook URL when available

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
