# Dockerfile for Naver SMS Automation Lambda Function
# Story 4.3: Build Docker Container
# 
# Purpose:
#   Build a Lambda-compatible container image that packages the refactored
#   Naver SMS automation service with Python 3.11, Chrome/ChromeDriver,
#   and all dependencies for ECR deployment.
#
# Base Image Rationale:
#   - public.ecr.aws/lambda/python:3.11 provides:
#     * Official AWS Lambda Python 3.11 runtime
#     * Pre-configured Lambda handler environment ($LAMBDA_TASK_ROOT)
#     * Minimal OS footprint optimized for Lambda execution
#     * Security patches and best practices baked in
#
# Build & Run Commands:
#   Build:  docker build -t naver-sms-automation .
#   Run:    docker run --rm -p 9000:8080 --env-file .env naver-sms-automation:latest
#   Tag:    docker tag naver-sms-automation:latest {account}.dkr.ecr.{region}.amazonaws.com/naver-sms-automation:latest
#   Push:   docker push {account}.dkr.ecr.{region}.amazonaws.com/naver-sms-automation:latest

FROM public.ecr.aws/lambda/python:3.11

# ============================================================================
# Layer 1: System dependencies
# ============================================================================
# Combine into single RUN to reduce layer count and image size
#
# Dependencies:
#   - ca-certificates: For SSL/TLS connections to APIs
#   - chromedriver: WebDriver binary for Selenium automation
#     * Installed from Amazon Linux 2 repository (chromium-chromedriver)
#     * Symlinked to /usr/local/bin for PATH discovery
#
# Chrome Browser:
#   - NOT pre-installed (saves ~300MB image size)
#   - Downloaded at runtime by webdriver-manager (Python package in requirements.txt)
#   - Fallback: Can be manually installed if needed via system packages
#
# Design Rationale:
#   - webdriver-manager handles automatic Chrome discovery/download
#   - Provides version matching between Chrome and ChromeDriver
#   - Reduces image size while maintaining compatibility
#   - Follows Lambda best practice of minimal base image
#
# yum cleanup:
#   - Remove package manager cache to save ~100MB per layer
#   - Critical for staying under 10GB image size gate

RUN yum update -y && \
    yum install -y \
    ca-certificates \
    chromium-chromedriver \
    gcc \
    python3-devel && \
    \
    # Create symlinks for compatibility
    ln -sf /usr/bin/chromedriver /usr/local/bin/chromedriver && \
    \
    # Cleanup to minimize layer size
    yum clean all && \
    rm -rf /var/cache/yum && \
    rm -rf /tmp/*

# ============================================================================
# Layer 2: Export Binary Paths for Selenium
# ============================================================================
# ChromeDriver binary location - explicitly set for Selenium
# Chrome binary - will be downloaded by webdriver-manager at first runtime
#
# webdriver-manager (Python package):
#   - Automatically discovers system Chrome if available
#   - Falls back to downloading Chrome to ~/.wdm/ if not found
#   - Provides automatic version matching
#
# Alternative approach (if pre-installed Chrome needed):
#   - Add: RUN yum install -y chromium-browser
#   - Set: ENV CHROME_BIN=/usr/bin/chromium-browser

ENV CHROMEDRIVER_BIN=/usr/bin/chromedriver

# ============================================================================
# Layer 3: Python dependencies
# ============================================================================
# Copy requirements.txt first to leverage Docker layer caching:
#   - If requirements.txt hasn't changed, this layer is reused
#   - Reduces rebuild time when only application code changes
#
# --no-cache-dir flag:
#   - Prevents pip from storing wheel cache in image
#   - Saves ~20-30MB per dependency
#   - Trade-off: Slightly slower installs, but image is smaller
#
# Key dependencies:
#   - selenium==4.15.2: Browser automation
#   - webdriver-manager==4.0.1: Automatic Chrome/ChromeDriver management
#   - boto3==1.34.0: AWS SDK for DynamoDB, Lambda context
#   - requests==2.31.0: HTTP client for APIs
#   - PyYAML==6.0.2: Configuration file parsing
#   - Other dependencies in requirements.txt

COPY requirements.txt ${LAMBDA_TASK_ROOT}/

RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

# ============================================================================
# Layer 4: Application code and configuration
# ============================================================================
# Copy project files into Lambda task root:
#   - src/: Refactored modules (auth, api, rules, notifications, etc.)
#   - config/: Runtime configuration (rules.yaml, stores.yaml, sms_templates.yaml)
#
# $LAMBDA_TASK_ROOT is set by AWS Lambda base image to /var/task
# Python PYTHONPATH automatically includes $LAMBDA_TASK_ROOT, so imports like
# 'from src.auth.naver_login import NaverAuthenticator' work without modification.

COPY src/ ${LAMBDA_TASK_ROOT}/src/
COPY config/ ${LAMBDA_TASK_ROOT}/config/

# ============================================================================
# Lambda Entrypoint
# ============================================================================
# CMD specifies the handler to invoke when Lambda invokes the function:
#   Format: [module_name, handler_function]
#   This translates to: python -m main lambda_handler
#   Which imports src/main.py and calls the lambda_handler() function
#
# Story 4.1 (Create main.py Lambda Handler) defines lambda_handler with signature:
#   def lambda_handler(event, context) -> dict
#
# Handler contract (AC 3):
#   - Accepts event (EventBridge trigger) and context (Lambda context)
#   - Returns dict with statusCode and body for Lambda response
#   - Performs full orchestration: auth, booking fetch, rule processing, notifications

CMD ["main.lambda_handler"]
