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
