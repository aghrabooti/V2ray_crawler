import requests
from bs4 import BeautifulSoup
import re

def load_channels():
    try:
        with open('channels.txt', 'r', encoding='utf-8') as f:
            channels = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            return channels
    except FileNotFoundError:
        return ['v2rayngvpn', 'v2raycollector']

CHANNELS = load_channels()
MAX_CONFIGS = 300
OUTPUT_FILE = 'sub.txt'

def main():
    all_configs = []
    
    for channel in CHANNELS:
        try:
            url = f"https://t.me/s/{channel.replace('@', '')}"
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            messages = soup.find_all('div', class_='tgme_widget_message_text')
            configs = []
            
            for message in messages:
                text = message.get_text()
                links = re.findall(r'vmess://[^\s]+|vless://[^\s]+|trojan://[^\s]+|ss://[^\s]+', text)
                configs.extend(links)
            
            print(f"{channel}: {len(configs)} configs")
            all_configs.extend(configs)
            
        except Exception as e:
            print(f"Error in {channel}: {e}")
            continue
    
    unique_configs = list(set(all_configs))[:MAX_CONFIGS]
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for config in unique_configs:
            f.write(config + '\n')
    
    print(f"Done! {len(unique_configs)} configs saved")

if __name__ == '__main__':
    main()
