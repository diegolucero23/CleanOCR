import { Archive, ArrowUp } from 'lucide-react';
import { motion } from 'framer-motion';

export function EmptyState() {
    return (
        <div className="flex flex-col items-center justify-center py-16 text-center space-y-4 opacity-50 select-none">
            <div className="relative">
                <div className="w-24 h-24 bg-muted rounded-full flex items-center justify-center mb-4">
                    <Archive className="w-10 h-10 text-muted-foreground" />
                </div>
                <motion.div
                    animate={{ y: [0, -10, 0] }}
                    transition={{ repeat: Infinity, duration: 2, ease: "easeInOut" }}
                    className="absolute -top-2 -right-2 bg-primary text-primary-foreground rounded-full p-2 shadow-lg"
                >
                    <ArrowUp className="w-4 h-4" />
                </motion.div>
            </div>

            <div className="max-w-xs mx-auto space-y-1">
                <h3 className="text-lg font-semibold text-foreground">No recent jobs</h3>
                <p className="text-sm text-muted-foreground">
                    Upload your first document above to start extracting text.
                </p>
            </div>
        </div>
    );
}
