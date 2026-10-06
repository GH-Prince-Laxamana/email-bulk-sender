import { useEffect, useState } from "react";
import { api } from "../api";
import type { Campaign } from "../types";

type RunStatus = {
    active: boolean;
    campaign_id: number | null;
    state: string | null;
    reason: string | null;
    counts: Record<string, number>;
};

type Props = {
    campaign: Campaign;
    onBack: () => void;
};

export default function RunProgress({ campaign, onBack }: Props) {
    const [status, setStatus] = useState<RunStatus | null>(null);
    const [starting, setStarting] = useState(false);
    const [stopping, setStopping] = useState(false);
    const [error, setError] = useState("");

    async function loadStatus() {
        try {
            const data = await api<RunStatus>(
                `/api/campaigns/${campaign.id}/status`,
            );

            setStatus(data);
            setError("");
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
    }, [campaign.id]);

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

            await api(`/api/campaigns/${campaign.id}/run/stop`, {
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
    const total = Object.values(counts).reduce(
        (sum, value) => sum + value,
        0,
    );

    const sent = counts.sent ?? 0;
    const failed = counts.failed ?? 0;
    const pending = counts.pending ?? 0;
    const interrupted = counts.interrupted ?? 0;

    const completed = sent + failed + interrupted;

    const progress =
        total > 0
            ? Math.round((completed / total) * 100)
            : 0;

    const canStart =
        status &&
        !status.active &&
        (status.state === "previewed" ||
            status.state === "paused");

    return (
        <section className="mx-auto w-full max-w-3xl px-4 py-10 sm:px-6">
            <button
                type="button"
                onClick={onBack}
                className="text-sm text-neutral-500 hover:text-neutral-900"
            >
                ← Back to campaign
            </button>

            <header className="mt-8">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-neutral-500">
                    Run
                </p>

                <h1 className="mt-3 text-4xl font-semibold tracking-tight">
                    {campaign.name}
                </h1>

                <p className="mt-3 text-sm text-neutral-600">
                    {status?.state ?? "Loading status..."}
                </p>
            </header>

            <div className="mt-10 border border-neutral-300 bg-white p-6 sm:p-8">
                <div className="flex items-end justify-between">
                    <span className="text-sm text-neutral-500">
                        Progress
                    </span>

                    <span className="text-sm font-medium">
                        {progress}%
                    </span>
                </div>

                <div className="mt-3 h-2 bg-neutral-200">
                    <div
                        className="h-full bg-neutral-900 transition-all"
                        style={{ width: `${progress}%` }}
                    />
                </div>

                <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
                    <div>
                        <p className="text-xs uppercase tracking-wide text-neutral-500">
                            Sent
                        </p>
                        <p className="mt-1 text-2xl font-semibold">
                            {sent}
                        </p>
                    </div>

                    <div>
                        <p className="text-xs uppercase tracking-wide text-neutral-500">
                            Pending
                        </p>
                        <p className="mt-1 text-2xl font-semibold">
                            {pending}
                        </p>
                    </div>

                    <div>
                        <p className="text-xs uppercase tracking-wide text-neutral-500">
                            Failed
                        </p>
                        <p className="mt-1 text-2xl font-semibold">
                            {failed}
                        </p>
                    </div>

                    <div>
                        <p className="text-xs uppercase tracking-wide text-neutral-500">
                            Interrupted
                        </p>
                        <p className="mt-1 text-2xl font-semibold">
                            {interrupted}
                        </p>
                    </div>
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
                            onClick={() => void startRun()}
                            disabled={starting || !canStart}
                            className="border border-neutral-900 bg-neutral-900 px-4 py-3 text-sm font-medium text-white disabled:opacity-50"
                        >
                            {starting ? "Starting..." : "Start campaign"}
                        </button>
                    )}

                    <button
                        type="button"
                        onClick={onBack}
                        className="border border-neutral-300 bg-white px-4 py-3 text-sm font-medium"
                    >
                        Back
                    </button>
                </div>
            </div>
        </section>
    );
}