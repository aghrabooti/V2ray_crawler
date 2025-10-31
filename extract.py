import requests
from bs4 import BeautifulSoup
import re
import json
import base64
from urllib.parse import urlparse

def load_channels():
    try:
        with open('channels.txt', 'r', encoding='utf-8') as f:
            channels = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            print(f"Loaded {len(channels)} channels from file")
            return channels
    except FileNotFoundError:
        print("channels.txt not found, using default channels")
        return ['v2rayngvpn', 'v2raycollector']

CHANNELS = load_channels()
MAX_CONFIGS = 300
OUTPUT_FILE = 'sub.txt'

def get_channel_messages(channel_username):
    url = f"https://t.me/s/{channel_username}"
    configs = []
    
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        messages = soup.find_all('div', class_='tgme_widget_message_text')
        
        for message in messages[-50:]:
            text = message.get_text()
            links = re.findall(
                r'(vmess://[^\s\n]+|vless://[^\s\n]+|trojan://[^\s\n]+|ss://[^\s\n]+)', 
                text, 
                re.IGNORECASE
            )
            configs.extend(links)
            
        print(f"{channel_username}: {len(configs)} configs")
        return configs
        
    except Exception as e:
        print(f"{channel_username}: {e}")
        return []

def main():
    print("Starting proxy config collector...")
    
    all_configs = []
    
    for channel in CHANNELS:
        configs = get_channel_messages(channel)
        all_configs.extend(configs)
    
    unique_configs = list(set(all_configs))[:MAX_CONFIGS]
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for config in unique_configs:
            f.write(config + '\n')
    
    print(f"Done! {len(unique_configs)} configs saved to {OUTPUT_FILE}")

if __name__ == '__main__':
    main()
