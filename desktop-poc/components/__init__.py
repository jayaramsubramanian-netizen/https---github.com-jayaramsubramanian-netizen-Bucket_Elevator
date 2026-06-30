"""
components -- every ported piece of the desktop app, one module per
original JSX component (elevation_view.py ~ ElevatorSchematic.jsx,
equipment_tree.py ~ EquipmentTree.jsx, etc), plus one module per
InputSidebar section dialog once it grew past a single file (takeup_edit.py,
feed_edit.py, discharge_edit.py, etc -- see dialog_helpers.py for the
shared widgets these all import instead of duplicating).

Re-exporting here so main.py (and anything else) can do:
    from components import ElevationView, EquipmentTreePanel
instead of reaching into each submodule individually. As each new
component or section dialog gets ported, add its import here too -- this
file is the one place that lists everything available in the package,
which matters more as this folder grows past a couple of files.
"""
from .elevation_view import ElevationView
from .equipment_tree import EquipmentTreePanel
from .input_sidebar import InputSidebarPanel
from .takeup_edit import TakeupEditDialog
from .feed_edit import FeedEditDialog
from .discharge_edit import DischargeEditDialog
from .casing_edit import CasingEditDialog
from .service_edit import ServiceEditDialog
from .power_edit import PowerEditDialog
from .status_panel import StatusPanel
from .optimizer_panel import OptimizerPanel
from .bom_panel import BomPanel
from .status_design_leaves import StatusDesignLeaves
from .maintenance_panel import MaintenancePanel
from .checks_panel import ChecksPanel
from .design_review_panel import DesignReviewPanel

__all__ = [
    "ElevationView", "EquipmentTreePanel", "InputSidebarPanel",
    "TakeupEditDialog", "FeedEditDialog", "DischargeEditDialog", "CasingEditDialog",
    "ServiceEditDialog", "PowerEditDialog", "StatusPanel", "OptimizerPanel",
    "BomPanel", "StatusDesignLeaves", "MaintenancePanel", "ChecksPanel", "DesignReviewPanel",
]