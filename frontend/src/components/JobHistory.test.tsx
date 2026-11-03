// @vitest-environment jsdom
/**
 * Regression: a failing GET /jobs must surface ONE error, not a toast storm.
 *
 * App.tsx passes `onError` as an inline arrow, so every App render creates a
 * new function. When loadJobs depended on onError, each error toast re-rendered
 * App, recreated loadJobs, re-ran the effect, and fetched again, flooding the
 * page with "History Notice: Network error" toasts while the backend was down.
 */
import { useState } from 'react';
import { cleanup, render, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('../lib/api', async (importOriginal) => {
    const actual = await importOriginal<typeof import('../lib/api')>();
    return {
        ...actual,
        fetchJobs: vi.fn().mockRejectedValue(new Error('Network Error')),
        fetchJobDetail: vi.fn(),
    };
});

import { fetchJobs } from '../lib/api';
import { JobHistory } from './JobHistory';

/** Mirrors App.tsx: an inline onError that triggers a parent re-render. */
function AppLikeHost({ onToast }: { onToast: (msg: string) => void }) {
    const [, setToasts] = useState<string[]>([]);
    return (
        <JobHistory
            onSelectJob={() => {}}
            onError={(msg) => {
                onToast(msg);
                setToasts((prev) => [...prev, msg]);
            }}
        />
    );
}

afterEach(() => {
    cleanup();
    vi.mocked(fetchJobs).mockClear();
});

describe('JobHistory error handling', () => {
    it('fetches once and reports one error when the API is unreachable', async () => {
        const onToast = vi.fn();
        render(<AppLikeHost onToast={onToast} />);

        await waitFor(() => expect(onToast).toHaveBeenCalled());
        await new Promise((resolve) => setTimeout(resolve, 300));

        expect(vi.mocked(fetchJobs)).toHaveBeenCalledTimes(1);
        expect(onToast).toHaveBeenCalledTimes(1);
    });
});
