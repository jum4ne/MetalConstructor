from core.calculator import CabinetCalculator
import json


def load_project(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    cabinet = CabinetCalculator.calculate(
        height=data.get("height", 1800),
        width=data.get("width", 900),
        depth=data.get("depth", 500),
        shelves=data.get("shelves", 4),
        thickness=data.get("thickness", 1.0),
    )

    return cabinet, data