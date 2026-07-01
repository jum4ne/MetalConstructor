from dataclasses import dataclass


@dataclass
class Part:
    """Описание одной детали."""

    name: str
    width: int
    height: int
    quantity: int = 1
    thickness: float = 1.0

    @property
    def area(self):
        return (self.width * self.height) / 1_000_000

    def __str__(self):
        return (
            f"{self.name}: "
            f"{self.width}×{self.height} мм  "
            f"x{self.quantity}"
        )