# RedTeam Campaign 1: Input Fuzzing

**Date:** 2026-01-29
**Target:** `http://localhost:8001/upload`
**Agent:** @RedTeam

## 1. Objectives
Attempt to crash the server or exploit filesystem logic using malformed inputs.

## 2. Attack Vectors & Results

| Vector | Payload | Expected | Actual | Verdict |
| :--- | :--- | :--- | :--- | :--- |
| **Magic Header Spoofing** | Text file (`This is not a PDF`) renamed to `.pdf` | 400 Bad Request | 400 Bad Request | ✅ **SAFE** (Blocked by `python-magic`) |
| **Zero-Byte File** | Empty content | 400 Bad Request | 400 Bad Request | ✅ **SAFE** (Blocked by Empty Check) |
| **Path Traversal** | Filename: `../../etc/passwd.pdf` | 400 Bad Request | **200 OK** | ⚠️ **NEUTERED** (See Analysis) |
| **Buffer Overflow** | 10MB Header Blob | 400 Bad Request | 400 Bad Request | ✅ **SAFE** (Blocked by Header Parser) |

## 3. Deep Dive: Path Traversal
The server returned **200 OK** for `../../etc/passwd.pdf`.
*   **Hypothesis:** Vulnerability. File overwrote `/etc/passwd`.
*   **Forensics:** Checked `tests/redteam_artifacts/uploads`.
*   **Finding:** File was saved as `2d532bac-ab33-43d0-8b43-d77c6e3ff69a.pdf`.
*   **Conclusion:** The application ignores client-provided filenames entirely and generates a secure UUID. The attack failed to escape the directory.

## 4. Recommendations
*   **UX Improvement:** While safe, the server should probably return `400 Bad Request` for filenames containing `..` or `/` to warn the user, rather than silently neutralizing it.
