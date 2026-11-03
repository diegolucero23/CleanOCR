import time
import json
import uuid
import sys
import os
from typing import Any
from app.services.ocr_interface import OCRProvider

class RedTeamMockProvider(OCRProvider):
    def __init__(self):
        print("⚠️  MOCK MODE ENABLED: No API calls will be made.", flush=True)

    def detect_layout_type(self, image: Any) -> str:
        """Mock layout classification: returns single-column by default."""
        return "single-column"

    def generate_content(self, contents: list, config: Any = None) -> str:
        """
        Simulates the Google API for RedTeam testing.
        """
        print(f"⚠️  [MOCK] Skipping Google API Check", flush=True)
        time.sleep(0.05)  # Fast simulated latency

        job_uuid = str(uuid.uuid4())[:8]

        return json.dumps({
            "markdown_content": f"# Mock Page ({job_uuid})\n\n**[REDTEAM MOCK DATA]**\n\nGenerated under strict isolation.",
            "metadata": {
                "volume": "1", 
                "issue": "1", 
                "page_number": "001",
                "confidence": 0.99
            }
        })
