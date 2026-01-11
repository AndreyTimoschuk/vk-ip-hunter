#!/usr/bin/env python3
"""
Helper script to get required configuration parameters for VM creation
"""

import requests
import json
import os
import sys
from pathlib import Path

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded environment variables from {env_path}")
    else:
        print(f"Warning: .env file not found at {env_path}")
        print("Copy env.example to .env and configure it first")
except ImportError:
    print("Warning: python-dotenv not installed. Install it with: pip install python-dotenv")
    print("Or use run.sh script to load .env file")

# Configuration
AUTH_TOKEN = os.getenv("VK_CLOUD_AUTH_TOKEN", "")
NOVA_ENDPOINT = os.getenv("VK_CLOUD_NOVA_ENDPOINT", "https://infra.mail.ru:8774/v2.1")
GLANCE_ENDPOINT = os.getenv("VK_CLOUD_GLANCE_ENDPOINT", "https://infra.mail.ru:9292")
NEUTRON_ENDPOINT = os.getenv("VK_CLOUD_NEUTRON_ENDPOINT", "https://infra.mail.ru:9696")

if not AUTH_TOKEN:
    print("Error: VK_CLOUD_AUTH_TOKEN environment variable is not set")
    print("Usage: export VK_CLOUD_AUTH_TOKEN='your_token' && python3 vk_cloud_get_config.py")
    sys.exit(1)

headers = {
    "X-Auth-Token": AUTH_TOKEN,
    "Content-Type": "application/json"
}


def get_flavors():
    """Get available VM flavors"""
    print("\n" + "=" * 80)
    print("AVAILABLE FLAVORS (VM Configurations)")
    print("=" * 80)
    
    url = f"{NOVA_ENDPOINT}/flavors/detail"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        flavors = data.get("flavors", [])
        for flavor in flavors:
            print(f"\nName: {flavor.get('name')}")
            print(f"  ID: {flavor.get('id')}")
            print(f"  RAM: {flavor.get('ram')} MB")
            print(f"  vCPUs: {flavor.get('vcpus')}")
            print(f"  Disk: {flavor.get('disk')} GB")
        
        if flavors:
            print(f"\n✓ Found {len(flavors)} flavors")
            print(f"Recommended for testing: Use smallest flavor")
            smallest = min(flavors, key=lambda x: x.get('ram', 999999))
            print(f"Smallest: {smallest.get('name')} (ID: {smallest.get('id')})")
            return smallest.get('id')
    except Exception as e:
        print(f"✗ Error getting flavors: {e}")
    
    return None


def get_images():
    """Get available images"""
    print("\n" + "=" * 80)
    print("AVAILABLE IMAGES")
    print("=" * 80)
    
    url = f"{GLANCE_ENDPOINT}/v2/images"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        images = data.get("images", [])
        for img in images[:20]:  # Limit to first 20
            status = img.get('status', 'unknown')
            visibility = img.get('visibility', 'unknown')
            name = img.get('name', 'unnamed')
            img_id = img.get('id')
            
            if status == 'active':
                print(f"\nName: {name}")
                print(f"  ID: {img_id}")
                print(f"  Status: {status}")
                print(f"  Visibility: {visibility}")
        
        # Find a suitable Ubuntu or basic image
        active_images = [img for img in images if img.get('status') == 'active']
        if active_images:
            print(f"\n✓ Found {len(active_images)} active images")
            # Try to find Ubuntu
            ubuntu = next((img for img in active_images if 'ubuntu' in img.get('name', '').lower()), None)
            if ubuntu:
                print(f"Recommended: {ubuntu.get('name')} (ID: {ubuntu.get('id')})")
                return ubuntu.get('id')
            else:
                print(f"Recommended: {active_images[0].get('name')} (ID: {active_images[0].get('id')})")
                return active_images[0].get('id')
    except Exception as e:
        print(f"✗ Error getting images: {e}")
    
    return None


def get_networks():
    """Get available networks"""
    print("\n" + "=" * 80)
    print("AVAILABLE NETWORKS")
    print("=" * 80)
    
    url = f"{NEUTRON_ENDPOINT}/v2.0/networks"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        networks = data.get("networks", [])
        external_networks = []
        internal_networks = []
        
        for net in networks:
            name = net.get('name', 'unnamed')
            net_id = net.get('id')
            status = net.get('status', 'unknown')
            is_external = net.get('router:external', False)
            
            print(f"\nName: {name}")
            print(f"  ID: {net_id}")
            print(f"  Status: {status}")
            print(f"  External: {is_external}")
            
            if is_external:
                external_networks.append(net)
            else:
                internal_networks.append(net)
        
        # For floating IPs, we need external networks
        if external_networks:
            print(f"\n✓ Found {len(external_networks)} external networks (for floating IPs)")
            print(f"Recommended for floating IPs: {external_networks[0].get('name')} (ID: {external_networks[0].get('id')})")
            return external_networks[0].get('id')
        elif internal_networks:
            print(f"\n✓ Found {len(internal_networks)} internal networks")
            print(f"Note: For floating IPs, you need an external network")
            return internal_networks[0].get('id')
    except Exception as e:
        print(f"✗ Error getting networks: {e}")
    
    return None


def main():
    """Main function"""
    print("=" * 80)
    print("VK Cloud Configuration Helper")
    print("=" * 80)
    
    # For floating IP reservation, we only need networks
    network_id = get_networks()
    
    print("\n" + "=" * 80)
    print("CONFIGURATION SUMMARY FOR FLOATING IP RESERVATION")
    print("=" * 80)
    
    print("\nAdd this to your .env file:")
    print(f'VK_CLOUD_FLOATING_NETWORK_ID={network_id or "PLEASE_SET_NETWORK_ID"}')
    
    print("\n" + "=" * 80)
    print("NOTE: For VM creation (old method), run with --vm flag")
    print("=" * 80)
    
    # Optionally show VM config if needed
    if len(sys.argv) > 1 and sys.argv[1] == '--vm':
        print("\n" + "=" * 80)
        print("VM CONFIGURATION (LEGACY)")
        print("=" * 80)
        
        flavor_id = get_flavors()
        image_id = get_images()
        
        config = {
            "flavorRef": flavor_id or "PLEASE_SET_FLAVOR_ID",
            "imageRef": image_id or "PLEASE_SET_IMAGE_ID",
            "networks": [{"uuid": network_id or "PLEASE_SET_NETWORK_ID"}]
        }
        
        print("\nCopy this configuration to vk_cloud_vm_creator.py:")
        print("\nVM_CONFIG = {")
        print(f'    "name": "auto-vm",')
        print(f'    "flavorRef": "{config["flavorRef"]}",')
        print(f'    "imageRef": "{config["imageRef"]}",')
        print(f'    "adminPass": "TempPassword123!",')
        print(f'    "networks": [{{"uuid": "{config["networks"][0]["uuid"]}"}}]')
        print("}")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()

