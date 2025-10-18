"""
Infrastructure tests for ECR repository setup.

Tests verify:
- ECR repository exists with correct configuration
- Image scanning is enabled
- Lifecycle policy is configured
- IAM permissions are correct

Note: These tests require valid AWS credentials and access to the actual
ECR repository and IAM resources. Tests will be skipped in CI environments
without AWS credentials configured.
"""

import json
import os
import boto3
import pytest
from botocore.exceptions import NoCredentialsError, ClientError


# Constants
REPOSITORY_NAME = "naver-sms-automation"
REGION = "ap-northeast-2"
ACCOUNT_ID = "654654307503"
EXPECTED_IMAGE_COUNT_LIMIT = 5


def _check_aws_credentials():
    """Check if AWS credentials are available.

    Returns:
        bool: True if credentials are available, False otherwise.
    """
    try:
        # Try to get credentials from boto3 session
        session = boto3.Session()
        credentials = session.get_credentials()
        return credentials is not None
    except Exception:
        # Catch all exceptions to handle various credential errors gracefully
        return False


# Skip all tests in this module if AWS credentials are not available
pytestmark = pytest.mark.skipif(
    not _check_aws_credentials(),
    reason="AWS credentials not available - skipping infrastructure tests"
)


@pytest.fixture
def ecr_client():
    """Create ECR client for testing."""
    return boto3.client('ecr', region_name=REGION)


@pytest.fixture
def iam_client():
    """Create IAM client for testing.

    Note: IAM is a global service and does not use regional endpoints.
    """
    return boto3.client('iam')


def test_ecr_repository_exists(ecr_client):
    """Test that ECR repository exists with correct name."""
    response = ecr_client.describe_repositories(
        repositoryNames=[REPOSITORY_NAME]
    )

    assert len(response['repositories']) == 1
    repo = response['repositories'][0]
    assert repo['repositoryName'] == REPOSITORY_NAME


def test_ecr_repository_in_correct_region(ecr_client):
    """Test that ECR repository is in ap-northeast-2 region."""
    response = ecr_client.describe_repositories(
        repositoryNames=[REPOSITORY_NAME]
    )

    repo = response['repositories'][0]
    repo_arn = repo['repositoryArn']

    # Extract region from ARN: arn:aws:ecr:REGION:ACCOUNT:repository/NAME
    arn_parts = repo_arn.split(':')
    region = arn_parts[3]

    assert region == REGION


def test_image_scanning_enabled(ecr_client):
    """Test that image scanning on push is enabled."""
    response = ecr_client.describe_repositories(
        repositoryNames=[REPOSITORY_NAME]
    )

    repo = response['repositories'][0]
    assert repo['imageScanningConfiguration']['scanOnPush'] is True


def test_lifecycle_policy_configured(ecr_client):
    """Test that lifecycle policy keeps only latest 5 images."""
    response = ecr_client.get_lifecycle_policy(
        repositoryName=REPOSITORY_NAME
    )

    policy = json.loads(response['lifecyclePolicyText'])

    # Verify policy structure
    assert 'rules' in policy
    assert len(policy['rules']) > 0

    # Find the rule that keeps latest images
    keep_latest_rule = None
    for rule in policy['rules']:
        if rule['selection']['countType'] == 'imageCountMoreThan':
            keep_latest_rule = rule
            break

    assert keep_latest_rule is not None
    assert keep_latest_rule['selection']['countNumber'] == EXPECTED_IMAGE_COUNT_LIMIT
    assert keep_latest_rule['action']['type'] == 'expire'


def test_iam_ecr_access_policy_exists(iam_client):
    """Test that IAM policy for ECR access exists."""
    policy_arn = f"arn:aws:iam::{ACCOUNT_ID}:policy/NaverSmsAutomationECRAccessPolicy"

    response = iam_client.get_policy(PolicyArn=policy_arn)

    assert response['Policy']['PolicyName'] == 'NaverSmsAutomationECRAccessPolicy'
    assert response['Policy']['Arn'] == policy_arn


def test_iam_ecr_access_policy_permissions(iam_client):
    """Test that IAM policy has correct ECR permissions."""
    policy_arn = f"arn:aws:iam::{ACCOUNT_ID}:policy/NaverSmsAutomationECRAccessPolicy"

    # Get the policy
    response = iam_client.get_policy(PolicyArn=policy_arn)
    default_version_id = response['Policy']['DefaultVersionId']

    # Get the policy version (actual policy document)
    version_response = iam_client.get_policy_version(
        PolicyArn=policy_arn,
        VersionId=default_version_id
    )

    policy_document = version_response['PolicyVersion']['Document']

    # Verify required permissions
    required_actions = {
        'ecr:GetDownloadUrlForLayer',
        'ecr:BatchGetImage',
        'ecr:BatchCheckLayerAvailability',
        'ecr:GetAuthorizationToken'
    }

    found_actions = set()
    for statement in policy_document['Statement']:
        if isinstance(statement['Action'], list):
            found_actions.update(statement['Action'])
        else:
            found_actions.add(statement['Action'])

    assert required_actions.issubset(found_actions)


def test_iam_policy_attached_to_lambda_role(iam_client):
    """Test that ECR access policy is attached to Lambda execution role."""
    role_name = "naverplace_send_inform-role-vb1bx6ro"
    policy_arn = f"arn:aws:iam::{ACCOUNT_ID}:policy/NaverSmsAutomationECRAccessPolicy"

    response = iam_client.list_attached_role_policies(RoleName=role_name)

    attached_policy_arns = [p['PolicyArn'] for p in response['AttachedPolicies']]
    assert policy_arn in attached_policy_arns


def test_ecr_repository_uri_format(ecr_client):
    """Test that repository URI has correct format."""
    response = ecr_client.describe_repositories(
        repositoryNames=[REPOSITORY_NAME]
    )

    repo = response['repositories'][0]
    repo_uri = repo['repositoryUri']

    expected_uri = f"{ACCOUNT_ID}.dkr.ecr.{REGION}.amazonaws.com/{REPOSITORY_NAME}"
    assert repo_uri == expected_uri


def test_test_image_exists(ecr_client):
    """Test that the test image was successfully pushed."""
    response = ecr_client.describe_images(
        repositoryName=REPOSITORY_NAME
    )

    # Should have at least one image (the test image)
    assert len(response['imageDetails']) > 0

    # Check if test tag exists
    image_tags = []
    for image in response['imageDetails']:
        if 'imageTags' in image:
            image_tags.extend(image['imageTags'])

    assert 'test' in image_tags
