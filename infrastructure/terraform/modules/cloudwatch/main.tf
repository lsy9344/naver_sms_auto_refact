###############################################################################
# CloudWatch Logging and Monitoring Module
#
# Provisions:
# - CloudWatch Log Group for Lambda logs
# - Metric Filters for key operational events
# - CloudWatch Dashboard for observability
# - CloudWatch Alarms for error conditions
# - SNS Topic for alarm notifications
###############################################################################

###############################################################################
# CloudWatch Log Group
###############################################################################

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.lambda_function_name}"
  retention_in_days = var.log_retention_days
  kms_key_id        = null # Use AWS-managed encryption

  tags = {
    Name        = "${var.lambda_function_name}-logs"
    Environment = var.environment
    Component   = "logging"
  }
}

###############################################################################
# Metric Filters
###############################################################################

# SMS Sent Total
resource "aws_cloudwatch_log_metric_filter" "sms_sent_total" {
  name           = "${var.lambda_function_name}-sms-sent-total"
  log_group_name = aws_cloudwatch_log_group.lambda.name
  pattern        = "{ $.action_type = \"send_sms\" && $.status = \"success\" }"

  metric_transformation {
    name          = "SMSSentTotal"
    namespace     = var.cloudwatch_namespace
    value         = "1"
    default_value = 0
  }

  depends_on = [aws_cloudwatch_log_group.lambda]
}

# SMS Failed Total
resource "aws_cloudwatch_log_metric_filter" "sms_failed_total" {
  name           = "${var.lambda_function_name}-sms-failed-total"
  log_group_name = aws_cloudwatch_log_group.lambda.name
  pattern        = "{ $.action_type = \"send_sms\" && $.status = \"failure\" }"

  metric_transformation {
    name          = "SMSFailedTotal"
    namespace     = var.cloudwatch_namespace
    value         = "1"
    default_value = 0
  }

  depends_on = [aws_cloudwatch_log_group.lambda]
}

# Login Failure Total
resource "aws_cloudwatch_log_metric_filter" "login_failure_total" {
  name           = "${var.lambda_function_name}-login-failure-total"
  log_group_name = aws_cloudwatch_log_group.lambda.name
  pattern        = "{ $.action_type = \"login\" && $.status = \"failure\" }"

  metric_transformation {
    name          = "LoginFailureTotal"
    namespace     = var.cloudwatch_namespace
    value         = "1"
    default_value = 0
  }

  depends_on = [aws_cloudwatch_log_group.lambda]
}

# Secrets Error Total
resource "aws_cloudwatch_log_metric_filter" "secrets_error_total" {
  name           = "${var.lambda_function_name}-secrets-error-total"
  log_group_name = aws_cloudwatch_log_group.lambda.name
  pattern        = "{ $.component = \"secrets\" && ($.status = \"failure\" || $.status = \"error\") }"

  metric_transformation {
    name          = "SecretsErrorTotal"
    namespace     = var.cloudwatch_namespace
    value         = "1"
    default_value = 0
  }

  depends_on = [aws_cloudwatch_log_group.lambda]
}

###############################################################################
# SNS Topic for Alarm Notifications
###############################################################################

resource "aws_sns_topic" "alerts" {
  name              = "${var.lambda_function_name}-alerts"
  kms_master_key_id = "alias/aws/sns"

  tags = {
    Name        = "${var.lambda_function_name}-alerts"
    Environment = var.environment
    Component   = "alerting"
  }
}

# SNS Topic Subscription (if email provided)
resource "aws_sns_topic_subscription" "alerts_email" {
  count     = var.alarm_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alarm_email

  depends_on = [aws_sns_topic.alerts]
}

###############################################################################
# CloudWatch Alarms
###############################################################################

# Lambda Invocation Errors
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${var.lambda_function_name}-lambda-errors"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300 # 5 minutes
  statistic           = "Sum"
  threshold           = var.error_alarm_threshold
  alarm_description   = "Alert when Lambda invocation errors occur (threshold: >=${var.error_alarm_threshold} in 5 minutes)"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = var.lambda_function_name
  }

  tags = {
    Name        = "${var.lambda_function_name}-lambda-errors"
    Environment = var.environment
    Component   = "alerting"
    Severity    = "high"
  }
}

# Secrets Retrieval Failures
resource "aws_cloudwatch_metric_alarm" "secrets_errors" {
  alarm_name          = "${var.lambda_function_name}-secrets-errors"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "SecretsErrorTotal"
  namespace           = var.cloudwatch_namespace
  period              = 900 # 15 minutes
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "Alert when secret retrieval fails (threshold: >=1 in 15 minutes)"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"

  tags = {
    Name        = "${var.lambda_function_name}-secrets-errors"
    Environment = var.environment
    Component   = "alerting"
    Severity    = "high"
  }
}

# Login Failures
resource "aws_cloudwatch_metric_alarm" "login_failures" {
  alarm_name          = "${var.lambda_function_name}-login-failures"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "LoginFailureTotal"
  namespace           = var.cloudwatch_namespace
  period              = 1800 # 30 minutes
  statistic           = "Sum"
  threshold           = var.login_failure_alarm_threshold
  alarm_description   = "Alert when login failures exceed threshold (threshold: >=${var.login_failure_alarm_threshold} in 30 minutes)"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"

  tags = {
    Name        = "${var.lambda_function_name}-login-failures"
    Environment = var.environment
    Component   = "alerting"
    Severity    = "medium"
  }
}

###############################################################################
# CloudWatch Dashboard
###############################################################################

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.lambda_function_name}-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            [var.cloudwatch_namespace, "SMSSentTotal", { stat = "Sum", label = "SMS Sent" }],
            [".", "SMSFailedTotal", { stat = "Sum", label = "SMS Failed" }]
          ]
          period = 300
          stat   = "Sum"
          region = var.aws_region
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
            ["AWS/Lambda", "Errors", { stat = "Sum", label = "Lambda Errors", dimensions = { FunctionName = var.lambda_function_name } }],
            [var.cloudwatch_namespace, "LoginFailureTotal", { stat = "Sum", label = "Login Failures" }],
            [".", "SecretsErrorTotal", { stat = "Sum", label = "Secrets Errors" }]
          ]
          period = 300
          stat   = "Sum"
          region = var.aws_region
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
          query  = "SOURCE '${aws_cloudwatch_log_group.lambda.name}'\n| fields @timestamp, level, message, status\n| filter ispresent(status)\n| stats count() by status"
          region = var.aws_region
          title  = "Log Summary by Status (Last 1h)"
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
            ["AWS/Lambda", "Duration", { stat = "p50", label = "Duration p50", dimensions = { FunctionName = var.lambda_function_name } }],
            [".", "Duration", { stat = "p95", label = "Duration p95", dimensions = { FunctionName = var.lambda_function_name } }]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
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
            ["AWS/Lambda", "Invocations", { stat = "Sum", label = "Total Invocations", dimensions = { FunctionName = var.lambda_function_name } }],
            [".", "Throttles", { stat = "Sum", label = "Throttles", dimensions = { FunctionName = var.lambda_function_name } }]
          ]
          period = 300
          stat   = "Sum"
          region = var.aws_region
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
  name        = "${var.lambda_function_name}-cloudwatch-logs"
  description = "Policy to allow Lambda to write to CloudWatch Logs"
  policy      = data.aws_iam_policy_document.lambda_cloudwatch_logs.json

  tags = {
    Name        = "${var.lambda_function_name}-cloudwatch-logs"
    Environment = var.environment
  }
}
