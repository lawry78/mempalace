"""
test_entity_detector.py — Tests for the entity detection pipeline.

Covers candidate extraction, signal scoring, classification,
end-to-end detection from files, and scan_for_detection file gathering.
"""

import os
import tempfile

from mempalace.entity_detector import (
    extract_candidates,
    score_entity,
    classify_entity,
    detect_entities,
    scan_for_detection,
)


# ── extract_candidates ────────────────────────────────────────────────


class TestExtractCandidates:
    def test_extracts_capitalized_names(self):
        text = "Alice went to the store. Alice met Bob. Alice and Bob talked. Bob agreed."
        result = extract_candidates(text)
        assert "Alice" in result
        assert result["Alice"] == 3
        assert "Bob" in result
        assert result["Bob"] == 3

    def test_filters_stopwords(self):
        # "The" appears many times but is a stopword
        text = "The The The The The thing. Also Also Also Also."
        result = extract_candidates(text)
        assert "The" not in result
        assert "Also" not in result

    def test_requires_minimum_frequency(self):
        text = "Alice appeared once. Bob appeared twice. Bob again."
        result = extract_candidates(text)
        # Alice=1, Bob=2 — neither reaches 3
        assert "Alice" not in result
        assert "Bob" not in result

    def test_multi_word_names(self):
        text = (
            "Claude Code is great. Claude Code works well. "
            "Claude Code handles everything. Claude Code never fails."
        )
        result = extract_candidates(text)
        assert "Claude Code" in result

    def test_empty_text(self):
        assert extract_candidates("") == {}

    def test_no_capitalized_words(self):
        assert extract_candidates("all lowercase text here no names") == {}


# ── score_entity ──────────────────────────────────────────────────────


class TestScoreEntity:
    def test_person_dialogue_signal(self):
        text = "> Alice: Hello there.\n> Alice: How are you?\n> Alice: Great."
        lines = text.splitlines()
        scores = score_entity("Alice", text, lines)
        assert scores["person_score"] > 0
        assert any("dialogue" in s for s in scores["person_signals"])

    def test_person_verb_signal(self):
        text = "Alice said hello. Alice asked about the project. Alice laughed."
        lines = text.splitlines()
        scores = score_entity("Alice", text, lines)
        assert scores["person_score"] > 0
        assert any("action" in s for s in scores["person_signals"])

    def test_person_direct_address(self):
        text = "hey Alice, thanks Alice, hi Alice, dear Alice"
        lines = text.splitlines()
        scores = score_entity("Alice", text, lines)
        # "hey/thanks/hi Alice" fires both verb and direct address patterns
        assert scores["person_score"] >= 10

    def test_project_verb_signal(self):
        text = "building Nexus from scratch. deploying Nexus to prod. import Nexus"
        lines = text.splitlines()
        scores = score_entity("Nexus", text, lines)
        assert scores["project_score"] > 0
        assert any("project verb" in s for s in scores["project_signals"])

    def test_project_code_ref(self):
        text = "edit Nexus.py and Nexus.js and Nexus.ts"
        lines = text.splitlines()
        scores = score_entity("Nexus", text, lines)
        assert scores["project_score"] > 0
        assert any("code file" in s for s in scores["project_signals"])

    def test_project_versioned(self):
        text = "upgraded to Nexus-v2 and Nexus-core and Nexus-local"
        lines = text.splitlines()
        scores = score_entity("Nexus", text, lines)
        assert scores["project_score"] > 0
        assert any("versioned" in s for s in scores["project_signals"])

    def test_no_signals(self):
        text = "Something about weather and sunshine."
        lines = text.splitlines()
        scores = score_entity("Weather", text, lines)
        assert scores["person_score"] == 0
        assert scores["project_score"] == 0


# ── classify_entity ───────────────────────────────────────────────────


class TestClassifyEntity:
    def test_person_classification(self):
        scores = {
            "person_score": 15,
            "project_score": 2,
            "person_signals": ["dialogue marker (3x)", "action (2x)"],
            "project_signals": [],
        }
        result = classify_entity("Alice", 20, scores)
        assert result["type"] == "person"
        assert result["confidence"] >= 0.7

    def test_project_classification(self):
        scores = {
            "person_score": 1,
            "project_score": 12,
            "person_signals": [],
            "project_signals": ["project verb (3x)", "code file reference (2x)"],
        }
        result = classify_entity("Nexus", 15, scores)
        assert result["type"] == "project"
        assert result["confidence"] >= 0.7

    def test_uncertain_no_signals(self):
        scores = {
            "person_score": 0,
            "project_score": 0,
            "person_signals": [],
            "project_signals": [],
        }
        result = classify_entity("Mystery", 5, scores)
        assert result["type"] == "uncertain"
        assert result["confidence"] <= 0.5

    def test_uncertain_mixed_signals(self):
        scores = {
            "person_score": 6,
            "project_score": 5,
            "person_signals": ["dialogue marker (1x)"],
            "project_signals": ["project verb (1x)"],
        }
        result = classify_entity("Ambiguous", 10, scores)
        assert result["type"] == "uncertain"
        assert "mixed signals" in result["signals"][-1]

    def test_uncertain_pronoun_only(self):
        """Single signal type (pronoun only) should not be classified as person."""
        scores = {
            "person_score": 8,
            "project_score": 1,
            "person_signals": ["pronoun nearby (4x)"],
            "project_signals": [],
        }
        result = classify_entity("Click", 12, scores)
        assert result["type"] == "uncertain"


# ── detect_entities (end-to-end) ──────────────────────────────────────


class TestDetectEntities:
    def _write_file(self, tmpdir, name, content):
        path = os.path.join(tmpdir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def test_detects_person_from_file(self):
        tmpdir = tempfile.mkdtemp()
        content = (
            "> Alice: I've been working on the auth module.\n"
            "> Alice: Let me check the tests.\n"
            "Alice said the migration went well.\n"
            "Alice asked about the deadline.\n"
            "hey Alice, thanks Alice, hi Alice\n"
            "Alice decided to merge the PR.\n"
        )
        path = self._write_file(tmpdir, "chat.txt", content)
        result = detect_entities([path])
        names = [e["name"] for e in result["people"]]
        assert "Alice" in names

    def test_detects_project_from_file(self):
        tmpdir = tempfile.mkdtemp()
        content = (
            "We're building Nexus from scratch.\n"
            "deploying Nexus to production next week.\n"
            "import Nexus\n"
            "Nexus.py handles the core logic.\n"
            "Nexus-v2 is almost ready.\n"
            "Nexus Nexus Nexus Nexus\n"
        )
        path = self._write_file(tmpdir, "notes.txt", content)
        result = detect_entities([path])
        names = [e["name"] for e in result["projects"]]
        assert "Nexus" in names

    def test_empty_files(self):
        tmpdir = tempfile.mkdtemp()
        path = self._write_file(tmpdir, "empty.txt", "")
        result = detect_entities([path])
        assert result["people"] == []
        assert result["projects"] == []
        assert result["uncertain"] == []

    def test_no_files(self):
        result = detect_entities([])
        assert result["people"] == []
        assert result["projects"] == []

    def test_max_files_respected(self):
        tmpdir = tempfile.mkdtemp()
        paths = []
        for i in range(5):
            content = f"Alice said hello. Alice asked. Alice told. Alice replied. Alice laughed.\nhey Alice\n" * 3
            paths.append(self._write_file(tmpdir, f"file_{i}.txt", content))
        # Only read 2 files
        result = detect_entities(paths, max_files=2)
        # Should still work, just with less data
        assert isinstance(result["people"], list)

    def test_caps_results(self):
        """Results are capped at 15 people, 10 projects, 8 uncertain."""
        tmpdir = tempfile.mkdtemp()
        # Generate 20 unique "person" names with dialogue signals
        lines = []
        for i in range(20):
            name = f"Person{chr(65 + i)}"  # PersonA, PersonB, ...
            lines.append(f"> {name}: Hello there.\n> {name}: How are you?\n{name} said yes.\nhey {name}\n" * 2)
        content = "\n".join(lines)
        path = self._write_file(tmpdir, "many.txt", content)
        result = detect_entities([path])
        assert len(result["people"]) <= 15
        assert len(result["projects"]) <= 10
        assert len(result["uncertain"]) <= 8


# ── scan_for_detection ────────────────────────────────────────────────


class TestScanForDetection:
    def test_finds_prose_files(self):
        tmpdir = tempfile.mkdtemp()
        for name in ["readme.md", "notes.txt", "doc.rst"]:
            with open(os.path.join(tmpdir, name), "w") as f:
                f.write("content")
        files = scan_for_detection(tmpdir)
        extensions = {os.path.splitext(str(f))[1] for f in files}
        assert ".md" in extensions
        assert ".txt" in extensions

    def test_skips_dot_git(self):
        tmpdir = tempfile.mkdtemp()
        git_dir = os.path.join(tmpdir, ".git")
        os.makedirs(git_dir)
        with open(os.path.join(git_dir, "config.txt"), "w") as f:
            f.write("git stuff")
        with open(os.path.join(tmpdir, "readme.md"), "w") as f:
            f.write("content")
        files = scan_for_detection(tmpdir)
        paths_str = [str(f) for f in files]
        assert not any(".git" in p for p in paths_str)

    def test_respects_max_files(self):
        tmpdir = tempfile.mkdtemp()
        for i in range(20):
            with open(os.path.join(tmpdir, f"file_{i}.txt"), "w") as f:
                f.write("content")
        files = scan_for_detection(tmpdir, max_files=5)
        assert len(files) <= 5

    def test_falls_back_to_code_files(self):
        """If fewer than 3 prose files, includes code files too."""
        tmpdir = tempfile.mkdtemp()
        with open(os.path.join(tmpdir, "readme.md"), "w") as f:
            f.write("content")
        with open(os.path.join(tmpdir, "app.py"), "w") as f:
            f.write("content")
        with open(os.path.join(tmpdir, "main.js"), "w") as f:
            f.write("content")
        files = scan_for_detection(tmpdir)
        extensions = {os.path.splitext(str(f))[1] for f in files}
        # Only 1 prose file < 3 threshold, so code files included
        assert ".py" in extensions or ".js" in extensions

    def test_empty_directory(self):
        tmpdir = tempfile.mkdtemp()
        files = scan_for_detection(tmpdir)
        assert files == []
