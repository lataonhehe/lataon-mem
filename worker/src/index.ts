import { Api } from "grammy";
import type { Update } from "grammy/types";
import { BOT_COMMANDS } from "./bot";
import { getNotesAfterId } from "./db/queries";
import { upsertNoteVectors } from "./db/vectors";

export { UserSession } from "./session";

const WEBHOOK_PATH = "/tg";
const REINDEX_PAGE_SIZE = 50;

function isAdmin(req: Request, env: Env): boolean {
  return !!env.ADMIN_TOKEN && req.headers.get("Authorization") === `Bearer ${env.ADMIN_TOKEN}`;
}

export default {
  async fetch(req, env): Promise<Response> {
    const url = new URL(req.url);

    // Telegram webhook
    if (req.method === "POST" && url.pathname === WEBHOOK_PATH) {
      if (req.headers.get("X-Telegram-Bot-Api-Secret-Token") !== env.WEBHOOK_SECRET) {
        return new Response("Unauthorized", { status: 401 });
      }
      const update = await req.json<Update>();
      const userId = update.message?.from?.id;
      if (userId) {
        const stub = env.USER_SESSION.get(env.USER_SESSION.idFromName(String(userId)));
        await stub.handleUpdate(update);
      }
      return new Response("ok");
    }

    // Đăng ký webhook + menu command: POST /admin/setup
    if (req.method === "POST" && url.pathname === "/admin/setup") {
      if (!isAdmin(req, env)) return new Response("Unauthorized", { status: 401 });
      const api = new Api(env.TELEGRAM_TOKEN);
      await api.setWebhook(`${url.origin}${WEBHOOK_PATH}`, {
        secret_token: env.WEBHOOK_SECRET,
        allowed_updates: ["message"],
        drop_pending_updates: false,
      });
      await api.setMyCommands(BOT_COMMANDS);
      return Response.json(await api.getWebhookInfo());
    }

    // Embed lại toàn bộ ghi chú vào Vectorize, từng trang: POST /admin/reindex?after=<id>
    if (req.method === "POST" && url.pathname === "/admin/reindex") {
      if (!isAdmin(req, env)) return new Response("Unauthorized", { status: 401 });
      const after = Number(url.searchParams.get("after") ?? 0);
      const notes = await getNotesAfterId(env.DB, after, REINDEX_PAGE_SIZE);
      await upsertNoteVectors(env, notes);
      const next = notes.length === REINDEX_PAGE_SIZE ? notes[notes.length - 1].id : null;
      return Response.json({ processed: notes.length, next });
    }

    return new Response("Not found", { status: 404 });
  },
} satisfies ExportedHandler<Env>;
