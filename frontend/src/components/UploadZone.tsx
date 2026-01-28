import { useState, useCallback } from 'react';
import { Upload, FileWarning } from 'lucide-react';
import { cn } from '../lib/utils';
import { motion, AnimatePresence } from 'framer-motion';

interface UploadZoneProps {
    onFileSelect: (file: File) => void;
    isUploading: boolean;
}

export function UploadZone({ onFileSelect, isUploading }: UploadZoneProps) {
    const [isDragOver, setIsDragOver] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragOver(true);
    }, []);

    const handleDragLeave = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragOver(false);
    }, []);

    const validateFile = (file: File) => {
        if (file.type !== 'application/pdf') {
            setError('Only PDF files are allowed.');
            return false;
        }
        setError(null);
        return true;
    };

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragOver(false);

        const file = e.dataTransfer.files[0];
        if (file && validateFile(file)) {
            onFileSelect(file);
        }
    }, [onFileSelect]);

    const handleBrowse = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file && validateFile(file)) {
            onFileSelect(file);
        }
    };

    return (
        <div className="w-full max-w-xl mx-auto">
            <motion.div
                layout
                className={cn(
                    "relative flex flex-col items-center justify-center w-full h-64 border-2 border-dashed rounded-xl transition-colors cursor-pointer overflow-hidden",
                    isDragOver ? "border-primary bg-primary/10" : "border-border bg-card/50 hover:bg-card/80",
                    error ? "border-destructive/50 bg-destructive/10" : "",
                    isUploading ? "opacity-50 pointer-events-none" : ""
                )}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                whileHover={{ scale: 1.01 }}
                whileTap={{ scale: 0.99 }}
            >
                <input
                    type="file"
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                    onChange={handleBrowse}
                    accept=".pdf"
                    disabled={isUploading}
                />

                <AnimatePresence mode="wait">
                    {error ? (
                        <motion.div
                            key="error"
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -10 }}
                            className="flex flex-col items-center text-destructive"
                        >
                            <FileWarning className="w-12 h-12 mb-4" />
                            <p className="text-lg font-medium">{error}</p>
                            <p className="text-sm">Please upload a valid PDF file.</p>
                        </motion.div>
                    ) : (
                        <motion.div
                            key="default"
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -10 }}
                            className="flex flex-col items-center text-muted-foreground"
                        >
                            <div className={cn(
                                "p-4 rounded-full bg-background mb-4 transition-transform duration-500",
                                isDragOver ? "scale-110" : ""
                            )}>
                                <Upload className="w-8 h-8 text-primary" />
                            </div>
                            <p className="text-lg font-medium mb-1">
                                <span className="text-primary">Click to upload</span> or drag and drop
                            </p>
                            <p className="text-sm">PDF files only (max 50MB)</p>
                        </motion.div>
                    )}
                </AnimatePresence>
            </motion.div>
        </div>
    );
}
