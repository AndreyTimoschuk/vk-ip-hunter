# VK Cloud Floating IP Hunter

Automated VK Cloud floating IP reserver that searches for IP addresses in specific ranges. Reserves floating IPs in parallel, checks their addresses, and releases those that don't match the target ranges.

## Features

- 🚀 **Parallel IP Reservation** - Reserves multiple IPs simultaneously (configurable workers)
- 🎯 **IP Range Filtering** - Checks if IP is in target ranges
- 🔄 **Auto Retry** - Automatically releases and reserves new IPs with non-matching addresses
- 📊 **Statistics Tracking** - Records all attempts and IP addresses with duplicates count
- 🤖 **Telegram Notifications** - Optional notifications for events (start, success, errors, stop)
- ⚡ **Fast Shutdown** - Properly handles Ctrl+C with cleanup
- 🛑 **Auth Error Handling** - Automatically stops when API token expires
- 💰 **Cost Effective** - Much cheaper and faster than creating VMs

## Advantages Over VM Creation

- **10x Faster** - IP reservation takes ~1-3 seconds vs ~30-60 seconds for VM
- **90% Cheaper** - Floating IPs cost ~$1/month vs VMs costing $5-50/month
- **Simpler** - No need for OS images, flavors, or boot configuration
- **No Cleanup Required** - Can leave successful IPs reserved

## Requirements

- Python 3.7+
- VK Cloud account with API access
- Valid VK Cloud authentication token

## Installation

1. Clone the repository:
```bash
git clone https://github.com/AndreyTimoschuk/vk-ip-hunter.git
cd vk-ip-hunter
```

2. Install dependencies:
```bash
pip install -r requirements_vk_cloud.txt
```

3. Copy and configure environment variables:
```bash
cp env.example .env
# Edit .env with your credentials
```

## Configuration

Create a `.env` file from `env.example` and set the required variables.

### Where to Get Configuration Values

#### Network ID

Run the helper script to get available networks:

```bash
export VK_CLOUD_AUTH_TOKEN="your_token"
python3 vk_cloud_get_config.py
```

This will list available networks. Look for external networks (usually named "ext-net" or "internet").

### Example .env File

```bash
# VK Cloud API
VK_CLOUD_AUTH_TOKEN=gAAAAABhZ...your_token_here
VK_CLOUD_PROJECT_ID=abc123def456...
VK_CLOUD_NEUTRON_ENDPOINT=https://infra.mail.ru:9696/v2.0

# Floating IP Configuration
VK_CLOUD_FLOATING_NETWORK_ID=298117ae-3fa4-4109-9e08-8be5602be5a2  # ext-net

# Telegram (optional)
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789

# Workers
MAX_WORKERS=13
```

## Usage

### Basic Usage

```bash
export VK_CLOUD_AUTH_TOKEN="your_token"
export VK_CLOUD_PROJECT_ID="your_project_id"

python3 vk_cloud_ip_reserver.py
```

### With Telegram Notifications

```bash
export TELEGRAM_BOT_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="your_chat_id"

python3 vk_cloud_ip_reserver.py
```

### Using .env File

```bash
# Just run the script, it will load from .env
python3 vk_cloud_ip_reserver.py
```

## How It Works

1. **Reserves Floating IPs** in parallel (13 workers by default)
2. **Instantly checks** the assigned IP address
3. **Keeps** IPs in target ranges
4. **Releases** IPs outside target ranges and reserves new ones
5. **Stops** when a matching IP is found or Ctrl+C is pressed

## IP Ranges

Default IP ranges to search (configurable in code):
- `95.163.248.10` - `95.163.251.250` (ext-sub35)
- `217.16.16.0` - `217.16.23.255` (ext-sub8)
- `90.156.150.0` - `90.156.151.255` (ext-sub9)
- `217.16.24.0` - `217.16.27.255` (ext-sub9)

## Telegram Bot Commands

If Telegram notifications are enabled:

- `/stats` - Show statistics
- `/help` - Show available commands

## Statistics

Statistics are saved to `ip_statistics.json`:
- Total attempts count
- All IP addresses encountered with occurrence count
- Duplicate IP statistics
- Runtime information

## Helper Scripts

- `vk_cloud_get_config.py` - Get available networks and configuration
- `test_vk_cloud_connection.py` - Test API connection and authentication
- `demo_ip_check.py` - Demo IP range checking logic

## Example Output

```
================================================================================
VK Cloud Floating IP Reserver - IP Range Hunter
Target IP Ranges:
  Range 1: 95.163.248.10 - 95.163.251.250
  Range 2: 217.16.16.0 - 217.16.23.255
  Range 3: 90.156.150.0 - 90.156.151.255
  Range 4: 217.16.24.0 - 217.16.27.255
Workers: 13
================================================================================

[Worker 1] Reserving floating IP (attempt 1)...
[Worker 1] Reserved floating IP: 95.163.249.100 (ID: abc-123)
[Worker 1] ✓ SUCCESS! Found IP in target range: 95.163.249.100

🎉 FOUND MATCHING IP!
IP Address: 95.163.249.100
IP ID: abc-123
```

## Performance

Typical performance metrics:
- **IP Reservation Time**: 1-3 seconds
- **Success Rate**: ~1-5% (depends on IP range availability)
- **Cost per Attempt**: ~$0.001 (vs ~$0.01-0.05 for VMs)
- **Throughput**: 10-20 IPs per minute with 13 workers

## Security

⚠️ **Important**:
- Never commit `.env` file or tokens to Git
- Rotate API tokens regularly
- Review and release unused floating IPs to avoid costs

## Cost Warning

💰 Reserving floating IPs will incur costs on your VK Cloud account, but much less than VMs:
- **Floating IP**: ~$1/month (~$0.0014/hour)
- **VM (smallest)**: ~$5/month (~$0.007/hour)

The script automatically releases IPs with non-matching addresses, minimizing costs.

## Stopping the Script

Press `Ctrl+C` to gracefully stop the script. All workers will shut down and final statistics will be sent via Telegram (if configured).

## Troubleshooting

### 401 Unauthorized
- Token expired or invalid
- Get a new token from VK Cloud console
- Script will automatically stop and send notification

### 403 Forbidden
- Quota exceeded or insufficient permissions
- Check your project quotas for floating IPs
- Verify network ID is correct

### Network Not Found
- Check VK_CLOUD_FLOATING_NETWORK_ID is set correctly
- Run `vk_cloud_get_config.py` to list available networks
- Make sure to use an external network (router:external = true)

## License

MIT License - See LICENSE file for details

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Disclaimer

This tool is provided as-is. Users are responsible for managing their VK Cloud resources and associated costs. Always monitor your floating IP usage and costs.
