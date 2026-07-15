"""
Дерево сборки (BOM) - комплекс -> секции -> подсборки -> детали.

--------------------------------------------------------------------------
ЗАЧЕМ ЭТОТ МОДУЛЬ ВООБЩЕ ПОЯВИЛСЯ
--------------------------------------------------------------------------
Иерархии сборки в проекте НЕ БЫЛО. KitchenProject.parts - это property,
которое СХЛОПЫВАЕТ детали всех модулей в один плоский список, приклеивая
к имени префикс "[Название модуля]":

    [Тумба открытая] Боковина
    [Тумба открытая] Крыша
    [Шкаф под мойку] Боковина      <- граница между узлами существует
    [Шкаф под мойку] Дверь            только внутри строки-названия

Экспортер чертежей итерировал ровно этот плоский список - отсюда и
взялась главная беда документа: чертежи деталей разных сборочных единиц
идут подряд, без разделения по модулям, и понять "к какому узлу относится
этот лист" можно только вчитавшись в префикс в штампе.

AssemblyNode восстанавливает потерянную иерархию ЯВНО: узел знает своих
детей (подсборки) и свои собственные листовые детали. Обход - строго
depth-first: узел не считается закрытым, пока не выпущены все его
подсборки и все его детали. Никакого перемешивания между узлами.

--------------------------------------------------------------------------
ОБОЗНАЧЕНИЯ ПО ГОСТ
--------------------------------------------------------------------------
Раньше обозначение в штампе было просто "К 07" - порядковый номер листа.
Это неверно: обозначение должно кодировать МЕСТО детали в структуре
изделия, а не то, на какой странице она напечатана (переставил страницы -
поменялось обозначение детали, чего быть не должно).

Здесь обозначение строится по структуре дерева:

    К 01.00.00.000   комплекс (изделие целиком)
    К 01.02.00.000   секция №2 в составе комплекса
    К 01.02.01.000   подсборка №1 внутри секции №2
    К 01.02.01.005   деталь №5 внутри этой подсборки
    К 01.02.00.005   деталь №5, входящая прямо в секцию №2

Это соответствует формату из референсного комплекта (К 01.00.00.000).
"""
from core.part_semantics import annotate


class AssemblyNode:
    """
    Узел дерева сборки: сборочная единица (комплекс / секция / подсборка).

    children - вложенные сборочные единицы (обходятся ДО деталей этого узла,
               рекурсивно, каждая полностью закрывается перед следующей)
    parts    - листовые детали, входящие НЕПОСРЕДСТВЕННО в этот узел
    tubes    - трубы каркаса, входящие непосредственно в этот узел
    source   - исходный объект (Module / KitchenProject), нужен страницам,
               которые рисуют 3D-виды: им нужны height/width/depth
    """

    def __init__(self, name, source=None, pos_num=0, parent=None, node_type="assembly"):
        self.name = name
        self.source = source
        self.pos_num = pos_num          # номер позиции этого узла у родителя
        self.parent = parent
        self.node_type = node_type      # 'complex' | 'module' | 'subassembly'
        self.children = []
        self.parts = []
        self.tubes = []

    # ---------- построение ----------

    def add_child(self, node):
        node.parent = self
        node.pos_num = len(self.children) + 1
        self.children.append(node)
        return node

    # ---------- обозначения ГОСТ ----------

    @property
    def depth(self):
        """Глубина узла: 0 = комплекс, 1 = секция, 2 = подсборка"""
        return 0 if self.parent is None else self.parent.depth + 1

    def _chain(self):
        """Цепочка номеров позиций от комплекса до этого узла"""
        if self.parent is None:
            return []
        return self.parent._chain() + [self.pos_num]

    def code(self, prefix="К"):
        """
        Обозначение самой сборочной единицы.
        Комплекс -> 'К 01.00.00.000', секция №2 -> 'К 01.02.00.000',
        подсборка №1 в секции №2 -> 'К 01.02.01.000'.
        """
        chain = self._chain()               # [] | [2] | [2,1]
        section = chain[0] if len(chain) >= 1 else 0
        sub = chain[1] if len(chain) >= 2 else 0
        return f"{prefix} 01.{section:02d}.{sub:02d}.000"

    def part_code(self, index, prefix="К"):
        """
        Обозначение детали №index (1-based), входящей в ЭТОТ узел.
        Деталь №5 секции №2 -> 'К 01.02.00.005'.
        """
        chain = self._chain()
        section = chain[0] if len(chain) >= 1 else 0
        sub = chain[1] if len(chain) >= 2 else 0
        return f"{prefix} 01.{section:02d}.{sub:02d}.{index:03d}"

    # ---------- содержимое ----------

    def grouped_parts(self):
        """
        Детали этого узла, свёрнутые по (имя, размеры, толщина): 4 одинаковые
        полки -> одна строка с Кол-во=4, один чертёж, а не четыре.

        Порядок групп = порядок первого появления детали в узле (стабильный).
        """
        groups = {}
        order = []
        for p in self.parts:
            key = (p.name, p.width, p.height, p.thickness)
            if key not in groups:
                groups[key] = {"part": p, "qty": 0}
                order.append(key)
            groups[key]["qty"] += p.quantity
        return [groups[k] for k in order]

    def grouped_tubes(self):
        """Трубы этого узла, свёрнутые по (профиль, длина)"""
        groups = {}
        order = []
        for t in self.tubes:
            key = (t.profile_w, t.profile_h, t.wall, t.length)
            if key not in groups:
                groups[key] = {"tube": t, "qty": 0}
                order.append(key)
            groups[key]["qty"] += t.quantity
        return [groups[k] for k in order]

    def walk(self):
        """
        Обход дерева depth-first: сначала сам узел, затем ПОЛНОСТЬЮ каждая
        подсборка (рекурсивно), и только потом - следующий узел того же
        уровня. Именно этот порядок гарантирует, что детали разных узлов
        никогда не перемежаются в документе.
        """
        yield self
        for child in self.children:
            yield from child.walk()

    def is_cabinet_like(self):
        """
        Можно ли для этого узла строить изометрию/разнесённый вид.

        Признак - наличие боковины: у столешницы, например, поле height
        хранит толщину металла (не настоящую высоту), поэтому height>0
        ненадёжен, а "есть Боковина" - надёжен. Логика сохранена из
        прежнего кода (_is_cabinet_like в technical_drawing).
        """
        if self.source is None:
            return False
        if not hasattr(self.source, "height"):
            return False
        return any(p.name.startswith("Боковина") for p in self.parts)

    def __repr__(self):
        return f"<AssemblyNode {self.name!r} parts={len(self.parts)} children={len(self.children)}>"


# --------------------------------------------------------------------------
# Построение дерева из существующих объектов (Module / KitchenProject)
# --------------------------------------------------------------------------

def _strip_module_prefix(name):
    """'[Тумба] Боковина' -> 'Боковина' (префикс нужен был только чтобы
    отличать детали в плоском списке; в дереве узел уже известен)"""
    if name.startswith("["):
        close = name.find("]")
        if close != -1:
            return name[close + 1:].strip()
    return name


def _module_node(module, node_type="module"):
    """Собрать узел из Module: его детали + трубы + (если есть) подсборки."""
    node = AssemblyNode(module.name, source=module, node_type=node_type)

    for p in module.parts:
        p.name = _strip_module_prefix(p.name)
        annotate(p)                       # description + is_hidden_in_assembly
        node.parts.append(p)

    node.tubes = list(getattr(module, "tubes", None) or [])

    # Подсборки: модуль МОЖЕТ объявить вложенные сборочные единицы через
    # поле .subassemblies (например "Ящик под хранение" внутри "Секции с
    # ящиками"). Сейчас ни один билдер их не создаёт, но рекурсия по дереву
    # уже готова принять их без единой правки в экспортере - просто добавь
    # module.subassemblies = [<Module>, ...] в билдере.
    for sub in getattr(module, "subassemblies", None) or []:
        node.add_child(_module_node(sub, node_type="subassembly"))

    return node


def build_assembly_tree(source):
    """
    Построить дерево сборки из KitchenProject (комплекс) или Module
    (одиночный модуль - тогда он и есть корень).

    Returns: AssemblyNode (корень)
    """
    if hasattr(source, "modules"):        # KitchenProject
        root = AssemblyNode(source.name, source=source, node_type="complex")
        for m in source.modules:
            root.add_child(_module_node(m))
        return root

    root = _module_node(source, node_type="module")
    root.node_type = "module"
    return root