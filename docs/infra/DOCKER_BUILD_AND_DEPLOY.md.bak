# Docker Build & Deployment Guide

**Story 4.3: Build Docker Container**  
**Updated:** 2025-10-19  
**Status:** Production Ready

---

## Quick Start

### Local Build & Test

```bash
# 1. Build image
docker build -t naver-sms-automation .

# 2. Test with Lambda RIE
docker run --rm -p 9000:8080 --env-file .env naver-sms-automation:latest

# 3. In another terminal, invoke
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" \
  -d '{"smoke_test": true}'
```

### Deploy to ECR

```bash
# 1. Authenticate with ECR
aws ecr get-login-password --region ap-northeast-2 | \
  docker login --username AWS --password-stdin \
  654654307503.dkr.ecr.ap-northeast-2.amazonaws.com

# 2. Tag image for ECR
docker tag naver-sms-automation:latest \
  654654307503.dkr.ecr.ap-northeast-2.amazonaws.com/naver-sms-automation:latest

# 3. Push to ECR
docker push 654654307503.dkr.ecr.ap-northeast-2.amazonaws.com/naver-sms-automation:latest

# 4. Update Lambda
aws lambda update-function-code \
  --function-name naverplace_send_inform \
  --image-uri 654654307503.dkr.ecr.ap-northeast-2.amazonaws.com/naver-sms-automation:latest
```

---

## Detailed Workflow

### 1. Setup (One-Time)

#### 1.1 Clone Repository
```bash
git clone https://github.com/your-org/naver-sms-automation.git
cd naver-sms-automation
```

#### 1.2 Install Prerequisites
```bash
# Docker Desktop (macOS/Windows)
# - Download: https://www.docker.com/products/docker-desktop
# - Install and start Docker daemon

# AWS CLI
brew install awscli  # macOS
# or
choco install awscliv2  # Windows

# Verify installations
docker --version    # Docker 25.x+
aws --version       # AWS CLI 2.x+
```

#### 1.3 Configure AWS Credentials
```bash
# Option 1: AWS CLI config
aws configure
# Enter: Access Key ID, Secret Access Key, Region (ap-northeast-2), Output format (json)

# Option 2: Environment variables
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=ap-northeast-2

# Verify credentials
aws sts get-caller-identity
```

#### 1.4 Create .env File
```bash
# Copy template
cp .env.example .env

# Edit .env with your values
# - AWS_ACCESS_KEY_ID
# - AWS_SECRET_ACCESS_KEY
# - NAVER_USERNAME
# - NAVER_PASSWORD
# - SENS_ACCESS_KEY
# - SENS_SECRET_KEY
# - SENS_SERVICE_ID
# - TELEGRAM_BOT_TOKEN
# - TELEGRAM_CHAT_ID

# IMPORTANT: Do NOT commit .env to git
# .env is in .gitignore for safety
```

---

### 2. Local Development Build

#### 2.1 Build Image
```bash
# Build with default tag
docker build -t naver-sms-automation .

# Build and output build log
docker build -t naver-sms-automation . | tee build.log

# Build with specific tag
docker build -t naver-sms-automation:v1.0.0 .

# Build without cache (force fresh build)
docker build --no-cache -t naver-sms-automation .
```

**Build Output:**
```
#11 exporting to image
#11 exporting layers 3.0s done
#11 exporting manifest sha256:0ec26e27eacb7556b5881a784e7faefd3550692c... done
#11 naming to docker.io/library/naver-sms-automation:latest done
```

**Status Codes:**
- ✅ 0: Build successful
- ❌ 1: Build failed (check error messages above)

#### 2.2 Verify Image
```bash
# List images
docker images naver-sms-automation

# Output should show:
# REPOSITORY                   TAG    IMAGE ID       SIZE
# naver-sms-automation         latest 0f168d8d8b46   1.28GB

# Inspect image details
docker inspect naver-sms-automation:latest

# Check image architecture
docker inspect naver-sms-automation:latest | jq '.[0].Architecture'
# Output: "arm64" (Apple Silicon) or "amd64" (Intel)
```

---

### 3. Local Testing with Lambda RIE

#### 3.1 Start Container
```bash
# Start in foreground (see logs)
docker run --rm -p 9000:8080 --env-file .env naver-sms-automation:latest

# Start in background
docker run --rm -d -p 9000:8080 --env-file .env naver-sms-automation:latest

# Start with volume mount for config (for development)
docker run --rm -p 9000:8080 \
  --env-file .env \
  -v $(pwd)/config:/var/task/config:ro \
  naver-sms-automation:latest
```

**Container Output:**
```
time="2025-10-19T14:57:25Z" level=info msg="Starting up Lambda Runtime Interface Emulator..."
time="2025-10-19T14:57:25Z" level=info msg="Lambda Runtime Interface Emulator listening on port 8080"
time="2025-10-19T14:57:25Z" level=info msg="Ready for Lambda requests"
```

#### 3.2 Invoke Handler
```bash
# Basic invoke (empty event)
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" \
  -d '{}'

# Invoke with test event
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" \
  -H "Content-Type: application/json" \
  -d '{"test": true, "dry_run": true}'

# Capture response to file
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" \
  -d '{}' > response.json

# Pretty-print response
cat response.json | jq .
```

**Expected Response:**
```json
{
  "statusCode": 200,
  "body": "{\"message\": \"Naver SMS automation completed successfully\", ...}"
}
```

#### 3.3 Stop Container
```bash
# Stop background container
docker stop $(docker ps -q --filter ancestor=naver-sms-automation:latest)

# Kill container running in foreground
Ctrl+C

# Remove all stopped containers
docker container prune
```

---

### 4. ECR Deployment

#### 4.1 Create ECR Repository (One-Time)
```bash
# Create repository
aws ecr create-repository \
  --repository-name naver-sms-automation \
  --region ap-northeast-2 \
  --image-scanning-configuration scanOnPush=true \
  --image-tag-mutability MUTABLE

# Output:
# {
#   "repository": {
#     "repositoryArn": "arn:aws:ecr:ap-northeast-2:654654307503:repository/naver-sms-automation",
#     "registryId": "654654307503",
#     "repositoryName": "naver-sms-automation",
#     "repositoryUri": "654654307503.dkr.ecr.ap-northeast-2.amazonaws.com/naver-sms-automation"
#   }
# }
```

#### 4.2 Login to ECR
```bash
# Login (credential valid for 12 hours)
aws ecr get-login-password --region ap-northeast-2 | \
  docker login --username AWS --password-stdin \
  654654307503.dkr.ecr.ap-northeast-2.amazonaws.com

# Output: Login Succeeded

# Verify login
cat ~/.docker/config.json | jq '.auths | keys'
```

#### 4.3 Tag & Push Image
```bash
# Set variables
ACCOUNT=654654307503
REGION=ap-northeast-2
REPO=naver-sms-automation
TAG=v1.0.0
COMMIT_SHA=$(git rev-parse --short HEAD)

# Tag for ECR
docker tag naver-sms-automation:latest \
  $ACCOUNT.dkr.ecr.$REGION.amazonaws.com/$REPO:$TAG

docker tag naver-sms-automation:latest \
  $ACCOUNT.dkr.ecr.$REGION.amazonaws.com/$REPO:latest

docker tag naver-sms-automation:latest \
  $ACCOUNT.dkr.ecr.$REGION.amazonaws.com/$REPO:$COMMIT_SHA

# Push to ECR
docker push $ACCOUNT.dkr.ecr.$REGION.amazonaws.com/$REPO:$TAG
docker push $ACCOUNT.dkr.ecr.$REGION.amazonaws.com/$REPO:latest
docker push $ACCOUNT.dkr.ecr.$REGION.amazonaws.com/$REPO:$COMMIT_SHA

# Verify in ECR
aws ecr list-images --repository-name $REPO --region $REGION

# Output:
# {
#   "imageIds": [
#     {"imageTag": "v1.0.0", "imageDigest": "sha256:..."},
#     {"imageTag": "latest", "imageDigest": "sha256:..."},
#     {"imageTag": "abc1234", "imageDigest": "sha256:..."}
#   ]
# }
```

#### 4.4 Update Lambda Function
```bash
# Update with image URI
aws lambda update-function-code \
  --function-name naverplace_send_inform \
  --image-uri 654654307503.dkr.ecr.ap-northeast-2.amazonaws.com/naver-sms-automation:latest \
  --region ap-northeast-2

# Output:
# {
#   "FunctionName": "naverplace_send_inform",
#   "FunctionArn": "arn:aws:lambda:ap-northeast-2:654654307503:function:naverplace_send_inform",
#   "Runtime": "python3.11",
#   "ImageConfigResponse": {
#     "ImageUri": "654654307503.dkr.ecr.ap-northeast-2.amazonaws.com/naver-sms-automation:latest"
#   }
# }
```

#### 4.5 Test Deployed Function
```bash
# Invoke Lambda
aws lambda invoke \
  --function-name naverplace_send_inform \
  --region ap-northeast-2 \
  response.json

# Check response
cat response.json | jq .

# View CloudWatch logs
aws logs tail /aws/lambda/naverplace_send_inform --follow
```

---

### 5. CI/CD Integration

#### 5.1 GitHub Actions Workflow

**File:** `.github/workflows/docker-deploy.yml`

```yaml
name: Build and Deploy Docker Container

on:
  push:
    branches: [main]
    paths:
      - 'Dockerfile'
      - 'src/**'
      - 'config/**'
      - 'requirements.txt'

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v3

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ap-northeast-2

      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v1

      - name: Build, tag, and push image to Amazon ECR
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          ECR_REPOSITORY: naver-sms-automation
          IMAGE_TAG: ${{ github.sha }}
        run: |
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG .
          docker tag $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG \
            $ECR_REGISTRY/$ECR_REPOSITORY:latest
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:latest

      - name: Update Lambda function
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          ECR_REPOSITORY: naver-sms-automation
          IMAGE_TAG: latest
        run: |
          aws lambda update-function-code \
            --function-name naverplace_send_inform \
            --image-uri $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG

      - name: Verify Lambda update
        run: |
          aws lambda get-function-code-location \
            --function-name naverplace_send_inform
```

#### 5.2 GitHub Secrets Setup

```bash
# Required secrets in GitHub repository settings:
# Settings → Secrets → Actions → New repository secret

AWS_ACCESS_KEY_ID=your_access_key_id
AWS_SECRET_ACCESS_KEY=your_secret_access_key
```

#### 5.3 CI/CD Workflow Trigger

```bash
# Workflow triggers on:
# 1. Push to main branch
# 2. AND changes to these files:
#    - Dockerfile
#    - src/**
#    - config/**
#    - requirements.txt

# Example workflow:
git add Dockerfile src/main.py
git commit -m "Update Lambda handler"
git push origin main

# → GitHub Actions runs docker-deploy.yml
# → Builds image
# → Pushes to ECR
# → Updates Lambda
```

---

## Troubleshooting

### Build Issues

#### Issue: "No space left on device"
```bash
# Problem: Docker disk full
# Solution: Clean up Docker artifacts
docker system prune -a --volumes
docker image prune -a
docker container prune
docker volume prune
```

#### Issue: "Failed to resolve module"
```bash
# Problem: Python package missing
# Solution: Update requirements.txt and rebuild
pip install -r requirements.txt
docker build --no-cache -t naver-sms-automation .
```

#### Issue: "Chrome binary not found"
```bash
# Problem: Chrome installation failed
# Solution: Rebuild and check logs
docker build --no-cache -t naver-sms-automation . | grep -i chrome
```

### Runtime Issues

#### Issue: "Connection refused" from container
```bash
# Problem: Lambda RIE not running or wrong port
# Solution: Verify container running
docker ps
docker logs <container_id>
```

#### Issue: "Environment variable not set"
```bash
# Problem: .env file not loaded
# Solution: Verify .env file and Docker run command
docker run --rm -p 9000:8080 --env-file .env naver-sms-automation:latest
```

#### Issue: "Permission denied" on AWS operations
```bash
# Problem: AWS credentials invalid or insufficient permissions
# Solution: Check credentials and IAM role
aws sts get-caller-identity
aws lambda get-function --function-name naverplace_send_inform
```

### Deployment Issues

#### Issue: "ImageNotFound" in Lambda update
```bash
# Problem: Image URI incorrect or not pushed
# Solution: Verify image in ECR
aws ecr list-images --repository-name naver-sms-automation
```

#### Issue: "Lambda timeout during update"
```bash
# Problem: Image too large or slow to pull
# Solution: Check image size and network
docker images naver-sms-automation
aws lambda update-function-code ... --region ap-northeast-2
```

---

## Make Targets

```makefile
# Local development
make docker-build          # Build image locally
make docker-run            # Run container with Lambda RIE
make docker-test           # Invoke test request

# ECR deployment
make docker-login          # Login to ECR
make docker-tag            # Tag image for ECR
make docker-push           # Push to ECR
make docker-deploy         # Build, tag, push, update Lambda
make docker-verify         # Verify Lambda updated

# Cleanup
make docker-clean          # Remove local image
make docker-prune          # Clean Docker system
```

---

## Deployment Checklist

### Pre-Deployment

- [ ] Docker Desktop installed and running
- [ ] AWS CLI installed (`aws --version`)
- [ ] AWS credentials configured (`aws sts get-caller-identity`)
- [ ] ECR repository exists (`aws ecr describe-repositories --repository-names naver-sms-automation`)
- [ ] Lambda function exists (`aws lambda get-function --function-name naverplace_send_inform`)
- [ ] DynamoDB tables exist (`aws dynamodb list-tables | grep sms`)
- [ ] All secrets/credentials ready (Naver, SENS, Telegram)

### Build & Test

- [ ] Local build succeeds (`docker build -t naver-sms-automation .`)
- [ ] Image size acceptable (`docker images` shows < 2GB)
- [ ] Lambda RIE starts (`docker run --rm -p 9000:8080 ...`)
- [ ] Handler invocation works (`curl -XPOST http://localhost:9000/...`)
- [ ] No errors in Lambda logs

### Deployment

- [ ] ECR login successful (`docker login ...`)
- [ ] Image tagged correctly (`docker tag naver-sms-automation:latest ...`)
- [ ] Image pushed to ECR (`docker push ...`)
- [ ] Lambda code updated (`aws lambda update-function-code ...`)
- [ ] Lambda invocation works (`aws lambda invoke ...`)

### Post-Deployment

- [ ] CloudWatch logs show successful execution
- [ ] DynamoDB records updated
- [ ] Telegram notification received
- [ ] SMS sent to test phone (if enabled)
- [ ] No error notifications
- [ ] Monitor for 24 hours

---

## Version Management

### Semantic Versioning

- **Major** (v1.0.0): Breaking changes, major refactors
- **Minor** (v1.1.0): New features, non-breaking changes
- **Patch** (v1.0.1): Bug fixes, hotpatches

### Git Tags

```bash
# Tag release
git tag -a v1.0.0 -m "Initial Docker containerization"
git push origin v1.0.0

# View tags
git tag -l
git show v1.0.0

# Retag if needed
git tag -d v1.0.0
git tag -a v1.0.0 -m "New message"
```

### Image Tags in ECR

- `latest`: Current production version
- `v1.0.0`: Release version tag
- `abc1234f`: Git commit SHA (for debugging)

---

## Security Best Practices

### Image Security

- ✅ Use official Lambda base image (`public.ecr.aws/lambda/python:3.11`)
- ✅ Pin Chrome/ChromeDriver versions
- ✅ Remove unnecessary packages (`yum clean all`)
- ✅ No hardcoded credentials in Dockerfile

### ECR Security

- ✅ Image scanning enabled (`scanOnPush=true`)
- ✅ Private repository (not public)
- ✅ IAM permissions restricted
- ✅ Lifecycle policy for old images

### Deployment Security

- ✅ Credentials in AWS Secrets Manager (not in code)
- ✅ GitHub Secrets for CI/CD credentials
- ✅ .env file not committed to Git
- ✅ .env in .gitignore

### Runtime Security

- ✅ Lambda execution role with minimal permissions
- ✅ VPC endpoint for DynamoDB (if in VPC)
- ✅ CloudWatch Logs encryption
- ✅ Regular security updates

---

## Performance Optimization

### Build Optimization

```bash
# Use BuildKit for faster builds
DOCKER_BUILDKIT=1 docker build -t naver-sms-automation .

# Enable inline cache for CI/CD
docker buildx build --push --cache-from type=registry,ref=image:buildcache .
```

### Image Optimization

- Multi-stage builds (future)
- Layer caching strategy
- Dependency consolidation

### Runtime Optimization

- Lazy Chrome initialization
- Connection pooling for APIs
- Lambda memory configuration

---

## References

- [AWS Lambda Container Images](https://docs.aws.amazon.com/lambda/latest/dg/images-create.html)
- [Lambda Runtime Interface](https://github.com/aws/aws-lambda-runtime-interface-emulator)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [ECR User Guide](https://docs.aws.amazon.com/AmazonECR/latest/userguide/)

---

## Support & Questions

For questions or issues:
1. Check [Troubleshooting](#troubleshooting) section
2. Review CloudWatch logs
3. Check AWS documentation
4. Contact DevOps team

---

**Last Updated:** 2025-10-19  
**Maintained By:** DevOps Team  
**Status:** Production Ready
