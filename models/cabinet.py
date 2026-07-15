from dataclasses import dataclass
from core.module import Module

@dataclass
class Cabinet(Module):
    """Закрытый шкаф с дверями (совместим со старым кодом)"""
    module_type: str = "Шкаф"

    @property
    def door_gap(self):
        from core.rules import Rules
        return Rules.DOOR_GAP