import axios, { type AxiosError } from 'axios';

/** Structured error body returned by the CleanOCR API (see app/api/server.py). */
export interface ApiErrorPayload {
    error?: {
        code?: string;
        message?: string;
        details?: { retry_after_seconds?: number };
    };
}

/** What axios rejects with for a CleanOCR request; data may be plain text from a proxy. */
export type ApiError = AxiosError<ApiErrorPayload | string>;

/** The structured error body, or undefined when the server sent none (or plain text). */
export function apiErrorPayload(err: ApiError): ApiErrorPayload['error'] {
    const data = err.response?.data;
    return data && typeof data === 'object' ? data.error : undefined;
}

const API = axios.create({
    baseURL: '/api', // Proxied by Vite to localhost:8000
    headers: {
        'Accept': 'application/json',
    }
});

export const getActiveApiKey = (): string | null => {
    return localStorage.getItem('cleanocr_api_key') || (import.meta.env.VITE_API_KEY as string) || null;
};

export const setActiveApiKey = (key: string | null): void => {
    if (key && key.trim()) {
        localStorage.setItem('cleanocr_api_key', key.trim());
    } else {
        localStorage.removeItem('cleanocr_api_key');
    }
};

API.interceptors.request.use((config) => {
    const key = getActiveApiKey();
    if (key) {
        config.headers['X-API-Key'] = key;
    }
    return config;
});

export interface IngestionLimits {
    max_upload_mb: number;
    max_pdf_pages: number;
    max_page_pixels: number;
    render_dpi: number;
    accepted_types: string[];
    stream_base_budget_seconds: number;
    stream_page_budget_seconds: number;
}

export interface JobExpectations {
    page_count: number;
    estimated_max_processing_seconds: number;
    stream_timeout_seconds: number;
    limits: IngestionLimits;
}

export interface JobResponse {
    status: string;
    job_id: string;
    task_id?: string;
    message?: string;
    progress?: number;
    markdown?: string;
    upload_time?: number;
    file_size?: number;
    processing_time?: number;
    complexity?: number;
    expectations?: JobExpectations;
}

interface UploadMetadata {
    title: string;
    volume?: string;
    issue?: string;
    date?: string;
}

export const uploadFile = async (file: File, metadata?: UploadMetadata, skipMetadata = false): Promise<JobResponse> => {
    const formData = new FormData();
    formData.append('file', file);

    if (skipMetadata) {
        formData.append('skip_metadata', 'true');
    } else if (metadata) {
        formData.append('title', metadata.title);
        if (metadata.volume) formData.append('volume', metadata.volume);
        if (metadata.issue) formData.append('issue', metadata.issue);
        if (metadata.date) formData.append('date', metadata.date);
    }

    const response = await API.post('/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
};

export const pollJobStatus = async (jobId: string): Promise<JobResponse> => {
    const response = await API.get<JobResponse>(`/status/${jobId}`);
    return response.data;
};

/**
 * Fetch the server's ingestion limits (max upload size, page count,
 * page dimensions) and streaming budgets, so the UI can disclose them
 * before the user picks a file. Matches GET /limits on the backend.
 */
export const fetchLimits = async (): Promise<IngestionLimits> => {
    const response = await API.get<IngestionLimits>('/limits');
    return response.data;
};

/**
 * Subscribe to live job status updates via SSE.
 * Returns a cleanup function that closes the connection.
 *
 * The stream closes automatically on the server side when the job
 * reaches a terminal state (completed / failed) or when the stream's
 * time budget expires (status 'stream_timeout' — the job itself may
 * still be running; the caller should fall back to /status polling).
 * The cleanup function should still be called on unmount.
 */
export const subscribeToJobStatus = (
    jobId: string,
    onUpdate: (data: JobResponse) => void,
    onError?: (err: Event) => void,
): (() => void) => {
    const key = getActiveApiKey();
    const streamUrl = key ? `/api/stream/${jobId}?api_key=${encodeURIComponent(key)}` : `/api/stream/${jobId}`;
    const source = new EventSource(streamUrl);

    source.onmessage = (event) => {
        try {
            const data: JobResponse = JSON.parse(event.data);
            onUpdate(data);
            if (data.status === 'completed' || data.status === 'failed' || data.status === 'stream_timeout') {
                source.close();
            }
        } catch (e) {
            console.error(`SSE parse error for ${jobId}`, e);
        }
    };

    source.onerror = (err) => {
        onError?.(err);
        source.close();
    };

    return () => source.close();
};


export interface PersistedJobSummary {
    id: string;
    filename: string;
    status: 'queued' | 'processing' | 'completed' | 'failed' | 'cached';
    progress: number;
    page_count?: number;
    file_size_bytes?: number;
    processing_time_seconds?: number;
    created_at: string;
    completed_at?: string;
    error_message?: string;
    metadata?: {
        title?: string;
        volume?: string;
        issue?: string;
        date?: string;
    };
}

export interface JobsListResponse {
    total: number;
    page: number;
    limit: number;
    total_pages: number;
    jobs: PersistedJobSummary[];
    items?: PersistedJobSummary[];
}

// ---------------------------------------------------------------------------
// Backend -> UI adapters for GET /jobs and GET /jobs/{id}.
// The backend (app/db/models.py to_summary_dict / to_detail_dict) sends
// job_id, original_filename, total_pages, processed_pages, file_size,
// duration_seconds, upload_time/end_time (epoch seconds), metadata.publication_date
// and result.markdown_text. The UI components read the PersistedJobSummary
// shape above, so every record is normalized here before it reaches React.
// ---------------------------------------------------------------------------
type RawRecord = Record<string, unknown>;

const asString = (value: unknown): string | undefined =>
    typeof value === 'string' && value.length > 0 ? value : undefined;

const asNumber = (value: unknown): number | undefined =>
    typeof value === 'number' && Number.isFinite(value) ? value : undefined;

const epochToIso = (seconds: unknown): string | undefined => {
    const n = asNumber(seconds);
    return n === undefined ? undefined : new Date(n * 1000).toISOString();
};

export const normalizeJobSummary = (raw: RawRecord): PersistedJobSummary => {
    const status = (asString(raw.status) ?? 'failed') as PersistedJobSummary['status'];
    const totalPages = asNumber(raw.total_pages) ?? asNumber(raw.page_count);
    const processedPages = asNumber(raw.processed_pages);

    let progress = asNumber(raw.progress);
    if (progress === undefined) {
        if (status === 'completed' || status === 'cached') progress = 100;
        else if (totalPages && processedPages !== undefined) progress = Math.round((processedPages / totalPages) * 100);
        else progress = 0;
    }

    const rawMeta = (raw.metadata ?? null) as RawRecord | null;
    const metadata = rawMeta
        ? {
              title: asString(rawMeta.title),
              volume: asString(rawMeta.volume),
              issue: asString(rawMeta.issue),
              date: asString(rawMeta.date) ?? asString(rawMeta.publication_date),
          }
        : undefined;

    return {
        id: asString(raw.id) ?? asString(raw.job_id) ?? 'unknown-job',
        filename: asString(raw.filename) ?? asString(raw.original_filename) ?? 'Untitled document',
        status,
        progress,
        page_count: totalPages,
        file_size_bytes: asNumber(raw.file_size_bytes) ?? asNumber(raw.file_size),
        processing_time_seconds: asNumber(raw.processing_time_seconds) ?? asNumber(raw.duration_seconds),
        created_at: asString(raw.created_at) ?? epochToIso(raw.upload_time) ?? new Date(0).toISOString(),
        completed_at: asString(raw.completed_at) ?? epochToIso(raw.end_time),
        error_message: asString(raw.error_message),
        metadata,
    };
};

export const normalizeJobsList = (raw: RawRecord): JobsListResponse => {
    const records = (Array.isArray(raw.items) ? raw.items : Array.isArray(raw.jobs) ? raw.jobs : []) as RawRecord[];
    const jobs = records.map(normalizeJobSummary);
    return {
        total: asNumber(raw.total) ?? jobs.length,
        page: asNumber(raw.page) ?? 1,
        limit: asNumber(raw.limit) ?? jobs.length,
        total_pages: asNumber(raw.total_pages) ?? 0,
        jobs,
    };
};

export const normalizeJobDetail = (raw: RawRecord): PersistedJobSummary & { markdown?: string } => {
    const result = (raw.result ?? null) as RawRecord | null;
    return {
        ...normalizeJobSummary(raw),
        markdown: asString(raw.markdown) ?? (result ? asString(result.markdown_text) : undefined),
    };
};

// The Processing tab covers every in-flight job: the UI renders both `queued`
// and `processing` as running, so it asks the backend for status=active.
export const jobStatusQuery = (tab: 'all' | 'completed' | 'processing' | 'failed'): string | undefined =>
    tab === 'all' ? undefined : tab === 'processing' ? 'active' : tab;

export const fetchJobs = async (params?: {
    page?: number;
    limit?: number;
    status?: string;
    search?: string;
}): Promise<JobsListResponse> => {
    const response = await API.get<RawRecord>('/jobs', { params });
    return normalizeJobsList(response.data);
};

export const fetchJobDetail = async (jobId: string): Promise<PersistedJobSummary & { markdown?: string }> => {
    const response = await API.get<RawRecord>(`/jobs/${jobId}`);
    return normalizeJobDetail(response.data);
};
