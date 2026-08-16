import json
import os
import socket
import subprocess
import tempfile
import time
import base64
from urllib.parse import urlparse, parse_qs, unquote

import requests


INPUT_FILE = "sub.txt"
OUTPUT_FILE = "sublink.txt"

XRAY_BINARY = r"C:\Users\User\Desktop\apps\v2rayN-windows-64\bin\xray\xray.exe"

SOCKS_HOST = "127.0.0.1"
SOCKS_PORT = 10808

START_TIMEOUT = 5
TEST_TIMEOUT = 8

TEST_URL = "https://www.youtube.com"


def decode_base64(value):
    value = value.strip()
    value += "=" * (-len(value) % 4)

    try:
        return base64.urlsafe_b64decode(value).decode()
    except Exception:
        return base64.b64decode(value).decode()


def parse_vmess(uri):
    data = json.loads(
        decode_base64(uri.replace("vmess://", "", 1))
    )

    stream = {
        "network": data.get("net", "tcp")
    }

    tls = data.get("tls")

    if tls:
        stream["security"] = "tls"

        tls_settings = {}

        if data.get("sni"):
            tls_settings["serverName"] = data["sni"]

        elif data.get("host"):
            tls_settings["serverName"] = data["host"]

        stream["tlsSettings"] = tls_settings

    network = stream["network"]

    if network == "ws":

        ws = {
            "path": data.get("path", "/")
        }

        if data.get("host"):
            ws["headers"] = {
                "Host": data["host"]
            }

        stream["wsSettings"] = ws

    elif network == "grpc":

        stream["grpcSettings"] = {
            "serviceName": data.get("path", "")
        }

    return {
        "protocol": "vmess",

        "settings": {
            "vnext": [
                {
                    "address": data["add"],
                    "port": int(data["port"]),

                    "users": [
                        {
                            "id": data["id"],
                            "alterId": int(data.get("aid", 0)),
                            "security": data.get("scy", "auto")
                        }
                    ]
                }
            ]
        },

        "streamSettings": stream
    }


def parse_vless(uri):

    parsed = urlparse(uri)

    query = parse_qs(parsed.query)

    network = query.get("type", ["tcp"])[0]
    security = query.get("security", ["none"])[0]

    stream = {
        "network": network
    }

    if security == "tls":

        stream["security"] = "tls"

        tls = {}

        if "sni" in query:
            tls["serverName"] = query["sni"][0]

        if "fp" in query:
            tls["fingerprint"] = query["fp"][0]

        stream["tlsSettings"] = tls

    elif security == "reality":

        stream["security"] = "reality"

        reality = {}

        if "sni" in query:
            reality["serverName"] = query["sni"][0]

        if "fp" in query:
            reality["fingerprint"] = query["fp"][0]

        if "pbk" in query:
            reality["publicKey"] = query["pbk"][0]

        if "sid" in query:
            reality["shortId"] = query["sid"][0]

        stream["realitySettings"] = reality

    if network == "ws":

        ws = {
            "path": unquote(
                query.get("path", ["/"])[0]
            )
        }

        if "host" in query:
            ws["headers"] = {
                "Host": query["host"][0]
            }

        stream["wsSettings"] = ws

    elif network == "grpc":

        stream["grpcSettings"] = {
            "serviceName":
                query.get("serviceName", [""])[0]
        }

    user = {
        "id": parsed.username,
        "encryption": "none"
    }

    if "flow" in query:
        user["flow"] = query["flow"][0]

    return {

        "protocol": "vless",

        "settings": {
            "vnext": [
                {
                    "address": parsed.hostname,
                    "port": parsed.port,

                    "users": [
                        user
                    ]
                }
            ]
        },

        "streamSettings": stream
    }


def parse_trojan(uri):

    parsed = urlparse(uri)

    query = parse_qs(parsed.query)

    network = query.get("type", ["tcp"])[0]

    stream = {
        "network": network,
        "security": "tls"
    }

    tls = {}

    if "sni" in query:
        tls["serverName"] = query["sni"][0]

    stream["tlsSettings"] = tls

    if network == "ws":

        stream["wsSettings"] = {
            "path": query.get("path", ["/"])[0]
        }

        if "host" in query:

            stream["wsSettings"]["headers"] = {
                "Host": query["host"][0]
            }

    elif network == "grpc":

        stream["grpcSettings"] = {
            "serviceName":
                query.get("serviceName", [""])[0]
        }

    return {

        "protocol": "trojan",

        "settings": {
            "servers": [
                {
                    "address": parsed.hostname,
                    "port": parsed.port or 443,
                    "password": parsed.username
                }
            ]
        },

        "streamSettings": stream
    }


def parse_ss(uri):

    # Basic SIP002 format

    raw = uri.replace("ss://", "", 1)

    raw = raw.split("#")[0]

    if "@" not in raw:
        raise ValueError("Unsupported SS format")

    userinfo, server = raw.rsplit("@", 1)

    try:
        decoded = decode_base64(userinfo)
    except Exception:
        decoded = userinfo

    if ":" not in decoded:
        raise ValueError("Invalid SS credentials")

    method, password = decoded.split(":", 1)

    parsed = urlparse(
        "ss://" + server
    )

    return {

        "protocol": "shadowsocks",

        "settings": {
            "servers": [
                {
                    "address": parsed.hostname,
                    "port": parsed.port,
                    "method": method,
                    "password": password
                }
            ]
        }
    }


def parse_config(uri):

    uri = uri.strip()

    if uri.startswith("vmess://"):
        return parse_vmess(uri)

    if uri.startswith("vless://"):
        return parse_vless(uri)

    if uri.startswith("trojan://"):
        return parse_trojan(uri)

    if uri.startswith("ss://"):
        return parse_ss(uri)

    raise ValueError("Unsupported protocol")


def create_config(outbound):

    return {

        "log": {
            "loglevel": "warning"
        },

        "inbounds": [

            {
                "listen": SOCKS_HOST,

                "port": SOCKS_PORT,

                "protocol": "socks",

                "settings": {
                    "auth": "noauth",
                    "udp": True
                }
            }

        ],

        "outbounds": [

            outbound,

            {
                "protocol": "freedom",
                "tag": "direct"
            }

        ]
    }


def port_open():

    try:

        sock = socket.create_connection(
            (SOCKS_HOST, SOCKS_PORT),
            timeout=0.3
        )

        sock.close()

        return True

    except OSError:

        return False


def wait_for_port(process):

    start = time.time()

    while time.time() - start < START_TIMEOUT:

        if process.poll() is not None:
            return False

        if port_open():
            return True

        time.sleep(0.1)

    return False


def test_proxy():

    proxies = {

        "http":
            f"socks5h://{SOCKS_HOST}:{SOCKS_PORT}",

        "https":
            f"socks5h://{SOCKS_HOST}:{SOCKS_PORT}"
    }

    start = time.perf_counter()

    response = requests.get(

        TEST_URL,

        proxies=proxies,

        timeout=TEST_TIMEOUT
    )

    latency = (
        time.perf_counter() - start
    ) * 1000

    return response.status_code, latency


def test_config(uri):

    temp_dir = tempfile.mkdtemp(
        prefix="xray_test_"
    )

    config_path = os.path.join(
        temp_dir,
        "config.json"
    )

    process = None

    try:

        outbound = parse_config(uri)

        config = create_config(
            outbound
        )

        with open(
            config_path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                config,
                f,
                indent=2
            )

        process = subprocess.Popen(

            [
                XRAY_BINARY,
                "run",
                "-c",
                config_path
            ],

            stdout=subprocess.DEVNULL,

            stderr=subprocess.DEVNULL
        )

        # IMPORTANT:
        # Wait until SOCKS port actually exists.

        if not wait_for_port(process):

            return False, None

        # Now actually test traffic.

        status, latency = test_proxy()

        if status in (200, 204):

            return True, latency

        return False, latency

    except Exception as e:

        return False, None

    finally:

        if process:

            process.terminate()

            try:

                process.wait(
                    timeout=2
                )

            except subprocess.TimeoutExpired:

                process.kill()

        try:

            os.remove(config_path)

            os.rmdir(temp_dir)

        except Exception:

            pass


def load_configs():

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        return [

            line.strip()

            for line in f

            if line.strip()

            and not line.startswith("#")

        ]


def main():

    configs = load_configs()

    print(
        f"Loaded {len(configs)} configs"
    )

    print("-" * 60)

    working = []

    for index, config in enumerate(
        configs,
        1
    ):

        print(
            f"[{index}/{len(configs)}] "
            f"{config[:45]}...",
            end=" "
        )

        try:

            ok, latency = test_config(
                config
            )

            if ok:

                print(
                    f"OK - {latency:.0f} ms"
                )

                working.append(
                    (
                        latency,
                        config
                    )
                )

            else:

                print(
                    "FAILED"
                )

        except Exception as e:

            print(
                f"ERROR - {e}"
            )

    # Fastest first

    working.sort(
        key=lambda x: x[0]
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        for latency, config in working:

            f.write(
                config + "\n"
            )

    print()

    print("=" * 60)

    print(
        f"Working configs: {len(working)}"
    )

    print(
        f"Saved to: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()