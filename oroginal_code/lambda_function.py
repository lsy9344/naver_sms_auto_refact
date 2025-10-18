import json
import time
from random import uniform

from boto3.dynamodb.conditions import Attr
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import *
import boto3
from sens_sms import Sens_sms
import requests
import base64

from datetime import datetime, timedelta

client = boto3.resource('dynamodb')
sms_table = client.Table('sms')
session_table = client.Table('session')

delay = 0


def session_get_db():
    try:
        response = session_table.get_item(Key={
            'id': '1'
        })
        return response['Item']['cookies']
    except KeyError:
        return None
    except:
        return None


def session_upsert_db(value):
    response = session_table.put_item(Item={
        'id': '1',
        'cookies': value
    }
    )

    if response['ResponseMetadata']['HTTPStatusCode'] == 200:
        return True
    else:
        return False


def get_item(booking_num, phone):
    try:
        response = sms_table.get_item(
            Key={
                'booking_num': booking_num,
                'phone': phone
            }
        )

        return response['Item']
    except KeyError:
        return None
    except:
        return None


def update_item(booking_num, phone, send_check, sms_type):
    response = sms_table.update_item(
        Key={
            'booking_num': booking_num,
            'phone': phone
        },
        UpdateExpression=f'SET {sms_type} = :val1',
        ExpressionAttributeValues={
            ':val1': send_check
        }
    )

    if response['ResponseMetadata']['HTTPStatusCode'] == 200:
        return True
    else:
        return False


def send_sms(phone, type, biz: str = None):
    # for test
    #if phone != '010-5581-5282':
    #    print('테스트용 전송 안함')
    #    return
    
    sens = Sens_sms()
    if type == 1:
        print('예약확정', phone)
        sens.send_confirm_sms(phone)
    elif type == 2:
        print('예약리마인드', phone, biz)
        sens.send_guide_sms(biz, phone)
    elif type == 3:
        print('옵션', phone)
        sens.send_event_sms(phone)


def reservation_not_confirm(biz_list):
    try:
        response = sms_table.scan(
            FilterExpression=Attr('option_sms').eq(False)
        )
        items = response['Items']

        #     item group by biz_list
        #     booking_num is biz_id

        group = {}
        for biz_id in biz_list:
            filtered_items = list(filter(lambda x: x['booking_num'].startswith(biz_id), items))
            sorted_items = sorted(filtered_items, key=lambda x: x['booking_time'])
            group[biz_id] = {
                'start_time': datetime.strptime(sorted_items[0]['booking_time'], '%Y-%m-%d %H:%M:%S').strftime(
                    '%Y-%m-%dT%H:%M:%S.000Z'),
                'end_time': datetime.strptime(sorted_items[-1]['booking_time'], '%Y-%m-%d %H:%M:%S').strftime(
                    '%Y-%m-%dT%H:%M:%S.000Z'),
            }

        return group

    except KeyError:
        return group
    except:
        return group


def reservation_check(user_data):
    print('메세지 발송 시작')
    results = []
    for i in user_data:
        prefix = f"{i['biz_id']}_{i['book_id']}"
        try:
            db_response = get_item(prefix, i['phone'])
            if db_response is None:
                remind_yn = i['reserve_at'] - timedelta(hours=2) <= datetime.now() < i['reserve_at']
                booking_data = {
                    'booking_num': prefix,
                    'phone': i['phone'],
                    'name': i['name'],
                    'booking_time': i['reserve_at'].strftime('%Y-%m-%d %H:%M:%S'),
                    'confirm_sms': True,
                    'remind_sms': remind_yn,
                    'option_sms': False,
                    'option_time': ''
                }
                sms_table.put_item(Item=booking_data)

                send_sms(i['phone'], 1)
                results.append(i['phone'] + ' 예약확정 문자 발송 완료')

                if remind_yn:
                    send_sms(i['phone'], 2, str(i['biz_id']))
                    results.append(i['phone'] + ' 안내 문자 발송 완료')
                continue
            else:
                if db_response['remind_sms'] == False and i['reserve_at'] > datetime.now() and i[
                    'reserve_at'] - datetime.now() < timedelta(hours=2):
                    if db_response['confirm_sms'] == False:
                        update_item(prefix, i['phone'], True, 'confirm_sms')
                        send_sms(i['phone'], 1)
                        results.append(i['phone'] + ' 예약확정 문자 발송 완료')

                    update_item(prefix, i['phone'], True, 'remind_sms')
                    send_sms(i['phone'], 2, str(i['biz_id']))
                    results.append(i['phone'] + ' 안내 문자 발송 완료')
        except Exception as err:
            print('err', err)
            results.append(i['phone'] + ' 안내 문자 발송 실패')
    return results


def option_sms_check(user_data):
    if datetime.now().hour != 20:
        return []

    print('옵션 메세지 발송 시작')
    results = []
    for i in user_data:
        prefix = f"{i['biz_id']}_{i['book_id']}"
        try:
            db_response = get_item(prefix, i['phone'])
            if db_response is None:
                continue
            else:
                if db_response['option_sms'] == False and i['option'] == True:
                    update_item(prefix, i['phone'], True, 'option_sms')
                    send_sms(i['phone'], 3)
                    results.append(i['phone'] + ' 옵션 문자 발송 완료')
        except Exception as err:
            print('err', err)
            results.append(i['phone'] + ' 옵션 문자 발송 실패')
    return results


def format_date(date_string: str):
    try:

        day_names = {
            "월": "Mon",
            "화": "Tue",
            "수": "Wed",
            "목": "Thu",
            "금": "Fri",
            "토": "Sat",
            "일": "Sun"
        }

        am_pm = {
            "오전": "AM",
            "오후": "PM"
        }

        for korean_day, english_day in day_names.items():
            date_string = date_string.replace(korean_day, english_day)

        for korean_am_pm, english_am_pm in am_pm.items():
            date_string = date_string.replace(korean_am_pm, english_am_pm)

        date = datetime.strptime(date_string.split("~")[0].strip(), "%y. %m. %d.(%a) %p %I:%M")
        return date
    except:
        return None


chrome_options = Options()
chrome_options.add_argument('--headless')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-gpu')
chrome_options.add_argument('--window-size=1280x1696')
chrome_options.add_argument('--user-data-dir=/tmp/user-data')
chrome_options.add_argument('--hide-scrollbars')
chrome_options.add_argument('--enable-logging')
chrome_options.add_argument('--log-level=0')
chrome_options.add_argument('--v=99')
chrome_options.add_argument('--single-process')
chrome_options.add_argument('--data-path=/tmp/data-path')
chrome_options.add_argument('--ignore-certificate-errors')
chrome_options.add_argument('--homedir=/tmp')
chrome_options.add_argument('--disk-cache-dir=/tmp/cache-dir')
chrome_options.add_argument(
    'user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36')

chrome_options.binary_location = "/opt/python/bin/headless-chromium"
driver = webdriver.Chrome('/opt/python/bin/chromedriver', chrome_options=chrome_options)

userid = 'dltnduf4318'
userpw = 'Doolim01!@'
biz_list = ['1051707', '951291', '1120125', '1285716', '1462519', '1473826', '1466783', '867589'] # 사업장 데이터. 사업장 추가를 원하시면 253번줄 [] 안에 있는 내용과 같은 방식으로 내용 추가해주세요
#biz_list = ['1051707', '951291', '867589', '1120125'] 사업장 추가
#추가로, 코드 수정이후엔, 상단의 Deploy버튼을 눌러야 저장 및 반영됩니다.
option_keyword_list = ['네이버', '인스타', '원본']                  # 키워드 데이터. 키워드 추가도 사업장 추가와 같은 방식으로 진행됩니다.
driver.get('https://new.smartplace.naver.com/')
driver.implicitly_wait(10)


def login(cookies):
    print('로그인')
    if not cookies:
        print("쿠키 없음, 로그인 진행")
        driver.refresh()
        
        
        driver.get('https://nid.naver.com/nidlogin.login?mode=form&url=https://www.naver.com/')
            
            
        login_btn = driver.find_element(By.ID, "log.login")


        
        driver.execute_script(f"document.querySelector('input[id=\"id\"]').setAttribute('value', '{userid}')")
        time.sleep(uniform(delay + 0.33643, delay + 0.54354))
        driver.execute_script(f"document.querySelector('input[id=\"pw\"]').setAttribute('value', '{userpw}')")
        time.sleep(uniform(delay + 0.33643, delay + 0.54354))
        login_btn.click()
        time.sleep(uniform(delay + 0.63643, delay + 0.94354))

        time.sleep(1)
        
        WebDriverWait(driver, 10).until(
            EC.url_contains('naver.com')
        )

        cookies = driver.get_cookies()
        session_upsert_db(json.dumps(cookies))
    else:
        for cookie in cookies:
            driver.add_cookie(cookie)

        driver.get('https://nid.naver.com/user2/help/myInfoV2?lang=ko_KR')
        driver.implicitly_wait(10)

        print("쿠키 로그인 확인중")
        time.sleep(3)
        if "login" in driver.current_url:
            print("쿠키 로그인 실패, 쿠키 재발급 진행")
            login(None)


def count_items(session, biz, param):
    try:
        headers = {
            'authority': 'partner.booking.naver.com',
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'referer': f'https://partner.booking.naver.com/bizes/{biz}/booking-list-view',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'x-booking-naver-role': 'OWNER',
        }

        # unixtimestamp
        param['noCache'] = round(datetime.now().timestamp() * 1000)
        response = session.get(f'https://partner.booking.naver.com/v3.1/businesses/{biz}/bookings/count?', params=param,
                               headers=headers)
        return response.json()['count']
    except Exception as e:
        print('오류', e)
        return None


def get_items(session, biz_id, booking_status: str = 'RC03', start_date: str = None, end_Date: str = None) -> list:
    params = {
        'bizItemTypes': 'STANDARD',
        'bookingStatusCodes': booking_status,
        'dateDropdownType': 'ENTIRE',
        'dateFilter': 'USEDATE',
        'maxDays': '31',
        'nPayChargedStatusCodes': '',
        'orderBy': '',
        'orderByStartDate': 'ASC',
        'paymentStatusCodes': '',
        'searchValue': '',
        'page': '0',
        'size': '50',
    }

    if start_date is not None and end_Date is not None:
        params['startDateTime'] = start_date
        params['endDateTime'] = end_Date

    count = count_items(session, biz_id, params)

    items = []
    for idx, value in enumerate(range(0, count, 50)):
        params['page'] = idx
        params['noCache'] = round(datetime.now().timestamp() * 1000)

        response = session.get(f'https://partner.booking.naver.com/api/businesses/{biz_id}/bookings?', params=params)
        booking_info = response.json()
        for booking in booking_info:
            booking_information = booking['snapshotJson']

            option_tf = False
            options = booking_information['bookingOptionJson']
            for option in options:
                for keyword in option_keyword_list:
                    if keyword in option['name']:
                        option_tf = True
                        break

            reserve_at = datetime.strptime(booking_information['startDateTime'], '%Y-%m-%dT%H:%M:%SZ') + timedelta(
                hours=9)
            reserve_at = reserve_at.strftime('%y. %m. %d.(%a) %p %I:%M')
            reserve_at = datetime.strptime(reserve_at, '%y. %m. %d.(%a) %p %I:%M')

            phone = booking['phone']
            phone = phone[:3] + '-' + phone[3:7] + '-' + phone[7:]
            items.append({
                'book_id': booking['bookingId'],
                'biz_id': booking['businessId'],
                'name': booking['name'],
                'phone': phone,
                'option': option_tf,
                'reserve_at': reserve_at
            })
        time.sleep(1)

        print("작업 완료:", biz_id, len(items))

    return items


def get_complete_items(session) -> list:
    print('완료 작업 시작')
    reservation_data = reservation_not_confirm(biz_list)
    items = []

    for item in reservation_data.items():
        biz_id = item[0]
        start_date = item[1]['start_time']
        end_date = item[1]['end_time']
        items += get_items(session, biz_id, 'RC08', start_date, end_date)

    return items


def lambda_handler(event, context):
    try:
        session_data = session_get_db()
        if not session_data:
            login(None)
        else:
            print("쿠키 로그인 진행")
            print("쿠키:", json.loads(session_data))
            login(json.loads(session_data))
        print('로그인 완료')
        cookies = driver.get_cookies()
        driver.quit()
    
        session = requests.Session()
        for cookie in cookies:
            session.cookies.set(cookie['name'], cookie['value'])
    
        user_data = []
        user_complete_data = get_complete_items(session)
        
        for biz in biz_list:
            print("작업 진행:", biz)
            user_data += get_items(session, biz)
    
        print(user_data)
        print(user_complete_data)
        print("모든 사업장의 예약 확정 개수:", len(user_data))
        print("모든 사업장의 완료 개수:", len(user_complete_data))
    
        reservation_results = reservation_check(user_data)
        option_results = option_sms_check(user_complete_data)
    
        arrays = reservation_results + option_results
    
        requests.post(f'https://api.telegram.org/bot6657330606:AAFX9uYEwkcuuSpQORGpShFTSpG7e8GO1sg/sendMessage', {
            'chat_id': '6968094848',
            'text': '\n'.join(arrays) if len(arrays) > 0 else '문자 발송 대상 없음'
        })
    except Exception as err:
        requests.post(f'https://api.telegram.org/bot6657330606:AAFX9uYEwkcuuSpQORGpShFTSpG7e8GO1sg/sendMessage', {
            'chat_id': '6968094848',
            'text': '요청중 오류 발생'
        })
        
