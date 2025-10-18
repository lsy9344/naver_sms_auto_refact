terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

###############################################################################
# Provider configuration
###############################################################################

variable "aws_region" {
  description = "AWS region where secrets will be provisioned."
  type        = string
  default     = "ap-northeast-2"
}

provider "aws" {
  region = var.aws_region
}

###############################################################################
# IAM role configuration
###############################################################################

variable "lambda_role_arn" {
  description = "ARN of the Lambda execution role that is allowed to read secrets."
  type        = string
  default     = "arn:aws:iam::654654307503:role/naver-sms-automation-lambda-role"
}

variable "ci_deployment_role_arn" {
  description = "ARN of the CI deployment role that manages secret values."
  type        = string
  default     = "arn:aws:iam::654654307503:role/naver-sms-automation-ci-role"
}

locals {
  namespace          = "naver-sms-automation"
  allowed_principals = distinct([var.lambda_role_arn, var.ci_deployment_role_arn])
}

###############################################################################
# Secret value placeholders
###############################################################################

variable "naver_credentials" {
  description = "Placeholder values for Naver credentials."
  type = object({
    username = string
    password = string
  })
  default = {
    username = "CHANGE_ME"
    password = "CHANGE_ME"
  }
}

variable "sens_credentials" {
  description = "Placeholder values for Naver Cloud SENS credentials."
  type = object({
    access_key = string
    secret_key = string
    service_id = string
  })
  default = {
    access_key = "CHANGE_ME"
    secret_key = "CHANGE_ME"
    service_id = "CHANGE_ME"
  }
}

variable "telegram_credentials" {
  description = "Placeholder values for Telegram bot credentials."
  type = object({
    bot_token = string
    chat_id   = string
  })
  default = {
    bot_token = "CHANGE_ME"
    chat_id   = "CHANGE_ME"
  }
}

locals {
  secrets = {
    "naver-credentials" = {
      description = "Contains Naver login credentials (fields: username, password). Rotation: manual per SOP until Epic 5."
      values      = {
        username = var.naver_credentials.username
        password = var.naver_credentials.password
      }
    }
    "sens-credentials" = {
      description = "Contains SENS API credentials (fields: access_key, secret_key, service_id). Rotation: manual per SOP until Epic 5."
      values      = {
        access_key = var.sens_credentials.access_key
        secret_key = var.sens_credentials.secret_key
        service_id = var.sens_credentials.service_id
      }
    }
    "telegram-credentials" = {
      description = "Contains Telegram bot credentials (fields: bot_token, chat_id). Rotation: manual per SOP until Epic 5."
      values      = {
        bot_token = var.telegram_credentials.bot_token
        chat_id   = var.telegram_credentials.chat_id
      }
    }
  }
}

###############################################################################
# Secret definitions
###############################################################################

resource "aws_secretsmanager_secret" "secrets" {
  for_each = local.secrets

  name        = "${local.namespace}/${each.key}"
  description = each.value.description

  recovery_window_in_days = 7
  tags = {
    Project   = "naver-sms-automation"
    ManagedBy = "terraform"
    Type      = "credential"
  }
}

resource "aws_secretsmanager_secret_version" "secrets" {
  for_each = local.secrets

  secret_id     = aws_secretsmanager_secret.secrets[each.key].id
  secret_string = jsonencode(each.value.values)
}

###############################################################################
# IAM resource policies
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
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
      "secretsmanager:PutSecretValue",
      "secretsmanager:UpdateSecret",
      "secretsmanager:DeleteSecret",
      "secretsmanager:TagResource",
      "secretsmanager:UntagResource"
    ]

    resources = [each.value.arn]
  }
}

resource "aws_secretsmanager_secret_policy" "secrets" {
  for_each = aws_secretsmanager_secret.secrets

  secret_arn = each.value.arn
  policy     = data.aws_iam_policy_document.secrets[each.key].json
}
