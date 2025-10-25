# VK Cloud VM IP Hunter

Automated VK Cloud virtual machine creator that searches for VMs with IP addresses in specific ranges. Creates VMs in parallel, checks their IPs, and deletes those that don't match the target ranges.

## Features

- 🚀 **Parallel VM Creation** - Creates multiple VMs simultaneously (configurable workers)
- 🎯 **IP Range Filtering** - Checks if VM IP is in target ranges
- 🔄 **Auto Retry** - Automatically deletes and recreates VMs with non-matching IPs
- 📊 **Statistics Tracking** - Records all attempts and IP addresses with duplicates count
- 🤖 **Telegram Notifications** - Optional notifications for events (start, success, errors, stop)
- ⚡ **Fast Shutdown** - Properly handles Ctrl+C with cleanup
- 🛑 **Auth Error Handling** - Automatically stops when API token expires

## Requirements

- Python 3.7+
- VK Cloud account with API access
- Valid VK Cloud authentication token

## Installation

1. Clone the repository:
```bash
git clone <your-repo-url>
cd vk_parser
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

#### VM Configuration IDs

Run the helper script to get available options:

```bash
export VK_CLOUD_AUTH_TOKEN="your_token"
python3 vk_cloud_get_config.py
```

This will list:
- **VM_FLAVOR_ID** - Available flavors (VM sizes)
  - Example: `STD2-1-1` = 1 vCPU, 1GB RAM
  - Example: `Basic-1-2-10` = 1 vCPU, 2GB RAM, 10GB disk
  
- **VM_IMAGE_ID** - Available OS images
  - Example: Ubuntu 22.04, CentOS 9, etc.
  
- **VM_NETWORK_ID** - Available networks
  - Usually "ext-net" or "internet" for external network

### Example .env File

```bash
# VK Cloud API
VK_CLOUD_AUTH_TOKEN=gAAAAABhZ...your_token_here
VK_CLOUD_PROJECT_ID=abc123def456...
VK_CLOUD_NOVA_ENDPOINT=https://infra.mail.ru:8774/v2.1

# VM Configuration (get IDs from vk_cloud_get_config.py)
VM_FLAVOR_ID=9cdbca68-5e15-4c54-979d-9952785ba33e  # STD2-1-1
VM_IMAGE_ID=9b8ad1ea-cc40-4910-9e5e-eb12bc7e208c   # Ubuntu 24.04
VM_NETWORK_ID=ec8c610e-6387-447e-83d2-d2c541e88164 # ext-net
VM_ADMIN_PASSWORD=SecurePass123!

# Telegram (optional)
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789

# Workers
MAX_WORKERS=14
```

## Usage

### Basic Usage

```bash
export VK_CLOUD_AUTH_TOKEN="your_token"
export VM_FLAVOR_ID="your_flavor_id"
export VM_IMAGE_ID="your_image_id"
export VM_NETWORK_ID="your_network_id"

python3 vk_cloud_vm_creator.py
```

### With Telegram Notifications

```bash
export TELEGRAM_BOT_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="your_chat_id"

python3 vk_cloud_vm_creator.py
```

## How It Works

1. **Creates VMs** in parallel (14 workers by default)
2. **Waits** for each VM to become ACTIVE (~30-60 seconds)
3. **Checks IPs** against configured ranges
4. **Keeps** VMs with matching IPs
5. **Deletes** VMs with non-matching IPs and creates new ones
6. **Stops** when a matching VM is found or Ctrl+C is pressed

## IP Ranges

Default IP ranges to search (configurable in code):
- `95.163.248.10` - `95.163.251.250`
- `217.16.24.1` - `217.16.24.2`
- `217.16.24.3` - `217.16.27.253`

## Telegram Bot Commands

If Telegram notifications are enabled:

- `/stats` - Show statistics
- `/help` - Show available commands

## Statistics

Statistics are saved to `vm_statistics.json`:
- Total attempts count
- All IP addresses encountered with occurrence count
- Duplicate IP statistics
- Runtime information

## Helper Scripts

- `vk_cloud_get_config.py` - Get available flavors, images, and networks
- `test_vk_cloud_connection.py` - Test API connection and authentication
- `demo_ip_check.py` - Demo IP range checking logic

## Example Output

```
================================================================================
VK Cloud VM Creator - IP Range Hunter
Target IP Ranges:
  Range 1: 95.163.248.10 - 95.163.251.250
  Range 2: 217.16.24.1 - 217.16.24.2
  Range 3: 217.16.24.3 - 217.16.27.253
Workers: 14
================================================================================

[Worker 1] Creating VM: vm-hunt-1761394962-worker1-attempt1
[Worker 1] VM created with ID: abc-123, waiting for ACTIVE status...
[Worker 1] VM abc-123 is ACTIVE with IPs: ['95.163.249.100']
[Worker 1] ✓ SUCCESS! Found VM with IP in range: ['95.163.249.100']

🎉 FOUND MATCHING VM!
Server ID: abc-123
Name: vm-hunt-1761394962-worker1-attempt1
All IPs: ['95.163.249.100']
Matching IPs: ['95.163.249.100']
```

## Security

⚠️ **Important**:
- Never commit `.env` file or tokens to Git
- Use strong passwords for VM admin accounts
- Rotate API tokens regularly
- Review and delete unused VMs to avoid costs

## Cost Warning

💰 Creating multiple VMs will incur costs on your VK Cloud account. Monitor your quota and balance. The script automatically deletes VMs with non-matching IPs, but charges may still apply.

## Stopping the Script

Press `Ctrl+C` to gracefully stop the script. All workers will shut down and final statistics will be sent via Telegram (if configured).

## Troubleshooting

### 401 Unauthorized
- Token expired or invalid
- Get a new token from VK Cloud console
- Script will automatically stop and send notification

### 403 Forbidden
- Quota exceeded or insufficient permissions
- Check your project quotas
- Verify flavor/image/network IDs are correct

### VMs not becoming ACTIVE
- Check VK Cloud service status
- Try different flavor or image
- Check network configuration

## License

MIT License - See LICENSE file for details

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Disclaimer

This tool is provided as-is. Users are responsible for managing their VK Cloud resources and associated costs. Always monitor your VM usage and costs.

