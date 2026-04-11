import axios from 'axios';

const API = axios.create({
    baseURL: '/api', // Proxied by Vite to localhost:8000
    headers: {
        'Accept': 'application/json',
    }
});

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
 * Subscribe to live job status updates via SSE.
 * Returns a cleanup function that closes the connection.
 *
 * The stream closes automatically on the server side when the job
 * reaches a terminal state (completed / failed), but the cleanup
 * function should still be called on unmount.
 */
export const subscribeToJobStatus = (
    jobId: string,
    onUpdate: (data: JobResponse) => void,
    onError?: (err: Event) => void,
): (() => void) => {
    const source = new EventSource(`/api/stream/${jobId}`);

    source.onmessage = (event) => {
        try {
            const data: JobResponse = JSON.parse(event.data);
            onUpdate(data);
            if (data.status === 'completed' || data.status === 'failed') {
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
