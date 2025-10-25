###############################################################################
# Sandbox Environment Configuration (for testing IaC deployments)
###############################################################################

# AWS Configuration
aws_region     = "ap-northeast-2"
aws_account_id = "654654307503"
environment    = "sandbox"

# ECR Configuration
ecr_repository_name           = "naver-sms-automation-sandbox"
ecr_image_tag_mutability      = "MUTABLE"
ecr_lifecycle_max_image_count = 3 # Minimal retention for sandbox

# CloudWatch Configuration
log_retention_days               = 7  # Minimal retention for sandbox
alarm_email                      = "" # Optional for sandbox
error_alarm_threshold            = 5  # Lenient for testing
login_failure_alarm_threshold    = 10
lambda_function_name             = "naverplace_send_inform_v2"
cloudwatch_namespace             = "NaverSMSAutomationSandbox"
comparison_namespace             = "naver-sms/comparison"
comparison_metrics_enabled       = true
discrepancy_alarm_threshold      = 0
match_percentage_alarm_threshold = 100
slack_webhook_url                = "" # Optional: webhook for sandbox alarm testing
telegram_webhook_url             = "" # Optional: webhook for sandbox alarm testing

# IAM Role ARNs
lambda_role_arn        = "arn:aws:iam::654654307503:role/naver-sms-automation-lambda-role"
ci_deployment_role_arn = "arn:aws:iam::654654307503:role/naver-sms-automation-ci-role"

# Secrets - Test placeholders only
naver_credentials = {
  username = "sandbox_user"
  password = "sandbox_pass"
}

sens_credentials = {
  access_key = "sandbox_key"
  secret_key = "sandbox_secret"
  service_id = "sandbox_id"
}

telegram_credentials = {
  bot_token = "sandbox_token"
  chat_id   = "sandbox_chat"
}
