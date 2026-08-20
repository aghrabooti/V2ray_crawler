import { Bot, InlineKeyboard, InputFile } from "grammy";
import type {
  D1Database,
  ExecutionContext,
  ScheduledController,
} from "@cloudflare/workers-types";

interface Env {
  BOT_TOKEN: string;
  confighub_users: D1Database;
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


  console.log(
    "Broadcast finished."
  );

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

    // Nothing needs to run here.
    // The bot is webhook-based.
    //
    // GitHub sends POST /github-update
    // whenever crawler/sublink.txt changes.

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
    // TELEGRAM WEBHOOK
    // ========================================================

    if (
      url.pathname ===
      "/telegram"
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