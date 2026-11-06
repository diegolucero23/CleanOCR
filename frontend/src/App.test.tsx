// @vitest-environment jsdom
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('react-pdf', () => ({
    Document: () => <div>Document</div>,
    Page: () => <div>Page</div>,
    pdfjs: { GlobalWorkerOptions: { workerSrc: '' } },
}));

import App from './App';

describe('App resiliency to corrupt localStorage', () => {
    beforeEach(() => {
        localStorage.clear();
    });

    it('renders cleanly without throwing when localStorage contains a job without an id', () => {
        localStorage.setItem('cleanocr_job_history_v1', JSON.stringify({
            version: 1,
            jobs: [
                {
                    // Malformed entry with no id
                    uploaded_filename: "trial-of-gen-r-t-burton-deseret-news.pdf",
                    status: "queued",
                    progress: 0,
                    timestamp: Date.now()
                },
                {
                    // Valid entry
                    id: "valid-job-id-1234-5678",
                    uploaded_filename: "valid.pdf",
                    status: "completed",
                    progress: 100,
                    timestamp: Date.now()
                }
            ]
        }));

        // Must render cleanly without throwing
        const { container } = render(<App />);
        expect(container).toBeTruthy();
        expect(screen.getByText(/CleanOCR/i)).toBeTruthy();
    });
});
