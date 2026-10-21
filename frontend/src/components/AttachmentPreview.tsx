import { useEffect, useState } from "react";
import { attachmentBlob } from "../api";

type Props = {
    endpoint: string;
    filename: string;
};

export default function AttachmentPreview({ endpoint, filename }: Props) {
    const [file, setFile] = useState<{ url: string; text?: string } | null>(null);
    const [error, setError] = useState("");
    const extension = filename.split(".").pop()?.toLowerCase() ?? "";
    const imageType = ({ png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg", gif: "image/gif", webp: "image/webp" } as Record<string, string>)[extension];
    const isText = ["txt", "csv", "tsv", "json", "log", "md"].includes(extension);

    useEffect(() => {
        let cancelled = false;
        let url: string | undefined;
        void attachmentBlob(endpoint).then(async (blob) => {
            const text = isText ? await blob.text() : undefined;
            if (cancelled) return;
            url = URL.createObjectURL(new Blob([blob], { type: imageType || (extension === "pdf" ? "application/pdf" : "application/octet-stream") }));
            setFile({ url, text });
        }).catch((err) => {
            if (!cancelled) setError(err instanceof Error ? err.message : "Could not load file.");
        });
        return () => {
            cancelled = true;
            if (url) URL.revokeObjectURL(url);
        };
    }, [endpoint, extension, imageType, isText]);

    if (error) return <p role="alert" className="mt-3 text-sm text-red-700">{error} Close and reopen the preview to retry.</p>;
    if (!file) return <p role="status" className="mt-3 text-sm text-neutral-600">Loading file…</p>;

    return <div className="mt-3">
        <a href={file.url} download={filename} className="text-sm font-medium underline underline-offset-4">Download {filename}</a>
        {imageType ? <img src={file.url} alt={filename} className="mt-3 max-h-96 max-w-full object-contain" />
            : extension === "pdf" ? <iframe title={filename} src={file.url} className="mt-3 h-128 w-full border border-neutral-200" />
                : isText ? <pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap break-words bg-neutral-50 p-4 text-sm">{file.text}</pre>
                    : <p className="mt-3 text-sm text-neutral-600">Download this file to review it in its usual application.</p>}
    </div>;
}
