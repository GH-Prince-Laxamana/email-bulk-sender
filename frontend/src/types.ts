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
  counts: Record<string, number>;
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

export type RecipientPreview = {
  recipient_id: number;
  email: string;
  subject: string;
  text: string;
  html: string;
};

export type PreviewError = {
  recipient_id: number;
  email: string;
  code: string;
  message: string;
};

export type CampaignPreview = {
  state: Campaign["state"];
  clean: boolean;
  total: number;
  valid: number;
  invalid: number;
  errors: PreviewError[];
  previews: RecipientPreview[];
};

export type AttachmentRule = {
  path: string | null;
  folder: string | null;
  filename_template: string | null;
};