"""
Naver Booking API Client

Handles fetching booking data from Naver Partner Booking API with authenticated session.
Implements exact transformation logic from legacy lambda_function.py:303-388.

Reference: docs/brownfield-architecture.md - Naver Booking API Details
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging

import requests

from src.domain.booking import Booking

logger = logging.getLogger(__name__)


class NaverBookingAPIClient:
    """
    Client for fetching booking data from Naver Partner Booking API.

    Requires an authenticated requests.Session from NaverAuthenticator
    that contains valid Naver cookies.
    """

    BASE_URL = "https://partner.booking.naver.com"

    # Booking status codes
    STATUS_CONFIRMED = "RC03"  # Reservation Confirmed
    STATUS_COMPLETED = "RC08"  # Reservation Completed

    def __init__(self, session: requests.Session, option_keywords: Optional[List[str]] = None):
        """
        Initialize Naver Booking API client.

        Args:
            session: Authenticated requests.Session with Naver cookies
            option_keywords: List of keywords for option detection (default: ['네이버', '인스타', '원본'])
        """
        self.session = session
        self.option_keywords = option_keywords or ["네이버", "인스타", "원본"]

    def get_bookings(
        self,
        store_id: str,
        status: str = STATUS_CONFIRMED,
        date_filter: str = "USEDATE",
        page: int = 0,
        size: int = 20,
    ) -> List[Booking]:
        """
        Fetch bookings for a specific store.

        Implements API call logic from lambda_function.py:329-388.

        Args:
            store_id: Business ID (biz_id)
            status: Booking status code (RC03 or RC08)
            date_filter: Filter type (default: "USEDATE")
            page: Page number for pagination
            size: Page size

        Returns:
            List of Booking domain objects

        Raises:
            requests.RequestException: If API call fails
        """
        logger.info(f"Fetching bookings for store {store_id} with status {status}")

        # Build headers matching legacy implementation (lines 305-317)
        headers = {
            "authority": "partner.booking.naver.com",
            "referer": f"https://partner.booking.naver.com/bizes/{store_id}/booking-list-view",
            "x-booking-naver-role": "OWNER",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "accept": "application/json, text/plain, */*",
            "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        }

        # Build query parameters
        params = {
            "bizItemTypes": "STANDARD",
            "bookingStatusCodes": status,
            "dateFilter": date_filter,
            "page": page,
            "size": size,
        }

        # Make API request
        url = f"{self.BASE_URL}/api/businesses/{store_id}/bookings"

        try:
            response = self.session.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            bookings_data = data if isinstance(data, list) else []

            logger.info(f"Retrieved {len(bookings_data)} bookings for store {store_id}")

            # Transform to Booking domain objects
            bookings = []
            for booking_data in bookings_data:
                try:
                    booking = self._transform_booking(booking_data, store_id)
                    bookings.append(booking)
                except Exception as e:
                    logger.warning(
                        f"Failed to transform booking {booking_data.get('bookingId')}: {e}"
                    )

            return bookings

        except requests.RequestException as e:
            logger.error(f"Failed to fetch bookings for store {store_id}: {e}")
            raise

    def get_all_confirmed_bookings(self, store_ids: List[str]) -> List[Booking]:
        """
        Fetch confirmed (RC03) bookings for all stores.

        Args:
            store_ids: List of store IDs to query

        Returns:
            Combined list of all confirmed bookings
        """
        all_bookings = []

        for store_id in store_ids:
            try:
                bookings = self.get_bookings(store_id, status=self.STATUS_CONFIRMED)
                all_bookings.extend(bookings)
            except Exception as e:
                logger.error(f"Failed to fetch confirmed bookings for store {store_id}: {e}")

        logger.info(
            f"Retrieved {len(all_bookings)} total confirmed bookings across {len(store_ids)} stores"
        )
        return all_bookings

    def get_all_completed_bookings(self, store_ids: List[str]) -> List[Booking]:
        """
        Fetch completed (RC08) bookings for all stores.

        Args:
            store_ids: List of store IDs to query

        Returns:
            Combined list of all completed bookings
        """
        all_bookings = []

        for store_id in store_ids:
            try:
                bookings = self.get_bookings(store_id, status=self.STATUS_COMPLETED)
                all_bookings.extend(bookings)
            except Exception as e:
                logger.error(f"Failed to fetch completed bookings for store {store_id}: {e}")

        logger.info(
            f"Retrieved {len(all_bookings)} total completed bookings across {len(store_ids)} stores"
        )
        return all_bookings

    def _transform_booking(self, booking_data: Dict[str, Any], store_id: str) -> Booking:
        """
        Transform API response to Booking domain object.

        Implements exact transformation logic from lambda_function.py:358-383:
        - Phone formatting: 01012345678 -> 010-1234-5678
        - Timezone conversion: UTC ISO -> KST datetime +9hrs
        - Option keyword detection

        Args:
            booking_data: Raw booking data from API
            store_id: Business ID

        Returns:
            Booking domain object
        """
        booking_id = booking_data["bookingId"]
        name = booking_data.get("name", "")
        phone_raw = booking_data.get("phone", "")

        # Format phone number: 01012345678 -> 010-1234-5678 (line 375)
        phone = self._format_phone(phone_raw)

        # Extract booking info from snapshot
        snapshot = booking_data.get("snapshotJson", {})
        start_datetime_str = snapshot.get("startDateTime", "")

        # Convert UTC ISO to KST datetime +9hrs (lines 369-372)
        reserve_at = self._parse_datetime_kst(start_datetime_str)

        # Detect option keywords (lines 361-367)
        booking_options = snapshot.get("bookingOptionJson", [])
        option = self._detect_option_keywords(booking_options)

        # Extract coupon name
        coupon_name = None
        coupon_json_list = snapshot.get("couponJson", [])
        if coupon_json_list:
            first_coupon = coupon_json_list[0]
            coupon_name = first_coupon.get("couponName")

        # Extract option keywords and option-specific info
        option_keywords_list = []
        has_pro_edit_option = False
        pro_edit_count = 0
        has_edit_add_person_option = False
        edit_add_person_count = 0
        for option_item in booking_options:
            option_name = option_item.get("name", "")
            # Collect all option names as keywords
            if option_name:
                option_keywords_list.append(option_name)
            # Track specific options
            if "전문가 보정" in option_name:
                has_pro_edit_option = True
                pro_edit_count = option_item.get("bookingCount", 0)
            elif "사진 보정 추가" in option_name:
                has_edit_add_person_option = True
                edit_add_person_count = option_item.get("bookingCount", 0)

        # Create composite booking_num key
        booking_num = f"{store_id}_{booking_id}"

        # Format booking_time for DynamoDB
        booking_time = reserve_at.strftime("%Y-%m-%d %H:%M:%S")

        return Booking(
            booking_num=booking_num,
            book_id=booking_id,
            biz_id=store_id,
            name=name,
            phone=phone,
            option=option,
            reserve_at=reserve_at,
            booking_time=booking_time,
            status=booking_data.get("bookingStatusCode", ""),
            coupon_name=coupon_name,
            has_pro_edit_option=has_pro_edit_option,
            pro_edit_count=pro_edit_count,
            has_edit_add_person_option=has_edit_add_person_option,
            edit_add_person_count=edit_add_person_count,
            option_keywords=option_keywords_list,
        )

    def _format_phone(self, phone_raw: str) -> str:
        """
        Format phone number with hyphens.

        Transforms: 01012345678 -> 010-1234-5678
        Matches legacy formatting at line 375.

        Args:
            phone_raw: Raw phone number (no hyphens)

        Returns:
            Formatted phone number with hyphens
        """
        # Remove any existing hyphens/spaces
        digits = "".join(c for c in phone_raw if c.isdigit())

        # Format as 010-XXXX-XXXX
        if len(digits) == 11 and digits.startswith("010"):
            return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
        elif len(digits) == 10:
            return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
        else:
            # Return as-is if unexpected format
            return phone_raw

    def _parse_datetime_kst(self, iso_string: str) -> datetime:
        """
        Parse UTC ISO datetime and convert to KST (+9 hours).

        Matches legacy conversion at lines 369-372:
        datetime.strptime(booking_information['startDateTime'],
                         '%Y-%m-%dT%H:%M:%SZ') + timedelta(hours=9)

        Args:
            iso_string: ISO 8601 datetime string (e.g., '2025-10-19T11:30:00Z')

        Returns:
            Naive datetime in KST timezone
        """
        # Parse UTC datetime
        dt_utc = datetime.strptime(iso_string, "%Y-%m-%dT%H:%M:%SZ")

        # Add 9 hours for KST
        dt_kst = dt_utc + timedelta(hours=9)

        return dt_kst

    def _detect_option_keywords(self, booking_options: List[Dict[str, Any]]) -> bool:
        """
        Detect if booking has option keywords.

        Matches legacy nested loop detection at lines 361-367:
        for option in booking_options:
            for keyword in option_keyword_list:
                if keyword in option['name']:
                    option_tf = True

        Args:
            booking_options: List of booking option dicts with 'name' field

        Returns:
            True if any option contains a keyword, False otherwise
        """
        for option in booking_options:
            option_name = option.get("name", "")
            for keyword in self.option_keywords:
                if keyword in option_name:
                    logger.debug(f"Option keyword '{keyword}' found in '{option_name}'")
                    return True

        return False
