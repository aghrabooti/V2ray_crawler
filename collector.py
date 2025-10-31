import os
import re
import asyncio
from telegram import Bot
from telegram.ext import Application

BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHANNELS = load.channels()
MAX_CONFIGS = 300
OUTPUT_FILE = 'sub.txt'

async def collect_from_channel(bot, channel):
    configs = []
    try:
        async for message in bot.get_chat_history(chat_id=channel, limit=100):
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
    """تابع اصلی"""
    bot = Bot(token=BOT_TOKEN)
    all_configs = []
    
    print("🚀 Starting bot collector...")
    
    for channel in CHANNELS:
        try:
            configs = await collect_from_channel(bot, channel)
            all_configs.extend(configs)
            
            if len(all_configs) >= 500:
                break
                
        except Exception as e:
            print(f"Failed to access {channel}: {e}")
            continue
    
    # پردازش نهایی
    unique_configs = list(set(all_configs))[:MAX_CONFIGS]
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for config in unique_configs:
            f.write(config + '\n')
    
    print(f"✅ Done! {len(unique_configs)} configs saved")

if __name__ == '__main__':
    asyncio.run(main())
