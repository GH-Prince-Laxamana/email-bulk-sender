import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { api } from "../api";
import type { AttachmentRule, Campaign } from "../types";

type Props = {
    campaign?: Campaign;
    onSaved: (campaign: Campaign) => void;
    onBack: () => void;
    onRecipients: (campaign: Campaign) => void;
};

export default function CampaignEditor({
    campaign,
    onSaved,
    onBack,
    onRecipients,
}: Props) {
    const [name, setName] = useState(campaign?.name ?? "");
    const [subject, setSubject] = useState(campaign?.subject ?? "");
    const [bodyHtml, setBodyHtml] = useState(campaign?.body_html ?? "");
    const [variables, setVariables] = useState(
        campaign?.variables.join(", ") ?? "",
    );
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState("");

    const [attachments, setAttachments] = useState<AttachmentRule[]>([]);
    const [attachmentsLoading, setAttachmentsLoading] = useState(false);
    const [attachmentsSaving, setAttachmentsSaving] = useState(false);
    const [attachmentsMessage, setAttachmentsMessage] = useState("");

    const editable =
        !campaign?.locked &&
        campaign?.state !== "running";

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
    }

    function removeAttachment(index: number) {
        setAttachments((current) =>
            current.filter((_, attachmentIndex) => attachmentIndex !== index),
        );
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

    async function saveAttachments() {
        if (!campaign) {
            return;
        }

        try {
            setAttachmentsSaving(true);
            setAttachmentsMessage("");

            await api<AttachmentRule[]>(
                `/api/campaigns/${campaign.id}/attachments`,
                {
                    method: "PUT",
                    body: JSON.stringify(attachments),
                },
            );

            setAttachmentsMessage("Attachments saved.");
        } catch (err) {
            setAttachmentsMessage(
                err instanceof Error
                    ? err.message
                    : "Could not save attachments.",
            );
        } finally {
            setAttachmentsSaving(false);
        }
    }

    async function duplicateCampaign() {
        if (!campaign) {
            return;
        }

        const nameInput = window.prompt(
            "Name for the duplicated campaign:",
            `${campaign.name} Copy`,
        );

        if (nameInput === null) {
            return;
        }

        const newName = nameInput.trim();

        if (!newName) {
            setError("Campaign name is required.");
            return;
        }

        const carryRecipients = window.confirm(
            "Carry the existing recipients into the new campaign?",
        );

        try {
            setSaving(true);
            setError("");

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

        const variableList = variables
            .split(",")
            .map((value) => value.trim())
            .filter(Boolean);

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

            onSaved(saved);
        } catch (err) {
            setError(
                err instanceof Error ? err.message : "Could not save campaign.",
            );
        } finally {
            setSaving(false);
        }
    }

    return (
        <section className="mx-auto w-full max-w-3xl px-4 py-10 sm:px-6">
            <button
                type="button"
                onClick={onBack}
                className="text-sm text-neutral-500 hover:text-neutral-900"
            >
                ← Back to campaigns
            </button>

            <header className="mt-8">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-neutral-500">
                    {campaign ? "Edit campaign" : "New campaign"}
                </p>

                <h1 className="mt-3 text-4xl font-semibold tracking-tight">
                    {campaign ? campaign.name : "Create campaign"}
                </h1>
            </header>

            <form
                onSubmit={handleSubmit}
                className="mt-10 space-y-6 border border-neutral-300 bg-white p-6 sm:p-8"
            >
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
                        rows={14}
                        className="w-full resize-y border border-neutral-300 px-3 py-3 font-mono text-sm leading-6 outline-none focus:border-neutral-900"
                        placeholder="<p>Hello {{Name|there}}</p>"
                    />
                </div>

                <div>
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
                        className="w-full border border-neutral-300 px-3 py-3 text-sm outline-none focus:border-neutral-900"
                        placeholder="Name, Company, Invoice Number"
                    />

                    <p className="mt-2 text-xs text-neutral-500">
                        Separate variable names with commas.
                    </p>
                </div>

                {campaign && (
                    <div className="border-t border-neutral-200 pt-6">
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

                                <button
                                    type="button"
                                    onClick={() => void saveAttachments()}
                                    disabled={attachmentsSaving}
                                    className="border border-neutral-900 bg-neutral-900 px-4 py-3 text-sm font-medium text-white disabled:opacity-50"
                                >
                                    {attachmentsSaving
                                        ? "Saving..."
                                        : "Save attachments"}
                                </button>
                            </div>
                        )}

                        {attachmentsMessage && (
                            <p className="mt-4 text-sm text-neutral-600">
                                {attachmentsMessage}
                            </p>
                        )}
                    </div>
                )}

                {error && (
                    <div className="border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                        {error}
                    </div>
                )}

                <div className="flex gap-3 border-t border-neutral-200 pt-6">
                    <button
                        type="submit"
                        disabled={saving}
                        className="border border-neutral-900 bg-neutral-900 px-4 py-3 text-sm font-medium text-white disabled:opacity-50"
                    >
                        {saving ? "Saving..." : "Save campaign"}
                    </button>

                    {campaign && (
                        <button
                            type="button"
                            onClick={() => onRecipients(campaign)}
                            className="border border-neutral-300 bg-white px-4 py-3 text-sm font-medium"
                        >
                            Recipients
                        </button>
                    )}

                    {campaign && (
                        <button
                            type="button"
                            onClick={() => void duplicateCampaign()}
                            disabled={saving}
                            className="border border-neutral-300 bg-white px-4 py-3 text-sm font-medium hover:bg-neutral-50 disabled:opacity-50"
                        >
                            Duplicate
                        </button>
                    )}

                    <button
                        type="button"
                        onClick={onBack}
                        className="border border-neutral-300 bg-white px-4 py-3 text-sm font-medium"
                    >
                        Cancel
                    </button>
                </div>
            </form>
        </section>
    );
}