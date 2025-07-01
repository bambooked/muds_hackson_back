"""
基本的なデータ操作機能
単一データの登録、更新、削除、取得
"""
import os
from typing import Dict, Any, Optional
from datetime import datetime

from ..database_handler import DatabaseHandler
from ..metadata_extractor import MetadataExtractor
from ..processing.file_processor import FileProcessor


class DataOperations:
    """基本的なデータ操作を行うクラス"""
    
    def __init__(self, db_handler: DatabaseHandler,
                 metadata_extractor: MetadataExtractor,
                 file_processor: FileProcessor):
        """
        データ操作クラスの初期化
        
        Args:
            db_handler: データベースハンドラ
            metadata_extractor: メタデータ抽出器
            file_processor: ファイルプロセッサ
        """
        self.db_handler = db_handler
        self.metadata_extractor = metadata_extractor
        self.file_processor = file_processor
    
    def register_single_data(self, file_path: str,
                           title: Optional[str] = None,
                           summary: Optional[str] = None,
                           research_field: Optional[str] = None) -> Dict[str, Any]:
        """
        単一ファイルのデータを登録
        
        Args:
            file_path: ファイルパス
            title: タイトル（省略時は自動抽出）
            summary: 概要（省略時は自動生成）
            research_field: 研究分野
        
        Returns:
            登録結果の辞書
        """
        try:
            # ファイルの存在確認
            if not os.path.exists(file_path):
                return {
                    'success': False,
                    'error': f'ファイルが見つかりません: {file_path}'
                }
            
            # メタデータの抽出
            metadata = self.metadata_extractor.extract_metadata(file_path)
            
            # ファイル処理（要約生成など）
            processed_data = self.file_processor.process_file(file_path)
            
            # データの統合
            data = {
                'data_id': metadata['data_id'],
                'data_type': metadata['data_type'],
                'title': title or processed_data.get('title') or metadata.get('title') or os.path.basename(file_path),
                'summary': summary or processed_data.get('summary', ''),
                'research_field': research_field or processed_data.get('research_field', ''),
                'created_date': metadata.get('created_date', datetime.now().isoformat()),
                'file_path': file_path,
                'metadata': {
                    **metadata,
                    **processed_data.get('additional_metadata', {})
                }
            }
            
            # データベースに挿入
            success = self.db_handler.insert_data(data)
            
            if success:
                return {
                    'success': True,
                    'data_id': data['data_id'],
                    'message': 'データが正常に登録されました'
                }
            else:
                return {
                    'success': False,
                    'error': 'データベースへの登録に失敗しました'
                }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'データ登録エラー: {str(e)}'
            }
    
    def update_data(self, data_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        既存のデータを更新
        
        Args:
            data_id: データID
            updates: 更新するフィールド
        
        Returns:
            更新結果
        """
        # データの存在確認
        existing_data = self.db_handler.get_data_by_id(data_id)
        if not existing_data:
            return {
                'success': False,
                'error': f'データが見つかりません: {data_id}'
            }
        
        # 更新実行
        success = self.db_handler.update_data(data_id, updates)
        
        if success:
            return {
                'success': True,
                'message': 'データが正常に更新されました'
            }
        else:
            return {
                'success': False,
                'error': 'データの更新に失敗しました'
            }
    
    def delete_data(self, data_id: str, delete_file: bool = False) -> Dict[str, Any]:
        """
        データを削除
        
        Args:
            data_id: データID
            delete_file: 実ファイルも削除するか
        
        Returns:
            削除結果
        """
        # データの取得
        data = self.db_handler.get_data_by_id(data_id)
        if not data:
            return {
                'success': False,
                'error': f'データが見つかりません: {data_id}'
            }
        
        # ファイルの削除（オプション）
        if delete_file and data.get('file_path'):
            try:
                if os.path.exists(data['file_path']):
                    os.remove(data['file_path'])
            except Exception as e:
                return {
                    'success': False,
                    'error': f'ファイル削除エラー: {str(e)}'
                }
        
        # データベースから削除
        success = self.db_handler.delete_data(data_id)
        
        if success:
            return {
                'success': True,
                'message': 'データが正常に削除されました'
            }
        else:
            return {
                'success': False,
                'error': 'データの削除に失敗しました'
            }
    
    def get_data_info(self, data_id: str) -> Optional[Dict[str, Any]]:
        """
        データの詳細情報を取得
        
        Args:
            data_id: データID
        
        Returns:
            データ情報またはNone
        """
        return self.db_handler.get_data_by_id(data_id)