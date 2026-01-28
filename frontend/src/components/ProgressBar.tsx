import { motion } from "framer-motion";
// import { cn } from "../lib/utils";

interface ProgressBarProps {
    progress: number; // 0 to 100
    status?: string;
}

export function ProgressBar({ progress, status }: ProgressBarProps) {
    return (
        <div className="w-full space-y-2">
            <div className="flex justify-between text-xs text-muted-foreground uppercase tracking-wider font-semibold">
                <span>Processing</span>
                <span>{Math.round(progress)}%</span>
            </div>
            <div className="h-2 w-full bg-secondary rounded-full overflow-hidden">
                <motion.div
                    className="h-full bg-primary"
                    initial={{ width: 0 }}
                    animate={{ width: `${progress}%` }}
                    transition={{ type: "spring", stiffness: 50, damping: 15 }}
                />
            </div>
            {status && (
                <motion.p
                    key={status}
                    initial={{ opacity: 0, y: 5 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="text-xs text-center text-primary/80"
                >
                    {status}
                </motion.p>
            )}
        </div>
    );
}
