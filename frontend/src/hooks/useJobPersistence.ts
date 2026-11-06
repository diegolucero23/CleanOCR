
import { useState, useCallback } from 'react';

// --- Types ---

export type JobStatus = 'queued' | 'processing' | 'completed' | 'failed' | 'cached' | 'cancelled' | 'partial_failure';

export interface PersistedJob {
    id: string;              // UUID from backend
    uploaded_filename: string; // Original filename
    status: JobStatus;
    progress: number;        // 0-100
    timestamp: number;       // Date.now() when created
    markdown?: string;       // The final output (cached locally)
    resultMessage?: string;  // Details from backend
    upload_time?: number;
    file_size?: number;
    processing_time?: number;
    complexity?: number;
    page_count?: number;         // from /upload expectations
    expected_seconds?: number;   // stream/processing budget disclosed at upload
}

interface StorageSchema {
    version: number;
    jobs: PersistedJob[];
}

const STORAGE_KEY = 'cleanocr_job_history_v1';
const MAX_HISTORY = 50;

/** Read saved jobs from localStorage; wipes and returns [] on bad or corrupt data. */
function loadHistory(): PersistedJob[] {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return [];

        const parsed: StorageSchema = JSON.parse(raw);

        // Basic Schema Validation
        if (parsed.version !== 1 || !Array.isArray(parsed.jobs)) {
            console.warn("[Persistence] Invalid schema detected. Resetting history.");
            localStorage.removeItem(STORAGE_KEY);
            return [];
        }

        // Sanitize: enforce that every entry has a valid, non-empty string ID
        const validJobs = parsed.jobs.filter((j): j is PersistedJob =>
            Boolean(j && typeof j === 'object' && typeof j.id === 'string' && j.id.trim().length > 0)
        );

        if (validJobs.length !== parsed.jobs.length) {
            console.warn(`[Persistence] Filtered out ${parsed.jobs.length - validJobs.length} malformed job(s) lacking an ID.`);
            try {
                localStorage.setItem(STORAGE_KEY, JSON.stringify({ version: 1, jobs: validJobs.slice(0, MAX_HISTORY) }));
            } catch {
                // Ignore storage write errors on startup sanitization
            }
        }

        console.log(`[Persistence] Restored ${validJobs.length} jobs from storage.`);
        return validJobs;
    } catch (e) {
        console.error("[Persistence] Failed to parse history:", e);
        localStorage.removeItem(STORAGE_KEY); // Wipe corrupt data
        return [];
    }
}

// --- Hook ---

export function useJobPersistence() {
    // 1. Load once, synchronously, on first render (lazy initializer, so no
    //    extra render from setting state in a mount effect).
    const [history, setHistory] = useState<PersistedJob[]>(loadHistory);


    // 2. Saver (Debounce wrapping not strictly needed if state updates are atomic, 
    // but we use a distinct save function to be explicit)
    const _saveToDisk = (jobs: PersistedJob[]) => {
        try {
            const payload: StorageSchema = {
                version: 1,
                jobs: jobs.slice(0, MAX_HISTORY) // Enforce Capacity
            };
            localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
        } catch (e) {
            console.error("[Persistence] writes failed (Quota?):", e);
            // Optional: Strategy to delete oldest 10 if quota exceeded
        }
    };

    // --- Public Actions ---

    const addOrUpdateJob = useCallback((job: PersistedJob) => {
        if (!job || typeof job.id !== 'string' || !job.id.trim()) {
            console.warn('[Persistence] Rejected job without valid id:', job);
            return;
        }

        setHistory(prev => {
            // Check if exists
            const existingIdx = prev.findIndex(j => j.id === job.id);
            let next: PersistedJob[];

            if (existingIdx >= 0) {
                // Update: Merge new data into old (preserve missing fields if any)
                next = [...prev];
                next[existingIdx] = { ...next[existingIdx], ...job };
            } else {
                // Add New to TOP
                next = [job, ...prev];
            }

            _saveToDisk(next);
            return next;
        });
    }, []);

    const clearHistory = useCallback(() => {
        setHistory([]);
        localStorage.removeItem(STORAGE_KEY);
    }, []);

    return {
        history,
        addOrUpdateJob,
        clearHistory
    };
}
