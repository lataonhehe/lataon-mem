import { DurableObject } from "cloudflare:workers";
import type { Bot } from "grammy";
import type { Update } from "grammy/types";
import { createBot, type StateHolder } from "./bot";
import { newState, type UserState } from "./types";

const STATE_KEY = "state";

/**
 * Mỗi user Telegram có 1 instance (idFromName(userId)).
 * Update của cùng 1 user được xử lý tuần tự, state lưu trong storage của DO.
 */
export class UserSession extends DurableObject<Env> implements StateHolder {
  state: UserState = newState();
  private bot: Bot;
  private queue: Promise<void> = Promise.resolve();

  constructor(ctx: DurableObjectState, env: Env) {
    super(ctx, env);
    this.bot = createBot(env, this);
    ctx.blockConcurrencyWhile(async () => {
      const saved = await ctx.storage.get<UserState>(STATE_KEY);
      if (saved) this.state = { ...newState(), ...saved };
    });
  }

  /** Xếp hàng update — tránh 2 tin nhắn liên tiếp cùng sửa state khi đang chờ LLM. */
  handleUpdate(update: Update): Promise<void> {
    const run = this.queue.then(() => this.process(update));
    this.queue = run.catch(() => {});
    return run;
  }

  private async process(update: Update): Promise<void> {
    try {
      if (!this.bot.isInited()) await this.bot.init();
      await this.bot.handleUpdate(update);
    } catch (e) {
      // Nuốt lỗi để Worker vẫn trả 200 — tránh Telegram gửi lại update mãi
      console.error(`Lỗi xử lý update ${update.update_id}:`, e);
      const chatId = update.message?.chat.id;
      if (chatId) {
        await this.bot.api
          .sendMessage(chatId, "⚠️ Có lỗi xảy ra, thử lại sau nhé.")
          .catch(() => {});
      }
    } finally {
      await this.ctx.storage.put(STATE_KEY, this.state);
    }
  }
}
