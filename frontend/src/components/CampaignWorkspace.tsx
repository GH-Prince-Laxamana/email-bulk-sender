import { useState } from "react";
import type { ReactNode } from "react";
import type { Campaign } from "../types";

type Section = "compose" | "recipients" | "preview" | "run";

type Props = {
    campaign: Campaign;
    active: Section;
    onBack: () => void;
    onCompose: () => void;
    onRecipients: () => void;
    onPreview: () => void;
    onRun: () => void;
    hasUnsavedChanges?: boolean;
    children: ReactNode;
};

export default function CampaignWorkspace({
    campaign,
    active,
    onBack,
    onCompose,
    onRecipients,
    onPreview,
    onRun,
    hasUnsavedChanges = false,
    children,
}: Props) {
    const [pendingAction, setPendingAction] = useState<(() => void) | null>(null);
    function requestNavigation(action: () => void) {
        if (hasUnsavedChanges) {
            setPendingAction(() => action);
            return;
        }
        action();
    }
    const stateMessage: Record<Campaign["state"], string> = {
        draft: "Preview required before sending.",
        previewed: "Ready to send.",
        paused: campaign.halt_reason ?? "Review recipients before resuming.",
        running: "Sending in progress.",
        finished: "All recipients processed.",
    };
    const stateColor = campaign.state === "finished"
        ? "text-emerald-700"
        : campaign.state === "paused"
            ? "text-amber-700"
            : campaign.state === "running"
                ? "text-neutral-700"
                : "text-neutral-500";
    const tabs = [
        {
            id: "compose" as const,
            label: "Compose",
            onClick: onCompose,
            disabled: false,
        },
        {
            id: "recipients" as const,
            label: "Recipients",
            onClick: onRecipients,
            disabled: false,
        },
        {
            id: "preview" as const,
            label: "Preview",
            onClick: onPreview,
            disabled: false,
        },
        {
            id: "run" as const,
            label: "Run",
            onClick: onRun,
            disabled: false,
        },
    ];

    return (
        <div>
            <div className="sticky top-0 z-10 border-b border-neutral-200 bg-white/95 backdrop-blur-sm">
                <div className="mx-auto w-full max-w-6xl px-4 sm:px-6">
                    <div className="flex min-h-16 items-center justify-between gap-6">
                        <button
                            type="button"
                            onClick={() => requestNavigation(onBack)}
                            className="shrink-0 text-sm text-neutral-500 hover:text-neutral-900"
                        >
                            ← Campaigns
                        </button>

                        <div className="min-w-0 flex-1 text-center">
                            <p className="truncate text-sm font-medium">
                                {campaign.name}
                            </p>

                            <p className={`mt-0.5 text-xs tracking-wide ${stateColor}`}>
                                {stateMessage[campaign.state]}
                            </p>
                        </div>

                        <div className="w-20 shrink-0" />
                    </div>

                    <nav
                        aria-label="Campaign"
                        className="flex overflow-x-auto"
                    >
                        {tabs.map((tab) => {
                            const selected = tab.id === active;

                            return (
                                <button
                                    key={tab.id}
                                    type="button"
                                    onClick={() => requestNavigation(tab.onClick)}
                                    disabled={tab.disabled}
                                    aria-current={selected ? "page" : undefined}
                                    className={`border-b-2 px-4 py-3 text-sm font-medium whitespace-nowrap ${selected
                                            ? "border-neutral-900 text-neutral-900"
                                            : "border-transparent text-neutral-500 hover:text-neutral-900"
                                        } disabled:cursor-not-allowed disabled:opacity-40`}
                                >
                                    {tab.label}
                                </button>
                            );
                        })}
                    </nav>
                </div>
            </div>

            {children}
            {pendingAction && (
                <div className="fixed inset-0 z-30 flex items-center justify-center bg-neutral-900/30 p-4">
                    <div role="dialog" aria-modal="true" className="w-full max-w-md border border-neutral-300 bg-white p-6 shadow-xl">
                        <h2 className="text-lg font-semibold">Leave without saving?</h2>
                        <p className="mt-2 text-sm leading-6 text-neutral-600">
                            Would you like to save your campaign before leaving Compose?
                        </p>
                        <div className="mt-6 flex justify-end gap-3">
                            <button type="button" onClick={() => setPendingAction(null)} className="border border-neutral-300 bg-white px-4 py-3 text-sm font-medium">Stay</button>
                            <button type="button" onClick={() => { const action = pendingAction; setPendingAction(null); action(); }} className="border border-neutral-900 bg-neutral-900 px-4 py-3 text-sm font-medium text-white">Leave without saving</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}