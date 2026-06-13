"""
Конфигурация pytest: добавляет корень проекта в sys.path,
чтобы тесты могли импортировать пакеты core/, db/, web/ напрямую.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
