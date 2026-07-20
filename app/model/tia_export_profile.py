"""TIA Portal PLC Tag workbook export profile definitions."""

from __future__ import annotations

from dataclasses import dataclass, field

_TIA_V20_PLC_TAG_HEADERS = [
    "Name",
    "Path",
    "Data Type",
    "Logical Address",
    "Comment",
    "Hmi Visible",
    "Hmi Accessible",
    "Hmi Writeable",
    "Typeobject ID",
    "Version ID",
]

_TIA_V20_TAG_PROPERTY_HEADERS = [
    "Path",
    "BelongsToUnit",
    "Accessibility",
]


@dataclass
class TIAExportProfile:
    """Exact workbook structure for one TIA Portal PLC Tag export format."""

    profile_name: str
    tia_version: str
    plc_tags_sheet_name: str
    tag_properties_sheet_name: str
    plc_tag_headers: list[str] = field(default_factory=list)
    tag_property_headers: list[str] = field(default_factory=list)
    default_path: str = ""
    default_hmi_visible: bool = True
    default_hmi_accessible: bool = True
    default_hmi_writeable: bool = True
    default_typeobject_id: str = ""
    default_version_id: str = ""
    default_belongs_to_unit: str = ""
    default_accessibility: str = ""


TIA_V20_EXPORT_PROFILE = TIAExportProfile(
    profile_name="TIA Portal V20 PLC Tags",
    tia_version="V20",
    plc_tags_sheet_name="PLC Tags",
    tag_properties_sheet_name="TagTable Properties",
    plc_tag_headers=list(_TIA_V20_PLC_TAG_HEADERS),
    tag_property_headers=list(_TIA_V20_TAG_PROPERTY_HEADERS),
    default_path="test",
    default_hmi_visible=True,
    default_hmi_accessible=True,
    default_hmi_writeable=True,
    default_typeobject_id="",
    default_version_id="",
    default_belongs_to_unit="",
    default_accessibility="",
)


def get_tia_v20_profile() -> TIAExportProfile:
    """Return the verified TIA Portal V20 PLC Tag export profile."""
    return TIA_V20_EXPORT_PROFILE


def validate_export_profile(profile: TIAExportProfile) -> list[str]:
    """Return validation errors for a TIA export profile."""
    errors: list[str] = []

    if not profile.plc_tags_sheet_name.strip():
        errors.append("PLC Tags sheet name must not be blank.")
    if not profile.tag_properties_sheet_name.strip():
        errors.append("TagTable Properties sheet name must not be blank.")

    if profile.plc_tag_headers != _TIA_V20_PLC_TAG_HEADERS:
        errors.append(
            "PLC Tags headers do not match the verified TIA V20 structure."
        )
    if profile.tag_property_headers != _TIA_V20_TAG_PROPERTY_HEADERS:
        errors.append(
            "TagTable Properties headers do not match the verified TIA V20 structure."
        )

    if not profile.default_path.strip():
        errors.append("Default Path must not be blank.")

    # Reserved Siemens fields (Typeobject ID, Version ID, BelongsToUnit,
    # Accessibility) are allowed to be empty strings.

    return errors
