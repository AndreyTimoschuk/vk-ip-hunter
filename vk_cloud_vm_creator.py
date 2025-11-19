#!/usr/bin/env python3
"""
VK Cloud VM Creator with IP Range Filter
Creates VMs and checks if their IP is in VK Cloud ranges with REAL services
Based on comprehensive scan results showing 459 real services (excluding Mail.ru infrastructure)
Includes government, banking, retail, technology, and business services
"""

import requests
import time
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Dict, Any
import ipaddress
import signal
import sys
from collections import Counter
from pathlib import Path
import threading
import os
import random
import string
from datetime import datetime

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # python-dotenv not installed, continue without it

# Configuration
AUTH_TOKEN = os.getenv("VK_CLOUD_AUTH_TOKEN", "")
NOVA_ENDPOINT = os.getenv("VK_CLOUD_NOVA_ENDPOINT", "https://infra.mail.ru:8774/v2.1")
PROJECT_ID = os.getenv("VK_CLOUD_PROJECT_ID", "")

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")  # Set your Chat ID here (send /start to bot and get ID from @userinfobot)

# IP Ranges - VK Cloud ranges with REAL services (excluding Mail.ru infrastructure)
IP_RANGES = [
    # Top priority ranges with government and banking services
    
    # (ipaddress.IPv4Address("109.120.188.0"), ipaddress.IPv4Address("109.120.191.255")),  # 109.120.188.0/22 - mailer.digital.gov.ru
    
    # High priority ranges with banking and retail services
    # (ipaddress.IPv4Address("5.188.140.0"), ipaddress.IPv4Address("5.188.143.255")),      # 5.188.140.0/22 - greenmoney.ru, gigasport.ru
    # (ipaddress.IPv4Address("213.219.212.0"), ipaddress.IPv4Address("213.219.215.255")),  # 213.219.212.0/22 - bank-hlynov.ru, fix-price.ru
    # (ipaddress.IPv4Address("185.241.192.0"), ipaddress.IPv4Address("185.241.195.255")),  # 185.241.192.0/22 - magnit.ru, bitrix24.com
    # (ipaddress.IPv4Address("87.239.104.0"), ipaddress.IPv4Address("87.239.111.255")),   # 87.239.104.0/21 - greenmoney.ru, finenumbers.com
    
    # Technology and business services ranges
    # (ipaddress.IPv4Address("89.208.196.0"), ipaddress.IPv4Address("89.208.199.255")),    # 89.208.196.0/22 - bitrix24.com, finenumbers.com
    # (ipaddress.IPv4Address("95.163.212.0"), ipaddress.IPv4Address("95.163.215.255")),    # 95.163.212.0/22 - tarantool.org, bitrix24.com
    # (ipaddress.IPv4Address("109.120.180.0"), ipaddress.IPv4Address("109.120.183.255")),  # 109.120.180.0/22 - bitrix24.com, delo-group.com
    # (ipaddress.IPv4Address("89.208.208.0"), ipaddress.IPv4Address("89.208.211.255")),   # 89.208.208.0/22 - bank-hlynov.ru, olimpoks.ru
    
    # Additional ranges with real services
    # (ipaddress.IPv4Address("85.192.32.0"), ipaddress.IPv4Address("85.192.35.255")),      # 85.192.32.0/22 - bitrix24.com, education services
    # (ipaddress.IPv4Address("37.139.40.0"), ipaddress.IPv4Address("37.139.43.255")),     # 37.139.40.0/22 - comfortbooking.ru, business services
    # (ipaddress.IPv4Address("89.208.84.0"), ipaddress.IPv4Address("89.208.87.255")),     # 89.208.84.0/22 - bitrix24.com, business services
    # (ipaddress.IPv4Address("217.16.16.0"), ipaddress.IPv4Address("217.16.23.255")),      # 217.16.16.0/21 - r7.ru, delo-group.com
    # (ipaddress.IPv4Address("94.139.244.0"), ipaddress.IPv4Address("94.139.247.255")),  # 94.139.244.0/22 - fix-price.ru, bitrix24.com
    # (ipaddress.IPv4Address("95.163.248.0"), ipaddress.IPv4Address("95.163.251.255")),  # 95.163.248.0/22 - bitrix24.com, education services
    
    # Original ranges (keep for compatibility)
    (ipaddress.IPv4Address("95.163.248.10"), ipaddress.IPv4Address("95.163.251.250")),
    (ipaddress.IPv4Address("217.16.24.1"), ipaddress.IPv4Address("217.16.24.2")),
    (ipaddress.IPv4Address("217.16.24.3"), ipaddress.IPv4Address("217.16.27.253")),
]

# VM Configuration - adjust these parameters according to your needs
VM_CONFIG = {
    "name": "auto-vm",
    "flavorRef": "9cdbca68-5e15-4c54-979d-9952785ba33e",  # STD2-1-1: 1GB RAM, 1 CPU, 0GB disk
    "imageRef": "",  # Not used with block_device_mapping_v2
    "adminPass": "12345678a",
    "config_drive": True,  # Enable config drive for network setup
    "OS-DCF:diskConfig": "AUTO",  # Automatic disk configuration
    "security_groups": [
        {
            "name": "default"
        }
    ],
    "metadata": {
        "backup_policy": "disabled"  # Disable auto backup
    },
    "networks": [
        {
            "uuid": "ec8c610e-6387-447e-83d2-d2c541e88164"  # internet (external network)
        }
    ],
    "block_device_mapping_v2": [
        {
            "device_name": "/dev/vda",
            "source_type": "image",
            "destination_type": "volume",
            "uuid": "769e4c02-680c-420e-874b-6fd41f2da6be",  # ubuntu-22-202508151311.gitfaa03fa8
            "boot_index": 0,
            "delete_on_termination": True,
            "volume_size": 10  # 10GB disk
        }
    ]
}


# Parallel workers
MAX_WORKERS = 13

# Global variables for cleanup
created_vms = []
executor = None
shutdown_event = threading.Event()

# Statistics file
STATS_FILE = Path(__file__).parent / "vm_statistics.json"
stats_lock = threading.Lock()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_statistics():
    """Load statistics from file"""
    if not STATS_FILE.exists():
        return {
            "total_attempts": 0,
            "ip_addresses": {},  # {ip: count}
            "start_time": time.time(),
            "last_update": time.time()
        }
    
    try:
        with open(STATS_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load statistics: {e}")
        return {
            "total_attempts": 0,
            "ip_addresses": {},
            "start_time": time.time(),
            "last_update": time.time()
        }


def save_statistics(stats):
    """Save statistics to file"""
    try:
        with stats_lock:
            stats["last_update"] = time.time()
            with open(STATS_FILE, 'w') as f:
                json.dump(stats, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save statistics: {e}")


def update_statistics(ips: list):
    """Update statistics with new IPs"""
    stats = load_statistics()
    stats["total_attempts"] += 1
    
    for ip in ips:
        if ip in stats["ip_addresses"]:
            stats["ip_addresses"][ip] += 1
        else:
            stats["ip_addresses"][ip] = 1
    
    save_statistics(stats)
    
    # Send stats update every 100 attempts
    if stats["total_attempts"] % 100 == 0:
        msg = f"📈 <b>Промежуточная статистика</b>\n\n"
        msg += f"Попыток: {stats['total_attempts']}\n"
        msg += f"Уникальных IP: {len(stats['ip_addresses'])}\n\n"
        msg += f"<i>Отправь /stats для подробной статистики</i>"
        send_telegram_message(msg)


def get_statistics_message():
    """Generate statistics message for Telegram"""
    stats = load_statistics()
    
    total_attempts = stats["total_attempts"]
    ip_dict = stats["ip_addresses"]
    unique_ips = len(ip_dict)
    
    # Count duplicates
    duplicates = {ip: count for ip, count in ip_dict.items() if count > 1}
    duplicate_count = len(duplicates)
    
    # Runtime
    start_time = stats.get("start_time", time.time())
    runtime = time.time() - start_time
    runtime_hours = int(runtime // 3600)
    runtime_mins = int((runtime % 3600) // 60)
    
    msg = "📊 <b>СТАТИСТИКА</b>\n\n"
    msg += f"<b>Общее количество попыток:</b> {total_attempts}\n"
    msg += f"<b>Уникальных IP:</b> {unique_ips}\n"
    msg += f"<b>IP с дублями:</b> {duplicate_count}\n"
    msg += f"<b>Время работы:</b> {runtime_hours}ч {runtime_mins}мин\n\n"
    
    # Top 10 most common IPs
    if ip_dict:
        msg += "<b>🔥 Топ-10 самых частых IP:</b>\n"
        sorted_ips = sorted(ip_dict.items(), key=lambda x: x[1], reverse=True)[:10]
        for ip, count in sorted_ips:
            msg += f"  • {ip}: {count}x\n"
    
    # Show duplicates
    if duplicates:
        msg += f"\n<b>📋 IP с дублями ({len(duplicates)}):</b>\n"
        sorted_dupes = sorted(duplicates.items(), key=lambda x: x[1], reverse=True)[:15]
        for ip, count in sorted_dupes:
            msg += f"  • {ip}: {count}x\n"
        if len(duplicates) > 15:
            msg += f"  ... и ещё {len(duplicates) - 15}"
    
    return msg


def send_telegram_message(message: str):
    """Send message to Telegram"""
    if not TELEGRAM_CHAT_ID:
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")


def check_and_notify_auth_error(exception):
    """Check if exception is 401 and send Telegram notification, then exit"""
    if hasattr(exception, 'response') and exception.response is not None:
        if exception.response.status_code == 401:
            logger.error("❌ API токен истёк!")
            
            # Set shutdown event to stop all workers
            shutdown_event.set()
            
            # Send final statistics
            stats_msg = get_statistics_message()
            msg = "⚠️ <b>AUTH ERROR - ОСТАНОВКА</b>\n\n"
            msg += "API токен истёк! Скрипт остановлен.\n\n"
            msg += stats_msg
            send_telegram_message(msg)
            
            # Exit script
            logger.error("Exiting due to authentication error")
            time.sleep(2)  # Give time for telegram message to send
            sys.exit(1)
    return False


def cleanup_vms(client):
    """Delete all created VMs"""
    global created_vms
    if not created_vms:
        return
    
    logger.info("Cleaning up created VMs...")
    send_telegram_message("🧹 <b>Очистка VM...</b>\n\nУдаляю созданные виртуальные машины...")
    
    deleted_count = 0
    for vm_id in created_vms:
        try:
            if client.delete_server(vm_id):
                deleted_count += 1
                logger.info(f"Deleted VM: {vm_id}")
        except Exception as e:
            logger.error(f"Failed to delete VM {vm_id}: {e}")
    
    msg = f"✅ <b>Очистка завершена</b>\n\nУдалено VM: {deleted_count} из {len(created_vms)}"
    send_telegram_message(msg)
    created_vms = []


def telegram_bot_listener():
    """Background thread to listen for Telegram bot commands"""
    last_update_id = 0
    
    while not shutdown_event.is_set():
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
            params = {"offset": last_update_id + 1, "timeout": 10}
            
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            if data.get("ok") and data.get("result"):
                for update in data["result"]:
                    update_id = update.get("update_id")
                    if update_id:
                        last_update_id = max(last_update_id, update_id)
                    
                    message = update.get("message", {})
                    text = message.get("text", "")
                    
                    if text in ["/stats", "/статистика", "/stat"]:
                        stats_msg = get_statistics_message()
                        send_telegram_message(stats_msg)
                    elif text == "/help" or text == "/помощь":
                        help_msg = "ℹ️ <b>ДОСТУПНЫЕ КОМАНДЫ</b>\n\n"
                        help_msg += "/stats - Показать статистику\n"
                        help_msg += "/help - Показать эту справку"
                        send_telegram_message(help_msg)
        except Exception as e:
            logger.debug(f"Telegram listener error: {e}")
            if not shutdown_event.wait(5):
                continue


def signal_handler(sig, frame):
    """Handle Ctrl+C"""
    logger.info("\n⚠️  Received interrupt signal. Stopping all workers...")
    
    # Set shutdown event to stop all threads
    shutdown_event.set()
    
    # Send statistics before stopping
    stats_msg = get_statistics_message()
    send_telegram_message(f"🛑 <b>ОСТАНОВКА СКРИПТА</b>\n\n{stats_msg}")
    
    logger.info("Shutdown signal sent to all workers. Exiting...")
    
    # Force exit
    sys.exit(0)


class VKCloudClient:
    """Client for VK Cloud Nova API"""
    
    def __init__(self, auth_token: str, endpoint: str):
        self.auth_token = auth_token
        self.endpoint = endpoint
        self.headers = {
            "X-Auth-Token": auth_token,
            "Content-Type": "application/json"
        }
    
    def create_server(self, name: str, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new VM"""
        url = f"{self.endpoint}/servers"
        
        server_config = {
            "name": name,
            "flavorRef": config["flavorRef"],
            "adminPass": config["adminPass"],
            "networks": config.get("networks", []),
            "metadata": config.get("metadata", {})
        }
        
        # Add imageRef only if provided (not needed with block_device_mapping_v2)
        if config.get("imageRef"):
            server_config["imageRef"] = config["imageRef"]
        
        # Add block_device_mapping_v2 if provided
        if config.get("block_device_mapping_v2"):
            server_config["block_device_mapping_v2"] = config["block_device_mapping_v2"]
        
        payload = {"server": server_config}
        
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create server: {e}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")
            check_and_notify_auth_error(e)
            return None
    
    def get_server_details(self, server_id: str) -> Optional[Dict[str, Any]]:
        """Get server details"""
        url = f"{self.endpoint}/servers/{server_id}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get server details for {server_id}: {e}")
            check_and_notify_auth_error(e)
            return None
    
    def delete_server(self, server_id: str) -> bool:
        """Delete a VM"""
        url = f"{self.endpoint}/servers/{server_id}"
        
        try:
            response = requests.delete(url, headers=self.headers)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to delete server {server_id}: {e}")
            check_and_notify_auth_error(e)
            return False
    
    def wait_for_server_active(self, server_id: str, timeout: int = 300) -> bool:
        """Wait for server to become ACTIVE"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Check if shutdown requested
            if shutdown_event.is_set():
                logger.info(f"Shutdown requested while waiting for {server_id}")
                return False
            
            details = self.get_server_details(server_id)
            if not details:
                return False
            
            status = details.get("server", {}).get("status")
            logger.debug(f"Server {server_id} status: {status}")
            
            if status == "ACTIVE":
                return True
            elif status == "ERROR":
                logger.error(f"Server {server_id} entered ERROR state")
                return False
            
            # Human-like waiting: variable check intervals
            check_interval = random.randint(3, 8)  # Sometimes check more/less frequently
            if shutdown_event.wait(check_interval):
                return False
        
        logger.error(f"Server {server_id} did not become ACTIVE within timeout")
        return False
    
    def get_server_ips(self, server_id: str) -> list:
        """Extract all IPs from server details"""
        details = self.get_server_details(server_id)
        if not details:
            return []
        
        ips = []
        addresses = details.get("server", {}).get("addresses", {})
        
        for network_name, network_addresses in addresses.items():
            for addr_info in network_addresses:
                ip = addr_info.get("addr")
                if ip:
                    ips.append(ip)
        
        return ips
    
    def configure_server_network(self, server_id: str) -> bool:
        """Configure server network interface after creation"""
        try:
            # Get server details
            details = self.get_server_details(server_id)
            if not details:
                return False
            
            # Check if server has IP addresses
            addresses = details.get("server", {}).get("addresses", {})
            if not addresses:
                logger.warning(f"Server {server_id} has no IP addresses")
                return False
            
            # Log network configuration
            for network_name, network_ips in addresses.items():
                for ip_info in network_ips:
                    ip = ip_info.get("addr")
                    if ip:
                        logger.info(f"Server {server_id} configured with IP: {ip} on network: {network_name}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to configure network for server {server_id}: {e}")
            return False
    
    def list_flavors(self) -> Optional[Dict[str, Any]]:
        """List available flavors"""
        url = f"{self.endpoint}/flavors/detail"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to list flavors: {e}")
            check_and_notify_auth_error(e)
            return None


def generate_random_vm_name() -> str:
    """Generate random VM name with random pattern"""
    pattern = random.choice([
        # Pattern 1: word-word-chars
        lambda: f"{''.join(random.choices(string.ascii_lowercase, k=random.randint(4, 7)))}-{''.join(random.choices(string.ascii_lowercase, k=random.randint(4, 6)))}-{''.join(random.choices(string.ascii_lowercase + string.digits, k=random.randint(4, 8)))}",
        # Pattern 2: word-word-word
        lambda: f"{''.join(random.choices(string.ascii_lowercase, k=random.randint(3, 5)))}-{''.join(random.choices(string.ascii_lowercase, k=random.randint(3, 5)))}-{''.join(random.choices(string.ascii_lowercase, k=random.randint(3, 5)))}",
        # Pattern 3: word-chars
        lambda: f"{''.join(random.choices(string.ascii_lowercase, k=random.randint(5, 8)))}-{''.join(random.choices(string.ascii_lowercase + string.digits, k=random.randint(6, 10)))}",
        # Pattern 4: chars-word
        lambda: f"{''.join(random.choices(string.ascii_lowercase + string.digits, k=random.randint(5, 8)))}-{''.join(random.choices(string.ascii_lowercase, k=random.randint(4, 7)))}",
        # Pattern 5: word-word
        lambda: f"{''.join(random.choices(string.ascii_lowercase, k=random.randint(4, 7)))}-{''.join(random.choices(string.ascii_lowercase, k=random.randint(4, 7)))}",
        # Pattern 6: word-digits
        lambda: f"{''.join(random.choices(string.ascii_lowercase, k=random.randint(4, 7)))}-{''.join(random.choices(string.digits, k=random.randint(4, 8)))}",
        # Pattern 7: digits-word
        lambda: f"{''.join(random.choices(string.digits, k=random.randint(3, 6)))}-{''.join(random.choices(string.ascii_lowercase, k=random.randint(4, 7)))}",
        # Pattern 8: single long word
        lambda: ''.join(random.choices(string.ascii_lowercase + string.digits, k=random.randint(8, 15))),
        # Pattern 9: word-word-word-chars
        lambda: f"{''.join(random.choices(string.ascii_lowercase, k=random.randint(3, 4)))}-{''.join(random.choices(string.ascii_lowercase, k=random.randint(3, 4)))}-{''.join(random.choices(string.ascii_lowercase, k=random.randint(3, 4)))}-{''.join(random.choices(string.ascii_lowercase + string.digits, k=random.randint(4, 6)))}",
        # Pattern 10: mixed alphanumeric without separators
        lambda: ''.join(random.choices(string.ascii_lowercase + string.digits, k=random.randint(10, 18))),
    ])
    return pattern()


def human_like_delay(min_seconds: int, max_seconds: int, distribution: str = "normal") -> int:
    """
    Generate human-like delay with natural distribution
    distribution: "normal" (most common), "exponential" (longer tails), "uniform"
    """
    if distribution == "normal":
        # Normal distribution - most delays around the middle, some outliers
        mean = (min_seconds + max_seconds) / 2
        std = (max_seconds - min_seconds) / 4
        delay = int(random.gauss(mean, std))
    elif distribution == "exponential":
        # Exponential - more short delays, occasional very long ones
        delay = int(random.expovariate(1.0 / ((min_seconds + max_seconds) / 2)))
    else:
        # Uniform distribution
        delay = random.randint(min_seconds, max_seconds)
    
    # Clamp to bounds
    return max(min_seconds, min(max_seconds, delay))


def random_break_chance(attempt: int) -> bool:
    """
    Simulate human behavior: sometimes take a break
    Higher chance after multiple attempts
    """
    # 5% base chance, increases with attempts
    break_chance = 0.05 + (attempt * 0.01)
    return random.random() < min(break_chance, 0.25)  # Max 25% chance


def get_time_based_delay_multiplier() -> float:
    """
    Simulate human activity patterns based on time of day
    More activity during work hours, less at night
    """
    hour = datetime.now().hour
    
    # Work hours (9-18) - normal activity
    if 9 <= hour <= 18:
        return random.uniform(0.8, 1.2)
    # Evening (18-22) - moderate activity
    elif 18 < hour <= 22:
        return random.uniform(1.0, 1.5)
    # Night (22-6) - low activity
    elif hour >= 22 or hour < 6:
        return random.uniform(1.5, 3.0)
    # Early morning (6-9) - increasing activity
    else:
        return random.uniform(1.2, 1.8)


def human_like_wait(seconds: int, check_interval: int = 5):
    """
    Wait with human-like behavior: occasional micro-pauses
    """
    elapsed = 0
    while elapsed < seconds:
        if shutdown_event.is_set():
            return True
        
        # Sometimes pause briefly (like human checking something)
        if random.random() < 0.1:  # 10% chance
            micro_pause = random.uniform(0.5, 2.0)
            time.sleep(micro_pause)
            elapsed += micro_pause
        
        wait_time = min(check_interval, seconds - elapsed)
        if shutdown_event.wait(wait_time):
            return True
        elapsed += wait_time
    
    return False


def is_ip_in_range(ip_str: str) -> bool:
    """Check if IP is in any of the target ranges"""
    try:
        ip = ipaddress.IPv4Address(ip_str)
        for start, end in IP_RANGES:
            if start <= ip <= end:
                return True
        return False
    except:
        return False


def process_vm_creation(client: VKCloudClient, worker_id: int) -> Optional[Dict[str, Any]]:
    """
    Create VMs until one with correct IP is found
    Returns VM info if successful, None otherwise
    """
    attempt = 0
    
    while True:
        # Check if shutdown requested
        if shutdown_event.is_set():
            logger.info(f"[Worker {worker_id}] Shutdown requested, exiting...")
            return None
        
        attempt += 1
        
        # Simulate human behavior: occasional breaks
        if random_break_chance(attempt):
            break_duration = human_like_delay(60, 300, "exponential")  # 1-5 minutes
            logger.info(f"[Worker {worker_id}] Taking a break for {break_duration} seconds...")
            if human_like_wait(break_duration):
                return None
        
        # Longer break after many attempts (like human getting tired)
        if attempt > 0 and attempt % 20 == 0:
            long_break = human_like_delay(180, 600, "exponential")  # 3-10 minutes
            logger.info(f"[Worker {worker_id}] Long break after {attempt} attempts: {long_break} seconds...")
            if human_like_wait(long_break):
                return None
        
        # Generate random VM name
        vm_name = generate_random_vm_name()
        
        logger.info(f"[Worker {worker_id}] Creating VM: {vm_name} (attempt {attempt})")
        
        # Human-like delay with time-based adjustment
        base_delay = human_like_delay(45, 120, "normal")  # 45-120 seconds base
        time_multiplier = get_time_based_delay_multiplier()
        delay = int(base_delay * time_multiplier)
        
        # Sometimes "think" before creating (like human double-checking)
        if random.random() < 0.3:  # 30% chance
            thinking_time = random.uniform(5, 15)
            logger.info(f"[Worker {worker_id}] Thinking for {thinking_time:.1f} seconds...")
            if shutdown_event.wait(thinking_time):
                return None
        
        logger.info(f"[Worker {worker_id}] Waiting {delay} seconds before creating VM...")
        if human_like_wait(delay):
            return None
        
        # Sometimes "change mind" before creating (5% chance)
        if random.random() < 0.05:
            logger.info(f"[Worker {worker_id}] Changed mind, skipping this VM...")
            skip_delay = human_like_delay(20, 60, "normal")
            if human_like_wait(skip_delay):
                return None
            continue
        
        # Create server
        result = client.create_server(vm_name, VM_CONFIG)
        if not result:
            logger.error(f"[Worker {worker_id}] Failed to create VM, retrying...")
            # Human-like retry delay: longer when frustrated
            retry_delay = human_like_delay(15, 45, "exponential")
            logger.info(f"[Worker {worker_id}] Waiting {retry_delay} seconds before retry...")
            if human_like_wait(retry_delay):
                return None
            continue
        
        server_id = result.get("server", {}).get("id")
        if not server_id:
            logger.error(f"[Worker {worker_id}] No server ID in response")
            continue
        
        # Track created VM
        global created_vms
        created_vms.append(server_id)
        
        logger.info(f"[Worker {worker_id}] VM created with ID: {server_id}, waiting for ACTIVE status...")
        
        # Wait for server to become active (with human-like patience)
        # Sometimes check status more frequently, sometimes less
        if not client.wait_for_server_active(server_id):
            logger.warning(f"[Worker {worker_id}] VM {server_id} failed to become ACTIVE, deleting...")
            if client.delete_server(server_id):
                if server_id in created_vms:
                    created_vms.remove(server_id)
            # Human reaction: wait a bit after failure
            failure_delay = human_like_delay(10, 30, "normal")
            if human_like_wait(failure_delay):
                return None
            continue
        
        # Get IPs
        ips = client.get_server_ips(server_id)
        logger.info(f"[Worker {worker_id}] VM {server_id} is ACTIVE with IPs: {ips}")
        
        # Configure network interface
        if not client.configure_server_network(server_id):
            logger.warning(f"[Worker {worker_id}] Failed to configure network for VM {server_id}")
        
        # Update statistics
        if ips:
            update_statistics(ips)
        
        # Check if any IP is in range
        matching_ips = [ip for ip in ips if is_ip_in_range(ip)]
        
        if matching_ips:
            logger.info(f"[Worker {worker_id}] ✓ SUCCESS! Found VM with IP in range: {matching_ips}")
            
            # Send Telegram notification
            msg = f"🎉 <b>УСПЕХ! Найден VM с нужным IP</b>\n\n"
            msg += f"<b>Name:</b> {vm_name}\n"
            msg += f"<b>ID:</b> {server_id}\n"
            msg += f"<b>IPs:</b> {', '.join(matching_ips)}\n"
            msg += f"<b>All IPs:</b> {', '.join(ips)}"
            send_telegram_message(msg)
            
            return {
                "server_id": server_id,
                "name": vm_name,
                "ips": ips,
                "matching_ips": matching_ips,
                "worker_id": worker_id
            }
        else:
            logger.info(f"[Worker {worker_id}] ✗ IP not in range, deleting VM {server_id}...")
            if client.delete_server(server_id):
                if server_id in created_vms:
                    created_vms.remove(server_id)
            
            # Human-like behavior: sometimes take longer to decide next action
            logger.info(f"[Worker {worker_id}] VM deleted, considering next step...")
            
            # Sometimes "review" what happened (10% chance)
            if random.random() < 0.1:
                review_time = human_like_delay(10, 30, "normal")
                logger.info(f"[Worker {worker_id}] Reviewing results for {review_time} seconds...")
                if human_like_wait(review_time):
                    return None
            
            # Wait after deletion with human-like delay
            post_delete_delay = human_like_delay(20, 90, "normal")
            time_multiplier = get_time_based_delay_multiplier()
            post_delete_delay = int(post_delete_delay * time_multiplier)
            
            logger.info(f"[Worker {worker_id}] Waiting {post_delete_delay} seconds before creating new VM...")
            if human_like_wait(post_delete_delay):
                return None


def main():
    """Main function"""
    global executor
    
    # Setup signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    logger.info("=" * 80)
    logger.info("VK Cloud VM Creator - IP Range Hunter")
    logger.info("Target IP Ranges:")
    for i, (start, end) in enumerate(IP_RANGES, 1):
        logger.info(f"  Range {i}: {start} - {end}")
    logger.info(f"Workers: {MAX_WORKERS}")
    logger.info("=" * 80)
    
    # Send start notification
    msg = "🚀 <b>ЗАПУСК СКРИПТА</b>\n\n"
    msg += f"<b>Воркеров:</b> {MAX_WORKERS}\n"
    msg += f"<b>IP диапазоны:</b>\n"
    for i, (start, end) in enumerate(IP_RANGES, 1):
        msg += f"  {i}. {start} - {end}\n"
    msg += f"\n<i>Отправь /stats для просмотра статистики</i>"
    send_telegram_message(msg)
    
    # Start Telegram bot listener in background thread
    if TELEGRAM_CHAT_ID:
        bot_thread = threading.Thread(target=telegram_bot_listener, daemon=True)
        bot_thread.start()
        logger.info("Telegram bot listener started")
    
    client = VKCloudClient(AUTH_TOKEN, NOVA_ENDPOINT)
    
    # Check configuration
    logger.info("Checking configuration...")
    
    if not VM_CONFIG["flavorRef"]:
        logger.info("FlavorRef not set, listing available flavors...")
        flavors = client.list_flavors()
        if flavors:
            logger.info("Available flavors:")
            for flavor in flavors.get("flavors", [])[:5]:
                logger.info(f"  - {flavor.get('name')} (ID: {flavor.get('id')})")
            logger.error("Please set VM_CONFIG['flavorRef'] in the script")
            return
    
    # imageRef is not required when using block_device_mapping_v2
    if not VM_CONFIG["imageRef"] and not VM_CONFIG.get("block_device_mapping_v2"):
        logger.error("Please set VM_CONFIG['imageRef'] or VM_CONFIG['block_device_mapping_v2'] in the script")
        return
    
    if not VM_CONFIG["networks"] or not VM_CONFIG["networks"][0].get("uuid"):
        logger.error("Please set VM_CONFIG['networks'][0]['uuid'] in the script")
        return
    
    # Start parallel processing
    logger.info(f"Starting {MAX_WORKERS} workers...")
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as exec:
        executor = exec
        futures = {
            executor.submit(process_vm_creation, client, i): i 
            for i in range(1, MAX_WORKERS + 1)
        }
        
        for future in as_completed(futures):
            if shutdown_event.is_set():
                break
            
            try:
                result = future.result()
                if result:
                    logger.info("=" * 80)
                    logger.info("🎉 FOUND MATCHING VM!")
                    logger.info(f"Server ID: {result['server_id']}")
                    logger.info(f"Name: {result['name']}")
                    logger.info(f"All IPs: {result['ips']}")
                    logger.info(f"Matching IPs: {result['matching_ips']}")
                    logger.info("=" * 80)
                    
                    # Set shutdown to stop other workers
                    shutdown_event.set()
                    
                    return result
            except Exception as e:
                logger.error(f"Worker error: {e}")
                if shutdown_event.is_set():
                    break
    
    logger.info("Process completed")


if __name__ == "__main__":
    main()

