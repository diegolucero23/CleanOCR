# Phase 4: The "Wow" Finish (PDF Viewer)

## Goal
Implement a fully functional Side-by-Side view where the user can see the original PDF (served from backend) next to the Markdown output.

## Proposed Changes

### 1. Backend: Serve Static Files (@Architect)
#### [MODIFY] [server.py](file:///c:/Users/dluce/Projects/CleanOCR/server.py)
- Import `StaticFiles` from `fastapi.staticfiles`.
- Mount `/uploads` to `StaticFiles(directory="uploads")`.
- **Security Note:** Allow CORS if needed (Vite proxy handles this, but good to know).

### 2. Frontend: Install & Configure (@Engineer)
- **Command:** `npm install react-pdf`
- **Asset Handling:** Copy `pdf.worker.min.js` or configure `vite-plugin-static-copy` if strictly needed, but `esm` import usually works in Vite.
- **Config:** `pdfjs.GlobalWorkerOptions.workerSrc = new URL('pdfjs-dist/build/pdf.worker.min.mjs', import.meta.url).toString();`

### 3. Frontend: Component Implementation (@Designer)
#### [MODIFY] [DiffViewer.tsx](file:///c:/Users/dluce/Projects/CleanOCR/frontend/src/components/DiffViewer.tsx)
- Replace placeholder with `<Document>` and `<Page>` from `react-pdf`.
- Add simple pagination controls (Prev/Next).
- **Style:** Ensure PDF fits container width.

## Verification Plan
### Manual Verification
1.  Upload PDF.
2.  Wait for completion.
3.  Open Diff Viewer.
4.  **Confirm:** PDF renders on left, Markdown on right.
