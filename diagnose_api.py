#!/usr/bin/env python3
"""Quick diagnostic to identify why Claude API calls are failing.

Run from the project root:
    python diagnose_api.py
"""

import os
import sys

from dotenv import load_dotenv

load_dotenv(override=True)


def main():
    key = os.getenv("ANTHROPIC_API_KEY", "")
    model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")

    print(f"1. API key loaded: {bool(key)}")
    if not key:
        print("   PROBLEM: ANTHROPIC_API_KEY is empty. Check your .env file.")
        sys.exit(1)
    print(f"   Key prefix: {key[:12]}...")
    print(f"   Key length: {len(key)}")

    try:
        import anthropic
        print(f"\n2. anthropic SDK version: {anthropic.__version__}")
    except ImportError:
        print("\n2. PROBLEM: anthropic package not installed. Run: pip install anthropic")
        sys.exit(1)

    print(f"\n3. Model to test: {model}")

    print("\n4. Attempting API call...")
    try:
        client = anthropic.Anthropic(api_key=key)
        message = client.messages.create(
            model=model,
            max_tokens=20,
            messages=[{"role": "user", "content": "Say hello in one word."}],
        )
        print(f"   SUCCESS! Response: {message.content[0].text}")
    except anthropic.AuthenticationError as e:
        print(f"   FAILED - Authentication error: {e}")
        print("   Your API key is invalid or expired.")
    except anthropic.NotFoundError as e:
        print(f"   FAILED - Model not found: {e}")
        print(f"   The model '{model}' is not available for your API key.")
        print("   Try setting CLAUDE_MODEL=claude-3-5-sonnet-20241022 in your .env")
    except anthropic.PermissionDeniedError as e:
        print(f"   FAILED - Permission denied: {e}")
        print("   Your API key doesn't have access to this model.")
    except anthropic.RateLimitError as e:
        print(f"   FAILED - Rate limit: {e}")
    except anthropic.APIConnectionError as e:
        print(f"   FAILED - Connection error: {e}")
        print("   Cannot reach the Anthropic API. Check your network.")
    except Exception as e:
        print(f"   FAILED - {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
