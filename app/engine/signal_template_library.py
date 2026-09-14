"""Signal Template library — loads Device Type templates from YAML rules."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import yaml

from app.engine.rule_engine import DeviceRule, RuleEngine, SignalRule, UNKNOWN_DEVICE
from app.model.device import Device
from app.model.signal import Signal
from app.model.signal_template import (
    SignalTemplate,
    TemplateIdentityError,
    TemplateSignal,
    make_template_id,
    make_template_signal_id,
    next_display_name,
    next_template_id,
    regenerate_signal_ids,
    template_to_yaml_data,
    validate_template,
)


def template_signal_from_rule(
    rule: SignalRule,
    *,
    device_type: str,
    order: int,
) -> TemplateSignal:
    """Map a library SignalRule to an independent TemplateSignal."""
    signal_id = rule.signal_id.strip() or make_template_signal_id(
        device_type,
        rule.name,
    )
    return TemplateSignal(
        id=signal_id,
        name=rule.name,
        signal_type=rule.signal_type,
        required=rule.required,
        description=rule.description,
        remark=rule.remark,
        default_enabled=rule.resolved_default_enabled,
        order=rule.order if rule.order != 0 else order,
    )


def template_from_device_rule(rule: DeviceRule) -> SignalTemplate:
    """Build a SignalTemplate from a loaded DeviceRule."""
    signals = tuple(
        template_signal_from_rule(
            item,
            device_type=rule.name,
            order=index,
        )
        for index, item in enumerate(rule.signals)
    )
    return SignalTemplate(
        id=rule.id,
        device_type=rule.name,
        category=rule.category,
        description=rule.description,
        signals=signals,
        source_path=rule.source_path,
    )


def write_yaml_atomic(path: Path | str, data: dict) -> None:
    """Write YAML via a temp file, validate, then atomically replace the target."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    text = yaml.safe_dump(
        data,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )
    tmp.write_text(text, encoding="utf-8", newline="\n")
    try:
        loaded = yaml.safe_load(tmp.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise TemplateIdentityError("Serialized YAML is not a mapping.")
        if not str(loaded.get("id", "")).strip() or not str(loaded.get("name", "")).strip():
            raise TemplateIdentityError("Serialized YAML is missing id or name.")
        tmp.replace(target)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


class SignalTemplateLibrary:
    """Load, query, and persist Signal Templates from the YAML library."""

    def __init__(
        self,
        *,
        rule_engine: RuleEngine | None = None,
        library_root: Path | str | None = None,
    ) -> None:
        if rule_engine is not None:
            self._rule_engine = rule_engine
        else:
            self._rule_engine = RuleEngine(library_root)
        self._templates: dict[str, SignalTemplate] = {}
        self._rebuild_working_set()

    @property
    def library_root(self) -> Path:
        """Configured YAML library root."""
        return self._rule_engine._library_root

    @property
    def load_errors(self) -> tuple[str, ...]:
        """Identity / load failures from the last reload."""
        return self._rule_engine.load_errors

    def reload(self) -> None:
        """Reload templates from YAML into the working set."""
        self._rule_engine.reload()
        self._rebuild_working_set()

    def _rebuild_working_set(self) -> None:
        templates: dict[str, SignalTemplate] = {}
        for name in self._rule_engine.available_types():
            rule = self._rule_engine.load_rule(name)
            if rule is UNKNOWN_DEVICE or rule.name == "Unknown":
                continue
            template = template_from_device_rule(rule)
            templates[template.id] = template
        self._templates = templates

    def device_types(self) -> tuple[str, ...]:
        """Return Device Type display names in the working set."""
        return tuple(sorted(item.device_type for item in self._templates.values()))

    @staticmethod
    def _clone(template: SignalTemplate) -> SignalTemplate:
        """Return a deep copy so callers cannot mutate working-set objects."""
        return SignalTemplate(
            id=template.id,
            device_type=template.device_type,
            category=template.category,
            description=template.description,
            signals=tuple(replace(item) for item in template.signals),
            source_path=template.source_path,
        )

    def get_template(self, device_type: str) -> SignalTemplate | None:
        """Return a copy of the working template for a Device Type name or id."""
        key = device_type.strip()
        if not key:
            return None
        found: SignalTemplate | None = None
        for template in self._templates.values():
            if template.device_type == key:
                found = template
                break
        if found is None:
            found = self._templates.get(key)
        if found is None:
            return None
        return self._clone(found)

    def get_template_by_id(self, template_id: str) -> SignalTemplate | None:
        """Return a copy of the working template for a persistent id, or None."""
        found = self._templates.get(template_id.strip())
        if found is None:
            return None
        return self._clone(found)

    def get_signals(self, device_type: str) -> tuple[TemplateSignal, ...]:
        """Return ordered template signals for a Device Type."""
        template = self.get_template(device_type)
        if template is None:
            return ()
        return template.signals_in_order()

    def load_all(self) -> tuple[SignalTemplate, ...]:
        """Return copies of every working template, sorted by Device Type."""
        return tuple(
            self._clone(item)
            for item in sorted(
                self._templates.values(),
                key=lambda item: item.device_type.casefold(),
            )
        )

    def copy_signals_for_type(self, device_type: str) -> list[Signal]:
        """Create independent Device Signal copies for a Device Type."""
        template = self.get_template(device_type)
        if template is None:
            return []
        return template.copy_signals()

    def apply_copy_to_device(self, device: Device) -> list[Signal]:
        """Copy the Device Type template onto the device as owned signals.

        Replaces device.signals with new copies. Does not keep template refs.
        """
        copies = self.copy_signals_for_type(device.type)
        device.clear_signals()
        for signal in copies:
            device.add_signal(signal)
        return copies

    def serialize_template(self, template: SignalTemplate) -> dict:
        """Return the canonical YAML-compatible mapping for a template."""
        return template_to_yaml_data(template)

    def create_template(
        self,
        *,
        display_name: str,
        template_id: str = "",
        category: str = "Equipment",
        description: str = "",
        signals: tuple[TemplateSignal, ...] | list[TemplateSignal] | None = None,
    ) -> SignalTemplate:
        """Create an unsaved template in the working set. Does not write YAML."""
        name = display_name.strip()
        if not name:
            raise TemplateIdentityError("Template display name is required.")
        existing_ids = tuple(self._templates)
        existing_names = self.device_types()
        if name in existing_names:
            raise TemplateIdentityError(f"Duplicate template name '{name}'.")

        explicit = template_id.strip()
        if explicit:
            new_id = explicit
        else:
            derived = make_template_id(name)
            new_id = (
                derived
                if derived not in self._templates
                else next_template_id(derived, existing_ids)
            )

        ordered = tuple(signals or ())
        template = SignalTemplate(
            id=new_id,
            device_type=name,
            category=(category or "Equipment").strip() or "Equipment",
            description=description,
            signals=tuple(
                replace(item, order=index) for index, item in enumerate(ordered)
            ),
            source_path="",
        )
        validate_template(template, other_ids=existing_ids, other_names=existing_names)
        self._templates[template.id] = template
        return self._clone(template)

    def update_template(self, template: SignalTemplate) -> SignalTemplate:
        """Replace a working template located by persistent id. Does not write YAML."""
        template_id = template.id.strip()
        current = self.get_template_by_id(template_id)
        if current is None:
            raise TemplateIdentityError(
                f"Cannot update unknown template id '{template_id}'."
            )
        other_ids = tuple(item for item in self._templates if item != current.id)
        other_names = tuple(
            item.device_type
            for item in self._templates.values()
            if item.id != current.id
        )
        updated = SignalTemplate(
            id=current.id,
            device_type=template.device_type.strip(),
            category=template.category,
            description=template.description,
            signals=tuple(
                replace(item, order=index)
                for index, item in enumerate(template.signals_in_order())
            ),
            source_path=current.source_path,
        )
        validate_template(updated, other_ids=other_ids, other_names=other_names)
        self._templates[updated.id] = updated
        return self._clone(updated)

    def delete_template(self, template_id: str, *, persist: bool = False) -> None:
        """Remove a template from the working set. Persist deletes its YAML file."""
        key = template_id.strip()
        current = self.get_template_by_id(key)
        if current is None:
            raise TemplateIdentityError(f"Cannot delete unknown template id '{key}'.")
        if persist:
            self._delete_source_file(current)
        del self._templates[current.id]
        if persist:
            self.reload()

    def duplicate_template(self, template_id: str) -> SignalTemplate:
        """Copy a template with a new id/name and regenerated signal ids.

        Does not write YAML. The duplicate is independent of the source.
        """
        source = self.get_template_by_id(template_id.strip())
        if source is None:
            source = self.get_template(template_id)
        if source is None:
            raise TemplateIdentityError(
                f"Cannot duplicate unknown template '{template_id}'."
            )
        new_name = next_display_name(source.device_type, self.device_types())
        derived_id = make_template_id(new_name)
        new_id = (
            derived_id
            if derived_id not in self._templates
            else next_template_id(source.id, self._templates)
        )
        duplicate = SignalTemplate(
            id=new_id,
            device_type=new_name,
            category=source.category,
            description=source.description,
            signals=regenerate_signal_ids(source.signals_in_order()),
            source_path="",
        )
        validate_template(
            duplicate,
            other_ids=tuple(self._templates),
            other_names=self.device_types(),
        )
        self._templates[duplicate.id] = duplicate
        return self._clone(duplicate)

    def save_template(
        self,
        template: SignalTemplate,
        path: Path | str | None = None,
    ) -> SignalTemplate:
        """Validate and atomically persist one template, then reload from disk."""
        existing = self.get_template_by_id(template.id)
        if existing is None:
            raise TemplateIdentityError(
                f"Cannot save unknown template id '{template.id}'."
            )
        other_ids = tuple(item for item in self._templates if item != existing.id)
        other_names = tuple(
            item.device_type
            for item in self._templates.values()
            if item.id != existing.id
        )
        to_save = SignalTemplate(
            id=existing.id,
            device_type=template.device_type.strip(),
            category=template.category,
            description=template.description,
            signals=tuple(
                replace(item, order=index)
                for index, item in enumerate(template.signals_in_order())
            ),
            source_path=existing.source_path,
        )
        validate_template(to_save, other_ids=other_ids, other_names=other_names)
        if path is not None:
            target = Path(path)
        else:
            target = self._assert_library_file_path(
                self._resolve_save_path(to_save),
                must_exist=False,
            )
        # Preserve other working-set edits across reload so saving B cannot
        # silently discard unsaved changes to A (Template Manager Save safety).
        preserved = {
            tid: self._clone(item)
            for tid, item in self._templates.items()
            if tid != to_save.id
        }
        write_yaml_atomic(target, template_to_yaml_data(to_save))
        self.reload()
        for tid, item in preserved.items():
            self._templates[tid] = item
        reloaded = self.get_template_by_id(to_save.id)
        if reloaded is None:
            raise TemplateIdentityError(
                f"Template '{to_save.id}' was written but did not reload."
            )
        return reloaded

    def _resolve_save_path(self, template: SignalTemplate) -> Path:
        if template.source_path.strip():
            return Path(template.source_path)
        category = template.category.strip() or "Equipment"
        if category.casefold() == "instrument":
            folder = "Instrument"
        else:
            folder = "Equipment"
        return self.library_root / folder / f"{template.id}.yaml"

    def _delete_source_file(self, template: SignalTemplate) -> None:
        raw = template.source_path.strip()
        if not raw:
            return
        path = Path(raw)
        owned = self._assert_library_file_path(path, must_exist=True)
        owned.unlink()

    def _assert_library_file_path(self, path: Path, *, must_exist: bool) -> Path:
        """Return a resolved .yaml path that is inside this library root."""
        root = self.library_root.resolve()
        candidate = path if path.is_absolute() else root / path
        try:
            resolved = candidate.resolve()
        except OSError as exc:
            raise TemplateIdentityError(f"Invalid template path '{path}': {exc}") from exc
        if resolved.suffix.casefold() != ".yaml":
            raise TemplateIdentityError(f"Template path is not a YAML file: {path}")
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise TemplateIdentityError(
                f"Template path is outside the library: {path}"
            ) from exc
        if resolved == root:
            raise TemplateIdentityError("Refusing to operate on the library root.")
        if resolved.is_dir():
            raise TemplateIdentityError(f"Refusing to operate on a directory: {path}")
        if must_exist and not resolved.is_file():
            raise TemplateIdentityError(f"Template source file not found: {path}")
        return resolved
