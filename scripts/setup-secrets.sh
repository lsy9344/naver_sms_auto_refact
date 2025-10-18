#!/bin/bash
###############################################################################
# Secrets Manager Bootstrap Script
#
# Safely creates or updates the secrets required by the Terraform infrastructure
# modules. Secrets are never written to disk or echoed back to the terminal.
#
# Usage:
#   ./scripts/setup-secrets.sh --env dev
#   TF_AUTO_APPROVE=true ./scripts/setup-secrets.sh --env staging
#
# Requirements:
#   - AWS CLI v2.13+
#   - python3 (for JSON encoding)
#   - IAM permissions from docs/qa/required-iam-policy.json
###############################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_ENV_FILE="${SCRIPT_DIR}/.env.local"
AWS_REGION_DEFAULT="ap-northeast-2"

ENVIRONMENT=""
AWS_REGION="${AWS_REGION_DEFAULT}"
DRY_RUN=false
AUTO_APPROVE="${TF_AUTO_APPROVE:-false}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

usage() {
  cat <<EOF
Secrets Manager bootstrap helper.

Usage:
  $(basename "$0") --env <dev|staging|prod|sandbox> [--region <aws-region>] [--dry-run]

Options:
  --env, -e        Target environment (required)
  --region, -r     AWS region (default: ${AWS_REGION_DEFAULT})
  --dry-run        Validate inputs and show actions without calling AWS
  --help, -h       Show this help message

Environment variables:
  TF_AUTO_APPROVE=true   Skip confirmation prompts
  NAVER_USERNAME, NAVER_PASSWORD
  SENS_ACCESS_KEY, SENS_SECRET_KEY, SENS_SERVICE_ID
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

If variables are not set, you will be prompted (input hidden).
EOF
}

require_cmd() {
  local cmd=$1
  if ! command -v "$cmd" &> /dev/null; then
    log_error "Required command not found: $cmd"
    exit 1
  fi
}

load_env_file() {
  if [ -f "$DEFAULT_ENV_FILE" ]; then
    log_info "Loading environment overrides from ${DEFAULT_ENV_FILE}"
    # shellcheck disable=SC1090
    source "$DEFAULT_ENV_FILE"
  fi
}

confirm() {
  local question=$1
  if [ "${AUTO_APPROVE}" = "true" ]; then
    return 0
  fi
  read -rp "${question} [y/N]: " answer
  case "$answer" in
    [yY][eE][sS]|[yY]) return 0 ;;
    *)                 return 1 ;;
  esac
}

prompt_secret() {
  local env_var=$1
  local prompt=$2
  local value="${!env_var:-}"

  if [ -n "$value" ]; then
    log_info "Using ${env_var} from environment"
    printf '%s' "$value"
    return
  fi

  read -rsp "${prompt}: " value
  echo

  if [ -z "$value" ]; then
    log_error "${env_var} cannot be empty"
    exit 1
  fi

  printf '%s' "$value"
}

build_secret_json() {
  python3 - "$@" <<'PY'
import json, sys
args = sys.argv[1:]
if len(args) % 2 != 0:
    raise SystemExit("Secret fields must be passed as key/value pairs")
pairs = zip(args[0::2], args[1::2])
print(json.dumps({k: v for k, v in pairs}))
PY
}

secret_exists() {
  local name=$1
  aws secretsmanager describe-secret \
    --secret-id "$name" \
    --region "$AWS_REGION" >/dev/null 2>&1
}

apply_secret() {
  local name=$1
  local description=$2
  local payload=$3

  if [ "$DRY_RUN" = true ]; then
    log_info "[DRY-RUN] Would upsert secret: ${name}"
    return
  fi

  if secret_exists "$name"; then
    log_info "Updating existing secret: ${name}"
    aws secretsmanager put-secret-value \
      --secret-id "$name" \
      --secret-string "$payload" \
      --region "$AWS_REGION" >/dev/null
  else
    log_info "Creating new secret: ${name}"
    aws secretsmanager create-secret \
      --name "$name" \
      --description "$description" \
      --secret-string "$payload" \
      --region "$AWS_REGION" >/dev/null
  fi

  log_info "Secret upsert successful: ${name}"
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --env|-e)
        ENVIRONMENT="${2:-}"
        shift 2
        ;;
      --region|-r)
        AWS_REGION="${2:-}"
        shift 2
        ;;
      --dry-run)
        DRY_RUN=true
        shift
        ;;
      --help|-h)
        usage
        exit 0
        ;;
      *)
        log_error "Unknown argument: $1"
        echo
        usage
        exit 1
        ;;
    esac
  done

  if [ -z "$ENVIRONMENT" ]; then
    log_error "--env flag is required"
    echo
    usage
    exit 1
  fi

  case "$ENVIRONMENT" in
    dev|staging|prod|sandbox) ;;
    *)
      log_error "Unsupported environment: ${ENVIRONMENT}"
      exit 1
      ;;
  esac
}

main() {
  parse_args "$@"

  require_cmd aws
  require_cmd python3

  load_env_file

  log_info "Target environment: ${ENVIRONMENT}"
  log_info "AWS region: ${AWS_REGION}"

  if ! aws sts get-caller-identity --region "$AWS_REGION" >/dev/null 2>&1; then
    log_error "Unable to validate AWS credentials. Configure profile or environment variables."
    exit 1
  fi

  if [ "$DRY_RUN" = false ] && ! confirm "Proceed with secret upsert operations?"; then
    log_warn "Aborted by user"
    exit 0
  fi

  local prefix="naver-sms-automation/${ENVIRONMENT}"

  local naver_username naver_password sens_access sens_secret sens_service telegram_token telegram_chat
  naver_username=$(prompt_secret "NAVER_USERNAME" "Enter NAVER_USERNAME")
  naver_password=$(prompt_secret "NAVER_PASSWORD" "Enter NAVER_PASSWORD")
  sens_access=$(prompt_secret "SENS_ACCESS_KEY" "Enter SENS_ACCESS_KEY")
  sens_secret=$(prompt_secret "SENS_SECRET_KEY" "Enter SENS_SECRET_KEY")
  sens_service=$(prompt_secret "SENS_SERVICE_ID" "Enter SENS_SERVICE_ID")
  telegram_token=$(prompt_secret "TELEGRAM_BOT_TOKEN" "Enter TELEGRAM_BOT_TOKEN")
  telegram_chat=$(prompt_secret "TELEGRAM_CHAT_ID" "Enter TELEGRAM_CHAT_ID")

  local naver_payload sens_payload telegram_payload
  naver_payload=$(build_secret_json username "$naver_username" password "$naver_password")
  sens_payload=$(build_secret_json access_key "$sens_access" secret_key "$sens_secret" service_id "$sens_service")
  telegram_payload=$(build_secret_json bot_token "$telegram_token" chat_id "$telegram_chat")

  apply_secret \
    "${prefix}/naver-credentials" \
    "Naver login credentials (username/password) for ${ENVIRONMENT}" \
    "$naver_payload"

  apply_secret \
    "${prefix}/sens-credentials" \
    "Naver Cloud SENS API credentials for ${ENVIRONMENT}" \
    "$sens_payload"

  apply_secret \
    "${prefix}/telegram-credentials" \
    "Telegram bot credentials for ${ENVIRONMENT}" \
    "$telegram_payload"

  log_info "Secrets bootstrap complete"
}

main "$@"
