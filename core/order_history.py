"""
История заказов — лог всех экспортированных модулей/проектов.
Хранится в одном JSON-файле cad/reports/order_history.json
"""
import json
import os
import time
from config import Config

HISTORY_FILE = os.path.join(Config.REPORTS_DIR, 'order_history.json')

STATUSES = ["В расчёте", "В резке", "Готово", "Отгружено"]


def _load_all():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save_all(records):
    Config.init_dirs()
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(records, f, indent=2, ensure_ascii=False)


def add_record(name, client, module_type, report, dxf_path, status="В расчёте"):
    """Добавить запись в историю после успешного экспорта DXF"""
    records = _load_all()
    record = {
        'id': int(time.time() * 1000),
        'date': time.strftime('%Y-%m-%d %H:%M:%S'),
        'name': name,
        'client': client or '-',
        'module_type': module_type,
        'sheets_count': report.get('sheets_count') if report else None,
        'parts_count': report.get('parts_count') if report else None,
        'total_cost_rub': report.get('total_cost_rub') if report else None,
        'dxf_path': dxf_path,
        'status': status,
    }
    records.append(record)
    _save_all(records)
    return record


def get_history():
    """Вернуть всю историю, последние заказы сначала"""
    return list(reversed(_load_all()))


def update_status(record_id, new_status):
    records = _load_all()
    updated = False
    for r in records:
        if r['id'] == record_id:
            r['status'] = new_status
            updated = True
    if updated:
        _save_all(records)
    return updated


def delete_record(record_id):
    records = _load_all()
    new_records = [r for r in records if r['id'] != record_id]
    _save_all(new_records)
    return len(new_records) != len(records)