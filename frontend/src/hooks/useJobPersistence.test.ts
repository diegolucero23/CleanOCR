// @vitest-environment jsdom
/**
 * useJobPersistence loads saved history with a lazy useState initializer
 * (not a mount effect), so the very first render already has the jobs.
 */
import { renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useJobPersistence } from './useJobPersistence';

const KEY = 'cleanocr_job_history_v1';

afterEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
});

describe('useJobPersistence', () => {
    it('restores saved jobs on the first render', () => {
        localStorage.setItem(KEY, JSON.stringify({ version: 1, jobs: [{ id: 'a' }, { id: 'b' }] }));
        vi.spyOn(console, 'log').mockImplementation(() => {});
        const { result } = renderHook(() => useJobPersistence());
        expect(result.current.history.map((j) => j.id)).toEqual(['a', 'b']);
    });

    it('wipes corrupt storage and starts empty', () => {
        localStorage.setItem(KEY, '{not json');
        vi.spyOn(console, 'error').mockImplementation(() => {});
        const { result } = renderHook(() => useJobPersistence());
        expect(result.current.history).toEqual([]);
        expect(localStorage.getItem(KEY)).toBeNull();
    });

    it('wipes data with the wrong schema version', () => {
        localStorage.setItem(KEY, JSON.stringify({ version: 2, jobs: [] }));
        vi.spyOn(console, 'warn').mockImplementation(() => {});
        const { result } = renderHook(() => useJobPersistence());
        expect(result.current.history).toEqual([]);
        expect(localStorage.getItem(KEY)).toBeNull();
    });
});
