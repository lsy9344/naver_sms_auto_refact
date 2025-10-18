"""
Lambda Handler - Main entry point for Naver SMS automation

Integrates NaverAuthenticator for authentication and uses authenticated
session for booking API calls.
"""

import json
import logging
import boto3
from datetime import datetime, timedelta

from auth.naver_login import NaverAuthenticator
from auth.session_manager import SessionManager

logger = logging.getLogger(__name__)

# AWS clients
dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-2')
sms_table = dynamodb.Table('sms')
session_table = dynamodb.Table('session')


class Settings:
    """Load configuration from Secrets Manager"""

    @staticmethod
    def load():
        """Load Naver credentials from AWS Secrets Manager"""
        import boto3
        
        secrets_client = boto3.client('secretsmanager', region_name='ap-northeast-2')
        
        try:
            secret = secrets_client.get_secret_value(SecretId='naver/credentials')
            credentials = json.loads(secret['SecretString'])
            return credentials
        except Exception as e:
            logger.error(f"Failed to load credentials: {e}")
            raise


def lambda_handler(event, context):
    """
    Main Lambda handler for Naver booking SMS automation.

    Workflow:
    1. Load Naver credentials from Secrets Manager
    2. Authenticate with Naver (use cached cookies or fresh login)
    3. Get authenticated requests.Session
    4. Fetch booking data from Naver API
    5. Process bookings and send SMS notifications
    6. Return results

    Args:
        event: Lambda event (not used for scheduled execution)
        context: Lambda context

    Returns:
        dict: Status and results
    """
    try:
        logger.info("Starting Naver SMS automation")

        # 1. Load configuration
        settings = Settings.load()
        
        # 2. Initialize session manager (for DynamoDB cookie storage)
        session_mgr = SessionManager(dynamodb)

        # 3. Get cached cookies if available
        cached_cookies = session_mgr.get_cookies()
        logger.info(f"Cached cookies: {len(cached_cookies) if cached_cookies else 0}")

        # 4. Initialize authenticator
        authenticator = NaverAuthenticator(
            username=settings['naver_username'],
            password=settings['naver_password'],
            session_manager=session_mgr
        )

        # 5. Authenticate (uses cached cookies or fresh login)
        cookies = authenticator.login(cached_cookies=cached_cookies)
        logger.info(f"Authentication successful: {len(cookies)} cookies")

        # 6. Get authenticated requests.Session for API calls
        api_session = authenticator.get_session()

        # 7. Fetch booking data from Naver API
        # (Implementation depends on booking API structure)
        user_data = fetch_bookings(api_session, settings)
        logger.info(f"Fetched {len(user_data)} bookings")

        # 8. Process bookings and send SMS
        sms_results = process_bookings(user_data)
        logger.info(f"SMS processing complete: {len(sms_results)} results")

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


def fetch_bookings(session, settings):
    """
    Fetch booking data from Naver API.

    Args:
        session: Authenticated requests.Session with Naver cookies
        settings: Configuration settings

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
    print(json.dumps(result, indent=2))
