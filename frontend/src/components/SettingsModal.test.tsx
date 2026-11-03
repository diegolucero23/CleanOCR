// @vitest-environment jsdom
/** SettingsModal reloads the stored API key every time it opens. */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

let storedKey: string | null = 'first-key';
vi.mock('../lib/api', () => ({
    getActiveApiKey: () => storedKey,
    setActiveApiKey: vi.fn(),
}));

import { SettingsModal } from './SettingsModal';

afterEach(cleanup);

describe('SettingsModal', () => {
    it('shows the current stored key each time it is reopened', () => {
        const { rerender } = render(<SettingsModal isOpen onClose={() => {}} />);
        expect(screen.getByDisplayValue('first-key')).toBeTruthy();

        rerender(<SettingsModal isOpen={false} onClose={() => {}} />);
        storedKey = 'second-key';
        rerender(<SettingsModal isOpen onClose={() => {}} />);
        expect(screen.getByDisplayValue('second-key')).toBeTruthy();
    });
});
