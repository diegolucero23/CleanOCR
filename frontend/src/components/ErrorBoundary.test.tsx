// @vitest-environment jsdom
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { ErrorBoundary } from './ErrorBoundary';

function ProblemChild(): never {
    throw new Error('Simulated explosive render error');
}

afterEach(() => {
    cleanup();
});

describe('ErrorBoundary', () => {
    it('catches render errors and displays recovery UI instead of blank screen', () => {
        const spy = vi.spyOn(console, 'error').mockImplementation(() => {});

        render(
            <ErrorBoundary>
                <ProblemChild />
            </ErrorBoundary>
        );

        expect(screen.getByText('Application Render Error')).toBeTruthy();
        expect(screen.getByText(/Simulated explosive render error/)).toBeTruthy();
        expect(screen.getByText('Reload Application')).toBeTruthy();
        expect(screen.getByText('Clear Cache & Reload')).toBeTruthy();

        spy.mockRestore();
    });

    it('clears localStorage on Clear Cache & Reload click', () => {
        const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
        localStorage.setItem('cleanocr_job_history_v1', 'corrupt_data');

        render(
            <ErrorBoundary>
                <ProblemChild />
            </ErrorBoundary>
        );

        const clearBtn = screen.getByText('Clear Cache & Reload');
        fireEvent.click(clearBtn);

        expect(localStorage.getItem('cleanocr_job_history_v1')).toBeNull();
        spy.mockRestore();
    });
});
