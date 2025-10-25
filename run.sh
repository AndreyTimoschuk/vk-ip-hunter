#!/bin/bash

# Quick run script for VK Cloud VM Creator
# Load environment variables from .env file if exists

if [ -f .env ]; then
    echo "Loading environment variables from .env..."
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "Warning: .env file not found"
    echo "Copy env.example to .env and configure it first"
    exit 1
fi

# Check if required variables are set
if [ -z "$VK_CLOUD_AUTH_TOKEN" ]; then
    echo "Error: VK_CLOUD_AUTH_TOKEN is not set in .env"
    exit 1
fi

# Run the script
python3 vk_cloud_vm_creator.py

