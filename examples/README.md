# Walutomat-py Examples

This directory contains example scripts demonstrating how to use the `walutomat-py` library.

## get_balances_example.py

This script fetches and displays your wallet balances from the Walutomat API.

### Setup and Configuration

1.  **Install Dependencies:**
    Ensure you have installed the project's development dependencies, which include `python-dotenv` for loading environment variables:
    ```bash
    cd walutomat-py
    ./.venv/bin/pip install -e ".[dev]" python-dotenv
    ```

2.  **Configure API Key and Environment:**
    The script requires your Walutomat API Key and allows you to choose between the production and sandbox environments.

    *   **Create `.env` file:** Copy the provided `.env.example` file to `.env` in the `walutomat-py` directory:
        ```bash
        cp walutomat-py/.env.example walutomat-py/.env
        ```
    *   **Edit `.env`:** Open `walutomat-py/.env` and add your Walutomat API Key:
        ```
        WALUTOMAT_API_KEY="YOUR_API_KEY_HERE"
        ```
        Replace `"YOUR_API_KEY_HERE"` with your actual API key.

    *   **Choose Environment (Optional):** By default, the script connects to the **production** environment. If you wish to use the **sandbox** environment, add or modify the `WALUTOMAT_SANDBOX` variable in your `.env` file:
        ```
        WALUTOMAT_SANDBOX="true"
        ```
        Any value like `"true"`, `"1"`, `"yes"` (case-insensitive) will activate the sandbox. If this variable is absent or set to any other value, the production environment will be used.

### Running the Example

Navigate to the `walutomat-py` directory and run the script:

```bash
cd walutomat-py
./.venv/bin/python examples/get_balances_example.py
```

The script will print your current balances or an error message if something goes wrong.
