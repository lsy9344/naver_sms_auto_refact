"""
Session Manager - Handles DynamoDB cookie storage and retrieval
"""

import json
import logging

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Manages session cookies in DynamoDB.

    Handles persistence and retrieval of Naver authentication cookies
    to enable cookie reuse across Lambda invocations.
    """

    def __init__(self, dynamodb_resource):
        """
        Initialize SessionManager.

        Args:
            dynamodb_resource: boto3 DynamoDB resource.
        """
        self.dynamodb = dynamodb_resource
        self.table = self.dynamodb.Table("session")

    def get_cookies(self):
        """
        Retrieve cached cookies from DynamoDB.

        Returns:
            List of cookie dicts or None if no cookies exist
        """
        try:
            response = self.table.get_item(Key={"id": "1"})
            cookies_json = response["Item"]["cookies"]
            cookies = json.loads(cookies_json)
            logger.info(f"Retrieved {len(cookies)} cookies from DynamoDB")
            return cookies
        except KeyError:
            logger.info("No cached cookies found in DynamoDB")
            return None
        except Exception as e:
            logger.error(f"Error retrieving cookies: {e}")
            return None

    def put_item(self, Item: dict):
        """
        Minimal DynamoDB compatibility layer for preserved login code.

        Args:
            Item: DynamoDB item payload

        Returns:
            dict: Result from DynamoDB put_item
        """
        return self.table.put_item(Item=Item)

    def save_cookies(self, cookies_json: str) -> bool:
        """
        Save cookies to DynamoDB.

        Args:
            cookies_json: JSON string of cookies list

        Returns:
            True if successful, False otherwise
        """
        try:
            response = self.put_item({"id": "1", "cookies": cookies_json})

            http_status = response["ResponseMetadata"]["HTTPStatusCode"]
            if http_status == 200:
                logger.info("Cookies saved to DynamoDB successfully")
                return True
            else:
                logger.error(f"DynamoDB put_item failed with status {http_status}")
                return False
        except Exception as e:
            logger.error(f"Error saving cookies: {e}")
            return False

    def clear_cookies(self) -> bool:
        """
        Remove cached cookies from DynamoDB.

        Returns:
            True if cookies were deleted successfully, False otherwise.
        """
        try:
            response = self.table.delete_item(Key={"id": "1"})
            http_status = response["ResponseMetadata"]["HTTPStatusCode"]
            if http_status == 200:
                logger.info("Cleared cached cookies from DynamoDB")
                return True

            logger.warning(f"DynamoDB delete_item returned unexpected status {http_status}")
            return False
        except Exception as e:
            logger.error(f"Error clearing cached cookies: {e}")
            return False
