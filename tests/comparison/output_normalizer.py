"""
Output Normalizer - Normalize outputs from both implementations for comparison

Story 4.2 Task 2: Implements AC 2, 3 (Output normalization and diffing)
"""

import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class OutputNormalizer:
    """
    Normalize outputs from legacy and refactored implementations.
    
    Responsibilities:
    - Convert legacy output formats to canonical form
    - Normalize refactored output formats to canonical form
    - Handle SMS, DynamoDB, and Telegram outputs
    - Ensure stable ordering for deterministic comparison
    """

    @staticmethod
    def normalize_sms_outputs(sms_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Normalize SMS outputs to canonical form.
        
        Canonical SMS record:
        {
            "type": "confirm|guide|event",
            "phone": "phone_number",
            "template": "template_name",
            "store_specific": bool,
            "timestamp": "ISO timestamp"
        }
        
        Args:
            sms_list: List of SMS send records
            
        Returns:
            Normalized and sorted SMS records
        """
        normalized = []

        for sms in sms_list:
            normalized_sms = {
                "type": sms.get("type") or sms.get("sms_type") or "unknown",
                "phone": sms.get("phone"),
                "template": sms.get("template") or sms.get("sms_type"),
                "store_specific": sms.get("store_specific", False),
                "timestamp": sms.get("timestamp") or datetime.now().isoformat(),
            }
            normalized.append(normalized_sms)

        # Sort for stable comparison
        return sorted(normalized, key=lambda x: (x["phone"], x["type"]))

    @staticmethod
    def normalize_dynamodb_outputs(db_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Normalize DynamoDB outputs to canonical form.
        
        Canonical DB record:
        {
            "booking_num": "biz_id_book_id",
            "phone": "phone_number",
            "confirm_sms": bool,
            "remind_sms": bool,
            "option_sms": bool,
            "created_at": "ISO timestamp"
        }
        
        Args:
            db_records: List of DynamoDB records
            
        Returns:
            Normalized and sorted records
        """
        normalized = []

        for record in db_records:
            normalized_record = {
                "booking_num": record.get("booking_num"),
                "phone": record.get("phone"),
                "confirm_sms": bool(record.get("confirm_sms")),
                "remind_sms": bool(record.get("remind_sms")),
                "option_sms": bool(record.get("option_sms")),
                "created_at": record.get("created_at") or datetime.now().isoformat(),
            }
            normalized.append(normalized_record)

        # Sort for stable comparison
        return sorted(normalized, key=lambda x: (x["booking_num"], x["phone"]))

    @staticmethod
    def normalize_telegram_outputs(telegram_messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Normalize Telegram outputs to canonical form.
        
        Canonical Telegram record:
        {
            "chat_id": "chat_id",
            "message_type": "summary|error|notification",
            "timestamp": "ISO timestamp",
            "content_hash": "hash of message content"
        }
        
        Args:
            telegram_messages: List of Telegram messages
            
        Returns:
            Normalized messages (without content for idempotency)
        """
        normalized = []

        for msg in telegram_messages:
            normalized_msg = {
                "chat_id": msg.get("chat_id"),
                "message_type": msg.get("message_type") or "notification",
                "timestamp": msg.get("timestamp") or datetime.now().isoformat(),
            }
            normalized.append(normalized_msg)

        # Sort for stable comparison
        return sorted(normalized, key=lambda x: (x["chat_id"], x["timestamp"]))

    @staticmethod
    def normalize_action_results(actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Normalize action execution results.
        
        Canonical action result:
        {
            "action_type": "send_sms|create_db_record|update_flag|send_telegram",
            "success": bool,
            "message": "result message",
            "params": {optional params}
        }
        
        Args:
            actions: List of action results
            
        Returns:
            Normalized action results
        """
        normalized = []

        for action in actions:
            normalized_action = {
                "action_type": action.get("action_type"),
                "success": bool(action.get("success")),
                "message": action.get("message") or "",
                "params": action.get("params") or {},
            }
            normalized.append(normalized_action)

        # Sort for stable comparison
        return sorted(normalized, key=lambda x: x["action_type"])

    @staticmethod
    def normalize_handler_response(response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize Lambda handler response.
        
        Args:
            response: Handler response dict
            
        Returns:
            Normalized response with extracted fields
        """
        return {
            "status_code": response.get("statusCode"),
            "bookings_processed": response.get("bookings_processed"),
            "actions_executed": response.get("actions_executed"),
            "actions_succeeded": response.get("actions_succeeded"),
            "actions_failed": response.get("actions_failed"),
            "sms_sent": response.get("sms_sent"),
            "error": response.get("error"),
        }

    @staticmethod
    def canonicalize_all_outputs(
        legacy_outputs: Dict[str, Any],
        refactored_outputs: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Canonicalize all outputs from both implementations.
        
        Args:
            legacy_outputs: Dict with sms, db_records, telegram, actions
            refactored_outputs: Dict with same structure
            
        Returns:
            Tuple of (canonical_legacy, canonical_refactored)
        """
        canonical_legacy = {
            "sms": OutputNormalizer.normalize_sms_outputs(
                legacy_outputs.get("sms", [])
            ),
            "db_records": OutputNormalizer.normalize_dynamodb_outputs(
                legacy_outputs.get("db_records", [])
            ),
            "telegram": OutputNormalizer.normalize_telegram_outputs(
                legacy_outputs.get("telegram", [])
            ),
            "actions": OutputNormalizer.normalize_action_results(
                legacy_outputs.get("actions", [])
            ),
        }

        canonical_refactored = {
            "sms": OutputNormalizer.normalize_sms_outputs(
                refactored_outputs.get("sms", [])
            ),
            "db_records": OutputNormalizer.normalize_dynamodb_outputs(
                refactored_outputs.get("db_records", [])
            ),
            "telegram": OutputNormalizer.normalize_telegram_outputs(
                refactored_outputs.get("telegram", [])
            ),
            "actions": OutputNormalizer.normalize_action_results(
                refactored_outputs.get("actions", [])
            ),
        }

        return canonical_legacy, canonical_refactored
