import base64
import hashlib
import hmac
import json
import logging
import os
import time
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)

_DEFAULT_FROM_NUMBER = "01055814318"
_DEFAULT_FROM_MAP: Dict[str, str] = {
    "1466783": "01055811814",
    "1051707": "01055814318",
    "951291": "01055814318",
    "1462519": "01055814318",
    "1120125": "01055814318",
    "1285716": "01055814318",
    "1473826": "01055814318",
    "867589": "01022392673", # 초지점
}


def _normalize_map(source: Dict) -> Dict[str, str]:
    normalized: Dict[str, str] = {}
    for key, value in source.items():
        key_str = str(key).strip()
        value_str = str(value).strip()
        if key_str and value_str:
            normalized[key_str] = value_str
    return normalized


def _load_from_map() -> Dict[str, str]:
    raw = os.getenv("SENS_FROM_MAP_JSON")
    if not raw:
        return _normalize_map(_DEFAULT_FROM_MAP)
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError as err:
        logger.warning("Failed to decode SENS_FROM_MAP_JSON: %s", err)
        return _normalize_map(_DEFAULT_FROM_MAP)

    if isinstance(loaded, dict):
        normalized = _normalize_map(loaded)
        if normalized:
            return normalized
        logger.warning("SENS_FROM_MAP_JSON normalized to empty map; using defaults")
        return _normalize_map(_DEFAULT_FROM_MAP)

    logger.warning("SENS_FROM_MAP_JSON is not a dict; using defaults")
    return _normalize_map(_DEFAULT_FROM_MAP)


class Sens_sms():
    def __init__(self) -> None:
        timestamp = int(time.time() * 1000)
        self.timestamp = str(timestamp)

        self.access_key = "tpAFhfAWvpLqS5ve35Zw"			# access key id (from portal or Sub Account)
        self.secret_key = "YrAgDCC20hiItoFrzrolbStsIwzyEWBFi4szm1Vh"			# secret key (from portal or Sub Account)

        self.url = "https://sens.apigw.ntruss.com"
        self.uri = "/sms/v2/services/ncp:sms:kr:324182048243:dabistudio/messages"

        self.header = {
        "Content-Type" : "application/json; charset=utf-8",
        "x-ncp-apigw-timestamp" : self.timestamp,
        "x-ncp-iam-access-key" : self.access_key,
        "x-ncp-apigw-signature-v2" : self.make_signature()
    }

        self.from_map = _load_from_map()
        self.default_from = os.getenv("SENS_DEFAULT_FROM", _DEFAULT_FROM_NUMBER)

    def	make_signature(self):
        secret_key_bytes = bytes(self.secret_key, 'UTF-8')
        method = "POST"
        message = method + " " + self.uri + "\n" + self.timestamp + "\n" + self.access_key
        message = bytes(message, 'UTF-8')
        signingKey = base64.b64encode(hmac.new(secret_key_bytes, message, digestmod=hashlib.sha256).digest())
        return signingKey

    def get_from_number(self, store_id: Optional[str] = None) -> str:
        if store_id:
            key = str(store_id).strip()
            if key:
                from_number = self.from_map.get(key)
                if from_number:
                    return from_number
        return self.default_from

    
    def send_confirm_sms(self, phone: str, store_id: Optional[str] = None):
        if not phone:
            raise ValueError("phone is required")
        phone_num = phone.strip().replace("-", "")
        from_number = self.get_from_number(store_id)
        masked_phone = phone_num[-4:] if len(phone_num) >= 4 else phone_num
        logger.info(
            "Sending confirm SMS store_id=%s from=%s to=***%s",
            store_id,
            from_number,
            masked_phone,
        )
        booking_confirm_template = """다비스튜디오를 찾아주신 고객님, 안녕하세요
예약 확정되어 이용 안내 드립니다.

비밀번호 입력 후 입장하셔서 커튼 안쪽의 "촬영실"로 들어가셔서 책상 위의 메뉴얼을 따라만 하시면 너무 쉬워요,
문 열고 들어오시면 전 타임 손님들이 셀렉실 사용 중일 수도 있어요.
바로 '촬영실'로 들어가시면 된답니다!

*풍선 및 테이프 사용 시 "겔 타입"의 테이프만 사용 가능합니다,
겔 타입이 아니면 벽 및 배경지가 훼손되니 주의 부탁드립니다.

정시 입실, 퇴실 꼭 지켜주셔야 다음 예약 손님에게 피해가 가지 않습니다!

[제공서비스]
-이용시간 구성:
촬영 50분 10분 내보내기 후
셀렉실로 이동하여 50분 셀렉 및 인화
(내가 촬영할 때 셀렉실에서 전 타임 셀렉)
(평일 1시간 더 쿠폰 사용하신 분은
기본 촬영 시간에 50분 추가돼요!)

-사진인화 4장 (비닐백 포함)
-모든 원본파일 무료 제공
-2,4,6,9컷 무료 편집
-사진 레터링 무료 제공
-지점에 따라 배경지 무료 제공

2,4,9컷 및 레터링은 아래 링크에서도 휴대폰으로 편집이 가능해요~
집 소파, 침대에 누워 편하게 작업하세요 :)
https://dabistudio.vercel.app

이용시간 2시간전에 도어락 비밀번호, 주차관련, 이용 상세 정보 문자메시지가 발송 됩니다!
"""

        data = {
            "type":"LMS",
            "contentType":"COMM",
            "from": from_number,
            "subject":"다비스튜디오 안내",
            "content": booking_confirm_template,
            "messages":[
                {
                    "to": phone_num,
                }
            ]
        }

        res = requests.post(self.url + self.uri, headers=self.header, data=json.dumps(data))
        logger.debug("SENS response: %s", res.text)



    def send_guide_sms(self, store_id: Optional[str] = None, phone: Optional[str] = None):
        if not phone:
            raise ValueError("phone is required")
        phone_num = phone.strip().replace("-", "")
        from_number = self.get_from_number(store_id)
        masked_phone = phone_num[-4:] if len(phone_num) >= 4 else phone_num
        logger.info(
            "Sending guide SMS store_id=%s from=%s to=***%s",
            store_id,
            from_number,
            masked_phone,
        )
        booking_guide_template_1051707 = """다비스튜디오를 찾아주신 고객님, 안녕하세요
이용 상세 안내 드립니다.

-도어락 비밀번호 : 5282*

-와이파이 ID : SK_WIFIGIGA6C48_2.4G

-와이파이 비밀번호 : GIH4B@7451

-오시는 길 :
경기도 화성시 수노을중앙로 130, 1동 5층 510호
(스타벅스 바로 옆 "다이소 건물" 5층이 다비스튜디오 입니다!)

-주차 : 다이소 건물 지하주차장 이용
평일 3시간, 주말 2시간 무료 제공
셀렉실에서 PC로 주차 정산
지하주차장 만차 시 "수노을중앙공원 공영주차장"(2시간 무료) 이용 바랍니다. 도보 2분 거리

-예습 매뉴얼 :
https://blog.naver.com/dabi-/223902385799

-배경지 설치치 동영상 :
http://pf.kakao.com/_EwvUxj/104914467

비밀번호 입력 후 입장하셔서 커튼 안쪽의 "촬영실"로 들어가셔서 책상 위의 메뉴얼을 따라만 하시면 너무 쉬워요 :)

[제공서비스]
-이용시간 구성:
촬영 50분 10분 내보내기 후
셀렉실로 이동하여 50분 셀렉 및 인화
(내가 촬영할 때 셀렉실에서 전 타임 셀렉)
(평일 1시간 더 쿠폰 사용하신 분은
기본 촬영 시간에 50분 추가돼요!)

-프리미엄 인화지 4장
-모든 원본파일 무료 제공
-사진 레터링 무료 제공
-3색 배경지 무료 이벤트

이용하시다가 문의사항 있다면 연락 부탁 드릴께요! :)
"""
        
        booking_guide_template_951291 ="""다비스튜디오를 찾아주신 고객님, 안녕하세요
이용 상세 안내 드립니다.

-도어락 비밀번호 : 5581*

-와이파이 ID : U+NetFE24_5G

-와이파이 비밀번호 : 5FDB7P@251

-오시는 길 :
경기도 안산시 단원구 당곡로 9 진양빌딩, 203호 (파란색 문을 찾으세요!)
("전주식 콩나물 국밥집" 2층이 다비스튜디오 입니다!)

-주차 : 건물 바로 뒤, 옆에 시간당 1,200원인 주차 대수가 많은 공영주차장이 2개 있어요!
번화가의 공영주차장은 협소한 경우도 있으니 30분 전 미리 도착하시면 편하실 거예요 :)

-예습 매뉴얼 :
https://blog.naver.com/dabi-/223902385799

-배경지 설치 동영상 :
http://pf.kakao.com/_EwvUxj/104973470

비밀번호 입력 후 입장하셔서 커튼 안쪽의 "촬영실"로 들어가셔서 책상 위의 메뉴얼을 따라만 하시면 너무 쉬워요 :)

[제공서비스]
-이용시간 구성:촬영실 50분/셀렉실 이동 후 50분 (시간 조정 불가)
(내가 촬영할 때 셀렉실에서 전 타임 셀렉)
  ㄴ 이벤트 쿠폰 사용 고객님은 촬영실 100분 이용입니다 :)
-프리미엄 인화지 4장
-모든 원본파일 무료 제공
-사진 레터링 무료 제공
-3색 배경지 무료 이벤트

이용하시다가 문의사항 있다면 연락 부탁 드릴께요!
        """

        booking_guide_template_867589 = """다비스튜디오를 찾아주신 고객님, 안녕하세요
이용 상세 안내 드립니다.

-도어락 비밀번호 : 5282* (화장실 동일)

-와이파이 ID : U+Net0C58_5G

-와이파이 비밀번호 : #7K7046ABF

-오시는 길 :
경기도 안산시 단원구 광덕3로 41, 3층 다비스튜디오
('하나로차사랑' 쌩노란색 간판이 독보적으로 보이는 건물이에요!)

-주차 : 건물 뒷편, 뒷편의 옆 코다리 건물, 그 옆 CU건물, 대로변 앞은 오전8시 이전, 11-2시, 오후 6시 이후만 단속 없습니다.

-예습 매뉴얼 :
http://pf.kakao.com/_EwvUxj/104666553

비밀번호 입력 후 입장하셔서 커튼 안쪽의 "촬영실"로 들어가셔서 책상 위의 메뉴얼을 따라만 하시면 너무 쉬워요 :)

[제공서비스]
-이용시간 구성:촬영실 50분/셀렉실 이동 후 50분 (시간 조정 불가)
  ㄴ 이벤트 쿠폰 사용 고객님은 촬영실 100분 이용입니다 :)
-프리미엄 인화지 4장 
-모든 원본파일 무료 제공
-사진 레터링 무료 제공

이용하시다가 문의사항 있다면 연락 부탁 드릴께요!
        """
        
        booking_guide_template_1120125 = """
        다비스튜디오를 찾아주신 고객님, 안녕하세요
이용 상세 안내 드립니다.

-도어락 비밀번호 : 5282*
-와이파이 ID : KT_GiGA_A42B
-와이파이 비밀번호 : 8fhcdgb752

-오시는 길 :
경기도 수원시 권선구 금곡로 201, 로얄팰리스 1차 2층 215호
엘레베이터 내리셔서 오른쪽 문으로 나가시면 "다비스튜디오" 간판이 보입니다.

-주차 : 건물 지하 1,2,3층 주차장 이용 가능합니다. 만약 만차 시 건물 주차장 출입구 근처 이면주차 가능합니다. 주차는 2시간 무료 지원됩니다.
주차 정산 방법: 셀렉실 PC에서 차량번호 입력.

입주자전용, 상가전용 엘레베이터 있지만 모두 사용하셔도 무방합니다.
-엘레베이터 비밀번호 : #1234#

비밀번호 입력 후 입장하셔서 커튼 안쪽의 "촬영실"로 들어가셔서 책상 위의 메뉴얼을 따라만 하시면 너무 쉬워요 :)

⬇이용 매뉴얼 미리보기⬇
https://blog.naver.com/dabi-/223902385799

⬇배경지 설치 동영상 미리보기
http://pf.kakao.com/_EwvUxj/108482706

[제공서비스]
-이용시간 구성:촬영실 50분/셀렉실 이동 후 50분 (시간 조정 불가)
(내가 촬영할 때 셀렉실에서 전 타임 셀렉)
  ㄴ 이벤트 쿠폰 사용 고객님은 촬영실 100분 이용입니다 :)
-프리미엄 인화지 4장
-모든 원본파일 무료 제공
-3색 배경지 무료 이벤트
-사진레터링 무료

이용하시다가 문의사항 있다면 연락 부탁 드릴께요!
        """
        booking_guide_template_1285716 = """
        안녕하세요! 고객님~

다비스튜디오 동탄점을 찾아주셔서 감사합니다 :)
금일 이용 상세 안내 드립니다.

정시 입실/퇴실 꼭 지켜주셔야 하며,
이용시간 준수하지 않음으로 인한 불이익은 책임지지 않습니다.

⬇이용 매뉴얼 미리보기⬇
https://blog.naver.com/dabi-/223902385799

⬇배경지 설치 동영상 미리보기
http://pf.kakao.com/_EwvUxj/108482706

-도어락 비밀번호 : 3756*
-오시는 길 :
경기도 화성시 동탄대로 636-1번지 센테라 IT 타워 2차, 704호.   (1층 농협 건물이에요!)
-주차 : 건물 주차장 이용, 평일 3시간 주말 2시간 무료 지원
추가 주차비는 10분당 500원 입니다!

주차 정산 방법: 셀렉실 PC에서 차량번호 입력.

비밀번호 입력 후 입장하셔서 커튼 안쪽의 "촬영실"로 들어가셔서 책상 위의 메뉴얼을 따라만 하시면 너무 쉬워요 :)

[제공서비스]
이용 시간 구성:
촬영 50분 10분 내보내기 후
셀렉실로 이동하여 50분 셀렉 및 인화
(내가 촬영할 때 셀렉실에서 전 타임 셀렉)

(평일 1시간 더 쿠폰 사용하신 분은
기본 촬영 시간에 50분 추가돼요!)

-프리미엄 인화지 4장
-모든 원본파일 무료 제공
-2색 배경지 무료 이벤트
-레터링 무료
-2컷,4컷,6컷,9컷 무료 편집

이용하시다가 문의사항 있다면 연락 부탁 드릴께요!
        """
        booking_guide_template_1462519 = """
        안녕하세요! 고객님~

다비스튜디오 인천검단점을 찾아주셔서 감사합니다 :)
금일 이용 상세 안내 드립니다.

정시 입실/퇴실 꼭 지켜주셔야 하며,
이용시간 준수하지 않음으로 인한 불이익은 책임지지 않습니다.

⬇이용 매뉴얼 미리보기⬇
https://blog.naver.com/dabi-/223902385799

⬇배경지 설치 동영상 미리보기
http://pf.kakao.com/_EwvUxj/108482706

-도어락 비밀번호 : 열려있어요!
-오시는 길 :
인천광역시 서구 이름4로 6, KR법조타워 1, 1024호.  (1층 메가커피 건물이에요!)
-주차 : 건물 주차장 이용, 평일 3시간 주말 2시간 무료 지원
추가 주차비는 10분당 1,000원 입니다!

주차 정산 방법: 셀렉실 PC에서 차량번호 입력.

비밀번호 입력 후 입장하셔서 커튼 안쪽의 "촬영실"로 들어가셔서 책상 위의 메뉴얼을 따라만 하시면 너무 쉬워요 :)

[제공서비스]
이용 시간 구성:
촬영 50분 10분 내보내기 후
셀렉실로 이동하여 50분 셀렉 및 인화
(내가 촬영할 때 셀렉실에서 전 타임 셀렉)

(평일 1시간 더 쿠폰 사용하신 분은
기본 촬영 시간에 50분 추가돼요!)

-프리미엄 인화지 4장
-모든 원본파일 무료 제공
-2색 배경지 무료 이벤트
-레터링 무료
-2컷,4컷,6컷,9컷 무료 편집

이용하시다가 문의사항 있다면 연락 부탁 드릴께요!
        """
        booking_guide_template_1473826 = """
        안녕하세요! 고객님~

다비스튜디오 부천점을 찾아주셔서 감사합니다 :)
금일 이용 상세 안내 드립니다.

정시 입실/퇴실 꼭 지켜주셔야 하며,
이용시간 준수하지 않음으로 인한 불이익은 책임지지 않습니다.

⬇이용 매뉴얼 미리보기⬇
https://blog.naver.com/dabi-/223902385799

⬇배경지 설치 동영상 미리보기
http://pf.kakao.com/_EwvUxj/108482706

-도어락 비밀번호 : 5858*
-오시는 길 :
경기도 부천시 원미구 춘의동 73-1 (디아크원), 508호.  (1층 컴포즈커피 건물이에요!)
-주차 : 건물 지하, 지상주차장 이용, (5층 주차 추천)
주차비는 평일 3시간 주말 2시간 무료 지원
추가 주차비는 10분당 1,000원 입니다!

주차 정산 방법: 셀렉실 PC에서 차량번호 입력.

비밀번호 입력 후 입장하셔서 커튼 안쪽의 "촬영실"로 들어가셔서 책상 위의 메뉴얼을 따라만 하시면 너무 쉬워요 :)

[제공서비스]
이용 시간 구성:
촬영 50분 10분 내보내기 후
셀렉실로 이동하여 50분 셀렉 및 인화
(내가 촬영할 때 셀렉실에서 전 타임 셀렉)

(평일 1시간 더 쿠폰 사용하신 분은
기본 촬영 시간에 50분 추가돼요!)

-프리미엄 인화지 4장
-모든 원본파일 무료 제공
-2색 배경지 무료 이벤트
-레터링 무료
-2컷,4컷,6컷,9컷 무료 편집

이용하시다가 문의사항 있다면 연락 부탁 드릴께요!
        """
        booking_guide_template_1466783 = """
        안녕하세요! 고객님~

다비스튜디오 평택 고덕점을 찾아주셔서 감사합니다 :)
금일 이용 상세 안내 드립니다.

정시 입실/퇴실 꼭 지켜주셔야 하며,
이용시간 준수하지 않음으로 인한 불이익은 책임지지 않습니다.

-도어락 비밀번호 : 5805*
-오시는 길 :
경기도 평택시 고덕국제대로77 301동 3218호 (아파트 아니라 상가입니다)
-주차 : 건물 주차장 이용, 주차비 무료

**** 건물 특성상 길 찾기가 매우 어려우니
아래 블로그 꼭 읽어주세요 ****
 
https://blog.naver.com/dabi-/223967105578

⬇이용 매뉴얼 미리보기⬇
https://blog.naver.com/dabi-/223902385799

⬇배경지 설치 동영상 미리보기
http://pf.kakao.com/_EwvUxj/108482706

입장 후 커튼 안쪽의 "촬영실" 들어가셔서 책상 위에 있는 "셀프사진관 메뉴얼"을 꼭 정독 해주세요!
보고 따라만 하시면 너무 쉽습니다!

[제공서비스]
이용 시간 구성:
촬영 50분 10분 내보내기 후
셀렉실로 이동하여 50분 셀렉 및 인화
(내가 촬영할 때 셀렉실에서 전 타임 셀렉)

(평일 1시간 더 쿠폰 사용하신 분은
기본 촬영 시간에 50분 추가돼요!)

-프리미엄 인화지 4장 무료
-모든 원본파일 무료 제공
-5색 배경지 무료 이벤트
-레터링 무료
-2컷,4컷,6컷,9컷 무료 편집

이용하시다가 문의사항 있다면 연락 부탁 드릴께요!
        """
        booking_guide_template_867589 = """
        안녕하세요! 고객님~

다비스튜디오 안산초지점을 찾아주셔서 감사합니다 :)
금일 이용 상세 안내 드립니다.

정시 입실/퇴실 꼭 지켜주셔야 하며,
이용시간 준수하지 않음으로 인한 불이익은 책임지지 않습니다.

⬇이용 매뉴얼 미리보기⬇
http://pf.kakao.com/_EwvUxj/104666553

-도어락 비밀번호 : 5282*
-오시는 길 :
경기도 안산시 ��원구 광덕3로 41, 3층
('하나로차사랑' 쌩노란색 간판이 독보적으로 보이는 건물이에요!)
-주차 : 건물 뒷편, 그 옆 CU건물, 대로변 앞은 오전8시 이전, 11-2시, 오후 6시 이후만 단속 없습니다.

비밀번호 입력 후 입장하셔서 커튼 안쪽의 "촬영실"로 들어가셔서 책상 위의 메뉴얼을 따라만 하시면 너무 쉬워요 :)

⚠️ 사진관 카메라 주의 안내 ⚠️
사진관 내 고정 카메라는 초점,구도가 맞춰져 있으니, 절대 건드리거나 위치를 변경하지 말아주세요

❗ 한 번 흐트러지면 다시 맞추기가 어렵고, 촬영에 큰 지장이 발생할 수 있습니다.
꼭 유의 부탁드립니다.

[제공서비스]
이용 시간 구성:
촬영 50분 10분 내보내기 후
셀렉실로 이동하여 50분 셀렉 및 인화
(내가 촬영할 때 셀렉실에서 전 타임 셀렉)

(평일 1시간 더 쿠폰 사용하신 분은
기본 촬영 시간에 50분 추가돼요!)

-프리미엄 인화지 4장
-모든 원본파일 무료 제공
-레터링 무료
-2컷,4컷,6컷,9컷 무료 편집

이용하시다가 문의사항 있다면 연락 부탁 드릴께요!
        """
        #문자양식템플릿.앞의 샵은 제거하고, 사업장번호칸에 적절한 번호를 수정한뒤, 문자 내용을 적으시면 됩니다. 


        



        #booking_guide_template_사업장번호 = """
        #이 안에다가 내용 쓰기
        #"""
        #문자양식템플릿.앞의 샵은 제거하고, 사업장번호칸에 적절한 번호를 수정한뒤, 문자 내용을 적으시면 됩니다. 

        booking_guide_sms = None
        if store_id == "1051707":
            booking_guide_sms = booking_guide_template_1051707
        elif store_id == "951291":
            booking_guide_sms = booking_guide_template_951291
        elif store_id == "1462519":
            booking_guide_sms = booking_guide_template_1462519
        elif store_id == '1120125':
            booking_guide_sms = booking_guide_template_1120125
        elif store_id == '1285716':
            booking_guide_sms = booking_guide_template_1285716
        elif store_id == '1473826':
            booking_guide_sms = booking_guide_template_1473826
        elif store_id == '1466783':
            booking_guide_sms = booking_guide_template_1466783
        elif store_id == '867589':
            booking_guide_sms = booking_guide_template_867589                    
        #elif store_id == '사업장번호':
        #    booking_guide_sms = booking_guide_template_사업장번호
        #사업장번호 검사코드입니다. 만약 사업장 문자 템플릿을 추가했을경우, 해당 사업자번호입력 후 앞의 #을 지우시면 됩니다.
        
        data = {
            "type":"LMS",
            "contentType":"COMM",
            "from": from_number,
            "subject":"다비스튜디오 안내",
            "content": booking_guide_sms,
            "messages":[
                {
                    "to": phone_num,
                }
            ]
        }
        
        res = requests.post(self.url + self.uri, headers=self.header, data=json.dumps(data))
        logger.debug("SENS response: %s", res.text)

    def send_event_sms(self, phone: str, store_id: Optional[str] = None):
        if not phone:
            raise ValueError("phone is required")
        phone_num = phone.strip().replace("-", "")
        from_number = self.get_from_number(store_id)
        masked_phone = phone_num[-4:] if len(phone_num) >= 4 else phone_num
        logger.info(
            "Sending event SMS store_id=%s from=%s to=***%s",
            store_id,
            from_number,
            masked_phone,
        )
        event_template="""
고객님~ 안녕하세요, 다비스튜디오예요 :)

소중한 사람들과의 소중한 추억을 잘 남기셨는지 궁금하네요!

5,000원 상당의 무료 인화지 리뷰이벤트는 등록 하셨을까요?
네이버: 예약 -> 포토리뷰 작성
인스타: 팔로우하고 결과물 게시 후 사람태그 @_dabistudio_

좋은 하루 보내세요 :D
        """

        data = {
            "type":"LMS",
            "contentType":"COMM",
            "from": from_number,
            "subject":"다비스튜디오 안내",
            "content": event_template,
            "messages":[
                {
                    "to": phone_num,
                }
            ]
        }
        
        res = requests.post(self.url + self.uri, headers=self.header, data=json.dumps(data))
        logger.debug("SENS response: %s", res.text)
