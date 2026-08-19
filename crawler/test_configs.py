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

# Main connectivity test
TEST_URL = "https://www.google.com"

# GeoIP service
GEOIP_URL = "http://ip-api.com/json/?fields=status,country,countryCode,query"
CONFIG_NAME = "on bir mehmet buyuk"


# ============================================================
# DATE / NAME
# ============================================================

def get_config_name(country_code=None):

    date = datetime.now().strftime("%Y-%m-%d")

    if country_code:
        flag = country_code_to_flag(country_code)

        if flag:
            return f"{flag} {CONFIG_NAME} {date}"

    return f"{CONFIG_NAME} {date}"


# ============================================================
# COUNTRY CODE -> FLAG
# ============================================================

def country_code_to_flag(code):

    if not code:
        return ""

    code = code.upper().strip()

    if len(code) != 2:
        return ""

    try:

        return "".join(
            chr(
                127397 + ord(char)
            )
            for char in code
        )

    except Exception:

        return ""


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
# PROXY SESSION
# ============================================================

def get_proxy_session():

    session = requests.Session()

    proxy = (
        f"socks5h://"
        f"{SOCKS_HOST}:"
        f"{SOCKS_PORT}"
    )

    session.proxies.update({

        "http": proxy,
        "https": proxy

    })

    return session


# ============================================================
# TEST GOOGLE
# ============================================================

def test_proxy(session):

    start = time.perf_counter()

    response = session.get(

        TEST_URL,

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
# GET REAL EXIT COUNTRY
# ============================================================

def get_exit_country(session):
    
    try:

        response = session.get(
            GEOIP_URL,
            timeout=TEST_TIMEOUT,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        response.raise_for_status()

        data = response.json()

        if data.get("status") != "success":
            return None, None, None

        country_code = data.get(
            "countryCode"
        )

        country = data.get(
            "country"
        )

        ip = data.get(
            "query"
        )

        return (
            country_code,
            country,
            ip
        )

    except Exception as e:

        print(
            "GEOIP ERROR:",
            e
        )

        return (
            None,
            None,
            None
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

        # ----------------------------------------------------
        # Write Xray config
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Validate Xray config
        # ----------------------------------------------------

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
                None,
                None,
                "XRAY_CONFIG_INVALID: "
                + error[-500:]
            )

        # ----------------------------------------------------
        # Start Xray
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Wait for SOCKS
        # ----------------------------------------------------

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
                None,
                None,
                "XRAY_START_FAILED: "
                + stderr[-500:]
            )

        # ----------------------------------------------------
        # Create proxy session
        # ----------------------------------------------------

        session = get_proxy_session()

        # ----------------------------------------------------
        # Test Google
        # ----------------------------------------------------

        try:

            status, latency = test_proxy(
                session
            )

        except Exception as e:

            return (
                False,
                None,
                None,
                None,
                "CONNECTION_FAILED: "
                + str(e)
            )

        if status not in (200, 204):

            return (
                False,
                latency,
                None,
                None,
                f"HTTP_STATUS_{status}"
            )

        # ----------------------------------------------------
        # Get REAL exit IP / country
        # ----------------------------------------------------

        country_code, country, exit_ip = (
            get_exit_country(
                session
            )
        )

        return (
            True,
            latency,
            country_code,
            country,
            exit_ip
        )

    except Exception as e:

        return (
            False,
            None,
            None,
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
            os.remove(
                config_path
            )

        except Exception:
            pass

        try:
            os.rmdir(
                temp_dir
            )

        except Exception:
            pass


# ============================================================
# LOAD FILE
# ============================================================

def load_configs(filename):

    if not os.path.exists(
        filename
    ):

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
# CLEAN CONFIG
# ============================================================

def clean_config(config):

    return config.split(
        "#",
        1
    )[0].strip()


# ============================================================
# RENAME CONFIG
# ============================================================

def rename_config(
    config,
    country_code
):

    config = clean_config(
        config
    )

    name = get_config_name(
        country_code
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
    # 1. Load configs from sub.txt
    # --------------------------------------------------------

    scraped_configs = load_configs(
        SUB_FILE
    )

    print()
    print("=" * 60)
    print("SUB.TXT")
    print("=" * 60)

    print(
        f"Configs in {SUB_FILE}: "
        f"{len(scraped_configs)}"
    )

    # --------------------------------------------------------
    # 2. Load existing working configs
    # --------------------------------------------------------

    existing_configs = load_configs(
        SUBLINK_FILE
    )

    print()
    print("=" * 60)
    print("CURRENT SUBLINK")
    print("=" * 60)

    print(
        f"Existing configs: "
        f"{len(existing_configs)}"
    )

    # --------------------------------------------------------
    # 3. Normalize everything
    #
    # Remove #name before comparing.
    # --------------------------------------------------------

    existing_clean = {

        clean_config(config)

        for config in existing_configs

        if config.strip()

    }

    scraped_clean = {

        clean_config(config)

        for config in scraped_configs

        if config.strip()

    }

    # --------------------------------------------------------
    # 4. Combine existing + new
    #
    # Every unique config will be tested.
    # --------------------------------------------------------

    all_configs = list(
        dict.fromkeys(
            list(existing_clean)
            + list(scraped_clean)
        )
    )

    print()
    print("=" * 60)
    print("CONFIGS TO TEST")
    print("=" * 60)

    print(
        f"Existing: "
        f"{len(existing_clean)}"
    )

    print(
        f"From sub.txt: "
        f"{len(scraped_clean)}"
    )

    print(
        f"Unique configs to test: "
        f"{len(all_configs)}"
    )

    # --------------------------------------------------------
    # 5. Test ALL configs
    # --------------------------------------------------------

    working_configs = []

    healthy_count = 0
    failed_count = 0

    total = len(all_configs)

    print()
    print("=" * 60)
    print("TESTING")
    print("=" * 60)


    for index, config in enumerate(all_configs, 1):

        print(
            f"[{index}/{total}] "
            f"{config[:55]}...",
            end=" ",
            flush=True
        )

        try:

            result = test_config(config)

            ok = result[0]

            if ok:
            
                latency = result[1]

                country_code = result[2]
                country = result[3]
                exit_ip = result[4]

                healthy_count += 1

                flag = country_code_to_flag(
                    country_code
                )

                print(
                    f"OK - "
                    f"{latency:.0f} ms - "
                    f"{flag or '?'} "
                    f"{country or 'Unknown'} - "
                    f"{exit_ip or 'Unknown IP'}"
                )

                working_configs.append(
                    (
                        latency,
                        config,
                        country_code
                    )
                )

            else:

                failed_count += 1

                error = result[-1]

                print("FAILED")

                if error:
                    print(
                        f"    {error}"
                    )


        except Exception as e:

            failed_count += 1

            print(
                f"ERROR - {e}"
            )


        print(
            f"working: {healthy_count} | "
            f"not working: {failed_count} | "
            f"remaining: {total-index}"
        )
    # --------------------------------------------------------
    # 6. Sort working configs by latency
    # --------------------------------------------------------

    working_configs.sort(
        key=lambda x: x[0]
    )

    # --------------------------------------------------------
    # 7. Rename working configs
    # --------------------------------------------------------

    final_configs = [

        rename_config(
            config,
            country_code
        )

        for latency, config, country_code
        in working_configs

    ]

    # --------------------------------------------------------
    # 8. Save ONLY working configs
    #
    # Failed configs are automatically removed.
    # --------------------------------------------------------

    save_configs(
        SUBLINK_FILE,
        final_configs
    )

    # --------------------------------------------------------
    # 9. Statistics
    # --------------------------------------------------------

    new_configs = (
        scraped_clean - existing_clean
    )

    removed_configs = (
        existing_clean - {
            clean_config(config)
            for config in final_configs
        }
    )

    print()
    print("=" * 60)
    print("DONE")
    print("=" * 60)

    print(
        f"Previously in sublink: "
        f"{len(existing_clean)}"
    )

    print(
        f"Configs in sub.txt: "
        f"{len(scraped_clean)}"
    )

    print(
        f"New configs found: "
        f"{len(new_configs)}"
    )

    print(
        f"Total tested: "
        f"{total}"
    )

    print(
        f"Healthy: "
        f"{healthy_count}"
    )

    print(
        f"Failed: "
        f"{failed_count}"
    )

    print(
        f"Removed from sublink: "
        f"{len(removed_configs)}"
    )

    print(
        f"Final working configs: "
        f"{len(final_configs)}"
    )

    print(
        f"Output: "
        f"{SUBLINK_FILE}"
    )
# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()