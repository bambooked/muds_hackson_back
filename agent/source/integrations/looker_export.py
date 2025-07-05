"""
Looker Studio用データエクスポート機能（Phase 1）
サマリー統計データのCSVエクスポートに特化
"""

import csv
import io
import os
from datetime import datetime
from typing import Dict, Any, Optional
import logging

from agent.source.database.new_repository import DatasetRepository, PaperRepository, PosterRepository

logger = logging.getLogger(__name__)

class LookerDataExporter:
    """Looker Studio用データエクスポートクラス"""
    
    def __init__(self, google_drive_integration=None):
        self.gdrive = google_drive_integration
        self.dataset_folder_name = "dataset"
        
        # リポジトリの初期化
        self.dataset_repo = DatasetRepository()
        self.paper_repo = PaperRepository()
        self.poster_repo = PosterRepository()
        
    def collect_summary_statistics(self) -> Dict[str, Any]:
        """サマリー統計データを収集"""
        try:
            # 各リポジトリから統計情報を取得
            papers_count = len(self.paper_repo.find_all())
            posters_count = len(self.poster_repo.find_all())
            datasets_count = len(self.dataset_repo.find_all())
            
            # データセットの詳細情報
            all_datasets = self.dataset_repo.find_all()
            total_files = sum(ds.file_count for ds in all_datasets)
            total_size_mb = sum(ds.total_size for ds in all_datasets)
            total_size_gb = round(total_size_mb / 1024, 2)
            
            # カテゴリ別の集計（データセット名から推測）
            category_counts = {
                'machine_learning': 0,
                'esg': 0,
                'visualization': 0,
                'others': 0
            }
            
            for ds in all_datasets:
                name_lower = ds.name.lower()
                if 'ml' in name_lower or 'ai' in name_lower or 'jbbq' in name_lower:
                    category_counts['machine_learning'] += 1
                elif 'esg' in name_lower:
                    category_counts['esg'] += 1
                elif 'chart' in name_lower or 'visual' in name_lower or 'tv' in name_lower:
                    category_counts['visualization'] += 1
                else:
                    category_counts['others'] += 1
            
            # 現在時刻
            current_time = datetime.now().isoformat()
            
            return {
                'total_papers': papers_count,
                'total_posters': posters_count,
                'total_datasets': datasets_count,
                'total_files': total_files,
                'total_size_gb': total_size_gb,
                'category_ml': category_counts['machine_learning'],
                'category_esg': category_counts['esg'],
                'category_viz': category_counts['visualization'],
                'category_others': category_counts['others'],
                'last_updated': current_time
            }
            
        except Exception as e:
            logger.error(f"Error collecting summary statistics: {e}")
            raise
    
    def create_summary_csv(self, stats: Dict[str, Any]) -> str:
        """統計データからCSV文字列を生成"""
        output = io.StringIO()
        writer = csv.writer(output)
        
        # ヘッダー
        writer.writerow(['metric', 'value', 'updated_at'])
        
        # データ行
        timestamp = stats['last_updated']
        metrics = [
            ('total_papers', stats['total_papers']),
            ('total_posters', stats['total_posters']),
            ('total_datasets', stats['total_datasets']),
            ('total_files', stats['total_files']),
            ('total_size_gb', stats['total_size_gb']),
            ('category_machine_learning', stats['category_ml']),
            ('category_esg', stats['category_esg']),
            ('category_visualization', stats['category_viz']),
            ('category_others', stats['category_others']),
        ]
        
        for metric_name, metric_value in metrics:
            writer.writerow([metric_name, metric_value, timestamp])
        
        return output.getvalue()
    
    async def export_to_drive(self) -> Dict[str, Any]:
        """Google Driveにサマリーデータをエクスポート"""
        try:
            # 1. 統計データを収集
            stats = self.collect_summary_statistics()
            logger.info(f"Collected statistics: {stats}")
            
            # 2. CSV文字列を生成
            csv_content = self.create_summary_csv(stats)
            
            # 3. 一時ファイルとして保存
            temp_file_path = '/tmp/summary_latest.csv'
            with open(temp_file_path, 'w', encoding='utf-8') as f:
                f.write(csv_content)
            
            # 4. Google Driveにアップロード
            if self.gdrive and self.gdrive.is_enabled():
                # datasetフォルダのIDを取得または作成
                dataset_folder_id = await self._ensure_dataset_folder()
                
                # ファイルをアップロード
                result = self.gdrive.upload_file(
                    file_path=temp_file_path,
                    parent_folder_id=dataset_folder_id
                )
                
                # 一時ファイルを削除
                os.remove(temp_file_path)
                
                return {
                    'success': True,
                    'file_id': result.get('id') if result else None,
                    'stats': stats,
                    'message': 'サマリーデータをGoogle Driveにエクスポートしました'
                }
            else:
                return {
                    'success': False,
                    'stats': stats,
                    'message': 'Google Drive連携が無効です'
                }
                
        except Exception as e:
            logger.error(f"Error exporting to drive: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f'エクスポート中にエラーが発生しました: {e}'
            }
    
    async def _ensure_dataset_folder(self) -> Optional[str]:
        """Google Drive内にdatasetフォルダを確保"""
        if not self.gdrive:
            return None
            
        try:
            # フォルダ検索
            query = f"name='{self.dataset_folder_name}' and mimeType='application/vnd.google-apps.folder'"
            results = self.gdrive.service.files().list(q=query).execute()
            folders = results.get('files', [])
            
            if folders:
                logger.info(f"Found existing dataset folder with ID: {folders[0]['id']}")
                return folders[0]['id']
            else:
                # フォルダ作成
                file_metadata = {
                    'name': self.dataset_folder_name,
                    'mimeType': 'application/vnd.google-apps.folder'
                }
                folder = self.gdrive.service.files().create(
                    body=file_metadata,
                    fields='id'
                ).execute()
                logger.info(f"Created dataset folder with ID: {folder.get('id')}")
                return folder.get('id')
        except Exception as e:
            logger.error(f"Error ensuring dataset folder: {e}")
            return None