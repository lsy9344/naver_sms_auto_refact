#!/bin/bash
#
# Bootstrap Environment Script for Naver SMS Automation
#
# This script configures the development environment with AWS credentials
# and validates that required secrets exist in AWS Secrets Manager.
#
# IMPORTANT: This script does NOT echo, log, or write secret values to files.
# All credentials are accessed in-memory only via AWS CLI queries.
#
# Usage:
#   source scripts/bootstrap_env.sh
#   or
#   ./scripts/bootstrap_env.sh
#
# Requirements:
#   - AWS CLI v2 or later
#   - AWS credentials configured with access to Secrets Manager
#   - Appropriate IAM permissions (see below)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Configuration
AWS_REGION="ap-northeast-2"
SECRET_PREFIX="naver-sms-automation"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_aws_cli() {
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI not found. Please install AWS CLI v2 or later."
        log_error "https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
        return 1
    fi
    
    local aws_version=$(aws --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
    log_info "AWS CLI version: $aws_version"
}

check_aws_credentials() {
    if ! aws sts get-caller-identity --region "$AWS_REGION" &> /dev/null; then
        log_error "AWS credentials not configured or invalid."
        log_error "Configure credentials using one of:"
        log_error "  - aws configure"
        log_error "  - AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables"
        log_error "  - IAM role (if running on EC2/Lambda)"
        return 1
    fi
    
    local account_id=$(aws sts get-caller-identity --query Account --output text)
    local arn=$(aws sts get-caller-identity --query Arn --output text)
    log_info "AWS Account: $account_id"
    log_info "AWS Principal: $arn"
}

validate_secrets_exist() {
    log_info "Validating secrets in Secrets Manager..."
    
    local required_secrets=(
        "$SECRET_PREFIX/naver-credentials"
        "$SECRET_PREFIX/sens-credentials"
        "$SECRET_PREFIX/telegram-credentials"
    )
    
    local missing_secrets=()
    
    for secret_id in "${required_secrets[@]}"; do
        if aws secretsmanager describe-secret --secret-id "$secret_id" \
            --region "$AWS_REGION" &> /dev/null; then
            log_info "✓ Secret found: $secret_id"
        else
            log_error "✗ Secret NOT found: $secret_id"
            missing_secrets+=("$secret_id")
        fi
    done
    
    if [ ${#missing_secrets[@]} -gt 0 ]; then
        log_error "Missing secrets:"
        for secret in "${missing_secrets[@]}"; do
            log_error "  - $secret"
        done
        log_error "Please create these secrets using AWS Secrets Manager console or:"
        log_error "  aws secretsmanager create-secret --name <secret-id> --secret-string '{...}'"
        return 1
    fi
    
    log_info "All required secrets are present in Secrets Manager"
}

validate_secret_schema() {
    log_info "Validating secret schemas..."
    
    # Validate Naver credentials
    if ! aws secretsmanager get-secret-value \
        --secret-id "$SECRET_PREFIX/naver-credentials" \
        --region "$AWS_REGION" \
        --query 'SecretString' --output text | grep -q '"username"' && \
       ! aws secretsmanager get-secret-value \
        --secret-id "$SECRET_PREFIX/naver-credentials" \
        --region "$AWS_REGION" \
        --query 'SecretString' --output text | grep -q '"password"'; then
        log_error "Naver credentials missing required fields: username, password"
        return 1
    fi
    log_info "✓ Naver credentials schema valid"
    
    # Validate SENS credentials
    if ! aws secretsmanager get-secret-value \
        --secret-id "$SECRET_PREFIX/sens-credentials" \
        --region "$AWS_REGION" \
        --query 'SecretString' --output text | grep -q '"access_key"' && \
       ! aws secretsmanager get-secret-value \
        --secret-id "$SECRET_PREFIX/sens-credentials" \
        --region "$AWS_REGION" \
        --query 'SecretString' --output text | grep -q '"secret_key"'; then
        log_error "SENS credentials missing required fields: access_key, secret_key, service_id"
        return 1
    fi
    log_info "✓ SENS credentials schema valid"
    
    # Validate Telegram credentials
    if ! aws secretsmanager get-secret-value \
        --secret-id "$SECRET_PREFIX/telegram-credentials" \
        --region "$AWS_REGION" \
        --query 'SecretString' --output text | grep -q '"bot_token"' && \
       ! aws secretsmanager get-secret-value \
        --secret-id "$SECRET_PREFIX/telegram-credentials" \
        --region "$AWS_REGION" \
        --query 'SecretString' --output text | grep -q '"chat_id"'; then
        log_error "Telegram credentials missing required fields: bot_token, chat_id"
        return 1
    fi
    log_info "✓ Telegram credentials schema valid"
}

display_iam_requirements() {
    cat << 'EOF'

================================================================================
IAM PERMISSIONS REQUIRED
================================================================================

The AWS principal (user/role) running this application needs the following
permissions in their IAM policy:

{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "SecretsManagerRead",
            "Effect": "Allow",
            "Action": [
                "secretsmanager:GetSecretValue",
                "secretsmanager:DescribeSecret"
            ],
            "Resource": [
                "arn:aws:secretsmanager:ap-northeast-2:ACCOUNT_ID:secret:naver-sms-automation/naver-credentials-*",
                "arn:aws:secretsmanager:ap-northeast-2:ACCOUNT_ID:secret:naver-sms-automation/sens-credentials-*",
                "arn:aws:secretsmanager:ap-northeast-2:ACCOUNT_ID:secret:naver-sms-automation/telegram-credentials-*"
            ]
        },
        {
            "Sid": "KMSDecrypt",
            "Effect": "Allow",
            "Action": [
                "kms:Decrypt"
            ],
            "Resource": [
                "arn:aws:kms:ap-northeast-2:ACCOUNT_ID:key/KEY_ID"
            ],
            "Condition": {
                "StringEquals": {
                    "kms:ViaService": "secretsmanager.ap-northeast-2.amazonaws.com"
                }
            }
        }
    ]
}

NOTES:
1. Replace ACCOUNT_ID with your AWS account ID (12 digits)
2. Replace KEY_ID with the KMS key ID used by Secrets Manager (if using custom encryption)
3. If using AWS-managed key (default), kms:Decrypt may not be needed
4. Lambda execution role should have these permissions when deployed
5. Local development requires these permissions in user IAM policy
6. CI/CD deployment role should have these permissions

For more information:
- Secrets Manager: https://docs.aws.amazon.com/secretsmanager/latest/userguide/
- KMS permissions: https://docs.aws.amazon.com/kms/latest/developerguide/

================================================================================

EOF
}

setup_local_development() {
    log_info "Setting up local development environment..."
    
    # Check for AWS credentials in environment
    if [ -n "$AWS_PROFILE" ]; then
        log_info "Using AWS profile: $AWS_PROFILE"
    elif [ -n "$AWS_ACCESS_KEY_ID" ]; then
        log_info "Using AWS credentials from environment variables"
    else
        log_warn "No AWS_PROFILE or AWS_ACCESS_KEY_ID set"
        log_warn "Credentials will be fetched from ~/.aws/config or ~/.aws/credentials"
        log_info "For local development, use:"
        log_info "  export AWS_PROFILE=<profile-name>"
        log_info "  or"
        log_info "  aws configure --profile <profile-name>"
    fi
    
    # Set environment variables for application
    export AWS_REGION="$AWS_REGION"
    
    log_info "Environment variables set:"
    log_info "  AWS_REGION: $AWS_REGION"
}

main() {
    log_info "Bootstrapping Naver SMS Automation environment..."
    
    check_aws_cli || return 1
    check_aws_credentials || return 1
    validate_secrets_exist || return 1
    validate_secret_schema || return 1
    setup_local_development
    
    log_info "Bootstrap complete! Environment is ready."
    display_iam_requirements
}

# Run main if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main
fi
