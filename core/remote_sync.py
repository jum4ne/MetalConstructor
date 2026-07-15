"""
Синхронизация десктопной программы с сервером (тем же, что использует
мобильное приложение). Работает по принципу "по возможности":
- если сервер не настроен (в settings.json нет server_url) - ничего не делает,
  программа работает как раньше, полностью локально;
- если сервер настроен, но недоступен (нет интернета, сервер выключен) -
  ошибка молча логируется в консоль, но НЕ мешает работе программы
  (DXF/PDF/Excel экспортируются как обычно, просто заказ не попадёт
  в общий список, пока связь не восстановится).

Требует библиотеку requests (добавлена в requirements.txt).
"""
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    # requests нужен только для синхронизации с сервером - если библиотека
    # не установлена (забыли сделать pip install -r requirements.txt), вся
    # остальная программа должна продолжать работать локально, а не падать.
    REQUESTS_AVAILABLE = False

from core.builders import MODULE_TYPE_BY_LABEL
from core.settings_store import load_settings

TIMEOUT = 5  # секунд - не подвешивать программу, если сервер не отвечает


def _server_config():
    settings = load_settings()
    url = settings.get("server_url", "").rstrip("/")
    password = settings.get("server_password", "")
    return url, password


def is_configured():
    url, _ = _server_config()
    return bool(url)


def _headers(password):
    return {"Content-Type": "application/json", "X-Access-Password": password}


def _module_to_spec(module):
    """Собрать ModuleSpec-совместимый словарь из объекта Module/Cabinet"""
    module_type = MODULE_TYPE_BY_LABEL.get(module.module_type, "cabinet")
    shelves = next((p.quantity for p in module.parts if p.name == "Полка"), 0)
    return {
        "type": module_type,
        "width": module.width,
        "depth": module.depth,
        "height": module.height,
        "thickness": module.thickness,
        "shelves": shelves,
    }


def push_module_order(name, client, module, report):
    """Отправить одиночный модуль на сервер как заказ. Возвращает True/False."""
    if not REQUESTS_AVAILABLE:
        return False
    url, password = _server_config()
    if not url:
        return False
    try:
        payload = {
            "name": name,
            "client": client or "",
            "order_type": "module",
            "module": _module_to_spec(module),
        }
        resp = requests.post(f"{url}/orders", json=payload, headers=_headers(password), timeout=TIMEOUT)
        return resp.status_code == 200
    except requests.RequestException as e:
        print(f"[remote_sync] Не удалось отправить заказ на сервер: {e}")
        return False


def push_project_order(project, report):
    """Отправить проект кухни на сервер как заказ. Возвращает True/False."""
    if not REQUESTS_AVAILABLE:
        return False
    url, password = _server_config()
    if not url:
        return False
    try:
        payload = {
            "name": project.name,
            "client": project.client or "",
            "order_type": "project",
            "modules": [_module_to_spec(m) for m in project.modules],
        }
        resp = requests.post(f"{url}/orders", json=payload, headers=_headers(password), timeout=TIMEOUT)
        return resp.status_code == 200
    except requests.RequestException as e:
        print(f"[remote_sync] Не удалось отправить проект на сервер: {e}")
        return False


def fetch_orders():
    """Получить единый список заказов с сервера. Возвращает список или None при ошибке."""
    if not REQUESTS_AVAILABLE:
        return None
    url, password = _server_config()
    if not url:
        return None
    try:
        resp = requests.get(f"{url}/orders", headers=_headers(password), timeout=TIMEOUT)
        if resp.status_code == 200:
            return resp.json()
        return None
    except requests.RequestException as e:
        print(f"[remote_sync] Не удалось получить заказы с сервера: {e}")
        return None


def update_order_status(order_id, status):
    """Обновить статус заказа на сервере. Возвращает True/False."""
    if not REQUESTS_AVAILABLE:
        return False
    url, password = _server_config()
    if not url:
        return False
    try:
        resp = requests.patch(
            f"{url}/orders/{order_id}/status", json={"status": status},
            headers=_headers(password), timeout=TIMEOUT,
        )
        return resp.status_code == 200
    except requests.RequestException as e:
        print(f"[remote_sync] Не удалось обновить статус на сервере: {e}")
        return False


def fetch_order_detail(order_id):
    """Получить заказ целиком (с payload для пересборки) для 'Загрузить в расчёт'.
    Возвращает dict или None при ошибке."""
    if not REQUESTS_AVAILABLE:
        return None
    url, password = _server_config()
    if not url:
        return None
    try:
        resp = requests.get(f"{url}/orders/{order_id}", headers=_headers(password), timeout=TIMEOUT)
        if resp.status_code == 200:
            return resp.json()
        return None
    except requests.RequestException as e:
        print(f"[remote_sync] Не удалось получить заказ #{order_id} с сервера: {e}")
        return None


def rebuild_module_from_spec(spec):
    """Собрать объект Module/Cabinet из спеки {type, width, depth, height, thickness, shelves} -
    то же самое, что делает сервер, только локально на компе, теми же билдерами."""
    from core.calculator import CabinetCalculator
    from core.builders import TumbaBuilder, SinkCabinetBuilder, GrillCabinetBuilder, CountertopBuilder

    module_type = spec['type']
    width, depth = spec['width'], spec['depth']
    height = spec.get('height', 0)
    thickness = spec.get('thickness', 1.0)
    shelves = spec.get('shelves', 0)

    if module_type == "cabinet":
        return CabinetCalculator.calculate(height, width, depth, shelves, thickness)
    elif module_type == "tumba":
        return TumbaBuilder.build(height, width, depth, thickness, shelves=shelves)
    elif module_type == "sink_cabinet":
        return SinkCabinetBuilder.build(height, width, depth, thickness)
    elif module_type == "grill_cabinet":
        return GrillCabinetBuilder.build(height, width, depth, thickness)
    elif module_type == "countertop":
        return CountertopBuilder.build(width, depth, thickness)
    raise ValueError(f"Неизвестный тип модуля в заказе: {module_type}")


def rebuild_from_order_detail(detail):
    """Пересобрать Module или KitchenProject из полного заказа (fetch_order_detail).
    Возвращает (obj, kind) где kind - 'module' или 'project'."""
    from core.kitchen_project import KitchenProject

    payload = detail['payload']
    if payload['type'] == 'module':
        module = rebuild_module_from_spec(payload['spec'])
        return module, 'module'
    else:
        project = KitchenProject(name=detail.get('name', 'Проект кухни'), client=detail.get('client', ''))
        for spec in payload['modules']:
            project.add_module(rebuild_module_from_spec(spec))
        return project, 'project'


def delete_order_remote(order_id):
    """Удалить заказ на сервере. Возвращает True/False."""
    if not REQUESTS_AVAILABLE:
        return False
    url, password = _server_config()
    if not url:
        return False
    try:
        resp = requests.delete(f"{url}/orders/{order_id}", headers=_headers(password), timeout=TIMEOUT)
        return resp.status_code == 200
    except requests.RequestException as e:
        print(f"[remote_sync] Не удалось удалить заказ на сервере: {e}")
        return False


def check_connection():
    """Проверить, отвечает ли сервер (для кнопки 'Проверить соединение' в настройках)"""
    if not REQUESTS_AVAILABLE:
        return False, "Библиотека requests не установлена (выполните: pip install requests)"
    url, password = _server_config()
    if not url:
        return False, "Сервер не настроен"
    try:
        resp = requests.get(f"{url}/health", timeout=TIMEOUT)
        if resp.status_code == 200:
            return True, "Соединение установлено"
        return False, f"Сервер ответил с кодом {resp.status_code}"
    except requests.RequestException as e:
        return False, f"Нет соединения: {e}"