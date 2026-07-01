from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QFormLayout,
    QSpinBox,
    QDoubleSpinBox,
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Metal Constructor")
        self.resize(900, 600)

        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)

        title = QLabel("Metal Constructor")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            font-size:26px;
            font-weight:bold;
            padding:15px;
        """)

        layout.addWidget(title)

        form = QFormLayout()

        self.height = QSpinBox()
        self.height.setMaximum(5000)
        self.height.setValue(1800)

        self.width = QSpinBox()
        self.width.setMaximum(5000)
        self.width.setValue(900)

        self.depth = QSpinBox()
        self.depth.setMaximum(5000)
        self.depth.setValue(500)

        self.thickness = QDoubleSpinBox()
        self.thickness.setValue(1.0)
        self.thickness.setSingleStep(0.1)

        self.shelves = QSpinBox()
        self.shelves.setValue(4)

        form.addRow("Высота (мм)", self.height)
        form.addRow("Ширина (мм)", self.width)
        form.addRow("Глубина (мм)", self.depth)
        form.addRow("Толщина металла (мм)", self.thickness)
        form.addRow("Количество полок", self.shelves)

        layout.addLayout(form)

        button = QPushButton("Рассчитать")
        button.setMinimumHeight(45)

        layout.addWidget(button)