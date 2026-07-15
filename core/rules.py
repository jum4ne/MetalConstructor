from config import Config

class Rules:
    DOOR_GAP = Config.DOOR_GAP
    CUT_TOLERANCE = Config.CUT_TOLERANCE
    EDGE_CLEARANCE = Config.EDGE_CLEARANCE
    MIN_EDGE_DISTANCE = Config.MIN_EDGE_DISTANCE
    DEFAULT_THICKNESS = Config.DEFAULT_THICKNESS
    STEEL_DENSITY = Config.STEEL_DENSITY
    SHEET_WIDTH = Config.SHEET_SIZES[Config.DEFAULT_SHEET]['width']
    SHEET_HEIGHT = Config.SHEET_SIZES[Config.DEFAULT_SHEET]['height']
    METAL_PRICE_PER_M2 = Config.METAL_PRICE_PER_M2
    WORK_PRICE_PER_PART = Config.WORK_PRICE_PER_PART

    @classmethod
    def set_sheet_size(cls, size_key):
        if size_key in Config.SHEET_SIZES:
            sheet = Config.SHEET_SIZES[size_key]
            cls.SHEET_WIDTH = sheet['width']
            cls.SHEET_HEIGHT = sheet['height']
            return True
        return False

    @classmethod
    def set_custom_sheet_size(cls, width, height):
        """Задать нестандартный размер листа вручную (под конкретный заказ)"""
        cls.SHEET_WIDTH = width
        cls.SHEET_HEIGHT = height

    @classmethod
    def get_available_sheets(cls):
        return {k: f"{v['name']} ({v['width']}x{v['height']}мм)" for k, v in Config.SHEET_SIZES.items()}