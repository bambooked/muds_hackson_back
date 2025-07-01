"""
研究データ基盤システム
ローカルデータベースベースの研究データ管理・検索・相談システム
"""

__version__ = "1.0.0"
__author__ = "Research Data Platform Team"
__description__ = "ローカルデータベースベースの研究データ管理・検索・相談システム"

# パッケージレベルでの主要クラスのインポート
from .config import Config, get_config
from .database_handler import DatabaseHandler
from .data_management.data_manager import DataManager
from .search.search_engine import SearchEngine
from .metadata_extractor import MetadataExtractor
from .processing.file_processor import FileProcessor

# 相談機能
from .consultation.advisor import ResearchAdvisor
from .consultation.llm_advisor import LLMAdvisor
from .consultation.recommender import DataRecommender

__all__ = [
    'Config',
    'get_config',
    'DatabaseHandler',
    'DataManager',
    'SearchEngine',
    'MetadataExtractor',
    'FileProcessor',
    'ResearchAdvisor',
    'LLMAdvisor',
    'DataRecommender'
]