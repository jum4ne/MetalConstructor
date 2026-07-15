"""
Хранилище пользовательских настроек: settings.json в папке проекта.
Позволяет менять цены, толщины, зазоры и типоразмеры листов без правки кода.

При первом запуске файла нет - берутся значения-дефолты из config.py.
После первого сохранения появляется settings.json, и Config.SHEET_SIZES,
Config.METAL_PRICE_PER_M2 и остальные атрибуты класса Config подменяются
на пользовательские значения при старте приложения (см. app.py).

Это позволяет менять настройки прямо из GUI, и они переживают перезапуск
и обновление exe (settings.json лежит рядом с exe, а не внутри него).
"""
import json
import os
from config import Config


SETTINGS_FILE = "settings.json"


def get_defaults():
    """Значения по умолчанию (из config.py). Используются, если settings.json нет"""
    return {
        "metal_price_per_m2": Config.METAL_PRICE_PER_M2,
        "work_price_per_part": Config.WORK_PRICE_PER_PART,
        "default_thickness": Config.DEFAULT_THICKNESS,
        "steel_density": Config.STEEL_DENSITY,
        "cut_tolerance": Config.CUT_TOLERANCE,
        "door_gap": Config.DOOR_GAP,
        "edge_clearance": Config.EDGE_CLEARANCE,
        "min_edge_distance": Config.MIN_EDGE_DISTANCE,
        "thickness_options": [0.8, 1.0, 1.2, 1.5, 2.0, 3.0],
        "sheet_sizes": [
            {"key": key, "width": info["width"], "height": info["height"],
             "name": info["name"],
             "price_per_m2": info.get("price_per_m2", Config.METAL_PRICE_PER_M2)}
            for key, info in Config.SHEET_SIZES.items()
        ],
        # Синхронизация с сервером (тот же, что использует мобильное приложение).
        # Пусто по умолчанию - без сервера программа работает полностью локально.
        "server_url": "",
        "server_password": "",
    }


def load_settings():
    """Загрузить настройки из settings.json или вернуть дефолты"""
    if not os.path.exists(SETTINGS_FILE):
        return get_defaults()
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Дозаполняем недостающие ключи дефолтами (на случай, если файл старый
        # и в нём нет новых опций - иначе программа упадёт)
        defaults = get_defaults()
        for key, value in defaults.items():
            data.setdefault(key, value)
        return data
    except (json.JSONDecodeError, OSError):
        return get_defaults()


def save_settings(settings):
    """Записать настройки в settings.json"""
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)


def apply_to_config(settings):
    """
    Применить настройки к классу Config - подменяем атрибуты.
    Вызывается один раз при старте приложения (в app.py).

    Это работает, потому что весь остальной код обращается к Config.<ATTR>
    через класс, а не хранит копии значений в момент импорта. Единственное
    исключение - core/rules.py, но там значения тоже читаются из Config при
    старте, а Rules.set_sheet_size() и Rules.set_custom_sheet_size() потом
    их перезаписывают, если пользователь меняет размер листа в UI.
    """
    Config.METAL_PRICE_PER_M2 = settings["metal_price_per_m2"]
    Config.WORK_PRICE_PER_PART = settings["work_price_per_part"]
    Config.DEFAULT_THICKNESS = settings["default_thickness"]
    Config.STEEL_DENSITY = settings["steel_density"]
    Config.CUT_TOLERANCE = settings["cut_tolerance"]
    Config.DOOR_GAP = settings["door_gap"]
    Config.EDGE_CLEARANCE = settings["edge_clearance"]
    Config.MIN_EDGE_DISTANCE = settings["min_edge_distance"]
    Config.THICKNESS_OPTIONS = list(settings["thickness_options"])

    # Пересобираем словарь SHEET_SIZES
    Config.SHEET_SIZES = {
        sheet["key"]: {
            "width": sheet["width"],
            "height": sheet["height"],
            "name": sheet["name"],
            "price_per_m2": sheet["price_per_m2"],
        }
        for sheet in settings["sheet_sizes"]
    }
    if Config.SHEET_SIZES and Config.DEFAULT_SHEET not in Config.SHEET_SIZES:
        Config.DEFAULT_SHEET = next(iter(Config.SHEET_SIZES))

    # Перезагружаем Rules, чтобы они подхватили новые дефолты
    from core.rules import Rules
    Rules.DOOR_GAP = Config.DOOR_GAP
    Rules.CUT_TOLERANCE = Config.CUT_TOLERANCE
    Rules.EDGE_CLEARANCE = Config.EDGE_CLEARANCE
    Rules.MIN_EDGE_DISTANCE = Config.MIN_EDGE_DISTANCE
    Rules.DEFAULT_THICKNESS = Config.DEFAULT_THICKNESS
    Rules.STEEL_DENSITY = Config.STEEL_DENSITY
    Rules.METAL_PRICE_PER_M2 = Config.METAL_PRICE_PER_M2
    Rules.WORK_PRICE_PER_PART = Config.WORK_PRICE_PER_PART
    if Config.SHEET_SIZES:
        default_sheet = Config.SHEET_SIZES[Config.DEFAULT_SHEET]
        Rules.SHEET_WIDTH = default_sheet["width"]
        Rules.SHEET_HEIGHT = default_sheet["height"]
