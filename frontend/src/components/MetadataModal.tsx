import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { BookOpen, Calendar, Database, FileText, Hash, X } from 'lucide-react';
import { cn } from '../lib/utils';

interface MetadataModalProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: (data: MetadataForm) => void;
    onSkip: () => void;
    filename: string;
}

export interface MetadataForm {
    title: string;
    volume: string;
    issue: string;
    date: string;
}

export function MetadataModal({ isOpen, onClose, onConfirm, onSkip, filename }: MetadataModalProps) {
    const [formData, setFormData] = useState<MetadataForm>({
        title: '',
        volume: '',
        issue: '',
        date: ''
    });

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        onConfirm(formData);
    };

    return (
        <AnimatePresence>
            {isOpen && (
                <>
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        onClick={onClose}
                        className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
                    >
                        <motion.div
                            initial={{ scale: 0.95, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ scale: 0.95, opacity: 0 }}
                            onClick={(e) => e.stopPropagation()}
                            className="bg-card border border-border w-full max-w-lg rounded-xl shadow-2xl overflow-hidden"
                        >
                            <div className="p-6 border-b border-border flex justify-between items-center bg-muted/30">
                                <div>
                                    <h2 className="text-xl font-semibold flex items-center gap-2">
                                        <Database className="w-5 h-5 text-primary" />
                                        Citation Metadata
                                    </h2>
                                    <p className="text-sm text-muted-foreground mt-1">
                                        For: <span className="font-mono text-xs bg-muted px-1 py-0.5 rounded">{filename}</span>
                                    </p>
                                </div>
                                <button onClick={onClose} className="p-2 hover:bg-muted rounded-full transition-colors">
                                    <X className="w-5 h-5" />
                                </button>
                            </div>

                            <form onSubmit={handleSubmit} className="p-6 space-y-4">
                                <div className="space-y-2">
                                    <label className="text-sm font-medium flex items-center gap-2">
                                        <BookOpen className="w-4 h-4 text-muted-foreground" />
                                        Publication Title
                                    </label>
                                    <input
                                        type="text"
                                        placeholder="e.g. The Messenger And Advocate"
                                        value={formData.title}
                                        onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                                        className="w-full p-2 rounded-md border border-input bg-background focus:outline-none focus:ring-2 focus:ring-primary/50"
                                        autoFocus
                                    />
                                    <p className="text-xs text-muted-foreground">This will replace the header of the Markdown file.</p>
                                </div>

                                <div className="grid grid-cols-2 gap-4">
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium flex items-center gap-2">
                                            <Hash className="w-4 h-4 text-muted-foreground" />
                                            Volume (Opt)
                                        </label>
                                        <input
                                            type="text"
                                            placeholder="e.g. 1"
                                            value={formData.volume}
                                            onChange={(e) => setFormData({ ...formData, volume: e.target.value })}
                                            className="w-full p-2 rounded-md border border-input bg-background focus:outline-none focus:ring-2 focus:ring-primary/50"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium flex items-center gap-2">
                                            <FileText className="w-4 h-4 text-muted-foreground" />
                                            Issue (Opt)
                                        </label>
                                        <input
                                            type="text"
                                            placeholder="e.g. 3"
                                            value={formData.issue}
                                            onChange={(e) => setFormData({ ...formData, issue: e.target.value })}
                                            className="w-full p-2 rounded-md border border-input bg-background focus:outline-none focus:ring-2 focus:ring-primary/50"
                                        />
                                    </div>
                                </div>

                                <div className="space-y-2">
                                    <label className="text-sm font-medium flex items-center gap-2">
                                        <Calendar className="w-4 h-4 text-muted-foreground" />
                                        Publication Date/Range
                                    </label>
                                    <input
                                        type="text"
                                        placeholder="e.g. October 1844"
                                        value={formData.date}
                                        onChange={(e) => setFormData({ ...formData, date: e.target.value })}
                                        className="w-full p-2 rounded-md border border-input bg-background focus:outline-none focus:ring-2 focus:ring-primary/50"
                                    />
                                </div>

                                <div className="pt-4 flex gap-3">
                                    <button
                                        type="button"
                                        onClick={onSkip}
                                        className="flex-1 py-2 px-4 rounded-lg border border-border hover:bg-muted transition-colors text-muted-foreground text-sm font-medium"
                                    >
                                        Skip (Quick Upload)
                                    </button>
                                    <button
                                        type="submit"
                                        className={cn(
                                            "flex-[2] py-2 px-4 rounded-lg bg-primary text-primary-foreground font-medium hover:opacity-90 transition-opacity shadow-lg shadow-primary/25",
                                            !formData.title && "opacity-50 cursor-not-allowed"
                                        )}
                                        disabled={!formData.title}
                                    >
                                        Confirm & Process
                                    </button>
                                </div>
                            </form>
                        </motion.div>
                    </motion.div>
                </>
            )}
        </AnimatePresence>
    );
}
