"""
Pre-download the Gemma model required for OCR_TIER=local.

Usage:
    python -m app.local_setup

Downloads ~9 GB to your HuggingFace cache (~/.cache/huggingface).
Subsequent runs are instant (cache hit).
"""

import sys


def main() -> None:
    print("CleanOCR — Local Model Setup")
    print("=" * 40)
    print(f"Model: ", end="", flush=True)

    try:
        from app.core import config as app_config
        print(app_config.LOCAL_GEMMA_MODEL)
    except Exception:
        print("(could not read config)")

    print("Estimated download: ~9 GB (cached after first run)")
    print("Downloading…\n")

    try:
        from app.services.gemma_provider import get_gemma_provider
    except ImportError:
        print(
            "\nERROR: Local dependencies are not installed.\n"
            "Run:  pip install -r requirements-local.txt\n"
            "Then retry:  python -m app.local_setup"
        )
        sys.exit(1)

    try:
        provider = get_gemma_provider()
        provider._load()
    except ImportError:
        print(
            "\nERROR: torch or transformers not found.\n"
            "Run:  pip install -r requirements-local.txt"
        )
        sys.exit(1)
    except Exception as exc:
        print(f"\nERROR: Model failed to load: {exc}")
        sys.exit(1)

    print("\nModel ready.")
    print("You can now run CleanOCR with OCR_TIER=local.")


if __name__ == "__main__":
    main()
