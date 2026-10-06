import { useState } from "react";
import type { Campaign } from "./types";
import CampaignEditor from "./pages/CampaignEditor";
import Campaigns from "./pages/Campaigns";
import Recipients from "./pages/Recipients";
import Preview from "./pages/Preview";
import Settings from "./pages/Settings";
import RunProgress from "./pages/RunProgress";

type View =
    | { type: "campaigns" }
    | { type: "create-campaign" }
    | { type: "edit-campaign"; campaign: Campaign }
    | { type: "recipients"; campaign: Campaign }
    | { type: "preview"; campaign: Campaign }
    | { type: "settings" }
    | { type: "run"; campaign: Campaign };

export default function App() {
    const [view, setView] = useState<View>({
        type: "campaigns",
    });

    if (view.type === "create-campaign") {
        return (
            <CampaignEditor
                onBack={() => setView({ type: "campaigns" })}
                onSaved={(campaign) => {
                    setView({
                        type: "edit-campaign",
                        campaign,
                    });
                }}
                onRecipients={(campaign) =>
                    setView({
                        type: "recipients",
                        campaign,
                    })
                }
            />
        );
    }

    if (view.type === "edit-campaign") {
        return (
            <CampaignEditor
                campaign={view.campaign}
                onBack={() => setView({ type: "campaigns" })}
                onSaved={(campaign) => {
                    setView({
                        type: "edit-campaign",
                        campaign,
                    });
                }}
                onRecipients={(campaign) =>
                    setView({
                        type: "recipients",
                        campaign,
                    })
                }
            />
        );
    }

    if (view.type === "recipients") {
        return (
            <Recipients
                campaign={view.campaign}
                onBack={() =>
                    setView({
                        type: "edit-campaign",
                        campaign: view.campaign,
                    })
                }
                onPreview={(campaign) =>
                    setView({
                        type: "preview",
                        campaign,
                    })
                }
            />
        );
    }

    if (view.type === "preview") {
        return (
            <Preview
                campaign={view.campaign}
                onBack={() =>
                    setView({
                        type: "recipients",
                        campaign: view.campaign,
                    })
                }
                onPreviewed={(campaign) => {
                    setView({
                        type: "preview",
                        campaign,
                    });
                }}
                onRun={(campaign) => {
                    setView({
                        type: "run",
                        campaign,
                    });
                }}
            />
        );
    }

    if (view.type === "settings") {
        return (
            <Settings
                onBack={() => setView({ type: "campaigns" })}
            />
        );
    }

    if (view.type === "run") {
        return (
            <RunProgress
                campaign={view.campaign}
                onBack={() =>
                    setView({
                        type: "preview",
                        campaign: view.campaign,
                    })
                }
            />
        );
    }

    return (
        <Campaigns
            onCreate={() => setView({ type: "create-campaign" })}
            onSettings={() => setView({ type: "settings" })}
            onOpen={(campaign) =>
                setView({
                    type: "edit-campaign",
                    campaign,
                })
            }
        />
    );
}