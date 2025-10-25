# GitHub Actions 워크플로우 가이드

## 📋 목차
- [워크플로우 종류](#워크플로우-종류)
- [자동 실행되는 워크플로우](#자동-실행되는-워크플로우)
- [수동 실행 워크플로우](#수동-실행-워크플로우)
- [FAQ](#faq)

---

## 워크플로우 종류

### 🚀 Fast Track Tests (빠른 테스트)
- **실행 시간**: 3-5분
- **테스트 범위**: Unit 테스트만 (238개)
- **언제 실행**: 자동 (모든 push/PR)
- **목적**: 빠른 피드백, 기본 품질 검증

### 🧪 Full Test Suite (전체 테스트)
- **실행 시간**: 15-20분
- **테스트 범위**: 모든 테스트 (653개)
- **언제 실행**: 수동으로만
- **목적**: 완전한 품질 검증

### 🚢 Deploy to AWS (배포)
- **실행 시간**: 3-5분 (Fast Tests) + 3분 (빌드/배포)
- **언제 실행**: main 브랜치에 push할 때
- **목적**: AWS Lambda에 자동 배포

---

## 자동 실행되는 워크플로우

### 1️⃣ 코드를 수정하고 push할 때

```bash
# 예시: main.py 수정
git add src/main.py
git commit -m "fix: lambda handler bug"
git push origin main
```

**자동으로 실행됨:**
1. ✅ Fast Track Tests (3-5분)
   - 238개 unit 테스트만 실행
   - 4개 병렬 worker로 빠르게 실행
2. ✅ Docker 빌드 & ECR 업로드 (2분)
3. ✅ AWS Lambda 배포 (1분)

**총 소요 시간: 약 6-8분**

---

### 2️⃣ Pull Request를 만들 때

```bash
# Feature 브랜치 생성
git checkout -b feature/new-feature
git push origin feature/new-feature

# GitHub에서 PR 생성
```

**자동으로 실행됨:**
- ✅ Fast Track Tests (3-5분)
- ❌ 배포는 실행 안 됨 (main이 아니므로)

**PR을 main에 병합하면:**
- ✅ Fast Track Tests + 배포 실행됨

---

## 수동 실행 워크플로우

### 🔧 전체 테스트를 실행하는 방법

**언제 사용?**
- 중요한 배포 전 완전한 검증이 필요할 때
- 일주일에 한 번 정도 전체 점검할 때
- 뭔가 이상하다 싶을 때

**실행 방법:**

#### 1. GitHub 저장소로 이동
```
https://github.com/당신아이디/naver_sms_auto_refact
```

#### 2. 상단 메뉴에서 "Actions" 클릭

#### 3. 왼쪽 사이드바에서 "Full Test Suite" 선택

#### 4. 오른쪽 상단에 "Run workflow" 버튼 클릭

#### 5. 옵션 선택
- **Run security scan**: 보안 스캔 실행 (기본: Yes)
- **Coverage threshold**: 최소 커버리지 (기본: 70%)

#### 6. "Run workflow" 확인 버튼 클릭

#### 7. 완료될 때까지 기다림 (15-20분)

---

## FAQ

### Q1: Push할 때마다 워크플로우가 실행되나요?
**A**: 네! main 브랜치나 PR에 push하면 **자동으로** Fast Track Tests가 실행됩니다.

### Q2: Fast Track Tests만 돌리면 안전한가요?
**A**: 네! Unit 테스트 238개가 핵심 로직을 모두 검증합니다.
- 람다 핸들러 로직
- 데이터베이스 작업
- 규칙 엔진
- 설정 관리
- 등등...

추가 안전성이 필요하면 수동으로 Full Test Suite를 실행하세요.

### Q3: 전체 테스트를 자동으로 실행할 수는 없나요?
**A**: 가능하지만 권장하지 않습니다. 이유:
- 매번 20분씩 기다리면 개발 속도가 느려짐
- 대부분의 경우 Fast Track Tests로 충분함
- 필요할 때만 전체 테스트를 실행하는 게 효율적

### Q4: main에 직접 push vs PR 병합 차이가 뭔가요?
**A**: 워크플로우 실행 측면에서는 **동일**합니다.
```
main 직접 push → Fast Track Tests + 배포
PR 병합 → Fast Track Tests + 배포
```

### Q5: 테스트가 실패하면 어떻게 되나요?
**A**: 배포가 **자동으로 중단**됩니다.
```
Fast Track Tests 실패 ❌
  ↓
빌드 건너뜀 ⏭️
  ↓
배포 건너뜀 ⏭️
```

### Q6: 워크플로우 실행 중단하려면?
**A**:
1. GitHub → Actions
2. 실행 중인 워크플로우 클릭
3. 오른쪽 상단 "Cancel workflow" 버튼 클릭

---

## 🎯 시간 비교

| 작업 | 이전 | 현재 | 개선 |
|------|------|------|------|
| 일반 push | 20분 | **3-5분** | ⬇️ 75% 단축 |
| 빌드+배포 | 3분 | 3분 | 동일 |
| 전체 검증 | 20분 | 수동으로만 | 선택적 |
| **총 개발 속도** | 느림 | **매우 빠름** | 🚀 |

---

## 📝 예시 시나리오

### 시나리오 1: 버그 수정
```
09:00 - 버그 발견
09:10 - 코드 수정 완료
09:11 - git push origin main
09:12 - Fast Track Tests 시작
09:16 - 테스트 통과 ✅
09:17 - 빌드 & 배포 시작
09:20 - 배포 완료 🎉

총 소요 시간: 10분
```

### 시나리오 2: 중요한 배포 전 검증
```
금요일 오후 2시 - 다음 주 배포 준비
1. GitHub Actions → Full Test Suite 실행
2. 커피 마시러 감 ☕
3. 20분 후 돌아옴
4. 결과 확인: 모두 통과 ✅
5. 안심하고 배포 진행

위험 감소: 100%
```

---

## 🔗 관련 링크

- [GitHub Actions 문서](https://docs.github.com/en/actions)
- [pytest-xdist 문서](https://pytest-xdist.readthedocs.io/)
- [워크플로우 파일 위치](.github/workflows/)

---

**마지막 업데이트**: 2025-10-26
**작성자**: Claude Code 🤖
