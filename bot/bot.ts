import { Bot, InlineKeyboard, InputFile } from "grammy";
import type {
  D1Database,
  ExecutionContext,
  ScheduledController,
} from "@cloudflare/workers-types";

interface Env {
  BOT_TOKEN: string;
  confighub_users: D1Database;
  // Public URL of this worker, e.g.
  // https://confighub-bot.<account>.workers.dev
  // Used by the cron job to keep the Telegram
  // webhook pointed at this worker.
  WORKER_URL?: string;
}

const SUBLINK_URL =
  "https://raw.githubusercontent.com/aghrabooti/V2ray_crawler/refs/heads/main/crawler/sublink.txt";

const SUBSCRIPTION_URL =
  "https://www.canvaqr.com/RGQotQsltm";


// ============================================================
// BOT
// ============================================================

async function createBot(env: Env) {
  const bot = new Bot(env.BOT_TOKEN);

  await bot.init();

  return bot;
}


// ============================================================
// USERS
// ============================================================

async function loadUsers(env: Env): Promise<string[]> {
  try {
    const result = await env.confighub_users
      .prepare("SELECT chat_id FROM users")
      .all<{ chat_id: string }>();

    return result.results.map((row) => row.chat_id);
  } catch (error) {
    console.error("Failed to load users:", error);
    return [];
  }
}


async function addUser(
  env: Env,
  chatId: string
): Promise<void> {
  try {
    await env.confighub_users
      .prepare(
        "INSERT OR IGNORE INTO users (chat_id) VALUES (?)"
      )
      .bind(chatId)
      .run();

    console.log(`User registered: ${chatId}`);
  } catch (error) {
    console.error("Failed to add user:", error);
  }
}


async function removeUser(
  env: Env,
  chatId: string
): Promise<void> {
  try {
    await env.confighub_users
      .prepare("DELETE FROM users WHERE chat_id = ?")
      .bind(chatId)
      .run();
  } catch (error) {
    console.error("Failed to remove user:", error);
  }
}


// ============================================================
// LOAD SUBLINK
// ============================================================

async function loadSublink(): Promise<string> {
  try {
    const response = await fetch(
      `${SUBLINK_URL}?t=${Date.now()}`,
      {
        headers: {
          "Cache-Control": "no-cache",
        },
      }
    );

    if (!response.ok) {
      throw new Error(
        `HTTP ${response.status}`
      );
    }

    return await response.text();
  } catch (error) {
    console.error(
      "Failed to load sublink:",
      error
    );

    return "";
  }
}


// ============================================================
// LOAD CONFIGS
// ============================================================

async function loadConfigs(): Promise<string[]> {
  const sublink = await loadSublink();

  if (!sublink) {
    return [];
  }

  return sublink
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}


// ============================================================
// MAIN KEYBOARD
// ============================================================

function mainKeyboard() {
  return new InlineKeyboard()
    .text(
      "🔗 Subscription Link",
      "subscription"
    )
    .row()
    .text(
      "⚙️ Configs",
      "configs"
    );
}


// ============================================================
// /START
// ============================================================

function registerHandlers(
  bot: Bot,
  env: Env
) {

  bot.command(
    "start",
    async (ctx) => {

      try {

        const chatId = String(
          ctx.chat.id
        );

        console.log(
          `START received from ${chatId}`
        );

        await addUser(
          env,
          chatId
        );

        await ctx.reply(
          "Welcome to ConfigHub.\n\n" +
          "Choose what you need:",
          {
            reply_markup:
              mainKeyboard(),
          }
        );

      } catch (error) {

        console.error(
          "START ERROR:",
          error
        );

      }

    }
  );


  // ==========================================================
  // SUBSCRIPTION
  // ==========================================================

  bot.callbackQuery(
    "subscription",
    async (ctx) => {

      try {

        await ctx.answerCallbackQuery();

        await ctx.reply(
          SUBSCRIPTION_URL
        );

      } catch (error) {

        console.error(
          "SUBSCRIPTION ERROR:",
          error
        );

      }

    }
  );


  // ==========================================================
  // CONFIG LIST
  // ==========================================================

  bot.callbackQuery(
    "configs",
    async (ctx) => {

      try {

        await ctx.answerCallbackQuery();

        const configs =
          await loadConfigs();

        if (!configs.length) {

          await ctx.reply(
            "❌ No configurations are currently available."
          );

          return;
        }


        const keyboard =
          new InlineKeyboard();


        // COPY ALL

        keyboard
          .text(
            "📋 Copy All Configs",
            "copy_all"
          )
          .row();


        // INDIVIDUAL CONFIGS

        configs.forEach(
          (_, index) => {

            keyboard
              .text(
                `⚡ Config ${String(
                  index + 1
                ).padStart(3, "0")}`,
                `config:${index}`
              )
              .row();

          }
        );


        // BACK

        keyboard.text(
          "⬅️ Back",
          "main"
        );


        await ctx.reply(
          "Choose a configuration:",
          {
            reply_markup:
              keyboard,
          }
        );

      } catch (error) {

        console.error(
          "CONFIG LIST ERROR:",
          error
        );

      }

    }
  );


  // ==========================================================
  // COPY ALL
  // ==========================================================

  bot.callbackQuery(
    "copy_all",
    async (ctx) => {

      try {

        await ctx.answerCallbackQuery(
          "Sending all configurations..."
        );


        const sublink =
          await loadSublink();


        if (!sublink) {

          await ctx.reply(
            "❌ No configurations are currently available."
          );

          return;
        }


        // Telegram message limit

        if (sublink.length <= 4000) {

          const message =
            `<pre>${escapeHtml(
              sublink
            )}</pre>`;


          await ctx.reply(
            message,
            {
              parse_mode: "HTML",
            }
          );

        } else {

          const blob =
            new Blob(
              [sublink],
              {
                type: "text/plain",
              }
            );


          await ctx.replyWithDocument(
            new InputFile(
              blob,
              "sublink.txt"
            ),
            {
              caption:
                "📋 All configurations",
            }
          );

        }

      } catch (error) {

        console.error(
          "COPY ALL ERROR:",
          error
        );

      }

    }
  );


  // ==========================================================
  // INDIVIDUAL CONFIG
  // ==========================================================

  bot.callbackQuery(
    /^config:(\d+)$/,
    async (ctx) => {

      try {

        await ctx.answerCallbackQuery();


        const index =
          Number(
            ctx.match[1]
          );


        const configs =
          await loadConfigs();


        if (
          index < 0 ||
          index >= configs.length
        ) {

          await ctx.reply(
            "❌ This configuration no longer exists."
          );

          return;
        }


        await ctx.reply(
          configs[index]
        );

      } catch (error) {

        console.error(
          "CONFIG SEND ERROR:",
          error
        );

      }

    }
  );


  // ==========================================================
  // BACK
  // ==========================================================

  bot.callbackQuery(
    "main",
    async (ctx) => {

      try {

        await ctx.answerCallbackQuery();

        await ctx.reply(
          "Choose what you need:",
          {
            reply_markup:
              mainKeyboard(),
          }
        );

      } catch (error) {

        console.error(
          "MAIN MENU ERROR:",
          error
        );

      }

    }
  );


  // ==========================================================
  // ANY OTHER MESSAGE -> SHOW THE MENU
  // ==========================================================

  bot.on(
    "message",
    async (ctx) => {

      try {

        await addUser(
          env,
          String(ctx.chat.id)
        );

        await ctx.reply(
          "Choose what you need:",
          {
            reply_markup:
              mainKeyboard(),
          }
        );

      } catch (error) {

        console.error(
          "MESSAGE FALLBACK ERROR:",
          error
        );

      }

    }
  );


  // ==========================================================
  // ANY UNMATCHED CALLBACK
  // ==========================================================

  bot.on(
    "callback_query",
    async (ctx) => {

      try {

        await ctx.answerCallbackQuery();

      } catch {}

    }
  );


  // ==========================================================
  // INLINE MODE
  // ==========================================================

  bot.on(
    "inline_query",
    async (ctx) => {

      try {

        const configs =
          await loadConfigs();


        const results: any[] =
          [];


        const search =
          ctx.inlineQuery.query
            .trim()
            .toLowerCase();


        // ------------------------------------------------------
        // ALL CONFIGS
        // ------------------------------------------------------

        if (
          !search ||
          search === "all" ||
          search === "*"
        ) {

          const allConfigs =
            configs.join("\n");


          if (
            allConfigs.length <= 4096
          ) {

            results.push({

              type: "article",

              id: "all_configs",

              title:
                "📋 All Configs",

              description:
                `${configs.length} configurations`,

              input_message_content: {

                message_text:
                  allConfigs,

              },

            });

          }

        }


        // ------------------------------------------------------
        // INDIVIDUAL CONFIGS
        // ------------------------------------------------------

        for (
          let index = 0;
          index < configs.length;
          index++
        ) {

          const config =
            configs[index];


          if (
            search &&
            !config
              .toLowerCase()
              .includes(search)
          ) {

            continue;

          }


          let preview =
            config;


          if (
            preview.length > 80
          ) {

            preview =
              preview.slice(
                0,
                80
              ) + "...";

          }


          results.push({

            type: "article",

            id:
              `config_${index}`,

            title:
              `⚡ Config ${String(
                index + 1
              ).padStart(3, "0")}`,

            description:
              preview,

            input_message_content: {

              message_text:
                config,

            },

          });


          if (
            results.length >= 50
          ) {

            break;

          }

        }


        await ctx.answerInlineQuery(
          results,
          {
            cache_time: 5,
            is_personal: true,
          }
        );

      } catch (error) {

        console.error(
          "INLINE ERROR:",
          error
        );


        try {

          await ctx.answerInlineQuery(
            [],
            {
              cache_time: 1,
            }
          );

        } catch {}

      }

    }
  );

}


// ============================================================
// BROADCAST
// ============================================================

async function broadcastUpdate(
  env: Env
): Promise<void> {

  const bot =
    await createBot(env);


  const users =
    await loadUsers(env);


  if (!users.length) {

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


  for (
    const chatId of users
  ) {

    try {

      await bot.api.sendMessage(
        chatId,
        message,
        {
          reply_markup:
            mainKeyboard(),
        }
      );


      console.log(
        `Broadcast sent to ${chatId}`
      );

    } catch (error) {

      console.error(
        `Failed to send to ${chatId}:`,
        error
      );


      const errorText =
        String(error).toLowerCase();


      if (
        errorText.includes(
          "bot was blocked"
        ) ||
        errorText.includes(
          "chat not found"
        ) ||
        errorText.includes(
          "user is deactivated"
        )
      ) {

        await removeUser(
          env,
          chatId
        );

      }

    }

  }


  // Remember what was broadcast, so the cron
  // fallback does not send a duplicate message.

  try {

    const sublink = await loadSublink();

    if (sublink.trim()) {

      await setState(
        env,
        "sublink_fingerprint",
        `${sublink.length}:${hashString(sublink)}`
      );

    }

  } catch {}


  console.log(
    "Broadcast finished."
  );

}


// ============================================================
// SIMPLE HASH
// ============================================================

function hashString(text: string): string {

  let hash = 5381;

  for (let i = 0; i < text.length; i++) {

    hash = ((hash * 33) ^ text.charCodeAt(i)) >>> 0;

  }

  return hash.toString(16);

}


// ============================================================
// STATE (D1 key/value)
// ============================================================

async function ensureStateTable(
  env: Env
): Promise<void> {

  await env.confighub_users
    .prepare(
      "CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT)"
    )
    .run();

}


async function getState(
  env: Env,
  key: string
): Promise<string | null> {

  try {

    await ensureStateTable(env);

    const row = await env.confighub_users
      .prepare(
        "SELECT value FROM state WHERE key = ?"
      )
      .bind(key)
      .first<{ value: string }>();

    return row ? row.value : null;

  } catch (error) {

    console.error("getState failed:", error);

    return null;

  }

}


async function setState(
  env: Env,
  key: string,
  value: string
): Promise<void> {

  try {

    await ensureStateTable(env);

    await env.confighub_users
      .prepare(
        "INSERT INTO state (key, value) VALUES (?, ?) " +
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value"
      )
      .bind(key, value)
      .run();

  } catch (error) {

    console.error("setState failed:", error);

  }

}


// ============================================================
// WEBHOOK SELF-HEALING
//
// Telegram delivers updates to exactly ONE target.
// If the webhook gets dropped (token revoked, someone ran
// the polling script in bot/bot.py, someone set another
// webhook) the bot can still SEND messages but stops
// REACTING to /start and buttons.
// The cron job re-arms the webhook automatically.
// ============================================================

async function ensureWebhook(
  env: Env
): Promise<void> {

  if (!env.WORKER_URL) {

    console.log(
      "WORKER_URL not configured, skipping webhook check."
    );

    return;

  }

  const expected =
    `${env.WORKER_URL.replace(/\/+$/, "")}/telegram`;

  try {

    const infoResponse = await fetch(
      `https://api.telegram.org/bot${env.BOT_TOKEN}/getWebhookInfo`
    );

    const info = await infoResponse.json() as {
      result?: {
        url?: string;
        last_error_message?: string;
      };
    };

    const current = info.result?.url || "";

    if (info.result?.last_error_message) {

      console.error(
        "Webhook last error:",
        info.result.last_error_message
      );

    }

    if (current === expected) {

      return;

    }

    console.log(
      `Webhook is "${current}", re-arming to "${expected}"`
    );

    await fetch(
      `https://api.telegram.org/bot${env.BOT_TOKEN}/setWebhook`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          url: expected,
          allowed_updates: [
            "message",
            "callback_query",
            "inline_query",
          ],
        }),
      }
    );

  } catch (error) {

    console.error(
      "ensureWebhook failed:",
      error
    );

  }

}


// ============================================================
// HTML ESCAPE
// ============================================================

function escapeHtml(
  text: string
): string {

  return text
    .replace(
      /&/g,
      "&amp;"
    )
    .replace(
      /</g,
      "&lt;"
    )
    .replace(
      />/g,
      "&gt;"
    )
    .replace(
      /"/g,
      "&quot;"
    );

}


// ============================================================
// CLOUDFLARE WORKER
// ============================================================

export default {

  // ==========================================================
  // SCHEDULED
  // ==========================================================

  async scheduled(
    controller: ScheduledController,
    env: Env,
    ctx: ExecutionContext
  ): Promise<void> {

    console.log(
      `Scheduled event: ${new Date().toISOString()}`
    );


    // 1. Keep the Telegram webhook pointed here,
    //    so /start and buttons never go silent.

    await ensureWebhook(env);


    // 2. Fallback change detection, in case the
    //    GitHub webhook to /github-update is off.

    try {

      const sublink = await loadSublink();

      if (!sublink.trim()) {

        return;

      }

      const fingerprint =
        `${sublink.length}:${hashString(sublink)}`;

      const previous =
        await getState(env, "sublink_fingerprint");

      if (previous === null) {

        await setState(
          env,
          "sublink_fingerprint",
          fingerprint
        );

        console.log(
          "Stored initial sublink fingerprint."
        );

        return;

      }

      if (previous !== fingerprint) {

        console.log(
          "sublink.txt changed, broadcasting."
        );

        await setState(
          env,
          "sublink_fingerprint",
          fingerprint
        );

        await broadcastUpdate(env);

      }

    } catch (error) {

      console.error(
        "SCHEDULED ERROR:",
        error
      );

    }

  },


  // ==========================================================
  // FETCH
  // ==========================================================

  async fetch(
    request: Request,
    env: Env,
    ctx: ExecutionContext
  ): Promise<Response> {

    const url =
      new URL(request.url);


    // ========================================================
    // GITHUB WEBHOOK
    // ========================================================

    if (
      url.pathname ===
      "/github-update"
    ) {

      if (
        request.method !== "POST"
      ) {

        return new Response(
          "Method Not Allowed",
          {
            status: 405,
          }
        );

      }


      try {

        const body =
          await request.json() as {
            commits?: Array<{
              added?: string[];
              modified?: string[];
              removed?: string[];
            }>;
          };


        const commits =
          body.commits || [];


        const changed =
          commits.some(
            (commit) => {

              const files = [

                ...(commit.added || []),

                ...(commit.modified || []),

                ...(commit.removed || []),

              ];


              return files.some(
                (file) =>
                  file ===
                  "crawler/sublink.txt"
              );

            }
          );


        console.log(
          `GitHub webhook received. Changed: ${changed}`
        );


        if (changed) {

          // Wait for broadcast before
          // returning the response.

          await broadcastUpdate(
            env
          );

        }


        return Response.json({

          success: true,

          changed,

        });

      } catch (error) {

        console.error(
          "GITHUB WEBHOOK ERROR:",
          error
        );


        return Response.json(
          {
            success: false,
            error: "Invalid webhook payload",
          },
          {
            status: 400,
          }
        );

      }

    }


    // ========================================================
    // WEBHOOK MANAGEMENT
    //   GET /set-webhook   -> points Telegram to this worker
    //   GET /webhook-info  -> shows the current webhook state
    // ========================================================

    if (
      url.pathname === "/set-webhook"
    ) {

      try {

        const webhookUrl =
          `${url.origin}/telegram`;


        const response =
          await fetch(
            `https://api.telegram.org/bot${env.BOT_TOKEN}/setWebhook`,
            {
              method: "POST",
              headers: {
                "Content-Type":
                  "application/json",
              },
              body: JSON.stringify({
                url: webhookUrl,
                allowed_updates: [
                  "message",
                  "callback_query",
                  "inline_query",
                ],
                drop_pending_updates: true,
              }),
            }
          );


        return new Response(
          await response.text(),
          {
            headers: {
              "Content-Type":
                "application/json",
            },
          }
        );

      } catch (error) {

        return new Response(
          `setWebhook failed: ${String(error)}`,
          { status: 500 }
        );

      }

    }


    if (
      url.pathname === "/webhook-info"
    ) {

      const response =
        await fetch(
          `https://api.telegram.org/bot${env.BOT_TOKEN}/getWebhookInfo`
        );


      return new Response(
        await response.text(),
        {
          headers: {
            "Content-Type":
              "application/json",
          },
        }
      );

    }


    // ========================================================
    // TELEGRAM WEBHOOK
    //
    // Accept the update on /telegram, on /<bot token>
    // and on any POST to the root path, so a webhook that
    // was registered with a different path still works.
    // ========================================================

    if (
      request.method === "POST" &&
      (
        url.pathname === "/telegram" ||
        url.pathname === "/" ||
        url.pathname === "" ||
        url.pathname ===
          `/${env.BOT_TOKEN}`
      )
    ) {

      try {

        const bot =
          await createBot(env);


        registerHandlers(
          bot,
          env
        );


        const update =
          await request.json();


        await bot.handleUpdate(
          update as any
        );


        return new Response(
          "OK"
        );

      } catch (error) {

        console.error(
          "TELEGRAM WEBHOOK ERROR:",
          error
        );


        return new Response(
          "Error",
          {
            status: 500,
          }
        );

      }

    }


    // ========================================================
    // HEALTH CHECK
    // ========================================================

    return new Response(
      "ConfigHub bot is running."
    );

  },

};