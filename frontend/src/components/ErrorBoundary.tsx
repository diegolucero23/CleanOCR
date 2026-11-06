import React, { Component, type ReactNode } from 'react';
import { AlertTriangle, RotateCcw, Trash2 } from 'lucide-react';

interface ErrorBoundaryProps {
    children: ReactNode;
}

interface ErrorBoundaryState {
    hasError: boolean;
    error: Error | null;
    showDetails: boolean;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
    constructor(props: ErrorBoundaryProps) {
        super(props);
        this.state = {
            hasError: false,
            error: null,
            showDetails: false,
        };
    }

    static getDerivedStateFromError(error: Error): ErrorBoundaryState {
        return {
            hasError: true,
            error,
            showDetails: false,
        };
    }

    componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
        console.error('[ErrorBoundary] Uncaught React render error:', error, errorInfo);
    }

    handleReset = (): void => {
        this.setState({ hasError: false, error: null, showDetails: false });
        window.location.reload();
    };

    handleClearCacheAndReload = (): void => {
        try {
            localStorage.removeItem('cleanocr_job_history_v1');
            sessionStorage.clear();
        } catch (e) {
            console.error('[ErrorBoundary] Failed to clear local storage:', e);
        }
        window.location.reload();
    };

    render(): ReactNode {
        if (this.state.hasError) {
            return (
                <div className="min-h-screen bg-background text-foreground flex items-center justify-center p-4">
                    <div className="w-full max-w-lg bg-card/80 border border-destructive/30 rounded-2xl p-6 sm:p-8 shadow-2xl backdrop-blur-md space-y-6 text-center animate-in fade-in zoom-in-95 duration-200">
                        <div className="w-14 h-14 mx-auto rounded-full bg-destructive/10 border border-destructive/20 flex items-center justify-center text-destructive">
                            <AlertTriangle className="w-7 h-7" />
                        </div>

                        <div className="space-y-2">
                            <h2 className="text-xl font-bold tracking-tight text-foreground">
                                Application Render Error
                            </h2>
                            <p className="text-sm text-muted-foreground leading-relaxed">
                                CleanOCR encountered an unexpected client error while rendering. Your database records remain safe on the backend.
                            </p>
                        </div>

                        {this.state.error && (
                            <div className="text-left bg-muted/40 border border-border/80 rounded-lg p-3 text-xs font-mono overflow-hidden">
                                <div className="text-destructive font-semibold truncate">
                                    {this.state.error.name}: {this.state.error.message}
                                </div>
                                {this.state.showDetails && this.state.error.stack && (
                                    <pre className="mt-2 text-[10px] text-muted-foreground whitespace-pre-wrap max-h-40 overflow-y-auto pt-2 border-t border-border/60">
                                        {this.state.error.stack}
                                    </pre>
                                )}
                                <button
                                    onClick={() => this.setState((prev) => ({ showDetails: !prev.showDetails }))}
                                    className="mt-2 text-[10px] text-primary hover:underline font-sans cursor-pointer"
                                >
                                    {this.state.showDetails ? 'Hide technical details' : 'Show technical details'}
                                </button>
                            </div>
                        )}

                        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
                            <button
                                onClick={this.handleReset}
                                className="w-full sm:w-auto px-4 py-2 text-xs font-semibold rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-all inline-flex items-center justify-center gap-1.5 shadow-sm"
                            >
                                <RotateCcw className="w-3.5 h-3.5" />
                                <span>Reload Application</span>
                            </button>
                            <button
                                onClick={this.handleClearCacheAndReload}
                                className="w-full sm:w-auto px-4 py-2 text-xs font-medium rounded-lg border border-border hover:bg-muted text-muted-foreground hover:text-foreground transition-all inline-flex items-center justify-center gap-1.5"
                            >
                                <Trash2 className="w-3.5 h-3.5" />
                                <span>Clear Cache & Reload</span>
                            </button>
                        </div>
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}

