###############################################################################
# TFLint Configuration
#
# Enforces code quality and best practices for Terraform code.
# Rules enforce naming conventions, prevent deprecated resources,
# and detect hardcoded values.
###############################################################################

plugin "aws" {
  enabled = true
  version = "0.25.0"
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

rule "aws_instance_default_security_group" {
  enabled = true
}

rule "aws_resource_missing_tags" {
  enabled = true
  tags    = ["Project", "ManagedBy", "Environment"]
}

rule "aws_s3_bucket_server_side_encryption_configuration" {
  enabled = true
}

rule "aws_s3_bucket_versioning" {
  enabled = true
}

rule "aws_iam_policy_no_admin_privileges" {
  enabled = true
}

rule "aws_iam_policy_blacklist_check" {
  enabled = false
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

rule "aws_security_group_rule_description_required" {
  enabled = true
}

rule "aws_elasticache_replication_group_default_parameter_group" {
  enabled = true
}

rule "aws_db_instance_encrypted" {
  enabled = true
}
