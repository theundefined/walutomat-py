import os
import sys

from dotenv import load_dotenv

from walutomat_py import WalutomatAPIError, WalutomatClient


def main():
    """
    Example script to fetch and display wallet balances from Walutomat.
    """
    # Load environment variables from .env file
    load_dotenv()

    # Get API key from environment variables
    api_key = os.getenv("WALUTOMAT_API_KEY")

    if not api_key:
        print("Error: WALUTOMAT_API_KEY not found.")
        print("Please create a .env file (copy from .env.example) and add your API key.")
        sys.exit(1)

    print("Connecting to Walutomat API...")

    # Determine if sandbox environment should be used based on WALUTOMAT_SANDBOX env var
    use_sandbox = os.getenv("WALUTOMAT_SANDBOX", "false").lower() in ("true", "1")
    env_name = "Sandbox" if use_sandbox else "Production"
    print(f"Using {env_name} environment.")

    try:
        # Initialize the client. Environment is determined by use_sandbox variable.
        client = WalutomatClient(api_key=api_key, sandbox=use_sandbox)

        # Fetch balances
        balances = client.get_balances()

        if not balances:
            print("No balances found or an empty response was received.")
            return

        print("\n--- Your Wallet Balances ---")
        for balance in balances:
            currency = balance.get("currency")
            total = balance.get("balanceTotal")
            available = balance.get("balanceAvailable")
            reserved = balance.get("balanceReserved")
            print(f"Currency: {currency}\n  Total:     {total}\n  Available: {available}\n  Reserved:  {reserved}\n")
        print("--------------------------")

    except WalutomatAPIError as e:
        print(f"\nAn API error occurred: {e}")
        if e.errors:
            for error in e.errors:
                print(f"  - Error Key: {error.get('key')}, Description: {error.get('description')}")
        sys.exit(1)
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
