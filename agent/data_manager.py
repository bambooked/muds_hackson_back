"""
データ管理モジュール
研究データの登録、更新、削除などの管理機能を提供
"""
import os
import shutil
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

from .database_handler import DatabaseHandler
from .metadata_extractor import MetadataExtractor
from .file_processor import FileProcessor


class DataManager:
    """研究データを管理するクラス"""
    
    def __init__(self, db_handler: Optional[DatabaseHandler] = None):
        """
        データマネージャの初期化
        
        Args:
            db_handler: データベースハンドラ（Noneの場合は新規作成）
        """
        self.db_handler = db_handler or DatabaseHandler()
        self.metadata_extractor = MetadataExtractor()
        self.file_processor = FileProcessor()
    
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
    
    def search_data(self, **kwargs) -> List[Dict[str, Any]]:
        """
        データを検索
        
        Args:
            **kwargs: 検索条件（keyword, data_type, research_field, limit）
        
        Returns:
            検索結果のリスト
        """
        return self.db_handler.search_data(**kwargs)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        システム統計を取得
        
        Returns:
            統計情報
        """
        stats = self.db_handler.get_statistics()
        
        # 追加の統計情報
        stats['system_info'] = {
            'version': '1.0.0',
            'database_path': self.db_handler.db_path,
            'supported_types': ['dataset', 'paper', 'poster']
        }
        
        return stats
    
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
        try:
            if data_ids:
                # 指定されたIDのデータを取得
                data_list = []
                for data_id in data_ids:
                    data = self.db_handler.get_data_by_id(data_id)
                    if data:
                        data_list.append(data)
            else:
                # 全データを取得
                data_list = self.db_handler.search_data(limit=10000)
            
            if format == 'json':
                import json
                export_path = f"agent/export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(export_path, 'w', encoding='utf-8') as f:
                    json.dump(data_list, f, ensure_ascii=False, indent=2)
            
            elif format == 'csv':
                import csv
                export_path = f"agent/export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                
                if data_list:
                    # CSVヘッダーの決定
                    headers = ['data_id', 'data_type', 'title', 'summary', 
                              'research_field', 'created_date', 'file_path']
                    
                    with open(export_path, 'w', encoding='utf-8', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=headers)
                        writer.writeheader()
                        
                        for data in data_list:
                            row = {k: data.get(k, '') for k in headers}
                            writer.writerow(row)
            else:
                return {
                    'success': False,
                    'error': f'サポートされていない形式: {format}'
                }
            
            return {
                'success': True,
                'export_path': export_path,
                'count': len(data_list),
                'message': f'{len(data_list)}件のデータをエクスポートしました'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'エクスポートエラー: {str(e)}'
            }
    
    def backup_database(self) -> Dict[str, Any]:
        """
        データベースのバックアップを作成
        
        Returns:
            バックアップ結果
        """
        try:
            backup_path = f"agent/database/backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            
            shutil.copy2(self.db_handler.db_path, backup_path)
            
            return {
                'success': True,
                'backup_path': backup_path,
                'message': 'データベースのバックアップが作成されました'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'バックアップエラー: {str(e)}'
            }