#!/usr/bin/env python3
"""Test LLM connection with current provider configuration."""

import os
import sys

# Set environment file to prod.env before importing config
os.environ.setdefault("MIOHUB_ENV_FILE", "prod.env")

from providers import LLMClient
import config

def test_llm_connection():
    """Test if LLM provider is properly configured and responding."""
    
    print("=" * 60)
    print("LLM Connection Test")
    print("=" * 60)
    print(f"Provider: {config.PROVIDER}")
    print(f"Default Model: {config.DEFAULT_CHAT_MODEL}")
    print("-" * 60)
    
    try:
        # Initialize LLM client
        print("Initializing LLM client...")
        client = LLMClient()
        print(f"✓ Client initialized successfully")
        print(f"  URL: {client.url}")
        print(f"  Model: {client.model}")
        
        # Test simple chat completion
        print("\nTesting chat completion...")
        messages = [
            {"role": "user", "content": "Say 'Hello from MioChat!' and nothing else."}
        ]
        
        response = client.chat(messages=messages, temperature=0.7, max_tokens=50)
        
        print(f"✓ Chat completion successful!")
        print(f"  Response: {response}")
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED - LLM connection is working!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n✗ ERROR: {str(e)}")
        print("\n" + "=" * 60)
        print("✗ TEST FAILED - Check your API key configuration")
        print("=" * 60)
        print("\nTroubleshooting:")
        print("1. Check that OPENROUTER_API_KEY is set in config.py")
        print("2. Verify the API key is valid at https://openrouter.ai")
        print("3. Ensure you have credits/quota available")
        return False

if __name__ == "__main__":
    success = test_llm_connection()
    sys.exit(0 if success else 1)
