"""
Booking domain model.

Represents a customer booking with SMS tracking flags.
Designed to support dynamic field expansion for future requirements.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any


@dataclass
class Booking:
    """
    Booking domain model with SMS tracking state.

    Attributes:
        booking_num: Composite key "{biz_id}_{book_id}" (partition key)
        phone: Customer phone number "010-XXXX-XXXX" (sort key)
        name: Customer name
        booking_time: Booking datetime as "YYYY-MM-DD HH:MM:SS" string
        confirm_sms: Flag indicating confirmation SMS was sent
        remind_sms: Flag indicating 2-hour reminder SMS was sent
        option_sms: Flag indicating event/option SMS was sent
        option_time: Reserved field (currently unused)

    Future fields (to be added in later stories):
        - customer_id: Naver member ID
        - visit_count: Number of previous visits
        - booking_amount: Total booking cost
        - booking_source: 'web', 'mobile_app', 'phone', etc.
        - customer_age_group: '10s', '20s', '30s', etc.
        - customer_gender: 'M', 'F', 'N'
        - special_requests: Customer notes
        - payment_method: 'card', 'cash', 'npay'

    Design Note:
        This model uses a generic `extra_fields` dict to support future expansion
        without requiring schema changes. Additional fields provided by the business
        team will be stored there.
    """

    booking_num: str
    phone: str
    name: str
    booking_time: str
    confirm_sms: bool
    remind_sms: bool
    option_sms: bool
    option_time: str = ""
    extra_fields: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Booking":
        """
        Create Booking from dictionary (e.g., from DynamoDB response).

        Handles both legacy format (8 core fields) and future formats with
        additional fields. Extra fields are stored in extra_fields dict.

        Args:
            data: Dictionary with booking data

        Returns:
            Booking instance
        """
        # Known core fields
        core_fields = {
            "booking_num",
            "phone",
            "name",
            "booking_time",
            "confirm_sms",
            "remind_sms",
            "option_sms",
            "option_time",
        }

        # Extract core fields
        core_data = {k: v for k, v in data.items() if k in core_fields}

        # Extract extra fields (for future expansion)
        extra_data = {k: v for k, v in data.items() if k not in core_fields}

        return cls(**core_data, extra_fields=extra_data)

    def to_dict(self, include_extra: bool = True) -> Dict[str, Any]:
        """
        Convert Booking to dictionary for DynamoDB storage.

        Args:
            include_extra: If True, include extra_fields in output

        Returns:
            Dictionary representation
        """
        data = asdict(self)
        if not include_extra:
            data.pop("extra_fields", None)
        else:
            # Flatten extra_fields into top-level dict
            extra = data.pop("extra_fields", {})
            data.update(extra)

        return data

    def get_field(self, field_name: str, default: Any = None) -> Any:
        """
        Get field value with support for dynamic fields.

        This allows checking both core fields and dynamically-added fields
        without knowing the full schema ahead of time.

        Args:
            field_name: Field name to retrieve
            default: Default value if field not found

        Returns:
            Field value or default
        """
        # Check core fields first
        if hasattr(self, field_name):
            return getattr(self, field_name)

        # Check extra fields
        return self.extra_fields.get(field_name, default)

    def set_field(self, field_name: str, value: Any):
        """
        Set field value with support for dynamic fields.

        Args:
            field_name: Field name to set
            value: Value to set
        """
        # Check if it's a core field
        core_fields = {
            "booking_num",
            "phone",
            "name",
            "booking_time",
            "confirm_sms",
            "remind_sms",
            "option_sms",
            "option_time",
        }

        if field_name in core_fields:
            setattr(self, field_name, value)
        else:
            # Store in extra_fields
            self.extra_fields[field_name] = value
