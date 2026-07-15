"""Left-side project tree widget."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from app.common.constants import COMMON_SUBNODES, PROJECT_AREAS, PROJECT_ROOT_LABEL
from app.model.device import Device

KIND_PROJECT = "project"
KIND_AREA = "area"
KIND_SUBNODE = "subnode"
KIND_TYPE = "type"
KIND_DEVICE = "device"

ROLE_KIND = Qt.ItemDataRole.UserRole
ROLE_DEVICE_ID = Qt.ItemDataRole.UserRole + 1


class ProjectTreeWidget(QWidget):
    """Project hierarchy shown in a QTreeWidget."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("projectTreePanel")

        self.tree = QTreeWidget()
        self._project_root: QTreeWidgetItem | None = None
        self._area_items: dict[str, QTreeWidgetItem] = {}

        self._build_ui()
        self._populate_tree()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tree.setObjectName("projectTree")
        self.tree.setHeaderLabel("Project Tree")
        self.tree.setRootIsDecorated(True)
        self.tree.setUniformRowHeights(True)
        layout.addWidget(self.tree)

    def _populate_tree(self) -> None:
        self.tree.clear()
        self._area_items.clear()

        root = QTreeWidgetItem([PROJECT_ROOT_LABEL])
        root.setData(0, ROLE_KIND, KIND_PROJECT)
        self.tree.addTopLevelItem(root)
        self._project_root = root

        for area_name in PROJECT_AREAS:
            area_item = QTreeWidgetItem([area_name])
            area_item.setData(0, ROLE_KIND, KIND_AREA)
            root.addChild(area_item)
            self._area_items[area_name] = area_item

            if area_name == "COMMON":
                for sub_name in COMMON_SUBNODES:
                    sub_item = QTreeWidgetItem([sub_name])
                    sub_item.setData(0, ROLE_KIND, KIND_SUBNODE)
                    area_item.addChild(sub_item)

        self.tree.expandItem(root)
        self.tree.expandItem(self._area_items["COMMON"])

    def ensure_area(self, area_name: str) -> QTreeWidgetItem:
        """Return the area node, creating it under Project if missing."""
        if area_name in self._area_items:
            return self._area_items[area_name]

        if self._project_root is None:
            raise RuntimeError("Project tree root is not initialized.")

        area_item = QTreeWidgetItem([area_name])
        area_item.setData(0, ROLE_KIND, KIND_AREA)
        self._project_root.addChild(area_item)
        self._area_items[area_name] = area_item
        return area_item

    def ensure_type(self, area_name: str, type_name: str) -> QTreeWidgetItem:
        """Return the device-type node under an area, creating it if missing."""
        area_item = self.ensure_area(area_name)
        for index in range(area_item.childCount()):
            child = area_item.child(index)
            if (
                child.data(0, ROLE_KIND) == KIND_TYPE
                and child.text(0) == type_name
            ):
                return child

        type_item = QTreeWidgetItem([type_name])
        type_item.setData(0, ROLE_KIND, KIND_TYPE)
        area_item.addChild(type_item)
        return type_item

    def add_device(self, device: Device) -> QTreeWidgetItem | None:
        """Insert device under Area → Type → Tag. Skips duplicate tags in the tree."""
        if self.find_device_item_by_tag(device.tag) is not None:
            return None

        type_item = self.ensure_type(device.area, device.type)
        device_item = QTreeWidgetItem([device.tag])
        device_item.setData(0, ROLE_KIND, KIND_DEVICE)
        device_item.setData(0, ROLE_DEVICE_ID, device.id)
        type_item.addChild(device_item)

        self.tree.expandItem(self._area_items.get(device.area))
        self.tree.expandItem(type_item)
        return device_item

    def find_device_item_by_tag(self, tag: str) -> QTreeWidgetItem | None:
        """Find a device node by tag anywhere under Project."""
        if self._project_root is None:
            return None
        return self._find_device_item(self._project_root, tag)

    def selected_device_id(self) -> str | None:
        """Return the selected device id, or None if selection is not a device."""
        items = self.tree.selectedItems()
        if not items:
            return None
        item = items[0]
        if item.data(0, ROLE_KIND) != KIND_DEVICE:
            return None
        device_id = item.data(0, ROLE_DEVICE_ID)
        return str(device_id) if device_id is not None else None

    def select_device_item(self, item: QTreeWidgetItem) -> None:
        """Select and reveal a device tree item."""
        self.tree.setCurrentItem(item)

    def find_device_item_by_id(self, device_id: str) -> QTreeWidgetItem | None:
        """Find a device node by device id."""
        if self._project_root is None:
            return None
        return self._find_device_item_by_id(self._project_root, device_id)

    def remove_device_by_id(self, device_id: str) -> bool:
        """Remove a device node. Also drops an empty type folder."""
        item = self.find_device_item_by_id(device_id)
        if item is None:
            return False

        type_item = item.parent()
        if type_item is None:
            return False

        type_item.removeChild(item)

        if (
            type_item.data(0, ROLE_KIND) == KIND_TYPE
            and type_item.childCount() == 0
        ):
            area_item = type_item.parent()
            if area_item is not None:
                area_item.removeChild(type_item)

        return True

    def _find_device_item(
        self,
        parent: QTreeWidgetItem,
        tag: str,
    ) -> QTreeWidgetItem | None:
        for index in range(parent.childCount()):
            child = parent.child(index)
            if child.data(0, ROLE_KIND) == KIND_DEVICE and child.text(0) == tag:
                return child
            found = self._find_device_item(child, tag)
            if found is not None:
                return found
        return None

    def _find_device_item_by_id(
        self,
        parent: QTreeWidgetItem,
        device_id: str,
    ) -> QTreeWidgetItem | None:
        for index in range(parent.childCount()):
            child = parent.child(index)
            if (
                child.data(0, ROLE_KIND) == KIND_DEVICE
                and str(child.data(0, ROLE_DEVICE_ID)) == device_id
            ):
                return child
            found = self._find_device_item_by_id(child, device_id)
            if found is not None:
                return found
        return None
