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

SUB_FILE = r"E:\CODE\repos\V2ray_crawler\crawler\sub.txt"
SUBLINK_FILE = r"E:\CODE\repos\V2ray_crawler\crawler\sublink.txt"


SING_BOX_BINARY = r"C:\Users\User\OneDrive\Desktop\sing-box-1.14.3-windows-amd64\sing-box.exe"

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
# TLS / REALITY (shared helper for VLESS, VMess, Trojan)
# ============================================================

def build_tls(query):
    """
    Build sing-box tls object from URI query parameters.
    Returns None if no TLS, otherwise a dict suitable for the "tls" field.
    Handles both plain TLS and REALITY.
    """
    security = query.get("security", ["none"])[0]

    if security not in ("tls", "reality"):
        return None

    tls = {"enabled": True}

    if "sni" in query:
        tls["server_name"] = query["sni"][0]
    elif "host" in query:
        tls["server_name"] = query["host"][0]

    if "alpn" in query:
        alpn_raw = query["alpn"][0]
        tls["alpn"] = [a.strip() for a in alpn_raw.split(",") if a.strip()]

    if "fp" in query:
        fp = query["fp"][0]
        if fp and fp.lower() != "none" and fp != "":
            tls["utls"] = {
                "enabled": True,
                "fingerprint": fp
            }

    if security == "reality":
        reality = {"enabled": True}

        if "pbk" in query:
            reality["public_key"] = query["pbk"][0]

        if "sid" in query:
            reality["short_id"] = query["sid"][0]

        if "spx" in query:
            reality["spider_x"] = query["spx"][0]

        tls["reality"] = reality

    # Disable certificate verification when "allowInsecure" is set
    if "allowInsecure" in query and query["allowInsecure"][0] in ("1", "true", "True"):
        tls["insecure"] = True

    return tls


# ============================================================
# TRANSPORT (shared helper)
# ============================================================

def build_transport(query):
    """
    Build sing-box transport object from URI query parameters.
    Returns None for plain TCP, otherwise a dict for the "transport" field.
    """
    network = query.get("type", ["tcp"])[0]

    if network == "tcp":
        return None

    if network == "ws":
        transport = {
            "type": "ws",
            "path": unquote(query.get("path", ["/"])[0])
        }

        headers = {}
        if "host" in query:
            headers["Host"] = query["host"][0]
        # Early data support
        if "ed" in query:
            try:
                ed = int(query["ed"][0])
                if ed > 0:
                    transport["max_early_data"] = ed
                    transport["early_data_header_name"] = "Sec-WebSocket-Protocol"
            except ValueError:
                pass
        if headers:
            transport["headers"] = headers
        return transport

    if network == "grpc":
        transport = {
            "type": "grpc",
            "service_name": query.get("serviceName", [""])[0]
        }
        if "authority" in query:
            transport["authority"] = query["authority"][0]
        if "mode" in query and query["mode"][0] == "multi":
            transport["multi_mode"] = True
        return transport

    if network in ("h2", "http"):
        transport = {
            "type": "http",
            "path": unquote(query.get("path", ["/"])[0]),
            "method": "CONNECT"
        }
        if "host" in query:
            transport["host"] = [query["host"][0]]
        return transport

    if network == "httpupgrade":
        transport = {
            "type": "httpupgrade",
            "path": unquote(query.get("path", ["/"])[0])
        }
        if "host" in query:
            transport["host"] = query["host"][0]
        return transport

    if network == "splithttp":
        transport = {
            "type": "splithttp",
            "path": unquote(query.get("path", ["/"])[0])
        }
        if "host" in query:
            transport["host"] = query["host"][0]
        return transport

    # Unknown transport – return None and let the caller handle it
    return None


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

    network = data.get("net", "tcp")

    outbound = {
        "type": "vmess",
        "server": data["add"],
        "server_port": int(data["port"]),
        "uuid": data["id"],
        "alter_id": int(data.get("aid", 0)),
        "security": data.get("scy", "auto")
    }

    # TLS
    if data.get("tls") and data["tls"] not in ("none", ""):
        tls = {"enabled": True}

        if data.get("sni"):
            tls["server_name"] = data["sni"]
        elif data.get("host"):
            tls["server_name"] = data["host"]

        if data.get("alpn"):
            tls["alpn"] = [a.strip() for a in data["alpn"].split(",") if a.strip()]

        if data.get("fp"):
            fp = data["fp"]
            if fp and fp.lower() != "none":
                tls["utls"] = {
                    "enabled": True,
                    "fingerprint": fp
                }

        if data.get("allowInsecure") in (1, "1", "true", "True", True):
            tls["insecure"] = True

        outbound["tls"] = tls

    # Transport
    if network == "ws":
        transport = {
            "type": "ws",
            "path": unquote(data.get("path", "/"))
        }
        headers = {}
        if data.get("host"):
            headers["Host"] = data["host"]
        if headers:
            transport["headers"] = headers
        outbound["transport"] = transport

    elif network == "grpc":
        outbound["transport"] = {
            "type": "grpc",
            "service_name": data.get("path", "")
        }

    elif network == "h2":
        transport = {
            "type": "http",
            "path": data.get("path", "/"),
            "method": "CONNECT"
        }
        if data.get("host"):
            transport["host"] = [data["host"]]
        outbound["transport"] = transport

    return outbound


# ============================================================
# VLESS
# ============================================================

def parse_vless(uri):

    parsed = urlparse(uri)
    query = parse_qs(parsed.query)

    outbound = {
        "type": "vless",
        "server": parsed.hostname,
        "server_port": parsed.port if parsed.port else 443,
        "uuid": parsed.username
    }

    # encryption
    encryption = query.get("encryption", ["none"])[0]
    if encryption and encryption != "none":
        outbound["encryption"] = encryption

    # flow
    flow = query.get("flow", [""])[0]
    if flow:
        outbound["flow"] = flow

    # packet encoding (Vision)
    if flow and "vision" in flow.lower():
        outbound["packet_encoding"] = "xudp"

    # TLS / Reality
    tls = build_tls(query)
    if tls:
        outbound["tls"] = tls

    # Transport
    transport = build_transport(query)
    if transport:
        outbound["transport"] = transport

    return outbound


# ============================================================
# TROJAN
# ============================================================

def parse_trojan(uri):

    parsed = urlparse(uri)
    query = parse_qs(parsed.query)

    outbound = {
        "type": "trojan",
        "server": parsed.hostname,
        "server_port": parsed.port if parsed.port else 443,
        "password": unquote(parsed.username) if parsed.username else ""
    }

    # Trojan almost always uses TLS; default to enabled when security=tls
    tls = build_tls(query)
    if tls is None:
        # If no security field but the URI has TLS-like params, still default to TLS
        if "sni" in query or "fp" in query or "alpn" in query:
            tls = {"enabled": True}
            if "sni" in query:
                tls["server_name"] = query["sni"][0]
            if "fp" in query and query["fp"][0].lower() != "none":
                tls["utls"] = {"enabled": True, "fingerprint": query["fp"][0]}
            if "alpn" in query:
                tls["alpn"] = [a.strip() for a in query["alpn"][0].split(",") if a.strip()]
        else:
            tls = {"enabled": True}
    outbound["tls"] = tls

    # Transport
    transport = build_transport(query)
    if transport:
        outbound["transport"] = transport

    return outbound


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

    outbound = {
        "type": "shadowsocks",
        "server": parsed.hostname,
        "server_port": parsed.port if parsed.port else 443,
        "method": method,
        "password": password
    }

    # Shadowsocks plugin (simple-obfs / v2ray-plugin) - basic support
    plugin = parse_qs(parsed.query).get("plugin", [None])[0]
    if plugin:
        if "obfs-local" in plugin or "simple-obfs" in plugin:
            # simple-obfs is deprecated in sing-box; skip for now
            pass
        elif "v2ray-plugin" in plugin:
            # v2ray-plugin uses WebSocket transport
            plugin_opts = {}
            for part in plugin.split(";")[1:]:
                if "=" in part:
                    k, v = part.split("=", 1)
                    plugin_opts[k.strip()] = v.strip()
            transport = {
                "type": "ws",
                "path": plugin_opts.get("path", "/")
            }
            if plugin_opts.get("host"):
                transport["headers"] = {"Host": plugin_opts["host"]}
            if plugin_opts.get("tls") == "true":
                outbound["tls"] = {
                    "enabled": True,
                    "server_name": plugin_opts.get("host", "")
                }
            outbound["transport"] = transport

    return outbound


# ============================================================
# HYSTERIA2  (hysteria2:// - supported by sing-box)
# ============================================================

def parse_hysteria2(uri):

    parsed = urlparse(uri)
    query = parse_qs(parsed.query)

    outbound = {
        "type": "hysteria2",
        "server": parsed.hostname,
        "server_port": parsed.port if parsed.port else 443,
        "password": unquote(parsed.username) if parsed.username else ""
    }

    # TLS is required for Hysteria2
    tls = {"enabled": True}
    sni = query.get("sni", [None])[0]
    if sni:
        tls["server_name"] = sni
    if "fp" in query and query["fp"][0].lower() != "none":
        tls["utls"] = {"enabled": True, "fingerprint": query["fp"][0]}
    if "insecure" in query and query["insecure"][0] in ("1", "true", "True"):
        tls["insecure"] = True
    if "alpn" in query:
        tls["alpn"] = [a.strip() for a in query["alpn"][0].split(",") if a.strip()]
    outbound["tls"] = tls

    # obfs
    obfs = query.get("obfs", [None])[0]
    obfs_password = query.get("obfs-password", [None])[0]
    if obfs:
        outbound["obfs"] = {
            "type": obfs,
            "password": obfs_password or ""
        }

    # up / down Mbps (optional)
    up_mbps = query.get("upmbps", [None])[0]
    down_mbps = query.get("downmbps", [None])[0]
    if up_mbps:
        try:
            outbound["up_mbps"] = int(up_mbps)
        except ValueError:
            pass
    if down_mbps:
        try:
            outbound["down_mbps"] = int(down_mbps)
        except ValueError:
            pass

    return outbound


# ============================================================
# TUIC (tuic:// - supported by sing-box)
# ============================================================

def parse_tuic(uri):

    parsed = urlparse(uri)
    query = parse_qs(parsed.query)

    # TUIC format: tuic://uuid:password@host:port?params...
    userinfo = parsed.username or ""
    password = parsed.password or ""

    outbound = {
        "type": "tuic",
        "server": parsed.hostname,
        "server_port": parsed.port if parsed.port else 443,
        "uuid": unquote(userinfo)
    }
    if password:
        outbound["password"] = unquote(password)

    # TLS required
    tls = {"enabled": True}
    sni = query.get("sni", [None])[0]
    if sni:
        tls["server_name"] = sni
    if "fp" in query and query["fp"][0].lower() != "none":
        tls["utls"] = {"enabled": True, "fingerprint": query["fp"][0]}
    if "alpn" in query:
        tls["alpn"] = [a.strip() for a in query["alpn"][0].split(",") if a.strip()]
    if "insecure" in query and query["insecure"][0] in ("1", "true", "True"):
        tls["insecure"] = True
    outbound["tls"] = tls

    # congestion control
    congestion = query.get("congestion_control", [None])[0]
    if congestion:
        outbound["congestion_control"] = congestion

    # UDP relay
    if "udp_relay_mode" in query:
        outbound["udp_relay_mode"] = query["udp_relay_mode"][0]

    return outbound


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

    if uri.startswith("hysteria2://") or uri.startswith("hy2://"):
        return parse_hysteria2(uri)

    if uri.startswith("tuic://"):
        return parse_tuic(uri)

    raise ValueError(
        f"Unsupported protocol: {uri[:20]}"
    )


# ============================================================
# SING-BOX CONFIG
# ============================================================

def create_singbox_config(outbound):

    return {

        "log": {
            "level": "warn"
        },

        "inbounds": [

            {
                "type": "socks",
                "tag": "socks-in",
                "listen": SOCKS_HOST,
                "listen_port": SOCKS_PORT,
                "users": []
            }

        ],

        "outbounds": [

            outbound,

            {
                "type": "direct",
                "tag": "direct"
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
        prefix="singbox_test_"
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

        config = create_singbox_config(
            outbound
        )

        # ----------------------------------------------------
        # Write sing-box config
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
        # Validate sing-box config
        # ----------------------------------------------------

        validation = subprocess.run(

            [
                SING_BOX_BINARY,
                "check",
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
                "SINGBOX_CONFIG_INVALID: "
                + error[-500:]
            )

        # ----------------------------------------------------
        # Start sing-box
        # ----------------------------------------------------

        process = subprocess.Popen(

            [
                SING_BOX_BINARY,
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
                "SINGBOX_START_FAILED: "
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
    # 0. Quick check: sing-box binary exists and runs
    # --------------------------------------------------------

    try:
        version_check = subprocess.run(
            [SING_BOX_BINARY, "version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5
        )
        version_line = (version_check.stdout or version_check.stderr).strip().split("\n")[0]
        print(f"sing-box binary: {SING_BOX_BINARY}")
        print(f"sing-box version: {version_line}")
        print()
    except Exception as e:
        print(f"ERROR: Cannot run sing-box binary at {SING_BOX_BINARY}")
        print(f"  {e}")
        print(f"Please set SING_BOX_BINARY to the correct path in the script settings.")
        return

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
    print("CONFIGS TO TEST (sing-box)")
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
    print("TESTING (sing-box)")
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
    print("DONE (sing-box)")
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
