import os
import re
from telegram import Update
from telegram.ext import Application, ContextTypes

def load_channels():
    try:
        with open('channels.txt', 'r', encoding='utf-8') as f:
            channels = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            print(f"Loaded {len(channels)} channels from file")
            return channels
    except FileNotFoundError:
        print("channels.txt not found, using default channels")
        return ['@v2rayngvpn', '@v2raycollector']

BOT_TOKEN = os.getenv('8384616715:AAHOXxcY8c7MQAiMQAh6ZX-eQeLN6rr9MNY')
CHANNELS = load_channels()
MAX_CONFIGS = 300
OUTPUT_FILE = 'sub.txt'

async def collect_from_channel(app, channel):
    configs = []
    try:
        async for message in app.bot.get_chat_history(chat_id=channel, limit=100):
            if message.text:
                links = re.findall(
                    r'vmess://[A-Za-z0-9+/=]+|vless://[^\s]+|trojan://[^\s]+|ss://[^\s]+', 
                    message.text
                )
                configs.extend(links)
        
        print(f"✅ {channel}: {len(configs)} configs")
        return configs
    except Exception as e:
        print(f"❌ {channel}: {e}")
        return []

async def main():
    application = Application.builder().token(BOT_TOKEN).build()
    all_configs = []
    
    print("🚀 Starting bot collector...")
    
    for channel in CHANNELS:
        try:
            configs = await collect_from_channel(application, channel)
            all_configs.extend(configs)
            
            if len(all_configs) >= 500:
                break
                
        except Exception as e:
            print(f"Failed to access {channel}: {e}")
            continue
    
    unique_configs = list(set(all_configs))[:MAX_CONFIGS]
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for config in unique_configs:
            f.write(config + '\n')
    
    print(f"✅ Done! {len(unique_configs)} configs saved")

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
