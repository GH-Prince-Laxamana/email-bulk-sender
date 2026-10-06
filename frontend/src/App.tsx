import { useState } from "react";
import type { Campaign } from "./types";
import CampaignEditor from "./pages/CampaignEditor";
import Campaigns from "./pages/Campaigns";
import Recipients from "./pages/Recipients";
import Preview from "./pages/Preview";
import Settings from "./pages/Settings";
import RunProgress from "./pages/RunProgress";
import CampaignWorkspace from "./components/CampaignWorkspace";

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
    const [composeDirty, setComposeDirty] = useState(false);

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
            />
        );
    }

    if (view.type === "edit-campaign") {
        return (
            <CampaignWorkspace
                campaign={view.campaign}
                active="compose"
                onBack={() => setView({ type: "campaigns" })}
                onCompose={() =>
                    setView({
                        type: "edit-campaign",
                        campaign: view.campaign,
                    })
                }
                onRecipients={() =>
                    setView({
                        type: "recipients",
                        campaign: view.campaign,
                    })
                }
                onPreview={() =>
                    setView({
                        type: "preview",
                        campaign: view.campaign,
                    })
                }
                onRun={() =>
                    setView({
                        type: "run",
                        campaign: view.campaign,
                    })
                }
                hasUnsavedChanges={composeDirty}
            >
                <CampaignEditor
                    campaign={view.campaign}
                    onDirtyChange={setComposeDirty}
                    onRecipients={(campaign) =>
                        setView({ type: "recipients", campaign })
                    }
                    onSaved={(campaign) => {
                        setComposeDirty(false);
                        setView({
                            type: "edit-campaign",
                            campaign,
                        });
                    }}
                />
            </CampaignWorkspace>
        );
    }

    if (view.type === "recipients") {
        return (
            <CampaignWorkspace
                campaign={view.campaign}
                active="recipients"
                onBack={() => setView({ type: "campaigns" })}
                onCompose={() =>
                    setView({
                        type: "edit-campaign",
                        campaign: view.campaign,
                    })
                }
                onRecipients={() =>
                    setView({
                        type: "recipients",
                        campaign: view.campaign,
                    })
                }
                onPreview={() =>
                    setView({
                        type: "preview",
                        campaign: view.campaign,
                    })
                }
                onRun={() =>
                    setView({
                        type: "run",
                        campaign: view.campaign,
                    })
                }
            >
                <Recipients
                    campaign={view.campaign}
                    onPreview={(campaign) =>
                        setView({
                            type: "preview",
                            campaign,
                        })
                    }
                    onCampaignUpdated={(campaign) =>
                        setView({
                            type: "recipients",
                            campaign,
                        })
                    }
                />
            </CampaignWorkspace>
        );
    }

    if (view.type === "preview") {
        return (
            <CampaignWorkspace
                campaign={view.campaign}
                active="preview"
                onBack={() =>
                    setView({
                        type: "campaigns",
                    })
                }
                onCompose={() =>
                    setView({
                        type: "edit-campaign",
                        campaign: view.campaign,
                    })
                }
                onRecipients={() =>
                    setView({
                        type: "recipients",
                        campaign: view.campaign,
                    })
                }
                onPreview={() =>
                    setView({
                        type: "preview",
                        campaign: view.campaign,
                    })
                }
                onRun={() =>
                    setView({
                        type: "run",
                        campaign: view.campaign,
                    })
                }
            >
                <Preview
                    campaign={view.campaign}
                    onPreviewed={(campaign) => {
                        setView({
                            type: "preview",
                            campaign,
                        });
                    }}
                    onRun={(campaign) =>
                        setView({
                            type: "run",
                            campaign,
                        })
                    }
                />
            </CampaignWorkspace>
        );
    }

    if (view.type === "run") {
        return (
            <CampaignWorkspace
                campaign={view.campaign}
                active="run"
                onBack={() =>
                    setView({
                        type: "campaigns",
                    })
                }
                onCompose={() =>
                    setView({
                        type: "edit-campaign",
                        campaign: view.campaign,
                    })
                }
                onRecipients={() =>
                    setView({
                        type: "recipients",
                        campaign: view.campaign,
                    })
                }
                onPreview={() =>
                    setView({
                        type: "preview",
                        campaign: view.campaign,
                    })
                }
                onRun={() =>
                    setView({
                        type: "run",
                        campaign: view.campaign,
                    })
                }
            >
                <RunProgress
                    campaign={view.campaign}
                    onCampaignUpdated={(campaign) =>
                        setView({
                            type: "run",
                            campaign,
                        })
                    }
                />
            </CampaignWorkspace>
        );
    }

    if (view.type === "settings") {
        return (
            <Settings
                onBack={() => setView({ type: "campaigns" })}
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