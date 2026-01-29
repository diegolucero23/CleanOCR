import { useState, useCallback } from 'react';
import { Maximize2, Minimize2, Download, ChevronLeft, ChevronRight, Loader2, ClipboardCopy, FileJson, X } from 'lucide-react';
import { motion } from 'framer-motion';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

// --- Worker Configuration for Vite ---
// Standard way to load worker in Vite without extra plugins
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

const SimpleButton = ({ children, onClick, className, disabled }: any) => (
    <button
        onClick={onClick}
        disabled={disabled}
        className={`px-3 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 ${className}`}
    >
        {children}
    </button>
);

interface DiffViewerProps {
    job_id?: string;
    markdown?: string;
    onClose: () => void;
}

// Basic parser to split markdown by page metadata
// Looks for "## METADATA ... **Page:** <Num>"
// Robust parser: Splits by the separator "----------" (10 dashes)
const parseMarkdownByPage = (md: string): Record<number, string> => {
    const pages: Record<number, string> = {};

    // Split by the separator used in stitch_to_markdown.py
    // We use a regex to handle potential whitespace around the dashes
    // We match a line that has at least 10 dashes
    const chunks = md.split(/\n-{10,}\s*\n/);

    let currentPage = 1;

    chunks.forEach(chunk => {
        // Line format: **Volume:** 1 | **Issue:** 1 | **Page:** 1
        // We look for "**Page:** <digits>" or "Page: <digits>"
        const pageMatch = chunk.match(/\*\*Page:\*\*\s*(\d+)/) || chunk.match(/Page:\s*(\d+)/);

        if (pageMatch) {
            currentPage = parseInt(pageMatch[1]);
            // Re-add the separator for visual consistency if desired, 
            // or just ensure the metadata block is clean.
            // We append the chunk to that page.
            pages[currentPage] = (pages[currentPage] || "") + "\n----------\n" + chunk;
        } else {
            // No page header found? It belongs to the PREVIOUS page (or Page 1 if at start)
            pages[currentPage] = (pages[currentPage] || "") + chunk;
        }
    });

    return pages;
};

export function DiffViewer({ job_id, markdown, onClose }: DiffViewerProps) {
    const [isFullscreen, setIsFullscreen] = useState(false);
    const [numPages, setNumPages] = useState<number>(0);
    const [pageNumber, setPageNumber] = useState<number>(1);
    const [scale, setScale] = useState(1.0);

    // Feature: Page Sync
    const [isSynced, setIsSynced] = useState(true);
    const [pageMap, setPageMap] = useState<Record<number, string>>({});

    // Parse markdown when it loads
    useState(() => {
        if (markdown) {
            setPageMap(parseMarkdownByPage(markdown));
        }
    });

    const onDocumentLoadSuccess = useCallback(({ numPages }: { numPages: number }) => {
        setNumPages(numPages);
    }, []);

    // Construct PDF URL
    // Nginx/Vite Proxy will route /uploads -> Backend
    const pdfUrl = job_id ? `/uploads/${job_id}.pdf` : null;

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            className={`fixed z-50 flex flex-col bg-background/95 backdrop-blur-sm border rounded-xl shadow-2xl overflow-hidden ${isFullscreen ? 'inset-0' : 'inset-4'}`}
        >
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b bg-card/50">
                <div className="flex items-center gap-4">
                    <h2 className="text-xl font-bold font-mono text-primary">Result Viewer</h2>
                    <span className="text-sm text-muted-foreground font-mono">
                        {job_id ? `ID: ${job_id.substring(0, 8)}...` : 'Preview'}
                    </span>

                    {/* Sync Toggle */}
                    <div className="flex items-center gap-2 bg-muted/50 p-1 rounded-lg border ml-4">
                        <button
                            onClick={() => setIsSynced(true)}
                            className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${isSynced ? 'bg-primary text-primary-foreground shadow-sm' : 'hover:bg-muted text-muted-foreground'}`}
                        >
                            Sync Page
                        </button>
                        <button
                            onClick={() => setIsSynced(false)}
                            className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${!isSynced ? 'bg-primary text-primary-foreground shadow-sm' : 'hover:bg-muted text-muted-foreground'}`}
                        >
                            Full Text
                        </button>
                    </div>
                </div>

                <div className="flex gap-2">
                    <SimpleButton onClick={() => {
                        navigator.clipboard.writeText(markdown || "");
                        // Optional: Add toast notification here
                    }}>
                        <ClipboardCopy className="w-4 h-4" /> Copy
                    </SimpleButton>

                    <SimpleButton onClick={() => {
                        const blob = new Blob([markdown || ""], { type: "text/markdown" });
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement("a");
                        a.href = url;
                        a.download = `${job_id || "result"}.md`;
                        a.click();
                    }}>
                        <Download className="w-4 h-4" /> MD
                    </SimpleButton>

                    {/* JSON Download */}
                    <button
                        onClick={() => {
                            // Reconstruct basic JSON structure since we don't have the full original response here easily
                            // unless we passed it. But we can dump what we have.
                            const data = { job_id, markdown, source: "CleanOCR Export" };
                            const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
                            const url = URL.createObjectURL(blob);
                            const a = document.createElement("a");
                            a.href = url;
                            a.download = `${job_id || "result"}.json`;
                            a.click();
                        }}
                        className="p-2 hover:bg-muted rounded-full text-muted-foreground hover:text-foreground"
                        title="Download Raw JSON"
                    >
                        <FileJson className="w-5 h-5" />
                    </button>

                    <div className="w-px h-6 bg-border mx-1 self-center" />

                    <button onClick={() => setIsFullscreen(!isFullscreen)} className="p-2 hover:bg-muted rounded-full">
                        {isFullscreen ? <Minimize2 className="w-5 h-5" /> : <Maximize2 className="w-5 h-5" />}
                    </button>
                    <button onClick={onClose} className="p-2 hover:bg-muted rounded-full text-muted-foreground" aria-label="Close">
                        <X className="w-5 h-5" />
                    </button>
                </div>
            </div>

            {/* Split View */}
            <div className="flex-1 flex gap-4 p-4 min-h-0">

                {/* Left: PDF Viewer */}
                <div className="flex-1 rounded-lg border bg-muted/20 flex flex-col overflow-hidden relative group">
                    {/* Controls */}
                    <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-10 flex items-center gap-2 bg-background/80 backdrop-blur rounded-full px-4 py-2 shadow-lg border">
                        <button
                            onClick={() => setPageNumber(p => Math.max(1, p - 1))}
                            disabled={pageNumber <= 1}
                            className="p-1 hover:bg-primary/20 rounded disabled:opacity-30"
                            title="Previous Page"
                        >
                            <ChevronLeft className="w-4 h-4" />
                        </button>
                        <span className="text-xs font-mono w-16 text-center">{pageNumber} / {numPages || '-'}</span>
                        <button
                            onClick={() => setPageNumber(p => Math.min(numPages, p + 1))}
                            disabled={pageNumber >= numPages}
                            className="p-1 hover:bg-primary/20 rounded disabled:opacity-30"
                            title="Next Page"
                        >
                            <ChevronRight className="w-4 h-4" />
                        </button>

                        <div className="w-px h-4 bg-border/50 mx-2" />

                        <button
                            onClick={() => setScale(s => Math.max(0.5, s - 0.1))}
                            className="text-xs font-mono hover:text-primary px-1"
                            title="Zoom Out"
                        >
                            -
                        </button>
                        <span className="text-xs font-mono w-12 text-center">{Math.round(scale * 100)}%</span>
                        <button
                            onClick={() => setScale(s => Math.min(2.5, s + 0.1))}
                            className="text-xs font-mono hover:text-primary px-1"
                            title="Zoom In"
                        >
                            +
                        </button>
                    </div>

                    <div className="flex-1 overflow-auto flex items-center justify-center bg-zinc-900/5">
                        {pdfUrl ? (
                            <Document
                                file={pdfUrl}
                                onLoadSuccess={onDocumentLoadSuccess}
                                loading={
                                    <div className="flex flex-col items-center gap-2 text-muted-foreground">
                                        <Loader2 className="w-8 h-8 animate-spin text-primary" />
                                        <span>Loading PDF...</span>
                                    </div>
                                }
                                error={
                                    <div className="text-destructive text-sm text-center p-4">
                                        Failed to load PDF.<br />
                                        Is the Backend running?
                                    </div>
                                }
                                className="shadow-lg"
                            >
                                <Page
                                    pageNumber={pageNumber}
                                    scale={scale}
                                    width={isFullscreen ? undefined : 500}
                                    className="shadow-xl"
                                    renderTextLayer={false}
                                    renderAnnotationLayer={false}
                                />
                            </Document>
                        ) : (
                            <p className="text-muted-foreground">No PDF Loaded</p>
                        )}
                    </div>
                </div>

                {/* Right: Markdown */}
                <div className="flex-1 rounded-lg border bg-card overflow-auto relative">
                    {/* Copy Button could go here */}
                    <pre className="p-6 text-sm font-mono whitespace-pre-wrap text-foreground leading-relaxed">
                        {isSynced
                            ? (pageMap[pageNumber] || `[No parsed content found for Page ${pageNumber}]`)
                            : (markdown || "No content extracted.")
                        }
                    </pre>
                </div>
            </div>
        </motion.div>
    );
}
