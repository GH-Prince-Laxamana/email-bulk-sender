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

