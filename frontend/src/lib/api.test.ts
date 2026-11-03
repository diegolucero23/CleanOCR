/**
 * Contract tests for the GET /jobs and GET /jobs/{id} adapters.
 *
 * The backend (app/db/models.py to_summary_dict / to_detail_dict) returns
 * `job_id`, `original_filename`, `upload_time` (epoch seconds), etc. The UI
 * reads `id`, `filename`, `created_at`, ... A raw backend record left
 * `job.id` undefined and `job.id.slice()` crashed the whole app on load.
 */
import { describe, expect, it } from 'vitest';
import { jobStatusQuery, normalizeJobDetail, normalizeJobSummary, normalizeJobsList } from './api';

const backendSummary = {
    job_id: '0f420d4e-8c15-404b-993a-64802aa9291a',
    status: 'completed',
    original_filename: 'messenger_vol_1.pdf',
    file_size: 2048,
    total_pages: 10,
    processed_pages: 10,
    model_name: 'gemini-3.1-flash-lite',
    layout_type: 'multi_column',
    upload_time: 1730592000.5,
    end_time: 1730592060.5,
    duration_seconds: 60,
    complexity: 4.2,
    error_message: null,
    metadata: { title: 'Messenger', volume: '1', issue: '2', publication_date: '1834-10' },
    created_at: '2024-11-03T00:00:00+00:00',
};

describe('normalizeJobSummary', () => {
    it('maps backend field names to the UI contract', () => {
        const job = normalizeJobSummary(backendSummary);
        expect(job.id).toBe(backendSummary.job_id);
        expect(job.filename).toBe('messenger_vol_1.pdf');
        expect(job.page_count).toBe(10);
        expect(job.file_size_bytes).toBe(2048);
        expect(job.processing_time_seconds).toBe(60);
        expect(job.created_at).toBe('2024-11-03T00:00:00+00:00');
        expect(job.completed_at).toBe(new Date(1730592060500).toISOString());
        expect(job.metadata).toEqual({ title: 'Messenger', volume: '1', issue: '2', date: '1834-10' });
    });

    it('derives progress from processed and total pages', () => {
        expect(normalizeJobSummary({ ...backendSummary, status: 'processing', processed_pages: 3 }).progress).toBe(30);
        expect(normalizeJobSummary(backendSummary).progress).toBe(100);
        expect(normalizeJobSummary({ ...backendSummary, status: 'queued', total_pages: null, processed_pages: 0 }).progress).toBe(0);
    });

    it('falls back to upload_time when created_at is missing', () => {
        const job = normalizeJobSummary({ ...backendSummary, created_at: null });
        expect(job.created_at).toBe(new Date(1730592000500).toISOString());
    });

    it('passes through records already in the UI shape', () => {
        const uiShaped = { id: 'abc12345-0000', filename: 'a.pdf', status: 'failed', progress: 0, created_at: '2024-01-01T00:00:00Z' };
        const job = normalizeJobSummary(uiShaped);
        expect(job.id).toBe('abc12345-0000');
        expect(job.filename).toBe('a.pdf');
    });

    it('never yields an undefined id or filename', () => {
        const job = normalizeJobSummary({ status: 'failed' });
        expect(typeof job.id).toBe('string');
        expect(typeof job.filename).toBe('string');
    });
});

describe('normalizeJobsList', () => {
    it('reads items (or legacy jobs) and normalizes every record', () => {
        const list = normalizeJobsList({ items: [backendSummary], jobs: [backendSummary], total: 263, page: 1, limit: 8, total_pages: 33 });
        expect(list.jobs).toHaveLength(1);
        expect(list.jobs[0].id).toBe(backendSummary.job_id);
        expect(list.total).toBe(263);
        expect(list.total_pages).toBe(33);
    });

    it('tolerates a missing array', () => {
        expect(normalizeJobsList({ total: 0, page: 1, limit: 8, total_pages: 0 }).jobs).toEqual([]);
    });
});

describe('jobStatusQuery', () => {
    it('maps UI filter tabs to GET /jobs status values', () => {
        expect(jobStatusQuery('all')).toBeUndefined();
        expect(jobStatusQuery('processing')).toBe('active');
        expect(jobStatusQuery('completed')).toBe('completed');
        expect(jobStatusQuery('failed')).toBe('failed');
    });
});

describe('normalizeJobDetail', () => {
    it('exposes result.markdown_text as markdown', () => {
        const detail = normalizeJobDetail({ ...backendSummary, result: { markdown_text: '# Page 001', total_words: 3 } });
        expect(detail.id).toBe(backendSummary.job_id);
        expect(detail.markdown).toBe('# Page 001');
    });

    it('leaves markdown undefined when there is no result', () => {
        expect(normalizeJobDetail({ ...backendSummary, result: null }).markdown).toBeUndefined();
    });
});
