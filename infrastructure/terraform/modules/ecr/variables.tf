###############################################################################
# ECR Module Variables
###############################################################################

variable "repository_name" {
  description = "Name of the ECR repository"
  type        = string
  default     = "naver-sms-automation"
}

variable "aws_account_id" {
  description = "AWS account ID where the repository resides"
  type        = string
  validation {
    condition     = can(regex("^[0-9]{12}$", var.aws_account_id))
    error_message = "aws_account_id must be a 12-digit AWS account identifier."
  }
}

variable "image_tag_mutability" {
  description = "ECR image tag mutability setting"
  type        = string
  default     = "MUTABLE"
  validation {
    condition     = contains(["MUTABLE", "IMMUTABLE"], var.image_tag_mutability)
    error_message = "Must be MUTABLE or IMMUTABLE."
  }
}

variable "lifecycle_max_image_count" {
  description = "Maximum number of images to retain before expiration"
  type        = number
  default     = 5
  validation {
    condition     = var.lifecycle_max_image_count > 0
    error_message = "Must be greater than 0."
  }
}

variable "environment" {
  description = "Environment name (dev, staging, prod, sandbox)"
  type        = string
}

variable "scan_on_push" {
  description = "Enable image scanning on push"
  type        = bool
  default     = true
}

variable "lambda_role_arn" {
  description = "IAM role ARN for the Lambda function pulling images"
  type        = string
  validation {
    condition     = can(regex("^arn:aws:iam::[0-9]{12}:role/.+", var.lambda_role_arn))
    error_message = "lambda_role_arn must be a valid IAM role ARN."
  }
}

variable "deployment_role_arn" {
  description = "IAM role ARN allowed to push images to the repository"
  type        = string
  validation {
    condition     = can(regex("^arn:aws:iam::[0-9]{12}:role/.+", var.deployment_role_arn))
    error_message = "deployment_role_arn must be a valid IAM role ARN."
  }
}
