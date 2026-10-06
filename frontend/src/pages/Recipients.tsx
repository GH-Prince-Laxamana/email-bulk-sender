import { type ChangeEvent, useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { Campaign, ImportResult, Recipient } from "../types";

type Props = {
    campaign: Campaign;
    onPreview: (campaign: Campaign) => void;
    onCampaignUpdated: (campaign: Campaign) => void;
};

export default function Recipients({
    campaign,
    onPreview,
    onCampaignUpdated,
}: Props) {
    const [recipients, setRecipients] = useState<Recipient[]>([]);
    const [text, setText] = useState("");
    const [loading, setLoading] = useState(true);
    const [importing, setImporting] = useState(false);
    const [message, setMessage] = useState("");
    const [messageKind, setMessageKind] = useState<"success" | "error">("success");
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [retryingFailed, setRetryingFailed] = useState(false);
    const [resolvingId, setResolvingId] = useState<number | null>(null);
    const [editingRecipient, setEditingRecipient] =
        useState<Recipient | null>(null);
    const [editEmail, setEditEmail] = useState("");
    const [editValues, setEditValues] =
        useState<Record<string, string>>({});
    const [savingEdit, setSavingEdit] = useState(false);
    const [deletingId, setDeletingId] = useState<number | null>(null);
    const [deleteTarget, setDeleteTarget] = useState<Recipient | null>(null);
    const [query, setQuery] = useState("");
    const [statusFilter, setStatusFilter] = useState<"all" | Recipient["status"]>("all");
    const [adding, setAdding] = useState(false);
    const [addEmail, setAddEmail] = useState("");
    const [addValues, setAddValues] = useState<Record<string, string>>({});
    const [savingAdd, setSavingAdd] = useState(false);
    const [importSummary, setImportSummary] = useState<{ rows: number; newRows: number; duplicates: number; columns: string[] } | null>(null);
    const [importOpen, setImportOpen] = useState(false);

    const editable = campaign.state !== "running";
    const detectedVariables = (() => {
        const found = new Set(campaign.variables);
        for (const match of `${campaign.subject} ${campaign.body_html}`.matchAll(/\{\{\s*([^}|]+?)(?:\|[^}]*)?\s*\}\}/g)) {
            const name = match[1].trim();
            if (name) found.add(name);
        }
        recipients.forEach((recipient) => Object.keys(recipient.values).forEach((key) => found.add(key)));
        return [...found];
    })();
    const visibleRecipients = recipients.filter((recipient) => {
        const matchesQuery = !query.trim() ||
            recipient.email.toLowerCase().includes(query.trim().toLowerCase()) ||
            Object.values(recipient.values).some((value) => value.toLowerCase().includes(query.trim().toLowerCase()));
        return matchesQuery && (statusFilter === "all" || recipient.status === statusFilter);
    });
    const statusCounts = recipients.reduce<Record<string, number>>((counts, recipient) => {
        counts[recipient.status] = (counts[recipient.status] ?? 0) + 1;
        return counts;
    }, {});

    useEffect(() => {
        void loadRecipients();
    }, [campaign.id]);

    async function loadRecipients() {
        try {
            setLoading(true);
            const data = await api<Recipient[]>(
                `/api/campaigns/${campaign.id}/recipients`,
            );
            setRecipients(data);
        } catch (error) {
            setMessage(
                error instanceof Error
                    ? error.message
                    : "Could not load recipients.",
            );
        } finally {
            setLoading(false);
        }
    }

    async function refreshCampaign() {
        const updated = await api<Campaign>(
            `/api/campaigns/${campaign.id}`,
        );

        onCampaignUpdated(updated);
    }

    function showMessage(value: string, kind: "success" | "error" = "success") {
        setMessage(value);
        setMessageKind(kind);
    }

    function parseImport(value: string) {
        const lines = value.trim().split(/\r?\n/).filter(Boolean);
        const header = lines[0]?.split(lines[0]?.includes("\t") ? "\t" : ",").map((item) => item.trim()) ?? [];
        const emailIndex = header.findIndex((item) => item.toLowerCase() === "email");
        const existing = new Set(recipients.map((recipient) => recipient.email.toLowerCase()));
        const emails = emailIndex >= 0
            ? lines.slice(1).map((line) => line.split(lines[0].includes("\t") ? "\t" : ",")[emailIndex]?.trim().toLowerCase()).filter(Boolean)
            : [];
        const uniqueEmails = new Set(emails);
        setImportSummary(lines.length > 1 ? {
            rows: lines.length - 1,
            newRows: [...uniqueEmails].filter((email) => !existing.has(email)).length,
            duplicates: emails.length - uniqueEmails.size + [...uniqueEmails].filter((email) => existing.has(email)).length,
            columns: header,
        } : null);
    }

    function startAdding() {
        setAdding(true);
        setAddEmail("");
        setAddValues(Object.fromEntries(detectedVariables.map((variable) => [variable, ""])));
        showMessage("");
    }

    async function saveNewRecipient() {
        if (!addEmail.trim()) {
            showMessage("Email is required.", "error");
            return;
        }
        try {
            setSavingAdd(true);
            const created = await api<Recipient>(`/api/campaigns/${campaign.id}/recipients`, {
                method: "POST",
                body: JSON.stringify({ email: addEmail.trim(), values: addValues }),
            });
            setRecipients((current) => [...current, created]);
            await refreshCampaign();
            setAdding(false);
            showMessage("Recipient added.");
        } catch (error) {
            showMessage(error instanceof Error ? error.message : "Could not add recipient.", "error");
        } finally {
            setSavingAdd(false);
        }
    }

    function startEditing(recipient: Recipient) {
        setEditingRecipient(recipient);
        setEditEmail(recipient.email);
        setEditValues({ ...recipient.values });
        setMessage("");
    }

    function cancelEditing() {
        setEditingRecipient(null);
        setEditEmail("");
        setEditValues({});
    }

    async function saveRecipient() {
        if (!editingRecipient) {
            return;
        }

        if (!editEmail.trim()) {
            setMessage("Email is required.");
            return;
        }

        try {
            setSavingEdit(true);
            setMessage("");

            const updated = await api<Recipient>(
                `/api/recipients/${editingRecipient.id}`,
                {
                    method: "PATCH",
                    body: JSON.stringify({
                        email: editEmail.trim(),
                        values: editValues,
                    }),
                },
            );

            setRecipients((current) =>
                current.map((recipient) =>
                    recipient.id === updated.id ? updated : recipient,
                ),
            );

            await refreshCampaign();

            setEditingRecipient(null);
            setEditEmail("");
            setEditValues({});
            showMessage("Recipient updated.");
        } catch (error) {
            showMessage(
                error instanceof Error
                    ? error.message
                    : "Could not update recipient.",
            );
        } finally {
            setSavingEdit(false);
        }
    }

    async function deleteRecipient(recipientId: number) {
        const recipient = recipients.find(
            (item) => item.id === recipientId,
        );

        if (!recipient) {
            return;
        }

        try {
            setDeletingId(recipientId);
            setMessage("");

            await api(`/api/recipients/${recipientId}`, {
                method: "DELETE",
            });

            setRecipients((current) =>
                current.filter((item) => item.id !== recipientId),
            );

            await refreshCampaign();

            if (editingRecipient?.id === recipientId) {
                cancelEditing();
            }

            setDeleteTarget(null);
            showMessage("Recipient deleted.");
        } catch (error) {
            showMessage(
                error instanceof Error
                    ? error.message
                    : "Could not delete recipient.",
            );
        } finally {
            setDeletingId(null);
        }
    }

    async function importRecipients() {
        if (!text.trim()) {
            setMessage("Paste recipient data first.");
            return;
        }

        try {
            setImporting(true);
            setMessage("");

            const result = await api<ImportResult>(
                `/api/campaigns/${campaign.id}/recipients/import`,
                {
                    method: "POST",
                    body: JSON.stringify({ text }),
                },
            );

            setText("");
            setImportSummary(null);
            await loadRecipients();
            await refreshCampaign();
            setImportOpen(false);

            showMessage(
                `${result.inserted} recipient${result.inserted === 1 ? "" : "s"
                } imported.${result.ignored_duplicates
                    ? ` ${result.ignored_duplicates} duplicate${result.ignored_duplicates === 1 ? "" : "s"
                    } ignored.`
                    : ""
                }`,
            );
        } catch (error) {
            setMessage(
                error instanceof Error
                    ? error.message
                    : "Could not import recipients.",
            );
        } finally {
            setImporting(false);
        }
    }

    async function retryFailed() {
        try {
            setRetryingFailed(true);
            setMessage("");

            const result = await api<{ reset: number }>(
                `/api/campaigns/${campaign.id}/recipients/retry-failed`,
                {
                    method: "POST",
                },
            );

            await loadRecipients();
            await refreshCampaign();

            showMessage(
                `${result.reset} failed recipient${result.reset === 1 ? "" : "s"} reset to pending.`,
            );
        } catch (error) {
            setMessage(
                error instanceof Error
                    ? error.message
                    : "Could not retry failed recipients.",
            );
        } finally {
            setRetryingFailed(false);
        }
    }

    async function resolveInterrupted(
        recipientId: number,
        retry: boolean,
    ) {
        try {
            setResolvingId(recipientId);
            setMessage("");

            await api(
                `/api/recipients/${recipientId}/resolve`,
                {
                    method: "POST",
                    body: JSON.stringify({
                        retry,
                    }),
                },
            );

            await loadRecipients();

            setMessage(
                retry
                    ? "Recipient reset to pending."
                    : "Recipient marked as sent.",
            );
        } catch (error) {
            setMessage(
                error instanceof Error
                    ? error.message
                    : "Could not resolve interrupted recipient.",
            );
        } finally {
            setResolvingId(null);
        }
    }

    async function handleFile(event: ChangeEvent<HTMLInputElement>) {
        const file = event.target.files?.[0];

        if (!file) {
            return;
        }

        try {
            const contents = await file.text();
            setText(contents);
            parseImport(contents);
            showMessage(`Loaded ${file.name}. Review the data, then import it.`);
        } catch {
            showMessage("Could not read the selected file.", "error");
        } finally {
            event.target.value = "";
        }
    }

    return (
        <section className="mx-auto w-full max-w-5xl px-4 py-10 sm:px-6">
            <header className="mt-8">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-neutral-500">
                    Recipients
                </p>

                <div className="mt-3 flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
                    <div>
                        <h1 className="text-4xl font-semibold tracking-tight">
                            {campaign.name}
                        </h1>

                        <p className="mt-3 text-sm text-neutral-600">
                            {recipients.length} recipient
                            {recipients.length === 1 ? "" : "s"}
                        </p>
                    </div>
                </div>
                <div className="mt-6 flex flex-wrap gap-2">
                    {detectedVariables.length > 0 ? detectedVariables.map((variable) => (
                        <span key={variable} className="rounded-full bg-neutral-100 px-3 py-1 text-xs text-neutral-600">
                            {`{{${variable}}}`}
                        </span>
                    )) : <span className="text-sm text-neutral-500">No template variables detected yet.</span>}
                </div>
            </header>

            {message && (
                <p
                    role="status"
                    className={`mt-5 border-t pt-4 text-sm ${messageKind === "error" ? "border-red-200 text-red-700" : "border-neutral-200 text-neutral-600"}`}
                >
                    {message}
                </p>
            )}

            <section className="mt-10">
                {loading ? (
                    <p className="text-sm text-neutral-500">
                        Loading recipients...
                    </p>
                ) : recipients.length === 0 ? (
                    <div>
                        <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-5">
                            {(["all", "pending", "sent", "failed", "interrupted"] as const).map((status) => (
                                <div key={status} className="border border-neutral-200 bg-white p-3 text-left">
                                    <span className="block text-xs uppercase tracking-wide text-neutral-500">{status}</span>
                                    <span className="mt-1 block text-lg font-semibold">{status === "all" ? 0 : 0}</span>
                                </div>
                            ))}
                        </div>
                        <div className="mb-5 flex flex-col gap-3 sm:flex-row">
                            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search email or variable values" className="flex-1 border border-neutral-300 bg-white px-3 py-3 text-sm outline-none focus:border-neutral-900" />
                            <button type="button" onClick={() => { setQuery(""); setStatusFilter("all"); }} className="border border-neutral-300 bg-white px-4 py-3 text-sm font-medium hover:bg-neutral-50">Clear filters</button>
                        </div>
                        <div className="border border-dashed border-neutral-300 bg-white p-10 text-center">
                            <h2 className="text-lg font-medium">No recipients yet</h2>
                            <p className="mt-2 text-sm text-neutral-500">Add one recipient or import a CSV to get started.</p>
                            {editable && (
                                <div className="mt-5 flex flex-wrap justify-center gap-3">
                                    <button type="button" onClick={startAdding} className="border border-neutral-900 bg-neutral-900 px-4 py-3 text-sm font-medium text-white">Add recipient</button>
                                    <button type="button" onClick={() => setImportOpen(true)} className="border border-neutral-300 bg-white px-4 py-3 text-sm font-medium">Import CSV</button>
                                </div>
                            )}
                        </div>
                        {adding && (
                            <div className="fixed inset-0 z-30 flex items-center justify-center overflow-y-auto bg-neutral-900/30 p-4">
                                <div role="dialog" aria-modal="true" className="w-full max-w-md border border-neutral-300 bg-white p-6 shadow-xl">
                                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-neutral-500">Add recipient</p>
                                <label className="mt-5 block text-sm font-medium">Email</label>
                                <input type="email" value={addEmail} onChange={(event) => setAddEmail(event.target.value)} autoFocus className="mt-2 w-full border border-neutral-300 px-3 py-3 text-sm outline-none focus:border-neutral-900" />
                                {detectedVariables.length > 0 && (
                                    <div className="mt-5 space-y-4">
                                        <p className="text-sm font-medium">Recipient variables</p>
                                        {detectedVariables.map((key) => (
                                            <label key={key} className="block text-sm text-neutral-600">
                                                {key}
                                                <input
                                                    type="text"
                                                    value={addValues[key] ?? ""}
                                                    onChange={(event) => setAddValues((current) => ({ ...current, [key]: event.target.value }))}
                                                    className="mt-2 w-full border border-neutral-300 px-3 py-3 text-sm text-neutral-900 outline-none focus:border-neutral-900"
                                                />
                                            </label>
                                        ))}
                                    </div>
                                )}
                                <div className="mt-4 flex gap-3">
                                    <button type="button" onClick={() => void saveNewRecipient()} disabled={savingAdd} className="border border-neutral-900 bg-neutral-900 px-4 py-3 text-sm font-medium text-white disabled:opacity-50">{savingAdd ? "Adding..." : "Add recipient"}</button>
                                    <button type="button" onClick={() => setAdding(false)} className="border border-neutral-300 bg-white px-4 py-3 text-sm font-medium">Cancel</button>
                                </div>
                                </div>
                            </div>
                        )}
                    </div>
                ) : (
                    <>
                        <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-5">
                            {(["all", "pending", "sent", "failed", "interrupted"] as const).map((status) => (
                                <button key={status} type="button" onClick={() => setStatusFilter(status)}
                                    className={`border p-3 text-left ${statusFilter === status ? "border-neutral-900 bg-neutral-900 text-white" : "border-neutral-200 bg-white hover:border-neutral-400"}`}>
                                    <span className="block text-xs uppercase tracking-wide opacity-70">{status}</span>
                                    <span className="mt-1 block text-lg font-semibold">{status === "all" ? recipients.length : statusCounts[status] ?? 0}</span>
                                </button>
                            ))}
                        </div>
                        <div className="mb-5 flex flex-col gap-3 sm:flex-row">
                            <label className="flex-1">
                                <span className="sr-only">Search recipients</span>
                                <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search email or variable values"
                                    className="w-full border border-neutral-300 bg-white px-3 py-3 text-sm outline-none focus:border-neutral-900" />
                            </label>
                            <button type="button" onClick={() => { setQuery(""); setStatusFilter("all"); }}
                                className="border border-neutral-300 bg-white px-4 py-3 text-sm font-medium hover:bg-neutral-50">Clear filters</button>
                        </div>
                        {recipients.some(
                            (recipient) => recipient.status === "failed",
                        ) && (
                                <div className="mb-5 flex items-center justify-between gap-4 border-t border-neutral-200 pt-5">
                                    <p className="text-sm text-neutral-500">
                                        Some recipients failed during sending.
                                    </p>

                                    <button
                                        type="button"
                                        onClick={() => void retryFailed()}
                                        disabled={
                                            retryingFailed ||
                                            campaign.state === "running"
                                        }
                                        className="border border-neutral-300 bg-white px-4 py-3 text-sm font-medium hover:bg-neutral-50 disabled:cursor-not-allowed disabled:opacity-50"
                                    >
                                        {retryingFailed
                                            ? "Retrying..."
                                            : "Retry failed"}
                                    </button>
                                </div>
                            )}

                        <div className="mb-5 flex flex-wrap justify-between gap-3">
                            {editable && (
                                <button type="button" onClick={startAdding} className="border border-neutral-300 bg-white px-4 py-3 text-sm font-medium hover:bg-neutral-50">
                                    Add recipient
                                </button>
                            )}
                            {editable && (
                                <button type="button" onClick={() => setImportOpen(true)} className="border border-neutral-300 bg-white px-4 py-3 text-sm font-medium hover:bg-neutral-50">
                                    Import CSV
                                </button>
                            )}
                            <button
                                type="button"
                                onClick={() => onPreview(campaign)}
                                disabled={campaign.state === "running"}
                                className="border border-neutral-900 bg-neutral-900 px-4 py-3 text-sm font-medium text-white hover:bg-neutral-800 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                                Preview campaign
                            </button>
                        </div>

                        {adding && (
                            <div className="fixed inset-0 z-30 flex items-center justify-center overflow-y-auto bg-neutral-900/30 p-4">
                            <section role="dialog" aria-modal="true" className="w-full max-w-md border border-neutral-300 bg-white p-6 shadow-xl">
                                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-neutral-500">Add recipient</p>
                                <label className="mt-5 block text-sm font-medium">Email</label>
                                <input
                                    type="email"
                                    value={addEmail}
                                    onChange={(event) => setAddEmail(event.target.value)}
                                    className="mt-2 w-full border border-neutral-300 px-3 py-3 text-sm outline-none focus:border-neutral-900"
                                    autoFocus
                                />
                                {detectedVariables.length > 0 && (
                                    <div className="mt-5 space-y-4">
                                        <p className="text-sm font-medium">Recipient variables</p>
                                        {detectedVariables.map((key) => (
                                            <div key={key}>
                                                <label className="block text-sm text-neutral-600">{key}</label>
                                                <input
                                                    value={addValues[key] ?? ""}
                                                    onChange={(event) => setAddValues((current) => ({ ...current, [key]: event.target.value }))}
                                                    className="mt-2 w-full border border-neutral-300 px-3 py-3 text-sm outline-none focus:border-neutral-900"
                                                />
                                            </div>
                                        ))}
                                    </div>
                                )}
                                <div className="mt-6 flex gap-3">
                                    <button type="button" onClick={() => void saveNewRecipient()} disabled={savingAdd || !editable} className="border border-neutral-900 bg-neutral-900 px-4 py-3 text-sm font-medium text-white disabled:opacity-50">{savingAdd ? "Adding..." : "Add recipient"}</button>
                                    <button type="button" onClick={() => setAdding(false)} disabled={savingAdd} className="border border-neutral-300 bg-white px-4 py-3 text-sm font-medium">Cancel</button>
                                </div>
                            </section>
                            </div>
                        )}

                        {editingRecipient && (
                            <section className="mb-5 border border-neutral-300 bg-white p-6 sm:p-8">
                                <div className="flex items-start justify-between gap-4">
                                    <div>
                                        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-neutral-500">
                                            Edit recipient
                                        </p>

                                        <h2 className="mt-3 text-base font-semibold">
                                            Recipient details
                                        </h2>
                                    </div>

                                    <button
                                        type="button"
                                        onClick={cancelEditing}
                                        className="text-sm text-neutral-500 hover:text-neutral-900"
                                    >
                                        Cancel
                                    </button>
                                </div>

                                <div className="mt-6">
                                    <label className="block text-sm font-medium">
                                        Email
                                    </label>

                                    <input
                                        type="email"
                                        value={editEmail}
                                        onChange={(event) => setEditEmail(event.target.value)}
                                        className="mt-2 w-full border border-neutral-300 px-3 py-3 text-sm outline-none focus:border-neutral-900"
                                    />
                                </div>

                                {Object.keys(editValues).length > 0 && (
                                    <div className="mt-6 space-y-4">
                                        <p className="text-sm font-medium">
                                            Variables
                                        </p>

                                        {Object.entries(editValues).map(([key, value]) => (
                                            <div key={key}>
                                                <label className="block text-sm text-neutral-600">
                                                    {key}
                                                </label>

                                                <input
                                                    type="text"
                                                    value={value}
                                                    onChange={(event) =>
                                                        setEditValues((current) => ({
                                                            ...current,
                                                            [key]: event.target.value,
                                                        }))
                                                    }
                                                    className="mt-2 w-full border border-neutral-300 px-3 py-3 text-sm outline-none focus:border-neutral-900"
                                                />
                                            </div>
                                        ))}
                                    </div>
                                )}

                                <div className="mt-6 flex gap-3">
                                    <button
                                        type="button"
                                        onClick={() => void saveRecipient()}
                                        disabled={savingEdit || campaign.state === "running"}
                                        className="border border-neutral-900 bg-neutral-900 px-4 py-3 text-sm font-medium text-white hover:bg-neutral-800 disabled:cursor-not-allowed disabled:opacity-50"
                                    >
                                        {savingEdit ? "Saving..." : "Save recipient"}
                                    </button>

                                    <button
                                        type="button"
                                        onClick={cancelEditing}
                                        disabled={savingEdit}
                                        className="border border-neutral-300 bg-white px-4 py-3 text-sm font-medium hover:bg-neutral-50 disabled:cursor-not-allowed disabled:opacity-50"
                                    >
                                        Cancel
                                    </button>
                                </div>
                            </section>
                        )}

                        <div className="overflow-x-auto border-y border-neutral-200 bg-white">
                            <table className="w-full min-w-170 border-collapse text-left">
                                <thead>
                                    <tr className="border-b border-neutral-200 text-xs uppercase tracking-wide text-neutral-500">
                                        <th className="px-5 py-4 font-medium">
                                            Email
                                        </th>

                                        <th className="px-5 py-4 font-medium">
                                            Variables
                                        </th>

                                        <th className="px-5 py-4 font-medium">
                                            Status
                                        </th>

                                        <th className="px-5 py-4 font-medium">
                                            Actions
                                        </th>

                                    </tr>
                                </thead>

                                <tbody>
                                    {visibleRecipients.map((recipient) => (
                                        <tr
                                            key={recipient.id}
                                            className="border-b border-neutral-100 last:border-0"
                                        >
                                            <td className="px-5 py-4 text-sm">
                                                {recipient.email}
                                            </td>

                                            <td className="px-5 py-4 text-sm text-neutral-500">
                                                {Object.keys(recipient.values).length}
                                            </td>

                                            <td className="px-5 py-4 text-xs font-medium uppercase tracking-wide text-neutral-500">
                                                {recipient.status}
                                            </td>

                                            <td className="px-5 py-4">
                                                <div className="flex flex-wrap gap-2">
                                                    {editable && (
                                                        <button
                                                            type="button"
                                                            onClick={() => startEditing(recipient)}
                                                            className="border border-neutral-300 bg-white px-3 py-2 text-xs font-medium hover:bg-neutral-50"
                                                        >
                                                            Edit
                                                        </button>
                                                    )}

                                                    {editable && (
                                                        <button
                                                            type="button"
                                                            onClick={() => setDeleteTarget(recipient)}
                                                            disabled={deletingId === recipient.id}
                                                            className="border border-neutral-300 bg-white px-3 py-2 text-xs font-medium text-red-700 hover:bg-neutral-50 disabled:cursor-not-allowed disabled:opacity-50"
                                                        >
                                                            {deletingId === recipient.id ? "Deleting..." : "Delete"}
                                                        </button>
                                                    )}

                                                    {recipient.status === "interrupted" && (
                                                        <>
                                                            <button
                                                                type="button"
                                                                onClick={() =>
                                                                    void resolveInterrupted(recipient.id, true)
                                                                }
                                                                disabled={resolvingId === recipient.id}
                                                                className="border border-neutral-300 bg-white px-3 py-2 text-xs font-medium hover:bg-neutral-50 disabled:opacity-50"
                                                            >
                                                                Retry
                                                            </button>

                                                            <button
                                                                type="button"
                                                                onClick={() =>
                                                                    void resolveInterrupted(recipient.id, false)
                                                                }
                                                                disabled={resolvingId === recipient.id}
                                                                className="border border-neutral-900 bg-neutral-900 px-3 py-2 text-xs font-medium text-white hover:bg-neutral-800 disabled:opacity-50"
                                                            >
                                                                Mark as sent
                                                            </button>
                                                        </>
                                                    )}
                                                </div>
                                            </td>

                                        </tr>
                                    ))}
                                    {visibleRecipients.length === 0 && (
                                        <tr><td colSpan={4} className="px-5 py-10 text-center text-sm text-neutral-500">No recipients match these filters.</td></tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </>
                )}
            </section>

            {importOpen && (
                <div className="fixed inset-0 z-20 flex items-center justify-center overflow-y-auto bg-neutral-900/30 p-4">
                    <div role="dialog" aria-modal="true" className="max-h-[calc(100vh-2rem)] w-full max-w-2xl overflow-y-auto border border-neutral-300 bg-white p-6 shadow-xl">
                        <h2 className="text-lg font-semibold">Import recipients</h2>
                        <p className="mt-2 text-sm leading-6 text-neutral-600">
                            Paste CSV or tab-separated data. The email column is required.
                        </p>
                        <textarea
                            value={text}
                            onChange={(event) => {
                                setText(event.target.value);
                                parseImport(event.target.value);
                            }}
                            rows={9}
                            placeholder={"email,Name,Company\nalice@example.com,Alice,Acme"}
                            className="mt-5 w-full resize-y border border-neutral-300 px-3 py-3 font-mono text-sm leading-6 outline-none focus:border-neutral-900"
                        />
                        {importSummary && (
                            <div className="mt-4 border border-neutral-200 bg-neutral-50 p-4 text-sm text-neutral-700">
                                <p className="font-medium">
                                    {importSummary.rows} row{importSummary.rows === 1 ? "" : "s"} detected · {importSummary.newRows} new · {importSummary.duplicates} duplicate{importSummary.duplicates === 1 ? "" : "s"}
                                </p>
                                <p className="mt-1 text-xs text-neutral-500">Columns: {importSummary.columns.join(" · ") || "none"}</p>
                            </div>
                        )}
                        <div className="mt-4 flex flex-wrap justify-between gap-3">
                            <button type="button" onClick={() => fileInputRef.current?.click()} disabled={importing} className="border border-neutral-300 bg-white px-4 py-3 text-sm font-medium disabled:opacity-50">Choose CSV file</button>
                            <input ref={fileInputRef} type="file" accept=".csv,text/csv" className="hidden" onChange={handleFile} />
                            <div className="flex gap-3">
                                <button type="button" onClick={() => setImportOpen(false)} disabled={importing} className="border border-neutral-300 bg-white px-4 py-3 text-sm font-medium">Cancel</button>
                                <button type="button" onClick={importRecipients} disabled={importing || !text.trim()} className="border border-neutral-900 bg-neutral-900 px-4 py-3 text-sm font-medium text-white disabled:opacity-50">{importing ? "Importing..." : "Import recipients"}</button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
            {deleteTarget && (
                <div className="fixed inset-0 z-20 flex items-center justify-center overflow-y-auto bg-neutral-900/30 p-4">
                    <div role="dialog" aria-modal="true" className="max-h-[calc(100vh-2rem)] w-full max-w-md overflow-y-auto border border-neutral-300 bg-white p-6 shadow-xl">
                        <h2 className="text-lg font-semibold">Delete recipient?</h2>
                        <p className="mt-2 text-sm leading-6 text-neutral-600">
                            Remove <span className="font-medium">{deleteTarget.email}</span> from this campaign?
                        </p>
                        <div className="mt-6 flex justify-end gap-3">
                            <button type="button" onClick={() => setDeleteTarget(null)} className="border border-neutral-300 bg-white px-4 py-3 text-sm font-medium">Cancel</button>
                            <button type="button" onClick={() => void deleteRecipient(deleteTarget.id)} disabled={deletingId !== null} className="border border-red-700 bg-red-700 px-4 py-3 text-sm font-medium text-white disabled:opacity-50">{deletingId === deleteTarget.id ? "Deleting..." : "Delete recipient"}</button>
                        </div>
                    </div>
                </div>
            )}
        </section>
    );
}