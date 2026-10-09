import type { ChatMsg } from "../types";
import { VALID_CATEGORIES } from "../types";
import {
  CLASSIFIER_SYSTEM,
  SOCRATIC_SYSTEM,
  SOCRATIC_CONTINUE_SYSTEM,
  DEEP_DIVE_SYSTEM,
  QUIZ_SYSTEM,
  SUMMARY_SYSTEM,
} from "./prompts";

const OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1";

async function ask(env: Env, system: string, messages: ChatMsg[], maxTokens = 128): Promise<string> {
  const res = await fetch(`${OPENROUTER_BASE_URL}/chat/completions`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.OPENROUTER_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: env.MODEL,
      max_tokens: maxTokens,
      messages: [{ role: "system", content: system }, ...messages],
    }),
  });
  if (!res.ok) {
    throw new Error(`OpenRouter ${res.status}: ${await res.text()}`);
  }
  const data = await res.json<{ choices: { message: { content: string | null } }[] }>();
  return (data.choices[0]?.message?.content ?? "").trim();
}

export interface Classification {
  category: string;
  tags: string[];
  summary: string;
}

/** Phân loại ghi chú, trả về {category, tags, summary}. */
export async function classifyNote(env: Env, content: string): Promise<Classification> {
  const raw = await ask(env, CLASSIFIER_SYSTEM, [{ role: "user", content }], 256);
  console.log(`Classifier raw response: ${raw}`);

  // Strip markdown code fences nếu model trả về ```json ... ```
  const cleaned = raw.replace(/^```(?:json)?\s*|\s*```$/gm, "").trim();

  try {
    const result = JSON.parse(cleaned) as Partial<Classification>;
    let category = result.category ?? "other";
    if (!(VALID_CATEGORIES as readonly string[]).includes(category)) {
      console.warn(`Invalid category '${category}', defaulting to 'other'`);
      category = "other";
    }
    return {
      category,
      tags: Array.isArray(result.tags) ? result.tags.map(String) : [],
      summary: result.summary ?? content.slice(0, 80),
    };
  } catch (e) {
    console.error(`JSON parse error: ${e} | raw: ${raw}`);
    return { category: "other", tags: [], summary: content.slice(0, 80) };
  }
}

/** Câu hỏi Socratic đầu tiên sau khi lưu ghi chú. */
export function generateFirstQuestion(env: Env, noteContent: string, category: string) {
  return ask(env, SOCRATIC_SYSTEM, [{ role: "user", content: `[${category}] ${noteContent}` }]);
}

/** Tiếp tục Socratic — history đã gồm câu trả lời mới nhất của user. */
export function continueSocratic(env: Env, history: ChatMsg[]) {
  return ask(env, SOCRATIC_CONTINUE_SYSTEM, history);
}

/** Câu hỏi đầu tiên cho /deep. */
export function startDeepDive(env: Env, topic: string) {
  return ask(env, DEEP_DIVE_SYSTEM, [{ role: "user", content: topic }]);
}

/** Tiếp tục /deep — history đã gồm câu trả lời mới nhất của user. */
export function continueDeepDive(env: Env, history: ChatMsg[]) {
  return ask(env, DEEP_DIVE_SYSTEM, history);
}

export function generateQuiz(env: Env, noteContent: string, category: string) {
  return ask(env, QUIZ_SYSTEM, [{ role: "user", content: `[${category}] ${noteContent}` }]);
}

export function generateSummary(env: Env, notesText: string) {
  return ask(env, SUMMARY_SYSTEM, [{ role: "user", content: notesText }], 512);
}
