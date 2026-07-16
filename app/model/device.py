"""Device domain entity."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.model.signal import Signal


@dataclass
class Device:
    """Equipment unit within a project area."""

    id: str
    tag: str
    area: str
    category: str
    type: str
    description: str
    quantity: int
    signals: list[Signal] = field(default_factory=list)
    di_start_address: str = ""
    do_start_address: str = ""
    ai_start_address: str = ""
    ao_start_address: str = ""
    use_di_start_address: bool = False
    use_do_start_address: bool = False
    use_ai_start_address: bool = False
    use_ao_start_address: bool = False

    def add_signal(self, signal: Signal) -> None:
        """Attach a signal object to this device."""
        self.signals.append(signal)

    def remove_signal(self, signal: Signal) -> None:
        """Remove a signal object from this device if present."""
        if signal in self.signals:
            self.signals.remove(signal)

    def clear_signals(self) -> None:
        """Remove all signals from this device."""
        self.signals.clear()
