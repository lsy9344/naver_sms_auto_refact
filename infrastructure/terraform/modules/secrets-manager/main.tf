###############################################################################
# Secrets Manager Module
#
# Provisions three AWS Secrets Manager secrets:
# - Naver login credentials
# - Naver Cloud SENS API credentials
# - Telegram bot credentials
#
# All secrets use sensitive() wrapper and are restricted to specific IAM roles.
###############################################################################

locals {
  namespace          = "naver-sms-automation"
  secret_prefix      = "${local.namespace}/${var.environment}"
  allowed_principals = distinct([var.lambda_role_arn, var.ci_deployment_role_arn])

  secrets = {
    "naver-credentials" = {
      description = "Naver login credentials (fields: username, password). Rotation: manual per SOP."
      values      = var.naver_credentials
    }
    "sens-credentials" = {
      description = "Naver Cloud SENS API credentials (fields: access_key, secret_key, service_id). Rotation: manual per SOP."
      values      = var.sens_credentials
    }
    "telegram-credentials" = {
      description = "Telegram bot credentials (fields: bot_token, chat_id). Rotation: manual per SOP."
      values      = var.telegram_credentials
    }
  }
}

###############################################################################
# Secrets Manager Secrets
###############################################################################

resource "aws_secretsmanager_secret" "secrets" {
  for_each = local.secrets

  name                    = "${local.secret_prefix}/${each.key}"
  description             = each.value.description
  recovery_window_in_days = var.secret_recovery_window_days

  tags = {
    Name        = each.key
    Environment = var.environment
    Type        = "credential"
  }
}

resource "aws_secretsmanager_secret_version" "secrets" {
  for_each = local.secrets

  secret_id     = aws_secretsmanager_secret.secrets[each.key].id
  secret_string = sensitive(jsonencode(each.value.values))
}

###############################################################################
# IAM Resource Policies for Secrets
#
# Grants Lambda read access, CI deployment role write access,
# and denies all others.
###############################################################################

data "aws_iam_policy_document" "secrets" {
  for_each = aws_secretsmanager_secret.secrets

  statement {
    sid    = "AllowLambdaAndDeploymentRead"
    effect = "Allow"

    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret"
    ]

    principals {
      type        = "AWS"
      identifiers = local.allowed_principals
    }

    resources = [each.value.arn]
  }

  statement {
    sid    = "AllowDeploymentWrite"
    effect = "Allow"

    actions = [
      "secretsmanager:PutSecretValue",
      "secretsmanager:UpdateSecret",
      "secretsmanager:TagResource",
      "secretsmanager:UntagResource"
    ]

    principals {
      type        = "AWS"
      identifiers = [var.ci_deployment_role_arn]
    }

    resources = [each.value.arn]
  }

  statement {
    sid    = "DenyAllOthers"
    effect = "Deny"

    not_principals {
      type        = "AWS"
      identifiers = local.allowed_principals
    }

    actions = [
      "secretsmanager:*"
    ]

    resources = [each.value.arn]
  }
}

resource "aws_secretsmanager_secret_policy" "secrets" {
  for_each = aws_secretsmanager_secret.secrets

  secret_arn = each.value.arn
  policy     = data.aws_iam_policy_document.secrets[each.key].json
}
