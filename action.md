🛠 Terraform tags 중복 수정 지침서 (LLM 명령용)
🎯 목표

Terraform 리소스 블록에서 tags 인자가 두 번 이상 정의되어 있는 경우 하나만 남기도록 수정한다.

리소스별로 상황에 따라 tags = var.tags 또는 tags = merge(var.tags, {...}) 중 하나만 사용한다.

최종적으로 terraform validate 에러가 발생하지 않도록 한다.

🧾 수정 규칙

같은 리소스 블록 안에 tags 인자가 중복되어 있으면 한 줄만 남긴다.
예시: 아래와 같은 코드는 ❌ 잘못된 코드

tags = var.tags
tags = merge(var.tags, { Name = "my-resource" })


리소스에 별도 태그가 필요 없다면 아래와 같이 수정한다.

tags = var.tags


리소스에 별도 태그가 필요하다면 아래와 같이 수정한다.

tags = merge(
  var.tags,
  {
    Name = "my-resource"
    # 기존에 남겨야 할 태그만 여기에 둔다
  }
)


tags 블록이 여러 개 있을 경우:

기존의 tags = var.tags는 삭제

merge() 버전만 유지하고 기존 태그들을 병합한다.

merge() 안에 불필요한 중복 키가 없는지 확인한다.

🧭 적용 대상

modules/ecr/main.tf

modules/secrets-manager/main.tf

modules/cloudwatch/main.tf (태그 지원 리소스만 적용)

aws_cloudwatch_log_group

aws_cloudwatch_metric_alarm

aws_cloudwatch_dashboard

aws_events_rule

❌ aws_lambda_permission, aws_cloudwatch_log_metric_filter, aws_events_target는 수정 대상 아님

🧪 작업 후 검증 절차

파일 저장 후 아래 명령 실행

terraform -chdir=infrastructure/terraform fmt -recursive
terraform -chdir=infrastructure/terraform validate


에러가 없는지 확인한다:

Success! The configuration is valid.


TFLint도 재실행

tflint --init
tflint

📝 주의 사항

tags는 한 리소스 블록에 단 1회만 선언할 수 있다.

merge() 사용 시, 동일한 키가 있을 경우 뒤쪽 값이 우선된다.

태그 미지원 리소스에는 tags를 추가하지 않는다.

코드 정렬(terraform fmt)도 함께 수행한다.