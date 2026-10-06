import { useState } from "react";
import { api } from "../api";
import type { Campaign, CampaignPreview } from "../types";

type Props = {
    campaign: Campaign;
    onBack: () => void;
    onPreviewed: (campaign: Campaign, preview: CampaignPreview) => void;
    onRun: (campaign: Campaign) => void;
};

export default function Preview({
    campaign,
    onBack,
    onPreviewed,
    onRun,
}: Props) {
    const [preview, setPreview] = useState<CampaignPreview | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    async function runPreview() {
        try {
            setLoading(true);
            setError("");

            const data = await api<CampaignPreview>(
                `/api/campaigns/${campaign.id}/preview`,
                {
                    method: "POST",
                },
            );

            setPreview(data);

            onPreviewed(
                {
                    ...campaign,
                    state: data.state,
                },
                data,
            );
        } catch (err) {
            setError(
                err instanceof Error
                    ? err.message
                    : "Could not generate preview.",
            );
        } finally {
            setLoading(false);
        }
    }

    return (
        <section className="mx-auto w-full max-w-6xl px-4 py-10 sm:px-6">
            <button
                type="button"
                onClick={onBack}
                className="text-sm text-neutral-500 hover:text-neutral-900"
            >
                ← Back to recipients
            </button>

            <header className="mt-8">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-neutral-500">
                    Preview
                </p>

                <h1 className="mt-3 text-4xl font-semibold tracking-tight">
                    {campaign.name}
                </h1>

                <p className="mt-3 max-w-2xl text-sm leading-6 text-neutral-600">
                    Preview uses the same rendering and message-building pipeline used
                    when the campaign is actually sent.
                </p>
            </header>

            {!preview && (
                <div className="mt-10 border border-neutral-300 bg-white p-6 sm:p-8">
                    <p className="text-sm text-neutral-600">
                        Generate a clean preview before starting the campaign.
                    </p>

                    <button
                        type="button"
                        onClick={runPreview}
                        disabled={loading}
                        className="mt-6 border border-neutral-900 bg-neutral-900 px-4 py-3 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        {loading ? "Generating preview..." : "Generate preview"}
                    </button>
                </div>
            )}

            {error && (
                <div className="mt-6 border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                    {error}
                </div>
            )}

            {preview && (
                <>
                    <div className="mt-10 border border-neutral-300 bg-white p-6 sm:p-8">
                        <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
                            <div>
                                <p className="text-sm font-medium">
                                    {preview.clean
                                        ? "Preview passed"
                                        : "Preview needs attention"}
                                </p>

                                <p className="mt-2 text-sm text-neutral-500">
                                    {preview.valid} valid
                                    {preview.invalid > 0 &&
                                        ` · ${preview.invalid} invalid`}
                                    {` · ${preview.total} pending recipient${preview.total === 1 ? "" : "s"
                                        }`}
                                </p>
                            </div>

                            <button
                                type="button"
                                onClick={runPreview}
                                disabled={loading}
                                className="border border-neutral-300 bg-white px-4 py-3 text-sm font-medium hover:border-neutral-900 disabled:opacity-50"
                            >
                                {loading ? "Refreshing..." : "Refresh preview"}
                            </button>

                            <button
                                type="button"
                                onClick={() => onRun(campaign)}
                                disabled={loading || !preview.clean}
                                className="border border-neutral-900 bg-neutral-900 px-4 py-3 text-sm font-medium text-white hover:bg-neutral-800 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                                Start campaign
                            </button>
                        </div>

                        {preview.errors.length > 0 && (
                            <div className="mt-8 border-t border-neutral-200 pt-6">
                                <h2 className="text-sm font-semibold">
                                    Problems
                                </h2>

                                <div className="mt-4 divide-y divide-neutral-200 border-y border-neutral-200">
                                    {preview.errors.map((item) => (
                                        <div
                                            key={`${item.recipient_id}-${item.code}`}
                                            className="py-4"
                                        >
                                            <p className="text-sm font-medium">
                                                {item.email}
                                            </p>

                                            <p className="mt-1 text-xs uppercase tracking-wide text-neutral-500">
                                                {item.code}
                                            </p>

                                            <p className="mt-2 text-sm text-neutral-600">
                                                {item.message}
                                            </p>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>

                    {preview.previews.length > 0 && (
                        <div className="mt-10 space-y-6">
                            {preview.previews.map((item) => (
                                <article
                                    key={item.recipient_id}
                                    className="border border-neutral-300 bg-white"
                                >
                                    <header className="border-b border-neutral-200 px-5 py-4">
                                        <p className="text-sm font-medium">
                                            {item.email}
                                        </p>

                                        <p className="mt-1 text-xs text-neutral-500">
                                            {item.subject || "No subject"}
                                        </p>
                                    </header>

                                    <div className="grid lg:grid-cols-2">
                                        <div className="border-b border-neutral-200 p-5 lg:border-b-0 lg:border-r">
                                            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-neutral-500">
                                                Text
                                            </p>

                                            <pre className="whitespace-pre-wrap font-sans text-sm leading-6 text-neutral-700">
                                                {item.text}
                                            </pre>
                                        </div>

                                        <div className="p-5">
                                            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-neutral-500">
                                                HTML
                                            </p>

                                            <iframe
                                                title={`Preview for ${item.email}`}
                                                srcDoc={item.html}
                                                sandbox=""
                                                className="h-80 w-full border border-neutral-200 bg-white"
                                            />
                                        </div>
                                    </div>
                                </article>
                            ))}
                        </div>
                    )}
                </>
            )}
        </section>
    );
}