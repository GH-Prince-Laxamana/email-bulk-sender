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
    const [deletingId, setDeletingId] = useState<number | null>(null);
    const [deleteTarget, setDeleteTarget] = useState<Campaign | null>(null);

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

    async function deleteCampaign(campaign: Campaign) {
        try {
            setDeletingId(campaign.id);
            setError("");

            await api(`/api/campaigns/${campaign.id}`, {
                method: "DELETE",
            });

            await loadCampaigns();
            setDeleteTarget(null);
        } catch (err) {
            setError(
                err instanceof Error
                    ? err.message
                    : "Could not delete campaign.",
            );
        } finally {
            setDeletingId(null);
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

                <div className="flex shrink-0 gap-3">
                    <button
                        type="button"
                        onClick={onSettings}
                        className="border border-neutral-300 bg-white px-4 py-3 text-sm font-medium hover:bg-neutral-50"
                    >
                        Settings
                    </button>

                    <button
                        type="button"
                        onClick={onCreate}
                        className="border border-neutral-900 bg-neutral-900 px-4 py-3 text-sm font-medium text-white hover:bg-neutral-800"
                    >
                        New campaign
                    </button>
                </div>
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
                            <div
                                key={campaign.id}
                                className="flex items-center justify-between gap-6 border-b border-neutral-200 px-5 py-5 last:border-0 hover:bg-neutral-50"
                            >
                                <button
                                    type="button"
                                    onClick={() => onOpen(campaign)}
                                    className="min-w-0 flex-1 text-left"
                                >
                                    <h2 className="truncate font-medium">
                                        {campaign.name}
                                    </h2>

                                    <p className="mt-1 truncate text-sm text-neutral-500">
                                        {campaign.subject || "No subject"}
                                    </p>
                                    <p className="mt-2 text-xs text-neutral-500">
                                        {Object.values(campaign.counts).reduce((sum, count) => sum + count, 0)} recipients
                                        {campaign.counts.sent ? ` · ${campaign.counts.sent} sent` : ""}
                                        {campaign.counts.failed ? ` · ${campaign.counts.failed} failed` : ""}
                                        {campaign.counts.pending ? ` · ${campaign.counts.pending} pending` : ""}
                                    </p>
                                </button>

                                <div className="flex shrink-0 items-center gap-4">
                                    <span className="text-xs font-medium uppercase tracking-wide text-neutral-500">
                                        {campaign.state}
                                    </span>

                                    <button
                                        type="button"
                                        onClick={() => setDeleteTarget(campaign)}
                                        disabled={
                                            deletingId === campaign.id ||
                                            campaign.state === "running"
                                        }
                                        className="border border-neutral-300 bg-white px-3 py-2 text-xs font-medium text-neutral-700 hover:border-red-300 hover:text-red-700 disabled:cursor-not-allowed disabled:opacity-50"
                                    >
                                        {deletingId === campaign.id
                                            ? "Deleting..."
                                            : "Delete"}
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
            {deleteTarget && (
                <div className="fixed inset-0 z-20 flex items-center justify-center overflow-y-auto bg-neutral-900/30 p-4">
                    <div role="dialog" aria-modal="true" className="max-h-[calc(100vh-2rem)] w-full max-w-md overflow-y-auto border border-neutral-300 bg-white p-6 shadow-xl">
                        <h2 className="text-lg font-semibold">Delete campaign?</h2>
                        <p className="mt-2 text-sm leading-6 text-neutral-600">
                            “{deleteTarget.name}” and its recipients and attachments will be permanently removed.
                        </p>
                        <div className="mt-6 flex justify-end gap-3">
                            <button type="button" onClick={() => setDeleteTarget(null)} className="border border-neutral-300 bg-white px-4 py-3 text-sm font-medium">Cancel</button>
                            <button type="button" onClick={() => void deleteCampaign(deleteTarget)} disabled={deletingId !== null} className="border border-red-700 bg-red-700 px-4 py-3 text-sm font-medium text-white disabled:opacity-50">{deletingId === deleteTarget.id ? "Deleting..." : "Delete campaign"}</button>
                        </div>
                    </div>
                </div>
            )}
        </section>
    );
}