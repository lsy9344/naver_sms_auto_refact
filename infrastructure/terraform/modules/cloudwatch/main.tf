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
# Story 5.4: Comparison Monitoring Metric Filters
###############################################################################

# Comparison Summary Events
resource "aws_cloudwatch_log_metric_filter" "comparison_summary" {
  count          = var.comparison_metrics_enabled ? 1 : 0
  name           = "${var.lambda_function_name}-comparison-summary"
  log_group_name = aws_cloudwatch_log_group.lambda.name
  pattern        = "{ $.event_type = \"comparison_summary\" }"

  metric_transformation {
    name          = "ComparisonRun"
    namespace     = var.comparison_namespace
    value         = "1"
    default_value = 0
  }

  depends_on = [aws_cloudwatch_log_group.lambda]
}

# SMS Comparison Mismatches
resource "aws_cloudwatch_log_metric_filter" "sms_comparison_mismatch" {
  count          = var.comparison_metrics_enabled ? 1 : 0
  name           = "${var.lambda_function_name}-sms-comparison-mismatch"
  log_group_name = aws_cloudwatch_log_group.lambda.name
  pattern        = "{ $.event_type = \"sms_comparison\" && $.match = false }"

  metric_transformation {
    name          = "SMSMismatchCount"
    namespace     = var.comparison_namespace
    value         = "1"
    default_value = 0
  }

  depends_on = [aws_cloudwatch_log_group.lambda]
}

# DynamoDB Operation Comparison Mismatches
resource "aws_cloudwatch_log_metric_filter" "db_comparison_mismatch" {
  count          = var.comparison_metrics_enabled ? 1 : 0
  name           = "${var.lambda_function_name}-db-comparison-mismatch"
  log_group_name = aws_cloudwatch_log_group.lambda.name
  pattern        = "{ $.event_type = \"db_operation_comparison\" && $.match = false }"

  metric_transformation {
    name          = "DBMismatchCount"
    namespace     = var.comparison_namespace
    value         = "1"
    default_value = 0
  }

  depends_on = [aws_cloudwatch_log_group.lambda]
}

# Telegram Event Comparison Mismatches
resource "aws_cloudwatch_log_metric_filter" "telegram_comparison_mismatch" {
  count          = var.comparison_metrics_enabled ? 1 : 0
  name           = "${var.lambda_function_name}-telegram-comparison-mismatch"
  log_group_name = aws_cloudwatch_log_group.lambda.name
  pattern        = "{ $.event_type = \"telegram_comparison\" && $.match = false }"

  metric_transformation {
    name          = "TelegramMismatchCount"
    namespace     = var.comparison_namespace
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

# SNS Topic Subscription (Slack via HTTP endpoint)
# Note: Configure Slack webhook URL in terraform.tfvars or environment variable TF_VAR_slack_webhook_url
resource "aws_sns_topic_subscription" "alerts_slack" {
  count             = var.slack_webhook_url != "" ? 1 : 0
  topic_arn         = aws_sns_topic.alerts.arn
  protocol          = "https"
  endpoint          = var.slack_webhook_url
  endpoint_auto_confirms = true

  depends_on = [aws_sns_topic.alerts]
}

# SNS Topic Subscription (Telegram via HTTP endpoint)
# Note: Configure Telegram bot webhook URL in terraform.tfvars or environment variable TF_VAR_telegram_webhook_url
resource "aws_sns_topic_subscription" "alerts_telegram" {
  count             = var.telegram_webhook_url != "" ? 1 : 0
  topic_arn         = aws_sns_topic.alerts.arn
  protocol          = "https"
  endpoint          = var.telegram_webhook_url
  endpoint_auto_confirms = true

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

# Story 5.4: Comparison - Discrepancies Detected
resource "aws_cloudwatch_metric_alarm" "comparison_discrepancies" {
  count               = var.comparison_metrics_enabled ? 1 : 0
  alarm_name          = "${var.lambda_function_name}-comparison-discrepancies"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "SMSMismatchCount"
  namespace           = var.comparison_namespace
  period              = 300  # 5 minutes
  statistic           = "Sum"
  threshold           = var.discrepancy_alarm_threshold
  alarm_description   = "Alert when discrepancies detected during SMS comparison (Story 5.4)"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"

  tags = {
    Name        = "${var.lambda_function_name}-comparison-discrepancies"
    Environment = var.environment
    Component   = "alerting"
    Story       = "5.4"
    Severity    = "high"
  }
}

# Story 5.4: Comparison - Database Operation Mismatches
resource "aws_cloudwatch_metric_alarm" "comparison_db_mismatches" {
  count               = var.comparison_metrics_enabled ? 1 : 0
  alarm_name          = "${var.lambda_function_name}-comparison-db-mismatches"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "DBMismatchCount"
  namespace           = var.comparison_namespace
  period              = 300  # 5 minutes
  statistic           = "Sum"
  threshold           = var.discrepancy_alarm_threshold
  alarm_description   = "Alert when DynamoDB operation mismatches detected (Story 5.4)"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"

  tags = {
    Name        = "${var.lambda_function_name}-comparison-db-mismatches"
    Environment = var.environment
    Component   = "alerting"
    Story       = "5.4"
    Severity    = "high"
  }
}

# Story 5.4: Comparison - Telegram Event Mismatches
resource "aws_cloudwatch_metric_alarm" "comparison_telegram_mismatches" {
  count               = var.comparison_metrics_enabled ? 1 : 0
  alarm_name          = "${var.lambda_function_name}-comparison-telegram-mismatches"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "TelegramMismatchCount"
  namespace           = var.comparison_namespace
  period              = 300  # 5 minutes
  statistic           = "Sum"
  threshold           = var.discrepancy_alarm_threshold
  alarm_description   = "Alert when Telegram event mismatches detected (Story 5.4)"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"

  tags = {
    Name        = "${var.lambda_function_name}-comparison-telegram-mismatches"
    Environment = var.environment
    Component   = "alerting"
    Story       = "5.4"
    Severity    = "medium"
  }
}

# Story 5.4: Comparison - Match Percentage Below Threshold
resource "aws_cloudwatch_metric_alarm" "comparison_match_percentage" {
  count               = var.comparison_metrics_enabled ? 1 : 0
  alarm_name          = "${var.lambda_function_name}-comparison-match-percentage"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "ComparisonMatchPercentage"
  namespace           = var.comparison_namespace
  period              = 300  # 5 minutes
  statistic           = "Average"
  threshold           = var.match_percentage_alarm_threshold
  alarm_description   = "Alert when match percentage drops below threshold (Story 5.4)"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"

  tags = {
    Name        = "${var.lambda_function_name}-comparison-match-percentage"
    Environment = var.environment
    Component   = "alerting"
    Story       = "5.4"
    Severity    = "high"
  }
}

# Story 5.4: Comparison - Any Discrepancies Detected
resource "aws_cloudwatch_metric_alarm" "comparison_any_discrepancies" {
  count               = var.comparison_metrics_enabled ? 1 : 0
  alarm_name          = "${var.lambda_function_name}-comparison-any-discrepancies"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "DiscrepanciesDetected"
  namespace           = var.comparison_namespace
  period              = 300  # 5 minutes
  statistic           = "Maximum"
  threshold           = 0
  alarm_description   = "Alert when any comparison discrepancies detected (Story 5.4)"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"

  tags = {
    Name        = "${var.lambda_function_name}-comparison-any-discrepancies"
    Environment = var.environment
    Component   = "alerting"
    Story       = "5.4"
    Severity    = "high"
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
            [var.cloudwatch_namespace, "SMSSentTotal"],
            [".", "SMSFailedTotal"]
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
            ["AWS/Lambda", "Errors", "FunctionName", var.lambda_function_name],
            [var.cloudwatch_namespace, "LoginFailureTotal"],
            [".", "SecretsErrorTotal"]
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
            ["AWS/Lambda", "Duration", "FunctionName", var.lambda_function_name, { stat = "p50" }],
            [".", "Duration", "FunctionName", var.lambda_function_name, { stat = "p95" }]
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
            ["AWS/Lambda", "Invocations", "FunctionName", var.lambda_function_name],
            [".", "Throttles", "FunctionName", var.lambda_function_name]
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
      },
      # Story 5.4: Comparison Monitoring Widgets
      # Row 3: Comparison Results Overview
      {
        type = "metric"
        properties = {
          metrics = [
            [var.comparison_namespace, "ComparisonRun", { stat = "Sum" }],
            [".", "SMSMismatchCount", { stat = "Sum" }],
            [".", "DBMismatchCount", { stat = "Sum" }],
            [".", "TelegramMismatchCount", { stat = "Sum" }]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "Comparison: Run Count & Discrepancies (5-min)"
          yAxis = {
            left = {
              min = 0
            }
          }
        }
        width  = 12
        height = 6
        x      = 0
        y      = 18
      },
      {
        type = "log"
        properties = {
          query  = "SOURCE '${aws_cloudwatch_log_group.lambda.name}'\n| filter event_type = 'comparison_summary'\n| fields @timestamp, sms_sent_old, sms_sent_new, match_percentage\n| stats avg(match_percentage) as avg_match, max(match_percentage) as max_match, min(match_percentage) as min_match"
          region = var.aws_region
          title  = "Comparison: Match Percentage Stats (Last 1h)"
        }
        width  = 12
        height = 6
        x      = 12
        y      = 18
      },
      # Row 4: Detailed Comparison Analysis
      {
        type = "log"
        properties = {
          query  = "SOURCE '${aws_cloudwatch_log_group.lambda.name}'\n| filter event_type like /comparison_/\n| stats count() as total_events, sum(case when match = false then 1 else 0 end) as mismatches by event_type\n| fields event_type, total_events, mismatches"
          region = var.aws_region
          title  = "Comparison: Event-Type Breakdown (Last 1h)"
        }
        width  = 12
        height = 6
        x      = 0
        y      = 24
      },
      {
        type = "log"
        properties = {
          query  = "SOURCE '${aws_cloudwatch_log_group.lambda.name}'\n| filter event_type = 'sms_comparison' && match = false\n| fields @timestamp, booking_id, phone_masked, sample_diffs\n| sort @timestamp desc\n| limit 100"
          region = var.aws_region
          title  = "Comparison: Recent SMS Mismatches (Last 1h)"
        }
        width  = 12
        height = 6
        x      = 12
        y      = 24
      }
    ]
  })

  depends_on = [
    aws_cloudwatch_log_metric_filter.sms_sent_total,
    aws_cloudwatch_log_metric_filter.sms_failed_total,
    aws_cloudwatch_log_metric_filter.login_failure_total,
    aws_cloudwatch_log_metric_filter.secrets_error_total,
    aws_cloudwatch_log_metric_filter.comparison_summary
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
