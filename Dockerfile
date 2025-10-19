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
# Layer 1: System dependencies (ChromeDriver, Chrome, and build tools)
# ============================================================================
# Combine into single RUN to reduce layer count and image size
#
# Chrome installation via Google's official repository:
#   - Stable release channel for Google Chrome
#   - Automatically updated with security patches
#   - Installed to /usr/bin/google-chrome for system-wide discovery
#
# ChromeDriver installation:
#   - Installed from Amazon Linux 2 repository (chromium-chromedriver)
#   - Matches Chrome major version for compatibility
#   - Installed to /usr/bin/chromedriver
#
# webdriver-manager:
#   - Python package to automatically download/manage matching Chrome/ChromeDriver
#   - Installed as part of requirements.txt for dynamic discovery
#   - Fallback if system binaries not available
#
# yum cleanup:
#   - Remove package manager cache to save ~100MB per layer
#   - Critical for staying under 10GB image size gate

RUN yum update -y && \
    yum install -y \
    wget \
    unzip \
    ca-certificates && \
    \
    # Install Google Chrome stable (x86_64 for Lambda)
    cd /tmp && \
    wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm && \
    yum install -y ./google-chrome-stable_current_x86_64.rpm && \
    rm -f ./google-chrome-stable_current_x86_64.rpm && \
    \
    # Install ChromeDriver from Amazon Linux repository
    yum install -y chromium-chromedriver && \
    \
    # Create symlinks for ease of discovery
    ln -sf /usr/bin/chromium-browser /usr/bin/google-chrome || true && \
    ln -sf /usr/bin/chromedriver /usr/local/bin/chromedriver && \
    \
    # Cleanup to minimize layer size
    yum clean all && \
    rm -rf /var/cache/yum && \
    rm -rf /tmp/*

# ============================================================================
# Layer 2: Export Chrome/ChromeDriver paths for Selenium
# ============================================================================
# These environment variables allow Selenium to discover and use the
# installed Chrome and ChromeDriver binaries without requiring PATH
# modifications or hardcoded binary paths in code.
#
# Naver login implementation (src/auth/naver_login.py) expects:
#   - CHROME_BIN: Path to Chrome executable
#   - CHROMEDRIVER_BIN: Path to ChromeDriver executable
#
# Fallback paths for webdriver-manager if system binaries not used:
#   - These can be overridden by webdriver-manager cache at runtime

ENV CHROME_BIN=/usr/bin/google-chrome
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
# webdriver-manager included in requirements.txt:
#   - Automatically detects Chrome version at runtime
#   - Downloads matching ChromeDriver if needed
#   - Provides fallback binary discovery for compatibility

COPY requirements.txt ${LAMBDA_TASK_ROOT}/

RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

# ============================================================================
# Layer 4: Application code and configuration
# ============================================================================
# Copy project files into Lambda task root:
#   - src/: Refactored modules (auth, api, rules, notifications, etc.)
#   - config/: Runtime configuration (rules.yaml, stores.yaml, sms_templates.yaml)
#   - bin/: Any utility scripts
#
# $LAMBDA_TASK_ROOT is set by AWS Lambda base image to:
#   /var/task (on Lambda) or /var/task (in RIE emulator)
#
# Python PYTHONPATH automatically includes $LAMBDA_TASK_ROOT, so imports like
# 'from src.auth.naver_login import NaverAuthenticator' work without modification.

COPY src/ ${LAMBDA_TASK_ROOT}/src/
COPY config/ ${LAMBDA_TASK_ROOT}/config/

# Optional: Copy utility scripts if needed
# COPY bin/ ${LAMBDA_TASK_ROOT}/bin/

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
