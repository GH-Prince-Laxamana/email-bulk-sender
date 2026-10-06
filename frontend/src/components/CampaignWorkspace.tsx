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
    children,
}: Props) {
    const tabs = [
        {
            id: "compose" as const,
            label: "Compose",
            onClick: onCompose,
        },
        {
            id: "recipients" as const,
            label: "Recipients",
            onClick: onRecipients,
        },
        {
            id: "preview" as const,
            label: "Preview",
            onClick: onPreview,
        },
        {
            id: "run" as const,
            label: "Run",
            onClick: onRun,
        },
    ];

    return (
        <div>
            <div className="border-b border-neutral-200 bg-white">
                <div className="mx-auto w-full max-w-6xl px-4 sm:px-6">
                    <div className="flex min-h-16 items-center justify-between gap-6">
                        <button
                            type="button"
                            onClick={onBack}
                            className="shrink-0 text-sm text-neutral-500 hover:text-neutral-900"
                        >
                            ← Campaigns
                        </button>

                        <div className="min-w-0 flex-1 text-center">
                            <p className="truncate text-sm font-medium">
                                {campaign.name}
                            </p>

                            <p className="mt-0.5 text-xs uppercase tracking-wide text-neutral-500">
                                {campaign.state}
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
                                    onClick={tab.onClick}
                                    aria-current={
                                        selected ? "page" : undefined
                                    }
                                    className={`border-b-2 px-4 py-3 text-sm font-medium whitespace-nowrap ${selected
                                            ? "border-neutral-900 text-neutral-900"
                                            : "border-transparent text-neutral-500 hover:text-neutral-900"
                                        }`}
                                >
                                    {tab.label}
                                </button>
                            );
                        })}
                    </nav>
                </div>
            </div>

            {children}
        </div>
    );
}