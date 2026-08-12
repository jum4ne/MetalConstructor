from dataclasses import dataclass, field
from typing import List


@dataclass
class BendLine:
    """
    Линия гиба.

    ВАЖНО, ЧТО ТАКОЕ offset (тут была ошибка, из-за которой цех мог
    загнуть не там):

      offset  - ПОЗИЦИЯ ЛИНИИ НА РАЗВЁРТКЕ, отступ от кромки заготовки.
                Именно по ней гибочный станок ставит нож. Для борта 20мм
                при S=1 это 17.8 (20 - вычет 2.2).
      nominal - ВЫСОТА ГОТОВОГО БОРТА после гибки (те самые 20мм).

      offset != nominal, потому что металл при гибке вытягивается.

    Раньше в offset местами клали номинал (20), местами позицию (17.8).
    Цех, прочитав "отступ 20", отмерил бы 20 от кромки и загнул бы не там:
    борт вышел бы 22.2 вместо 20. Теперь offset - ВСЕГДА позиция линии,
    а nominal печатается рядом, чтобы было видно оба числа.
    """
    """Линия гиба (отбортовка края детали)"""
    edge: str              # 'top' | 'bottom' | 'left' | 'right'
    offset: float          # ПОЗИЦИЯ ЛИНИИ ГИБА на развёртке: мм от кромки
                           # заготовки. По ней станок ставит нож.
    angle: float = 90.0    # угол гиба, градусы
    direction: str = 'up'  # 'up' | 'down' - куда отгибается борт
    nominal: float = 0     # ВЫСОТА ГОТОВОГО БОРТА после гибки (0 = не задана).
                           # offset != nominal: металл при гибке вытягивается,
                           # борт 20мм при S=1 гнётся по линии на 17.8мм.
    note: str = ''


@dataclass
class Cutout:
    """Вырез в детали (под мойку, гриль, вентиляцию и т.п.)"""
    shape: str              # 'rect' | 'circle'
    x: float                # центр выреза, мм от левого нижнего угла детали
    y: float
    width: float = 0        # для rect
    height: float = 0       # для rect
    radius: float = 0       # для circle
    label: str = ''


@dataclass
class TubePart:
    """
    Отрезок профильной трубы каркаса (несущая часть конструкции).

    В реальном производстве (разобрано по референсному комплекту чертежей)
    изделие держится на сварном каркасе из профильной трубы, а листовые
    детали (Part) - это обшивка на этот каркас. В спецификации трубы идут
    отдельным разделом со своим форматом наименования: "Труба 40х20х1 L=820".
    """
    profile_w: int          # ширина профиля, мм (напр. 40)
    profile_h: int          # высота профиля, мм (напр. 20)
    wall: float             # толщина стенки, мм (напр. 1.0 или 1.5)
    length: int             # длина отрезка, мм
    quantity: int = 1
    note: str = ''

    @property
    def profile_label(self):
        """Формат профиля как в референсе: '40х20х1' или '20х20х1,5'"""
        # толщина стенки: целые без дробной части, дробные через запятую (ГОСТ-стиль)
        if self.wall == int(self.wall):
            wall_str = str(int(self.wall))
        else:
            wall_str = str(self.wall).replace('.', ',')
        return f"{self.profile_w}х{self.profile_h}х{wall_str}"

    @property
    def name(self):
        """Наименование как в спецификации: 'Труба 40х20х1 L=820'"""
        return f"Труба {self.profile_label} L={self.length}"

    @property
    def total_length_mm(self):
        """Суммарная длина всех отрезков этого типа (для расчёта метража)"""
        return self.length * self.quantity

    def __str__(self):
        return f"{self.name}  x{self.quantity}"


@dataclass
class Part:
    """Описание одной детали."""
    name: str
    width: int
    height: int
    quantity: int = 1
    thickness: float = 1.0
    bend_lines: List[BendLine] = field(default_factory=list)
    cutouts: List[Cutout] = field(default_factory=list)
    # Размер углового выреза (мм) - если > 0, деталь на чертеже рисуется не
    # простым прямоугольником, а с вырезанными квадратами в углах, где
    # встречаются два загнутых края (иначе металл рвётся при гибке).
    # 0 = обычный прямоугольник без вырезов в углах.
    corner_relief: float = 0

    # --- Поля для конструкторской документации (см. docs-требования) ---

    # Текстовое пояснение к детали: 1-2 предложения о том, для чего деталь
    # нужна и как она встаёт в сборку. Выводится на чертеже детали под
    # контуром. Заполняется билдером (типовой текст по роли детали) и может
    # быть отредактировано конструктором в UI перед экспортом.
    description: str = ''

    # Видна ли деталь пользователю после окончательной сборки комплекса.
    # Если True - на чертёж автоматически выводится обязательная надпись
    # "Деталь скрыта в собранном изделии - не видна при эксплуатации".
    #
    # None = "не задано" -> annotate() проставит по роли детали.
    # True/False = задано явно (билдером или конструктором в UI) -> annotate()
    # НЕ трогает. Именно поэтому здесь None, а не False: с False нельзя было
    # отличить "конструктор явно сказал: деталь видна" от "никто не заполнял",
    # и явное False молча затиралось правилом по роли (открытая полка-рейлинг
    # уезжала в "скрытые").
    is_hidden_in_assembly: bool = None

    # Явный контур реза детали: список вершин [(x, y) | (x, y, bulge), ...]
    # относительно левого нижнего угла заготовки. bulge (выпуклость) задаёт
    # дугу к следующей вершине (tan(угол/4)); 0 или отсутствует = прямой отрезок.
    # Нужен для деталей со скруглёнными углами и надрезами-релизами, которые
    # не описываются простым «прямоугольник + угловой вырез». None = строить
    # контур по-старому (прямоугольник, при corner_relief — с угловыми вырезами).
    outline: list = None

    # Дополнительные замкнутые/открытые полилинии реза внутри детали (пазы,
    # прорези сложной формы, которых нет среди cutouts rect/circle). Каждый
    # элемент: (points, closed), где points = [(x, y[, bulge]), ...].
    extra_cuts: list = field(default_factory=list)

    @property
    def area(self):
        return (self.width * self.height) / 1_000_000

    @property
    def flat_width(self):
        """
        Ширина РАЗВЁРТКИ (плоской заготовки под лазер).

        В этой модели данных width/height детали УЖЕ хранят размер развёртки:
        add_flange() увеличивает width/height на припуск под загиб и добавляет
        BendLine. То есть width - это размер заготовки до гибки, а габарит
        готовой детали получается вычитанием загибов (см. formed_width).
        """
        return self.width

    @property
    def flat_height(self):
        """Высота развёртки (плоской заготовки) - см. flat_width."""
        return self.height

    def _fold_total(self, axis):
        """Суммарный припуск на загиб по оси ('x' = left/right, 'y' = top/bottom)"""
        edges = ('left', 'right') if axis == 'x' else ('top', 'bottom')
        return sum(b.offset for b in self.bend_lines
                   if b.edge in edges and b.direction != 'seam')

    @property
    def formed_width(self):
        """Габаритная ширина ГОТОВОЙ детали (после гибки бортов)"""
        return self.width - self._fold_total('x')

    @property
    def formed_height(self):
        """Габаритная высота ГОТОВОЙ детали (после гибки бортов)"""
        return self.height - self._fold_total('y')

    @property
    def is_bent(self):
        """Есть ли у детали настоящие линии гиба (швы под сварку не считаются)"""
        return any(b.direction != 'seam' for b in self.bend_lines)

    def __str__(self):
        return f"{self.name}: {self.width}×{self.height} мм  x{self.quantity}"