"""
Naver Booking API Client

Handles fetching booking data from Naver Partner Booking API with authenticated session.
Implements exact transformation logic from legacy lambda_function.py:303-388.

Reference: docs/brownfield-architecture.md - Naver Booking API Details
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, TYPE_CHECKING
import time

import requests

from src.domain.booking import Booking
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.database.dynamodb_client import BookingRepository

logger = get_logger(__name__)


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
    PAGE_SIZE = 50  # Matches legacy lambda pagination size

    def __init__(
        self,
        session: requests.Session,
        option_keywords: Optional[List[str]] = None,
        booking_repo: Optional["BookingRepository"] = None,
    ):
        """
        Initialize Naver Booking API client.

        Args:
            session: Authenticated requests.Session with Naver cookies
            option_keywords: List of keywords for option detection (default: ['네이버', '인스타', '원본'])
            booking_repo: Optional BookingRepository for fetching unnotified options (RC08 filtering)
        """
        self.session = session
        self.option_keywords = option_keywords or ["네이버", "인스타", "원본"]
        self.booking_repo = booking_repo

    def _get_default_date_range(self) -> tuple[str, str]:
        """
        Calculate default date range for booking queries.

        Returns last 30 days to ensure the range stays within Naver API's 31-day limit.
        This prevents 422 Unprocessable Entity errors when the date range exceeds maxDays=31.

        Returns:
            Tuple of (start_date, end_date) in ISO 8601 format
            Example: ("2025-09-29T00:00:00", "2025-10-29T18:27:22")
        """
        now = datetime.now()
        # Start: 30 days ago at midnight (ensures total range ≤ 31 days)
        start = now - timedelta(days=30)
        start_date = start.replace(hour=0, minute=0, second=0, microsecond=0).strftime(
            "%Y-%m-%dT%H:%M:%S"
        )
        # End: current time
        end_date = now.strftime("%Y-%m-%dT%H:%M:%S")
        return start_date, end_date

    def _build_query_params(
        self,
        status: str,
        start_date: Optional[str],
        end_date: Optional[str],
        page: int,
        size: int,
    ) -> Dict[str, Any]:
        """
        Build query parameters exactly like legacy implementation.

        Preserves optional fields with default values so behaviour stays identical.
        """
        params: Dict[str, Any] = {
            "bizItemTypes": "STANDARD",
            "bookingStatusCodes": status,
            "dateDropdownType": "ENTIRE",
            "dateFilter": "USEDATE",
            "maxDays": "31",
            "nPayChargedStatusCodes": "",
            "orderBy": "",
            "orderByStartDate": "ASC",
            "paymentStatusCodes": "",
            "searchValue": "",
            "page": str(page),
            "size": str(size),
        }

        if start_date and end_date:
            params["startDateTime"] = start_date
            params["endDateTime"] = end_date

        return params

    def _count_bookings(
        self,
        store_id: str,
        status: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> int:
        """
        Count total bookings matching criteria.

        Implements lambda_function.py:303-326 (count_items).

        Args:
            store_id: Business ID
            status: Booking status code (RC03 or RC08)
            start_date: Optional start date in ISO format
            end_date: Optional end date in ISO format

        Returns:
            Total count of bookings, or 0 if error
        """
        headers = {
            "authority": "partner.booking.naver.com",
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "referer": f"https://partner.booking.naver.com/bizes/{store_id}/booking-list-view",
            "x-booking-naver-role": "OWNER",
        }

        # Build base params for counting (legacy count_items)
        params = self._build_query_params(
            status=status,
            start_date=start_date,
            end_date=end_date,
            page=0,
            size=self.PAGE_SIZE,
        )
        params["noCache"] = round(datetime.now().timestamp() * 1000)

        url = f"{self.BASE_URL}/v3.1/businesses/{store_id}/bookings/count"

        try:
            response = self.session.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            count = response.json().get("count", 0)
            logger.debug(f"Count API returned {count} bookings for store {store_id}")
            return count
        except Exception as e:
            logger.error(f"Failed to count bookings for store {store_id}: {e}")
            return 0

    def get_bookings(
        self,
        store_id: str,
        status: str = STATUS_CONFIRMED,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Booking]:
        """
        Fetch all bookings for a specific store with pagination.

        Implements lambda_function.py:329-388 (get_items).
        Fetches all bookings in 50-item pages (size=50) like legacy code.

        Args:
            store_id: Business ID (biz_id)
            status: Booking status code (RC03 or RC08)
            start_date: Optional start date in ISO format for date range query
            end_date: Optional end date in ISO format for date range query

        Returns:
            List of all Booking domain objects across all pages

        Raises:
            requests.RequestException: If API call fails
        """
        logger.info(f"Fetching all bookings for store {store_id} with status {status}")

        # Count total bookings first (lambda_function.py:349)
        total_count = self._count_bookings(store_id, status, start_date, end_date)

        if total_count == 0:
            logger.info(f"No bookings found for store {store_id}")
            return []

        # Build headers for bookings fetch
        headers = {
            "authority": "partner.booking.naver.com",
            "referer": f"https://partner.booking.naver.com/bizes/{store_id}/booking-list-view",
            "x-booking-naver-role": "OWNER",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "accept": "application/json, text/plain, */*",
            "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        }

        url = f"{self.BASE_URL}/api/businesses/{store_id}/bookings"
        page_size = self.PAGE_SIZE
        all_bookings = []

        # Paginate through results (lambda_function.py:352-387)
        num_pages = (total_count + page_size - 1) // page_size
        for page_idx in range(num_pages):
            try:
                # Build params with noCache for each request (lambda_function.py:354)
                params = self._build_query_params(
                    status=status,
                    start_date=start_date,
                    end_date=end_date,
                    page=page_idx,
                    size=page_size,
                )
                params["noCache"] = round(datetime.now().timestamp() * 1000)

                logger.debug(f"Fetching page {page_idx} for store {store_id}")

                response = self.session.get(url, headers=headers, params=params, timeout=10)
                response.raise_for_status()

                data = response.json()
                bookings_data = data if isinstance(data, list) else []

                logger.debug(f"Retrieved {len(bookings_data)} bookings on page {page_idx}")

                # Transform to Booking domain objects (lambda_function.py:358-383)
                for booking_data in bookings_data:
                    try:
                        booking = self._transform_booking(booking_data, store_id)
                        all_bookings.append(booking)
                    except Exception as e:
                        logger.warning(
                            f"Failed to transform booking {booking_data.get('bookingId')}: {e}"
                        )

                # Sleep 1 second between pages (lambda_function.py:384)
                if page_idx < num_pages - 1:
                    time.sleep(1)

                logger.info(
                    f"Completed page {page_idx + 1}/{num_pages} for store {store_id}, "
                    f"total: {len(all_bookings)}"
                )

            except requests.RequestException as e:
                logger.error(f"Failed to fetch page {page_idx} for store {store_id}: {e}")
                # Continue to next page rather than failing entirely
                continue

        logger.info(f"Retrieved {len(all_bookings)} total bookings for store {store_id}")
        return all_bookings

    def get_all_confirmed_bookings(self, store_ids: List[str]) -> List[Booking]:
        """
        Fetch confirmed (RC03) bookings for all stores.

        Fetches only the last 31 days of bookings to prevent excessive data accumulation.
        This ensures tests and normal operations complete quickly without processing
        years of historical data.

        Args:
            store_ids: List of store IDs to query

        Returns:
            Combined list of confirmed bookings from the last 31 days
        """
        all_bookings = []

        # Use default 31-day lookback window to prevent fetching years of old data
        start_date, end_date = self._get_default_date_range()
        logger.info(f"Fetching confirmed bookings with date range: {start_date} to {end_date}")

        for store_id in store_ids:
            try:
                bookings = self.get_bookings(
                    store_id,
                    status=self.STATUS_CONFIRMED,
                    start_date=start_date,
                    end_date=end_date,
                )
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

        Implements legacy behavior from lambda_function.py:102, 391:
        1. Scans DynamoDB for bookings with option_sms=False (via scan_unnotified_options)
        2. Extracts date ranges from first and last booking times per store
        3. Fetches RC08 bookings within those date ranges

        This ensures RC08 data matches original Lambda behavior exactly.

        Args:
            store_ids: List of store IDs to query

        Returns:
            Combined list of completed bookings filtered by unnotified options date ranges
        """
        all_bookings = []

        # AC-6: Fetch unnotified options with date ranges (lambda_function.py:102)
        if self.booking_repo:
            try:
                unnotified_options = self.booking_repo.scan_unnotified_options()
                logger.info(
                    f"Found unnotified options for {len(unnotified_options)} stores",
                    context={"stores_with_unnotified_options": len(unnotified_options)},
                )

                # Fetch RC08 bookings within each store's date range (lambda_function.py:391)
                for store_id, date_range in unnotified_options.items():
                    try:
                        start_date = date_range.get("start_time")
                        end_date = date_range.get("end_time")
                        logger.debug(
                            f"Fetching RC08 for store {store_id} with date range",
                            context={"store_id": store_id, "start": start_date, "end": end_date},
                        )
                        bookings = self.get_bookings(
                            store_id,
                            status=self.STATUS_COMPLETED,
                            start_date=start_date,
                            end_date=end_date,
                        )
                        all_bookings.extend(bookings)
                    except Exception as e:
                        logger.error(
                            f"Failed to fetch completed bookings for store {store_id}: {e}"
                        )
            except Exception as e:
                logger.warning(
                    f"Failed to scan unnotified options, falling back to 31-day date range: {e}"
                )
                # Fallback: fetch RC08 bookings with default 31-day range
                start_date, end_date = self._get_default_date_range()
                logger.info(f"Using fallback date range for RC08: {start_date} to {end_date}")
                for store_id in store_ids:
                    try:
                        bookings = self.get_bookings(
                            store_id,
                            status=self.STATUS_COMPLETED,
                            start_date=start_date,
                            end_date=end_date,
                        )
                        all_bookings.extend(bookings)
                    except Exception as store_err:
                        logger.error(
                            f"Failed to fetch completed bookings for store {store_id}: {store_err}"
                        )
        else:
            # No repository provided: fetch RC08 bookings with default 31-day range
            start_date, end_date = self._get_default_date_range()
            logger.warning(
                f"BookingRepository not provided, fetching RC08 bookings with 31-day range: "
                f"{start_date} to {end_date}"
            )
            for store_id in store_ids:
                try:
                    bookings = self.get_bookings(
                        store_id,
                        status=self.STATUS_COMPLETED,
                        start_date=start_date,
                        end_date=end_date,
                    )
                    all_bookings.extend(bookings)
                except Exception as e:
                    logger.error(f"Failed to fetch completed bookings for store {store_id}: {e}")

        logger.info(
            f"Retrieved {len(all_bookings)} total completed bookings across {len(store_ids)} stores",
            context={"total_bookings": len(all_bookings), "store_count": len(store_ids)},
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
        # Store full option objects (not just names) to preserve bookingCount for has_multiple_options
        option_keywords_list: List[Dict[str, Any]] = []
        option_names_seen: set = set()
        has_pro_edit_option = False
        pro_edit_count = 0
        has_edit_add_person_option = False
        edit_add_person_count = 0
        for option_item in booking_options:
            option_name = option_item.get("name", "")
            # Collect full option objects (preserves bookingCount for rule engine)
            if option_name and option_name not in option_names_seen:
                option_keywords_list.append(option_item)
                option_names_seen.add(option_name)
            # Track specific options
            if "전문가 보정" in option_name:
                has_pro_edit_option = True
                pro_edit_count = option_item.get("bookingCount", 0)
            elif "사진 보정 추가" in option_name:
                has_edit_add_person_option = True
                edit_add_person_count = option_item.get("bookingCount", 0)

        # Add pro_edit marker if needed (for backward compatibility)
        if has_pro_edit_option and not any(
            "전문가 보정" in item.get("name", "") for item in option_keywords_list
        ):
            option_keywords_list.append({"name": "전문가 보정"})

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
            option_name = option.get("name", "") if isinstance(option, dict) else str(option)
            for keyword in self.option_keywords:
                if keyword in option_name:
                    logger.debug(f"Option keyword '{keyword}' found in '{option_name}'")
                    return True

        return False
