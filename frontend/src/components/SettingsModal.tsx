import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Key, ShieldCheck, Eye, EyeOff, X, Save, Check } from 'lucide-react';
import { getActiveApiKey, setActiveApiKey } from '../lib/api';

interface SettingsModalProps {
    isOpen: boolean;
    onClose: () => void;
}

export function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
    const [apiKey, setApiKey] = useState('');
    const [showKey, setShowKey] = useState(false);
    const [savedSuccess, setSavedSuccess] = useState(false);

    useEffect(() => {
        if (isOpen) {
            setApiKey(getActiveApiKey() || '');
            setSavedSuccess(false);
        }
    }, [isOpen]);

    const handleSave = (e: React.FormEvent) => {
        e.preventDefault();
        setActiveApiKey(apiKey);
        setSavedSuccess(true);
        setTimeout(() => {
            setSavedSuccess(false);
            onClose();
        }, 800);
    };

    const handleClear = () => {
        setApiKey('');
        setActiveApiKey(null);
        setSavedSuccess(true);
        setTimeout(() => {
            setSavedSuccess(false);
        }, 1200);
    };

    return (
        <AnimatePresence>
            {isOpen && (
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    onClick={onClose}
                    className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
                >
                    <motion.div
                        initial={{ scale: 0.95, opacity: 0, y: 10 }}
                        animate={{ scale: 1, opacity: 1, y: 0 }}
                        exit={{ scale: 0.95, opacity: 0, y: 10 }}
                        onClick={(e) => e.stopPropagation()}
                        className="bg-card border border-border w-full max-w-md rounded-2xl shadow-2xl overflow-hidden"
                    >
                        {/* Header */}
                        <div className="p-5 border-b border-border flex justify-between items-center bg-muted/20">
                            <div className="flex items-center gap-2.5">
                                <div className="p-2 bg-primary/10 rounded-lg text-primary">
                                    <Key className="w-5 h-5" />
                                </div>
                                <div>
                                    <h2 className="text-lg font-semibold tracking-tight">Security & Access</h2>
                                    <p className="text-xs text-muted-foreground">Configure your CleanOCR API Key</p>
                                </div>
                            </div>
                            <button
                                onClick={onClose}
                                className="text-muted-foreground hover:text-foreground p-1 rounded-md hover:bg-muted/50 transition-colors"
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        {/* Form */}
                        <form onSubmit={handleSave} className="p-6 space-y-5">
                            <div className="space-y-2">
                                <div className="flex justify-between items-center">
                                    <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                                        <ShieldCheck className="w-3.5 h-3.5 text-primary" />
                                        API Key
                                    </label>
                                    <span className="text-[10px] text-muted-foreground font-mono">
                                        {apiKey ? 'Configured' : 'Open Dev Mode'}
                                    </span>
                                </div>

                                <div className="relative">
                                    <input
                                        type={showKey ? 'text' : 'password'}
                                        value={apiKey}
                                        onChange={(e) => setApiKey(e.target.value)}
                                        placeholder="Paste your CleanOCR API key..."
                                        className="w-full px-3.5 py-2.5 pr-10 rounded-lg border border-border bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary transition-all font-mono"
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowKey(!showKey)}
                                        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground p-1 rounded transition-colors"
                                        tabIndex={-1}
                                    >
                                        {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                    </button>
                                </div>
                                <p className="text-xs text-muted-foreground leading-relaxed">
                                    Leave blank for local development if <code className="text-[11px] bg-muted px-1 py-0.5 rounded">CLEANOCR_API_KEY</code> is unset in the backend. When configured, this key is automatically attached to all requests.
                                </p>
                            </div>

                            <div className="flex items-center justify-between pt-3 border-t border-border">
                                <button
                                    type="button"
                                    onClick={handleClear}
                                    className="text-xs text-muted-foreground hover:text-destructive transition-colors font-medium"
                                >
                                    Clear Stored Key
                                </button>
                                <div className="flex items-center gap-2">
                                    <button
                                        type="button"
                                        onClick={onClose}
                                        className="px-3.5 py-2 text-xs font-medium rounded-lg border border-border hover:bg-muted transition-colors"
                                    >
                                        Cancel
                                    </button>
                                    <button
                                        type="submit"
                                        className="px-4 py-2 text-xs font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 flex items-center gap-1.5 shadow-sm transition-all"
                                    >
                                        {savedSuccess ? (
                                            <>
                                                <Check className="w-3.5 h-3.5" />
                                                <span>Saved!</span>
                                            </>
                                        ) : (
                                            <>
                                                <Save className="w-3.5 h-3.5" />
                                                <span>Save Key</span>
                                            </>
                                        )}
                                    </button>
                                </div>
                            </div>
                        </form>
                    </motion.div>
                </motion.div>
            )}
        </AnimatePresence>
    );
}
