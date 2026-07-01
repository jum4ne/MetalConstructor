from core.models import Part


class CabinetCalculator:

    @staticmethod
    def calculate(
        height,
        width,
        depth,
        shelves,
        thickness
    ):

        parts = []

        parts.append(
            Part(
                "Боковина",
                depth,
                height,
                2,
                thickness
            )
        )

        parts.append(
            Part(
                "Крыша",
                width,
                depth,
                1,
                thickness
            )
        )

        parts.append(
            Part(
                "Дно",
                width,
                depth,
                1,
                thickness
            )
        )

        parts.append(
            Part(
                "Полка",
                width,
                depth - 20,
                shelves,
                thickness
            )
        )

        door_width = width // 2 - 2

        parts.append(
            Part(
                "Дверь",
                door_width,
                height - 2,
                2,
                thickness
            )
        )

        return parts