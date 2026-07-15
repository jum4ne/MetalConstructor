"""
Общие настройки pytest для проекта Metal Constructor.

conftest.py - специальный файл, который pytest автоматически подхватывает
перед запуском тестов. Здесь мы добавляем корень проекта в sys.path,
чтобы можно было импортировать наши модули как `from core.calculator import ...`.
"""
import sys
import os

# Добавляем корень проекта в путь импортов
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)