import base64
import datetime
import json
import os
from typing import Any, Dict, List, Optional

import requests
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


class WalutomatAPIError(Exception):
    """Custom exception for Walutomat API errors."""

    def __init__(self, message: str, errors: Optional[List[Dict[str, Any]]] = None):
        super().__init__(message)
        self.errors = errors if errors is not None else []


class WalutomatClient:
    BASE_URL_PROD = "https://api.walutomat.pl/api/v2.0.0"
    BASE_URL_SANDBOX = "https://api.walutomat.dev/api/v2.0.0"

    def __init__(
        self,
        api_key: str,
        private_key_path: Optional[str] = None,
        sandbox: bool = False,
    ):
        self.api_key = api_key
        self.private_key_path = private_key_path
        self.base_url = self.BASE_URL_SANDBOX if sandbox else self.BASE_URL_PROD
        self.private_key = None

        if private_key_path:
            if not os.path.exists(private_key_path):
                raise ValueError(f"Private key file not found at {private_key_path}")
            try:
                with open(private_key_path, "rb") as f:
                    self.private_key = serialization.load_pem_private_key(
                        f.read(),
                        password=None,  # Assuming no password for simplicity
                        backend=default_backend(),
                    )
            except Exception as e:
                raise ValueError(f"Error loading private key from {private_key_path}: {e}") from e

    def _generate_signature(self, timestamp: str, endpoint: str, body: str = "") -> str:
        if not self.private_key:
            raise WalutomatAPIError("Private key is required for this operation but not provided.")

        message = f"{timestamp}{endpoint}{body}".encode("utf-8")

        signature = self.private_key.sign(message, padding.PKCS1v15(), hashes.SHA256())
        return base64.b64encode(signature).decode("utf-8")

    # noqa: C901
    def _make_request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        signed: bool = False,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
            if method in ["POST", "PUT"] and data
            else "application/x-www-form-urlencoded",
        }

        if signed:
            timestamp = (
                datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
            )

            # Determine body for signature based on Content-Type and data type
            if data:
                if isinstance(data, str):  # For signed GET requests, data is already the query string
                    body_for_signature = data
                elif headers["Content-Type"] == "application/json":
                    body_for_signature = json.dumps(
                        data, separators=(",", ":")
                    )  # Ensure no extra whitespace for signature
                elif headers["Content-Type"] == "application/x-www-form-urlencoded":
                    # For form-urlencoded, body needs to be constructed from data dict
                    # Order of params in form-urlencoded body for signature is crucial.
                    # API docs imply alphabetical sorting.
                    # Let's assume alphabetical sorting for now.
                    sorted_data_items = sorted(data.items())
                    body_for_signature = "&".join([f"{k}={v}" for k, v in sorted_data_items])
                else:
                    body_for_signature = ""  # Fallback for other content types
            else:
                body_for_signature = ""

            signature = self._generate_signature(timestamp, path, body_for_signature)
            headers["X-API-Timestamp"] = timestamp
            headers["X-API-Signature"] = signature

        try:
            response: requests.Response
            if method == "GET":
                response = requests.get(url, headers=headers, params=params)
            elif method == "POST":
                if headers["Content-Type"] == "application/json":
                    response = requests.post(url, headers=headers, json=data)
                else:  # application/x-www-form-urlencoded
                    response = requests.post(url, headers=headers, data=data)
            # Add other methods (PUT, DELETE) if needed later

            response.raise_for_status()  # Raise HTTPError for 4xx or 5xx responses

            json_response = response.json()

            if not json_response.get("success"):
                errors = json_response.get("errors", [])
                error_messages = [err.get("description", "Unknown error") for err in errors]
                raise WalutomatAPIError(
                    f"Walutomat API returned an error: {', '.join(error_messages)}",
                    errors=errors,
                )

            return json_response.get("result", {})

        except requests.exceptions.HTTPError as http_err:
            try:
                error_content = http_err.response.json()
                errors = error_content.get("errors", [])
                error_messages = [err.get("description", "Unknown error") for err in errors]
                raise WalutomatAPIError(
                    f"HTTP error occurred: {http_err.response.status_code} - {', '.join(error_messages)}",
                    errors=errors,
                )
            except json.JSONDecodeError:
                raise WalutomatAPIError(
                    f"HTTP error occurred: {http_err.response.status_code} - {http_err.response.text}"
                ) from http_err
        except requests.exceptions.ConnectionError as conn_err:
            raise WalutomatAPIError(f"Connection error occurred: {conn_err}") from conn_err
        except requests.exceptions.Timeout as timeout_err:
            raise WalutomatAPIError(f"Timeout error occurred: {timeout_err}") from timeout_err
        except requests.exceptions.RequestException as req_err:
            raise WalutomatAPIError(f"An unexpected request error occurred: {req_err}") from req_err

    def get_balances(self) -> List[Dict[str, Any]]:
        """
        Retrieves the wallet balances for all currencies.
        This endpoint does not require request signing.
        """
        path = "/account/balances"
        return self._make_request("GET", path, signed=False)

    @staticmethod
    def get_public_rate(currency_pair: str) -> Dict[str, Any]:
        """
        Returns current public market rate for a given currency pair.
        This endpoint is public and does not require an API key.
        Note: currency_pair format is with an underscore, e.g., "EUR_PLN".
        """
        url = f"https://user.walutomat.pl/api/public/marketPriceVolumes/{currency_pair}?brief=true"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            # ASK is what the market is selling the base currency for (our buy price)
            best_ask = data.get(f"ASK_{currency_pair}", [{}])[0].get("rate")
            # BID is what the market is buying the base currency for (our sell price)
            best_bid = data.get(f"BID_{currency_pair}", [{}])[0].get("rate")

            if not best_ask or not best_bid:
                raise WalutomatAPIError(f"Could not parse rate data from public endpoint for {currency_pair}")

            return {"buyRate": best_ask, "sellRate": best_bid}

        except requests.exceptions.RequestException as req_err:
            raise WalutomatAPIError(f"An unexpected request error occurred: {req_err}") from req_err
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise WalutomatAPIError(f"Failed to parse public rate data: {e}") from e

    def get_history(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        currencies: Optional[List[str]] = None,
        operation_type: Optional[str] = None,
        operation_detailed_type: Optional[str] = None,
        item_limit: Optional[int] = None,
        continue_from: Optional[int] = None,
        sort_order: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Returns wallet history - operations recorded on the wallet.
        This endpoint requires request signing.
        """
        path = "/account/history"
        params = {}
        if date_from:
            params["dateFrom"] = date_from
        if date_to:
            params["dateTo"] = date_to
        if currencies:
            params["currencies"] = ",".join(currencies)
        if operation_type:
            params["operationType"] = operation_type
        if operation_detailed_type:
            params["operationDetailedType"] = operation_detailed_type
        if item_limit:
            params["itemLimit"] = item_limit
        if continue_from:
            params["continueFrom"] = continue_from
        if sort_order:
            params["sortOrder"] = sort_order

        # For GET requests with signed=True, the body for signature is the query string.
        # API docs example for /account/history: query string is part of signed msg.
        # Query params must be sorted alphabetically for consistent signature generation.
        sorted_params = sorted(params.items())
        query_string_for_signature = "&".join([f"{k}={v}" for k, v in sorted_params])

        # The _make_request method will handle the actual URL construction with params
        # and pass the query_string_for_signature as the body for signing.
        return self._make_request("GET", path, params=params, data=query_string_for_signature, signed=True)
