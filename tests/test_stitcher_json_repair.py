# HITL: assertions in this file require human review before merge

import json
import os
import re
from unittest.mock import patch

import pytest

from app.core import config
from app.services import stitcher
from app.services.stitcher import load_and_repair_json, normalize_number, stitch_markdown


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_json(tmp_path, filename, data):
    """Write a dict as JSON to tmp_path/filename and return the full path."""
    p = tmp_path / filename
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _write_raw(tmp_path, filename, raw_text):
    """Write raw text (not necessarily valid JSON) to tmp_path/filename."""
    p = tmp_path / filename
    p.write_text(raw_text, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# 1. load_and_repair_json
# ---------------------------------------------------------------------------

class TestLoadAndRepairJson:

    def test_strategy1_clean_json(self, tmp_path):
        """Strategy 1: standard json.loads succeeds on well-formed input."""
        data = {"markdown_content": "Hello world", "metadata": {"volume": "1", "issue": "2", "page_number": "3"}}
        path = _write_json(tmp_path, "page_001.json", data)
        result = load_and_repair_json(str(path))
        assert result is not None
        assert result["markdown_content"] == "Hello world"
        assert result["metadata"]["volume"] == "1"

    def test_strategy2_truncated_output(self, tmp_path):
        """Strategy 2: model appended '--- OCR End ---' after the closing brace."""
        data = {"markdown_content": "Truncated content", "metadata": {"volume": "1", "issue": "1", "page_number": "5"}}
        raw = json.dumps(data) + "\n--- OCR End ---\n"
        path = _write_raw(tmp_path, "page_002.json", raw)
        result = load_and_repair_json(str(path))
        assert result is not None
        assert result["markdown_content"] == "Truncated content"

    def test_strategy4_regex_fallback(self, tmp_path):
        """Strategy 4: fully malformed JSON — regex extracts markdown_content."""
        raw = (
            '{"markdown_content": "Recovered text here", '
            '"metadata": {"volume": "2", "issue": "3", "page_number": "7"'
            # intentionally missing closing braces — not valid JSON
        )
        path = _write_raw(tmp_path, "page_003.json", raw)
        result = load_and_repair_json(str(path))
        assert result is not None
        assert "Recovered text here" in result["markdown_content"]

    def test_returns_none_on_total_failure(self, tmp_path):
        """Returns None when no strategy can extract meaningful JSON."""
        raw = "This is just some random plain text with no JSON whatsoever."
        path = _write_raw(tmp_path, "page_004.json", raw)
        result = load_and_repair_json(str(path))
        assert result is None

    def test_strategy2_preserves_metadata(self, tmp_path):
        """Strategy 2 repair preserves metadata fields."""
        data = {"markdown_content": "Some text", "metadata": {"volume": "III", "issue": "2", "page_number": "10"}}
        raw = json.dumps(data) + " extra garbage"
        path = _write_raw(tmp_path, "page_005.json", raw)
        result = load_and_repair_json(str(path))
        assert result is not None
        assert result["metadata"]["volume"] == "III"


# ---------------------------------------------------------------------------
# 2. normalize_number
# ---------------------------------------------------------------------------

class TestNormalizeNumber:

    @pytest.mark.parametrize("roman,expected", [
        ("I", 1),
        ("II", 2),
        ("V", 5),
        ("X", 10),
        ("III", 3),
    ])
    def test_roman_numerals(self, roman, expected):
        assert normalize_number(roman) == expected

    def test_vol_string(self):
        assert normalize_number("Vol 3") == 3

    def test_no_string(self):
        assert normalize_number("No. 7") == 7

    def test_plain_integer_string(self):
        assert normalize_number("4") == 4

    def test_none_input(self):
        assert normalize_number(None) is None

    def test_empty_string(self):
        assert normalize_number("") is None

    def test_volume_prefix(self):
        assert normalize_number("Volume 12") == 12

    def test_issue_prefix(self):
        assert normalize_number("Issue 5") == 5


# ---------------------------------------------------------------------------
# 3. Image markdown stripping (Gap 5)
# ---------------------------------------------------------------------------

_MOCK_VERIFY = "app.services.stitcher.verify_boundary_text"


class TestImageMarkdownStripping:

    def _make_input(self, tmp_path, pages):
        """Write a list of (filename, markdown_content) tuples into tmp_path."""
        for filename, content in pages:
            data = {
                "markdown_content": content,
                "metadata": {"volume": "1", "issue": "1", "page_number": "1"},
            }
            _write_json(tmp_path, filename, data)

    def test_single_image_tag_stripped(self, tmp_path):
        inp = tmp_path / "input"
        out = tmp_path / "output"
        inp.mkdir()
        self._make_input(inp, [
            ("page_001.json", "Some text ![alt text](http://example.com/img.png) more text"),
        ])
        with patch(_MOCK_VERIFY, side_effect=lambda a, b: a + b):
            stitch_markdown(str(inp), str(out))
        result = (out / "full_extracted_content.md").read_text(encoding="utf-8")
        assert "![alt text](http://example.com/img.png)" not in result
        assert "Some text" in result
        assert "more text" in result

    def test_multiple_image_tags_stripped(self, tmp_path):
        inp = tmp_path / "input"
        out = tmp_path / "output"
        inp.mkdir()
        self._make_input(inp, [
            ("page_001.json", "![a](1.jpg) text ![b](2.png) end"),
        ])
        with patch(_MOCK_VERIFY, side_effect=lambda a, b: a + b):
            stitch_markdown(str(inp), str(out))
        result = (out / "full_extracted_content.md").read_text(encoding="utf-8")
        assert "![a](1.jpg)" not in result
        assert "![b](2.png)" not in result
        assert "text" in result
        assert "end" in result

    def test_issue_page_files_also_stripped(self, tmp_path):
        """Image tags also stripped from the per-page .md files in issues/."""
        inp = tmp_path / "input"
        out = tmp_path / "output"
        inp.mkdir()
        self._make_input(inp, [
            ("page_001.json", "Before ![img](photo.jpg) after"),
        ])
        with patch(_MOCK_VERIFY, side_effect=lambda a, b: a + b):
            stitch_markdown(str(inp), str(out))
        # Find any .md page file under issues/
        issues_dir = out / "issues"
        page_mds = list(issues_dir.rglob("page_*.md"))
        assert page_mds, "Expected at least one page .md file"
        for md in page_mds:
            content = md.read_text(encoding="utf-8")
            assert "![img](photo.jpg)" not in content


# ---------------------------------------------------------------------------
# 4. YAML frontmatter
# ---------------------------------------------------------------------------

class TestYamlFrontmatter:

    def _make_single_page_input(self, inp):
        data = {"markdown_content": "Body text.", "metadata": {"volume": "1", "issue": "1", "page_number": "1"}}
        _write_json(inp, "page_001.json", data)

    def _make_metadata_file(self, tmp_path, meta):
        p = tmp_path / "metadata.json"
        p.write_text(json.dumps(meta), encoding="utf-8")
        return str(p)

    def test_frontmatter_present_when_metadata_provided(self, tmp_path):
        inp = tmp_path / "input"
        out = tmp_path / "output"
        inp.mkdir()
        self._make_single_page_input(inp)
        meta_path = self._make_metadata_file(tmp_path, {
            "title": "Test Publication",
            "date": "1834-10-01",
            "volume": "1",
            "issue": "1",
        })
        with patch(_MOCK_VERIFY, side_effect=lambda a, b: a + b):
            stitch_markdown(str(inp), str(out), metadata_file=meta_path)
        result = (out / "full_extracted_content.md").read_text(encoding="utf-8")
        assert result.startswith("---")

    def test_frontmatter_contains_required_keys(self, tmp_path):
        inp = tmp_path / "input"
        out = tmp_path / "output"
        inp.mkdir()
        self._make_single_page_input(inp)
        meta_path = self._make_metadata_file(tmp_path, {
            "title": "My Journal",
            "date": "1835-01-15",
            "volume": "2",
            "issue": "3",
        })
        with patch(_MOCK_VERIFY, side_effect=lambda a, b: a + b):
            stitch_markdown(str(inp), str(out), metadata_file=meta_path)
        result = (out / "full_extracted_content.md").read_text(encoding="utf-8")
        assert 'title:' in result
        assert 'date:' in result
        assert 'volume:' in result
        assert 'issue:' in result
        assert 'generated_by: "CleanOCR"' in result

    def test_frontmatter_values_match_metadata(self, tmp_path):
        inp = tmp_path / "input"
        out = tmp_path / "output"
        inp.mkdir()
        self._make_single_page_input(inp)
        meta_path = self._make_metadata_file(tmp_path, {
            "title": "Advocate",
            "date": "1836-06-01",
            "volume": "5",
            "issue": "9",
        })
        with patch(_MOCK_VERIFY, side_effect=lambda a, b: a + b):
            stitch_markdown(str(inp), str(out), metadata_file=meta_path)
        result = (out / "full_extracted_content.md").read_text(encoding="utf-8")
        assert '"Advocate"' in result
        assert '"1836-06-01"' in result
        assert '"5"' in result
        assert '"9"' in result

    def test_frontmatter_not_generated_when_skip_metadata_true(self, tmp_path):
        inp = tmp_path / "input"
        out = tmp_path / "output"
        inp.mkdir()
        self._make_single_page_input(inp)
        meta_path = self._make_metadata_file(tmp_path, {
            "skip_metadata": "true",
            "original_filename": "SomeDoc",
        })
        with patch(_MOCK_VERIFY, side_effect=lambda a, b: a + b):
            stitch_markdown(str(inp), str(out), metadata_file=meta_path)
        result = (out / "full_extracted_content.md").read_text(encoding="utf-8")
        assert not result.startswith("---")
        assert 'generated_by' not in result

    def test_frontmatter_not_generated_without_metadata_file(self, tmp_path):
        inp = tmp_path / "input"
        out = tmp_path / "output"
        inp.mkdir()
        self._make_single_page_input(inp)
        with patch(_MOCK_VERIFY, side_effect=lambda a, b: a + b):
            stitch_markdown(str(inp), str(out))
        result = (out / "full_extracted_content.md").read_text(encoding="utf-8")
        assert not result.startswith("---")


# ---------------------------------------------------------------------------
# 5. Hallucination detection (MAX_VOL_JUMP = 2)
# ---------------------------------------------------------------------------

class TestHallucinationDetection:

    def _write_pages(self, inp, pages):
        """pages: list of (filename, volume_str, issue_str, content)"""
        for filename, vol, iss, content in pages:
            data = {
                "markdown_content": content,
                "metadata": {"volume": vol, "issue": iss, "page_number": "1"},
            }
            _write_json(inp, filename, data)

    def test_large_vol_jump_rejected(self, tmp_path):
        """Vol 1 -> 37 exceeds MAX_VOL_JUMP=2; forward-fill keeps vol at 1."""
        inp = tmp_path / "input"
        out = tmp_path / "output"
        inp.mkdir()
        self._write_pages(inp, [
            ("page_001.json", "1", "1", "Page one text."),
            ("page_002.json", "37", "1", "Page two text."),
        ])
        with patch(_MOCK_VERIFY, side_effect=lambda a, b: a + b):
            stitch_markdown(str(inp), str(out))
        result = (out / "full_extracted_content.md").read_text(encoding="utf-8")
        # Volume 37 header should NOT appear; Volume 1 header should be present
        assert "Volume 37" not in result
        assert "Volume 1" in result

    def test_small_vol_jump_accepted(self, tmp_path):
        """Vol 1 -> 2 is within MAX_VOL_JUMP=2; transition should be accepted."""
        inp = tmp_path / "input"
        out = tmp_path / "output"
        inp.mkdir()
        self._write_pages(inp, [
            ("page_001.json", "1", "1", "First volume text."),
            ("page_002.json", "2", "1", "Second volume text."),
        ])
        with patch(_MOCK_VERIFY, side_effect=lambda a, b: a + b):
            stitch_markdown(str(inp), str(out))
        result = (out / "full_extracted_content.md").read_text(encoding="utf-8")
        assert "Volume 2" in result


# ---------------------------------------------------------------------------
# 6. REPAIR_TARGETS sourced from config
# ---------------------------------------------------------------------------

class TestRepairTargetsFromConfig:

    def test_repair_targets_is_config_object(self):
        """REPAIR_TARGETS must be the exact same object as config.REPAIR_TARGETS."""
        assert stitcher.REPAIR_TARGETS is config.REPAIR_TARGETS
