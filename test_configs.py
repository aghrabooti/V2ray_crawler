import base64
import json
import os
import socket
import subprocess
import tempfile
import time

from datetime import datetime
from urllib.parse import urlparse, parse_qs, unquote

import requests


# ============================================================
# SETTINGS
# ============================================================

SUB_FILE = "sub.txt"
SUBLINK_FILE = "sublink.txt"

XRAY_BINARY = r"C:\Users\User\Desktop\apps\v2rayN-windows-64\bin\xray\xray.exe"

SOCKS_HOST = "127.0.0.1"
SOCKS_PORT = 10808

START_TIMEOUT = 5
TEST_TIMEOUT = 8

TEST_URL = "https://www.google.com"

CONFIG_NAME = "on bir mehmet buyuk"


# ============================================================
# DATE / NAME
# ============================================================

def get_config_name():

    date = datetime.now().strftime("%Y-%m-%d")

    return f"{CONFIG_NAME} {date}"


# ============================================================
# BASE64
# ============================================================

def decode_base64(value):

    value = value.strip()

    value += "=" * (-len(value) % 4)

    try:
        return base64.urlsafe_b64decode(
            value
        ).decode("utf-8")

    except Exception:

        return base64.b64decode(
            value
        ).decode("utf-8")


# ============================================================
# VMESS
# ============================================================

def parse_vmess(uri):

    encoded = uri.replace(
        "vmess://",
        "",
        1
    )

    data = json.loads(
        decode_base64(encoded)
    )

    network = data.get(
        "net",
        "tcp"
    )

    stream = {
        "network": network
    }

    # TLS

    if data.get("tls"):

        stream["security"] = "tls"

        tls_settings = {}

        if data.get("sni"):

            tls_settings["serverName"] = data["sni"]

        elif data.get("host"):

            tls_settings["serverName"] = data["host"]

        stream["tlsSettings"] = tls_settings

    # WebSocket

    if network == "ws":

        ws_settings = {
            "path": unquote(
                data.get(
                    "path",
                    "/"
                )
            )
        }

        if data.get("host"):

            ws_settings["headers"] = {
                "Host": data["host"]
            }

        stream["wsSettings"] = ws_settings

    # gRPC

    elif network == "grpc":

        stream["grpcSettings"] = {
            "serviceName":
                data.get(
                    "path",
                    ""
                )
        }

    # HTTP/2

    elif network == "h2":

        http_settings = {
            "path":
                data.get(
                    "path",
                    "/"
                )
        }

        if data.get("host"):

            http_settings["host"] = [
                data["host"]
            ]

        stream["httpSettings"] = http_settings

    return {

        "protocol": "vmess",

        "settings": {

            "vnext": [

                {

                    "address":
                        data["add"],

                    "port":
                        int(data["port"]),

                    "users": [

                        {

                            "id":
                                data["id"],

                            "alterId":
                                int(
                                    data.get(
                                        "aid",
                                        0
                                    )
                                ),

                            "security":
                                data.get(
                                    "scy",
                                    "auto"
                                )

                        }

                    ]

                }

            ]

        },

        "streamSettings":
            stream

    }


# ============================================================
# VLESS
# ============================================================

def parse_vless(uri):

    parsed = urlparse(uri)

    query = parse_qs(
        parsed.query
    )

    network = query.get(
        "type",
        ["tcp"]
    )[0]

    security = query.get(
        "security",
        ["none"]
    )[0]

    stream = {
        "network": network
    }

    # TLS

    if security == "tls":

        stream["security"] = "tls"

        tls = {}

        if "sni" in query:
            tls["serverName"] = query["sni"][0]

        if "fp" in query:
            tls["fingerprint"] = query["fp"][0]

        if "alpn" in query:
            tls["alpn"] = query["alpn"][0].split(",")

        stream["tlsSettings"] = tls

    # Reality

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

    # WebSocket

    if network == "ws":

        ws = {
            "path": unquote(
                query.get(
                    "path",
                    ["/"]
                )[0]
            )
        }

        if "host" in query:

            ws["headers"] = {
                "Host":
                    query["host"][0]
            }

        stream["wsSettings"] = ws

    # gRPC

    elif network == "grpc":

        grpc = {
            "serviceName":
                query.get(
                    "serviceName",
                    [""]
                )[0]
        }

        if "authority" in query:

            grpc["authority"] = query[
                "authority"
            ][0]

        if "mode" in query:

            grpc["multiMode"] = (
                query["mode"][0] == "multi"
            )

        stream["grpcSettings"] = grpc

    # HTTP/2

    elif network == "h2":

        http_settings = {
            "path":
                query.get(
                    "path",
                    ["/"]
                )[0]
        }

        if "host" in query:

            http_settings["host"] = [
                query["host"][0]
            ]

        stream["httpSettings"] = http_settings

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

                    "address":
                        parsed.hostname,

                    "port":
                        parsed.port,

                    "users": [
                        user
                    ]

                }

            ]

        },

        "streamSettings":
            stream

    }


# ============================================================
# TROJAN
# ============================================================

def parse_trojan(uri):

    parsed = urlparse(uri)

    query = parse_qs(
        parsed.query
    )

    network = query.get(
        "type",
        ["tcp"]
    )[0]

    stream = {

        "network":
            network,

        "security":
            "tls"

    }

    tls = {}

    if "sni" in query:

        tls["serverName"] = query[
            "sni"
        ][0]

    if "fp" in query:

        tls["fingerprint"] = query[
            "fp"
        ][0]

    if "alpn" in query:

        tls["alpn"] = query[
            "alpn"
        ][0].split(",")

    stream["tlsSettings"] = tls

    # WebSocket

    if network == "ws":

        ws = {

            "path":
                query.get(
                    "path",
                    ["/"]
                )[0]

        }

        if "host" in query:

            ws["headers"] = {

                "Host":
                    query["host"][0]

            }

        stream["wsSettings"] = ws

    # gRPC

    elif network == "grpc":

        stream["grpcSettings"] = {

            "serviceName":
                query.get(
                    "serviceName",
                    [""]
                )[0]

        }

    return {

        "protocol":
            "trojan",

        "settings": {

            "servers": [

                {

                    "address":
                        parsed.hostname,

                    "port":
                        parsed.port or 443,

                    "password":
                        unquote(
                            parsed.username
                        )

                }

            ]

        },

        "streamSettings":
            stream

    }


# ============================================================
# SHADOWSOCKS
# ============================================================

def parse_ss(uri):

    raw = uri.replace(
        "ss://",
        "",
        1
    )

    raw = raw.split(
        "#",
        1
    )[0]

    if "@" not in raw:

        raise ValueError(
            "Unsupported Shadowsocks format"
        )

    userinfo, server = raw.rsplit(
        "@",
        1
    )

    try:

        decoded = decode_base64(
            userinfo
        )

    except Exception:

        decoded = userinfo

    if ":" not in decoded:

        raise ValueError(
            "Invalid Shadowsocks credentials"
        )

    method, password = decoded.split(
        ":",
        1
    )

    parsed = urlparse(
        "ss://" + server
    )

    return {

        "protocol":
            "shadowsocks",

        "settings": {

            "servers": [

                {

                    "address":
                        parsed.hostname,

                    "port":
                        parsed.port,

                    "method":
                        method,

                    "password":
                        password

                }

            ]

        }

    }


# ============================================================
# PARSE CONFIG
# ============================================================

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

    raise ValueError(
        "Unsupported protocol"
    )


# ============================================================
# XRAY CONFIG
# ============================================================

def create_xray_config(outbound):

    return {

        "log": {
            "loglevel":
                "warning"
        },

        "inbounds": [

            {

                "listen":
                    SOCKS_HOST,

                "port":
                    SOCKS_PORT,

                "protocol":
                    "socks",

                "settings": {

                    "auth":
                        "noauth",

                    "udp":
                        True

                }

            }

        ],

        "outbounds": [

            outbound,

            {

                "protocol":
                    "freedom",

                "tag":
                    "direct"

            }

        ]

    }


# ============================================================
# PORT CHECK
# ============================================================

def port_open():

    try:

        sock = socket.create_connection(

            (
                SOCKS_HOST,
                SOCKS_PORT
            ),

            timeout=0.3

        )

        sock.close()

        return True

    except OSError:

        return False


def wait_for_port(process):

    start = time.time()

    while (
        time.time() - start
        < START_TIMEOUT
    ):

        if process.poll() is not None:
            return False

        if port_open():
            return True

        time.sleep(0.1)

    return False


# ============================================================
# TEST PROXY
# ============================================================

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

        timeout=TEST_TIMEOUT,

        allow_redirects=True

    )

    latency = (

        time.perf_counter()
        - start

    ) * 1000

    return (
        response.status_code,
        latency
    )


# ============================================================
# TEST SINGLE CONFIG
# ============================================================

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

        outbound = parse_config(
            uri
        )

        config = create_xray_config(
            outbound
        )

        # Write config FIRST

        with open(
            config_path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                config,
                f,
                ensure_ascii=False,
                indent=2
            )

        # Validate config

        validation = subprocess.run(

            [
                XRAY_BINARY,
                "run",
                "-test",
                "-c",
                config_path
            ],

            stdout=subprocess.PIPE,

            stderr=subprocess.PIPE,

            text=True

        )

        if validation.returncode != 0:

            error = (
                validation.stderr
                or validation.stdout
            )

            return (
                False,
                None,
                "XRAY_CONFIG_INVALID: "
                + error[-500:]
            )

        # Start Xray

        process = subprocess.Popen(

            [
                XRAY_BINARY,
                "run",
                "-c",
                config_path
            ],

            stdout=subprocess.DEVNULL,

            stderr=subprocess.PIPE,

            text=True

        )

        # Wait for SOCKS port

        if not wait_for_port(
            process
        ):

            try:
                stderr = process.stderr.read()
            except Exception:
                stderr = ""

            return (
                False,
                None,
                "XRAY_START_FAILED: "
                + stderr[-500:]
            )

        # Test actual traffic

        try:

            status, latency = test_proxy()

        except Exception as e:

            return (
                False,
                None,
                "CONNECTION_FAILED: "
                + str(e)
            )

        if status in (200, 204):

            return (
                True,
                latency,
                None
            )

        return (
            False,
            latency,
            f"HTTP_STATUS_{status}"
        )

    except Exception as e:

        return (
            False,
            None,
            f"CONFIG_ERROR: {e}"
        )

    finally:

        if process:

            try:

                process.terminate()

                process.wait(
                    timeout=2
                )

            except Exception:

                try:
                    process.kill()
                except Exception:
                    pass

        try:
            os.remove(config_path)
        except Exception:
            pass

        try:
            os.rmdir(temp_dir)
        except Exception:
            pass


# ============================================================
# LOAD FILE
# ============================================================

def load_configs(filename):

    if not os.path.exists(filename):
        return []

    with open(
        filename,
        "r",
        encoding="utf-8"
    ) as f:

        return [

            line.strip()

            for line in f

            if line.strip()
            and not line.startswith("#")

        ]


# ============================================================
# SAVE FILE
# ============================================================

def save_configs(
    filename,
    configs
):

    configs = list(
        dict.fromkeys(
            configs
        )
    )

    with open(
        filename,
        "w",
        encoding="utf-8"
    ) as f:

        for config in configs:

            f.write(
                config + "\n"
            )


# ============================================================
# REMOVE CONFIG NAME
# ============================================================

def clean_config(config):

    return config.split(
        "#",
        1
    )[0]


# ============================================================
# RENAME CONFIG
# ============================================================

def rename_config(
    config,
    name
):

    config = clean_config(
        config
    )

    safe_name = requests.utils.quote(
        name,
        safe=""
    )

    return (
        config
        + "#"
        + safe_name
    )


# ============================================================
# MAIN
# ============================================================

def main():
    
    # --------------------------------------------------------
    # 1. Load scraped configs from sub.txt
    # --------------------------------------------------------

    scraped_configs = load_configs(SUB_FILE)

    print()
    print("=" * 60)
    print("SCRAPED CONFIGS")
    print("=" * 60)

    print(f"Configs in {SUB_FILE}: {len(scraped_configs)}")

    # --------------------------------------------------------
    # 2. Load existing working configs
    # --------------------------------------------------------

    existing_configs = load_configs(SUBLINK_FILE)

    print()
    print("=" * 60)
    print("CURRENT SUBLINK")
    print("=" * 60)

    print(f"Existing working configs: {len(existing_configs)}")

    # --------------------------------------------------------
    # 3. Normalize configs
    #
    # Remove #name so comparison is based only on the
    # actual connection string.
    # --------------------------------------------------------

    existing_clean = {
        config.split("#", 1)[0].strip()
        for config in existing_configs
        if config.strip()
    }

    scraped_clean = {
        config.split("#", 1)[0].strip()
        for config in scraped_configs
        if config.strip()
    }

    # --------------------------------------------------------
    # 4. Find ONLY new configs
    # --------------------------------------------------------

    new_configs = [
        config
        for config in scraped_clean
        if config not in existing_clean
    ]

    print()
    print("=" * 60)
    print("NEW CONFIGS")
    print("=" * 60)

    print(f"New configs to test: {len(new_configs)}")
    print(f"Already known: {len(existing_clean)}")

    # --------------------------------------------------------
    # 5. Test ONLY new configs
    # --------------------------------------------------------

    working_new = []

    for index, config in enumerate(new_configs, 1):

        print(
            f"[{index}/{len(new_configs)}] "
            f"{config[:55]}...",
            end=" ",
            flush=True
        )

        try:

            ok, latency, error = test_config(config)

            if ok:

                print(
                    f"OK - {latency:.0f} ms"
                )

                working_new.append(
                    (
                        latency,
                        config
                    )
                )

            else:

                print("FAILED")

                if error:
                    print(
                        f"    {error}"
                    )

        except Exception as e:

            print(
                f"ERROR - {e}"
            )

    # --------------------------------------------------------
    # 6. Sort new working configs
    # --------------------------------------------------------

    working_new.sort(
        key=lambda x: x[0]
    )

    # --------------------------------------------------------
    # 7. Rename new configs
    # --------------------------------------------------------

    current_name = get_config_name()

    new_final = [
        rename_config(
            config,
            current_name
        )
        for latency, config in working_new
    ]

    # --------------------------------------------------------
    # 8. Keep existing working configs
    # --------------------------------------------------------

    final_configs = (
        existing_configs +
        new_final
    )

    # --------------------------------------------------------
    # 9. Remove duplicates
    # --------------------------------------------------------

    unique_final = []

    seen = set()

    for config in final_configs:

        clean = config.split(
            "#",
            1
        )[0].strip()

        if clean not in seen:

            seen.add(clean)

            unique_final.append(
                config
            )

    # --------------------------------------------------------
    # 10. Save
    # --------------------------------------------------------

    save_configs(
        SUBLINK_FILE,
        unique_final
    )

    # --------------------------------------------------------
    # 11. Statistics
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("DONE")
    print("=" * 60)

    print(
        f"Previously working: "
        f"{len(existing_clean)}"
    )

    print(
        f"Configs from sub.txt: "
        f"{len(scraped_clean)}"
    )

    print(
        f"New configs tested: "
        f"{len(new_configs)}"
    )

    print(
        f"New working configs: "
        f"{len(new_final)}"
    )

    print(
        f"Final working configs: "
        f"{len(unique_final)}"
    )

    print(
        f"Output: "
        f"{SUBLINK_FILE}"
    )

    print(
        f"Name: "
        f"{current_name}"
    )


if __name__ == "__main__":
    main()