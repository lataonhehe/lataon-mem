export type Mode = "idle" | "socratic" | "deep_dive" | "quiz" | "conflict";

export interface ChatMsg {
  role: "user" | "assistant";
  content: string;
}

export interface Note {
  id: number;
  userId: number;
  content: string;
  category: string;
  tags: string[];
  summary: string;
  createdAt: string; // UTC 'YYYY-MM-DD HH:MM:SS'
}

export const SOCRATIC_MAX_TURNS = 3;
export const DEEP_MAX_TURNS = 5;
export const MAX_SUMMARY_LEN = 120;
export const VALID_CATEGORIES = [
  "it", "knowledge", "diary", "book", "idea", "health", "finance", "other",
] as const;

export interface UserState {
  mode: Mode;
  socraticEnabled: boolean; // user có thể tắt Socratic

  // ghi chú vừa lưu
  lastNoteId: number | null;
  lastNoteContent: string | null;
  lastCategory: string | null;

  // Socratic
  socraticTurns: number;
  socraticHistory: ChatMsg[];

  // Deep dive
  deepTopic: string | null;
  deepHistory: ChatMsg[];
  deepTurns: number;

  // Quiz
  quizNote: Note | null;

  // Nháp khi conflict
  pendingNoteText: string | null;
  prevMode: Mode | null;
}

export function newState(socraticEnabled = true): UserState {
  return {
    mode: "idle",
    socraticEnabled,
    lastNoteId: null,
    lastNoteContent: null,
    lastCategory: null,
    socraticTurns: 0,
    socraticHistory: [],
    deepTopic: null,
    deepHistory: [],
    deepTurns: 0,
    quizNote: null,
    pendingNoteText: null,
    prevMode: null,
  };
}
