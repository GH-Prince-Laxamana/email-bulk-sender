import { useEffect, useState } from "react";
import { api } from "../api";
import type { SenderSettings } from "../types";

type Props = {
    onBack: () => void;
};

export default function Settings({ onBack }: Props) {
    const [email, setEmail] = useState("");
    const [appPassword, setAppPassword] = useState("");
    const [hasAppPassword, setHasAppPassword] = useState(false);

    const [saving, setSaving] = useState(false);
    const [testing, setTesting] = useState(false);
    const [sendingTest, setSendingTest] = useState(false);

    const [message, setMessage] = useState("");
    const [error, setError] = useState("");

    useEffect(() => {
        void loadSettings();
    }, []);

    async function loadSettings() {
        try {
            const data = await api<SenderSettings>(
                "/api/settings/sender",
            );

            setEmail(data.email ?? "");
            setHasAppPassword(data.has_app_password);
        } catch (err) {
            setError(
                err instanceof Error
                    ? err.message
                    : "Could not load settings.",
            );
        }
    }

    async function handleSave() {
        setSaving(true);
        setMessage("");
        setError("");

        try {
            const data = await api<SenderSettings>(
                "/api/settings/sender",
                {
                    method: "PUT",
                    body: JSON.stringify({
                        email,
                        app_password: appPassword,
                    }),
                },
            );

            setHasAppPassword(data.has_app_password);
            setAppPassword("");
            setMessage("Sender settings saved.");
        } catch (err) {
            setError(
                err instanceof Error
                    ? err.message
                    : "Could not save settings.",
            );
        } finally {
            setSaving(false);
        }
    }

    async function handleTestConnection() {
        setTesting(true);
        setMessage("");
        setError("");

        try {
            await api("/api/settings/sender/test", {
                method: "POST",
            });

            setMessage("Connection successful.");
        } catch (err) {
            setError(
                err instanceof Error
                    ? err.message
                    : "Connection test failed.",
            );
        } finally {
            setTesting(false);
        }
    }

    async function handleSendTest() {
        setSendingTest(true);
        setMessage("");
        setError("");

        try {
            await api("/api/settings/sender/test-send", {
                method: "POST",
            });

            setMessage("Test email sent.");
        } catch (err) {
            setError(
                err instanceof Error
                    ? err.message
                    : "Could not send test email.",
            );
        } finally {
            setSendingTest(false);
        }
    }

    return (
        <section className="mx-auto w-full max-w-3xl px-4 py-10 sm:px-6">
            <button
                type="button"
                onClick={onBack}
                className="text-sm text-neutral-500 hover:text-neutral-900"
            >
                ← Back to campaigns
            </button>

            <header className="mt-8">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-neutral-500">
                    BulkMailer
                </p>

                <h1 className="mt-3 text-4xl font-semibold tracking-tight">
                    Settings
                </h1>

                <p className="mt-3 text-sm leading-6 text-neutral-600">
                    Configure the sender account used for campaigns.
                </p>
            </header>

            <div className="mt-10 space-y-6">
                <div className="border border-neutral-300 bg-white p-6 sm:p-8">
                    <h2 className="text-lg font-medium">
                        Sender account
                    </h2>

                    <p className="mt-2 text-sm leading-6 text-neutral-500">
                        BulkMailer uses Gmail SMTP with an app password.
                        Your password is never displayed after saving.
                    </p>

                    <div className="mt-6 space-y-5">
                        <div>
                            <label
                                htmlFor="sender-email"
                                className="mb-2 block text-sm font-medium"
                            >
                                Sender email
                            </label>

                            <input
                                id="sender-email"
                                type="email"
                                value={email}
                                onChange={(event) =>
                                    setEmail(event.target.value)
                                }
                                placeholder="you@gmail.com"
                                className="w-full border border-neutral-300 px-3 py-3 text-sm outline-none focus:border-neutral-900"
                            />
                        </div>

                        <div>
                            <label
                                htmlFor="app-password"
                                className="mb-2 block text-sm font-medium"
                            >
                                Gmail app password
                            </label>

                            <input
                                id="app-password"
                                type="password"
                                value={appPassword}
                                onChange={(event) =>
                                    setAppPassword(event.target.value)
                                }
                                placeholder={
                                    hasAppPassword
                                        ? "Saved. Enter a new one to replace it."
                                        : "Enter your app password"
                                }
                                className="w-full border border-neutral-300 px-3 py-3 text-sm outline-none focus:border-neutral-900"
                            />
                        </div>
                    </div>

                    {message && (
                        <div className="mt-6 border border-neutral-200 bg-neutral-50 p-4 text-sm text-neutral-700">
                            {message}
                        </div>
                    )}

                    {error && (
                        <div className="mt-6 border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                            {error}
                        </div>
                    )}

                    <div className="mt-6 flex flex-wrap gap-3 border-t border-neutral-200 pt-6">
                        <button
                            type="button"
                            onClick={() => void handleSave()}
                            disabled={saving}
                            className="border border-neutral-900 bg-neutral-900 px-4 py-3 text-sm font-medium text-white disabled:opacity-50"
                        >
                            {saving ? "Saving..." : "Save settings"}
                        </button>

                        <button
                            type="button"
                            onClick={() => void handleTestConnection()}
                            disabled={
                                testing ||
                                !email ||
                                !hasAppPassword
                            }
                            className="border border-neutral-300 bg-white px-4 py-3 text-sm font-medium hover:bg-neutral-50 disabled:opacity-50"
                        >
                            {testing
                                ? "Testing..."
                                : "Test connection"}
                        </button>

                        <button
                            type="button"
                            onClick={() => void handleSendTest()}
                            disabled={
                                sendingTest ||
                                !email ||
                                !hasAppPassword
                            }
                            className="border border-neutral-300 bg-white px-4 py-3 text-sm font-medium hover:bg-neutral-50 disabled:opacity-50"
                        >
                            {sendingTest
                                ? "Sending..."
                                : "Send test email"}
                        </button>
                    </div>
                </div>
            </div>
        </section>
    );
}