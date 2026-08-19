import { Bot, InlineKeyboard } from "grammy";
import dotenv from "dotenv";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

dotenv.config();


// ============================================================
// PATHS
// ============================================================

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const SUBLINK_PATH = path.join(
    __dirname,
    "..",
    "sublink.txt"
);

const USERS_PATH = path.join(
    __dirname,
    "users.json"
);


// ============================================================
// BOT
// ============================================================

const bot = new Bot(
    process.env.BOT_TOKEN
);


// ============================================================
// USERS
// ============================================================

function loadUsers() {

    try {

        if (!fs.existsSync(USERS_PATH)) {

            fs.writeFileSync(
                USERS_PATH,
                "[]",
                "utf8"
            );

            return [];

        }

        const data =
            fs.readFileSync(
                USERS_PATH,
                "utf8"
            );

        const users =
            JSON.parse(data);

        if (!Array.isArray(users)) {
            return [];
        }

        return users;

    } catch (error) {

        console.error(
            "Failed to load users:",
            error
        );

        return [];

    }

}


function saveUsers(users) {

    fs.writeFileSync(
        USERS_PATH,
        JSON.stringify(
            users,
            null,
            4
        ),
        "utf8"
    );

}


function addUser(chatId) {

    const users =
        loadUsers();

    if (!users.includes(chatId)) {

        users.push(chatId);

        saveUsers(users);

        console.log(
            `New user added: ${chatId}`
        );

    }

}


// ============================================================
// LOAD CONFIGS
// ============================================================

function loadConfigs() {

    try {

        const text =
            fs.readFileSync(
                SUBLINK_PATH,
                "utf8"
            );


        return text
            .split(/\r?\n/)
            .map(line => line.trim())
            .filter(line =>
                line.length > 0
            );


    } catch (error) {

        console.error(
            "Failed to load sublink.txt:",
            error
        );

        return [];

    }

}


// ============================================================
// MAIN MENU
// ============================================================

function mainKeyboard() {

    return new InlineKeyboard()

        .url(
            "🔗 Subscription Link",
            "https://qrco.de/bgy6Bk"
        )

        .row()

        .text(
            "⚙️ Configs",
            "configs"
        );

}


// ============================================================
// /start
// ============================================================

bot.command(
    "start",
    async ctx => {

        const chatId =
            ctx.chat.id;

        addUser(chatId);


        await ctx.reply(
            "Welcome to ConfigHub.\n\n" +
            "Choose what you need:",
            {
                reply_markup:
                    mainKeyboard()
            }
        );

    }
);


// ============================================================
// CONFIG LIST
// ============================================================

bot.callbackQuery(
    "configs",
    async ctx => {

        await ctx.answerCallbackQuery();


        const configs =
            loadConfigs();


        if (configs.length === 0) {

            await ctx.reply(
                "❌ No configurations are currently available."
            );

            return;

        }


        const keyboard =
            new InlineKeyboard();


        configs.forEach(
            (config, index) => {

                keyboard.text(
                    `⚡ Config ${String(index + 1).padStart(3, "0")}`,
                    `config:${index}`
                );

                keyboard.row();

            }
        );


        keyboard.text(
            "⬅️ Back",
            "main"
        );


        await ctx.reply(
            "Choose a configuration:",
            {
                reply_markup:
                    keyboard
            }
        );

    }
);


// ============================================================
// SEND CONFIG
// ============================================================

bot.callbackQuery(
    /^config:(\d+)$/,
    async ctx => {

        await ctx.answerCallbackQuery();


        const index =
            Number(
                ctx.match[1]
            );


        const configs =
            loadConfigs();


        if (
            index < 0 ||
            index >= configs.length
        ) {

            await ctx.reply(
                "❌ This configuration no longer exists."
            );

            return;

        }


        const config =
            configs[index];


        // Send the EXACT config
        await ctx.reply(
            config
        );

    }
);


// ============================================================
// BACK TO MAIN MENU
// ============================================================

bot.callbackQuery(
    "main",
    async ctx => {

        await ctx.answerCallbackQuery();


        await ctx.reply(
            "Choose what you need:",
            {
                reply_markup:
                    mainKeyboard()
            }
        );

    }
);


// ============================================================
// BROADCAST
// ============================================================

async function broadcastUpdate() {

    const users =
        loadUsers();


    if (users.length === 0) {

        console.log(
            "No users to broadcast."
        );

        return;

    }


    console.log(
        `Broadcasting update to ${users.length} users...`
    );


    const message =
        "🔄 Configurations updated!\n\n" +
        "New configurations are available.\n\n" +
        "Please update your Subscription.";


    const invalidUsers = [];


    for (const chatId of users) {

        try {

            await bot.api.sendMessage(
                chatId,
                message,
                {
                    reply_markup:
                        mainKeyboard()
                }
            );


            console.log(
                `Broadcast sent to ${chatId}`
            );


        } catch (error) {

            console.error(
                `Failed to send to ${chatId}:`,
                error.description ||
                error.message
            );


            /*
             * If the user blocked the bot
             * or the chat no longer exists,
             * remove the chat ID.
             */

            if (
                error.error_code === 403
            ) {

                invalidUsers.push(
                    chatId
                );

            }

        }

    }


    if (invalidUsers.length > 0) {

        const remainingUsers =
            users.filter(
                id =>
                    !invalidUsers.includes(id)
            );


        saveUsers(
            remainingUsers
        );

    }


    console.log(
        "Broadcast finished."
    );

}


// ============================================================
// WATCH SUBLINK
// ============================================================

let lastSublinkContent = null;


function initializeSublinkWatcher() {

    try {

        lastSublinkContent =
            fs.readFileSync(
                SUBLINK_PATH,
                "utf8"
            );

        console.log(
            "Initial sublink loaded."
        );

    } catch (error) {

        console.error(
            "Could not read sublink.txt:",
            error
        );

    }

}


async function checkSublink() {

    try {

        const currentContent =
            fs.readFileSync(
                SUBLINK_PATH,
                "utf8"
            );


        if (
            lastSublinkContent === null
        ) {

            lastSublinkContent =
                currentContent;

            return;

        }


        if (
            currentContent !==
            lastSublinkContent
        ) {

            console.log(
                "sublink.txt changed!"
            );


            lastSublinkContent =
                currentContent;


            await broadcastUpdate();

        }

    } catch (error) {

        console.error(
            "Sublink check failed:",
            error
        );

    }

}


// ============================================================
// START BOT
// ============================================================

initializeSublinkWatcher();


setInterval(
    checkSublink,
    30000
);


bot.catch(error => {

    console.error(
        "Bot error:",
        error
    );

});


bot.start({

    onStart:
        botInfo => {

            console.log(
                `Bot started: @${botInfo.username}`
            );

            console.log(
                `Watching: ${SUBLINK_PATH}`
            );

        }

});