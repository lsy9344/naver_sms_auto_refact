"""
Lambda Handler - Main entry point for Naver SMS automation

Orchestrates authentication, booking retrieval, rule processing, and notifications.
Implements Story 4.1 requirements for end-to-end Lambda execution.
"""

import json
import logging
from datetime import datetime, date
from typing import List, Dict, Any, Tuple, Optional
import yaml
from pathlib import Path

import boto3
import requests

from src.auth.naver_login import NaverAuthenticator
from src.auth.session_manager import SessionManager
from src.api.naver_booking import NaverBookingAPIClient
from src.config.settings import Settings, setup_logging_redaction, SLACK_ENABLED
from src.database.dynamodb_client import BookingRepository
from src.domain.booking import Booking
from src.notifications.sms_service import SensSmsClient
from src.notifications.slack_service import SlackWebhookClient
from src.rules.engine import RuleEngine, ActionResult
from src.rules.conditions import register_conditions
from src.rules.actions import register_actions, ActionServicesBundle, SlackTemplateLoader
from src.utils.logger import get_logger

logger = get_logger(__name__)

# AWS resources (initialized on cold start)
dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-2")


def lambda_handler(event, context):
    """
    Main Lambda handler for Naver booking SMS automation.

    Workflow (AC 1-8):
    1. Setup logging redaction (AC 1)
    2. Load configuration and credentials (AC 1)
    3. Authenticate with Naver using cached cookies (AC 2)
    4. Fetch confirmed and completed bookings (AC 3)
    5. Build rule-engine contexts for each booking (AC 4)
    6. Process bookings through rule engine (AC 5)
    7. Persist DynamoDB updates and send notifications (AC 6)
    8. Return structured response or error summary (AC 7, 8)

    Args:
        event: Lambda event (not used for scheduled execution)
        context: Lambda context

    Returns:
        dict: Status 200 with summary on success, 500 with error on failure
    """
    # ============================================================
    # AC 1: Bootstrap - Logging redaction and configuration
    # ============================================================
    try:
        setup_logging_redaction()
        logger.info("Starting Naver SMS automation Lambda handler")

        # Load settings and credentials
        settings = Settings()
        naver_creds = settings.load_naver_credentials()
        sens_creds = settings.load_sens_credentials()

        # Load stores configuration to get store IDs
        config_root = Path(__file__).resolve().parents[1] / "config"
        stores_path = config_root / "stores.yaml"
        with stores_path.open("r", encoding="utf-8") as f:
            stores_config = yaml.safe_load(f)

        store_ids = list(stores_config["stores"].keys())
        logger.info(f"Loaded {len(store_ids)} stores from configuration")

        # ============================================================
        # AC 2: Authentication - Naver login with cookie reuse (with resource cleanup)
        # ============================================================
        session_mgr = SessionManager(dynamodb)
        cached_cookies = session_mgr.get_cookies()

        logger.info(f"Cached cookies: {len(cached_cookies) if cached_cookies else 0} found")

        authenticator = NaverAuthenticator(
            username=naver_creds["username"],
            password=naver_creds["password"],
            session_manager=session_mgr,
        )

        try:
            cookies = authenticator.login(cached_cookies=cached_cookies)
            logger.info(f"Authentication successful: {len(cookies)} cookies")

            api_session = authenticator.get_session()

            # ============================================================
            # AC 3: Booking retrieval orchestration
            # ============================================================
            booking_api = NaverBookingAPIClient(
                session=api_session, option_keywords=["네이버", "인스타", "원본"]
            )

            # Fetch confirmed (RC03) bookings
            confirmed_bookings = booking_api.get_all_confirmed_bookings(store_ids)
            logger.info(f"Fetched {len(confirmed_bookings)} confirmed bookings")

            # Fetch completed (RC08) bookings
            completed_bookings = booking_api.get_all_completed_bookings(store_ids)
            logger.info(f"Fetched {len(completed_bookings)} completed bookings")

            # Combine all bookings
            all_bookings = confirmed_bookings + completed_bookings
            logger.info(f"Total bookings to process: {len(all_bookings)}")

            # ============================================================
            # AC 5: Rule engine setup and executor registration
            # ============================================================
            # Initialize rule engine
            rules_path = config_root / "rules.yaml"
            engine = RuleEngine(str(rules_path))

            # Register condition evaluators
            register_conditions(engine, settings)

            # Register action executors with services bundle
            booking_repo = BookingRepository(table_name="sms", dynamodb_resource=dynamodb)
            sms_service = SensSmsClient(settings=settings, credentials=sens_creds)

            # Initialize Slack services if enabled (Story 6.2, 6.1)
            # CRITICAL FIX: Slack is now independent from SMS settings
            # - Slack uses SLACK_ENABLED (global config)
            # - SMS uses settings.sens_delivery_enabled (approval gate)
            # These are now completely decoupled (AC1/AC3)
            slack_enabled = SLACK_ENABLED
            slack_service = None
            slack_template_loader = None

            if slack_enabled:
                try:
                    slack_webhook_url = Settings.load_slack_webhook_url()
                    if slack_webhook_url:
                        slack_service = SlackWebhookClient(
                            webhook_url=slack_webhook_url, logger=logger
                        )
                        slack_template_loader = SlackTemplateLoader(logger=logger)
                        logger.info("Slack services initialized and enabled")
                    else:
                        logger.warning(
                            "Slack enabled but webhook URL not configured; disabling Slack"
                        )
                        slack_enabled = False
                except Exception as e:
                    logger.error(f"Failed to initialize Slack services: {e}; disabling Slack")
                    slack_enabled = False

            services_bundle = ActionServicesBundle(
                db_repo=booking_repo,
                sms_service=sms_service,
                logger=logger,
                settings_dict={"slack_enabled": slack_enabled},
                slack_service=slack_service,
                slack_template_loader=slack_template_loader,
            )

            register_actions(engine, services_bundle)

            logger.info("Rule engine initialized with conditions and actions")

            # ============================================================
            # AC 4, 5, 6: Process bookings through rule engine
            # ============================================================
            all_results, summary = process_all_bookings(
                bookings=all_bookings, engine=engine, booking_repo=booking_repo, settings=settings
            )

            logger.info(
                f"Processing complete: {summary['bookings_processed']} bookings processed, "
                f"{summary['actions_executed']} actions executed, "
                f"{summary['actions_succeeded']} succeeded, {summary['actions_failed']} failed"
            )

            # ============================================================
            # AC 6: Send summary notification (Telegram)
            # ============================================================
            try:
                telegram_creds = settings.load_telegram_credentials()
                send_telegram_summary(
                    telegram_creds=telegram_creds, summary=summary, all_results=all_results
                )
            except Exception as e:
                logger.warning(f"Failed to send Telegram summary: {e}")

            # ============================================================
            # AC 7: Return success response
            # ============================================================
            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "message": "Naver SMS automation completed successfully",
                        "bookings_processed": summary["bookings_processed"],
                        "actions_executed": summary["actions_executed"],
                        "actions_succeeded": summary["actions_succeeded"],
                        "actions_failed": summary["actions_failed"],
                        "sms_sent": summary["sms_sent"],
                        "timestamp": datetime.now().isoformat(),
                    }
                ),
            }

        finally:
            # QA Fix: Always cleanup Selenium resources, even on errors
            authenticator.cleanup()

    except Exception as e:
        # ============================================================
        # AC 8: Error handling with logging and notification
        # ============================================================
        logger.error(f"Lambda handler failed: {e}", error=str(e))

        # Send error notification
        try:
            settings = Settings()
            telegram_creds = settings.load_telegram_credentials()
            notify_telegram_error(telegram_creds, str(e))
        except Exception as notify_err:
            logger.error(f"Failed to send error notification: {notify_err}")

        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "error": "Lambda execution failed",
                    "message": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
            ),
        }


def _build_expert_correction_roster(bookings: List[Booking]) -> List[Dict[str, Any]]:
    """
    Build Slack digest roster for bookings that include expert correction requests.

    Args:
        bookings: Combined list of Booking objects processed in this run.

    Returns:
        List of dictionaries ready for Slack template rendering.
    """
    roster: List[Dict[str, Any]] = []

    for booking in bookings:
        if not getattr(booking, "has_pro_edit_option", False):
            continue

        roster.append(
            {
                "name": booking.name,
                "phone_masked": booking.phone_masked,
                "pro_edit_count": getattr(booking, "pro_edit_count", 0) or 0,
            }
        )

    return roster


def _get_holiday_event_rule_window(engine: RuleEngine) -> Optional[Dict[str, Any]]:
    """
    Extract date range and option thresholds for the Holiday Event rule.
    """
    for rule in getattr(engine, "rules", []):
        if rule.name != "Holiday Event Customer List":
            continue

        window: Dict[str, Any] = {}

        for condition in rule.conditions:
            if condition.type == "date_range":
                window.update(condition.params or {})
            elif condition.type == "has_multiple_options":
                params = condition.params or {}
                if "min_count" in params:
                    window["min_count"] = params.get("min_count")

        return window

    return None


def _parse_rule_date(value: Optional[str]) -> Optional[date]:
    """
    Parse YYYY-MM-DD strings from rule configuration into date objects.
    """
    if not value:
        return None

    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        logger.warning(f"Ignored invalid holiday event date in rules configuration: {value}")
        return None


def _build_holiday_event_roster(
    bookings: List[Booking], engine: RuleEngine
) -> List[Dict[str, Any]]:
    """
    Build Slack roster for holiday/event marketing rule using rule windows.
    """
    window = _get_holiday_event_rule_window(engine)
    if not window:
        return []

    start_date = _parse_rule_date(window.get("start_date"))
    end_date = _parse_rule_date(window.get("end_date"))
    min_count = int(window.get("min_count", 0) or 0)

    roster: List[Dict[str, Any]] = []

    for booking in bookings:
        reserve_at = getattr(booking, "reserve_at", None)
        if reserve_at is None:
            continue

        booking_date = reserve_at.date()
        if start_date and booking_date < start_date:
            continue
        if end_date and booking_date > end_date:
            continue

        option_keywords = getattr(booking, "option_keywords", []) or []
        if min_count and len(option_keywords) < min_count:
            continue

        roster.append(
            {
                "name": booking.name,
                "phone_masked": booking.phone_masked,
                "reserve_at": booking_date.strftime("%Y-%m-%d"),
                "option_keywords": option_keywords,
            }
        )

    return roster


def process_all_bookings(
    bookings: List[Booking], engine: RuleEngine, booking_repo: BookingRepository, settings: Settings
) -> Tuple[List[ActionResult], Dict[str, Any]]:
    """
    Process all bookings through rule engine.

    Implements AC 4, 5, 6:
    - Build rule-engine-ready contexts (AC 4)
    - Execute rule engine and collect results (AC 5)
    - Track summary statistics (AC 6)

    Args:
        bookings: List of Booking domain objects
        engine: Initialized RuleEngine with registered conditions/actions
        booking_repo: BookingRepository for fetching DB records
        settings: Settings instance for context

    Returns:
        Tuple of (all_results, summary_dict)
    """
    all_results: List[ActionResult] = []
    current_time = datetime.now()

    # Summary statistics
    summary = {
        "bookings_processed": 0,
        "actions_executed": 0,
        "actions_succeeded": 0,
        "actions_failed": 0,
        "sms_sent": 0,
    }

    expert_correction_roster = _build_expert_correction_roster(bookings)
    holiday_event_roster = _build_holiday_event_roster(bookings, engine)

    for booking in bookings:
        try:
            # ============================================================
            # AC 4: Build rule-engine-ready context
            # ============================================================
            # Fetch existing DB record (if any)
            db_record = booking_repo.get_booking(booking.booking_num, booking.phone)

            # Build context dict
            context = {
                "booking": booking,
                "db_record": db_record,
                "current_time": current_time,
                "settings": settings,
                "db_repo": booking_repo,
                "bookings_with_expert_correction": expert_correction_roster,
                "bookings_in_date_range": holiday_event_roster,
            }

            logger.debug(
                f"Processing booking {booking.booking_num}",
                context={"has_db_record": db_record is not None},
            )

            # ============================================================
            # AC 5: Execute rule engine
            # ============================================================
            results = engine.process_booking(context)
            all_results.extend(results)

            # Update summary statistics
            summary["bookings_processed"] += 1
            summary["actions_executed"] += len(results)

            for result in results:
                if result.success:
                    summary["actions_succeeded"] += 1
                    if result.action_type == "send_sms":
                        summary["sms_sent"] += 1
                else:
                    summary["actions_failed"] += 1

        except Exception as e:
            logger.error(f"Failed to process booking {booking.booking_num}: {e}", error=str(e))
            summary["actions_failed"] += 1

    return all_results, summary


def send_telegram_summary(
    telegram_creds: Dict[str, str], summary: Dict[str, Any], all_results: List[ActionResult]
) -> None:
    """
    Send summary notification to Telegram.

    Implements AC 6 notification contract.

    Args:
        telegram_creds: Dict with 'bot_token' and 'chat_id'
        summary: Summary statistics dict
        all_results: List of ActionResult objects
    """
    bot_token = telegram_creds["bot_token"]
    chat_id = telegram_creds["chat_id"]

    # Build message
    message = (
        f"📊 Naver SMS Automation Summary\n\n"
        f"✅ Bookings Processed: {summary['bookings_processed']}\n"
        f"🔧 Actions Executed: {summary['actions_executed']}\n"
        f"✔️ Actions Succeeded: {summary['actions_succeeded']}\n"
        f"❌ Actions Failed: {summary['actions_failed']}\n"
        f"📨 SMS Sent: {summary['sms_sent']}\n"
        f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    # Send to Telegram
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info("Telegram summary sent successfully")
    except requests.RequestException as e:
        logger.error(f"Failed to send Telegram summary: {e}")
        raise


def notify_telegram_error(telegram_creds: Dict[str, str], error_message: str) -> None:
    """
    Send error notification to Telegram.

    Implements AC 8 error notification contract.

    Args:
        telegram_creds: Dict with 'bot_token' and 'chat_id'
        error_message: Error description
    """
    bot_token = telegram_creds["bot_token"]
    chat_id = telegram_creds["chat_id"]

    message = (
        f"🚨 Naver SMS Automation Error\n\n"
        f"Error: {error_message}\n"
        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info("Telegram error notification sent")
    except requests.RequestException as e:
        logger.error(f"Failed to send Telegram error notification: {e}")


if __name__ == "__main__":
    """
    Local testing entry point.

    Simulates Lambda execution environment with mock context.
    """

    class MockContext:
        def __init__(self):
            self.function_name = "naver-sms-automation"
            self.request_id = "local-test"
            self.invoked_function_arn = "arn:aws:lambda:local:local"

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    result = lambda_handler({}, MockContext())
    print(json.dumps(result, indent=2))
