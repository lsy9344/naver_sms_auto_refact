chromedriver/python3.7/arn:aws:lambda:ap-northeast-2:654654307503:layer:chromedriver:2


selenium/python3.7/arn:aws:lambda:ap-northeast-2:654654307503:layer:selenium:1



General configuration
Description
네이버플레이스 크롤링->안내문자 전송 (네이버 클라우드 api 연결)
Memory
512MB
Ephemeral storage
512MB
Timeout
5min0sec
SnapStart
Info
None


AWS - lambda alarm
"The python3.7 runtime is no longer supported. We recommend that you migrate your functions that use python3.7 to a newer runtime as soon as possible"


Trigger : eventbridge 20minute



람다 함수 이름 : naverplace_send_inform_v2

  - AWS_ACCESS_KEY_ID: [REDACTED - Use environment variables]
  - AWS_SECRET_ACCESS_KEY: [REDACTED - Use environment variables]
  - AWS_SESSION_TOKEN: (사용 안함)
  - 리전: ap-northeast-2 (서울)
  - 계정 ID: 654654307503