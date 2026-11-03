import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
    Search,
    RefreshCw,
    ChevronLeft,
    ChevronRight,
    FileText,
    CheckCircle2,
    AlertCircle,
    Clock,
    Database,
    BookOpen,
    Loader2,
    X,
} from 'lucide-react';
import { apiErrorPayload, fetchJobs, fetchJobDetail, jobStatusQuery, type ApiError, type PersistedJobSummary } from '../lib/api';
import type { PersistedJob } from '../hooks/useJobPersistence';
import { cn } from '../lib/utils';

interface JobHistoryProps {
    onSelectJob: (job: PersistedJob) => void;
    onError?: (message: string, code?: string) => void;
    currentActiveJobId?: string | null;
}

type FilterStatus = 'all' | 'completed' | 'processing' | 'failed';

export function JobHistory({ onSelectJob, onError, currentActiveJobId }: JobHistoryProps) {
    const [jobs, setJobs] = useState<PersistedJobSummary[]>([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [statusFilter, setStatusFilter] = useState<FilterStatus>('all');
    const [searchTerm, setSearchTerm] = useState('');
    const [activeSearch, setActiveSearch] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [loadingJobId, setLoadingJobId] = useState<string | null>(null);

    const limit = 8;

    // Parents usually pass onError inline, so its identity changes every render.
    // Reading it through a ref keeps loadJobs stable; otherwise each error toast
    // re-rendered the parent, recreated loadJobs, re-ran the load effect, and
    // looped (one fetch + one toast per pass) for as long as the API was down.
    const onErrorRef = useRef(onError);
    useEffect(() => {
        onErrorRef.current = onError;
    }, [onError]);

    const loadJobs = useCallback(async (targetPage: number, status: FilterStatus, search: string) => {
        setIsLoading(true);
        try {
            const resp = await fetchJobs({
                page: targetPage,
                limit,
                status: jobStatusQuery(status),
                search: search.trim() ? search.trim() : undefined,
            });
            setJobs(resp.jobs || resp.items || []);
            setTotal(resp.total);
            setTotalPages(Math.max(1, resp.total_pages));
            setPage(resp.page);
        } catch (caught) {
            const err = caught as ApiError;
            console.error('[JobHistory] Failed to load jobs:', err);
            const status = err.response?.status;
            const msg = apiErrorPayload(err)?.message || err.message || 'Failed to load job history';
            onErrorRef.current?.(msg, status === 401 ? 'UNAUTHORIZED' : status === 429 ? 'RATE_LIMIT_EXCEEDED' : 'FETCH_ERROR');
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        loadJobs(page, statusFilter, activeSearch);
    }, [loadJobs, page, statusFilter, activeSearch]);

    // Handle Search input with debouncing or on Enter
    const handleSearchSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        setPage(1);
        setActiveSearch(searchTerm);
    };

    const handleClearSearch = () => {
        setSearchTerm('');
        setActiveSearch('');
        setPage(1);
    };

    const handleStatusTab = (status: FilterStatus) => {
        setStatusFilter(status);
        setPage(1);
    };

    const handleJobClick = async (summary: PersistedJobSummary) => {
        if (summary.status === 'failed') {
            return;
        }

        setLoadingJobId(summary.id);
        try {
            const detail = await fetchJobDetail(summary.id);
            const persistedJob: PersistedJob = {
                id: summary.id,
                uploaded_filename: summary.filename,
                status: summary.status,
                progress: summary.progress,
                timestamp: new Date(summary.created_at).getTime(),
                markdown: detail.markdown || '',
                resultMessage: summary.error_message || (summary.status === 'completed' ? 'Extraction completed' : undefined),
                file_size: summary.file_size_bytes,
                processing_time: summary.processing_time_seconds,
                page_count: summary.page_count,
            };
            onSelectJob(persistedJob);
        } catch (caught) {
            const err = caught as ApiError;
            console.error(`[JobHistory] Failed to fetch detail for ${summary.id}:`, err);
            const msg = apiErrorPayload(err)?.message || 'Could not load job details';
            onError?.(msg, 'DETAIL_FETCH_FAILED');
        } finally {
            setLoadingJobId(null);
        }
    };

    const formatBytes = (bytes?: number): string => {
        if (!bytes) return '—';
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    };

    const formatDate = (isoString: string): string => {
        try {
            const d = new Date(isoString);
            return d.toLocaleDateString(undefined, {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
            });
        } catch {
            return isoString;
        }
    };

    return (
        <div className="w-full space-y-4">
            {/* Control Bar: Filters, Search & Refresh */}
            <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between bg-card/60 backdrop-blur-md p-3.5 rounded-xl border border-border/80 shadow-sm">
                {/* Status Tabs */}
                <div className="flex items-center gap-1 overflow-x-auto pb-1 sm:pb-0 scrollbar-none">
                    {(['all', 'completed', 'processing', 'failed'] as FilterStatus[]).map((tab) => {
                        const isActive = statusFilter === tab;
                        return (
                            <button
                                key={tab}
                                onClick={() => handleStatusTab(tab)}
                                className={cn(
                                    "px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-all duration-150 whitespace-nowrap select-none",
                                    isActive
                                        ? "bg-primary text-primary-foreground shadow-sm"
                                        : "text-muted-foreground hover:text-foreground hover:bg-muted/70"
                                )}
                            >
                                {tab}
                            </button>
                        );
                    })}
                </div>

                {/* Search Bar & Refresh */}
                <div className="flex items-center gap-2">
                    <form onSubmit={handleSearchSubmit} className="relative flex-1 sm:w-64">
                        <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
                        <input
                            type="text"
                            placeholder="Search by filename or title..."
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            className="w-full pl-8 pr-7 py-1.5 text-xs rounded-lg border border-border bg-background/80 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary transition-all"
                        />
                        {searchTerm && (
                            <button
                                type="button"
                                onClick={handleClearSearch}
                                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground p-0.5 rounded"
                            >
                                <X className="w-3 h-3" />
                            </button>
                        )}
                    </form>

                    <button
                        onClick={() => loadJobs(page, statusFilter, activeSearch)}
                        disabled={isLoading}
                        title="Refresh Job History"
                        className="p-2 rounded-lg border border-border bg-background/60 hover:bg-muted text-muted-foreground hover:text-foreground transition-all disabled:opacity-50"
                    >
                        <RefreshCw className={cn("w-3.5 h-3.5", isLoading && "animate-spin text-primary")} />
                    </button>
                </div>
            </div>

            {/* List / Table Content */}
            <div className="bg-card/40 backdrop-blur-sm rounded-xl border border-border/80 overflow-hidden shadow-sm">
                {isLoading && jobs.length === 0 ? (
                    <div className="py-16 flex flex-col items-center justify-center gap-2 text-muted-foreground">
                        <Loader2 className="w-6 h-6 animate-spin text-primary" />
                        <span className="text-xs">Loading persistent history...</span>
                    </div>
                ) : jobs.length === 0 ? (
                    <div className="py-16 text-center space-y-2">
                        <Database className="w-8 h-8 mx-auto text-muted-foreground/50" />
                        <p className="text-sm font-medium text-foreground">No matching jobs found</p>
                        <p className="text-xs text-muted-foreground max-w-sm mx-auto">
                            {activeSearch
                                ? `No extraction jobs matched "${activeSearch}". Try clearing your search.`
                                : statusFilter === 'processing'
                                  ? 'No queued or processing jobs right now.'
                                  : statusFilter === 'all'
                                    ? 'No jobs recorded in the database yet. Upload a PDF to get started.'
                                    : `No ${statusFilter} jobs recorded in the database.`}
                        </p>
                    </div>
                ) : (
                    <div>
                        {/* Desktop Table View (>= 640px) */}
                        <div className="hidden sm:block overflow-x-auto">
                            <table className="w-full text-left text-xs">
                                <thead className="bg-muted/40 border-b border-border/60 text-muted-foreground font-medium uppercase tracking-wider text-[10px]">
                                    <tr>
                                        <th className="py-3 px-4">Job / Document</th>
                                        <th className="py-3 px-4">Citation Metadata</th>
                                        <th className="py-3 px-4">Status</th>
                                        <th className="py-3 px-4">Pages / Size</th>
                                        <th className="py-3 px-4">Timestamp</th>
                                        <th className="py-3 px-4 text-right">Action</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-border/40">
                                    {jobs.map((job) => {
                                        const isRunning = currentActiveJobId === job.id || ['queued', 'processing'].includes(job.status);
                                        const isViewing = loadingJobId === job.id;

                                        return (
                                            <tr
                                                key={job.id}
                                                className="hover:bg-muted/30 transition-colors group cursor-pointer"
                                                onClick={() => handleJobClick(job)}
                                            >
                                                <td className="py-3 px-4">
                                                    <div className="flex items-center gap-2.5">
                                                        <div className={cn(
                                                            "p-2 rounded-lg flex-shrink-0",
                                                            job.status === "completed" ? "bg-emerald-500/10 text-emerald-500" :
                                                            job.status === "failed" ? "bg-red-500/10 text-red-500" :
                                                            "bg-blue-500/10 text-primary"
                                                        )}>
                                                            {job.status === "completed" ? <CheckCircle2 className="w-4 h-4" /> :
                                                             job.status === "failed" ? <AlertCircle className="w-4 h-4" /> :
                                                             isRunning ? <Loader2 className="w-4 h-4 animate-spin text-primary" /> :
                                                             <FileText className="w-4 h-4" />}
                                                        </div>
                                                        <div className="min-w-0">
                                                            <div className="font-medium text-foreground truncate max-w-[200px]" title={job.filename}>
                                                                {job.filename}
                                                            </div>
                                                            <div className="text-[10px] font-mono text-muted-foreground">
                                                                {job.id.slice(0, 8)}...
                                                            </div>
                                                        </div>
                                                    </div>
                                                </td>

                                                <td className="py-3 px-4">
                                                    {job.metadata?.title ? (
                                                        <div className="min-w-0 max-w-[180px]">
                                                            <div className="truncate font-medium text-foreground flex items-center gap-1" title={job.metadata.title}>
                                                                <BookOpen className="w-3 h-3 text-muted-foreground flex-shrink-0" />
                                                                <span className="truncate">{job.metadata.title}</span>
                                                            </div>
                                                            {(job.metadata.volume || job.metadata.issue) && (
                                                                <span className="text-[10px] text-muted-foreground">
                                                                    Vol {job.metadata.volume || '—'}, Issue {job.metadata.issue || '—'}
                                                                </span>
                                                            )}
                                                        </div>
                                                    ) : (
                                                        <span className="text-muted-foreground/60 italic text-[11px]">No metadata</span>
                                                    )}
                                                </td>

                                                <td className="py-3 px-4">
                                                    <span className={cn(
                                                        "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium capitalize",
                                                        job.status === "completed" ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20" :
                                                        job.status === "failed" ? "bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20" :
                                                        "bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20"
                                                    )}>
                                                        {job.status}
                                                    </span>
                                                </td>

                                                <td className="py-3 px-4 text-muted-foreground">
                                                    <div>{job.page_count ? `${job.page_count} pgs` : '—'}</div>
                                                    <div className="text-[10px]">{formatBytes(job.file_size_bytes)}</div>
                                                </td>

                                                <td className="py-3 px-4 text-muted-foreground whitespace-nowrap">
                                                    <div className="flex items-center gap-1">
                                                        <Clock className="w-3 h-3 text-muted-foreground/70" />
                                                        <span>{formatDate(job.created_at)}</span>
                                                    </div>
                                                </td>

                                                <td className="py-3 px-4 text-right">
                                                    {job.status === "completed" && (
                                                        <button
                                                            onClick={(e) => {
                                                                e.stopPropagation();
                                                                handleJobClick(job);
                                                            }}
                                                            disabled={isViewing}
                                                            className="px-2.5 py-1 text-xs font-medium rounded-md bg-primary/10 text-primary hover:bg-primary/20 transition-colors inline-flex items-center gap-1 disabled:opacity-50"
                                                        >
                                                            {isViewing ? <Loader2 className="w-3 h-3 animate-spin" /> : 'View'}
                                                        </button>
                                                    )}
                                                </td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>

                        {/* Mobile Card List View (< 640px) */}
                        <div className="sm:hidden divide-y divide-border/50">
                            {jobs.map((job) => {
                                const isViewing = loadingJobId === job.id;
                                return (
                                    <div
                                        key={job.id}
                                        onClick={() => handleJobClick(job)}
                                        className="p-3.5 space-y-2.5 active:bg-muted/40 transition-colors"
                                    >
                                        <div className="flex items-start justify-between gap-2">
                                            <div className="flex items-center gap-2 min-w-0">
                                                <div className={cn(
                                                    "p-1.5 rounded-md flex-shrink-0",
                                                    job.status === "completed" ? "bg-emerald-500/10 text-emerald-500" :
                                                    job.status === "failed" ? "bg-red-500/10 text-red-500" :
                                                    "bg-blue-500/10 text-primary"
                                                )}>
                                                    {job.status === "completed" ? <CheckCircle2 className="w-4 h-4" /> :
                                                     job.status === "failed" ? <AlertCircle className="w-4 h-4" /> :
                                                     <FileText className="w-4 h-4" />}
                                                </div>
                                                <div className="min-w-0">
                                                    <h4 className="text-xs font-semibold text-foreground truncate" title={job.filename}>
                                                        {job.filename}
                                                    </h4>
                                                    <span className="text-[10px] font-mono text-muted-foreground">
                                                        {job.id.slice(0, 8)}
                                                    </span>
                                                </div>
                                            </div>

                                            <span className={cn(
                                                "px-2 py-0.5 rounded-full text-[10px] font-medium capitalize flex-shrink-0",
                                                job.status === "completed" ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" :
                                                job.status === "failed" ? "bg-red-500/10 text-red-600 dark:text-red-400" :
                                                "bg-blue-500/10 text-blue-600 dark:text-blue-400"
                                            )}>
                                                {job.status}
                                            </span>
                                        </div>

                                        {job.metadata?.title && (
                                            <div className="text-[11px] text-muted-foreground flex items-center gap-1 truncate bg-muted/30 px-2 py-1 rounded">
                                                <BookOpen className="w-3 h-3 flex-shrink-0 text-primary" />
                                                <span className="truncate">{job.metadata.title}</span>
                                            </div>
                                        )}

                                        <div className="flex items-center justify-between text-[10px] text-muted-foreground pt-1 border-t border-border/40">
                                            <span>{formatDate(job.created_at)}</span>
                                            <div className="flex items-center gap-2">
                                                <span>{job.page_count ? `${job.page_count} pgs` : ''}</span>
                                                {job.status === "completed" && (
                                                    <button
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            handleJobClick(job);
                                                        }}
                                                        disabled={isViewing}
                                                        className="text-primary font-medium hover:underline inline-flex items-center gap-1"
                                                    >
                                                        {isViewing && <Loader2 className="w-2.5 h-2.5 animate-spin" />}
                                                        View Text
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                )}

                {/* Pagination Controls */}
                <div className="flex items-center justify-between px-4 py-3 bg-muted/20 border-t border-border/60 text-xs">
                    <span className="text-muted-foreground text-[11px]">
                        Showing {jobs.length > 0 ? (page - 1) * limit + 1 : 0}–{Math.min(page * limit, total)} of {total} jobs
                    </span>

                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => setPage((p) => Math.max(1, p - 1))}
                            disabled={page <= 1 || isLoading}
                            className="p-1 rounded-md border border-border/80 hover:bg-muted text-foreground transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                            title="Previous Page"
                        >
                            <ChevronLeft className="w-4 h-4" />
                        </button>
                        <span className="text-[11px] font-medium text-foreground px-1.5">
                            Page {page} of {totalPages}
                        </span>
                        <button
                            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                            disabled={page >= totalPages || isLoading}
                            className="p-1 rounded-md border border-border/80 hover:bg-muted text-foreground transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                            title="Next Page"
                        >
                            <ChevronRight className="w-4 h-4" />
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
