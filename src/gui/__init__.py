"""
GUI package for Hebrew Subtitle Service.
Provides modern, intuitive user interface components.
"""

from .main_window import MainWindow
from .components import FileSelector, ProgressPanel, ResultsPanel, ConfigurationPanel

__all__ = ['MainWindow', 'FileSelector', 'ProgressPanel', 'ResultsPanel', 'ConfigurationPanel'] 