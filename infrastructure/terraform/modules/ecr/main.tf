###############################################################################
# ECR Repository Module
#
# Provisions an AWS ECR repository with:
# - Image tag mutability setting
# - Lifecycle policy to manage image retention
# - Image scanning on push
# - Encryption using AWS managed keys
###############################################################################

###############################################################################
# ECR Repository
###############################################################################

resource "aws_ecr_repository" "main" {
  name                 = var.repository_name
  image_tag_mutability = var.image_tag_mutability

  image_scanning_configuration {
    scan_on_push = var.scan_on_push
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name        = var.repository_name
    Environment = var.environment
  }
}

###############################################################################
# ECR Lifecycle Policy
#
# Retains only the most recent images based on count.
# Expires older images to manage costs and storage.
###############################################################################

resource "aws_ecr_lifecycle_policy" "main" {
  repository = aws_ecr_repository.main.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep only latest ${var.lifecycle_max_image_count} images"
        selection = {
          tagStatus     = "any"
          countType     = "imageCountMoreThan"
          countNumber   = var.lifecycle_max_image_count
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

###############################################################################
# ECR Repository Policy
#
# Allows Lambda execution role to pull images.
# Restricts push access to CI/deployment roles only.
###############################################################################

data "aws_iam_policy_document" "ecr_policy" {
  statement {
    sid    = "AllowLambdaPull"
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = [var.lambda_role_arn]
    }

    actions = [
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
      "ecr:BatchCheckLayerAvailability"
    ]
  }

  statement {
    sid    = "AllowDeploymentPush"
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = [var.deployment_role_arn]
    }

    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:CompleteLayerUpload",
      "ecr:GetDownloadUrlForLayer",
      "ecr:GetRepositoryPolicy",
      "ecr:InitiateLayerUpload",
      "ecr:ListImages",
      "ecr:PutImage",
      "ecr:UploadLayerPart"
    ]
  }

  statement {
    sid    = "AllowECRTokenAuth"
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${var.aws_account_id}:root"]
    }

    actions = [
      "ecr:GetAuthorizationToken"
    ]
  }
}

resource "aws_ecr_repository_policy" "main" {
  repository = aws_ecr_repository.main.name
  policy     = data.aws_iam_policy_document.ecr_policy.json
}
