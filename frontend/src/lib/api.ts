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
}

export const uploadFile = async (file: File): Promise<JobResponse> => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await API.post('/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
};

export const pollJobStatus = async (jobId: string): Promise<JobResponse> => {
    const response = await API.get<JobResponse>(`/status/${jobId}`);
    return response.data;
};
