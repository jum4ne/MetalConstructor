"""
Сохранение / загрузка модулей и проектов кухни в JSON.
Сохраняются реальные детали (включая вырезы и линии гиба) —
при загрузке НЕ пересчитываются заново, а восстанавливаются как есть.
"""
import json
import dataclasses
from core.models import Part, BendLine, Cutout
from core.module import Module
from core.kitchen_project import KitchenProject


def _part_to_dict(part):
    return dataclasses.asdict(part)


def _dict_to_part(d):
    bend_lines = [BendLine(**b) for b in d.get('bend_lines', [])]
    cutouts = [Cutout(**c) for c in d.get('cutouts', [])]
    return Part(
        name=d['name'],
        width=d['width'],
        height=d['height'],
        quantity=d.get('quantity', 1),
        thickness=d.get('thickness', 1.0),
        bend_lines=bend_lines,
        cutouts=cutouts,
    )


def _module_to_dict(module):
    return {
        'name': module.name,
        'module_type': getattr(module, 'module_type', 'Модуль'),
        'height': getattr(module, 'height', 0),
        'width': getattr(module, 'width', 0),
        'depth': getattr(module, 'depth', 0),
        'thickness': getattr(module, 'thickness', 1.0),
        'parts': [_part_to_dict(p) for p in module.parts],
    }


def _dict_to_module(d):
    module = Module(
        name=d['name'],
        module_type=d.get('module_type', 'Модуль'),
        height=d.get('height', 0),
        width=d.get('width', 0),
        depth=d.get('depth', 0),
        thickness=d.get('thickness', 1.0),
    )
    for pd in d.get('parts', []):
        module.add_part(_dict_to_part(pd))
    return module


def save_module(module, path):
    """Сохранить один модуль (шкаф, тумбу и т.д.) в JSON"""
    data = {'type': 'module', **_module_to_dict(module)}
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_module(path):
    """Загрузить один модуль из JSON. Понимает старый формат (только габариты
    шкафа, без сохранённых деталей) и новый (с полным набором деталей)."""
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if data.get('type') == 'module' and 'parts' in data:
        return _dict_to_module(data), data

    if data.get('type') == 'kitchen_project':
        raise ValueError(
            "Это файл проекта кухни (несколько модулей), а не одного модуля. "
            "Открой его через 'Загрузить проект' в блоке 'Проект кухни'."
        )

    # старый формат: только height/width/depth/shelves/thickness для шкафа
    from core.calculator import CabinetCalculator
    module = CabinetCalculator.calculate(
        height=data.get('height', 1800),
        width=data.get('width', 900),
        depth=data.get('depth', 500),
        shelves=data.get('shelves', 4),
        thickness=data.get('thickness', 1.0),
    )
    return module, data


def save_kitchen_project(project, path):
    """Сохранить проект кухни (несколько модулей) в JSON - вместе с позицией
    и углом поворота каждого модуля (иначе при повторной загрузке ручная
    раскладка кухни потеряется и все модули встанут обратно в ряд)."""
    placements = getattr(project, 'placements', None) or []
    data = {
        'type': 'kitchen_project',
        'name': project.name,
        'client': project.client,
        'modules': [_module_to_dict(m) for m in project.modules],
        'placements': [
            {'x': p.x, 'y': p.y, 'angle': p.angle} for p in placements
        ],
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_kitchen_project(path):
    """Загрузить проект кухни из JSON"""
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if data.get('type') != 'kitchen_project':
        raise ValueError(
            "Это файл одного модуля, а не проекта кухни. "
            "Открой его через 'Открыть проект' в верхнем блоке."
        )

    project = KitchenProject(name=data.get('name', 'Проект'), client=data.get('client', ''))
    placements_data = data.get('placements', [])
    for i, md in enumerate(data.get('modules', [])):
        placement = placements_data[i] if i < len(placements_data) else None
        if placement:
            project.add_module(_dict_to_module(md), x=placement.get('x'),
                                y=placement.get('y'), angle=placement.get('angle', 0))
        else:
            # старые файлы проектов без сохранённых позиций - авто-раскладка в ряд
            project.add_module(_dict_to_module(md))
    return project