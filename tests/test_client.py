import base64
import os
import tempfile

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from walutomat_py import WalutomatAPIError, WalutomatClient

API_KEY = "test_api_key"
BASE_URL_PROD = "https://api.walutomat.pl/api/v2.0.0"
BASE_URL_SANDBOX = "https://api.walutomat.dev/api/v2.0.0"


@pytest.fixture
def client_prod():
    return WalutomatClient(api_key=API_KEY, sandbox=False)


@pytest.fixture
def client_sandbox():
    return WalutomatClient(api_key=API_KEY, sandbox=True)


@pytest.fixture
def rsa_key_pair():
    # Generate a new RSA private key
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    # Save the private key to a temporary file
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        private_key_path = f.name

    yield private_key_path, private_key  # Yield path/key object for potential direct use

    # Clean up the temporary file
    os.remove(private_key_path)


@pytest.fixture
def client_with_private_key(rsa_key_pair):
    private_key_path, _ = rsa_key_pair
    return WalutomatClient(api_key=API_KEY, private_key_path=private_key_path, sandbox=False)


def test_client_initialization(client_prod, client_sandbox, client_with_private_key):
    assert client_prod.api_key == API_KEY
    assert client_prod.base_url == BASE_URL_PROD
    assert client_prod.private_key is None

    assert client_sandbox.api_key == API_KEY
    assert client_sandbox.base_url == BASE_URL_SANDBOX
    assert client_sandbox.private_key is None

    assert client_with_private_key.api_key == API_KEY
    assert client_with_private_key.base_url == BASE_URL_PROD
    assert client_with_private_key.private_key is not None


def test_get_balances_success(requests_mock, client_prod):
    mock_response = {
        "success": True,
        "result": [
            {
                "currency": "EUR",
                "balanceTotal": "300.33",
                "balanceAvailable": "300.33",
                "balanceReserved": "0.00",
            },
            {
                "currency": "PLN",
                "balanceTotal": "17.34",
                "balanceAvailable": "17.34",
                "balanceReserved": "0.00",
            },
        ],
    }
    requests_mock.get(f"{BASE_URL_PROD}/account/balances", json=mock_response, status_code=200)

    balances = client_prod.get_balances()
    assert len(balances) == 2
    assert balances[0]["currency"] == "EUR"
    assert balances[1]["currency"] == "PLN"
    assert balances[0]["balanceTotal"] == "300.33"


def test_get_balances_api_error(requests_mock, client_prod):
    mock_response = {
        "success": False,
        "errors": [{"key": "INVALID_API_KEY", "description": "Invalid API key provided"}],
    }
    requests_mock.get(f"{BASE_URL_PROD}/account/balances", json=mock_response, status_code=200)

    with pytest.raises(WalutomatAPIError) as excinfo:
        client_prod.get_balances()

    assert "Invalid API key provided" in str(excinfo.value)
    assert excinfo.value.errors[0]["key"] == "INVALID_API_KEY"


def test_get_balances_http_error(requests_mock, client_prod):
    requests_mock.get(f"{BASE_URL_PROD}/account/balances", status_code=403, text="Forbidden")

    with pytest.raises(WalutomatAPIError) as excinfo:
        client_prod.get_balances()

    assert "HTTP error occurred: 403 - Forbidden" in str(excinfo.value)


def test_signed_request_missing_private_key(client_prod):
    # This test verifies that calling a signed request without proper RSA setup raises WalutomatAPIError
    # when a private key is not provided.
    with pytest.raises(
        WalutomatAPIError,
        match="Private key is required for this operation but not provided.",
    ):
        client_prod._make_request("GET", "/some/signed/path", signed=True)


def test_get_history_success(requests_mock, client_with_private_key, rsa_key_pair):
    private_key_path, private_key_obj = rsa_key_pair

    mock_response = {
        "success": True,
        "result": [{"historyItemId": 1, "operationType": "PAYIN", "currency": "PLN", "operationAmount": "100.00"}],
    }
    history_path = "/account/history"
    requests_mock.get(f"{BASE_URL_PROD}{history_path}", json=mock_response, status_code=200)

    # Call get_history with some parameters
    history = client_with_private_key.get_history(
        date_from="2023-01-01T00:00:00Z",
        currencies=["PLN", "EUR"],
        sort_order="ASC",
    )

    assert len(history) == 1
    assert history[0]["historyItemId"] == 1
    assert requests_mock.called_once

    # Verify headers for the signed request
    request_headers = requests_mock.request_history[0].headers
    assert "X-API-Key" in request_headers
    assert "X-API-Timestamp" in request_headers
    assert "X-API-Signature" in request_headers

    # Manually verify the signature
    timestamp = request_headers["X-API-Timestamp"]

    # The body for signature for GET /account/history is the sorted query string
    # The parameters are sorted alphabetically by key
    expected_query_params = {
        "dateFrom": "2023-01-01T00:00:00Z",
        "currencies": "PLN,EUR",
        "sortOrder": "ASC",
    }
    sorted_params = sorted(expected_query_params.items())
    body_for_signature = "&".join([f"{k}={v}" for k, v in sorted_params])

    message_to_sign = f"{timestamp}{history_path}{body_for_signature}".encode("utf-8")

    expected_signature = private_key_obj.sign(
        message_to_sign,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    expected_signature_b64 = base64.b64encode(expected_signature).decode("utf-8")

    assert request_headers["X-API-Signature"] == expected_signature_b64


def test_get_public_rate_success(requests_mock):
    """Test successful fetching of public exchange rates."""
    currency_pair = "EUR_PLN"
    mock_response = {
        "ASK_EUR_PLN": [{"rate": "4.3123"}],
        "BID_EUR_PLN": [{"rate": "4.3021"}],
    }
    url = f"https://user.walutomat.pl/api/public/marketPriceVolumes/{currency_pair}?brief=true"
    requests_mock.get(url, json=mock_response, status_code=200)

    rates = WalutomatClient.get_public_rate(currency_pair)

    assert rates["buyRate"] == "4.3123"
    assert rates["sellRate"] == "4.3021"


def test_get_public_rate_api_error(requests_mock):
    """Test API error handling for public exchange rates."""
    currency_pair = "FAKE_PAIR"
    url = f"https://user.walutomat.pl/api/public/marketPriceVolumes/{currency_pair}?brief=true"
    requests_mock.get(url, status_code=404, text="Not Found")

    with pytest.raises(WalutomatAPIError) as excinfo:
        WalutomatClient.get_public_rate(currency_pair)

    assert "An unexpected request error occurred" in str(excinfo.value)
