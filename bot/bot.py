import os
import json
import time
import threading
from pathlib import Path

import telebot
from telebot import types
from dotenv import load_dotenv


# ============================================================
# ENV
# ============================================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing from .env")


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

SUBLINK_PATH = (
    BASE_DIR
    / ".."
    / "crawler"
    / "sublink.txt"
).resolve()

USERS_PATH = BASE_DIR / "users.json"


# ============================================================
# BOT
# ============================================================

bot = telebot.TeleBot(
    BOT_TOKEN,
    parse_mode=None
)


# ============================================================
# USERS
# ============================================================

def load_users():

    try:

        if not USERS_PATH.exists():

            USERS_PATH.write_text(
                "[]",
                encoding="utf-8"
            )

            return []

        with open(
            USERS_PATH,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        if not isinstance(data, list):
            return []

        return data

    except Exception as error:

        print(
            "Failed to load users:",
            error
        )

        return []


def save_users(users):

    with open(
        USERS_PATH,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            users,
            file,
            indent=4
        )


def add_user(chat_id):

    users = load_users()

    if chat_id not in users:

        users.append(chat_id)

        save_users(users)

        print(
            f"New user added: {chat_id}"
        )


# ============================================================
# LOAD CONFIGS
# ============================================================

def load_configs():

    try:

        with open(
            SUBLINK_PATH,
            "r",
            encoding="utf-8"
        ) as file:

            text = file.read()

        configs = [

            line.strip()

            for line in text.splitlines()

            if line.strip()
        ]

        return configs

    except Exception as error:

        print(
            "Failed to load sublink.txt:",
            error
        )

        return []


# ============================================================
# MAIN KEYBOARD
# ============================================================

def main_keyboard():

    keyboard = types.InlineKeyboardMarkup()

    subscription_button = types.InlineKeyboardButton(
        "🔗 Subscription Link",
        url="https://qrco.de/bgy6Bk"
    )

    configs_button = types.InlineKeyboardButton(
        "⚙️ Configs",
        callback_data="configs"
    )

    keyboard.row(
        subscription_button
    )

    keyboard.row(
        configs_button
    )

    return keyboard


# ============================================================
# /START
# ============================================================

@bot.message_handler(
    commands=["start"]
)
def start_command(message):

    chat_id = message.chat.id

    print(
        f"START received from {chat_id}"
    )

    add_user(chat_id)

    try:

        bot.send_message(
            chat_id,
            "Welcome to ConfigHub.\n\n"
            "Choose what you need:",
            reply_markup=main_keyboard()
        )

        print(
            f"START response sent to {chat_id}"
        )

    except Exception as error:

        print(
            f"START ERROR for {chat_id}:",
            error
        )


# ============================================================
# CONFIG LIST
# ============================================================

@bot.callback_query_handler(
    func=lambda call:
        call.data == "configs"
)
def configs_callback(call):

    try:

        bot.answer_callback_query(
            call.id
        )

        configs = load_configs()

        if not configs:

            bot.send_message(
                call.message.chat.id,
                "❌ No configurations are currently available."
            )

            return


        keyboard = types.InlineKeyboardMarkup()


        for index, config in enumerate(configs):

            button = types.InlineKeyboardButton(
                f"⚡ Config {index + 1:03d}",
                callback_data=f"config:{index}"
            )

            keyboard.row(
                button
            )


        back_button = types.InlineKeyboardButton(
            "⬅️ Back",
            callback_data="main"
        )

        keyboard.row(
            back_button
        )


        bot.send_message(
            call.message.chat.id,
            "Choose a configuration:",
            reply_markup=keyboard
        )

    except Exception as error:

        print(
            "CONFIG LIST ERROR:",
            error
        )


# ============================================================
# SEND CONFIG
# ============================================================

@bot.callback_query_handler(
    func=lambda call:
        call.data.startswith("config:")
)
def config_callback(call):

    try:

        bot.answer_callback_query(
            call.id
        )

        index = int(
            call.data.split(":")[1]
        )

        configs = load_configs()


        if (
            index < 0
            or index >= len(configs)
        ):

            bot.send_message(
                call.message.chat.id,
                "❌ This configuration no longer exists."
            )

            return


        config = configs[index]


        # EXACT CONFIG
        bot.send_message(
            call.message.chat.id,
            config
        )


    except Exception as error:

        print(
            "CONFIG SEND ERROR:",
            error
        )


# ============================================================
# BACK TO MAIN
# ============================================================

@bot.callback_query_handler(
    func=lambda call:
        call.data == "main"
)
def main_callback(call):

    try:

        bot.answer_callback_query(
            call.id
        )

        bot.send_message(
            call.message.chat.id,
            "Choose what you need:",
            reply_markup=main_keyboard()
        )

    except Exception as error:

        print(
            "MAIN MENU ERROR:",
            error
        )


# ============================================================
# BROADCAST
# ============================================================

def broadcast_update():

    users = load_users()

    if not users:

        print(
            "No users to broadcast."
        )

        return


    print(
        f"Broadcasting update to {len(users)} users..."
    )


    message = (
        "🔄 Configurations updated!\n\n"
        "New configurations are available.\n\n"
        "Please update your Subscription."
    )


    invalid_users = []


    for chat_id in users:

        try:

            bot.send_message(
                chat_id,
                message,
                reply_markup=main_keyboard()
            )

            print(
                f"Broadcast sent to {chat_id}"
            )


        except Exception as error:

            print(
                f"Failed to send to {chat_id}:",
                error
            )


            # User blocked bot / chat unavailable
            error_text = str(error)

            if (
                "bot was blocked" in error_text.lower()
                or "chat not found" in error_text.lower()
                or "user is deactivated" in error_text.lower()
            ):

                invalid_users.append(
                    chat_id
                )


        # Avoid hammering Telegram
        time.sleep(0.05)


    if invalid_users:

        remaining_users = [

            user

            for user in users

            if user not in invalid_users
        ]

        save_users(
            remaining_users
        )


    print(
        "Broadcast finished."
    )


# ============================================================
# SUBLINK WATCHER
# ============================================================

last_sublink_content = None


def initialize_sublink():

    global last_sublink_content

    try:

        with open(
            SUBLINK_PATH,
            "r",
            encoding="utf-8"
        ) as file:

            last_sublink_content = file.read()


        print(
            "Initial sublink loaded."
        )

        print(
            f"Watching: {SUBLINK_PATH}"
        )


    except Exception as error:

        print(
            "Could not read sublink.txt:",
            error
        )


def check_sublink():

    global last_sublink_content

    while True:

        try:

            with open(
                SUBLINK_PATH,
                "r",
                encoding="utf-8"
            ) as file:

                current_content = file.read()


            if last_sublink_content is None:

                last_sublink_content = (
                    current_content
                )


            elif (
                current_content
                != last_sublink_content
            ):

                print(
                    "================================"
                )

                print(
                    "sublink.txt changed!"
                )

                print(
                    "================================"
                )


                last_sublink_content = (
                    current_content
                )


                broadcast_update()


        except Exception as error:

            print(
                "Sublink check failed:",
                error
            )


        time.sleep(30)


# ============================================================
# START
# ============================================================

print(
    "================================"
)

print(
    "Starting ConfigHub bot..."
)

print(
    f"Watching: {SUBLINK_PATH}"
)

print(
    "================================"
)


initialize_sublink()


watcher_thread = threading.Thread(
    target=check_sublink,
    daemon=True
)

watcher_thread.start()


try:

    print(
        "Bot polling started."
    )

    bot.infinity_polling(
        skip_pending=True,
        timeout=30,
        long_polling_timeout=30
    )


except Exception as error:

    print(
        "BOT ERROR:",
        error
    )