"""
DynamoDB repository implementations for Booking and Session persistence.

This module provides a clean abstraction over DynamoDB operations with
dependency injection for testability and structured logging.
"""

import time
from datetime import datetime
from typing import Optional, Dict, Any, Union

import boto3
from botocore.exceptions import ClientError, BotoCoreError

from src.domain.booking import Booking
from src.domain.session import Session
from src.utils.logger import get_logger, mask_phone
from .exceptions import (
    DynamoDBException,
    ThrottlingError,
    NetworkError,
    PermissionError,
)


logger = get_logger(__name__)


class BookingRepository:
    """
    Repository for Booking persistence in DynamoDB.

    Handles all CRUD operations for SMS tracking records with structured logging,
    retry logic, and exception translation. Supports dynamic field access for
    future schema extensions.

    Table Schema:
        Partition Key: booking_num (e.g., "1051707_12345")
        Sort Key: phone (e.g., "010-1234-5678")
    """

    def __init__(
        self,
        table_name: str = "sms",
        dynamodb_resource: Optional[Any] = None,
        max_retries: int = 3,
        backoff_base: float = 1.0,
    ):
        """
        Initialize BookingRepository.

        Args:
            table_name: DynamoDB table name (default: "sms")
            dynamodb_resource: boto3 DynamoDB resource (default: creates new)
            max_retries: Number of retries for throttling errors
            backoff_base: Base exponential backoff multiplier (seconds)
        """
        self.table_name = table_name
        self.dynamodb = dynamodb_resource or boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(table_name)
        self.max_retries = max_retries
        self.backoff_base = backoff_base

    def get_booking(  # type: ignore[return] # noqa: C901
        self, prefix: str, phone: str
    ) -> Optional[Union[Booking, Dict[str, Any]]]:
        """
        Retrieve a booking by composite key.

        Implements AC-4a: Returns None when item not found (not exception).
        This matches legacy behavior from lambda_function.py:138.

        Args:
            prefix: Booking prefix "{biz_id}_{book_id}"
            phone: Customer phone number "010-XXXX-XXXX"

        Returns:
            Booking object or dict, or None if not found

        Raises:
            ThrottlingError: If throttled after max retries
            NetworkError: If connection fails
            PermissionError: If IAM permissions insufficient
        """
        context = {"booking_num": prefix, "phone_masked": mask_phone(phone)}

        logger.debug("Fetching booking", operation="get_booking", context=context)

        for attempt in range(self.max_retries):
            try:
                start_time = time.time()
                response = self.table.get_item(Key={"booking_num": prefix, "phone": phone})
                duration_ms = (time.time() - start_time) * 1000

                item = response.get("Item")

                if item is None:
                    logger.debug(
                        "Booking not found",
                        operation="get_booking",
                        context=context,
                    )
                    return None

                logger.info(
                    "Booking retrieved successfully",
                    operation="get_booking",
                    context=context,
                    duration_ms=duration_ms,
                )

                # Return as dict (matches legacy behavior)
                return dict(item)

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")

                if error_code == "ProvisionedThroughputExceededException":
                    if attempt < self.max_retries - 1:
                        wait_time = self.backoff_base * (2**attempt)
                        logger.warning(
                            f"Throttled, retrying after {wait_time}s",
                            operation="get_booking",
                            context=context,
                            error=error_code,
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(
                            "Throttling after max retries",
                            operation="get_booking",
                            context=context,
                            error=error_code,
                        )
                        raise ThrottlingError(
                            f"DynamoDB throttled after {self.max_retries} retries"
                        )

                elif error_code == "AccessDeniedException":
                    logger.error(
                        "Permission denied",
                        operation="get_booking",
                        context=context,
                        error=error_code,
                    )
                    raise PermissionError(f"Insufficient IAM permissions: {error_code}")

                else:
                    logger.error(
                        "DynamoDB error",
                        operation="get_booking",
                        context=context,
                        error=str(e),
                    )
                    raise DynamoDBException(f"DynamoDB error: {e}")

            except (BotoCoreError, OSError) as e:
                logger.error(
                    "Network error",
                    operation="get_booking",
                    context=context,
                    error=str(e),
                )
                raise NetworkError(f"Network error: {e}")  # type: ignore[no-unreachable]

    def create_booking(self, record: Dict[str, Any]) -> bool:  # type: ignore[return]
        """
        Create a new booking record.

        Implements AC-1 put_item behavior from lambda_function.py:150.
        Validates required fields exist before insertion.

        Args:
            record: Booking data dict with keys:
                - booking_num: "{biz_id}_{book_id}"
                - phone: "010-XXXX-XXXX"
                - name: Customer name
                - booking_time: "YYYY-MM-DD HH:MM:SS"
                - confirm_sms: bool
                - remind_sms: bool
                - option_sms: bool

        Returns:
            True if successful

        Raises:
            DynamoDBException: If validation fails or DynamoDB error
            ThrottlingError: If throttled
            NetworkError: If connection fails
        """
        # Copy to avoid mutating caller data
        record = dict(record)

        # Remove disallowed columns before validation/persistence
        for disallowed in (
            "book_id",
            "option_keyword",
            "option_keyword_names",
            "option_keyword_counts",
            "option_time",
        ):
            record.pop(disallowed, None)

        # Validate required fields
        required = {"booking_num", "phone", "name", "booking_time"}
        if not required.issubset(record.keys()):
            missing = required - record.keys()
            raise DynamoDBException(f"Missing required fields: {missing}")

        # DynamoDB does not allow attributes with null (None) values - drop them
        record = {key: value for key, value in record.items() if value is not None}

        # Ensure booking_num is positioned last for readability
        if "booking_num" in record:
            booking_num_value = record["booking_num"]
            record = {key: value for key, value in record.items() if key != "booking_num"}
            record["booking_num"] = booking_num_value

        context = {
            "booking_num": record["booking_num"],
            "phone_masked": mask_phone(record["phone"]),
        }

        logger.debug("Creating booking", operation="create_booking", context=context)

        for attempt in range(self.max_retries):
            try:
                start_time = time.time()
                self.table.put_item(Item=record)
                duration_ms = (time.time() - start_time) * 1000

                logger.info(
                    "Booking created",
                    operation="create_booking",
                    context=context,
                    duration_ms=duration_ms,
                )
                return True

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")

                if error_code == "ProvisionedThroughputExceededException":
                    if attempt < self.max_retries - 1:
                        wait_time = self.backoff_base * (2**attempt)
                        logger.warning(
                            f"Throttled, retrying after {wait_time}s",
                            operation="create_booking",
                            context=context,
                            error=error_code,
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        raise ThrottlingError(
                            f"DynamoDB throttled after {self.max_retries} retries"
                        )

                elif error_code == "AccessDeniedException":
                    raise PermissionError(f"Insufficient IAM permissions: {error_code}")

                else:
                    logger.error(
                        "DynamoDB error",
                        operation="create_booking",
                        context=context,
                        error=str(e),
                    )
                    raise DynamoDBException(f"DynamoDB error: {e}")

            except (BotoCoreError, OSError) as e:
                logger.error(
                    "Network error",
                    operation="create_booking",
                    context=context,
                    error=str(e),
                )
                raise NetworkError(f"Network error: {e}")  # type: ignore[no-unreachable]

    def update_flag(  # type: ignore[return]
        self,
        prefix: str,
        phone: str,
        flag_name: str,
        value: bool,
    ) -> bool:
        """
        Update a specific SMS flag on a booking.

        Implements AC-1 update_item behavior from lambda_function.py:66-81.
        Supports dynamic flag names for future extensibility.

        Args:
            prefix: Booking prefix "{biz_id}_{book_id}"
            phone: Customer phone number "010-XXXX-XXXX"
            flag_name: Flag to update (e.g., "confirm_sms", "remind_sms", "option_sms")
            value: New flag value (bool)

        Returns:
            True if successful

        Raises:
            DynamoDBException: If validation fails
            ThrottlingError: If throttled
            NetworkError: If connection fails
        """
        # Validate flag name (allow dynamic fields)
        valid_flags = {"confirm_sms", "remind_sms", "option_sms"}
        if flag_name not in valid_flags and not flag_name.startswith("custom_"):
            logger.warning(
                f"Updating non-standard flag: {flag_name}",
                operation="update_flag",
            )

        context = {
            "booking_num": prefix,
            "phone_masked": mask_phone(phone),
            "flag": flag_name,
            "value": value,
        }

        logger.debug("Updating booking flag", operation="update_flag", context=context)

        for attempt in range(self.max_retries):
            try:
                start_time = time.time()
                self.table.update_item(
                    Key={"booking_num": prefix, "phone": phone},
                    UpdateExpression=f"SET {flag_name} = :val",
                    ExpressionAttributeValues={":val": value},
                )
                duration_ms = (time.time() - start_time) * 1000

                logger.info(
                    "Booking flag updated",
                    operation="update_flag",
                    context=context,
                    duration_ms=duration_ms,
                )
                return True

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")

                if error_code == "ProvisionedThroughputExceededException":
                    if attempt < self.max_retries - 1:
                        wait_time = self.backoff_base * (2**attempt)
                        logger.warning(
                            f"Throttled, retrying after {wait_time}s",
                            operation="update_flag",
                            context=context,
                            error=error_code,
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        raise ThrottlingError(
                            f"DynamoDB throttled after {self.max_retries} retries"
                        )

                elif error_code == "AccessDeniedException":
                    raise PermissionError(f"Insufficient IAM permissions: {error_code}")

                else:
                    logger.error(
                        "DynamoDB error",
                        operation="update_flag",
                        context=context,
                        error=str(e),
                    )
                    raise DynamoDBException(f"DynamoDB error: {e}")

            except (BotoCoreError, OSError) as e:
                logger.error(
                    "Network error",
                    operation="update_flag",
                    context=context,
                    error=str(e),
                )
                raise NetworkError(f"Network error: {e}")  # type: ignore[no-unreachable]

    def scan_unnotified_options(self) -> Dict[str, Dict[str, str]]:
        """
        Scan for bookings with unnotified options.

        Implements AC-1 scan logic from lambda_function.py:103-128.
        Returns grouped and sorted results by store for processing.

        This preserves the exact legacy output format (sorting/grouping for
        start/end windows) as per AC-6.

        Returns:
            Dict mapping biz_id to {"start_time": ISO8601, "end_time": ISO8601}
            Empty dict if no unnotified bookings found.

        Raises:
            NetworkError: If connection fails
            DynamoDBException: If scan fails
        """
        logger.debug(
            "Scanning for unnotified options",
            operation="scan_unnotified_options",
        )

        try:
            start_time = time.time()

            # Scan for option_sms=False
            response = self.table.scan(
                FilterExpression="attribute_exists(option_sms) AND #opt = :false",
                ExpressionAttributeNames={"#opt": "option_sms"},
                ExpressionAttributeValues={":false": False},
            )

            items = response.get("Items", [])
            duration_ms = (time.time() - start_time) * 1000

            logger.info(
                f"Scan completed, found {len(items)} unnotified bookings",
                operation="scan_unnotified_options",
                duration_ms=duration_ms,
            )

            if not items:
                return {}

            # Group by biz_id (extract from booking_num prefix)
            groups: Dict[str, list] = {}
            for item in items:
                booking_num = item.get("booking_num", "")
                biz_id = booking_num.split("_")[0]

                if biz_id not in groups:
                    groups[biz_id] = []
                groups[biz_id].append(item)

            # For each group, sort by booking_time and extract start/end times
            result = {}
            for biz_id, bookings in groups.items():
                try:
                    # Sort by booking_time
                    sorted_bookings = sorted(
                        bookings,
                        key=lambda x: datetime.strptime(
                            x.get("booking_time", ""), "%Y-%m-%d %H:%M:%S"
                        ),
                    )

                    if sorted_bookings:
                        first_time = datetime.strptime(
                            sorted_bookings[0]["booking_time"], "%Y-%m-%d %H:%M:%S"
                        ).strftime("%Y-%m-%dT%H:%M:%S.000Z")

                        last_time = datetime.strptime(
                            sorted_bookings[-1]["booking_time"], "%Y-%m-%d %H:%M:%S"
                        ).strftime("%Y-%m-%dT%H:%M:%S.000Z")

                        result[biz_id] = {
                            "start_time": first_time,
                            "end_time": last_time,
                        }

                except (ValueError, KeyError) as e:
                    logger.warning(
                        f"Failed to parse booking times for {biz_id}",
                        operation="scan_unnotified_options",
                        error=str(e),
                    )

            return result

        except ClientError as e:
            logger.error(
                "DynamoDB scan failed",
                operation="scan_unnotified_options",
                error=str(e),
            )
            raise DynamoDBException(f"Scan failed: {e}")

        except (BotoCoreError, OSError) as e:
            logger.error(
                "Network error during scan",
                operation="scan_unnotified_options",
                error=str(e),
            )
            raise NetworkError(f"Network error: {e}")


class SessionRepository:
    """
    Repository for Session (Naver login cookies) persistence in DynamoDB.

    Manages the lifecycle of cached Selenium cookies with structured logging.

    Table Schema:
        Partition Key: id (always "1" in current implementation)
        Single record design for cookie cache.
    """

    def __init__(
        self,
        table_name: str = "session",
        dynamodb_resource: Optional[Any] = None,
        max_retries: int = 3,
    ):
        """
        Initialize SessionRepository.

        Args:
            table_name: DynamoDB table name (default: "session")
            dynamodb_resource: boto3 DynamoDB resource (default: creates new)
            max_retries: Number of retries for throttling errors
        """
        self.table_name = table_name
        self.dynamodb = dynamodb_resource or boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(table_name)
        self.session_id = "1"  # Single session record
        self.max_retries = max_retries

    def get_session(self) -> Optional[Session]:  # type: ignore[return]
        """
        Retrieve cached session cookies.

        Implements AC-2 session_get_db behavior from lambda_function.py:103-109.
        Returns None if session not found (matches legacy behavior).

        Returns:
            Session object with cookies, or None if not found

        Raises:
            NetworkError: If connection fails
            PermissionError: If IAM permissions insufficient
        """
        context = {"session_id": self.session_id}

        logger.debug("Fetching session", operation="get_session", context=context)

        try:
            start_time = time.time()
            response = self.table.get_item(Key={"id": self.session_id})
            duration_ms = (time.time() - start_time) * 1000

            item = response.get("Item")

            if item is None:
                logger.debug(
                    "Session not found",
                    operation="get_session",
                    context=context,
                )
                return None

            session = Session.from_dict(item)

            logger.info(
                "Session retrieved",
                operation="get_session",
                context=context,
                duration_ms=duration_ms,
            )

            return session

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")

            if error_code == "AccessDeniedException":
                logger.error(
                    "Permission denied",
                    operation="get_session",
                    context=context,
                    error=error_code,
                )
                raise PermissionError(f"Insufficient IAM permissions: {error_code}")

            else:
                logger.error(
                    "DynamoDB error",
                    operation="get_session",
                    context=context,
                    error=str(e),
                )
                raise DynamoDBException(f"DynamoDB error: {e}")

        except (BotoCoreError, OSError) as e:
            logger.error(
                "Network error",
                operation="get_session",
                context=context,
                error=str(e),
            )
            raise NetworkError(f"Network error: {e}")  # type: ignore[no-unreachable]

    def save_session(self, cookies_json: str) -> bool:  # type: ignore[return]
        """
        Save session cookies.

        Implements AC-2 session_upsert_db behavior from lambda_function.py:110-128.
        Uses put_item for upsert semantics (overwrites existing session).

        Args:
            cookies_json: JSON string of Selenium cookies list

        Returns:
            True if successful

        Raises:
            DynamoDBException: If validation fails
            ThrottlingError: If throttled
            NetworkError: If connection fails
        """
        context = {"session_id": self.session_id, "cookies_length": len(cookies_json)}

        logger.debug("Saving session", operation="save_session", context=context)

        for attempt in range(self.max_retries):
            try:
                start_time = time.time()
                self.table.put_item(
                    Item={
                        "id": self.session_id,
                        "cookies": cookies_json,
                    }
                )
                duration_ms = (time.time() - start_time) * 1000

                logger.info(
                    "Session saved",
                    operation="save_session",
                    context=context,
                    duration_ms=duration_ms,
                )
                return True

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")

                if error_code == "ProvisionedThroughputExceededException":
                    if attempt < self.max_retries - 1:
                        wait_time = 1.0 * (2**attempt)
                        logger.warning(
                            f"Throttled, retrying after {wait_time}s",
                            operation="save_session",
                            context=context,
                            error=error_code,
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        raise ThrottlingError(
                            f"DynamoDB throttled after {self.max_retries} retries"
                        )

                elif error_code == "AccessDeniedException":
                    raise PermissionError(f"Insufficient IAM permissions: {error_code}")

                else:
                    logger.error(
                        "DynamoDB error",
                        operation="save_session",
                        context=context,
                        error=str(e),
                    )
                    raise DynamoDBException(f"DynamoDB error: {e}")

            except (BotoCoreError, OSError) as e:
                logger.error(
                    "Network error",
                    operation="save_session",
                    context=context,
                    error=str(e),
                )
                raise NetworkError(f"Network error: {e}")

    def delete_session(self) -> bool:
        """
        Delete session cookies (cache invalidation).

        Implements AC-2 requirement for cache invalidation.
        Used when session is invalid and needs to be cleared.

        Returns:
            True if successful (or item didn't exist)

        Raises:
            NetworkError: If connection fails
            PermissionError: If IAM permissions insufficient
        """
        context = {"session_id": self.session_id}

        logger.debug("Deleting session", operation="delete_session", context=context)

        try:
            start_time = time.time()
            self.table.delete_item(Key={"id": self.session_id})
            duration_ms = (time.time() - start_time) * 1000

            logger.info(
                "Session deleted",
                operation="delete_session",
                context=context,
                duration_ms=duration_ms,
            )
            return True

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")

            if error_code == "AccessDeniedException":
                logger.error(
                    "Permission denied",
                    operation="delete_session",
                    context=context,
                    error=error_code,
                )
                raise PermissionError(f"Insufficient IAM permissions: {error_code}")

            else:
                logger.error(
                    "DynamoDB error",
                    operation="delete_session",
                    context=context,
                    error=str(e),
                )
                raise DynamoDBException(f"DynamoDB error: {e}")

        except (BotoCoreError, OSError) as e:
            logger.error(
                "Network error",
                operation="delete_session",
                context=context,
                error=str(e),
            )
            raise NetworkError(f"Network error: {e}")
