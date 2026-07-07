"""
app_config.py — VECTOMEC™ Application Configuration & Folder Manager
═══════════════════════════════════════════════════════════════════════════
Sets up the application folder structure on first launch and provides
path helpers to every other module.

Folder structure (Windows: %APPDATA%\\VECTOMEC\\):
    db\\          vectrix.db (engineering database) + users.db (auth)
    designs\\     saved .vmdesign files
    logs\\        application log files

Reports are NOT auto-saved here — the user is asked via QFileDialog
every time a report is generated (per Jay's explicit decision).

The config.json at the root of the VECTOMEC folder stores the resolved
paths (in case a user ever wants to relocate any of them) plus app
preferences. It is created on first launch and migrated forward as
the schema evolves.
"""
import json
import os
import platform
import sys
from pathlib import Path

CONFIG_SCHEMA_VERSION = 1


def _default_appdata_root() -> Path:
    """Return the platform-appropriate application-data root."""
    system = platform.system()
    if system == "Windows":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "VECTOMEC"
    elif system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "VECTOMEC"
    # Linux / fallback
    return Path.home() / ".vectomec"


class AppConfig:
    """Singleton-style config object.  Use get() to obtain the instance."""

    _instance: "AppConfig | None" = None

    def __init__(self, root: Path | None = None):
        self.root = root or _default_appdata_root()
        self.config_path = self.root / "config.json"
        self._data: dict = {}
        self._ensure_dirs()
        self._load_or_create()

    # ── Singleton ──────────────────────────────────────────────────────
    @classmethod
    def get(cls) -> "AppConfig":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Folder setup ───────────────────────────────────────────────────
    def _ensure_dirs(self) -> None:
        for sub in ("db", "designs", "logs"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)

    def _load_or_create(self) -> None:
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {}
        if self._data.get("schema_version") != CONFIG_SCHEMA_VERSION:
            self._migrate()

    def _migrate(self) -> None:
        """Forward-migrate config to current schema version."""
        defaults = {
            "schema_version": CONFIG_SCHEMA_VERSION,
            "db_dir":      str(self.root / "db"),
            "designs_dir": str(self.root / "designs"),
            "logs_dir":    str(self.root / "logs"),
            "app_version": "1.0.0",
            "first_launch": True,
        }
        for key, val in defaults.items():
            self._data.setdefault(key, val)
        self._data["schema_version"] = CONFIG_SCHEMA_VERSION
        self._save()

    def _save(self) -> None:
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    # ── Path helpers ───────────────────────────────────────────────────
    @property
    def db_dir(self) -> Path:
        return Path(self._data.get("db_dir", str(self.root / "db")))

    @property
    def designs_dir(self) -> Path:
        return Path(self._data.get("designs_dir", str(self.root / "designs")))

    @property
    def logs_dir(self) -> Path:
        return Path(self._data.get("logs_dir", str(self.root / "logs")))

    @property
    def users_db_path(self) -> Path:
        return self.db_dir / "users.db"

    @property
    def engineering_db_path(self) -> Path:
        """Path for the main vectrix.db engineering database."""
        return self.db_dir / "vectrix.db"

    @property
    def is_first_launch(self) -> bool:
        return bool(self._data.get("first_launch", True))

    def mark_first_launch_done(self) -> None:
        self._data["first_launch"] = False
        self._save()

    def get_setting(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        self._data[key] = value
        self._save()

    # ── Design file helpers ────────────────────────────────────────────
    def next_design_version(self, model_number: str) -> int:
        """Scan the designs folder and return the next version number for
        this model number (existing v001, v002 → returns 3)."""
        prefix = model_number.replace("/", "_").replace("-", "-")
        existing = list(self.designs_dir.glob(f"{prefix}_v*.vmdesign"))
        versions = []
        for p in existing:
            parts = p.stem.split("_v")
            if len(parts) >= 2:
                try:
                    versions.append(int(parts[-1].split("_")[0]))
                except ValueError:
                    pass
        return max(versions, default=0) + 1

    def design_filename(self, model_number: str, stage: str, version: int,
                         timestamp: str) -> Path:
        """Build the full path for a design file.
        Example: VM-CD-B-305_500_v001_PRELIMINARY_20260706_1423.vmdesign"""
        safe_model = model_number.replace("/", "_")
        name = f"{safe_model}_v{version:03d}_{stage.upper()}_{timestamp}.vmdesign"
        return self.designs_dir / name