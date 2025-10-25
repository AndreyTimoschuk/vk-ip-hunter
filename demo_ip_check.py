#!/usr/bin/env python3
"""
Demo script to test IP range checking logic without creating actual VMs
"""

import ipaddress
import random

# IP Range
IP_RANGE_START = ipaddress.IPv4Address("95.163.248.10")
IP_RANGE_END = ipaddress.IPv4Address("95.163.251.250")


def is_ip_in_range(ip_str: str) -> bool:
    """Check if IP is in the target range"""
    try:
        ip = ipaddress.IPv4Address(ip_str)
        return IP_RANGE_START <= ip <= IP_RANGE_END
    except:
        return False


def generate_random_ip():
    """Generate a random IP for testing"""
    # 30% chance to generate IP in range
    if random.random() < 0.3:
        # Generate IP in range
        start_int = int(IP_RANGE_START)
        end_int = int(IP_RANGE_END)
        random_int = random.randint(start_int, end_int)
        return str(ipaddress.IPv4Address(random_int))
    else:
        # Generate random IP outside range
        return f"{random.randint(1, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"


def demo_ip_checking():
    """Demonstrate IP checking logic"""
    print("=" * 80)
    print("IP Range Checker Demo")
    print("=" * 80)
    print(f"\nTarget IP Range: {IP_RANGE_START} - {IP_RANGE_END}")
    print(f"Range size: {int(IP_RANGE_END) - int(IP_RANGE_START) + 1} addresses")
    
    print("\n" + "-" * 80)
    print("Testing with sample IPs:")
    print("-" * 80)
    
    test_ips = [
        "95.163.248.10",     # Start of range
        "95.163.249.100",    # Inside range
        "95.163.251.250",    # End of range
        "95.163.248.9",      # Just before range
        "95.163.251.251",    # Just after range
        "192.168.1.1",       # Completely outside
        "10.0.0.1",          # Private IP
        "95.163.247.255",    # Close but outside
    ]
    
    for ip in test_ips:
        in_range = is_ip_in_range(ip)
        status = "✓ IN RANGE" if in_range else "✗ OUT OF RANGE"
        print(f"{ip:20s} -> {status}")
    
    print("\n" + "-" * 80)
    print("Simulating VM creation loop:")
    print("-" * 80)
    
    attempts = 0
    max_attempts = 20
    
    while attempts < max_attempts:
        attempts += 1
        
        # Simulate getting IP from newly created VM
        vm_ip = generate_random_ip()
        in_range = is_ip_in_range(vm_ip)
        
        if in_range:
            print(f"\nAttempt {attempts}: VM IP = {vm_ip}")
            print(f"            Status: ✓ SUCCESS! IP is in range")
            print(f"\n🎉 Found matching IP after {attempts} attempts!")
            break
        else:
            print(f"Attempt {attempts}: VM IP = {vm_ip} -> ✗ Not in range, deleting VM...")
    else:
        print(f"\n⚠️  Did not find matching IP in {max_attempts} attempts (demo limit)")
    
    print("\n" + "=" * 80)
    print("Demo Complete")
    print("=" * 80)
    print("\nIn real scenario:")
    print("- Each worker would create actual VMs")
    print("- Wait for VM to become ACTIVE (~30-60 seconds)")
    print("- Get IP from VM details")
    print("- Delete and retry if IP is not in range")
    print("- 10 workers running in parallel increase chances")


if __name__ == "__main__":
    demo_ip_checking()

