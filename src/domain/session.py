"""
Session domain model for Naver login cookie caching.

Manages the lifecycle of Selenium WebDriver cookies stored in DynamoDB
for session reuse across Lambda invocations.
"""

import json
from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class Session:
    """
    Session domain model for cached Naver login cookies.

    Attributes:
        id: Session ID (always '1' for single-record design in current implementation)
        cookies: JSON string representation of Selenium cookies

    Design Note:
        DynamoDB session table uses a single record (id='1') currently.
        This design supports potential future expansion to multi-record sessions
        via the get_field/set_field pattern, similar to Booking model.
    """

    id: str
    cookies: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        """
        Create Session from dictionary (e.g., from DynamoDB response).

        Args:
            data: Dictionary with session data

        Returns:
            Session instance
        """
        return cls(id=data.get("id", "1"), cookies=data.get("cookies", "[]"))

    @classmethod
    def from_cookies_list(cls, cookies_list: List[Dict[str, Any]]) -> "Session":
        """
        Create Session from Selenium cookies list.

        Args:
            cookies_list: List of cookie dicts from WebDriver.get_cookies()

        Returns:
            Session instance with cookies serialized to JSON
        """
        cookies_json = json.dumps(cookies_list)
        return cls(id="1", cookies=cookies_json)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert Session to dictionary for DynamoDB storage.

        Returns:
            Dictionary representation
        """
        return {"id": self.id, "cookies": self.cookies}

    def get_cookies_list(self) -> List[Dict[str, Any]]:
        """
        Parse cookies JSON string back to list of cookie dicts.

        Useful for adding cookies back to a WebDriver:
            cookies = session.get_cookies_list()
            for cookie in cookies:
                driver.add_cookie(cookie)

        Returns:
            List of cookie dictionaries

        Raises:
            json.JSONDecodeError: If cookies JSON is malformed
        """
        try:
            return json.loads(self.cookies)  # type: ignore[no-any-return]
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse cookies JSON: {e}")

    def is_empty(self) -> bool:
        """
        Check if session has no cookies (empty or default state).

        Returns:
            True if cookies list is empty
        """
        try:
            cookies = self.get_cookies_list()
            return len(cookies) == 0
        except (ValueError, json.JSONDecodeError):
            return True
