"""Rule Engine — loads device rules from the YAML library."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class SignalRule:
    """One signal definition from a library rule file."""

    name: str
    signal_type: str


@dataclass(frozen=True)
class DeviceRule:
    """Full device rule loaded from library YAML."""

    name: str
    category: str
    description: str
    required_signals: tuple[SignalRule, ...]
    optional_signals: tuple[SignalRule, ...]


UNKNOWN_DEVICE = DeviceRule(
    name="Unknown",
    category="Unknown",
    description="Unknown device type. No library rule found.",
    required_signals=(),
    optional_signals=(),
)

_LIBRARY_SUBDIRS = (
    "Equipment",
    "equipment",
    "Instrument",
    "instrument",
)


class RuleEngine:
    """Loads and serves device rules from library YAML files."""

    def __init__(self, library_root: Path | str | None = None) -> None:
        if library_root is None:
            # app/engine/rule_engine.py -> project root / library
            library_root = Path(__file__).resolve().parents[2] / "library"
        self._library_root = Path(library_root)
        self._rules: dict[str, DeviceRule] = {}
        self.reload()

    def reload(self) -> None:
        """Reload all YAML rules from the library folders."""
        self._rules.clear()
        if not self._library_root.is_dir():
            return

        seen_dirs: set[Path] = set()
        for subdir_name in _LIBRARY_SUBDIRS:
            folder = self._library_root / subdir_name
            if not folder.is_dir():
                continue
            resolved = folder.resolve()
            if resolved in seen_dirs:
                continue
            seen_dirs.add(resolved)
            for path in sorted(folder.glob("*.yaml")):
                rule = self._load_yaml_file(path)
                if rule is not None:
                    self._rules[rule.name] = rule

    def load_rule(self, device_type: str) -> DeviceRule:
        """Return the rule for a device type, or Unknown Device if missing."""
        key = device_type.strip()
        if not key:
            return UNKNOWN_DEVICE
        return self._rules.get(key, UNKNOWN_DEVICE)

    def get_required_signals(self, device_type: str) -> tuple[SignalRule, ...]:
        """Return required signals for a device type."""
        return self.load_rule(device_type).required_signals

    def get_optional_signals(self, device_type: str) -> tuple[SignalRule, ...]:
        """Return optional signals for a device type."""
        return self.load_rule(device_type).optional_signals

    def available_types(self) -> tuple[str, ...]:
        """Return device type names currently loaded from the library."""
        return tuple(sorted(self._rules.keys()))

    def _load_yaml_file(self, path: Path) -> DeviceRule | None:
        try:
            with path.open(encoding="utf-8") as handle:
                data = yaml.safe_load(handle)
        except (OSError, yaml.YAMLError):
            return None

        if not isinstance(data, dict):
            return None

        name = str(data.get("name", "")).strip()
        if not name:
            return None

        return DeviceRule(
            name=name,
            category=str(data.get("category", "")).strip(),
            description=str(data.get("description", "")).strip(),
            required_signals=self._parse_signals(data.get("required_signals")),
            optional_signals=self._parse_signals(data.get("optional_signals")),
        )

    @staticmethod
    def _parse_signals(raw: object) -> tuple[SignalRule, ...]:
        if not isinstance(raw, list):
            return ()

        signals: list[SignalRule] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            signal_name = str(item.get("name", "")).strip()
            signal_type = str(item.get("signal_type", "")).strip()
            if not signal_name or not signal_type:
                continue
            signals.append(SignalRule(name=signal_name, signal_type=signal_type))
        return tuple(signals)
