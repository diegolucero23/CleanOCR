import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertCircle, Clock, Key, CheckCircle, Info, X } from 'lucide-react';
import { cn } from '../lib/utils';

export interface ToastNotification {
    id: string;
    type: 'error' | 'warning' | 'info' | 'success';
    title: string;
    message: string;
    code?: string;
    actionLabel?: string;
    onAction?: () => void;
    retryAfterSeconds?: number;
    durationMs?: number;
}

interface NotificationToastProps {
    notifications: ToastNotification[];
    onDismiss: (id: string) => void;
}

export function NotificationToastContainer({ notifications, onDismiss }: NotificationToastProps) {
    return (
        <div className="fixed z-50 pointer-events-none flex flex-col gap-2.5 top-4 sm:top-auto sm:bottom-6 inset-x-4 sm:inset-x-auto sm:right-6 sm:max-w-md w-auto">
            <AnimatePresence mode="sync">
                {notifications.map((toast) => (
                    <SingleToast key={toast.id} toast={toast} onDismiss={() => onDismiss(toast.id)} />
                ))}
            </AnimatePresence>
        </div>
    );
}

function SingleToast({ toast, onDismiss }: { toast: ToastNotification; onDismiss: () => void }) {
    const [countdown, setCountdown] = useState<number | null>(toast.retryAfterSeconds ?? null);

    // Live countdown effect for rate limit (429) notifications
    useEffect(() => {
        if (countdown === null || countdown <= 0) return;

        const timer = setInterval(() => {
            setCountdown((prev) => {
                if (prev === null || prev <= 1) {
                    clearInterval(timer);
                    return 0;
                }
                return prev - 1;
            });
        }, 1000);

        return () => clearInterval(timer);
    }, [countdown]);

    // Auto dismiss effect
    useEffect(() => {
        const timeout = toast.durationMs || (toast.retryAfterSeconds ? (toast.retryAfterSeconds + 2) * 1000 : 6000);
        const timer = setTimeout(() => {
            onDismiss();
        }, timeout);

        return () => clearTimeout(timer);
    }, [toast.durationMs, toast.retryAfterSeconds, onDismiss]);

    const isAuth = toast.code === 'UNAUTHORIZED';
    const isRateLimit = toast.code === 'RATE_LIMIT_EXCEEDED';

    return (
        <motion.div
            layout
            initial={{ opacity: 0, y: -16, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -16, scale: 0.95, transition: { duration: 0.2 } }}
            className={cn(
                "pointer-events-auto w-full p-4 rounded-xl border shadow-xl backdrop-blur-md bg-card/95 flex gap-3.5 items-start transition-all",
                toast.type === 'error' && !isRateLimit && "border-destructive/30 shadow-destructive/5",
                isRateLimit && "border-amber-500/40 shadow-amber-500/10 bg-amber-950/20",
                toast.type === 'success' && "border-emerald-500/30 shadow-emerald-500/5",
                toast.type === 'info' && "border-primary/30 shadow-primary/5"
            )}
            role="alert"
        >
            {/* Icon */}
            <div className={cn(
                "p-2 rounded-lg flex-shrink-0 mt-0.5",
                toast.type === 'error' && !isRateLimit && "bg-destructive/10 text-destructive",
                isRateLimit && "bg-amber-500/15 text-amber-500",
                isAuth && "bg-primary/10 text-primary",
                toast.type === 'success' && "bg-emerald-500/10 text-emerald-500",
                toast.type === 'info' && "bg-primary/10 text-primary"
            )}>
                {isRateLimit ? (
                    <Clock className="w-5 h-5 animate-pulse" />
                ) : isAuth ? (
                    <Key className="w-5 h-5" />
                ) : toast.type === 'error' ? (
                    <AlertCircle className="w-5 h-5" />
                ) : toast.type === 'success' ? (
                    <CheckCircle className="w-5 h-5" />
                ) : (
                    <Info className="w-5 h-5" />
                )}
            </div>

            {/* Body */}
            <div className="flex-1 min-w-0 pr-1">
                <div className="flex items-baseline justify-between gap-2">
                    <h4 className="text-sm font-semibold tracking-tight text-foreground truncate">
                        {toast.title}
                    </h4>
                    {isRateLimit && countdown !== null && countdown > 0 && (
                        <span className="text-[11px] font-mono font-medium px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/30">
                            {countdown}s remaining
                        </span>
                    )}
                </div>

                <p className="text-xs text-muted-foreground mt-1 leading-relaxed break-words">
                    {toast.message}
                </p>

                {/* Interactive Action Button */}
                {toast.actionLabel && toast.onAction && (
                    <button
                        onClick={() => {
                            toast.onAction?.();
                            onDismiss();
                        }}
                        className="mt-2.5 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-primary/10 text-primary hover:bg-primary/20 transition-colors focus:outline-none focus:ring-2 focus:ring-primary/40"
                    >
                        {isAuth && <Key className="w-3 h-3" />}
                        <span>{toast.actionLabel}</span>
                    </button>
                )}
            </div>

            {/* Close Button */}
            <button
                onClick={onDismiss}
                className="text-muted-foreground hover:text-foreground p-1 rounded-md hover:bg-muted/50 transition-colors flex-shrink-0"
                aria-label="Dismiss notification"
            >
                <X className="w-4 h-4" />
            </button>
        </motion.div>
    );
}
