"""
SDK Setup Verification

This example verifies that the Claude SDK is properly installed.
Run this after installing the SDK to confirm everything is working.
"""

import sys


def verify_sdk_installation():
    """Verify the Anthropic SDK is installed and accessible."""
    try:
        import anthropic

        print(f"✓ Anthropic SDK installed")
        print(f"  Version: {anthropic.__version__}")
        print(f"  Python: {sys.version}")
        return True

    except ImportError as e:
        print(f"✗ Anthropic SDK not found")
        print(f"  Error: {e}")
        print(f"\nTo install, run:")
        print(f"  pip install anthropic")
        return False


def verify_client_creation():
    """Verify we can create an Anthropic client."""
    import os

    # For validation mode, we don't need a real key
    if os.environ.get("FORGE_VALIDATION_MODE"):
        print("✓ Validation mode - skipping client creation")
        return True

    try:
        from anthropic import Anthropic

        # This will raise an error if no API key is set
        # We don't make any API calls here
        client = Anthropic()
        print(f"✓ Client created successfully")
        return True

    except Exception as e:
        print(f"✗ Could not create client")
        print(f"  Error: {e}")
        print(f"\nMake sure ANTHROPIC_API_KEY is set in your environment")
        return False


if __name__ == "__main__":
    print("Claude SDK Installation Verification")
    print("=" * 40)
    print()

    sdk_ok = verify_sdk_installation()
    print()

    if sdk_ok:
        verify_client_creation()
