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

MAX_CONFIGS = 100

OUTPUT_FILE = "sub.txt"
STATE_FILE = "telegram_state.json"

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

    channel = channel.replace(
        "@",
        ""
    )

    last_message_id = int(
        state.get(
            channel,
            0
        )
    )

    print()
    print("=" * 60)
    print(f"CHANNEL: {channel}")
    print(f"Last processed message: {last_message_id}")
    print("=" * 60)

    all_configs = []

    newest_message_id = last_message_id

    # --------------------------------------------------------
    # First page
    # --------------------------------------------------------

    url = BASE_URL + channel

    page_number = 0

    while True:

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

        reached_old_message = False

        for message in messages:

            message_id = get_message_id(
                message
            )

            if message_id is None:
                continue

            page_message_ids.append(
                message_id
            )

            # Newest message seen
            if message_id > newest_message_id:

                newest_message_id = message_id

            # ------------------------------------------------
            # Stop processing old messages
            # ------------------------------------------------

            if (
                last_message_id > 0
                and message_id <= last_message_id
            ):

                reached_old_message = True

                continue

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

        # ----------------------------------------------------
        # If we've reached messages we've already processed,
        # there is no reason to continue backwards.
        # ----------------------------------------------------

        if reached_old_message:

            print(
                "Reached previously processed messages."
            )

            break

        # ----------------------------------------------------
        # Find "previous" pagination link
        # ----------------------------------------------------

        previous_link = None

        # Telegram uses navigation links on public pages.
        # Look for a link that contains ?before=
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

        # ----------------------------------------------------
        # No more pages
        # ----------------------------------------------------

        if not previous_link:

            print(
                "No previous page available."
            )

            break

        # ----------------------------------------------------
        # Safety: avoid infinite loop
        # ----------------------------------------------------

        if page_number >= 100:

            print(
                "Pagination safety limit reached."
            )

            break

        # If current page doesn't move backwards,
        # stop to avoid infinite loop.

        if page_message_ids:

            oldest_on_page = min(
                page_message_ids
            )

            if (
                last_message_id > 0
                and oldest_on_page <= last_message_id
            ):

                break

        url = previous_link

    # --------------------------------------------------------
    # Update state
    # --------------------------------------------------------

    if newest_message_id > last_message_id:

        state[channel] = newest_message_id

    print()
    print(
        f"New configs found: "
        f"{len(all_configs)}"
    )

    print(
        f"Newest message ID: "
        f"{newest_message_id}"
    )

    return all_configs


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

    # --------------------------------------------------------
    # Remove duplicates
    # --------------------------------------------------------

    unique_configs = list(
        dict.fromkeys(
            all_configs
        )
    )

    # --------------------------------------------------------
    # Limit
    # --------------------------------------------------------

    unique_configs = unique_configs[
        :MAX_CONFIGS
    ]

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        for config in unique_configs:

            f.write(
                config + "\n"
            )

    save_state(
        state
    )

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("DONE")
    print("=" * 60)

    print(
        f"New configs saved: "
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


if __name__ == "__main__":
    main()