import { useState } from 'react';
import { Maximize2, Minimize2, Download } from 'lucide-react';
import { motion } from 'framer-motion';

// Quick Button shim
const SimpleButton = ({ children, onClick, className }: any) => (
    <button onClick={onClick} className={`px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 transition-colors ${className}`}>
        {children}
    </button>
);

interface DiffViewerProps {
    pdfUrl?: string; // Kept for future
    markdown?: string;
    onClose: () => void;
}

export function DiffViewer({ markdown, onClose }: DiffViewerProps) {
    const [isFullscreen, setIsFullscreen] = useState(false);

    // Mock data for demo if empty
    const displayText = markdown || "# Processing Complete\n\nNo text generated yet.";

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            className={`fixed z-50 flex flex-col bg-background/95 backdrop-blur-sm border rounded-xl shadow-2xl overflow-hidden ${isFullscreen ? 'inset-0' : 'inset-4'}`}
        >
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b bg-card/50">
                <h2 className="text-xl font-bold font-mono text-primary">Result Viewer</h2>
                <div className="flex gap-2">
                    <SimpleButton onClick={() => alert("Download feature coming soon!")}>
                        <Download className="w-4 h-4 mr-2 inline" /> Download MD
                    </SimpleButton>
                    <button onClick={() => setIsFullscreen(!isFullscreen)} className="p-2 hover:bg-muted rounded-full">
                        {isFullscreen ? <Minimize2 className="w-5 h-5" /> : <Maximize2 className="w-5 h-5" />}
                    </button>
                    <button onClick={onClose} className="p-2 hover:bg-muted rounded-full" aria-label="Close">
                        <Minimize2 className="w-5 h-5 rotate-45" /> {/* Use as close icon */}
                    </button>
                </div>
            </div>

            {/* Split View */}
            <div className="flex-1 flex gap-4 p-4 min-h-0">
                {/* Left: Input (Placeholder for PDF Viewer) */}
                <div className="flex-1 rounded-lg border bg-muted/20 flex items-center justify-center relative overflow-hidden group">
                    <div className="text-center p-6">
                        <p className="text-muted-foreground mb-2">Original PDF View</p>
                        <p className="text-xs text-muted-foreground/50">(PDF Rendering requires robust react-pdf setup)</p>
                    </div>
                </div>

                {/* Right: Output (Markdown) */}
                <div className="flex-1 rounded-lg border bg-card overflow-auto relative">
                    <pre className="p-4 text-sm font-mono whitespace-pre-wrap text-foreground">
                        {displayText}
                    </pre>
                </div>
            </div>
        </motion.div>
    );
}
