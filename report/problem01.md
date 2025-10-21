✦ 보고서: 옵션 키워드 감지 시스템 분석

  1. 시스템 개요
  네이버 예약 자동화 시스템은 예약 정보에서 특정 옵션 키워드(예: "네이버", "인스타", "원본")를 감지하여 알림을 발송하는 시스템입니다. 현재 시스템은 "전문가 보정" 키워드도 감지해야 하지만, 관련 설정이 누락되어
  있습니다.

  2. 문제 분석
  2.1. 관련 파일 구조
   - src/api/naver_booking.py: 네이버 예약 API 클라이언트
     - NaverBookingAPIClient 클래스가 예약 정보를 가져와 도메인 모델로 변환
     - option_keywords 파라미터로 감지할 키워드를 지정 (기본값: ["네이버", "인스타", "원본"])

   - src/domain/booking.py: 예약 도메인 모델
     - Booking 클래스는 예약 정보를 담는 데이터 클래스
     - option_keywords 필드는 포함되어 있지 않음

   - src/rules/conditions.py: 조건 평가 로직
     - has_option_keyword 함수가 키워드 감지를 수행
     - booking의 option_keywords 속성을 참조하여 키워드를 검색

   - src/main.py: 메인 Lambda 핸들러
     - 예약 정보 처리 및 규칙 엔진 실행
     - option_keywords에 대한 초기 설정 포함

  2.2. 데이터 흐름
   1. NaverBookingAPIClient가 네이버 API에서 예약 정보를 가져옴
   2. 예약 정보를 Booking 도메인 모델로 변환
   3. has_option_keyword 조건 평가기에서 booking.option_keywords 속성을 참조
   4. 설정된 키워드 목록과 비교하여 일치하는지 확인

  2.3. 문제점
   - 옵션 키워드를 감지하는 구조가 다른 것이 핵심 문제입니다. 도메인 모델에 option_keywords 속성이 없고, 예약 옵션 정보를 처리하는 방식이 일관되지 않아 "전문가 보정"을 포함한 키워드 감지가 불가능합니다.
   - NaverBookingAPIClient에서 "전문가 보정" 키워드가 포함되지 않도록 설정되어 있음
   - 규칙 파일(config/rules.yaml)에서 "전문가 보정"을 위한 조건 설정이 필요함

  3. 해결 방안
  3.1. 도메인 모델 개선
  src/domain/booking.py의 Booking 클래스에 option_keywords 속성을 추가해야 합니다.

  3.2. API 클라이언트 수정
  src/api/naver_booking.py의 NaverBookingAPIClient 초기화 시, "전문가 보정" 키워드를 포함한 리스트로 option_keywords를 설정해야 합니다.

  3.3. 규칙 설정 업데이트
  config/rules.yaml에 "전문가 보정" 키워드를 감지하는 규칙을 추가해야 합니다.

  4. 결론
  현재 시스템은 옵션 키워드를 감지하는 구조가 일관되지 않으며, "전문가 보정" 키워드를 감지할 수 있는 기능이 누락되어 있습니다. 시스템이 제대로 작동하려면 위에서 언급한 사항들을 수정해야 합니다.