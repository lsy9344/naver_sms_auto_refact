###############################################################################
# CloudWatch Module Outputs
###############################################################################

output "log_group_name" {
  description = "Name of the CloudWatch log group"
  value       = aws_cloudwatch_log_group.lambda.name
}

output "log_group_arn" {
  description = "ARN of the CloudWatch log group"
  value       = aws_cloudwatch_log_group.lambda.arn
}

output "dashboard_url" {
  description = "URL to access the CloudWatch dashboard"
  value       = "https://console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.main.dashboard_name}"
}

output "dashboard_name" {
  description = "Name of the CloudWatch dashboard"
  value       = aws_cloudwatch_dashboard.main.dashboard_name
}

output "sns_topic_arn" {
  description = "ARN of the SNS topic for alarm notifications"
  value       = aws_sns_topic.alerts.arn
}

output "metric_filters" {
  description = "Names of configured metric filters"
  value = {
    sms_sent_total      = aws_cloudwatch_log_metric_filter.sms_sent_total.name
    sms_failed_total    = aws_cloudwatch_log_metric_filter.sms_failed_total.name
    login_failure_total = aws_cloudwatch_log_metric_filter.login_failure_total.name
    secrets_error_total = aws_cloudwatch_log_metric_filter.secrets_error_total.name
  }
}

output "alarm_arns" {
  description = "ARNs of CloudWatch alarms"
  value = {
    lambda_errors  = aws_cloudwatch_metric_alarm.lambda_errors.arn
    secrets_errors = aws_cloudwatch_metric_alarm.secrets_errors.arn
    login_failures = aws_cloudwatch_metric_alarm.login_failures.arn
  }
}

output "cloudwatch_logs_policy_arn" {
  description = "ARN of the IAM policy for Lambda CloudWatch Logs access"
  value       = aws_iam_policy.lambda_cloudwatch_logs.arn
}

# Story 5.4: Comparison monitoring outputs
output "comparison_namespace" {
  description = "CloudWatch namespace for comparison metrics (Story 5.4)"
  value       = var.comparison_namespace
}
