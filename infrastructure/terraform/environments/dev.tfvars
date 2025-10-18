###############################################################################
# Development Environment Configuration
###############################################################################

# AWS Configuration
aws_region     = "ap-northeast-2"
aws_account_id = "654654307503"
environment    = "dev"

# ECR Configuration
ecr_repository_name           = "naver-sms-automation"
ecr_image_tag_mutability      = "MUTABLE"
ecr_lifecycle_max_image_count = 5

# CloudWatch Configuration
log_retention_days                = 30 # Shorter retention for dev
alarm_email                       = "" # Set to email if needed
error_alarm_threshold             = 2  # More lenient threshold for dev
login_failure_alarm_threshold     = 5
lambda_function_name              = "naver-sms-automation-dev"
cloudwatch_namespace              = "NaverSMSAutomationDev"

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
