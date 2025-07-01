"""
データエクスポート機能
データの出力、バックアップ、統計情報の提供
"""
import os
import shutil
import json
import csv
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..database_handler import DatabaseHandler


class ExportOperations:
    """データエクスポート操作を行うクラス"""
    
    def __init__(self, db_handler: DatabaseHandler):
        """
        エクスポート操作クラスの初期化
        
        Args:
            db_handler: データベースハンドラ
        """
        self.db_handler = db_handler
    
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
            # データの取得
            if data_ids:
                data_list = []
                for data_id in data_ids:
                    data = self.db_handler.get_data_by_id(data_id)
                    if data:
                        data_list.append(data)
            else:
                data_list = self.db_handler.search_data(limit=10000)
            
            # フォーマット別のエクスポート
            if format == 'json':
                return self._export_to_json(data_list)
            elif format == 'csv':
                return self._export_to_csv(data_list)
            else:
                return {
                    'success': False,
                    'error': f'サポートされていない形式: {format}'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'エクスポートエラー: {str(e)}'
            }
    
    def _export_to_json(self, data_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        JSONフォーマットでエクスポート
        
        Args:
            data_list: データリスト
        
        Returns:
            エクスポート結果
        """
        export_path = f"agent/export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        os.makedirs(os.path.dirname(export_path), exist_ok=True)
        
        with open(export_path, 'w', encoding='utf-8') as f:
            json.dump(data_list, f, ensure_ascii=False, indent=2)
        
        return {
            'success': True,
            'export_path': export_path,
            'count': len(data_list),
            'format': 'json',
            'message': f'{len(data_list)}件のデータをJSONでエクスポートしました'
        }
    
    def _export_to_csv(self, data_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        CSVフォーマットでエクスポート
        
        Args:
            data_list: データリスト
        
        Returns:
            エクスポート結果
        """
        export_path = f"agent/export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        os.makedirs(os.path.dirname(export_path), exist_ok=True)
        
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
        
        return {
            'success': True,
            'export_path': export_path,
            'count': len(data_list),
            'format': 'csv',
            'message': f'{len(data_list)}件のデータをCSVでエクスポートしました'
        }
    
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
    
    def export_metadata_summary(self) -> Dict[str, Any]:
        """
        メタデータサマリーをエクスポート
        
        Returns:
            サマリーエクスポート結果
        """
        try:
            # 全データを取得
            all_data = self.db_handler.search_data(limit=10000)
            
            # サマリー情報の生成
            summary = {
                'export_timestamp': datetime.now().isoformat(),
                'total_count': len(all_data),
                'data_types': {},
                'research_fields': {},
                'file_extensions': {},
                'monthly_distribution': {}
            }
            
            for data in all_data:
                # データタイプ別集計
                data_type = data.get('data_type', 'unknown')
                summary['data_types'][data_type] = summary['data_types'].get(data_type, 0) + 1
                
                # 研究分野別集計
                field = data.get('research_field', '未分類')
                if field:
                    summary['research_fields'][field] = summary['research_fields'].get(field, 0) + 1
                
                # ファイル拡張子別集計
                metadata = data.get('metadata', {})
                if isinstance(metadata, dict):
                    ext = metadata.get('file_extension', '')
                    if ext:
                        summary['file_extensions'][ext] = summary['file_extensions'].get(ext, 0) + 1
                
                # 月別分布
                created_date = data.get('created_date', '')
                if created_date:
                    try:
                        month = created_date[:7]  # YYYY-MM
                        summary['monthly_distribution'][month] = summary['monthly_distribution'].get(month, 0) + 1
                    except:
                        pass
            
            # サマリーファイルの保存
            export_path = f"agent/metadata_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            
            return {
                'success': True,
                'export_path': export_path,
                'summary': summary,
                'message': 'メタデータサマリーをエクスポートしました'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'サマリーエクスポートエラー: {str(e)}'
            }
    
    def export_research_field_report(self, research_field: str) -> Dict[str, Any]:
        """
        特定の研究分野のレポートをエクスポート
        
        Args:
            research_field: 研究分野
        
        Returns:
            レポートエクスポート結果
        """
        try:
            # 指定分野のデータを取得
            field_data = self.db_handler.search_data(
                research_field=research_field,
                limit=1000
            )
            
            if not field_data:
                return {
                    'success': False,
                    'error': f'研究分野「{research_field}」のデータが見つかりません'
                }
            
            # レポートの生成
            report = {
                'research_field': research_field,
                'report_timestamp': datetime.now().isoformat(),
                'total_count': len(field_data),
                'data_types': {},
                'recent_data': [],
                'popular_keywords': {},
                'data_list': field_data
            }
            
            # 分析処理
            for data in field_data:
                # データタイプ分布
                data_type = data.get('data_type', 'unknown')
                report['data_types'][data_type] = report['data_types'].get(data_type, 0) + 1
                
                # 最近のデータ（上位5件）
                if len(report['recent_data']) < 5:
                    report['recent_data'].append({
                        'data_id': data['data_id'],
                        'title': data.get('title', ''),
                        'created_date': data.get('created_date', '')
                    })
            
            # レポートファイルの保存
            export_path = f"agent/field_report_{research_field}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            
            return {
                'success': True,
                'export_path': export_path,
                'research_field': research_field,
                'count': len(field_data),
                'message': f'研究分野「{research_field}」のレポートをエクスポートしました'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'分野レポートエクスポートエラー: {str(e)}'
            }