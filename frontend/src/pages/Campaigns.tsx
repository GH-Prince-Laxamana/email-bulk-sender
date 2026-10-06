import { useEffect, useState } from "react";
import { api } from "../api";
import type { Campaign } from "../types";

type Props = {
    onCreate: () => void;
    onOpen: (campaign: Campaign) => void;
    onSettings: () => void;
};

export default function Campaigns({
    onCreate,
    onOpen,
    onSettings,
}: Props) {
    const [campaigns, setCampaigns] = useState<Campaign[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    useEffect(() => {
        void loadCampaigns();
    }, []);

    async function loadCampaigns() {
        try {
            setLoading(true);
            setError("");

            const data = await api<Campaign[]>("/api/campaigns");
            setCampaigns(data);
        } catch (err) {
            setError(
                err instanceof Error ? err.message : "Could not load campaigns.",
            );
        } finally {
            setLoading(false);
        }
    }

    return (
        <section className="mx-auto w-full max-w-5xl px-4 py-10 sm:px-6">
            <header className="flex items-end justify-between gap-6">
                <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.14em] text-neutral-500">
                        BulkMailer
                    </p>

                    <h1 className="mt-3 text-4xl font-semibold tracking-tight">
                        Campaigns
                    </h1>

                    <p className="mt-3 text-sm leading-6 text-neutral-600">
                        Create, review, and send email campaigns.
                    </p>
                </div>

                <button
                    type="button"
                    onClick={onCreate}
                    className="border border-neutral-900 bg-neutral-900 px-4 py-3 text-sm font-medium text-white hover:bg-neutral-800"
                >
                    New campaign
                </button>

                <button
                    type="button"
                    onClick={onSettings}
                    className="border border-neutral-300 bg-white px-4 py-3 text-sm font-medium hover:bg-neutral-50"
                >
                    Settings
                </button>
            </header>

            <div className="mt-10">
                {loading ? (
                    <p className="text-sm text-neutral-500">Loading campaigns...</p>
                ) : error ? (
                    <div className="border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                        {error}
                    </div>
                ) : campaigns.length === 0 ? (
                    <div className="border border-dashed border-neutral-300 bg-white p-10 text-center">
                        <h2 className="text-lg font-medium">No campaigns yet</h2>
                        <p className="mt-2 text-sm text-neutral-500">
                            Create your first campaign to get started.
                        </p>

                        <button
                            type="button"
                            onClick={onCreate}
                            className="mt-5 border border-neutral-900 bg-neutral-900 px-4 py-3 text-sm font-medium text-white"
                        >
                            Create campaign
                        </button>
                    </div>
                ) : (
                    <div className="divide-y divide-neutral-200 border-y border-neutral-200 bg-white">
                        {campaigns.map((campaign) => (
                            <button
                                key={campaign.id}
                                type="button"
                                onClick={() => onOpen(campaign)}
                                className="flex w-full items-center justify-between gap-6 px-5 py-5 text-left hover:bg-neutral-50"
                            >
                                <div className="min-w-0">
                                    <h2 className="truncate font-medium">
                                        {campaign.name}
                                    </h2>

                                    <p className="mt-1 truncate text-sm text-neutral-500">
                                        {campaign.subject || "No subject"}
                                    </p>
                                </div>

                                <div className="shrink-0 text-xs font-medium uppercase tracking-wide text-neutral-500">
                                    {campaign.state}
                                </div>
                            </button>
                        ))}
                    </div>
                )}
            </div>
        </section>
    );
}