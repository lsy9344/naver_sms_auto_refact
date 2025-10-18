###############################################################################
# TFLint Configuration
#
# Enforces code quality and best practices for Terraform code.
# Rules enforce naming conventions, prevent deprecated resources,
# and detect hardcoded values.
###############################################################################

plugin "aws" {
  enabled = true
  version = "0.35.0"
  source  = "github.com/terraform-linters/tflint-ruleset-aws"
}

rule "terraform_naming_convention" {
  enabled = true

  # Enforce snake_case for resource names
  variable {
    format = "snake_case"
  }

  locals {
    format = "snake_case"
  }

  output {
    format = "snake_case"
  }

  resource {
    format = "snake_case"
  }
}

rule "terraform_standard_module_structure" {
  enabled = true
}

rule "aws_resource_missing_tags" {
  enabled = true
  tags    = ["Project", "ManagedBy", "Environment"]
}

rule "terraform_unused_declarations" {
  enabled = true
}

rule "terraform_comment_syntax" {
  enabled = true
}

rule "terraform_required_version" {
  enabled = false
}
