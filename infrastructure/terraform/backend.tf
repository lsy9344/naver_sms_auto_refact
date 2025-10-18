###############################################################################
# Remote state backend configuration
# 
# Use: terraform init -backend-config="bucket=terraform-state-{account-id}" \
#                      -backend-config="key=naver-sms-automation/{environment}/terraform.tfstate" \
#                      -backend-config="region=ap-northeast-2" \
#                      -backend-config="dynamodb_table=terraform-locks" \
#                      -backend-config="encrypt=true"
############################################################################### 

terraform {
  backend "s3" {
    # Backend config values provided via -backend-config flags during init
    # Bucket: terraform-state-{account-id}
    # Key: naver-sms-automation/{environment}/terraform.tfstate
    # Region: ap-northeast-2
    # DynamoDB Table: terraform-locks
    # Encrypt: true
  }
}
