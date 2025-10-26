# Dockerfile for Naver SMS Automation Lambda Function
# Story 4.3: Build Docker Container (OPTIMIZED FOR FAST BUILDS)
# 
# Purpose:
#   Build a Lambda-compatible container image that packages the refactored
#   Naver SMS automation service with Python 3.11, Chrome/ChromeDriver,
#   and all dependencies for ECR deployment.
#
# Optimization Strategy:
#   - Multi-stage build to separate build dependencies from runtime
#   - Layer ordering optimized for cache hits (least changing → most changing)
#   - Minimal base image with only runtime dependencies
#   - BuildKit inline cache support for cross-build caching
#
# Build & Run Commands:
#   Build:  docker build -t naver-sms-automation .
#   Run:    docker run --rm -p 9000:8080 --env-file .env naver-sms-automation:latest
#   Tag:    docker tag naver-sms-automation:latest {account}.dkr.ecr.{region}.amazonaws.com/naver-sms-automation:latest
#   Push:   docker push {account}.dkr.ecr.{region}.amazonaws.com/naver-sms-automation:latest

# ============================================================================
# Stage 1: Build stage - Install Python dependencies with build tools
# ============================================================================
FROM public.ecr.aws/lambda/python:3.11 AS builder

# Install build dependencies (only needed for compilation)
RUN yum update -y && \
    yum install -y gcc python3-devel && \
    yum clean all && \
    rm -rf /var/cache/yum

# Copy only requirements.txt first for better caching
# This layer is cached unless requirements.txt changes
COPY requirements.txt /tmp/

# Install Python dependencies to /tmp/python
# Using --target to install to specific directory for easier copying
RUN pip install --no-cache-dir --target /tmp/python -r /tmp/requirements.txt

# ============================================================================
# Stage 2: Runtime stage - Minimal image with only runtime dependencies
# ============================================================================
FROM public.ecr.aws/lambda/python:3.11

# ============================================================================
# Layer 1: System runtime dependencies
# ============================================================================
# Install Chrome and ChromeDriver for Selenium automation
#
# Since Amazon Linux 2 doesn't have chromium in default repos,
# we download Chrome for Testing binaries directly from Google
#
# Chrome for Testing: Provides stable Chrome + ChromeDriver matching versions
# https://googlechromelabs.github.io/chrome-for-testing/

RUN yum update -y && \
    yum install -y \
    ca-certificates \
    wget \
    unzip \
    nss \
    atk \
    at-spi2-atk \
    at-spi2-core \
    cups-libs \
    dbus-glib \
    glib2 \
    gtk3 \
    pango \
    cairo \
    gdk-pixbuf2 \
    libdrm \
    libX11 \
    libXcomposite \
    libXcursor \
    libXdamage \
    libXext \
    libXfixes \
    libXi \
    libXrandr \
    libXrender \
    libXss \
    libXtst \
    libgbm \
    libxkbcommon \
    mesa-libEGL \
    mesa-libGL \
    alsa-lib \
    fontconfig \
    freetype \
    xorg-x11-fonts-Type1 && \
    \
    # Download Chrome for Testing (stable version compatible with ARM64)
    wget -q https://storage.googleapis.com/chrome-for-testing-public/131.0.6778.204/linux64/chrome-linux64.zip -O /tmp/chrome.zip && \
    wget -q https://storage.googleapis.com/chrome-for-testing-public/131.0.6778.204/linux64/chromedriver-linux64.zip -O /tmp/chromedriver.zip && \
    \
    # Extract Chrome
    unzip -q /tmp/chrome.zip -d /opt/ && \
    mv /opt/chrome-linux64 /opt/chrome && \
    \
    # Extract ChromeDriver
    unzip -q /tmp/chromedriver.zip -d /opt/ && \
    mv /opt/chromedriver-linux64/chromedriver /opt/chromedriver && \
    chmod +x /opt/chromedriver && \
    \
    # Create symlinks for compatibility
    ln -sf /opt/chromedriver /usr/local/bin/chromedriver && \
    \
    # Cleanup
    rm -rf /tmp/chrome.zip /tmp/chromedriver.zip /opt/chromedriver-linux64 && \
    yum clean all && \
    rm -rf /var/cache/yum

# ============================================================================
# Layer 2: Export Binary Paths for Selenium
# ============================================================================
ENV CHROME_BIN=/opt/chrome/chrome
ENV CHROMEDRIVER_BIN=/opt/chromedriver
ENV LD_LIBRARY_PATH=/opt/chrome:${LD_LIBRARY_PATH}

# ============================================================================
# Layer 3: Copy Python dependencies from builder stage
# ============================================================================
# Copy pre-compiled dependencies from builder stage
# This avoids reinstalling dependencies if they haven't changed
COPY --from=builder /tmp/python ${LAMBDA_TASK_ROOT}

# ============================================================================
# Layer 4: Application code and configuration
# ============================================================================
# Copy project files into Lambda task root
# These are copied LAST because they change most frequently
# This maximizes cache hit rate for previous layers
#
# $LAMBDA_TASK_ROOT is set by AWS Lambda base image to /var/task

COPY src/ ${LAMBDA_TASK_ROOT}/src/
COPY config/ ${LAMBDA_TASK_ROOT}/config/

# ============================================================================
# Lambda Entrypoint
# ============================================================================
# CMD specifies the handler to invoke when Lambda invokes the function:
#   Format: [module_path.handler_function]
#   This translates to: import src.main; call src.main.lambda_handler(event, context)
#
# Handler contract:
#   - Accepts event (EventBridge trigger) and context (Lambda context)
#   - Returns dict with statusCode and body for Lambda response
#
# Handler Path:
#   - src.main.lambda_handler: Module is at src/, function is lambda_handler

CMD ["src.main.lambda_handler"]
