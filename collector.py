import requests
from bs4 import BeautifulSoup
import re

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
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, timeout=10, headers=headers)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        messages = soup.find_all('div', class_='tgme_widget_message_text')
        print(f"Found {len(messages)} messages in {channel_username}")
        
        for message in messages:
            text = message.get_text()
            
            links = re.findall(
                r'vmess://[A-Za-z0-9+/=]+|vless://[^\s]+|trojan://[^\s]+|ss://[^\s]+', 
                text
            )
            
            if links:
                print(f"Found {len(links)} links in message")
                configs.extend(links)
            
        print(f"{channel_username}: {len(configs)} total configs")
        return configs
        
    except Exception as e:
        print(f"Error in {channel_username}: {e}")
        return []

def main():
    print("Starting proxy config collector...")
    
    all_configs = []
    
    for channel in CHANNELS:
        configs = get_channel_messages(channel)
        all_configs.extend(configs)
        print(f"Total so far: {len(all_configs)}")
    
    unique_configs = list(set(all_configs))
    print(f"Unique configs before limit: {len(unique_configs)}")
    
    final_configs = unique_configs[:MAX_CONFIGS]
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for config in final_configs:
            f.write(config + '\n')
    
    print(f"Done! {len(final_configs)} configs saved to {OUTPUT_FILE}")

if __name__ == '__main__':
    main()
