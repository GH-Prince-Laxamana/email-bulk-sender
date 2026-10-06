export type ApiError = {
    error: {
        code: string;
        message: string;
        retry_after?: number;
    };
};

function getToken(): string {
    const fragment = window.location.hash.replace(/^#/, "");
    const params = new URLSearchParams(fragment);
    return params.get("token") ?? "";
}

export async function api<T>(
    path: string,
    options: RequestInit = {},
): Promise<T> {
    const token = getToken();

    if (!token) {
        throw new Error("Missing application token.");
    }

    const headers = new Headers(options.headers);
    headers.set("X-App-Token", token);

    if (options.body && !headers.has("Content-Type")) {
        headers.set("Content-Type", "application/json");
    }

    const response = await fetch(path, {
        ...options,
        headers,
    });

    const data = await response.json().catch(() => null);

    if (!response.ok) {
        const error = data as ApiError | null;

        throw new Error(
            error?.error?.message ?? `Request failed (${response.status}).`,
        );
    }

    return data as T;
}