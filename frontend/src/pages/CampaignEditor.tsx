import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { api } from "../api";
import type { AttachmentRule, Campaign } from "../types";

type Props = {
    campaign?: Campaign;
    onSaved: (campaign: Campaign) => void;
    onBack?: () => void;
    onRecipients?: (campaign: Campaign) => void;
    onDirtyChange?: (dirty: boolean) => void;
};

export default function CampaignEditor({
    campaign,
    onSaved,
    onBack,
    onRecipients,
    onDirtyChange,
}: Props) {
    const [name, setName] = useState(campaign?.name ?? "");
    const [subject, setSubject] = useState(campaign?.subject ?? "");
    const [bodyHtml, setBodyHtml] = useState(campaign?.body_html ?? "");
    const [variables, setVariables] = useState(
        campaign?.variables.join(", ") ?? "",
    );
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState("");
    const [savedMessage, setSavedMessage] = useState("");

    const [attachments, setAttachments] = useState<AttachmentRule[]>([]);
    const [attachmentsLoading, setAttachmentsLoading] = useState(false);
    const [attachmentsDirty, setAttachmentsDirty] = useState(false);
    const [attachmentsMessage, setAttachmentsMessage] = useState("");
    const [duplicateOpen, setDuplicateOpen] = useState(false);
    const [duplicateName, setDuplicateName] = useState("");
    const [carryRecipients, setCarryRecipients] = useState(false);

    const editable =
        !campaign?.locked &&
        campaign?.state !== "running";
    const variableList = variables
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean);
    const dirty = !campaign || (
        campaign.name !== name ||
        campaign.subject !== subject ||
        campaign.body_html !== bodyHtml ||
        campaign.variables.join(", ") !== variableList.join(", ")
    ) || attachmentsDirty;

    useEffect(() => {
        onDirtyChange?.(dirty);
        return () => onDirtyChange?.(false);
    }, [dirty, onDirtyChange]);

    useEffect(() => {
        if (!campaign) {
            return;
        }

        void loadAttachments();
    }, [campaign?.id]);

    async function loadAttachments() {
        if (!campaign) {
            return;
        }

        try {
            setAttachmentsLoading(true);
            setAttachmentsMessage("");

            const data = await api<AttachmentRule[]>(
                `/api/campaigns/${campaign.id}/attachments`,
            );

            setAttachments(data);
            setAttachmentsDirty(false);
        } catch (err) {
            setAttachmentsMessage(
                err instanceof Error
                    ? err.message
                    : "Could not load attachments.",
            );
        } finally {
            setAttachmentsLoading(false);
        }
    }

    function addFixedAttachment() {
        setAttachments((current) => [
            ...current,
            {
                path: "",
                folder: null,
                filename_template: null,
            },
        ]);
        setAttachmentsDirty(true);
    }

    function addTemplatedAttachment() {
        setAttachments((current) => [
            ...current,
            {
                path: null,
                folder: "",
                filename_template: "",
            },
        ]);
        setAttachmentsDirty(true);
    }

    function updateAttachment(
        index: number,
        updates: Partial<AttachmentRule>,
    ) {
        setAttachments((current) =>
            current.map((attachment, attachmentIndex) =>
                attachmentIndex === index
                    ? { ...attachment, ...updates }
                    : attachment,
            ),
        );
        setAttachmentsDirty(true);
    }

    function removeAttachment(index: number) {
        setAttachments((current) =>
            current.filter((_, attachmentIndex) => attachmentIndex !== index),
        );
        setAttachmentsDirty(true);
    }

    async function checkAttachmentPath(path: string) {
        try {
            const result = await api<{
                path: string;
                exists: boolean;
                is_file: boolean;
                is_directory: boolean;
            }>("/api/paths/check", {
                method: "POST",
                body: JSON.stringify({ path }),
            });

            setAttachmentsMessage(
                result.exists
                    ? result.is_file
                        ? "File exists."
                        : result.is_directory
                            ? "Folder exists."
                            : "Path exists."
                    : "Path does not exist.",
            );
        } catch (err) {
            setAttachmentsMessage(
                err instanceof Error
                    ? err.message
                    : "Could not check path.",
            );
        }
    }

    async function persistAttachments(campaignId: number) {
        await api<AttachmentRule[]>(
            `/api/campaigns/${campaignId}/attachments`,
            {
                method: "PUT",
                body: JSON.stringify(attachments),
            },
        );
    }

    async function duplicateCampaign() {
        if (!campaign) {
            return;
        }

        const newName = duplicateName.trim();

        if (!newName) {
            setError("Campaign name is required.");
            return;
        }

        try {
            setSaving(true);
            setError("");
            setSavedMessage("");

            const duplicated = await api<Campaign>(
                `/api/campaigns/${campaign.id}/duplicate`,
                {
                    method: "POST",
                    body: JSON.stringify({
                        new_name: newName,
                        carry_recipients: carryRecipients,
                    }),
                },
            );

            onSaved(duplicated);
            setDuplicateOpen(false);
        } catch (err) {
            setError(
                err instanceof Error
                    ? err.message
                    : "Could not duplicate campaign.",
            );
        } finally {
            setSaving(false);
        }
    }

    async function handleSubmit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();

        setSaving(true);
        setError("");

        try {
            const saved = campaign
                ? await api<Campaign>(`/api/campaigns/${campaign.id}`, {
                    method: "PATCH",
                    body: JSON.stringify({
                        name,
                        subject,
                        body_html: bodyHtml,
                        variables: variableList,
                    }),
                })
                : await api<Campaign>("/api/campaigns", {
                    method: "POST",
                    body: JSON.stringify({
                        name,
                        subject,
                        body_html: bodyHtml,
                        variables: variableList,
                    }),
                });

            if (attachmentsDirty) {
                await persistAttachments(saved.id);
                setAttachmentsDirty(false);
            }
            onSaved(saved);
            setAttachmentsMessage("");
            setSavedMessage("Saved.");
        } catch (err) {
            setError(
                err instanceof Error ? err.message : "Could not save campaign.",
            );
        } finally {
            setSaving(false);
        }
    }

    return (
        <section className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6">
            <header className="flex flex-col gap-4 border-b border-neutral-200 pb-6 sm:flex-row sm:items-end sm:justify-between">
                <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.14em] text-neutral-500">
                        {campaign ? "Edit campaign" : "New campaign"}
                    </p>

                    <h1 className="mt-3 text-4xl font-semibold tracking-tight">
                        {campaign ? campaign.name : "Create campaign"}
                    </h1>
                </div>
                {campaign && (
                    <div className="flex flex-wrap items-center gap-3">
                        {savedMessage && (
                            <span role="status" className="text-sm text-emerald-700">
                                {savedMessage}
                            </span>
                        )}
                        <button
                            type="button"
                            onClick={() => {
                                setDuplicateName(`${campaign.name} Copy`);
                                setCarryRecipients(false);
                                setError("");
                                setDuplicateOpen(true);
                            }}
                            disabled={saving}
                            className="border border-neutral-300 bg-white px-4 py-3 text-sm font-medium hover:bg-neutral-50 disabled:opacity-50"
                        >
                            Duplicate
                        </button>
                    </div>
                )}
                {campaign && !editable && (
                    <p className="mt-3 border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                        This campaign has already sent messages. Its content is
                        read-only; duplicate it to create an editable draft.
                    </p>
                )}
            </header>

            <form
                onSubmit={handleSubmit}
                className="mt-8 border border-neutral-300 bg-white p-6 sm:p-8"
            >
                <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_18rem]">
                    <div className="space-y-6 lg:col-start-1 lg:row-start-1">
                        <div>
                            <label
                                htmlFor="campaign-name"
                                className="mb-2 block text-sm font-medium"
                            >
                                Campaign name
                            </label>

                            <input
                                id="campaign-name"
                                value={name}
                                onChange={(event) => setName(event.target.value)}
                                readOnly={!editable}
                                required
                                className="w-full border border-neutral-300 px-3 py-3 text-sm outline-none focus:border-neutral-900"
                            />
                        </div>

                        <div>
                            <label
                                htmlFor="campaign-subject"
                                className="mb-2 block text-sm font-medium"
                            >
                                Subject
                            </label>

                            <input
                                id="campaign-subject"
                                value={subject}
                                onChange={(event) => setSubject(event.target.value)}
                                readOnly={!editable}
                                className="w-full border border-neutral-300 px-3 py-3 text-sm outline-none focus:border-neutral-900"
                                placeholder="Hello {{Name}}"
                            />
                        </div>

                        <div>
                            <label
                                htmlFor="campaign-body"
                                className="mb-2 block text-sm font-medium"
                            >
                                HTML body
                            </label>

                            <textarea
                                id="campaign-body"
                                value={bodyHtml}
                                onChange={(event) => setBodyHtml(event.target.value)}
                                readOnly={!editable}
                                rows={14}
                                className="w-full resize-y border border-neutral-300 px-3 py-3 font-mono text-sm leading-6 outline-none focus:border-neutral-900"
                                placeholder="<p>Hello {{Name|there}}</p>"
                            />
                        </div>
                    </div>
                    <div className="border-t border-neutral-200 pt-6">
                        <label
                            htmlFor="campaign-variables"
                            className="mb-2 block text-sm font-medium"
                        >
                            Variables
                        </label>

                        <input
                            id="campaign-variables"
                            value={variables}
                            onChange={(event) => setVariables(event.target.value)}
                            readOnly={!editable}
                            className="w-full border border-neutral-300 px-3 py-3 text-sm outline-none focus:border-neutral-900"
                            placeholder="Name, Company, Invoice Number"
                        />

                        <p className="mt-2 text-xs text-neutral-500">
                            Separate variable names with commas.
                        </p>
                    </div>

                    <div className="lg:col-start-1 lg:row-start-2">
                        <h2 className="text-base font-semibold">
                            Attachments
                        </h2>

                        <p className="mt-2 text-sm leading-6 text-neutral-500">
                            Add a fixed file or generate a filename from recipient variables.
                        </p>

                        {attachmentsLoading ? (
                            <p className="mt-5 text-sm text-neutral-500">
                                Loading attachments...
                            </p>
                        ) : (
                            <div className="mt-5 space-y-4">
                                {attachments.map((attachment, index) => (
                                    <div
                                        key={index}
                                        className="border border-neutral-200 p-4"
                                    >
                                        {attachment.path !== null ? (
                                            <div>
                                                <label className="mb-2 block text-sm font-medium">
                                                    File path
                                                </label>

                                                <div className="flex gap-3">
                                                    <input
                                                        value={attachment.path}
                                                        onChange={(event) =>
                                                            updateAttachment(index, {
                                                                path: event.target.value,
                                                            })
                                                        }
                                                        placeholder="C:\Files\invoice.pdf"
                                                        disabled={!editable}
                                                        className="min-w-0 flex-1 border border-neutral-300 px-3 py-3 text-sm outline-none focus:border-neutral-900 disabled:bg-neutral-100"
                                                    />

                                                    <button
                                                        type="button"
                                                        onClick={() =>
                                                            void checkAttachmentPath(
                                                                attachment.path ?? "",
                                                            )
                                                        }
                                                        disabled={!editable}
                                                        className="border border-neutral-300 bg-white px-3 py-3 text-sm font-medium hover:bg-neutral-50 disabled:opacity-50"
                                                    >
                                                        Check
                                                    </button>
                                                </div>
                                            </div>
                                        ) : (
                                            <div className="grid gap-4 sm:grid-cols-2">
                                                <div>
                                                    <label className="mb-2 block text-sm font-medium">
                                                        Folder
                                                    </label>

                                                    <div className="flex gap-2">
                                                        <input
                                                            value={attachment.folder ?? ""}
                                                            onChange={(event) =>
                                                                updateAttachment(index, {
                                                                    folder: event.target.value,
                                                                })
                                                            }
                                                            placeholder="C:\Files\Invoices"
                                                            disabled={!editable}
                                                            className="min-w-0 flex-1 border border-neutral-300 px-3 py-3 text-sm outline-none focus:border-neutral-900 disabled:bg-neutral-100"
                                                        />

                                                        <button
                                                            type="button"
                                                            onClick={() =>
                                                                void checkAttachmentPath(
                                                                    attachment.folder ?? "",
                                                                )
                                                            }
                                                            disabled={!editable}
                                                            className="border border-neutral-300 bg-white px-3 py-3 text-sm font-medium hover:bg-neutral-50 disabled:opacity-50"
                                                        >
                                                            Check
                                                        </button>
                                                    </div>
                                                </div>

                                                <div>
                                                    <label className="mb-2 block text-sm font-medium">
                                                        Filename template
                                                    </label>

                                                    <input
                                                        value={
                                                            attachment.filename_template ?? ""
                                                        }
                                                        onChange={(event) =>
                                                            updateAttachment(index, {
                                                                filename_template:
                                                                    event.target.value,
                                                            })
                                                        }
                                                        placeholder="Invoice-{{Name}}.pdf"
                                                        disabled={!editable}
                                                        className="w-full border border-neutral-300 px-3 py-3 text-sm outline-none focus:border-neutral-900 disabled:bg-neutral-100"
                                                    />
                                                </div>
                                            </div>
                                        )}

                                        {editable && (
                                            <button
                                                type="button"
                                                onClick={() => removeAttachment(index)}
                                                className="mt-3 text-sm text-neutral-500 hover:text-neutral-900"
                                            >
                                                Remove
                                            </button>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}

                        {editable && (
                            <div className="mt-5 flex flex-wrap gap-3">
                                <button
                                    type="button"
                                    onClick={addFixedAttachment}
                                    className="border border-neutral-300 bg-white px-4 py-3 text-sm font-medium hover:bg-neutral-50"
                                >
                                    Add file
                                </button>

                                <button
                                    type="button"
                                    onClick={addTemplatedAttachment}
                                    className="border border-neutral-300 bg-white px-4 py-3 text-sm font-medium hover:bg-neutral-50"
                                >
                                    Add templated file
                                </button>

                            </div>
                        )}

                        {attachmentsMessage && (
                            <p className="mt-4 text-sm text-neutral-600">
                                {attachmentsMessage}
                            </p>
                        )}
                    </div>
                    {!campaign && (
                        <div className="lg:col-start-2 lg:row-start-2">
                            <p className="text-sm text-neutral-500">Add variables after creating the campaign.</p>
                        </div>
                    )}
                </div>

                {error && (
                    <div className="mt-6 border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                        {error}
                    </div>
                )}

                <div className="mt-6 flex flex-wrap gap-3 border-t border-neutral-200 pt-6">
                    <button
                        type="submit"
                        disabled={saving || !editable || !dirty}
                        className="border border-neutral-900 bg-neutral-900 px-4 py-3 text-sm font-medium text-white disabled:opacity-50"
                    >
                        {saving ? "Saving..." : editable ? "Save campaign" : "Content locked"}
                    </button>

                    {!campaign && (
                        <button
                            type="button"
                            onClick={onBack}
                            className="border border-neutral-300 bg-white px-4 py-3 text-sm font-medium"
                        >
                            Cancel
                        </button>
                    )}

                    {campaign && onRecipients && (
                        <button
                            type="button"
                            onClick={() => onRecipients(campaign)}
                            className="border border-neutral-300 bg-white px-4 py-3 text-sm font-medium"
                        >
                            View recipients
                        </button>
                    )}
                </div>
            </form>

            {duplicateOpen && campaign && (
                <div className="fixed inset-0 z-20 flex items-center justify-center overflow-y-auto bg-neutral-900/30 p-4">
                    <div role="dialog" aria-modal="true" aria-labelledby="duplicate-title" className="max-h-[calc(100vh-2rem)] w-full max-w-md overflow-y-auto border border-neutral-300 bg-white p-6 shadow-xl">
                        <h2 id="duplicate-title" className="text-lg font-semibold">Duplicate campaign</h2>
                        <p className="mt-2 text-sm leading-6 text-neutral-600">
                            Create a new unlocked draft based on “{campaign.name}”.
                        </p>
                        <label htmlFor="duplicate-name" className="mt-6 block text-sm font-medium">New campaign name</label>
                        <input
                            id="duplicate-name"
                            autoFocus
                            value={duplicateName}
                            onChange={(event) => setDuplicateName(event.target.value)}
                            className="mt-2 w-full border border-neutral-300 px-3 py-3 text-sm outline-none focus:border-neutral-900"
                        />
                        <label className="mt-5 flex items-start gap-3 text-sm text-neutral-700">
                            <input type="checkbox" checked={carryRecipients} onChange={(event) => setCarryRecipients(event.target.checked)} className="mt-1" />
                            <span>
                                Copy recipients into the new campaign
                                <span className="mt-1 block text-xs text-neutral-500">Copied recipients return to pending.</span>
                            </span>
                        </label>
                        {error && <p className="mt-4 text-sm text-red-700">{error}</p>}
                        <div className="mt-6 flex justify-end gap-3">
                            <button type="button" onClick={() => setDuplicateOpen(false)} disabled={saving} className="border border-neutral-300 bg-white px-4 py-3 text-sm font-medium">Cancel</button>
                            <button type="button" onClick={() => void duplicateCampaign()} disabled={saving} className="border border-neutral-900 bg-neutral-900 px-4 py-3 text-sm font-medium text-white disabled:opacity-50">{saving ? "Duplicating..." : "Duplicate"}</button>
                        </div>
                    </div>
                </div>
            )}
        </section>
    );
}