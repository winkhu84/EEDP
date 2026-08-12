"""Rule Engine — loads device rules from the YAML library."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from app.model.signal_template import (
    TemplateIdentityError,
    resolve_signal_id,
    resolve_template_id,
)


@dataclass(frozen=True)
class SignalRule:
    """One signal definition from a library rule file."""

    name: str
    signal_type: str
    description: str = ""
    required: bool = True
    remark: str = ""
    default_enabled: bool | None = None
    signal_id: str = ""
    order: int = 0

    @property
    def resolved_default_enabled(self) -> bool:
        """Return explicit default_enabled, otherwise match required."""
        if self.default_enabled is None:
            return self.required
        return self.default_enabled


@dataclass(frozen=True)
class DeviceRule:
    """Full device rule loaded from library YAML."""

    name: str
    category: str
    description: str
    signals: tuple[SignalRule, ...]
    id: str = ""

    @property
    def required_signals(self) -> tuple[SignalRule, ...]:
        """Required signals in library order."""
        return tuple(item for item in self.signals if item.required)

    @property
    def optional_signals(self) -> tuple[SignalRule, ...]:
        """Optional signals in library order."""
        return tuple(item for item in self.signals if not item.required)


UNKNOWN_DEVICE = DeviceRule(
    name="Unknown",
    category="Unknown",
    description="Unknown device type. No library rule found.",
    signals=(),
    id="unknown",
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
        self._rules_by_id: dict[str, DeviceRule] = {}
        self._load_errors: tuple[str, ...] = ()
        self.reload()

    @property
    def load_errors(self) -> tuple[str, ...]:
        """Human-readable identity / load failures from the last reload."""
        return self._load_errors

    def reload(self) -> None:
        """Reload all YAML rules from the library folders."""
        self._rules.clear()
        self._rules_by_id.clear()
        errors: list[str] = []
        if not self._library_root.is_dir():
            self._load_errors = tuple(errors)
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
                rule = self._load_yaml_file(path, errors)
                if rule is None:
                    continue
                if rule.id in self._rules_by_id:
                    existing = self._rules_by_id[rule.id]
                    errors.append(
                        f"Duplicate template id '{rule.id}' in {path.name} "
                        f"(already used by '{existing.name}')."
                    )
                    continue
                if rule.name in self._rules:
                    errors.append(
                        f"Duplicate template name '{rule.name}' in {path.name}."
                    )
                    continue
                self._rules[rule.name] = rule
                self._rules_by_id[rule.id] = rule

        self._load_errors = tuple(errors)

    def load_rule(self, device_type: str) -> DeviceRule:
        """Return the rule for a device type name or id, or Unknown Device."""
        key = device_type.strip()
        if not key:
            return UNKNOWN_DEVICE
        return self._rules.get(key) or self._rules_by_id.get(key, UNKNOWN_DEVICE)

    def get_required_signals(self, device_type: str) -> tuple[SignalRule, ...]:
        """Return required signals for a device type."""
        return self.load_rule(device_type).required_signals

    def get_optional_signals(self, device_type: str) -> tuple[SignalRule, ...]:
        """Return optional signals for a device type."""
        return self.load_rule(device_type).optional_signals

    def available_types(self) -> tuple[str, ...]:
        """Return device type names currently loaded from the library."""
        return tuple(sorted(self._rules.keys()))

    def _load_yaml_file(
        self,
        path: Path,
        errors: list[str],
    ) -> DeviceRule | None:
        try:
            with path.open(encoding="utf-8") as handle:
                data = yaml.safe_load(handle)
        except (OSError, yaml.YAMLError) as exc:
            errors.append(f"Failed to read {path.name}: {exc}")
            return None

        if not isinstance(data, dict):
            errors.append(f"Invalid YAML structure in {path.name}.")
            return None

        name = str(data.get("name", "")).strip()
        if not name:
            errors.append(f"Missing template name in {path.name}.")
            return None

        try:
            template_id = resolve_template_id(str(data.get("id", "")), name)
            signals = self._parse_device_signals(data, device_type=name)
            self._validate_signal_ids(signals, path.name)
        except TemplateIdentityError as exc:
            errors.append(f"{path.name}: {exc}")
            return None

        return DeviceRule(
            name=name,
            category=str(data.get("category", "")).strip(),
            description=str(data.get("description", "")).strip(),
            signals=signals,
            id=template_id,
        )

    @classmethod
    def _parse_device_signals(
        cls,
        data: dict,
        *,
        device_type: str,
    ) -> tuple[SignalRule, ...]:
        """Prefer ordered `signals`; fall back to required + optional lists."""
        raw_signals = data.get("signals")
        if isinstance(raw_signals, list):
            return cls._parse_signals(
                raw_signals,
                default_required=True,
                device_type=device_type,
                start_order=0,
            )

        required = cls._parse_signals(
            data.get("required_signals"),
            default_required=True,
            device_type=device_type,
            start_order=0,
        )
        optional = cls._parse_signals(
            data.get("optional_signals"),
            default_required=False,
            device_type=device_type,
            start_order=len(required),
        )
        return required + optional

    @staticmethod
    def _parse_signals(
        raw: object,
        *,
        default_required: bool,
        device_type: str = "",
        start_order: int = 0,
    ) -> tuple[SignalRule, ...]:
        if not isinstance(raw, list):
            return ()

        signals: list[SignalRule] = []
        order = start_order
        for item in raw:
            if not isinstance(item, dict):
                continue
            signal_name = str(item.get("name", "")).strip()
            signal_type = str(
                item.get("signal_type", item.get("io_type", ""))
            ).strip()
            description = str(item.get("description", "")).strip()
            remark = str(item.get("remark", "")).strip()
            if not signal_name or not signal_type:
                continue
            if "required" in item:
                required = bool(item.get("required"))
            else:
                required = default_required
            if "default_enabled" in item:
                default_enabled: bool | None = bool(item.get("default_enabled"))
            else:
                default_enabled = None
            if "order" in item:
                try:
                    order_value = int(item.get("order"))
                except (TypeError, ValueError):
                    order_value = order
            else:
                order_value = order
            signal_id = resolve_signal_id(
                str(item.get("id", "")),
                device_type=device_type,
                signal_name=signal_name,
            )
            signals.append(
                SignalRule(
                    name=signal_name,
                    signal_type=signal_type,
                    description=description,
                    required=required,
                    remark=remark,
                    default_enabled=default_enabled,
                    signal_id=signal_id,
                    order=order_value,
                )
            )
            order += 1
        return tuple(signals)

    @staticmethod
    def _validate_signal_ids(signals: tuple[SignalRule, ...], filename: str) -> None:
        seen: set[str] = set()
        for item in signals:
            if not item.signal_id:
                raise TemplateIdentityError(
                    f"Empty signal id in {filename} ({item.name})."
                )
            if item.signal_id in seen:
                raise TemplateIdentityError(
                    f"Duplicate signal id '{item.signal_id}' in {filename}."
                )
            seen.add(item.signal_id)
