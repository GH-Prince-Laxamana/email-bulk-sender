import { type ChangeEvent, useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { Campaign, ImportResult, Recipient } from "../types";

type Props = {
    campaign: Campaign;
    onBack: () => void;
};

export default function Recipients({ campaign, onBack }: Props) {
    const [recipients, setRecipients] = useState<Recipient[]>([]);
    const [text, setText] = useState("");
    const [loading, setLoading] = useState(true);
    const [importing, setImporting] = useState(false);
    const [message, setMessage] = useState("");
    const fileInputRef = useRef<HTMLInputElement>(null);

    const editable =
        !campaign.locked &&
        campaign.state !== "running";

    useEffect(() => {
        void loadRecipients();
    }, [campaign.id]);

    async function loadRecipients() {
        try {
            setLoading(true);
            const data = await api<Recipient[]>(
                `/api/campaigns/${campaign.id}/recipients`,
            );
            setRecipients(data);
        } catch (error) {
            setMessage(
                error instanceof Error
                    ? error.message
                    : "Could not load recipients.",
            );
        } finally {
            setLoading(false);
        }
    }

    async function importRecipients() {
        if (!text.trim()) {
            setMessage("Paste recipient data first.");
            return;
        }

        try {
            setImporting(true);
            setMessage("");

            const result = await api<ImportResult>(
                `/api/campaigns/${campaign.id}/recipients/import`,
                {
                    method: "POST",
                    body: JSON.stringify({ text }),
                },
            );

            setText("");
            await loadRecipients();

            setMessage(
                `${result.inserted} recipient${result.inserted === 1 ? "" : "s"
                } imported.${result.ignored_duplicates
                    ? ` ${result.ignored_duplicates} duplicate${result.ignored_duplicates === 1 ? "" : "s"
                    } ignored.`
                    : ""
                }`,
            );
        } catch (error) {
            setMessage(
                error instanceof Error
                    ? error.message
                    : "Could not import recipients.",
            );
        } finally {
            setImporting(false);
        }
    }

    async function handleFile(event: ChangeEvent<HTMLInputElement>) {
        const file = event.target.files?.[0];

        if (!file) {
            return;
        }

        try {
            setText(await file.text());
            setMessage(`Loaded ${file.name}. Review the data, then import it.`);
        } catch {
            setMessage("Could not read the selected file.");
        } finally {
            event.target.value = "";
        }
    }

    return (
        <section className="mx-auto w-full max-w-5xl px-4 py-10 sm:px-6">
            <button
                type="button"
                onClick={onBack}
                className="text-sm text-neutral-500 hover:text-neutral-900"
            >
                ← Back to campaign
            </button>

            <header className="mt-8">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-neutral-500">
                    Recipients
                </p>

                <div className="mt-3 flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
                    <div>
                        <h1 className="text-4xl font-semibold tracking-tight">
                            {campaign.name}
                        </h1>

                        <p className="mt-3 text-sm text-neutral-600">
                            {recipients.length} recipient
                            {recipients.length === 1 ? "" : "s"}
                        </p>
                    </div>
                </div>
            </header>

            {editable && (
                <section className="mt-10 border border-neutral-300 bg-white p-6 sm:p-8">
                    <div>
                        <h2 className="text-base font-semibold">
                            Import recipients
                        </h2>

                        <p className="mt-2 text-sm leading-6 text-neutral-500">
                            Paste CSV or tab-separated data. The <code>email</code> column
                            is required. Other columns become template variables.
                        </p>
                    </div>

                    <textarea
                        value={text}
                        onChange={(event) => setText(event.target.value)}
                        rows={10}
                        placeholder={
                            "email,Name,Company\nalice@example.com,Alice,Acme\nbob@example.com,Bob,Globex"
                        }
                        className="mt-6 w-full resize-y border border-neutral-300 px-3 py-3 font-mono text-sm leading-6 outline-none focus:border-neutral-900"
                    />

                    <div className="mt-4 flex flex-col gap-3 sm:flex-row">
                        <button
                            type="button"
                            onClick={importRecipients}
                            disabled={importing || !text.trim()}
                            className="border border-neutral-900 bg-neutral-900 px-4 py-3 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            {importing ? "Importing..." : "Import recipients"}
                        </button>

                        <button
                            type="button"
                            onClick={() => fileInputRef.current?.click()}
                            disabled={importing}
                            className="border border-neutral-300 bg-white px-4 py-3 text-sm font-medium text-neutral-900 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            Choose CSV file
                        </button>

                        <input
                            ref={fileInputRef}
                            type="file"
                            accept=".csv,text/csv"
                            className="hidden"
                            onChange={handleFile}
                        />
                    </div>
                </section>
            )}

            {message && (
                <p
                    role="status"
                    className="mt-5 border-t border-neutral-200 pt-4 text-sm text-neutral-600"
                >
                    {message}
                </p>
            )}

            <section className="mt-10">
                {loading ? (
                    <p className="text-sm text-neutral-500">
                        Loading recipients...
                    </p>
                ) : recipients.length === 0 ? (
                    <div className="border border-dashed border-neutral-300 bg-white p-10 text-center">
                        <h2 className="text-lg font-medium">
                            No recipients yet
                        </h2>

                        <p className="mt-2 text-sm text-neutral-500">
                            Import a CSV or paste recipient data above.
                        </p>
                    </div>
                ) : (
                    <div className="overflow-x-auto border-y border-neutral-200 bg-white">
                        <table className="w-full min-w-170 border-collapse text-left">
                            <thead>
                                <tr className="border-b border-neutral-200 text-xs uppercase tracking-wide text-neutral-500">
                                    <th className="px-5 py-4 font-medium">Email</th>
                                    <th className="px-5 py-4 font-medium">Variables</th>
                                    <th className="px-5 py-4 font-medium">Status</th>
                                </tr>
                            </thead>

                            <tbody>
                                {recipients.map((recipient) => (
                                    <tr
                                        key={recipient.id}
                                        className="border-b border-neutral-100 last:border-0"
                                    >
                                        <td className="px-5 py-4 text-sm">
                                            {recipient.email}
                                        </td>

                                        <td className="px-5 py-4 text-sm text-neutral-500">
                                            {Object.keys(recipient.values).length}
                                        </td>

                                        <td className="px-5 py-4 text-xs font-medium uppercase tracking-wide text-neutral-500">
                                            {recipient.status}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </section>
        </section>
    );
}