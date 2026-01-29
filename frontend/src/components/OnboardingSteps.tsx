import { FileText, Sparkles, UploadCloud, ChevronRight } from 'lucide-react';

export function OnboardingSteps() {
    return (
        <div className="w-full max-w-4xl mx-auto mb-12">
            <div className="flex flex-col md:flex-row items-center justify-between relative gap-8 md:gap-0">

                {/* Connector Line (Desktop) */}
                <div className="hidden md:block absolute top-1/2 left-0 w-full h-0.5 bg-gradient-to-r from-primary/20 via-primary/20 to-primary/20 -z-10 -translate-y-4" />

                {/* Step 1 */}
                <div className="flex flex-col items-center gap-4 bg-background p-4 relative z-10 w-full md:w-auto">
                    <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center text-primary shadow-sm ring-4 ring-background">
                        <UploadCloud className="w-6 h-6" />
                    </div>
                    <div className="text-center">
                        <h3 className="font-semibold">1. Upload PDF</h3>
                        <p className="text-xs text-muted-foreground w-32 mx-auto">Drag & drop any scanned document.</p>
                    </div>
                </div>

                {/* Arrow (Mobile) */}
                <ChevronRight className="md:hidden w-6 h-6 text-muted-foreground/50 rotate-90" />

                {/* Step 2 */}
                <div className="flex flex-col items-center gap-4 bg-background p-4 relative z-10 w-full md:w-auto">
                    <div className="w-12 h-12 rounded-full bg-blue-500/10 flex items-center justify-center text-blue-600 shadow-sm ring-4 ring-background">
                        <Sparkles className="w-6 h-6" />
                    </div>
                    <div className="text-center">
                        <h3 className="font-semibold">2. AI Extraction</h3>
                        <p className="text-xs text-muted-foreground w-32 mx-auto">OCR cleans and structures the text.</p>
                    </div>
                </div>

                {/* Arrow (Mobile) */}
                <ChevronRight className="md:hidden w-6 h-6 text-muted-foreground/50 rotate-90" />

                {/* Step 3 */}
                <div className="flex flex-col items-center gap-4 bg-background p-4 relative z-10 w-full md:w-auto">
                    <div className="w-12 h-12 rounded-full bg-green-500/10 flex items-center justify-center text-green-600 shadow-sm ring-4 ring-background">
                        <FileText className="w-6 h-6" />
                    </div>
                    <div className="text-center">
                        <h3 className="font-semibold">3. Get Markdown</h3>
                        <p className="text-xs text-muted-foreground w-32 mx-auto">View, diff, and export clean MD.</p>
                    </div>
                </div>

            </div>
        </div>
    );
}
