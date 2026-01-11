#!/usr/bin/env python3
"""
VK Cloud Floating IP Reserver with IP Range Filter
Reserves floating IPs and checks if they are in VK Cloud ranges with REAL services
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
from pathlib import Path
import threading
import os
import random
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
NEUTRON_ENDPOINT = os.getenv("VK_CLOUD_NEUTRON_ENDPOINT", "https://infra.mail.ru:9696/v2.0")
PROJECT_ID = os.getenv("VK_CLOUD_PROJECT_ID", "")
FLOATING_NETWORK_ID = os.getenv("VK_CLOUD_FLOATING_NETWORK_ID", "ec8c610e-6387-447e-83d2-d2c541e88164")  # internet

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# IP Ranges - Target subnets
IP_RANGES = [
    # 109.120.188.0/22 - Government and banking services
    (ipaddress.IPv4Address("109.120.188.0"), ipaddress.IPv4Address("109.120.191.255")),
    
    # 89.208.228.0/22 - Business services
    (ipaddress.IPv4Address("89.208.228.0"), ipaddress.IPv4Address("89.208.231.255")),
    
    # 5.188.140.0/22 - Retail and banking services
    (ipaddress.IPv4Address("5.188.140.0"), ipaddress.IPv4Address("5.188.143.255")),
    
    # 95.163.248.0/22 - Technology and business services
    (ipaddress.IPv4Address("95.163.248.0"), ipaddress.IPv4Address("95.163.251.255")),
]

# Parallel workers
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "13"))

# Global variables for cleanup
reserved_ips = []
executor = None
shutdown_event = threading.Event()

# Statistics file
STATS_FILE = Path(__file__).parent / "ip_statistics.json"
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


def update_statistics(ip: str):
    """Update statistics with new IP"""
    stats = load_statistics()
    stats["total_attempts"] += 1
    
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


def cleanup_floating_ips(client):
    """Delete all reserved floating IPs"""
    global reserved_ips
    if not reserved_ips:
        return
    
    logger.info("Cleaning up reserved floating IPs...")
    send_telegram_message("🧹 <b>Очистка IP...</b>\n\nОсвобождаю зарезервированные IP адреса...")
    
    deleted_count = 0
    for ip_id in reserved_ips:
        try:
            if client.delete_floating_ip(ip_id):
                deleted_count += 1
                logger.info(f"Released floating IP: {ip_id}")
        except Exception as e:
            logger.error(f"Failed to release floating IP {ip_id}: {e}")
    
    msg = f"✅ <b>Очистка завершена</b>\n\nОсвобождено IP: {deleted_count} из {len(reserved_ips)}"
    send_telegram_message(msg)
    reserved_ips = []


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
    """Client for VK Cloud Neutron API"""
    
    def __init__(self, auth_token: str, endpoint: str, project_id: str):
        self.auth_token = auth_token
        self.endpoint = endpoint
        self.project_id = project_id
        self.headers = {
            "X-Auth-Token": auth_token,
            "Content-Type": "application/json"
        }
    
    def create_floating_ip(self, network_id: str) -> Optional[Dict[str, Any]]:
        """Reserve a floating IP"""
        url = f"{self.endpoint}/floatingips"
        
        payload = {
            "floatingip": {
                "floating_network_id": network_id
            }
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create floating IP: {e}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")
            check_and_notify_auth_error(e)
            return None
    
    def get_floating_ip(self, ip_id: str) -> Optional[Dict[str, Any]]:
        """Get floating IP details"""
        url = f"{self.endpoint}/floatingips/{ip_id}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get floating IP details for {ip_id}: {e}")
            check_and_notify_auth_error(e)
            return None
    
    def delete_floating_ip(self, ip_id: str) -> bool:
        """Release a floating IP"""
        url = f"{self.endpoint}/floatingips/{ip_id}"
        
        try:
            response = requests.delete(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to delete floating IP {ip_id}: {e}")
            check_and_notify_auth_error(e)
            return False
    
    def list_networks(self) -> Optional[Dict[str, Any]]:
        """List available networks"""
        url = f"{self.endpoint}/networks"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to list networks: {e}")
            check_and_notify_auth_error(e)
            return None


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
        return random.uniform(0.9, 1.1)
    # Evening (18-22) - moderate activity
    elif 18 < hour <= 22:
        return random.uniform(1.0, 1.3)
    # Night (22-6) - low activity
    elif hour >= 22 or hour < 6:
        return random.uniform(1.2, 1.8)
    # Early morning (6-9) - increasing activity
    else:
        return random.uniform(1.1, 1.4)


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


def process_ip_reservation(client: VKCloudClient, worker_id: int, network_id: str) -> Optional[Dict[str, Any]]:
    """
    Reserve floating IPs until one with correct range is found
    Returns IP info if successful, None otherwise
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
            break_duration = human_like_delay(10, 60, "exponential")  # 10-60 seconds
            logger.info(f"[Worker {worker_id}] Taking a break for {break_duration} seconds...")
            if human_like_wait(break_duration):
                return None
        
        # Longer break after many attempts (like human getting tired)
        if attempt > 0 and attempt % 20 == 0:
            long_break = human_like_delay(30, 120, "exponential")  # 30-120 seconds
            logger.info(f"[Worker {worker_id}] Long break after {attempt} attempts: {long_break} seconds...")
            if human_like_wait(long_break):
                return None
        
        logger.info(f"[Worker {worker_id}] Reserving floating IP (attempt {attempt})...")
        
        # Human-like delay with time-based adjustment
        base_delay = human_like_delay(3, 10, "normal")  # 3-10 seconds base (faster than VM creation)
        time_multiplier = get_time_based_delay_multiplier()
        delay = int(base_delay * time_multiplier)
        
        # Sometimes "think" before creating (like human double-checking)
        if random.random() < 0.2:  # 20% chance
            thinking_time = random.uniform(1, 3)
            logger.info(f"[Worker {worker_id}] Thinking for {thinking_time:.1f} seconds...")
            if shutdown_event.wait(thinking_time):
                return None
        
        logger.info(f"[Worker {worker_id}] Waiting {delay} seconds before reserving IP...")
        if human_like_wait(delay):
            return None
        
        # Reserve floating IP
        result = client.create_floating_ip(network_id)
        if not result:
            logger.error(f"[Worker {worker_id}] Failed to reserve IP, retrying...")
            # Human-like retry delay: longer when frustrated
            retry_delay = human_like_delay(5, 15, "exponential")
            logger.info(f"[Worker {worker_id}] Waiting {retry_delay} seconds before retry...")
            if human_like_wait(retry_delay):
                return None
            continue
        
        ip_id = result.get("floatingip", {}).get("id")
        ip_address = result.get("floatingip", {}).get("floating_ip_address")
        
        if not ip_id or not ip_address:
            logger.error(f"[Worker {worker_id}] No IP ID or address in response")
            continue
        
        # Track reserved IP
        global reserved_ips
        reserved_ips.append(ip_id)
        
        logger.info(f"[Worker {worker_id}] Reserved floating IP: {ip_address} (ID: {ip_id})")
        
        # Update statistics
        update_statistics(ip_address)
        
        # Check if IP is in range
        if is_ip_in_range(ip_address):
            logger.info(f"[Worker {worker_id}] ✓ SUCCESS! Found IP in target range: {ip_address}")
            
            # Send Telegram notification
            msg = f"🎉 <b>УСПЕХ! Найден IP в нужном диапазоне</b>\n\n"
            msg += f"<b>IP:</b> {ip_address}\n"
            msg += f"<b>ID:</b> {ip_id}"
            send_telegram_message(msg)
            
            return {
                "ip_id": ip_id,
                "ip_address": ip_address,
                "worker_id": worker_id
            }
        else:
            logger.info(f"[Worker {worker_id}] ✗ IP not in range, releasing {ip_address}...")
            if client.delete_floating_ip(ip_id):
                if ip_id in reserved_ips:
                    reserved_ips.remove(ip_id)
            
            # Human-like behavior: sometimes take longer to decide next action
            logger.info(f"[Worker {worker_id}] IP released, considering next step...")
            
            # Sometimes "review" what happened (10% chance)
            if random.random() < 0.1:
                review_time = human_like_delay(2, 5, "normal")
                logger.info(f"[Worker {worker_id}] Reviewing results for {review_time} seconds...")
                if human_like_wait(review_time):
                    return None
            
            # Wait after deletion with human-like delay
            post_delete_delay = human_like_delay(2, 8, "normal")  # Shorter than VM
            time_multiplier = get_time_based_delay_multiplier()
            post_delete_delay = int(post_delete_delay * time_multiplier)
            
            logger.info(f"[Worker {worker_id}] Waiting {post_delete_delay} seconds before reserving new IP...")
            if human_like_wait(post_delete_delay):
                return None


def main():
    """Main function"""
    global executor
    
    # Setup signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    logger.info("=" * 80)
    logger.info("VK Cloud Floating IP Reserver - IP Range Hunter")
    logger.info("Target IP Ranges:")
    for i, (start, end) in enumerate(IP_RANGES, 1):
        logger.info(f"  Range {i}: {start} - {end}")
    logger.info(f"Workers: {MAX_WORKERS}")
    logger.info("=" * 80)
    
    # Send start notification
    msg = "🚀 <b>ЗАПУСК СКРИПТА (IP RESERVATION)</b>\n\n"
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
    
    client = VKCloudClient(AUTH_TOKEN, NEUTRON_ENDPOINT, PROJECT_ID)
    
    # Check configuration
    logger.info("Checking configuration...")
    
    if not FLOATING_NETWORK_ID:
        logger.info("Floating network ID not set, listing available networks...")
        networks = client.list_networks()
        if networks:
            logger.info("Available networks:")
            for network in networks.get("networks", [])[:5]:
                if network.get("router:external"):
                    logger.info(f"  - {network.get('name')} (ID: {network.get('id')}) [EXTERNAL]")
            logger.error("Please set FLOATING_NETWORK_ID in .env or script")
            return
    
    # Start parallel processing
    logger.info(f"Starting {MAX_WORKERS} workers...")
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as exec:
        executor = exec
        futures = {
            executor.submit(process_ip_reservation, client, i, FLOATING_NETWORK_ID): i 
            for i in range(1, MAX_WORKERS + 1)
        }
        
        for future in as_completed(futures):
            if shutdown_event.is_set():
                break
            
            try:
                result = future.result()
                if result:
                    logger.info("=" * 80)
                    logger.info("🎉 FOUND MATCHING IP!")
                    logger.info(f"IP Address: {result['ip_address']}")
                    logger.info(f"IP ID: {result['ip_id']}")
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
