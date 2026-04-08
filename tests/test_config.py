import logging
import os
import json
import tempfile
from mempalace.config import MempalaceConfig, DEFAULT_PALACE_PATH, DEFAULT_COLLECTION_NAME


def test_default_config():
    cfg = MempalaceConfig(config_dir=tempfile.mkdtemp())
    assert "palace" in cfg.palace_path
    assert cfg.collection_name == "mempalace_drawers"


def test_config_from_file():
    tmpdir = tempfile.mkdtemp()
    with open(os.path.join(tmpdir, "config.json"), "w") as f:
        json.dump({"palace_path": "/custom/palace"}, f)
    cfg = MempalaceConfig(config_dir=tmpdir)
    assert cfg.palace_path == "/custom/palace"


def test_env_override():
    os.environ["MEMPALACE_PALACE_PATH"] = "/env/palace"
    cfg = MempalaceConfig(config_dir=tempfile.mkdtemp())
    assert cfg.palace_path == "/env/palace"
    del os.environ["MEMPALACE_PALACE_PATH"]


def test_init():
    tmpdir = tempfile.mkdtemp()
    cfg = MempalaceConfig(config_dir=tmpdir)
    cfg.init()
    assert os.path.exists(os.path.join(tmpdir, "config.json"))


# ── Validation tests ──────────────────────────────────────────────────


class TestCorruptConfig:
    def test_corrupt_json_warns_and_uses_defaults(self, caplog):
        tmpdir = tempfile.mkdtemp()
        with open(os.path.join(tmpdir, "config.json"), "w") as f:
            f.write("{broken json!!!")

        with caplog.at_level(logging.WARNING, logger="mempalace.config"):
            cfg = MempalaceConfig(config_dir=tmpdir)

        assert cfg.palace_path == DEFAULT_PALACE_PATH
        assert "Corrupt config file" in caplog.text

    def test_non_dict_json_warns_and_uses_defaults(self, caplog):
        tmpdir = tempfile.mkdtemp()
        with open(os.path.join(tmpdir, "config.json"), "w") as f:
            json.dump(["this", "is", "a", "list"], f)

        with caplog.at_level(logging.WARNING, logger="mempalace.config"):
            cfg = MempalaceConfig(config_dir=tmpdir)

        assert cfg.palace_path == DEFAULT_PALACE_PATH
        assert "instead of object" in caplog.text

    def test_corrupt_people_map_warns(self, caplog):
        tmpdir = tempfile.mkdtemp()
        with open(os.path.join(tmpdir, "people_map.json"), "w") as f:
            f.write("not json{{{")

        with caplog.at_level(logging.WARNING, logger="mempalace.config"):
            cfg = MempalaceConfig(config_dir=tmpdir)
            result = cfg.people_map

        assert result == {}
        assert "Corrupt people_map" in caplog.text


class TestTypeValidation:
    def test_palace_path_wrong_type_falls_back(self, caplog):
        tmpdir = tempfile.mkdtemp()
        with open(os.path.join(tmpdir, "config.json"), "w") as f:
            json.dump({"palace_path": 12345}, f)

        with caplog.at_level(logging.WARNING, logger="mempalace.config"):
            cfg = MempalaceConfig(config_dir=tmpdir)
            result = cfg.palace_path

        assert result == DEFAULT_PALACE_PATH
        assert "palace_path" in caplog.text
        assert "int" in caplog.text

    def test_collection_name_wrong_type_falls_back(self, caplog):
        tmpdir = tempfile.mkdtemp()
        with open(os.path.join(tmpdir, "config.json"), "w") as f:
            json.dump({"collection_name": ["not", "a", "string"]}, f)

        with caplog.at_level(logging.WARNING, logger="mempalace.config"):
            cfg = MempalaceConfig(config_dir=tmpdir)
            result = cfg.collection_name

        assert result == DEFAULT_COLLECTION_NAME
        assert "collection_name" in caplog.text

    def test_topic_wings_wrong_type_falls_back(self, caplog):
        tmpdir = tempfile.mkdtemp()
        with open(os.path.join(tmpdir, "config.json"), "w") as f:
            json.dump({"topic_wings": "should be a list"}, f)

        with caplog.at_level(logging.WARNING, logger="mempalace.config"):
            cfg = MempalaceConfig(config_dir=tmpdir)
            result = cfg.topic_wings

        assert isinstance(result, list)
        assert "topic_wings" in caplog.text

    def test_hall_keywords_wrong_type_falls_back(self, caplog):
        tmpdir = tempfile.mkdtemp()
        with open(os.path.join(tmpdir, "config.json"), "w") as f:
            json.dump({"hall_keywords": "not a dict"}, f)

        with caplog.at_level(logging.WARNING, logger="mempalace.config"):
            cfg = MempalaceConfig(config_dir=tmpdir)
            result = cfg.hall_keywords

        assert isinstance(result, dict)
        assert "hall_keywords" in caplog.text

    def test_people_map_wrong_type_falls_back(self, caplog):
        tmpdir = tempfile.mkdtemp()
        with open(os.path.join(tmpdir, "people_map.json"), "w") as f:
            json.dump(["list", "not", "dict"], f)

        with caplog.at_level(logging.WARNING, logger="mempalace.config"):
            cfg = MempalaceConfig(config_dir=tmpdir)
            result = cfg.people_map

        assert result == {}
        assert "people_map" in caplog.text

    def test_valid_config_no_warnings(self, caplog):
        tmpdir = tempfile.mkdtemp()
        with open(os.path.join(tmpdir, "config.json"), "w") as f:
            json.dump({
                "palace_path": "/valid/path",
                "collection_name": "my_collection",
                "topic_wings": ["wing_a", "wing_b"],
                "hall_keywords": {"hall_a": ["kw1"]},
            }, f)

        with caplog.at_level(logging.WARNING, logger="mempalace.config"):
            cfg = MempalaceConfig(config_dir=tmpdir)
            _ = cfg.palace_path
            _ = cfg.collection_name
            _ = cfg.topic_wings
            _ = cfg.hall_keywords

        assert cfg.palace_path == "/valid/path"
        assert cfg.collection_name == "my_collection"
        assert caplog.text == ""

    def test_partial_config_uses_defaults_for_missing(self):
        tmpdir = tempfile.mkdtemp()
        with open(os.path.join(tmpdir, "config.json"), "w") as f:
            json.dump({"palace_path": "/my/palace"}, f)

        cfg = MempalaceConfig(config_dir=tmpdir)
        assert cfg.palace_path == "/my/palace"
        assert cfg.collection_name == DEFAULT_COLLECTION_NAME
