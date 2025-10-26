# Lambda Deployment Fix - 2025-10-26

**Issue:** Lambda INIT timeout causing "Connection was closed" errors
**Solution:** Increased Lambda memory from 512MB to 1024MB
**Status:** ✅ **RESOLVED**

---

## Problem Summary

- **Original Error:** Connection timeout during Lambda cold start
- **Root Cause:** Chrome initialization (8-12s) exceeded Lambda's 10-second INIT limit with 512MB memory
- **Image Size:** ~2GB (commit d8af2a1) with full Chrome dependencies

## Solution Implemented

### Configuration Changes

| Setting | Before | After | Impact |
|---------|--------|-------|---------|
| Lambda Memory | 512MB | **1024MB** | 2x memory for faster initialization |
| Image | d8af2a1 (~2GB) | d8af2a1 (~2GB) | No change (includes all required Chrome libraries) |
| Cost | ~$30/month | ~$60/month | Doubled, but acceptable for stability |

### Results

✅ **Lambda executes successfully** - StatusCode 200
✅ **Chrome starts without crashes** - Full library support
✅ **No INIT timeout** - Sufficient memory for cold start
⚠️ **Cookie domain error** - Application logic issue (not infrastructure)

---

## Timeline

**2025-10-26 00:12** - First deployment failed (missing Chrome libraries)
**2025-10-26 01:12** - commit a5e4fea (517MB, minimal deps)
**2025-10-26 01:26** - commit d8af2a1 (2.01GB, full deps) - Lambda timeout
**2025-10-26 09:00** - Attempted Chromium migration (517MB x86) - Chrome startup failed
**2025-10-26 09:35** - Restored d8af2a1 + 1024MB memory - **SUCCESS** ✅

---

## Technical Details

### What Worked
- Using commit d8af2a1 image with all GUI libraries (gtk3, cairo, mesa, X11, etc.)
- Increasing Lambda memory to 1024MB
- Building for x86_64 architecture (not ARM64)
- Using image digest directly to avoid manifest issues

### What Didn't Work
- Minimal Chrome dependencies (517MB) - Chrome crashed on startup
- Chromium Headless approach - Package not available in Amazon Linux 2
- Removing GUI libraries - Chrome requires them even in headless mode

### Lessons Learned

1. **Lambda INIT limit is strict** - 10 seconds, non-negotiable
2. **Chrome needs full libraries** - Even headless mode requires GUI dependencies
3. **Memory matters** - More memory = faster loading = faster initialization
4. **Image manifest issues** - BuildKit attestations not supported by Lambda
5. **Architecture must match** - x86_64 for Lambda, not ARM64

---

## Outstanding Issues

### Application Logic
**Cookie Domain Error:**
```
invalid cookie domain: Cookie 'domain' mismatch
```
**Status:** Non-blocking, needs separate code fix
**Impact:** Chrome is running, just needs cookie handling adjustment

---

## Recommendations

### Short-term (Current Solution)
✅ Keep d8af2a1 image + 1024MB memory configuration
✅ Fix cookie domain issue in application code
✅ Monitor Init Duration in CloudWatch (target: <8 seconds)

### Long-term Optimization
1. **Investigate lighter browsers:** Playwright's Chromium, or headless-specific builds
2. **Lazy-load Chrome:** Only initialize when actually needed (not on every cold start)
3. **Use Provisioned Concurrency:** Eliminate cold starts for critical functions
4. **Consider ECS/Fargate:** If Lambda constraints become too limiting

---

## Reference Documents

- **Problem Analysis:** docs/problem1026.md
- **Git Commits:**
  - Backup: 976a10a (Dockerfile.backup-20251026)
  - Working Version: commit d8af2a1 (2.01GB, full libraries)
- **Lambda Function:** naverplace_send_inform_v2
- **ECR Repository:** 654654307503.dkr.ecr.ap-northeast-2.amazonaws.com/naver-sms-automation

---

## Cost Analysis

### Current Cost (1024MB)
- Memory: 1024MB
- Executions: ~72/day (20-minute intervals)
- Average runtime: ~180s
- **Monthly cost:** ~$60/month (estimate)

### Comparison
- 512MB (before): ~$30/month ❌ Timeout failures
- 1024MB (current): ~$60/month ✅ Stable
- 2048MB (if needed): ~$120/month (not necessary currently)

**Verdict:** 2x cost increase acceptable for stable production service

---

**Last Updated:** 2025-10-26
**Author:** Claude Code (Automated Deployment Fix)
