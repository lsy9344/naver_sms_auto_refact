#!/bin/bash
###############################################################################
# Infrastructure Deployment Bootstrap Script
#
# Wraps Terraform commands with validation and workspace management.
# Automatically validates tool versions, sources environment config,
# selects workspace based on environment flag, and executes terraform commands.
#
# Usage:
#   ./scripts/deploy_infra.sh -dev plan       # Plan for dev environment
#   ./scripts/deploy_infra.sh -staging apply  # Apply to staging
#   ./scripts/deploy_infra.sh -prod plan      # Plan for production
#   ./scripts/deploy_infra.sh -sandbox destroy # Destroy sandbox resources
###############################################################################

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
TERRAFORM_MIN_VERSION="1.5.0"
AWS_CLI_MIN_VERSION="2.13.0"
TERRAFORM_DIR="infrastructure/terraform"
SCRIPTS_DIR="scripts"

###############################################################################
# Helper Functions
###############################################################################

log_info() {
  echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
  echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
  echo -e "${RED}[ERROR]${NC} $1"
}

check_version() {
  local cmd=$1
  local required=$2
  local actual

  if ! command -v "$cmd" &> /dev/null; then
    log_error "$cmd not found. Please install it."
    exit 1
  fi

  case $cmd in
    terraform)
      actual=$(terraform version | head -1 | awk '{print $2}' | sed 's/v//')
      ;;
    aws)
      actual=$(aws --version | awk '{print $1}' | cut -d'/' -f2)
      ;;
    *)
      log_error "Unknown command: $cmd"
      exit 1
      ;;
  esac

  # Simple version comparison (assumes semantic versioning)
  if [ "$(printf '%s\n' "$required" "$actual" | sort -V | head -n1)" != "$required" ]; then
    log_error "$cmd version $actual is less than required $required"
    exit 1
  fi

  log_info "$cmd version $actual is valid (required: $required)"
}

load_env_config() {
  local env_file="${SCRIPTS_DIR}/.env.local"

  if [ -f "$env_file" ]; then
    log_info "Loading environment configuration from $env_file"
    # shellcheck disable=SC1090
    source "$env_file"
  else
    log_warn "No $env_file found. Using defaults."
  fi
}

select_workspace() {
  local environment=$1
  local state_bucket="terraform-state-${AWS_ACCOUNT_ID}"
  local state_key="naver-sms-automation/terraform.tfstate"
  local workspace_prefix="naver-sms-automation"

  log_info "Initializing Terraform backend for environment: $environment"

  terraform init \
    -backend-config="bucket=${state_bucket}" \
    -backend-config="key=${state_key}" \
    -backend-config="workspace_key_prefix=${workspace_prefix}" \
    -backend-config="region=ap-northeast-2" \
    -backend-config="dynamodb_table=terraform-locks" \
    -backend-config="encrypt=true" \
    -upgrade=false

  log_info "Backend initialized successfully"

  if terraform workspace list | grep -qE "^[[:space:]]*(\\*\\s)?${environment}\$"; then
    log_info "Selecting existing workspace: ${environment}"
    terraform workspace select "${environment}" >/dev/null
  else
    log_info "Creating workspace: ${environment}"
    terraform workspace new "${environment}" >/dev/null
  fi

  log_info "Workspace ready: $(terraform workspace show)"
}

run_terraform_command() {
  local environment=$1
  local command=$2

  # Lock file path for concurrency prevention
  local lock_file="/tmp/terraform-${environment}.lock"

  # Attempt to acquire lock with timeout
  local lock_acquired=false
  for i in {1..5}; do
    if mkdir "$lock_file" 2>/dev/null; then
      lock_acquired=true
      break
    fi
    log_warn "Waiting for lock... (attempt $i/5)"
    sleep 2
  done

  if [ "$lock_acquired" = false ]; then
    log_error "Failed to acquire lock. Another deployment may be in progress."
    exit 1
  fi

  # Ensure lock cleanup
  trap "rm -rf $lock_file" EXIT

  local tfvars_file="environments/${environment}.tfvars"

  if [ ! -f "${TERRAFORM_DIR}/${tfvars_file}" ]; then
    log_error "Variables file not found: ${TERRAFORM_DIR}/${tfvars_file}"
    exit 1
  fi

  case $command in
    plan)
      log_info "Running terraform plan for $environment..."
      terraform plan \
        -var-file="$tfvars_file" \
        -out="tfplan-${environment}.bin"
      log_info "Plan saved to tfplan-${environment}.bin"
      ;;
    apply)
      log_info "Running terraform apply for $environment..."
      terraform apply \
        -var-file="$tfvars_file" \
        -auto-approve
      log_info "Apply completed successfully"
      ;;
    destroy)
      if [ "$environment" != "sandbox" ]; then
        log_error "Destroy is only allowed for sandbox environment"
        exit 1
      fi
      log_warn "Destroying all resources in sandbox environment..."
      terraform destroy \
        -var-file="$tfvars_file" \
        -auto-approve
      log_info "Sandbox destroyed successfully"
      ;;
    validate)
      log_info "Validating Terraform configuration..."
      terraform validate
      log_info "Configuration is valid"
      ;;
    fmt)
      log_info "Formatting Terraform files..."
      terraform fmt -recursive
      log_info "Files formatted"
      ;;
    *)
      log_error "Unknown command: $command"
      exit 1
      ;;
  esac
}

###############################################################################
# Main Script
###############################################################################

main() {
  local environment=""
  local command="plan"

  # Parse arguments
  while [[ $# -gt 0 ]]; do
    case $1 in
      -dev)
        environment="dev"
        shift
        ;;
      -staging)
        environment="staging"
        shift
        ;;
      -prod)
        environment="prod"
        shift
        ;;
      -sandbox)
        environment="sandbox"
        shift
        ;;
      plan|apply|destroy|validate|fmt)
        command="$1"
        shift
        ;;
      *)
        log_error "Unknown argument: $1"
        echo "Usage: $0 [-dev|-staging|-prod|-sandbox] [plan|apply|destroy|validate|fmt]"
        exit 1
        ;;
    esac
  done

  # Validate inputs
  if [ -z "$environment" ]; then
    log_error "Environment not specified. Use -dev, -staging, -prod, or -sandbox"
    exit 1
  fi

  log_info "Infrastructure deployment script started"
  log_info "Environment: $environment, Command: $command"

  # Change to terraform directory
  cd "$TERRAFORM_DIR" || exit 1

  # Validate tool versions
  check_version terraform "$TERRAFORM_MIN_VERSION"
  check_version aws "$AWS_CLI_MIN_VERSION"

  # Load environment configuration
  load_env_config

  # Validate AWS credentials
  if ! aws sts get-caller-identity > /dev/null 2>&1; then
    log_error "AWS credentials not configured or invalid"
    exit 1
  fi

  # Get AWS account ID
  AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
  export AWS_ACCOUNT_ID
  log_info "Using AWS Account: $AWS_ACCOUNT_ID"

  # Initialize backend and select workspace
  select_workspace "$environment"

  # Execute terraform command
  run_terraform_command "$environment" "$command"

  log_info "Script completed successfully"
}

main "$@"
