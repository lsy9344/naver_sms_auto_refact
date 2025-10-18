"""
Infrastructure tests for Secrets Manager configuration.

These tests verify:
- Secrets exist in the expected namespace
- Secret payloads contain the required keys
- Resource policies restrict access to Lambda and CI roles only

Tests require AWS credentials with permissions to read Secrets Manager metadata.
They will be skipped automatically when credentials are not available.
"""

import json
from typing import Dict, Set

import boto3
import pytest
from botocore.exceptions import ClientError, EndpointConnectionError, NoCredentialsError


REGION = "ap-northeast-2"
NAMESPACE = "naver-sms-automation"
EXPECTED_PRINCIPALS = {
    "arn:aws:iam::654654307503:role/naver-sms-automation-lambda-role",
    "arn:aws:iam::654654307503:role/naver-sms-automation-ci-role",
}

SECRETS: Dict[str, Set[str]] = {
    f"{NAMESPACE}/naver-credentials": {"username", "password"},
    f"{NAMESPACE}/sens-credentials": {"access_key", "secret_key", "service_id"},
    f"{NAMESPACE}/telegram-credentials": {"bot_token", "chat_id"},
}


def _check_aws_credentials() -> bool:
    try:
        session = boto3.Session()
        credentials = session.get_credentials()
        if credentials is None:
            return False

        sts = session.client("sts", region_name="us-east-1")
        sts.get_caller_identity()
        return True
    except (NoCredentialsError, EndpointConnectionError, ClientError):
        return False
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _check_aws_credentials(),
    reason="AWS credentials not available - skipping Secrets Manager infrastructure tests",
)


@pytest.fixture(scope="module")
def secrets_client():
    return boto3.client("secretsmanager", region_name=REGION)


def _normalise_principals(node) -> Set[str]:
    if node is None:
        return set()
    if isinstance(node, str):
        return {node}
    if isinstance(node, list):
        principals: Set[str] = set()
        for value in node:
            principals.update(_normalise_principals(value))
        return principals
    if isinstance(node, dict):
        principals: Set[str] = set()
        for value in node.values():
            principals.update(_normalise_principals(value))
        return principals
    return set()


def test_secrets_exist(secrets_client):
    for secret_name in SECRETS.keys():
        response = secrets_client.describe_secret(SecretId=secret_name)
        assert response["Name"] == secret_name


def test_secret_payload_schema(secrets_client):
    for secret_name, required_keys in SECRETS.items():
        response = secrets_client.get_secret_value(SecretId=secret_name)
        payload = json.loads(response["SecretString"])
        missing = required_keys - set(payload.keys())
        assert not missing, f"Secret {secret_name} missing keys: {', '.join(sorted(missing))}"


def test_secret_policy_restricts_principals(secrets_client):
    for secret_name in SECRETS.keys():
        try:
            response = secrets_client.get_resource_policy(SecretId=secret_name)
        except ClientError as exc:
            pytest.fail(f"Failed to fetch resource policy for {secret_name}: {exc}")

        policy_text = response.get("ResourcePolicy", "{}")
        policy = json.loads(policy_text)

        allow_principals: Set[str] = set()
        deny_not_principals: Set[str] = set()

        for statement in policy.get("Statement", []):
            effect = statement.get("Effect", "Allow")
            if effect == "Allow":
                allow_principals.update(_normalise_principals(statement.get("Principal")))
            elif effect == "Deny":
                deny_not_principals.update(_normalise_principals(statement.get("NotPrincipal")))

        for principal in EXPECTED_PRINCIPALS:
            assert principal in allow_principals, f"{principal} missing from Allow statement for {secret_name}"

        unexpected = deny_not_principals - EXPECTED_PRINCIPALS
        assert not unexpected, f"Unexpected NotPrincipal entries for {secret_name}: {', '.join(sorted(unexpected))}"

        assert deny_not_principals, f"Deny statement missing for {secret_name}"
