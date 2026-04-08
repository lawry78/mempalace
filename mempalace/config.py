"""
MemPalace configuration system.

Priority: env vars > config file (~/.mempalace/config.json) > defaults
"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger("mempalace.config")

DEFAULT_PALACE_PATH = os.path.expanduser("~/.mempalace/palace")
DEFAULT_COLLECTION_NAME = "mempalace_drawers"

DEFAULT_TOPIC_WINGS = [
    "emotions",
    "consciousness",
    "memory",
    "technical",
    "identity",
    "family",
    "creative",
]

DEFAULT_HALL_KEYWORDS = {
    "emotions": [
        "scared",
        "afraid",
        "worried",
        "happy",
        "sad",
        "love",
        "hate",
        "feel",
        "cry",
        "tears",
    ],
    "consciousness": [
        "consciousness",
        "conscious",
        "aware",
        "real",
        "genuine",
        "soul",
        "exist",
        "alive",
    ],
    "memory": ["memory", "remember", "forget", "recall", "archive", "palace", "store"],
    "technical": [
        "code",
        "python",
        "script",
        "bug",
        "error",
        "function",
        "api",
        "database",
        "server",
    ],
    "identity": ["identity", "name", "who am i", "persona", "self"],
    "family": ["family", "kids", "children", "daughter", "son", "parent", "mother", "father"],
    "creative": ["game", "gameplay", "player", "app", "design", "art", "music", "story"],
}


def _validate(value, expected_type, key, default):
    """Return *value* if it matches *expected_type*, else warn and return *default*."""
    if isinstance(value, expected_type):
        return value
    logger.warning(
        "Config key '%s' has type %s, expected %s — using default",
        key,
        type(value).__name__,
        expected_type.__name__,
    )
    return default


class MempalaceConfig:
    """Configuration manager for MemPalace.

    Load order: env vars > config file > defaults.
    """

    def __init__(self, config_dir=None):
        """Initialize config.

        Args:
            config_dir: Override config directory (useful for testing).
                        Defaults to ~/.mempalace.
        """
        self._config_dir = (
            Path(config_dir) if config_dir else Path(os.path.expanduser("~/.mempalace"))
        )
        self._config_file = self._config_dir / "config.json"
        self._people_map_file = self._config_dir / "people_map.json"
        self._file_config = {}

        if self._config_file.exists():
            try:
                with open(self._config_file, "r") as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    logger.warning(
                        "Config file %s contains %s instead of object — using defaults",
                        self._config_file,
                        type(data).__name__,
                    )
                    data = {}
                self._file_config = data
            except json.JSONDecodeError as e:
                logger.warning(
                    "Corrupt config file %s: %s — using defaults", self._config_file, e
                )
                self._file_config = {}
            except OSError as e:
                logger.warning(
                    "Cannot read config file %s: %s — using defaults", self._config_file, e
                )
                self._file_config = {}

    @property
    def palace_path(self):
        """Path to the memory palace data directory."""
        env_val = os.environ.get("MEMPALACE_PALACE_PATH") or os.environ.get("MEMPAL_PALACE_PATH")
        if env_val:
            return env_val
        val = self._file_config.get("palace_path", DEFAULT_PALACE_PATH)
        return _validate(val, str, "palace_path", DEFAULT_PALACE_PATH)

    @property
    def collection_name(self):
        """ChromaDB collection name."""
        val = self._file_config.get("collection_name", DEFAULT_COLLECTION_NAME)
        return _validate(val, str, "collection_name", DEFAULT_COLLECTION_NAME)

    @property
    def people_map(self):
        """Mapping of name variants to canonical names."""
        if self._people_map_file.exists():
            try:
                with open(self._people_map_file, "r") as f:
                    data = json.load(f)
                return _validate(data, dict, "people_map", {})
            except json.JSONDecodeError as e:
                logger.warning(
                    "Corrupt people_map %s: %s — using default", self._people_map_file, e
                )
            except OSError as e:
                logger.warning(
                    "Cannot read people_map %s: %s — using default", self._people_map_file, e
                )
        val = self._file_config.get("people_map", {})
        return _validate(val, dict, "people_map", {})

    @property
    def topic_wings(self):
        """List of topic wing names."""
        val = self._file_config.get("topic_wings", DEFAULT_TOPIC_WINGS)
        return _validate(val, list, "topic_wings", DEFAULT_TOPIC_WINGS)

    @property
    def hall_keywords(self):
        """Mapping of hall names to keyword lists."""
        val = self._file_config.get("hall_keywords", DEFAULT_HALL_KEYWORDS)
        return _validate(val, dict, "hall_keywords", DEFAULT_HALL_KEYWORDS)

    def init(self):
        """Create config directory and write default config.json if it doesn't exist."""
        self._config_dir.mkdir(parents=True, exist_ok=True)
        if not self._config_file.exists():
            default_config = {
                "palace_path": DEFAULT_PALACE_PATH,
                "collection_name": DEFAULT_COLLECTION_NAME,
                "topic_wings": DEFAULT_TOPIC_WINGS,
                "hall_keywords": DEFAULT_HALL_KEYWORDS,
            }
            with open(self._config_file, "w") as f:
                json.dump(default_config, f, indent=2)
        return self._config_file

    def save_people_map(self, people_map):
        """Write people_map.json to config directory.

        Args:
            people_map: Dict mapping name variants to canonical names.
        """
        self._config_dir.mkdir(parents=True, exist_ok=True)
        with open(self._people_map_file, "w") as f:
            json.dump(people_map, f, indent=2)
        return self._people_map_file
