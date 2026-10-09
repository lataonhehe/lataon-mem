// Secrets (wrangler secret put) — `wrangler types` không sinh ra nếu thiếu .dev.vars
interface Secrets {
  TELEGRAM_TOKEN: string;
  OPENROUTER_API_KEY: string;
  WEBHOOK_SECRET: string;
  ADMIN_TOKEN: string;
}

interface Env extends Secrets {}

declare namespace Cloudflare {
  interface Env extends Secrets {}
}
