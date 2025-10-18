###############################################################################
# CloudWatch Log Group and Monitoring Infrastructure
# 
# Provisions:
# - CloudWatch Log Group for Lambda
# - Metric Filters for key events (SMS sent/failed, login failures, secrets errors)
# - CloudWatch Dashboard for observability
# - Alarms for error conditions
# - SNS topic for alarm notifications (placeholder)
###############################################################################

###############################################################################
# Variables
###############################################################################

variable "log_retention_days" {
  description = "CloudWatch log retention period in days."
  type        = number
  default     = 90
}

variable "lambda_role_arn" {
  description = "ARN of the Lambda execution role (from secrets-manager.tf)."
  type        = string
  default     = "arn:aws:iam::654654307503:role/naver-sms-automation-lambda-role"
}

variable "alarm_email" {
  description = "Email address to receive alarm notifications (optional)."
  type        = string
  default     = ""
}

###############################################################################
# CloudWatch Log Group
###############################################################################

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/naver-sms-automation"
  retention_in_days = var.log_retention_days
  kms_key_id        = null  # Use AWS-managed key for now

  tags = {
    Project   = "naver-sms-automation"
    ManagedBy = "terraform"
    Component = "logging"
  }
}

###############################################################################
# Metric Filters
###############################################################################

# SMS Sent Total
resource "aws_cloudwatch_log_metric_filter" "sms_sent_total" {
  name           = "sms_sent_total"
  log_group_name = aws_cloudwatch_log_group.lambda.name
  pattern        = "{ $.action_type = \"send_sms\" && $.status = \"success\" }"

  metric_transformation {
    name      = "SMSSentTotal"
    namespace = "NaverSMSAutomation"
    value     = "1"
    default_value = 0
  }

  depends_on = [aws_cloudwatch_log_group.lambda]
}

# SMS Failed Total
resource "aws_cloudwatch_log_metric_filter" "sms_failed_total" {
  name           = "sms_failed_total"
  log_group_name = aws_cloudwatch_log_group.lambda.name
  pattern        = "{ $.action_type = \"send_sms\" && $.status = \"failure\" }"

  metric_transformation {
    name      = "SMSFailedTotal"
    namespace = "NaverSMSAutomation"
    value     = "1"
    default_value = 0
  }

  depends_on = [aws_cloudwatch_log_group.lambda]
}

# Login Failure Total
resource "aws_cloudwatch_log_metric_filter" "login_failure_total" {
  name           = "login_failure_total"
  log_group_name = aws_cloudwatch_log_group.lambda.name
  pattern        = "{ $.action_type = \"login\" && $.status = \"failure\" }"

  metric_transformation {
    name      = "LoginFailureTotal"
    namespace = "NaverSMSAutomation"
    value     = "1"
    default_value = 0
  }

  depends_on = [aws_cloudwatch_log_group.lambda]
}

# Secrets Error Total
resource "aws_cloudwatch_log_metric_filter" "secrets_error_total" {
  name           = "secrets_error_total"
  log_group_name = aws_cloudwatch_log_group.lambda.name
  pattern        = "{ $.component = \"secrets\" && ($.status = \"failure\" || $.status = \"error\") }"

  metric_transformation {
    name      = "SecretsErrorTotal"
    namespace = "NaverSMSAutomation"
    value     = "1"
    default_value = 0
  }

  depends_on = [aws_cloudwatch_log_group.lambda]
}

###############################################################################
# SNS Topic for Alarm Notifications (placeholder)
###############################################################################

resource "aws_sns_topic" "alerts" {
  name              = "naver-sms-automation-alerts"
  kms_master_key_id = "alias/aws/sns"

  tags = {
    Project   = "naver-sms-automation"
    ManagedBy = "terraform"
    Component = "alerting"
  }
}

# SNS Topic Subscription (if email provided)
resource "aws_sns_topic_subscription" "alerts_email" {
  count             = var.alarm_email != "" ? 1 : 0
  topic_arn         = aws_sns_topic.alerts.arn
  protocol          = "email"
  endpoint          = var.alarm_email
  depends_on        = [aws_sns_topic.alerts]
}

###############################################################################
# CloudWatch Alarms
###############################################################################

# Lambda Invocation Errors
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "naver-sms-automation-lambda-errors"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300  # 5 minutes
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "Alert when Lambda invocation errors occur (threshold: ≥1 in 5 minutes)"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = "naver-sms-automation"
  }

  tags = {
    Project   = "naver-sms-automation"
    ManagedBy = "terraform"
    Component = "alerting"
    Severity  = "high"
  }
}

# Secrets Retrieval Failures
resource "aws_cloudwatch_metric_alarm" "secrets_errors" {
  alarm_name          = "naver-sms-automation-secrets-errors"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "SecretsErrorTotal"
  namespace           = "NaverSMSAutomation"
  period              = 900  # 15 minutes
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "Alert when secret retrieval fails (threshold: ≥1 in 15 minutes)"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"

  tags = {
    Project   = "naver-sms-automation"
    ManagedBy = "terraform"
    Component = "alerting"
    Severity  = "high"
  }
}

# Login Failures
resource "aws_cloudwatch_metric_alarm" "login_failures" {
  alarm_name          = "naver-sms-automation-login-failures"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "LoginFailureTotal"
  namespace           = "NaverSMSAutomation"
  period              = 1800  # 30 minutes
  statistic           = "Sum"
  threshold           = 3
  alarm_description   = "Alert when login failures exceed threshold (threshold: ≥3 in 30 minutes)"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"

  tags = {
    Project   = "naver-sms-automation"
    ManagedBy = "terraform"
    Component = "alerting"
    Severity  = "medium"
  }
}

###############################################################################
# CloudWatch Dashboard
###############################################################################

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "naver-sms-automation-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            ["NaverSMSAutomation", "SMSSentTotal", { stat = "Sum", label = "SMS Sent" }],
            [".", "SMSFailedTotal", { stat = "Sum", label = "SMS Failed" }]
          ]
          period = 300
          stat   = "Sum"
          region = "ap-northeast-2"
          title  = "SMS Delivery Volume (5-min)"
          yAxis = {
            left = {
              min = 0
            }
          }
        }
        width  = 12
        height = 6
        x      = 0
        y      = 0
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/Lambda", "Errors", { stat = "Sum", label = "Lambda Errors" }],
            ["NaverSMSAutomation", "LoginFailureTotal", { stat = "Sum", label = "Login Failures" }],
            [".", "SecretsErrorTotal", { stat = "Sum", label = "Secrets Errors" }]
          ]
          period = 300
          stat   = "Sum"
          region = "ap-northeast-2"
          title  = "Error Metrics (5-min)"
          yAxis = {
            left = {
              min = 0
            }
          }
        }
        width  = 12
        height = 6
        x      = 12
        y      = 0
      },
      {
        type = "log"
        properties = {
          query   = "fields @timestamp, level, message, status\n| filter ispresent(status)\n| stats count() by status"
          region  = "ap-northeast-2"
          title   = "Log Summary by Status (Last 1h)"
        }
        width  = 24
        height = 6
        x      = 0
        y      = 6
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/Lambda", "Duration", { stat = "p50", label = "Duration p50" }],
            [".", "Duration", { stat = "p95", label = "Duration p95" }]
          ]
          period = 300
          stat   = "Average"
          region = "ap-northeast-2"
          title  = "Lambda Duration Percentiles (5-min)"
          yAxis = {
            left = {
              min = 0
            }
          }
        }
        width  = 12
        height = 6
        x      = 0
        y      = 12
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/Lambda", "Invocations", { stat = "Sum", label = "Total Invocations" }],
            [".", "Throttles", { stat = "Sum", label = "Throttles" }]
          ]
          period = 300
          stat   = "Sum"
          region = "ap-northeast-2"
          title  = "Lambda Invocations & Throttles (5-min)"
          yAxis = {
            left = {
              min = 0
            }
          }
        }
        width  = 12
        height = 6
        x      = 12
        y      = 12
      }
    ]
  })

  depends_on = [
    aws_cloudwatch_log_metric_filter.sms_sent_total,
    aws_cloudwatch_log_metric_filter.sms_failed_total,
    aws_cloudwatch_log_metric_filter.login_failure_total,
    aws_cloudwatch_log_metric_filter.secrets_error_total
  ]
}

###############################################################################
# IAM Policy for Lambda CloudWatch Logs
###############################################################################

data "aws_iam_policy_document" "lambda_cloudwatch_logs" {
  statement {
    sid    = "AllowCloudWatchLogs"
    effect = "Allow"

    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:DescribeLogStreams"
    ]

    resources = [
      "${aws_cloudwatch_log_group.lambda.arn}:*"
    ]
  }
}

resource "aws_iam_policy" "lambda_cloudwatch_logs" {
  name        = "naver-sms-automation-lambda-cloudwatch-logs"
  description = "Policy to allow Lambda to write to CloudWatch Logs"
  policy      = data.aws_iam_policy_document.lambda_cloudwatch_logs.json

  tags = {
    Project   = "naver-sms-automation"
    ManagedBy = "terraform"
  }
}

# Note: Attach this policy to the Lambda execution role manually or via output reference
output "cloudwatch_logs_policy_arn" {
  description = "ARN of the IAM policy for Lambda CloudWatch Logs access"
  value       = aws_iam_policy.lambda_cloudwatch_logs.arn
}

###############################################################################
# Outputs
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
  value       = "https://console.aws.amazon.com/cloudwatch/home?region=ap-northeast-2#dashboards:name=${aws_cloudwatch_dashboard.main.dashboard_name}"
}

output "sns_topic_arn" {
  description = "ARN of the SNS topic for alarm notifications"
  value       = aws_sns_topic.alerts.arn
}

output "metric_filters" {
  description = "Names of the configured metric filters"
  value = {
    sms_sent_total        = aws_cloudwatch_log_metric_filter.sms_sent_total.name
    sms_failed_total      = aws_cloudwatch_log_metric_filter.sms_failed_total.name
    login_failure_total   = aws_cloudwatch_log_metric_filter.login_failure_total.name
    secrets_error_total   = aws_cloudwatch_log_metric_filter.secrets_error_total.name
  }
}
