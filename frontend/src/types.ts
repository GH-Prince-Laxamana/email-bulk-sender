export type SenderSettings = {
  email: string | null;
  has_app_password: boolean;
};

export type ApiStatus = "idle" | "saving" | "testing" | "sending-test";

export type Campaign = {
  id: number;
  name: string;
  subject: string;
  body_html: string;
  variables: string[];
  state: "draft" | "previewed" | "running" | "paused" | "finished";
  locked: boolean;
  halt_reason: string | null;
};

export type RecipientStatus =
  | "pending"
  | "sending"
  | "sent"
  | "failed"
  | "interrupted";

export type Recipient = {
  id: number;
  email: string;
  values: Record<string, string>;
  status: RecipientStatus;
  error_code: string | null;
  error_message: string | null;
  attempts: number;
  sent_at: string | null;
  position: number;
};

export type ImportResult = {
  inserted: number;
  ignored_duplicates: number;
  total_rows: number;
};