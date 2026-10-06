import { useState } from "react";
import type { FormEvent } from "react";
import { api } from "../api";
import type { Campaign } from "../types";

type Props = {
    campaign?: Campaign;
    onSaved: (campaign: Campaign) => void;
    onBack: () => void;
    onRecipients: (campaign: Campaign) => void;
};

export default function CampaignEditor({
    campaign,
    onSaved,
    onBack,
    onRecipients,
}: Props) {
    const [name, setName] = useState(campaign?.name ?? "");
    const [subject, setSubject] = useState(campaign?.subject ?? "");
    const [bodyHtml, setBodyHtml] = useState(campaign?.body_html ?? "");
    const [variables, setVariables] = useState(
        campaign?.variables.join(", ") ?? "",
    );
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState("");

    async function handleSubmit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();

        setSaving(true);
        setError("");

        const variableList = variables
            .split(",")
            .map((value) => value.trim())
            .filter(Boolean);

        try {
            const saved = campaign
                ? await api<Campaign>(`/api/campaigns/${campaign.id}`, {
                    method: "PATCH",
                    body: JSON.stringify({
                        name,
                        subject,
                        body_html: bodyHtml,
                        variables: variableList,
                    }),
                })
                : await api<Campaign>("/api/campaigns", {
                    method: "POST",
                    body: JSON.stringify({
                        name,
                        subject,
                        body_html: bodyHtml,
                        variables: variableList,
                    }),
                });

            onSaved(saved);
        } catch (err) {
            setError(
                err instanceof Error ? err.message : "Could not save campaign.",
            );
        } finally {
            setSaving(false);
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
                    {campaign ? "Edit campaign" : "New campaign"}
                </p>

                <h1 className="mt-3 text-4xl font-semibold tracking-tight">
                    {campaign ? campaign.name : "Create campaign"}
                </h1>
            </header>

            <form
                onSubmit={handleSubmit}
                className="mt-10 space-y-6 border border-neutral-300 bg-white p-6 sm:p-8"
            >
                <div>
                    <label
                        htmlFor="campaign-name"
                        className="mb-2 block text-sm font-medium"
                    >
                        Campaign name
                    </label>

                    <input
                        id="campaign-name"
                        value={name}
                        onChange={(event) => setName(event.target.value)}
                        required
                        className="w-full border border-neutral-300 px-3 py-3 text-sm outline-none focus:border-neutral-900"
                    />
                </div>

                <div>
                    <label
                        htmlFor="campaign-subject"
                        className="mb-2 block text-sm font-medium"
                    >
                        Subject
                    </label>

                    <input
                        id="campaign-subject"
                        value={subject}
                        onChange={(event) => setSubject(event.target.value)}
                        className="w-full border border-neutral-300 px-3 py-3 text-sm outline-none focus:border-neutral-900"
                        placeholder="Hello {{Name}}"
                    />
                </div>

                <div>
                    <label
                        htmlFor="campaign-body"
                        className="mb-2 block text-sm font-medium"
                    >
                        HTML body
                    </label>

                    <textarea
                        id="campaign-body"
                        value={bodyHtml}
                        onChange={(event) => setBodyHtml(event.target.value)}
                        rows={14}
                        className="w-full resize-y border border-neutral-300 px-3 py-3 font-mono text-sm leading-6 outline-none focus:border-neutral-900"
                        placeholder="<p>Hello {{Name|there}}</p>"
                    />
                </div>

                <div>
                    <label
                        htmlFor="campaign-variables"
                        className="mb-2 block text-sm font-medium"
                    >
                        Variables
                    </label>

                    <input
                        id="campaign-variables"
                        value={variables}
                        onChange={(event) => setVariables(event.target.value)}
                        className="w-full border border-neutral-300 px-3 py-3 text-sm outline-none focus:border-neutral-900"
                        placeholder="Name, Company, Invoice Number"
                    />

                    <p className="mt-2 text-xs text-neutral-500">
                        Separate variable names with commas.
                    </p>
                </div>

                {error && (
                    <div className="border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                        {error}
                    </div>
                )}

                <div className="flex gap-3 border-t border-neutral-200 pt-6">
                    <button
                        type="submit"
                        disabled={saving}
                        className="border border-neutral-900 bg-neutral-900 px-4 py-3 text-sm font-medium text-white disabled:opacity-50"
                    >
                        {saving ? "Saving..." : "Save campaign"}
                    </button>

                    {campaign && (
                        <button
                            type="button"
                            onClick={() => onRecipients(campaign)}
                            className="border border-neutral-300 bg-white px-4 py-3 text-sm font-medium"
                        >
                            Recipients
                        </button>
                    )}

                    <button
                        type="button"
                        onClick={onBack}
                        className="border border-neutral-300 bg-white px-4 py-3 text-sm font-medium"
                    >
                        Cancel
                    </button>
                </div>
            </form>
        </section>
    );
}