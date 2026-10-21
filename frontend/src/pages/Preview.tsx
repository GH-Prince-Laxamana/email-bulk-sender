import { useEffect, useRef, useState } from "react";
import AttachmentPreview from "../components/AttachmentPreview";
import { api } from "../api";
import type {
    Campaign,
    CampaignPreview,
    Recipient,
    RecipientPreview,
} from "../types";

type Props = {
    campaign: Campaign;
    onPreviewed: (campaign: Campaign, preview: CampaignPreview) => void;
    onRun: (campaign: Campaign) => void;
    onEditAttachments: () => void;
    onEditRecipients: () => void;
};

export default function Preview({ campaign, onPreviewed, onRun, onEditAttachments, onEditRecipients }: Props) {
    const [preview, setPreview] = useState<CampaignPreview | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [selectedId, setSelectedId] = useState<number | null>(null);
    const [recipients, setRecipients] = useState<Recipient[]>([]);
    const [recipientPreview, setRecipientPreview] =
        useState<RecipientPreview | null>(null);
    const [loadingRecipient, setLoadingRecipient] = useState(false);
    const [starting, setStarting] = useState(false);
    const [sendConfirmOpen, setSendConfirmOpen] = useState(false);
    const [format, setFormat] = useState<"html" | "text">("html");
    const [openAttachment, setOpenAttachment] = useState<number | null>(null);
    const inspection = useRef(0);

    useEffect(() => {
        void loadReview();
    }, [campaign.id]);

    async function inspectRecipient(recipientId: number) {
        const requestId = ++inspection.current;
        try {
            setSelectedId(recipientId);
            setRecipientPreview(null);
            setOpenAttachment(null);
            setLoadingRecipient(true);
            setError("");
            const data = await api<RecipientPreview>(
                    `/api/campaigns/${campaign.id}/recipients/${recipientId}/preview`,
                    { method: "POST" },
                );
            if (requestId === inspection.current) setRecipientPreview(data);
        } catch (err) {
            if (requestId !== inspection.current) return;
            setRecipientPreview(null);
            setError(
                err instanceof Error
                    ? err.message
                    : "Could not preview recipient.",
            );
        } finally {
            if (requestId === inspection.current) setLoadingRecipient(false);
        }
    }

    async function runPreview() {
        try {
            setLoading(true);
            setError("");
            await loadReview();
        } catch (err) {
            setError(err instanceof Error ? err.message : "Could not generate preview.");
        } finally {
            setLoading(false);
        }
    }

    async function loadReview() {
        try {
            setLoading(true);
            setError("");
            const [recipientData, data] = await Promise.all([
                api<Recipient[]>(`/api/campaigns/${campaign.id}/recipients`),
                api<CampaignPreview>(`/api/campaigns/${campaign.id}/preview`, {
                    method: "POST",
                }),
            ]);
            setRecipients(recipientData);
            if (recipientData.length === 0) {
                setPreview(null);
                setRecipientPreview(null);
                return;
            }
            setPreview(data);
            const nextRecipientId = selectedId ?? recipientData[0]?.id;
            if (nextRecipientId !== undefined) {
                await inspectRecipient(nextRecipientId);
            }
            onPreviewed({ ...campaign, state: data.state }, data);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Could not load preview.");
        } finally {
            setLoading(false);
        }
    }

    async function startCampaign() {
        try {
            setStarting(true);
            setError("");
            await api(`/api/campaigns/${campaign.id}/run`, { method: "POST" });
            const updatedCampaign = await api<Campaign>(`/api/campaigns/${campaign.id}`);
            onRun(updatedCampaign);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Could not start campaign.");
        } finally {
            setStarting(false);
        }
    }

    return (
        <section className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6">
            <header className="flex flex-col justify-between gap-6 border-b border-neutral-200 pb-8 sm:flex-row sm:items-end">
                <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.14em] text-neutral-500">
                        Campaign preview
                    </p>
                    <h1 className="mt-3 text-4xl font-semibold tracking-tight">{campaign.name}</h1>
                    <p className="mt-3 max-w-2xl text-sm leading-6 text-neutral-600">
                        Review each recipient’s message and attached files before sending.
                    </p>
                </div>
                <div className="flex flex-wrap gap-3">
                    <button type="button" onClick={onEditAttachments}
                        className="border border-neutral-300 bg-white px-4 py-3 text-sm font-medium hover:border-neutral-900">
                        {campaign.locked ? "View attachment rules" : "Adjust attachments"}
                    </button>
                    <button type="button" onClick={() => void runPreview()} disabled={loading}
                        className="border border-neutral-300 bg-white px-4 py-3 text-sm font-medium hover:border-neutral-900 disabled:opacity-50">
                        {loading ? "Refreshing..." : "Refresh review"}
                    </button>
                    <button type="button" onClick={() => setSendConfirmOpen(true)} disabled={loading || starting || !preview?.clean}
                        className="border border-neutral-900 bg-neutral-900 px-4 py-3 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50">
                        {starting ? "Starting..." : "Start campaign"}
                    </button>
                </div>
            </header>

            {error && <div role="alert" className="mt-6 border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>}

            {loading && !preview ? (
                <div className="mt-10 border border-neutral-200 bg-white p-8 text-sm text-neutral-500">
                    Preparing the campaign review...
                </div>
            ) : recipients.length === 0 ? (
                <div className="mt-10 border border-dashed border-neutral-300 bg-white p-10 text-center">
                    <h2 className="text-lg font-medium">Add recipients before reviewing</h2>
                    <p className="mt-2 text-sm text-neutral-500">
                        The campaign preview will be available after at least one recipient is added.
                    </p>
                </div>
            ) : preview ? (
                <>
                    <div className="mt-8 grid gap-4 sm:grid-cols-3">
                        <div className={`border p-5 ${preview.clean ? "border-emerald-200 bg-emerald-50" : "border-amber-200 bg-amber-50"}`}>
                            <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Status</p>
                            <p className="mt-2 text-lg font-semibold">{preview.clean ? "Ready to send" : "Needs attention"}</p>
                        </div>
                        <div className="border border-neutral-200 bg-white p-5"><p className="text-xs uppercase tracking-wide text-neutral-500">Valid</p><p className="mt-2 text-2xl font-semibold">{preview.valid}</p></div>
                        <div className="border border-neutral-200 bg-white p-5"><p className="text-xs uppercase tracking-wide text-neutral-500">Invalid</p><p className="mt-2 text-2xl font-semibold">{preview.invalid}</p></div>
                    </div>

                    {preview.errors.length > 0 && (
                        <div className="mt-6 border border-red-200 bg-red-50 p-5">
                            <h2 className="text-sm font-semibold">Problems to fix</h2>
                            <div className="mt-3 space-y-3">
                                {preview.errors.map((item) => <div key={`${item.recipient_id}-${item.code}`} className="text-sm">
                                    <span className="font-medium">{item.email}</span><span className="ml-2 text-xs uppercase text-red-700">{item.code}</span>
                                    <p className="mt-1 text-red-800">{item.message}</p>
                                </div>)}
                            </div>
                        </div>
                    )}

                    <div className="mt-8 grid gap-6 lg:grid-cols-[15rem_1fr]">
                        <aside className="border border-neutral-200 bg-white">
                            <div className="border-b border-neutral-200 px-4 py-3"><p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Recipients</p></div>
                            <div className="max-h-96 overflow-y-auto p-2">
                                {recipients.map((item) => <button key={item.id} type="button" onClick={() => void inspectRecipient(item.id)}
                                    className={`w-full border-l-2 px-3 py-3 text-left text-sm ${selectedId === item.id ? "border-neutral-900 bg-neutral-50" : "border-transparent hover:bg-neutral-50"}`}>
                                    <span className="block truncate font-medium">{item.email}</span>
                                    <span className="mt-1 block text-xs text-neutral-600">{preview.previews.find((entry) => entry.recipient_id === item.id)?.attachments.length ?? "—"} files · {item.status}</span>
                                </button>)}
                                {!recipients.length && <p className="p-3 text-sm text-neutral-500">No recipients to preview.</p>}
                            </div>
                        </aside>
                        <article className="min-w-0 border border-neutral-200 bg-white">
                            {recipientPreview ? <>
                                <header className="flex flex-col gap-3 border-b border-neutral-200 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
                                    <div><p className="text-sm font-medium">{recipientPreview.email}</p><p className="mt-1 text-xs text-neutral-500">{recipientPreview.subject || "No subject"}</p></div>
                                    <div className="flex border border-neutral-200 text-xs">
                                        {(["html", "text"] as const).map((item) => <button key={item} type="button" onClick={() => setFormat(item)} className={`px-3 py-2 uppercase ${format === item ? "bg-neutral-900 text-white" : "bg-white text-neutral-500"}`}>{item}</button>)}
                                    </div>
                                </header>
                                <section aria-label="Recipient attachments" className="border-b border-neutral-200 px-5 py-5">
                                    <div className="flex flex-wrap items-center justify-between gap-3">
                                        <h2 className="text-sm font-semibold">Files for this recipient ({recipientPreview.attachments.length})</h2>
                                        <button type="button" onClick={onEditAttachments} className="text-sm underline underline-offset-4">{campaign.locked ? "View attachment rules" : "Adjust attachments"}</button>
                                    </div>
                                    <p className="mt-2 text-sm leading-6 text-neutral-600">Shared files go to everyone. Templated filenames use this recipient’s values. <button type="button" onClick={onEditRecipients} className="underline underline-offset-4">Review recipient values</button>.</p>
                                    {recipientPreview.attachments.length === 0 ? <p className="mt-4 text-sm text-neutral-600">No files will be attached to this email.</p> : <ul className="mt-4 divide-y divide-neutral-200">
                                        {recipientPreview.attachments.map((file, index) => <li key={`${recipientPreview.recipient_id}-${index}`} className="py-4 first:pt-0 last:pb-0">
                                            <div className="flex flex-wrap items-start justify-between gap-3">
                                                <div className="min-w-0 flex-1">
                                                    <p className="break-words text-sm font-medium">{file.filename}</p>
                                                    <p className="mt-1 break-all text-xs leading-5 text-neutral-600">{file.path}</p>
                                                    <p className="mt-1 text-xs text-neutral-600">{file.size.toLocaleString()} bytes</p>
                                                </div>
                                                <button type="button" aria-expanded={openAttachment === index} onClick={() => setOpenAttachment(openAttachment === index ? null : index)} className="border border-neutral-300 px-3 py-2 text-sm hover:bg-neutral-50">{openAttachment === index ? "Close preview" : "Preview file"}</button>
                                            </div>
                                            {openAttachment === index && <AttachmentPreview endpoint={`/api/campaigns/${campaign.id}/recipients/${recipientPreview.recipient_id}/attachments/${index}`} filename={file.filename} />}
                                        </li>)}
                                    </ul>}
                                </section>
                                {format === "html" ? <iframe title={`Preview for ${recipientPreview.email}`} srcDoc={recipientPreview.html} sandbox="" className="h-128 w-full bg-white" /> : <pre className="h-128 overflow-auto whitespace-pre-wrap p-6 font-sans text-sm leading-6 text-neutral-700">{recipientPreview.text}</pre>}
                            </> : <p className="p-8 text-sm text-neutral-500">{loadingRecipient ? "Previewing..." : "Select a recipient to view their message."}</p>}
                        </article>
                    </div>
                </>
            ) : null}
            {sendConfirmOpen && (
                <div className="fixed inset-0 z-30 flex items-center justify-center bg-neutral-900/30 p-4">
                    <div role="dialog" aria-modal="true" className="w-full max-w-md border border-neutral-300 bg-white p-6 shadow-xl">
                        <h2 className="text-lg font-semibold">Start campaign?</h2>
                        <p className="mt-2 text-sm leading-6 text-neutral-600">
                            Are you sure you want to send emails to the validated recipients?
                        </p>
                        <div className="mt-6 flex justify-end gap-3">
                            <button type="button" onClick={() => setSendConfirmOpen(false)} className="border border-neutral-300 bg-white px-4 py-3 text-sm font-medium">Cancel</button>
                            <button type="button" onClick={() => { setSendConfirmOpen(false); void startCampaign(); }} className="border border-neutral-900 bg-neutral-900 px-4 py-3 text-sm font-medium text-white">Send emails</button>
                        </div>
                    </div>
                </div>
            )}
        </section>
    );
}
