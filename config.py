"""
Конфигурация завода
Здесь все параметры производства в одном месте
"""
import os

class Config:
    """Основные настройки"""
    
    # === РАЗМЕРЫ ЛИСТОВ ===
    SHEET_SIZES = {
        'standard': {
            'width': 1250,
            'height': 2500,
            'name': 'Стандарт 1.25x2.5м',
            'price_per_m2': 1200,
        },
        'large': {
            'width': 1500,
            'height': 3000,
            'name': 'Большой 1.5x3м',
            'price_per_m2': 1200,  # поставь реальную цену большого листа, обычно на 100-200 руб дороже
        }
    }
    
    DEFAULT_SHEET = 'standard'
    
    # === ДОПУСКИ И ЗАЗОРЫ ===
    CUT_TOLERANCE = 2          # мм на пропил лазера/плазмы
    DOOR_GAP = 2               # зазор между дверями
    EDGE_CLEARANCE = 1         # отступ от края
    MIN_EDGE_DISTANCE = 10     # минимум от края листа
    
    # === МАТЕРИАЛЫ ===
    DEFAULT_THICKNESS = 1.0    # мм
    STEEL_DENSITY = 7.85       # кг/м² на 1мм толщины
    
    THICKNESS_OPTIONS = [0.8, 1.0, 1.2, 1.5, 2.0, 3.0]
    
    # === ЦЕНЫ (можно редактировать) ===
    METAL_PRICE_PER_M2 = 1200  # руб/м²
    WORK_PRICE_PER_PART = 150  # руб за деталь (резка+гибка)
    WELDING_PRICE_PER_METER = 80  # руб/метр шва
    
    # === ПУТИ ===
    CAD_DIR = 'cad'

    # ПАПКИ ЗАКАЗОВ - основное место выгрузки. Внутри одна папка на заказ:
    #   cad/orders/2026-07-16_Иванов_Секция-с-ящиками/
    #       Раскрой.dxf, Чертежи.pdf, Спецификация.xlsx, Развёртки/ ...
    # Раньше всё сыпалось в две общие папки (dxf/ и reports/) с именами,
    # которые различались только секундами - при десятках заказов от разных
    # людей найти нужный было невозможно (см. core/order_paths.py).
    ORDERS_DIR = os.path.join(CAD_DIR, 'orders')

    # Старые общие папки. Оставлены: в них лежат ранее выгруженные файлы,
    # и в reports/ живёт общий индекс истории заказов (order_history.json).
    DXF_DIR = os.path.join(CAD_DIR, 'dxf')
    REPORTS_DIR = os.path.join(CAD_DIR, 'reports')
    TEMPLATES_DIR = 'templates'

    # Создать папки при запуске
    @classmethod
    def init_dirs(cls):
        for path in [cls.CAD_DIR, cls.ORDERS_DIR, cls.DXF_DIR,
                     cls.REPORTS_DIR, cls.TEMPLATES_DIR]:
            os.makedirs(path, exist_ok=True)