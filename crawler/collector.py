import requests
from bs4 import BeautifulSoup
import re
import json
import os
from urllib.parse import urljoin


# ============================================================
# SETTINGS
# ============================================================

CHANNELS = ["DailyV2Proxy"]

MAX_CONFIGS = 300

# Files will be saved next to this Python script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

OUTPUT_FILE = os.path.join(
    SCRIPT_DIR,
    "sub.txt"
)

STATE_FILE = os.path.join(
    SCRIPT_DIR,
    "telegram_state.json"
)

BASE_URL = "https://t.me/s/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/150.0 Safari/537.36"
    )
}

REQUEST_TIMEOUT = 15


# ============================================================
# LOAD STATE
# ============================================================

def load_state():
    if not os.path.exists(STATE_FILE):
        return {}

    try:
        with open(
            STATE_FILE,
            "r",
            encoding="utf-8"
        ) as f:
            return json.load(f)

    except Exception:
        return {}


# ============================================================
# SAVE STATE
# ============================================================

def save_state(state):
    with open(
        STATE_FILE,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            state,
            f,
            indent=2,
            ensure_ascii=False
        )


# ============================================================
# EXTRACT MESSAGE ID
# ============================================================

def get_message_id(message):
    data_post = message.get("data-post")

    if not data_post:
        return None

    try:
        # Example:
        # DailyV2Proxy/12345

        return int(
            data_post.rsplit("/", 1)[-1]
        )

    except Exception:
        return None


# ============================================================
# EXTRACT CONFIGS
# ============================================================

def extract_configs(text):
    pattern = (
        r"vmess://[^\s<]+"
        r"|vless://[^\s<]+"
        r"|trojan://[^\s<]+"
        r"|ss://[^\s<]+"
    )

    return re.findall(
        pattern,
        text
    )


# ============================================================
# GET PAGE
# ============================================================

def get_page(url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()

    return BeautifulSoup(
        response.content,
        "html.parser"
    )


# ============================================================
# SCRAPE CHANNEL
# ============================================================

def scrape_channel(channel, state):

    channel = channel.replace("@", "")

    # Message ID saved from previous run
    last_saved_message_id = int(
        state.get(
            channel,
            0
        )
    )

    print()
    print("=" * 60)
    print(f"CHANNEL: {channel}")
    print(
        f"Saved message ID: "
        f"{last_saved_message_id}"
    )
    print("=" * 60)

    all_configs = []

    # This will contain the newest message ID
    # of the channel that we see during this run.
    newest_message_id = None

    url = BASE_URL + channel

    page_number = 0

    reached_saved_message = False

    # ========================================================
    # PAGINATION
    # ========================================================

    while True:

        # If we already have enough configs,
        # there is no reason to continue.
        if len(all_configs) >= MAX_CONFIGS:
            print(
                f"Reached MAX_CONFIGS ({MAX_CONFIGS})."
            )
            break

        page_number += 1

        print(
            f"Loading page {page_number}..."
        )

        try:
            soup = get_page(url)

        except Exception as e:
            print(
                f"ERROR loading page: {e}"
            )
            break

        messages = soup.find_all(
            "div",
            class_="tgme_widget_message"
        )

        if not messages:
            print(
                "No messages found."
            )
            break

        page_message_ids = []

        # ====================================================
        # PROCESS MESSAGES
        # ====================================================

        for message in messages:

            message_id = get_message_id(
                message
            )

            if message_id is None:
                continue

            page_message_ids.append(
                message_id
            )

            # ------------------------------------------------
            # Get newest message ID
            # ------------------------------------------------

            if (
                newest_message_id is None
                or message_id > newest_message_id
            ):
                newest_message_id = message_id

            # ------------------------------------------------
            # STOP AT SAVED MESSAGE
            # ------------------------------------------------

            if (
                last_saved_message_id > 0
                and message_id <= last_saved_message_id
            ):
                reached_saved_message = True

                print(
                    f"Reached saved message: "
                    f"{message_id}"
                )

                break

            # ------------------------------------------------
            # Extract text
            # ------------------------------------------------

            text_element = message.find(
                "div",
                class_="tgme_widget_message_text"
            )

            if not text_element:
                continue

            text = text_element.get_text(
                " ",
                strip=True
            )

            configs = extract_configs(
                text
            )

            if configs:

                print(
                    f"Message {message_id}: "
                    f"{len(configs)} configs"
                )

                all_configs.extend(
                    configs
                )

                # Don't unnecessarily collect
                # thousands of configs from one message.
                if len(all_configs) >= MAX_CONFIGS:
                    break

        # ====================================================
        # STOP CONDITIONS
        # ====================================================

        if reached_saved_message:
            print(
                "Reached previously saved message."
            )
            break

        if len(all_configs) >= MAX_CONFIGS:
            print(
                f"Reached MAX_CONFIGS ({MAX_CONFIGS})."
            )
            break

        # ====================================================
        # FIND PREVIOUS PAGE
        # ====================================================

        previous_link = None

        for link in soup.find_all(
            "a",
            href=True
        ):

            href = link["href"]

            if "?before=" in href:

                previous_link = urljoin(
                    "https://t.me",
                    href
                )

                break

        # ====================================================
        # NO MORE PAGES
        # ====================================================

        if not previous_link:

            print(
                "No previous page available."
            )
            break

        # ====================================================
        # SAFETY LIMIT
        # ========================================================

        if page_number >= 100:

            print(
                "Pagination safety limit reached."
            )
            break

        # ====================================================
        # SAFETY: MAKE SURE WE ARE MOVING BACKWARDS
        # ========================================================

        if page_message_ids:

            oldest_on_page = min(
                page_message_ids
            )

            # If the next page isn't actually older,
            # prevent an infinite loop.
            if previous_link == url:

                print(
                    "Pagination did not move. Stopping."
                )
                break

        url = previous_link

    # =========================================================
    # UPDATE STATE
    # =========================================================

    if newest_message_id is not None:

        state[channel] = newest_message_id

    # =========================================================
    # REMOVE DUPLICATES
    # =========================================================

    unique_configs = list(
        dict.fromkeys(
            all_configs
        )
    )

    # =========================================================
    # LIMIT
    # =========================================================

    unique_configs = unique_configs[
        :MAX_CONFIGS
    ]

    print()
    print(
        f"New configs found: "
        f"{len(unique_configs)}"
    )

    print(
        f"Newest message ID: "
        f"{newest_message_id}"
    )

    print(
        f"Reached saved message: "
        f"{reached_saved_message}"
    )

    return unique_configs


# ============================================================
# MAIN
# ============================================================

def main():

    state = load_state()

    all_configs = []

    for channel in CHANNELS:

        try:

            configs = scrape_channel(
                channel,
                state
            )

            all_configs.extend(
                configs
            )

        except Exception as e:

            print(
                f"ERROR {channel}: {e}"
            )

    # ========================================================
    # REMOVE DUPLICATES
    # ========================================================

    unique_configs = list(
        dict.fromkeys(
            all_configs
        )
    )

    # ========================================================
    # LIMIT
    # ========================================================

    unique_configs = unique_configs[
        :MAX_CONFIGS
    ]

    # ========================================================
    # SAVE SUB.TXT
    # ========================================================

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        for config in unique_configs:

            f.write(
                config + "\n"
            )

    # ========================================================
    # SAVE STATE
    # ========================================================

    save_state(
        state
    )

    # ========================================================
    # RESULT
    # ========================================================

    print()
    print("=" * 60)
    print("DONE")
    print("=" * 60)

    print(
        f"Configs saved: "
        f"{len(unique_configs)}"
    )

    print(
        f"Output: "
        f"{OUTPUT_FILE}"
    )

    print(
        f"State: "
        f"{STATE_FILE}"
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()