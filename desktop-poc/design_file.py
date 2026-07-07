"""
design_file.py — VECTOMEC™ Design File Save / Load
═══════════════════════════════════════════════════════════════════════════
Saves and loads .vmdesign files -- versioned full-snapshot JSON containing:

    - Format version (for forward migration)
    - Model number
    - Design review stage (embedded in both the file and the filename)
    - Version number (auto-incremented per model number)
    - Created by / last modified by (from the auth module)
    - The full inputs dict (loads back into run_calculation())
    - The full results dict (avoids needing a recalculation to view the design)
    - Sign-off history (who advanced each stage and when)

Filename convention:
    {safe_model_number}_v{version:03d}_{STAGE}_{YYYYMMDD_HHMM}.vmdesign

Example:
    VM-CD-B-305_500_v003_DETAILED_20260706_1423.vmdesign

"Save" always creates a NEW file (incremented version). "Save As" lets
the user pick a different designs folder but still auto-versions.

Loading any .vmdesign file restores inputs, results, and design review
stage. The sign-off history is read-only after the fact.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

FORMAT_VERSION = 1

STAGE_LABELS = {
    1: "CONCEPT",
    2: "PRELIMINARY",
    3: "DETAILED",
    4: "RELEASED",
}


class DesignFile:
    """Represents a loaded or newly-created design file."""

    def __init__(self, data: dict, path: Optional[Path] = None):
        self._data = data
        self.path = path

    # ── Factory: new design ────────────────────────────────────────────
    @classmethod
    def create(cls, inputs: dict, results: dict, model_number: str,
                stage: int, version: int, created_by: dict) -> "DesignFile":
        now = datetime.now()
        data = {
            "format_version": FORMAT_VERSION,
            "model_number":   model_number,
            "design_stage":   stage,
            "stage_label":    STAGE_LABELS.get(stage, "CONCEPT"),
            "version":        version,
            "created_at":     now.isoformat(),
            "created_by":     created_by,
            "modified_at":    now.isoformat(),
            "modified_by":    created_by,
            "inputs":         inputs,
            "results":        results,
            "sign_off_history": [],
        }
        return cls(data)

    # ── Factory: load from file ────────────────────────────────────────
    @classmethod
    def load(cls, path: Path) -> "DesignFile":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("format_version") != FORMAT_VERSION:
            data = _migrate_forward(data)
        return cls(data, path=path)

    # ── Properties ────────────────────────────────────────────────────
    @property
    def model_number(self) -> str:
        return self._data.get("model_number", "VM-??-?-???/???")

    @property
    def design_stage(self) -> int:
        return int(self._data.get("design_stage", 1))

    @property
    def stage_label(self) -> str:
        return STAGE_LABELS.get(self.design_stage, "CONCEPT")

    @property
    def version(self) -> int:
        return int(self._data.get("version", 1))

    @property
    def inputs(self) -> dict:
        return self._data.get("inputs") or {}

    @property
    def results(self) -> dict:
        return self._data.get("results") or {}

    @property
    def created_at(self) -> str:
        return self._data.get("created_at", "")

    @property
    def created_by(self) -> dict:
        return self._data.get("created_by") or {}

    @property
    def modified_at(self) -> str:
        return self._data.get("modified_at", "")

    @property
    def sign_off_history(self) -> list:
        return self._data.get("sign_off_history") or []

    # ── Mutation ───────────────────────────────────────────────────────
    def update_stage(self, new_stage: int, advanced_by: dict) -> None:
        """Advance the design review stage and record who did it."""
        entry = {
            "stage":        new_stage,
            "stage_label":  STAGE_LABELS.get(new_stage, "?"),
            "advanced_by":  advanced_by,
            "advanced_at":  datetime.now().isoformat(),
        }
        self._data["design_stage"] = new_stage
        self._data["stage_label"]  = STAGE_LABELS.get(new_stage, "?")
        history = self._data.setdefault("sign_off_history", [])
        # Replace any existing entry for this stage
        history[:] = [e for e in history if e.get("stage") != new_stage]
        history.append(entry)
        history.sort(key=lambda e: e.get("stage", 0))
        self._data["modified_at"] = datetime.now().isoformat()
        self._data["modified_by"] = advanced_by

    def get_sign_off_for_stage(self, stage: int) -> Optional[dict]:
        for entry in self.sign_off_history:
            if entry.get("stage") == stage:
                return entry
        return None

    # ── Save ───────────────────────────────────────────────────────────
    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)
        self.path = path

    def to_dict(self) -> dict:
        return dict(self._data)


def _migrate_forward(data: dict) -> dict:
    """Forward-migrate old format versions. Currently only v1 exists."""
    data.setdefault("format_version", FORMAT_VERSION)
    data.setdefault("sign_off_history", [])
    data.setdefault("created_by", {})
    data.setdefault("modified_by", {})
    return data


def build_filename(model_number: str, stage: int, version: int) -> str:
    """Build the bare filename (no directory) for a design file.

    Slashes in model number replaced with underscores so the string is
    safe as a filename on all platforms.

    Example: VM-CD-B-305_500_v003_DETAILED_20260706_1423.vmdesign
    """
    safe_model = model_number.replace("/", "_")
    stage_label = STAGE_LABELS.get(stage, "CONCEPT")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    return f"{safe_model}_v{version:03d}_{stage_label}_{timestamp}.vmdesign"


def list_design_files(designs_dir: Path) -> list[dict]:
    """Scan the designs folder and return a sorted list of design file
    metadata dicts, newest version first, suitable for display in the
    Open Design dialog."""
    if not designs_dir.exists():
        return []
    results = []
    for p in sorted(designs_dir.glob("*.vmdesign"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            df = DesignFile.load(p)
            results.append({
                "path":         p,
                "filename":     p.name,
                "model_number": df.model_number,
                "stage":        df.design_stage,
                "stage_label":  df.stage_label,
                "version":      df.version,
                "modified_at":  df.modified_at,
                "created_by":   df.created_by.get("display_name", "—"),
            })
        except Exception:
            pass   # skip corrupt files silently
    return results