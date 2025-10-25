#!/usr/bin/env python3
"""
Test script to verify VK Cloud API connection and authentication
"""

import requests
import json
import os
import sys

# Configuration
AUTH_TOKEN = os.getenv("VK_CLOUD_AUTH_TOKEN", "")
NOVA_ENDPOINT = os.getenv("VK_CLOUD_NOVA_ENDPOINT", "https://infra.mail.ru:8774/v2.1")

if not AUTH_TOKEN:
    print("Error: VK_CLOUD_AUTH_TOKEN environment variable is not set")
    print("Usage: export VK_CLOUD_AUTH_TOKEN='your_token' && python3 test_vk_cloud_connection.py")
    sys.exit(1)

headers = {
    "X-Auth-Token": AUTH_TOKEN,
    "Content-Type": "application/json"
}


def test_connection():
    """Test basic connection to Nova API"""
    print("=" * 80)
    print("Testing VK Cloud Nova API Connection")
    print("=" * 80)
    
    print(f"\nEndpoint: {NOVA_ENDPOINT}")
    print(f"Token: {AUTH_TOKEN[:20]}...{AUTH_TOKEN[-20:]}")
    
    # Test 1: Get API versions
    print("\n" + "-" * 80)
    print("Test 1: Get API Versions")
    print("-" * 80)
    try:
        url = f"{NOVA_ENDPOINT.rsplit('/', 1)[0]}/"
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print("✓ API is accessible")
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)[:500]}")
        else:
            print(f"✗ Unexpected status code: {response.status_code}")
            print(f"Response: {response.text[:500]}")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    # Test 2: List existing servers
    print("\n" + "-" * 80)
    print("Test 2: List Existing Servers")
    print("-" * 80)
    try:
        url = f"{NOVA_ENDPOINT}/servers"
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print("✓ Authentication successful")
            data = response.json()
            servers = data.get("servers", [])
            print(f"Number of servers: {len(servers)}")
            if servers:
                print(f"First server: {servers[0]}")
            else:
                print("No existing servers")
        else:
            print(f"✗ Unexpected status code: {response.status_code}")
            print(f"Response: {response.text[:500]}")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    # Test 3: List flavors
    print("\n" + "-" * 80)
    print("Test 3: List Flavors")
    print("-" * 80)
    try:
        url = f"{NOVA_ENDPOINT}/flavors"
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print("✓ Can list flavors")
            data = response.json()
            flavors = data.get("flavors", [])
            print(f"Number of flavors: {len(flavors)}")
            for flavor in flavors[:3]:
                print(f"  - {flavor.get('name')} (ID: {flavor.get('id')})")
        else:
            print(f"✗ Unexpected status code: {response.status_code}")
            print(f"Response: {response.text[:500]}")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    print("\n" + "=" * 80)
    print("Connection Test Complete")
    print("=" * 80)


if __name__ == "__main__":
    test_connection()

