"""
Validation script for verifying Secrets Manager configuration.

Usage examples:
    python scripts/validate_secrets.py --profile naver-prod
    python scripts/validate_secrets.py --assume-role-arn arn:aws:iam::654654307503:role/naver-sms-automation-lambda-role
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Set

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError


DEFAULT_REGION = "ap-northeast-2"
DEFAULT_NAMESPACE = "naver-sms-automation"


@dataclass(frozen=True)
class SecretExpectation:
    """Defines the required structure for a secret."""

    name: str
    required_keys: Sequence[str]
    description: str

    @property
    def fully_qualified_name(self) -> str:
        return f"{DEFAULT_NAMESPACE}/{self.name}"


EXPECTED_SECRETS: Sequence[SecretExpectation] = (
    SecretExpectation(
        name="naver-credentials",
        required_keys=("username", "password"),
        description="Naver portal login credentials",
    ),
    SecretExpectation(
        name="sens-credentials",
        required_keys=("access_key", "secret_key", "service_id"),
        description="Naver Cloud SENS API credentials",
    ),
    SecretExpectation(
        name="telegram-credentials",
        required_keys=("bot_token", "chat_id"),
        description="Telegram bot credentials for operational alerts",
    ),
)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate AWS Secrets Manager configuration for the naver-sms-automation project."
    )
    parser.add_argument(
        "--profile",
        help="AWS CLI profile to use for the base session.",
    )
    parser.add_argument(
        "--region",
        default=DEFAULT_REGION,
        help=f"AWS region to target (default: {DEFAULT_REGION}).",
    )
    parser.add_argument(
        "--assume-role-arn",
        help="Optional IAM role ARN to assume before performing validation (e.g., Lambda execution role).",
    )
    parser.add_argument(
        "--role-session-name",
        default="SecretsValidationSession",
        help="Session name to use when assuming the IAM role.",
    )
    parser.add_argument(
        "--namespace",
        default=DEFAULT_NAMESPACE,
        help=f"Secrets namespace prefix (default: {DEFAULT_NAMESPACE}).",
    )
    parser.add_argument(
        "--expected-principals",
        nargs="+",
        metavar="ARN",
        help="Optional list of IAM principal ARNs that should have access to the secrets (Lambda and CI roles).",
    )

    return parser.parse_args(argv)


def create_session(region: str, profile: Optional[str], assume_role_arn: Optional[str], session_name: str):
    try:
        base_session = boto3.Session(profile_name=profile, region_name=region)
    except (BotoCoreError, NoCredentialsError) as exc:
        raise RuntimeError(f"Failed to create base AWS session: {exc}") from exc

    if not assume_role_arn:
        return base_session

    sts = base_session.client("sts")
    try:
        response = sts.assume_role(RoleArn=assume_role_arn, RoleSessionName=session_name)
    except ClientError as exc:
        raise RuntimeError(f"Failed to assume role {assume_role_arn}: {exc}") from exc

    credentials = response["Credentials"]
    return boto3.Session(
        aws_access_key_id=credentials["AccessKeyId"],
        aws_secret_access_key=credentials["SecretAccessKey"],
        aws_session_token=credentials["SessionToken"],
        region_name=region,
    )


def _format_principals(principal_node) -> Set[str]:
    """Normalise Principals/NotPrincipals from a resource policy."""
    if principal_node is None:
        return set()
    if isinstance(principal_node, str):
        return {principal_node}
    if isinstance(principal_node, list):
        return set(principal_node)
    if isinstance(principal_node, dict):
        # Handle forms like {"AWS": "..."} or {"AWS": ["...", "..."]}
        identifiers: Set[str] = set()
        for value in principal_node.values():
            identifiers.update(_format_principals(value))
        return identifiers
    return set()


def validate_resource_policy(policy_text: str, expected_principals: Iterable[str]) -> List[str]:
    """Validate that the resource policy restricts principals to the expected list."""
    issues: List[str] = []
    if not policy_text:
        issues.append("No resource policy attached to secret.")
        return issues

    try:
        document = json.loads(policy_text)
    except json.JSONDecodeError as exc:
        issues.append(f"Resource policy is not valid JSON: {exc}")
        return issues

    principals_set: Set[str] = set()
    not_principals_set: Set[str] = set()

    for statement in document.get("Statement", []):
        effect = statement.get("Effect", "Allow")
        if effect == "Allow":
            principals_set.update(_format_principals(statement.get("Principal")))
        elif effect == "Deny":
            not_principals_set.update(_format_principals(statement.get("NotPrincipal")))

    expected_set = set(expected_principals)
    if expected_set and principals_set:
        missing = expected_set - principals_set
        if missing:
            issues.append(f"Allowed principals missing from Allow statement: {', '.join(sorted(missing))}")

    if expected_set and not_principals_set:
        unexpected_notprincipal = not_principals_set - expected_set
        if unexpected_notprincipal:
            issues.append(
                "Deny statement NotPrincipal contains unexpected ARNs: "
                + ", ".join(sorted(unexpected_notprincipal))
            )

    if expected_set and not not_principals_set:
        issues.append("Deny statement with NotPrincipal is missing; policy may allow unintended principals.")

    return issues


def validate_secret(client, expectation: SecretExpectation, namespace: str, expected_principals: Optional[Iterable[str]]):
    qualified_name = f"{namespace}/{expectation.name}"

    try:
        client.describe_secret(SecretId=qualified_name)
    except ClientError as exc:
        return False, [f"Secret {qualified_name} not found or not accessible: {exc}"]

    try:
        secret_response = client.get_secret_value(SecretId=qualified_name)
    except ClientError as exc:
        return False, [f"Failed to retrieve secret value for {qualified_name}: {exc}"]

    try:
        payload = json.loads(secret_response.get("SecretString", "{}"))
    except json.JSONDecodeError as exc:
        return False, [f"Secret {qualified_name} does not contain valid JSON: {exc}"]

    missing_keys = [key for key in expectation.required_keys if key not in payload]
    if missing_keys:
        return False, [f"Secret {qualified_name} missing keys: {', '.join(missing_keys)}"]

    issues: List[str] = []

    if expected_principals:
        try:
            policy_response = client.get_resource_policy(SecretId=qualified_name)
            policy_text = policy_response.get("ResourcePolicy")
        except ClientError as exc:
            return False, [f"Failed to fetch resource policy for {qualified_name}: {exc}"]

        issues.extend(validate_resource_policy(policy_text, expected_principals))

    return len(issues) == 0, issues


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    try:
        session = create_session(
            region=args.region,
            profile=args.profile,
            assume_role_arn=args.assume_role_arn,
            session_name=args.role_session_name,
        )
    except RuntimeError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    client = session.client("secretsmanager")

    expected_principals = args.expected_principals or []
    overall_success = True

    print(f"Validating secrets in namespace '{args.namespace}' (region: {args.region})")
    if args.assume_role_arn:
        print(f"- Using assumed role: {args.assume_role_arn}")
    if expected_principals:
        print("- Expected principals:")
        for principal in expected_principals:
            print(f"  - {principal}")

    for expectation in EXPECTED_SECRETS:
        success, issues = validate_secret(client, expectation, args.namespace, expected_principals)
        status = "PASS" if success else "FAIL"
        print(f"\n[{status}] {expectation.fully_qualified_name}")
        print(f"  Description: {expectation.description}")
        if issues:
            for issue in issues:
                print(f"  - {issue}")
            overall_success = False
        else:
            print(f"  - Contains required keys: {', '.join(expectation.required_keys)}")
            print("  - Secret value is valid JSON")
            if expected_principals:
                print("  - Resource policy restricts principals as expected")

    return 0 if overall_success else 1


if __name__ == "__main__":
    sys.exit(main())
