"""Domain model layer.

Pure data entities only — no business logic.
"""

from app.model.area import Area
from app.model.device import Device
from app.model.fc_io_row import FCIORow
from app.model.generate_item import GenerateItem
from app.model.plc_card_config import PlcCardConfig, default_plc_card_configurations
from app.model.plc_module_mapping import (
    PLCChannelAssignment,
    PLCChannelMapping,
    PLCModuleMapping,
    PLCModuleMappingResult,
)
from app.model.project import Project
from app.model.recommendation import IoSummary, Recommendation, RecommendationResult
from app.model.rules import Rules
from app.model.signal import Signal

__all__ = [
    "Area",
    "Device",
    "FCIORow",
    "GenerateItem",
    "IoSummary",
    "PLCChannelAssignment",
    "PLCChannelMapping",
    "PLCModuleMapping",
    "PLCModuleMappingResult",
    "PlcCardConfig",
    "Project",
    "Recommendation",
    "RecommendationResult",
    "Rules",
    "Signal",
    "default_plc_card_configurations",
]
