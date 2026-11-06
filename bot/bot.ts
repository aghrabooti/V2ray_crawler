import {
  Bot,
  Context,
  GrammyError,
  InlineKeyboard,
  InputFile,
  webhookCallback,
} from "grammy";
import type {
  D1Database,
  ExecutionContext,
  ScheduledController,
} from "@cloudflare/workers-types";

interface Env {
  BOT_TOKEN: string;
  confighub_users: D1Database;
  // اختیاری ولی توصیه می‌شود (با wrangler secret put ساخته شوند)
  TELEGRAM_SECRET?: string; // همان secret_token در setWebhook
  GITHUB_SECRET?: string; // همان secret در تنظیمات Webhook گیت‌هاب
}

const SUBLINK_URL =
  "https://raw.githubusercontent.com/aghrabooti/V2ray_crawler/refs/heads/main/crawler/sublink.txt";

const SUBSCRIPTION_URL = "https://www.canvaqr.com/RGQotQsltm";

const PAGE_SIZE = 10; // هر صفحه ۱۰ کانفیگ (حد تلگرام: ۱۰۰ دکمه)

// ============================================================
// HELPERS
// ============================================================

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

// ============================================================
// USERS (D1)
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

async function addUser(env: Env, chatId: string): Promise<void> {
  try {
    await env.confighub_users
      .prepare("INSERT OR IGNORE INTO users (chat_id) VALUES (?)")
      .bind(chatId)
      .run();
  } catch (error) {
    console.error("Failed to add user:", error);
  }
}

async function removeUser(env: Env, chatId: string): Promise<void> {
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
// SUBLINK / CONFIGS
// ============================================================

async function loadSublink(): Promise<string> {
  try {
    const response = await fetch(`${SUBLINK_URL}?t=${Date.now()}`, {
      headers: { "Cache-Control": "no-cache" },
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.text();
  } catch (error) {
    console.error("Failed to load sublink:", error);
    return "";
  }
}

async function loadConfigs(): Promise<string[]> {
  const sublink = await loadSublink();
  if (!sublink) return [];
  return sublink
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

// ============================================================
// KEYBOARDS
// ============================================================

function mainKeyboard() {
  return new InlineKeyboard()
    .text("🔗 Subscription Link", "subscription")
    .row()
    .text("⚙️ Configs", "configs:0");
}

function configsKeyboard(configs: string[], page: number) {
  const totalPages = Math.max(1, Math.ceil(configs.length / PAGE_SIZE));
  const safePage = Math.min(Math.max(page, 0), totalPages - 1);
  const start = safePage * PAGE_SIZE;
  const slice = configs.slice(start, start + PAGE_SIZE);

  const kb = new InlineKeyboard().text("📋 Copy All Configs", "copy_all").row();

  slice.forEach((_, i) => {
    const idx = start + i;
    kb.text(
      `⚡ Config ${String(idx + 1).padStart(3, "0")}`,
      `config:${idx}`
    ).row();
  });

  if (safePage > 0) kb.text("⬅️ قبلی", `configs:${safePage - 1}`);
  kb.text(`${safePage + 1}/${totalPages}`, "noop");
  if (safePage < totalPages - 1) kb.text("بعدی ➡️", `configs:${safePage + 1}`);

  kb.row().text("🏠 Back", "main");

  return { kb, safePage, totalPages };
}

// ============================================================
// SAFE ANSWER / EDIT
// ============================================================

// اگر callback قدیمی باشد answerCallbackQuery خطا می‌دهد؛
// نباید جلوی ادامه‌ی هندلر را بگیرد.
async function safeAnswer(ctx: Context, text?: string) {
  try {
    await ctx.answerCallbackQuery(text ? { text } : undefined);
  } catch (error) {
    console.warn("answerCallbackQuery failed:", String(error));
  }
}

async function editOrReply(
  ctx: Context,
  text: string,
  reply_markup: InlineKeyboard
) {
  try {
    await ctx.editMessageText(text, { reply_markup });
  } catch (error) {
    if (
      error instanceof GrammyError &&
      error.description.includes("message is not modified")
    ) {
      return;
    }
    await ctx.reply(text, { reply_markup });
  }
}

// ============================================================
// HANDLERS
// ============================================================

function registerHandlers(bot: Bot, env: Env) {
  bot.catch((err) => {
    console.error("BOT ERROR:", err.error);
  });

  // ---------- /start ----------
  bot.command("start", async (ctx) => {
    const chatId = String(ctx.chat.id);
    await addUser(env, chatId);
    await ctx.reply("Welcome to ConfigHub.\n\nChoose what you need:", {
      reply_markup: mainKeyboard(),
    });
  });

  // ---------- noop ----------
  bot.callbackQuery("noop", async (ctx) => {
    await safeAnswer(ctx);
  });

  // ---------- subscription ----------
  bot.callbackQuery("subscription", async (ctx) => {
    await safeAnswer(ctx);
    await ctx.reply(SUBSCRIPTION_URL);
  });

  // ---------- configs list (paginated) ----------
  bot.callbackQuery(/^configs:(\d+)$/, async (ctx) => {
    await safeAnswer(ctx);

    const page = Number(ctx.match[1]);
    const configs = await loadConfigs();

    if (!configs.length) {
      await ctx.reply("❌ No configurations are currently available.");
      return;
    }

    const { kb } = configsKeyboard(configs, page);
    await editOrReply(
      ctx,
      `Choose a configuration (${configs.length} total):`,
      kb
    );
  });

  // سازگاری با پیام‌های قدیمی که callback_data = "configs" دارند
  bot.callbackQuery("configs", async (ctx) => {
    await safeAnswer(ctx);
    const configs = await loadConfigs();
    if (!configs.length) {
      await ctx.reply("❌ No configurations are currently available.");
      return;
    }
    const { kb } = configsKeyboard(configs, 0);
    await editOrReply(
      ctx,
      `Choose a configuration (${configs.length} total):`,
      kb
    );
  });

  // ---------- copy all ----------
  bot.callbackQuery("copy_all", async (ctx) => {
    await safeAnswer(ctx, "Sending all configurations...");

    const configs = await loadConfigs();
    if (!configs.length) {
      await ctx.reply("❌ No configurations are currently available.");
      return;
    }

    const all = configs.join("\n");
    const html = `<pre>${escapeHtml(all)}</pre>`;

    // طول بعد از escape بررسی می‌شود (حد تلگرام: ۴۰۹۶)
    if (html.length <= 4000) {
      await ctx.reply(html, { parse_mode: "HTML" });
    } else {
      await ctx.replyWithDocument(
        new InputFile(new TextEncoder().encode(all), "sublink.txt"),
        { caption: `📋 All configurations (${configs.length})` }
      );
    }
  });

  // ---------- single config ----------
  bot.callbackQuery(/^config:(\d+)$/, async (ctx) => {
    await safeAnswer(ctx);

    const index = Number(ctx.match[1]);
    const configs = await loadConfigs();

    if (index < 0 || index >= configs.length) {
      await ctx.reply("❌ This configuration no longer exists.");
      return;
    }

    // داخل <code> تا با یک تپ کپی شود
    await ctx.reply(`<code>${escapeHtml(configs[index])}</code>`, {
      parse_mode: "HTML",
    });
  });

  // ---------- back ----------
  bot.callbackQuery("main", async (ctx) => {
    await safeAnswer(ctx);
    await editOrReply(ctx, "Choose what you need:", mainKeyboard());
  });

  // ---------- inline mode ----------
  bot.on("inline_query", async (ctx) => {
    try {
      const configs = await loadConfigs();
      const results: any[] = [];
      const search = ctx.inlineQuery.query.trim().toLowerCase();

      if (!search || search === "all" || search === "*") {
        const allConfigs = configs.join("\n");
        if (allConfigs && allConfigs.length <= 4096) {
          results.push({
            type: "article",
            id: "all_configs",
            title: "📋 All Configs",
            description: `${configs.length} configurations`,
            input_message_content: { message_text: allConfigs },
          });
        }
      }

      for (let index = 0; index < configs.length; index++) {
        const config = configs[index];
        if (search && search !== "all" && search !== "*") {
          if (!config.toLowerCase().includes(search)) continue;
        }
        if (config.length > 4096) continue;

        results.push({
          type: "article",
          id: `config_${index}`,
          title: `⚡ Config ${String(index + 1).padStart(3, "0")}`,
          description:
            config.length > 80 ? config.slice(0, 80) + "..." : config,
          input_message_content: { message_text: config },
        });

        if (results.length >= 50) break;
      }

      await ctx.answerInlineQuery(results, {
        cache_time: 5,
        is_personal: true,
      });
    } catch (error) {
      console.error("INLINE ERROR:", error);
      try {
        await ctx.answerInlineQuery([], { cache_time: 1 });
      } catch {}
    }
  });
}

// ============================================================
// BOT (ساخته و init فقط یک بار در هر isolate)
// ============================================================

let botPromise: Promise<Bot> | null = null;

function getBot(env: Env): Promise<Bot> {
  if (!botPromise) {
    botPromise = (async () => {
      const bot = new Bot(env.BOT_TOKEN);
      registerHandlers(bot, env);
      await bot.init();
      return bot;
    })().catch((error) => {
      botPromise = null; // اگر شکست خورد دفعه‌ی بعد دوباره تلاش کند
      throw error;
    });
  }
  return botPromise;
}

// ============================================================
// BROADCAST
// ============================================================

async function sendWithRetry(
  bot: Bot,
  chatId: string,
  text: string,
  attempt = 0
): Promise<void> {
  try {
    await bot.api.sendMessage(chatId, text, {
      reply_markup: mainKeyboard(),
    });
  } catch (error) {
    if (
      error instanceof GrammyError &&
      error.error_code === 429 &&
      attempt < 3
    ) {
      const wait = (error.parameters?.retry_after ?? 1) * 1000 + 200;
      await sleep(wait);
      return sendWithRetry(bot, chatId, text, attempt + 1);
    }
    throw error;
  }
}

async function broadcastUpdate(env: Env): Promise<void> {
  const users = await loadUsers(env);
  if (!users.length) {
    console.log("No users to broadcast.");
    return;
  }

  // برای ارسال به init نیازی نیست
  const bot = new Bot(env.BOT_TOKEN);

  console.log(`Broadcasting update to ${users.length} users...`);

  const message =
    "🔄 Configurations updated!\n\n" +
    "New configurations are available.\n\n" +
    "Please update your Subscription.";

  for (const chatId of users) {
    try {
      await sendWithRetry(bot, chatId, message);
    } catch (error) {
      console.error(`Failed to send to ${chatId}:`, String(error));

      if (error instanceof GrammyError) {
        const d = error.description.toLowerCase();
        if (
          error.error_code === 403 ||
          d.includes("chat not found") ||
          d.includes("user is deactivated")
        ) {
          await removeUser(env, chatId);
        }
      }
    }

    await sleep(40); // ~25 پیام در ثانیه، زیر حد تلگرام
  }

  console.log("Broadcast finished.");
}

// ============================================================
// GITHUB SIGNATURE
// ============================================================

async function verifyGithubSignature(
  secret: string,
  body: string,
  header: string | null
): Promise<boolean> {
  if (!header || !header.startsWith("sha256=")) return false;

  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const sig = await crypto.subtle.sign(
    "HMAC",
    key,
    new TextEncoder().encode(body)
  );
  const expected =
    "sha256=" +
    [...new Uint8Array(sig)]
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");

  if (expected.length !== header.length) return false;
  let diff = 0;
  for (let i = 0; i < expected.length; i++) {
    diff |= expected.charCodeAt(i) ^ header.charCodeAt(i);
  }
  return diff === 0;
}

// ============================================================
// WORKER
// ============================================================

export default {
  async scheduled(
    _controller: ScheduledController,
    _env: Env,
    _ctx: ExecutionContext
  ): Promise<void> {
    // لازم نیست؛ ربات وبهوک‌محور است.
  },

  async fetch(
    request: Request,
    env: Env,
    ctx: ExecutionContext
  ): Promise<Response> {
    const url = new URL(request.url);

    // ---------------- GITHUB WEBHOOK ----------------
    if (url.pathname === "/github-update") {
      if (request.method !== "POST") {
        return new Response("Method Not Allowed", { status: 405 });
      }

      const raw = await request.text();

      if (env.GITHUB_SECRET) {
        const ok = await verifyGithubSignature(
          env.GITHUB_SECRET,
          raw,
          request.headers.get("X-Hub-Signature-256")
        );
        if (!ok) return new Response("Forbidden", { status: 403 });
      }

      try {
        const body = JSON.parse(raw) as {
          commits?: Array<{
            added?: string[];
            modified?: string[];
            removed?: string[];
          }>;
        };

        const commits = body.commits || [];

        let changed = commits.some((commit) =>
          [
            ...(commit.added || []),
            ...(commit.modified || []),
            ...(commit.removed || []),
          ].includes("crawler/sublink.txt")
        );

        // گیت‌هاب در payload حداکثر ۲۰ کامیت می‌فرستد؛ اگر پر بود محتاطانه true
        if (!changed && commits.length >= 20) changed = true;

        console.log(`GitHub webhook received. Changed: ${changed}`);

        if (changed) {
          // پاسخ سریع به گیت‌هاب، broadcast در پس‌زمینه
          ctx.waitUntil(broadcastUpdate(env));
        }

        return Response.json({ success: true, changed });
      } catch (error) {
        console.error("GITHUB WEBHOOK ERROR:", error);
        return Response.json(
          { success: false, error: "Invalid webhook payload" },
          { status: 400 }
        );
      }
    }

    // ---------------- TELEGRAM WEBHOOK ----------------
    if (url.pathname === "/telegram") {
      if (request.method !== "POST") {
        return new Response("Method Not Allowed", { status: 405 });
      }

      try {
        const bot = await getBot(env);
        const handle = webhookCallback(bot, "cloudflare-mod", {
          secretToken: env.TELEGRAM_SECRET || undefined,
        });
        return await handle(request);
      } catch (error) {
        console.error("TELEGRAM WEBHOOK ERROR:", error);
        return new Response("Error", { status: 500 });
      }
    }

    return new Response("ConfigHub bot is running.");
  },
};
