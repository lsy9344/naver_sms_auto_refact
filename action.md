TFLint “태그 누락” 해결 작업 지시서 (LLM용)

목표:
tflint의 aws_resource_missing_tags Notice를 제거하고, 공통 태그(Project, ManagedBy, Environment)가 모든 태그 지원 리소스에 적용되도록 소스(HCL)를 수정한다.
(태그 미지원 리소스는 린트에서 제외한다)

0) 공통 원칙

루트에서 공통 태그를 정의하고 → 모듈로 전달 → 모듈 내부 각 리소스에 적용한다.

이미 tags = { ... }가 있는 리소스는 merge(var.tags, {...}) 로 결합한다.

태그 미지원 리소스는 .tflint.hcl의 exclude에 추가한다.

(선택) CI에서는 에러만 실패로 취급하도록 --minimum-failure-severity=error 를 사용한다.

1) 루트: 공통 태그 정의 및 모듈에 전달
1-1. main.tf 에 공통 태그 로컬 변수 추가
locals {
  global_tags = {
    Project     = var.project
    ManagedBy   = "terraform"      # 또는 "github-actions"
    Environment = var.environment
  }
}

1-2. 모듈 호출부에 tags = local.global_tags 전달
module "ecr" {
  source           = "./modules/ecr"
  repository_name  = var.ecr_repository_name
  environment      = var.environment
  tags             = local.global_tags          # ← 추가
}

module "secrets_manager" {
  source      = "./modules/secrets-manager"
  environment = var.environment
  tags        = local.global_tags               # ← 추가
}

module "cloudwatch" {
  source               = "./modules/cloudwatch"
  environment          = var.environment
  lambda_function_name = var.lambda_function_name
  tags                 = local.global_tags      # ← 추가
}

1-3. 필요 변수 정의(variables.tf)
variable "project" {
  type        = string
  description = "Project tag"
  default     = "naver-sms-automation"
}

variable "environment" {
  type        = string
  description = "Environment name"
  default     = "sandbox"
}

2) 각 모듈: variable "tags" 추가

모든 모듈(modules/ecr, modules/secrets-manager, modules/cloudwatch)의 variables.tf 에 아래 블록을 추가.

variable "tags" {
  description = "Common tags to apply to resources"
  type        = map(string)
  default     = {}
}

3) 모듈 내부 리소스: tags 적용
3-1. 태그 지원 리소스는 tags = var.tags (또는 merge) 추가
(ECR) modules/ecr/main.tf
resource "aws_ecr_repository" "main" {
  name                 = var.repository_name
  image_tag_mutability = var.image_tag_mutability

  image_scanning_configuration {
    scan_on_push = var.scan_on_push
  }

  tags = var.tags   # ← 추가
}

(Secrets Manager) modules/secrets-manager/main.tf

기존 태그가 있으므로 merge 사용:

resource "aws_secretsmanager_secret" "secrets" {
  for_each = local.secrets

  name                    = "${local.secret_prefix}/${each.key}"
  description             = each.value.description
  recovery_window_in_days = var.secret_recovery_window_days

  tags = merge(
    var.tags,
    {
      Name        = each.key
      Environment = var.environment
      Type        = "credential"
    }
  )
}

(CloudWatch/이벤트 등) modules/cloudwatch/main.tf

아래 표를 참고해 지원 리소스에만 추가:

리소스	태그 지원	적용 예시
aws_cloudwatch_log_group	✅	tags = var.tags
aws_cloudwatch_metric_alarm	✅	tags = var.tags
aws_cloudwatch_dashboard	✅	tags = var.tags
aws_events_rule	✅	tags = var.tags
aws_events_target	❌	(추가하지 않음)
aws_cloudwatch_log_metric_filter	❌	(추가하지 않음)
aws_lambda_permission	❌	(추가하지 않음)

예시:

resource "aws_cloudwatch_log_group" "app" {
  name              = var.log_group_name
  retention_in_days = 30
  tags              = var.tags
}

resource "aws_cloudwatch_metric_alarm" "error_alarm" {
  # ... 생략 ...
  tags = var.tags
}

resource "aws_events_rule" "schedule" {
  name                = "${var.app_name}-schedule"
  schedule_expression = "rate(20 minutes)"
  tags                = var.tags
}

/* 아래 리소스들은 태그 미지원 → 추가하지 말 것
resource "aws_cloudwatch_log_metric_filter" "filter" { ... }
resource "aws_lambda_permission" "allow_events" { ... }
resource "aws_events_target" "t" { ... }
*/

4) .tflint.hcl: 태그 미지원 리소스 제외

루트 .tflint.hcl에 룰 블록 추가(또는 갱신):

plugin "aws" {
  enabled = true
  version = "0.43.0"
  source  = "github.com/terraform-linters/tflint-ruleset-aws"
}

rule "aws_resource_missing_tags" {
  enabled  = true
  tag_keys = ["ManagedBy", "Project"]

  exclude = [
    "/^aws_lambda_permission\\./",
    "/^aws_cloudwatch_log_metric_filter\\./",
    "/^aws_events_target\\./"
  ]
}


필요 시, tflint 결과를 보고 실제 남는 항목의 정확한 주소(예: module.cloudwatch.aws_lambda_permission.allow_events)를 기준으로 exclude를 추가한다.

5) (선택) CI에서 Notice는 실패 처리하지 않기

.github/workflows/terraform-check.yml 의 TFLint 실행 스텝을 다음처럼 변경:

- run: tflint --config=../.tflint.hcl
+ run: tflint --config=../.tflint.hcl --minimum-failure-severity=error


이렇게 하면 Notice/Warning은 통과, Error만 실패로 처리된다.

6) 검증 절차

terraform -chdir=infrastructure/terraform fmt -recursive

terraform -chdir=infrastructure/terraform validate

로컬/CI에서:

tflint --init

tflint (Notice가 사라졌는지 확인)

일부 Notice가 남으면 → 해당 리소스가 태그 미지원인지 확인 후 .tflint.hcl의 exclude에 추가

7) 주의 사항

default_tags(provider)만으로는 정적 분석인 tflint가 태그를 인식하지 못할 수 있음 → 반드시 리소스 소스에 tags를 명시해야 한다.

merge() 사용 시, 뒤쪽 맵의 동일 키가 우선된다.

태그 미지원 리소스에 tags를 넣지 말 것(오류/불필요 경고 원인).