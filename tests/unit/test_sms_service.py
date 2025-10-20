import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

import pytest

sys.path.append(str(Path(__file__).resolve().parents[2] / "src"))

from notifications.sms_service import SensSmsClient, SmsServiceError  # noqa: E402


FIXTURE_PATH = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "sens" / "legacy_payloads.json"
)
TEMPLATES_PATH = Path(__file__).resolve().parents[2] / "config" / "sms_templates.yaml"
STORES_PATH = Path(__file__).resolve().parents[2] / "config" / "stores.yaml"

LEGACY_SECRET_KEY = "YrAgDCC20hiItoFrzrolbStsIwzyEWBFi4szm1Vh"  # matches original module
LEGACY_ACCESS_KEY = "tpAFhfAWvpLqS5ve35Zw"
LEGACY_SERVICE_ID = "ncp:sms:kr:324182048243:dabistudio"
LEGACY_TIMESTAMP = "1700000000000"


@pytest.fixture(scope="session")
def legacy_payloads():
    return json.loads(FIXTURE_PATH.read_text())


class HttpStub:
    def __init__(self, responses=None):
        self.responses = responses or []
        self.requests = []

    def post(self, url, headers=None, data=None, timeout=None):
        self.requests.append({"url": url, "headers": headers, "data": data, "timeout": timeout})
        index = min(len(self.requests) - 1, len(self.responses) - 1)
        status_code = self.responses[index] if self.responses else 200
        text = "error" if status_code >= 400 else "ok"
        return SimpleNamespace(status_code=status_code, text=text)


def build_client(http_stub: HttpStub, *, env_override: Optional[str] = None, max_retries: int = 1):
    credentials = {
        "access_key": LEGACY_ACCESS_KEY,
        "secret_key": LEGACY_SECRET_KEY,
        "service_id": LEGACY_SERVICE_ID,
    }
    original_override = os.environ.get("SENS_FROM_MAP_JSON")
    if env_override is not None:
        os.environ["SENS_FROM_MAP_JSON"] = env_override
    client = SensSmsClient(
        settings=None,
        credentials=credentials,
        templates_path=TEMPLATES_PATH,
        stores_path=STORES_PATH,
        http_client=http_stub,
        timestamp_provider=lambda: LEGACY_TIMESTAMP,
        max_retries=max_retries,
        retry_delay_seconds=0,
    )
    if env_override is not None:
        if original_override is None:
            del os.environ["SENS_FROM_MAP_JSON"]
        else:
            os.environ["SENS_FROM_MAP_JSON"] = original_override
    return client


def assert_request_matches(request, legacy_entry):
    assert request["url"] == legacy_entry["url"]
    assert request["headers"] == legacy_entry["headers"]
    assert json.loads(request["data"]) == legacy_entry["payload"]


def test_confirm_payload_matches_legacy(legacy_payloads):
    stub = HttpStub()
    client = build_client(stub)

    client.send_confirm_sms("010-1234-5678")

    assert len(stub.requests) == 1
    assert_request_matches(stub.requests[0], legacy_payloads["confirm"])


def test_event_payload_matches_legacy(legacy_payloads):
    stub = HttpStub()
    client = build_client(stub)

    client.send_event_sms("010-9876-5432")

    assert len(stub.requests) == 1
    assert_request_matches(stub.requests[0], legacy_payloads["event"])


@pytest.mark.parametrize(
    "store_id",
    ["1051707", "951291", "1462519", "1120125", "1285716", "1473826", "1466783", "867589"],
)
def test_guide_payload_matches_legacy(store_id, legacy_payloads):
    stub = HttpStub()
    client = build_client(stub)

    client.send_guide_sms(store_id=store_id, phone="010-0000-1234")

    assert len(stub.requests) == 1
    assert_request_matches(stub.requests[0], legacy_payloads[f"guide_{store_id}"])


def test_environment_override_updates_from_number(legacy_payloads):
    override = json.dumps({"951291": "01099998888"})
    stub = HttpStub()
    client = build_client(stub, env_override=override)

    client.send_guide_sms(store_id="951291", phone="010-0000-1234")

    sent_payload = json.loads(stub.requests[0]["data"])
    assert sent_payload["from"] == "01099998888"


def test_unknown_store_falls_back_to_default():
    stub = HttpStub()
    client = build_client(stub)

    assert client._get_from_number("999999") == "01055814318"  # noqa: SLF001 - test boundary


def test_retry_and_failure(caplog):
    stub = HttpStub(responses=[500, 500])
    client = build_client(stub, max_retries=2)

    with pytest.raises(SmsServiceError):
        client.send_confirm_sms("01012345678")

    assert len(stub.requests) == 2
    failure_logs = [record for record in caplog.records if record.levelname == "ERROR"]
    assert failure_logs, "Expected failure log record"
