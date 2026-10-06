import { useEffect, useState } from "react";
import { api } from "../api";
import type { Campaign, Recipient } from "../types";

type RunStatus = {
    active: boolean;
    campaign_id: number | null;
    state: string | null;
    reason: string | null;
    counts: Record<string, number>;
};

type Props = {
    campaign: Campaign;
    onCampaignUpdated: (campaign: Campaign) => void;
};

export default function RunProgress({
    campaign,
    onCampaignUpdated,
}: Props) {
    const [status, setStatus] = useState<RunStatus | null>(null);
    const [starting, setStarting] = useState(false);
    const [stopping, setStopping] = useState(false);
    const [sendConfirmOpen, setSendConfirmOpen] = useState(false);
    const [error, setError] = useState("");
    const [recipients, setRecipients] = useState<Recipient[]>([]);

    async function loadStatus() {
        try {
            const data = await api<RunStatus>(
                `/api/campaigns/${campaign.id}/status`,
            );

            setStatus(data);
            setError("");
            const currentRecipients = await api<Recipient[]>(`/api/campaigns/${campaign.id}/recipients`);
            setRecipients(currentRecipients);

            const countsChanged = Object.entries(data.counts).some(
                ([key, value]) => campaign.counts[key] !== value,
            );
            if (data.state !== campaign.state || countsChanged) {
                const updatedCampaign = await api<Campaign>(`/api/campaigns/${campaign.id}`);
                onCampaignUpdated(updatedCampaign);
            }
        } catch (err) {
            setError(
                err instanceof Error
                    ? err.message
                    : "Could not load run status.",
            );
        }
    }

    useEffect(() => {
        void loadStatus();

        const interval = window.setInterval(() => {
            void loadStatus();
        }, 1000);

        return () => window.clearInterval(interval);
    }, [campaign.id, campaign.state]);

    async function startRun() {
        try {
            setStarting(true);
            setError("");

            await api(`/api/campaigns/${campaign.id}/run`, {
                method: "POST",
            });

            await loadStatus();
        } catch (err) {
            setError(
                err instanceof Error
                    ? err.message
                    : "Could not start campaign.",
            );
        } finally {
            setStarting(false);
        }
    }

    async function stopRun() {
        try {
            setStopping(true);
            setError("");

            await api(`/api/campaigns/${campaign.id}/stop`, {
                method: "POST",
            });

            await loadStatus();
        } catch (err) {
            setError(
                err instanceof Error
                    ? err.message
                    : "Could not stop campaign.",
            );
        } finally {
            setStopping(false);
        }
    }

    const counts = status?.counts ?? {};
    const sent = counts.sent ?? 0;
    const failed = counts.failed ?? 0;
    const pending = counts.pending ?? 0;
    const interrupted = counts.interrupted ?? 0;

    const canStart =
        status &&
        !status.active &&
        recipients.length > 0 &&
        (status.state === "previewed" ||
            status.state === "paused");

    const stateMessage: Record<Campaign["state"], string> = {
        draft: "Preview required before sending.",
        previewed: "Ready to send.",
        paused: campaign.halt_reason ?? "Review the remaining recipients, then resume.",
        running: "Sending in progress.",
        finished: pending > 0
            ? "Some recipients still need attention before another run."
            : "All recipients processed.",
    };

    const activity = recipients
        .filter((recipient) => recipient.status !== "pending")
        .sort((a, b) => a.position - b.position);

    function activityTime(recipient: Recipient) {
        if (recipient.sent_at) {
            return new Date(recipient.sent_at).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
            });
        }
        return "--:--:--";
    }

    return (
        <section className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6">
            <header className="border-b border-neutral-200 pb-8">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-neutral-500">
                    Campaign run
                </p>

                <h1 className="mt-3 text-4xl font-semibold tracking-tight">
                    {campaign.name}
                </h1>

                <p className={`mt-3 text-sm ${campaign.state === "running" ? "text-neutral-700" : campaign.state === "finished" ? "text-emerald-700" : campaign.state === "paused" ? "text-amber-700" : "text-neutral-600"}`}>
                    {stateMessage[campaign.state] ?? "Loading status..."}
                </p>
            </header>

            <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,1fr)_15rem]">
                <div className="order-2 border border-neutral-300 bg-white lg:order-1">
                    <div className="flex items-center justify-between border-b border-neutral-200 px-5 py-4">
                        <div>
                            <h2 className="text-sm font-semibold">
                                {campaign.state === "running" ? "Sending activity" : "Delivery activity"}
                            </h2>
                            <p className="mt-1 text-xs text-neutral-500">
                                Newest recipient updates appear here.
                            </p>
                        </div>
                        <span className="text-xs text-neutral-500">{activity.length} events</span>
                    </div>
                    <div className="max-h-120 overflow-y-auto">
                        {activity.length ? activity.map((recipient) => (
                            <div key={recipient.id} className="grid grid-cols-[5.5rem_6rem_minmax(0,1fr)] gap-3 border-b border-neutral-100 px-5 py-3 text-sm last:border-0">
                                <span className="font-mono text-xs text-neutral-500">{activityTime(recipient)}</span>
                                <span className={`text-xs font-semibold uppercase tracking-wide ${recipient.status === "sent" ? "text-emerald-700" : recipient.status === "failed" ? "text-red-700" : recipient.status === "interrupted" ? "text-amber-700" : "text-neutral-600"}`}>
                                    {recipient.status}
                                </span>
                                <div className="min-w-0">
                                    <p className="truncate">{recipient.email}</p>
                                    {recipient.error_message && <p className="mt-1 truncate text-xs text-red-700">{recipient.error_message}</p>}
                                </div>
                            </div>
                        )) : (
                            <p className="px-5 py-8 text-sm text-neutral-500">
                                No delivery activity yet. Start the campaign from Preview to begin sending.
                            </p>
                        )}
                    </div>
                </div>

                <aside className="order-1 h-fit border-l-2 border-neutral-200 pl-5 lg:order-2">
                    <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Summary</p>
                    <div className="mt-5 space-y-4">
                        {[
                            ["Sent", sent, "text-emerald-700"],
                            ["Pending", pending, "text-neutral-700"],
                            ["Failed", failed, "text-red-700"],
                            ["Interrupted", interrupted, "text-amber-700"],
                        ].map(([label, value, color]) => (
                            <div key={label as string}>
                                <p className="text-xs uppercase tracking-wide text-neutral-500">{label}</p>
                                <p className={`mt-1 text-2xl font-semibold ${color}`}>{value}</p>
                            </div>
                        ))}
                    </div>
                </aside>
            </div>

                {status?.reason && (
                    <div className="mt-6 border-t border-neutral-200 pt-5 text-sm text-neutral-600">
                        {status.reason}
                    </div>
                )}

                {error && (
                    <div className="mt-6 border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                        {error}
                    </div>
                )}

                <div className="mt-6 flex gap-3 border-t border-neutral-200 pt-6">
                    {status?.active ? (
                        <button
                            type="button"
                            onClick={() => void stopRun()}
                            disabled={stopping}
                            className="border border-neutral-900 bg-neutral-900 px-4 py-3 text-sm font-medium text-white disabled:opacity-50"
                        >
                            {stopping ? "Stopping..." : "Stop campaign"}
                        </button>
                    ) : (
                        <button
                            type="button"
                            onClick={() => setSendConfirmOpen(true)}
                            disabled={starting || !canStart}
                            className="border border-neutral-900 bg-neutral-900 px-4 py-3 text-sm font-medium text-white disabled:opacity-50"
                        >
                            {starting ? "Starting..." : "Start campaign"}
                        </button>
                    )}

                </div>
                {!recipients.length && !status?.active && (
                    <p className="mt-4 text-sm text-amber-700">
                        Add at least one recipient before starting this campaign.
                    </p>
                )}
                {sendConfirmOpen && (
                    <div className="fixed inset-0 z-30 flex items-center justify-center bg-neutral-900/30 p-4">
                        <div role="dialog" aria-modal="true" className="w-full max-w-md border border-neutral-300 bg-white p-6 shadow-xl">
                            <h2 className="text-lg font-semibold">Start campaign?</h2>
                            <p className="mt-2 text-sm leading-6 text-neutral-600">
                                Are you sure you want to send emails to the remaining recipients?
                            </p>
                            <div className="mt-6 flex justify-end gap-3">
                                <button type="button" onClick={() => setSendConfirmOpen(false)} className="border border-neutral-300 bg-white px-4 py-3 text-sm font-medium">Cancel</button>
                                <button type="button" onClick={() => { setSendConfirmOpen(false); void startRun(); }} className="border border-neutral-900 bg-neutral-900 px-4 py-3 text-sm font-medium text-white">Send emails</button>
                            </div>
                        </div>
                    </div>
                )}
        </section>
    );
}