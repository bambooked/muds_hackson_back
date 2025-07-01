"""
統合データ管理クラス
分割された機能を統合して従来のインターフェースを提供
"""
from typing import Dict, Any, List, Optional

from ..database_handler import DatabaseHandler
from ..metadata_extractor import MetadataExtractor
from ..processing.file_processor import FileProcessor
from .data_operations import DataOperations
from .batch_operations import BatchOperations
from .export_operations import ExportOperations
from .dataset_manager import DatasetManager


class DataManager:
    """研究データを管理するメインクラス（リファクタリング版）"""
    
    def __init__(self, db_handler: Optional[DatabaseHandler] = None):
        """
        データマネージャの初期化
        
        Args:
            db_handler: データベースハンドラ（Noneの場合は新規作成）
        """
        self.db_handler = db_handler or DatabaseHandler()
        self.metadata_extractor = MetadataExtractor()
        self.file_processor = FileProcessor()
        
        # 分割された機能クラスのインスタンス化
        self.data_ops = DataOperations(
            self.db_handler, 
            self.metadata_extractor, 
            self.file_processor
        )
        self.batch_ops = BatchOperations(
            self.db_handler,
            self.metadata_extractor,
            self.file_processor
        )
        self.export_ops = ExportOperations(self.db_handler)
        self.dataset_manager = DatasetManager(self.db_handler)
    
    # === 基本データ操作（DataOperationsへの委譲） ===
    
    def register_data(self, file_path: str, 
                     title: Optional[str] = None,
                     summary: Optional[str] = None,
                     research_field: Optional[str] = None) -> Dict[str, Any]:
        """
        新しい研究データを登録
        
        Args:
            file_path: ファイルパス
            title: タイトル（省略時は自動抽出）
            summary: 概要（省略時は自動生成）
            research_field: 研究分野
        
        Returns:
            登録結果の辞書
        """
        return self.data_ops.register_single_data(file_path, title, summary, research_field)
    
    def update_data(self, data_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        既存のデータを更新
        
        Args:
            data_id: データID
            updates: 更新するフィールド
        
        Returns:
            更新結果
        """
        return self.data_ops.update_data(data_id, updates)
    
    def delete_data(self, data_id: str, delete_file: bool = False) -> Dict[str, Any]:
        """
        データを削除
        
        Args:
            data_id: データID
            delete_file: 実ファイルも削除するか
        
        Returns:
            削除結果
        """
        return self.data_ops.delete_data(data_id, delete_file)
    
    def get_data_info(self, data_id: str) -> Optional[Dict[str, Any]]:
        """
        データの詳細情報を取得
        
        Args:
            data_id: データID
        
        Returns:
            データ情報またはNone
        """
        return self.data_ops.get_data_info(data_id)
    
    # === バッチ操作（BatchOperationsへの委譲） ===
    
    def register_directory(self, directory_path: str, 
                          recursive: bool = True) -> Dict[str, Any]:
        """
        ディレクトリ内の全ファイルを一括登録
        
        Args:
            directory_path: ディレクトリパス
            recursive: サブディレクトリも処理するか
        
        Returns:
            登録結果のサマリー
        """
        return self.batch_ops.register_directory(directory_path, recursive)
    
    def process_file_list(self, file_paths: List[str]) -> Dict[str, Any]:
        """
        ファイルリストを一括処理
        
        Args:
            file_paths: ファイルパスのリスト
        
        Returns:
            処理結果のサマリー
        """
        return self.batch_ops.process_file_list(file_paths)
    
    def update_multiple_data(self, data_updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        複数のデータを一括更新
        
        Args:
            data_updates: 更新データのリスト
        
        Returns:
            更新結果のサマリー
        """
        return self.batch_ops.update_multiple_data(data_updates)
    
    # === エクスポート操作（ExportOperationsへの委譲） ===
    
    def export_data(self, data_ids: Optional[List[str]] = None, 
                   format: str = 'json') -> Dict[str, Any]:
        """
        データをエクスポート
        
        Args:
            data_ids: エクスポートするデータID（Noneの場合は全データ）
            format: エクスポート形式（json, csv）
        
        Returns:
            エクスポート結果
        """
        return self.export_ops.export_data(data_ids, format)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        システム統計を取得
        
        Returns:
            統計情報
        """
        return self.export_ops.get_statistics()
    
    def backup_database(self) -> Dict[str, Any]:
        """
        データベースのバックアップを作成
        
        Returns:
            バックアップ結果
        """
        return self.export_ops.backup_database()
    
    def export_metadata_summary(self) -> Dict[str, Any]:
        """
        メタデータサマリーをエクスポート
        
        Returns:
            サマリーエクスポート結果
        """
        return self.export_ops.export_metadata_summary()
    
    def export_research_field_report(self, research_field: str) -> Dict[str, Any]:
        """
        特定の研究分野のレポートをエクスポート
        
        Args:
            research_field: 研究分野
        
        Returns:
            レポートエクスポート結果
        """
        return self.export_ops.export_research_field_report(research_field)
    
    # === 検索機能（データベースハンドラへの委譲） ===
    
    def search_data(self, **kwargs) -> List[Dict[str, Any]]:
        """
        データを検索
        
        Args:
            **kwargs: 検索条件（keyword, data_type, research_field, limit）
        
        Returns:
            検索結果のリスト
        """
        return self.db_handler.search_data(**kwargs)
    
    # === データセット管理機能（DatasetManagerへの委譲） ===
    
    def register_dataset(self, directory_path: str, 
                        custom_name: str = None,
                        custom_description: str = None) -> Dict[str, Any]:
        """
        ディレクトリをデータセットとして登録
        
        Args:
            directory_path: ディレクトリパス
            custom_name: カスタム名
            custom_description: カスタム説明
        
        Returns:
            登録結果
        """
        return self.dataset_manager.register_dataset(directory_path, custom_name, custom_description)
    
    def search_datasets(self, query: str = "", 
                       research_field: str = None,
                       data_type: str = None,
                       tags: List[str] = None,
                       limit: int = 20) -> List[Dict[str, Any]]:
        """
        データセットを検索
        
        Args:
            query: 検索クエリ
            research_field: 研究分野
            data_type: データタイプ
            tags: タグリスト
            limit: 取得件数
        
        Returns:
            検索結果
        """
        return self.dataset_manager.search_datasets(query, research_field, data_type, tags, limit)
    
    def get_dataset_by_id(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """
        データセットIDでデータセットを取得
        
        Args:
            dataset_id: データセットID
        
        Returns:
            データセット情報
        """
        return self.dataset_manager.get_dataset_by_id(dataset_id)
    
    def update_dataset_tags(self, dataset_id: str, new_tags: List[str]) -> Dict[str, Any]:
        """
        データセットのタグを更新
        
        Args:
            dataset_id: データセットID
            new_tags: 新しいタグリスト
        
        Returns:
            更新結果
        """
        return self.dataset_manager.update_dataset_tags(dataset_id, new_tags)
    
    def get_all_dataset_tags(self) -> List[str]:
        """
        全データセットのタグを取得
        
        Returns:
            タグリスト
        """
        return self.dataset_manager.get_all_tags()