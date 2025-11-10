import sys

from walutomat_py import WalutomatAPIError, WalutomatClient

# List of currency pairs to fetch rates for, using the public API format (with underscore)
CURRENCY_PAIRS = [
    "EUR_PLN",
    "USD_PLN",
    "CHF_PLN",
    "GBP_PLN",
    "EUR_USD",
]

def main():
    """
    Example script to fetch and display public exchange rates from Walutomat.
    This method does not require an API key.
    """
    print("--- Fetching Public Exchange Rates ---")
    for pair in CURRENCY_PAIRS:
        try:
            # Call the static method directly on the class
            rate_data = WalutomatClient.get_public_rate(pair)
            print(f"  {pair}:")
            print(f"    Buy Rate (you buy): {rate_data.get('buyRate')}")
            print(f"    Sell Rate (you sell): {rate_data.get('sellRate')}")
        except WalutomatAPIError as e:
            print(f"  Error fetching rate for {pair}: {e}")
        except Exception as e:
            print(f"  An unexpected error occurred for {pair}: {e}")
            sys.exit(1)
    print("------------------------------------")

if __name__ == "__main__":
    main()
