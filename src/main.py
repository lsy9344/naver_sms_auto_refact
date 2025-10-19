"""
Lambda Handler - Main entry point for Naver SMS automation

Integrates NaverAuthenticator for authentication and uses authenticated
session for booking API calls. Credentials are loaded from AWS Secrets Manager.
"""

import json
import logging
import boto3
from datetime import datetime

from .auth.naver_login import NaverAuthenticator
from .auth.session_manager import SessionManager
from .config.settings import (
    get_naver_credentials,
    setup_logging_redaction,
)
from .utils.logger import get_logger

logger = get_logger(__name__)

# AWS clients
dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-2')
sms_table = dynamodb.Table('sms')
session_table = dynamodb.Table('session')


def lambda_handler(event, context):
    """
    Main Lambda handler for Naver booking SMS automation.

    Workflow:
    1. Load credentials from Secrets Manager (cold start)
    2. Setup logging redaction for CloudWatch
    3. Authenticate with Naver (use cached cookies or fresh login)
    4. Get authenticated requests.Session
    5. Fetch booking data from Naver API
    6. Process bookings and send SMS notifications
    7. Return results

    Args:
        event: Lambda event (not used for scheduled execution)
        context: Lambda context

    Returns:
        dict: Status and results
    """
    try:
        # Setup logging redaction on cold start
        setup_logging_redaction()
        logger.info("Starting Naver SMS automation")

        # 1. Load credentials from Secrets Manager
        naver_creds = get_naver_credentials()

        # 2. Initialize session manager (for DynamoDB cookie storage)
        session_mgr = SessionManager(dynamodb)

        # 3. Get cached cookies if available
        cached_cookies = session_mgr.get_cookies()
        ccount = len(cached_cookies) if cached_cookies else 0
        logger.info(f"Cached cookies: {ccount}")

        # 4. Initialize authenticator
        authenticator = NaverAuthenticator(
            username=naver_creds['username'],
            password=naver_creds['password'],
            session_manager=session_mgr
        )

        # 5. Authenticate (uses cached cookies or fresh login)
        cookies = authenticator.login(cached_cookies=cached_cookies)
        cookie_count = len(cookies)
        logger.info(f"Authentication successful: {cookie_count} cookies")

        # 6. Get authenticated requests.Session for API calls
        api_session = authenticator.get_session()

        # 7. Fetch booking data from Naver API
        user_data = fetch_bookings(api_session)
        logger.info(f"Fetched {len(user_data)} bookings")

        # 8. Process bookings and send SMS
        sms_results = process_bookings(user_data)
        result_count = len(sms_results)
        logger.info(f"SMS processing complete: {result_count} results")

        # 9. Cleanup
        authenticator.cleanup()

        # 10. Return results
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Naver SMS automation completed',
                'bookings_processed': len(user_data),
                'sms_sent': len([r for r in sms_results if r['status'] == 'sent']),
                'timestamp': datetime.now().isoformat()
            })
        }

    except Exception as e:
        logger.error(f"Error in lambda_handler: {e}", exc_info=True)

        # Send error notification
        notify_error(str(e))

        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Lambda execution failed',
                'message': str(e),
                'timestamp': datetime.now().isoformat()
            })
        }


def fetch_bookings(session):
    """
    Fetch booking data from Naver API.

    Args:
        session: Authenticated requests.Session with Naver cookies

    Returns:
        list: Booking data from API
    """
    logger.info("Fetching bookings from Naver API")

    # TODO: Implement booking API calls
    # Use session.get() for authenticated requests
    # API endpoints documented in architecture.md

    return []


def process_bookings(user_data):
    """
    Process bookings and send SMS notifications.

    Args:
        user_data: List of booking data

    Returns:
        list: Processing results
    """
    logger.info(f"Processing {len(user_data)} bookings")

    results = []
    for booking in user_data:
        # TODO: Implement booking processing logic
        # Check SMS status, send notifications, update DynamoDB
        pass

    return results


def notify_error(error_message):
    """
    Send error notification (e.g., via Telegram).

    Args:
        error_message: Error description
    """
    logger.warning(f"Error notification: {error_message}")
    # TODO: Implement error notification
    # Could use Telegram API, SNS, CloudWatch, etc.


if __name__ == '__main__':
    # Local testing
    class MockContext:
        def __init__(self):
            self.function_name = 'naver-sms-automation'
            self.request_id = 'local-test'

    logging.basicConfig(level=logging.INFO)
    result = lambda_handler({}, MockContext())
    logger.info("Lambda handler result", context={"result": result})
    # For direct output, use logger instead of print
    import sys
    json.dump(result, sys.stdout, indent=2)
