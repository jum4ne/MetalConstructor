# -*- coding: utf-8 -*-
"""
Раскладка выгрузок по ПАПКАМ ЗАКАЗОВ.

==========================================================================
ЗАЧЕМ
==========================================================================
Раньше все выгрузки сыпались в две общие папки:

    cad/dxf/      Секция с выдвижными ящиками_20260716_042320.dxf
    cad/reports/  chertezhi_20260716_043202.pdf
                  report_20260716_042320.json
                  spec_20260716_043210.xlsx

Проблемы, из-за которых с этим невозможно работать:
  - файлы ОДНОГО заказа лежат в РАЗНЫХ папках;
  - имена различаются только секундами - чей это заказ, не понять;
  - имени заказчика в файлах нет вообще.

Теперь один заказ = одна папка со всем комплектом:

    cad/orders/2026-07-16_Иванов_Секция-с-ящиками/
        Раскрой.dxf
        Чертежи.pdf
        Спецификация.xlsx
        Карта гибки.pdf
        Отчёт раскроя.json
        Развёртки/          (по одному DXF на деталь)

==========================================================================
ПОЧЕМУ ИМЯ ПАПКИ БЕЗ ВРЕМЕНИ (только дата)
==========================================================================
Экспорт DXF, PDF и Excel - это РАЗНЫЕ нажатия кнопок в разные моменты.
Если бы в имя папки входило время, каждое нажатие создавало бы СВОЮ папку,
и комплект снова оказался бы раскидан. Поэтому папка определяется самим
ЗАКАЗОМ (дата + заказчик + изделие), а не моментом нажатия: все выгрузки
одного заказа за день попадают в одну папку, повторный экспорт просто
перезаписывает файл свежей версией - что и нужно.
"""
import os
import re
import time

from config import Config

# Символы, запрещённые в именах файлов Windows, + управляющие
_BAD_CHARS = re.compile(r'[\\/:*?"<>|\r\n\t]+')


def slug(text, maxlen=45):
    """Привести кусок имени к безопасному для файловой системы виду."""
    s = _BAD_CHARS.sub('', (text or '').strip())
    s = re.sub(r'\s+', '-', s)
    s = s.strip('-. ')
    return s[:maxlen].strip('-. ')


def order_folder_name(name, client='', when=None):
    """Имя папки заказа: 2026-07-16_Иванов_Секция-с-ящиками"""
    date = time.strftime('%Y-%m-%d', when or time.localtime())
    chunks = [date]
    c = slug(client, 30)
    if c and c != '-':
        chunks.append(c)
    n = slug(name, 45)
    if n:
        chunks.append(n)
    return '_'.join(chunks)


def order_dir(name, client='', when=None, create=True):
    """Полный путь к папке заказа (создаёт её при необходимости)."""
    Config.init_dirs()
    path = os.path.join(Config.ORDERS_DIR, order_folder_name(name, client, when))
    if create:
        os.makedirs(path, exist_ok=True)
    return path


def order_dir_for(obj, create=True):
    """
    Папка заказа для модуля или проекта кухни.

    У KitchenProject есть поле client; у обычного Module его может не быть -
    тогда папка называется просто «дата_изделие».
    """
    name = (getattr(obj, 'name', '') or getattr(obj, 'module_type', '')
            or 'Изделие')
    client = getattr(obj, 'client', '') or ''
    return order_dir(name, client, create=create)


def order_file(obj, filename, create=True):
    """Путь к файлу внутри папки заказа: order_file(module, 'Раскрой.dxf')"""
    return os.path.join(order_dir_for(obj, create=create), filename)
