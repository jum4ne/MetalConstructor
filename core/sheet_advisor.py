"""
Советчик по выбору листа: прогоняет раскрой по всем доступным типоразмерам
листов и показывает варианты - "меньше отходов", "меньше денег",
плюс режим подбора ИДЕАЛЬНОГО (минимально возможного) размера листа под заказ.
"""
from config import Config
from core.nesting import pack_parts
from core.part_splitter import split_part_if_needed


IDEAL_KEY = "__ideal__"


def find_ideal_sheet(parts, margin, gap, max_dim=12000, step_mm=10, round_step=None):
    """
    Найти идеальный (минимально возможный) размер листа под этот набор деталей.

    Задача: все детали должны влезть в один лист, а его площадь должна быть
    минимальной - тогда отходов "по краям" почти не будет.

    Стратегия: перебираем набор кандидатов ширины (размеры деталей и суммы пар),
    для каждой ширины бинарным поиском находим минимальную высоту, при которой
    всё влезает в один лист. Возвращаем размер с минимальной итоговой площадью.

    Args:
        max_dim: максимальный размер стороны листа (мм). По умолчанию 12000 -
                 достаточно даже для очень больших проектов кухни (десятки
                 деталей). Для одного модуля обычно хватает 4000-5000.
        round_step: если задан (например 100), результат округляется ВВЕРХ
                    до кратного round_step - чтобы получились "красивые" размеры
                    типа 1900×3900 вместо 1822×3835 (реальные листы часто
                    поставляются с шагом 50 или 100 мм). Округление всегда
                    вверх - иначе детали перестанут влезать.

    Returns:
        (width, height) в мм или None если не удалось подобрать.
    """
    if not parts:
        return None

    # Кандидаты ширины - размеры деталей и суммы пар (сумма двух деталей рядом)
    dims = set()
    for p in parts:
        dims.add(p.width)
        dims.add(p.height)
    dims = sorted(dims)

    all_dims = set(dims)
    for i, d1 in enumerate(dims):
        for d2 in dims[i:]:
            s = d1 + d2 + gap
            if s <= max_dim:
                all_dims.add(s)

    min_side_needed = max(min(p.width, p.height) for p in parts) + 2 * margin
    max_reasonable = min(max_dim, int(sum(max(p.width, p.height) * p.quantity for p in parts) + 2 * margin))

    all_dims = sorted(int(d) + 2 * margin for d in all_dims
                      if min_side_needed <= d + 2 * margin <= max_reasonable)

    best = None
    best_area = float('inf')

    for real_width in all_dims:
        # Экспоненциальный рост, пока не найдём высоту, при которой всё влезает
        found_height = None
        h = min_side_needed
        while h <= max_reasonable:
            try:
                sheets = pack_parts(parts, real_width, h, margin, gap)
                if len(sheets) == 1:
                    found_height = h
                    break
            except ValueError:
                pass
            h = int(h * 1.5) + step_mm

        if found_height is None:
            continue

        # Уточняем бинарным поиском
        lo, hi = min_side_needed, found_height
        while hi - lo > step_mm:
            mid = (lo + hi) // 2
            try:
                sheets = pack_parts(parts, real_width, mid, margin, gap)
                if len(sheets) == 1:
                    hi = mid
                    found_height = mid
                else:
                    lo = mid + step_mm
            except ValueError:
                lo = mid + step_mm

        area = real_width * found_height
        if area < best_area:
            best_area = area
            best = (real_width, found_height)

    if best is None:
        return None

    if round_step and round_step > 1:
        # Округляем ВВЕРХ до кратности round_step (чтобы гарантированно влезли
        # все детали - иначе округление вниз может выкинуть деталь за границу)
        w, h = best
        rw = ((w + round_step - 1) // round_step) * round_step
        rh = ((h + round_step - 1) // round_step) * round_step
        # Проверка: детали действительно влезают после округления (обязана, но
        # на всякий случай перестраховываемся - вдруг round_step очень большой)
        try:
            sheets = pack_parts(parts, rw, rh, margin, gap)
            if len(sheets) == 1:
                return (rw, rh)
        except ValueError:
            pass
        return best  # если округление всё сломало (маловероятно) - вернуть исходный

    return best


def find_ideal_sheet_for_n(parts, margin, gap, target_sheets, round_step=None,
                             max_dim=12000, step_mm=10):
    """
    Найти минимальный размер листа, при котором детали раскладываются
    ровно в target_sheets листов (или меньше).

    Полезно, когда единый идеальный лист получается неудобно большой
    (условно 2×4м) - можно сказать "хочу в 2 листа" и получить размер
    поменьше, например ~1.5×2м.

    Args:
        target_sheets: желаемое количество листов (2, 3, 4...)
        round_step: округление вверх до кратности (например 100 мм)

    Returns:
        (width, height) или None
    """
    if not parts or target_sheets < 1:
        return None

    dims = set()
    for p in parts:
        dims.add(p.width)
        dims.add(p.height)
    dims = sorted(dims)

    all_dims = set(dims)
    for i, d1 in enumerate(dims):
        for d2 in dims[i:]:
            s = d1 + d2 + gap
            if s <= max_dim:
                all_dims.add(s)

    min_side_needed = max(min(p.width, p.height) for p in parts) + 2 * margin
    max_reasonable = min(max_dim, int(sum(max(p.width, p.height) * p.quantity for p in parts) + 2 * margin))

    all_dims = sorted(int(d) + 2 * margin for d in all_dims
                      if min_side_needed <= d + 2 * margin <= max_reasonable)

    best = None
    best_area = float('inf')

    for real_width in all_dims:
        # Экспоненциальный рост высоты до момента, когда всё влезает в <= N листов
        found_height = None
        h = min_side_needed
        while h <= max_reasonable:
            try:
                sheets = pack_parts(parts, real_width, h, margin, gap)
                if len(sheets) <= target_sheets:
                    found_height = h
                    break
            except ValueError:
                pass
            h = int(h * 1.5) + step_mm

        if found_height is None:
            continue

        # Уточняем бинарным поиском
        lo, hi = min_side_needed, found_height
        while hi - lo > step_mm:
            mid = (lo + hi) // 2
            try:
                sheets = pack_parts(parts, real_width, mid, margin, gap)
                if len(sheets) <= target_sheets:
                    hi = mid
                    found_height = mid
                else:
                    lo = mid + step_mm
            except ValueError:
                lo = mid + step_mm

        # Общая площадь всех листов - вот что минимизируем
        # (не одного листа, а total, потому что при target_sheets>1
        # один лист меньше, но их несколько)
        area = real_width * found_height * target_sheets
        if area < best_area:
            best_area = area
            best = (real_width, found_height)

    if best is None:
        return None

    if round_step and round_step > 1:
        w, h = best
        rw = ((w + round_step - 1) // round_step) * round_step
        rh = ((h + round_step - 1) // round_step) * round_step
        try:
            sheets = pack_parts(parts, rw, rh, margin, gap)
            if len(sheets) <= target_sheets:
                return (rw, rh)
        except ValueError:
            pass
        return best

    return best


def _analyze_one_sheet(parts, margin, gap, work_price_per_part,
                       sheet_w, sheet_h, name, key, price_per_m2):
    """Раскрой на конкретном размере листа + подсчёт стоимости"""
    variant = {
        'key': key,
        'name': name,
        'width': sheet_w,
        'height': sheet_h,
        'price_per_m2': price_per_m2,
        'sheets_count': None,
        'usage_percent': None,
        'waste_percent': None,
        'metal_cost': None,
        'work_cost': None,
        'total_cost': None,
        'error': None,
    }

    try:
        expanded = []
        for p in parts:
            expanded.extend(split_part_if_needed(p, sheet_w, sheet_h, margin))
        sheets = pack_parts(expanded, sheet_w, sheet_h, margin, gap)

        sheet_area_m2 = sheet_w * sheet_h / 1_000_000
        total_sheet_area = len(sheets) * sheet_area_m2
        parts_area_m2 = sum(pd['width'] * pd['height']
                            for s in sheets for pd in s['parts']) / 1_000_000
        parts_count = sum(len(s['parts']) for s in sheets)
        usage = (parts_area_m2 / total_sheet_area * 100) if total_sheet_area else 0

        metal_cost = total_sheet_area * price_per_m2
        work_cost = parts_count * work_price_per_part
        total = metal_cost + work_cost

        variant.update({
            'sheets_count': len(sheets),
            'usage_percent': round(usage, 2),
            'waste_percent': round(100 - usage, 2),
            'metal_cost': round(metal_cost, 2),
            'work_cost': round(work_cost, 2),
            'total_cost': round(total, 2),
        })
    except ValueError as e:
        variant['error'] = str(e)

    return variant


def analyze_sheets(parts, margin, gap, work_price_per_part,
                    sheet_keys=None, custom_sheets=None,
                    include_ideal=False, ideal_round_step=None,
                    force_sheet_count=None):
    """
    Проанализировать раскрой на выбранных листах.

    Args:
        parts: список деталей
        margin, gap: отступы и допуски
        work_price_per_part: цена работы за деталь
        sheet_keys: список ключей стандартных листов из Config.SHEET_SIZES.
                    Если None - берём все.
        custom_sheets: список dict {'width', 'height', 'name', 'price_per_m2'} -
                       листы, которые пользователь вписал вручную.
        include_ideal: если True, попробовать подобрать идеальный размер листа
                       под этот заказ и включить его в результаты.
        ideal_round_step: шаг округления вверх для идеального листа (например 100).
                          None = не округлять.
        force_sheet_count: если задано (2, 3, ...) - подобрать идеальный лист
                           при УСЛОВИИ что заказ будет разложен ровно в N листов.
                           Полезно, когда единый лист слишком большой для завода.
    """
    variants = []

    # 1. Стандартные листы из справочника
    if sheet_keys is None:
        sheet_keys = list(Config.SHEET_SIZES.keys())

    for key in sheet_keys:
        if key not in Config.SHEET_SIZES:
            continue
        info = Config.SHEET_SIZES[key]
        variants.append(_analyze_one_sheet(
            parts, margin, gap, work_price_per_part,
            info['width'], info['height'], info['name'], key,
            info.get('price_per_m2', Config.METAL_PRICE_PER_M2)
        ))

    # 2. Пользовательские листы
    if custom_sheets:
        for i, cs in enumerate(custom_sheets):
            name = cs.get('name') or f"Свой лист {cs['width']}×{cs['height']}"
            variants.append(_analyze_one_sheet(
                parts, margin, gap, work_price_per_part,
                cs['width'], cs['height'], name, f"custom_{i}",
                cs.get('price_per_m2', Config.METAL_PRICE_PER_M2)
            ))

    # 3. Идеальный лист
    if include_ideal:
        if force_sheet_count and force_sheet_count > 1:
            # Идеальный лист при условии, что заказ раскладывается ровно в N листов
            ideal = find_ideal_sheet_for_n(parts, margin, gap, force_sheet_count,
                                             round_step=ideal_round_step)
            if ideal is not None:
                iw, ih = ideal
                label = f"🎯 Идеальный {iw}×{ih} (×{force_sheet_count} листов)"
                variants.append(_analyze_one_sheet(
                    parts, margin, gap, work_price_per_part,
                    iw, ih, label, IDEAL_KEY,
                    Config.METAL_PRICE_PER_M2
                ))
            else:
                # Сообщаем пользователю, что идеальный лист не подобрался -
                # обычно это значит, что деталей слишком много для одного листа
                # разумного размера. Пусть попробует "разложить в N листов".
                variants.append({
                    'key': IDEAL_KEY,
                    'name': f"🎯 Идеальный лист ×{force_sheet_count} (не подобран)",
                    'width': 0, 'height': 0, 'price_per_m2': 0,
                    'sheets_count': None, 'usage_percent': None, 'waste_percent': None,
                    'metal_cost': None, 'work_cost': None, 'total_cost': None,
                    'error': f'Не удалось подобрать в {force_sheet_count} листов. Попробуйте больше листов.',
                })
        else:
            ideal = find_ideal_sheet(parts, margin, gap, round_step=ideal_round_step)
            if ideal is not None:
                iw, ih = ideal
                variants.append(_analyze_one_sheet(
                    parts, margin, gap, work_price_per_part,
                    iw, ih, f"🎯 Идеальный {iw}×{ih}", IDEAL_KEY,
                    Config.METAL_PRICE_PER_M2
                ))
            else:
                variants.append({
                    'key': IDEAL_KEY,
                    'name': "🎯 Идеальный лист (не подобран)",
                    'width': 0, 'height': 0, 'price_per_m2': 0,
                    'sheets_count': None, 'usage_percent': None, 'waste_percent': None,
                    'metal_cost': None, 'work_cost': None, 'total_cost': None,
                    'error': ('Единый лист получается слишком большой для этого набора деталей. '
                              'Попробуйте выбрать "Разложить в 2 или 3 листа".'),
                })

    return variants


def pick_best(variants):
    """Выбрать двух победителей: минимум отходов, минимум денег"""
    valid = [v for v in variants if v.get('error') is None]

    if not valid:
        return {'least_waste': None, 'least_cost': None, 'same': False}

    least_waste = max(valid, key=lambda v: v['usage_percent'])
    least_cost = min(valid, key=lambda v: v['total_cost'])

    return {
        'least_waste': least_waste,
        'least_cost': least_cost,
        'same': least_waste['key'] == least_cost['key'],
    }


# Обратная совместимость со старым интерфейсом
def analyze_all_sheets(parts, margin, gap, work_price_per_part):
    return analyze_sheets(parts, margin, gap, work_price_per_part)