import unittest
import os
import json
import shutil
import tempfile
import sys
from pathlib import Path

# Add project root to sys.path to allow importing stitch_to_markdown
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(PROJECT_ROOT)

from app.services import stitcher

class TestIssueSeparation(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for the test workspace
        self.test_dir = tempfile.mkdtemp()
        self.input_dir = os.path.join(self.test_dir, "input")
        self.output_dir = os.path.join(self.test_dir, "output")
        self.issues_dir = os.path.join(self.output_dir, "issues")
        
        os.makedirs(self.input_dir)
        os.makedirs(self.output_dir)

        # --- CREATE DUMMY DATA SEQUENCE ---
        # Page 1: Explicit Vol 1, Issue 1
        self.create_json("page_001.json", {"volume": "1", "issue": "1", "page_number": "1"})
        
        # Page 2: Implicit (No metadata) -> Should inherit Vol 1, Issue 1
        self.create_json("page_002.json", {})
        
        # Page 3: Explicit Vol 1, Issue 2 (New Issue)
        self.create_json("page_003.json", {"volume": "1", "issue": "2", "page_number": "3"})
        
        # Page 4: Hallucination (Vol 37) -> Should be ignored and stick to Vol 1, Issue 2
        # Note: stitcher currently logs warning but might update if logic permits. 
        # Logic says: if v_norm > current + 2: warn. 
        # It does NOT explicitly revert current_vol in the code I saw, 
        # WAIT: The code says:
        # if v_norm > current_vol + MAX_VOL_JUMP: print warn 
        # else: current_vol = v_norm
        # So it DOES revert/ignore the update effectively by NOT executing the else.
        self.create_json("page_004.json", {"volume": "37", "issue": "2", "page_number": "4"})

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def create_json(self, filename, metadata):
        content = {
            "metadata": metadata,
            "markdown_content": f"Content for {filename}",
            "full_text": f"Content for {filename}"
        }
        with open(os.path.join(self.input_dir, filename), "w") as f:
            json.dump(content, f)

    def test_folder_creation_logic(self):
        """Verify that pages are sorted into correct Issue folders based on Forward Fill & Hallucination checks."""
        
        # Override config paths for this test execution
        # We can't easily inject config changes if they are global constants in the module,
        # but stitch_to_markdown.stitch_markdown takes arguments.
        
        stitcher.stitch_markdown(self.input_dir, self.output_dir)
        
        # --- VERIFICATION ---
        
        # 1. Check Issue 1 Folder (Vol_001_Issue_001)
        issue1_path = os.path.join(self.issues_dir, "Vol_001_Issue_001", "pages")
        self.assertTrue(os.path.exists(issue1_path), "Issue 1 folder should exist")
        self.assertTrue(os.path.exists(os.path.join(issue1_path, "page_001.md")), "Page 1 should be in Issue 1")
        self.assertTrue(os.path.exists(os.path.join(issue1_path, "page_002.md")), "Page 2 (Implicit) should be in Issue 1")
        
        # 2. Check Issue 2 Folder (Vol_001_Issue_002)
        issue2_path = os.path.join(self.issues_dir, "Vol_001_Issue_002", "pages")
        self.assertTrue(os.path.exists(issue2_path), "Issue 2 folder should exist")
        self.assertTrue(os.path.exists(os.path.join(issue2_path, "page_003.md")), "Page 3 should be in Issue 2")
        
        # 3. Check Hallucination Handling (Page 4)
        # Page 4 tried to set Vol 37. Logic should have rejected it.
        # It should inherit previous state: Vol 1, Issue 2.
        self.assertTrue(os.path.exists(os.path.join(issue2_path, "page_004.md")), "Page 4 (Hallucination) should stay in Issue 2")
        
        # 4. Ensure no Vol_037 folder
        vol37_path = os.path.join(self.issues_dir, "Vol_037_Issue_002")
        self.assertFalse(os.path.exists(vol37_path), "Hallucinated Volume 37 folder should NOT exist")

if __name__ == '__main__':
    unittest.main()
