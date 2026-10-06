import { useState } from "react";
import type { Campaign } from "./types";
import CampaignEditor from "./pages/CampaignEditor";
import Campaigns from "./pages/Campaigns";
import Recipients from "./pages/Recipients";

type View =
    | { type: "campaigns" }
    | { type: "create-campaign" }
    | { type: "edit-campaign"; campaign: Campaign }
    | { type: "recipients"; campaign: Campaign };

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
            />
        );
    }

    return (
        <Campaigns
            onCreate={() => setView({ type: "create-campaign" })}
            onOpen={(campaign) =>
                setView({
                    type: "edit-campaign",
                    campaign,
                })
            }
        />
    );
}