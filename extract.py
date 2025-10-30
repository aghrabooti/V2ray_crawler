import asyncio
from telethon import TelegramClient
import re
import requests
import geoip2.database
import json
from urllib.parse import urlparse
import base64

API_ID = API_ID
API_HASH = 'API_HASH'
CHANNEL = '@DailyV2Proxy'
OUTPUT_FILE = 'sub.txt'
GEOIP_DB = 'GeoLite2-Country.mmdb'
TIMEOUT = 5

client = TelegramClient('session', API_ID, API_HASH)
reader = geoip2.database.Reader(GEOIP_DB)

FLAG_EMOJI = {
    'US': 'US', 'GB': 'GB', 'DE': 'DE', 'NL': 'NL', 'FR': 'FR',
    'CA': 'CA', 'JP': 'JP', 'SG': 'SG', 'HK': 'HK', 'KR': 'KR',
    'IR': 'IR', 'RU': 'RU', 'CN': 'CN', 'IN': 'IN', 'BR': 'BR'
}

def get_flag(code):
    return FLAG_EMOJI.get(code, 'Global')

def extract_ip_port(link):
    try:
        if link.startswith('vmess://'):
            data = json.loads(base64.urlsafe_b64decode(link[8:]).decode())
            return data.get('add'), data.get('port')
        else:
            parsed = urlparse(link)
            return parsed.hostname, parsed.port or 443
    except:
        return None, None

def test_config(ip, port):
    if not ip or not port:
        return False
    try:
        requests.get(f"http://{ip}:{port}", timeout=TIMEOUT, verify=False)
        return True
    except:
        try:
            requests.get(f"https://{ip}:{port}", timeout=TIMEOUT, verify=False)
            return True
        except:
            return False

async def main():
    await client.start()
    configs = set()
    pattern = r'(vmess|vless|trojan|ss)://[^\s\n]+'

    async for message in client.iter_messages(CHANNEL, limit=1000):
        if message.text:
            for link in re.findall(pattern, message.text, re.IGNORECASE):
                configs.add(link.strip())

    valid_configs = []
    for link in configs:
        ip, port = extract_ip_port(link)
        if not ip or not port:
            continue
        try:
            country = reader.country(ip).country.iso_code or 'XX'
        except:
            country = 'XX'
        if test_config(ip, port):
            flag = get_flag(country)
            base_link = link.split('#')[0] if '#' in link else link
            new_link = f"{base_link}#Aghrab - {flag} {country}"
            valid_configs.append(new_link)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for cfg in sorted(valid_configs):
            f.write(cfg + '\n')

if __name__ == '__main__':
    asyncio.run(main())
