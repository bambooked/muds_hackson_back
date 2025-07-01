"""
バッチ操作機能
複数ファイルの一括登録とディレクトリ処理
"""
import os
from typing import Dict, Any, List

from ..database_handler import DatabaseHandler
from ..metadata_extractor import MetadataExtractor
from ..processing.file_processor import FileProcessor


class BatchOperations:
    """バッチ操作を行うクラス"""
    
    def __init__(self, db_handler: DatabaseHandler,
                 metadata_extractor: MetadataExtractor,
                 file_processor: FileProcessor):
        """
        バッチ操作クラスの初期化
        
        Args:
            db_handler: データベースハンドラ
            metadata_extractor: メタデータ抽出器
            file_processor: ファイルプロセッサ
        """
        self.db_handler = db_handler
        self.metadata_extractor = metadata_extractor
        self.file_processor = file_processor
    
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
        if not os.path.isdir(directory_path):
            return {
                'success': False,
                'error': f'ディレクトリが見つかりません: {directory_path}'
            }
        
        results = {
            'total_files': 0,
            'successful': 0,
            'failed': 0,
            'errors': []
        }
        
        # メタデータを一括抽出
        metadata_list = self.metadata_extractor.extract_from_directory(
            directory_path, recursive
        )
        
        for metadata in metadata_list:
            results['total_files'] += 1
            
            try:
                # ファイル処理
                file_path = metadata['file_path']
                processed_data = self.file_processor.process_file(file_path)
                
                # データの準備
                data = {
                    'data_id': metadata['data_id'],
                    'data_type': metadata['data_type'],
                    'title': processed_data.get('title') or metadata.get('title') or metadata['file_name'],
                    'summary': processed_data.get('summary', ''),
                    'research_field': processed_data.get('research_field', ''),
                    'created_date': metadata.get('created_date'),
                    'file_path': file_path,
                    'metadata': {
                        **metadata,
                        **processed_data.get('additional_metadata', {})
                    }
                }
                
                # データベースに挿入
                if self.db_handler.insert_data(data):
                    results['successful'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append(f"DB挿入失敗: {file_path}")
                    
            except Exception as e:
                results['failed'] += 1
                results['errors'].append(f"処理エラー ({metadata['file_path']}): {str(e)}")
        
        results['success'] = results['failed'] == 0
        return results
    
    def process_file_list(self, file_paths: List[str]) -> Dict[str, Any]:
        """
        ファイルリストを一括処理
        
        Args:
            file_paths: ファイルパスのリスト
        
        Returns:
            処理結果のサマリー
        """
        results = {
            'total_files': len(file_paths),
            'successful': 0,
            'failed': 0,
            'errors': [],
            'processed_files': []
        }
        
        for file_path in file_paths:
            try:
                # ファイルの存在確認
                if not os.path.exists(file_path):
                    results['failed'] += 1
                    results['errors'].append(f"ファイルが見つかりません: {file_path}")
                    continue
                
                # メタデータ抽出
                metadata = self.metadata_extractor.extract_metadata(file_path)
                
                # ファイル処理
                processed_data = self.file_processor.process_file(file_path)
                
                # データの統合
                data = {
                    'data_id': metadata['data_id'],
                    'data_type': metadata['data_type'],
                    'title': processed_data.get('title') or metadata.get('title') or os.path.basename(file_path),
                    'summary': processed_data.get('summary', ''),
                    'research_field': processed_data.get('research_field', ''),
                    'created_date': metadata.get('created_date'),
                    'file_path': file_path,
                    'metadata': {
                        **metadata,
                        **processed_data.get('additional_metadata', {})
                    }
                }
                
                # データベースに挿入
                if self.db_handler.insert_data(data):
                    results['successful'] += 1
                    results['processed_files'].append({
                        'file_path': file_path,
                        'data_id': data['data_id'],
                        'status': 'success'
                    })
                else:
                    results['failed'] += 1
                    results['errors'].append(f"DB挿入失敗: {file_path}")
                    results['processed_files'].append({
                        'file_path': file_path,
                        'status': 'db_error'
                    })
                
            except Exception as e:
                results['failed'] += 1
                results['errors'].append(f"処理エラー ({file_path}): {str(e)}")
                results['processed_files'].append({
                    'file_path': file_path,
                    'status': 'error',
                    'error': str(e)
                })
        
        results['success'] = results['failed'] == 0
        return results
    
    def update_multiple_data(self, data_updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        複数のデータを一括更新
        
        Args:
            data_updates: 更新データのリスト
                [{'data_id': 'id1', 'updates': {...}}, ...]
        
        Returns:
            更新結果のサマリー
        """
        results = {
            'total_updates': len(data_updates),
            'successful': 0,
            'failed': 0,
            'errors': []
        }
        
        for update_item in data_updates:
            try:
                data_id = update_item.get('data_id')
                updates = update_item.get('updates', {})
                
                if not data_id:
                    results['failed'] += 1
                    results['errors'].append("data_idが指定されていません")
                    continue
                
                # データの存在確認
                if not self.db_handler.get_data_by_id(data_id):
                    results['failed'] += 1
                    results['errors'].append(f"データが見つかりません: {data_id}")
                    continue
                
                # 更新実行
                if self.db_handler.update_data(data_id, updates):
                    results['successful'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append(f"更新失敗: {data_id}")
                
            except Exception as e:
                results['failed'] += 1
                results['errors'].append(f"更新エラー: {str(e)}")
        
        results['success'] = results['failed'] == 0
        return results