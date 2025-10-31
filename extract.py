import asyncio
from telethon import TelegramClient
import re
import os

# اطلاعات شخصی
API_ID = int(os.getenv('TELEGRAM_API_ID', '20221005'))
API_HASH = os.getenv('TELEGRAM_API_HASH', '35a9246b9e00de8c09c5290e062d50a7')

CHANNEL = '@DailyV2Proxy'
OUTPUT_FILE = 'sub.txt'

client = TelegramClient('session', API_ID, API_HASH)

async def main():
    await client.start()
    configs = set()

    # فقط برای شناسایی پروتکل (بدون گروه)
    pattern = r'(?i)(vmess|vless|trojan|ss|shadowsocks|socks|http|https)://[^\s\n]+'

    print("در حال خواندن پیام‌ها از کانال...")
    async for message in client.iter_messages(CHANNEL, limit=5000):
        text = ""
        if message.text:
            text += message.text + "\n"
        if message.media and hasattr(message.media, 'document') and message.message:
            text += message.message + "\n"
        if message.fwd_from and message.fwd_from.channel_post:
            try:
                fwd_msg = await client.get_messages(message.fwd_from.from_id, ids=message.fwd_from.channel_post)
                if fwd_msg and fwd_msg.text:
                    text += fwd_msg.text + "\n"
            except:
                pass

        # کل لینک رو بگیر
        for match in re.finditer(pattern, text):
            full_link = match.group(0)  # کل متن لینک
            configs.add(full_link.strip())

    print(f"تعداد لینک‌های کامل پیدا شده: {len(configs)}")

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for link in sorted(configs):
            # فقط قسمت قبل از # رو نگه دار
            base_link = link.split('#', 1)[0] if '#' in link else link
            # اسم جدید: Aghrab
            new_link = f"{base_link}#Aghrab"
            f.write(new_link + '\n')

    print(f"{len(configs)} کانفیگ کامل با اسم 'Aghrab' ذخیره شد → {OUTPUT_FILE}")

if __name__ == '__main__':
    asyncio.run(main())
