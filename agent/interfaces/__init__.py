"""
インターフェースモジュール
"""
from .cli_interface import CLIInterface
from .web_interface import WebInterface

__all__ = [
    'CLIInterface',
    'WebInterface'
]