import json
from typing import Dict, Any, List
from datetime import datetime, timedelta
from collections import defaultdict
import logging

from ..database.repository import FileRepository, AnalysisResultRepository
from ..advisor.research_advisor import ResearchAdvisor

logger = logging.getLogger(__name__)


class StatsGenerator:
    """統計情報を生成するクラス"""
    
    def __init__(self):
        self.file_repo = FileRepository()
        self.analysis_repo = AnalysisResultRepository()
        self.advisor = ResearchAdvisor()
    
    def generate_overall_statistics(self) -> Dict[str, Any]:
        """全体の統計情報を生成"""
        all_files = self.file_repo.find_all()
        
        stats = {
            "総ファイル数": len(all_files),
            "カテゴリー別": self._get_category_stats(all_files),
            "ファイルタイプ別": self._get_file_type_stats(all_files),
            "サイズ統計": self._get_size_stats(all_files),
            "時系列統計": self._get_timeline_stats(all_files),
            "解析状況": self._get_analysis_stats(all_files),
            "研究トレンド": self.advisor.get_research_trends()
        }
        
        return stats
    
    def _get_category_stats(self, files: List) -> Dict[str, Any]:
        """カテゴリー別統計"""
        category_counts = defaultdict(int)
        category_sizes = defaultdict(int)
        
        for file in files:
            category_counts[file.category] += 1
            category_sizes[file.category] += file.file_size
        
        return {
            "件数": dict(category_counts),
            "合計サイズ（MB）": {
                cat: round(size / (1024 * 1024), 2) 
                for cat, size in category_sizes.items()
            }
        }
    
    def _get_file_type_stats(self, files: List) -> Dict[str, Any]:
        """ファイルタイプ別統計"""
        type_counts = defaultdict(int)
        type_sizes = defaultdict(int)
        
        for file in files:
            type_counts[file.file_type] += 1
            type_sizes[file.file_type] += file.file_size
        
        return {
            "件数": dict(type_counts),
            "合計サイズ（MB）": {
                ft: round(size / (1024 * 1024), 2) 
                for ft, size in type_sizes.items()
            }
        }
    
    def _get_size_stats(self, files: List) -> Dict[str, Any]:
        """サイズ統計"""
        if not files:
            return {
                "合計サイズ（MB）": 0,
                "平均サイズ（MB）": 0,
                "最大ファイル": None,
                "最小ファイル": None
            }
        
        sizes = [f.file_size for f in files]
        total_size = sum(sizes)
        
        max_file = max(files, key=lambda f: f.file_size)
        min_file = min(files, key=lambda f: f.file_size)
        
        return {
            "合計サイズ（MB）": round(total_size / (1024 * 1024), 2),
            "平均サイズ（MB）": round((total_size / len(files)) / (1024 * 1024), 2),
            "最大ファイル": {
                "名前": max_file.file_name,
                "サイズ（MB）": round(max_file.file_size / (1024 * 1024), 2)
            },
            "最小ファイル": {
                "名前": min_file.file_name,
                "サイズ（KB）": round(min_file.file_size / 1024, 2)
            }
        }
    
    def _get_timeline_stats(self, files: List) -> Dict[str, Any]:
        """時系列統計"""
        if not files:
            return {
                "最初の登録": None,
                "最新の登録": None,
                "過去30日の登録数": 0
            }
        
        indexed_dates = [f.indexed_at for f in files if f.indexed_at]
        if not indexed_dates:
            return {
                "最初の登録": None,
                "最新の登録": None,
                "過去30日の登録数": 0
            }
        
        earliest = min(indexed_dates)
        latest = max(indexed_dates)
        thirty_days_ago = datetime.now() - timedelta(days=30)
        
        recent_count = sum(1 for d in indexed_dates if d >= thirty_days_ago)
        
        return {
            "最初の登録": earliest.strftime("%Y-%m-%d %H:%M:%S"),
            "最新の登録": latest.strftime("%Y-%m-%d %H:%M:%S"),
            "過去30日の登録数": recent_count
        }
    
    def _get_analysis_stats(self, files: List) -> Dict[str, Any]:
        """解析状況の統計"""
        analyzed_count = 0
        
        for file in files:
            analysis_results = self.analysis_repo.find_by_file_id(file.id)
            if analysis_results:
                analyzed_count += 1
        
        return {
            "解析済みファイル数": analyzed_count,
            "未解析ファイル数": len(files) - analyzed_count,
            "解析率（%）": round((analyzed_count / len(files) * 100) if files else 0, 1)
        }
    
    def generate_category_report(self, category: str) -> Dict[str, Any]:
        """特定カテゴリーのレポートを生成"""
        files = self.file_repo.find_all(category=category)
        
        if not files:
            return {
                "カテゴリー": category,
                "ファイル数": 0,
                "メッセージ": f"{category}カテゴリーのファイルが見つかりません"
            }
        
        # キーワード集計
        all_keywords = []
        research_fields = defaultdict(int)
        
        for file in files:
            analysis_result = self.analysis_repo.find_latest_by_file_id(
                file.id, "content_analysis"
            )
            if analysis_result:
                try:
                    data = json.loads(analysis_result.result_data)
                    all_keywords.extend(data.get("keywords", []))
                    field = data.get("research_field")
                    if field:
                        research_fields[field] += 1
                except:
                    pass
        
        # キーワード頻度
        keyword_freq = defaultdict(int)
        for kw in all_keywords:
            keyword_freq[kw] += 1
        
        top_keywords = sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)[:20]
        
        return {
            "カテゴリー": category,
            "ファイル数": len(files),
            "合計サイズ（MB）": round(sum(f.file_size for f in files) / (1024 * 1024), 2),
            "ファイルタイプ分布": self._get_file_type_stats(files),
            "主要キーワード": dict(top_keywords),
            "研究分野": dict(research_fields),
            "最新ファイル": [
                {
                    "名前": f.file_name,
                    "登録日": f.indexed_at.strftime("%Y-%m-%d") if f.indexed_at else None
                }
                for f in sorted(files, key=lambda x: x.indexed_at or datetime.min, reverse=True)[:5]
            ]
        }
    
    def generate_analysis_report(self) -> Dict[str, Any]:
        """解析レポートを生成"""
        all_files = self.file_repo.find_all()
        
        analysis_types = defaultdict(int)
        analysis_timeline = defaultdict(int)
        
        for file in all_files:
            results = self.analysis_repo.find_by_file_id(file.id)
            for result in results:
                analysis_types[result.analysis_type] += 1
                if result.created_at:
                    date_key = result.created_at.strftime("%Y-%m-%d")
                    analysis_timeline[date_key] += 1
        
        # 最近7日間の解析数
        recent_days = []
        for i in range(7):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            recent_days.append({
                "日付": date,
                "解析数": analysis_timeline.get(date, 0)
            })
        
        return {
            "総解析数": sum(analysis_types.values()),
            "解析タイプ別": dict(analysis_types),
            "最近7日間の解析": recent_days,
            "平均解析数/日": round(sum(analysis_types.values()) / max(len(analysis_timeline), 1), 1)
        }
    
    def export_statistics(self, format: str = "json") -> str:
        """統計情報をエクスポート"""
        stats = self.generate_overall_statistics()
        
        if format == "json":
            return json.dumps(stats, ensure_ascii=False, indent=2, default=str)
        
        elif format == "text":
            lines = []
            lines.append("=" * 50)
            lines.append("研究データ管理システム 統計レポート")
            lines.append("=" * 50)
            lines.append(f"生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append("")
            
            # 基本統計
            lines.append("【基本統計】")
            lines.append(f"総ファイル数: {stats['総ファイル数']}")
            lines.append("")
            
            # カテゴリー別
            lines.append("【カテゴリー別統計】")
            for cat, count in stats['カテゴリー別']['件数'].items():
                size = stats['カテゴリー別']['合計サイズ（MB）'][cat]
                lines.append(f"  {cat}: {count}件 ({size} MB)")
            lines.append("")
            
            # ファイルタイプ別
            lines.append("【ファイルタイプ別統計】")
            for ft, count in stats['ファイルタイプ別']['件数'].items():
                size = stats['ファイルタイプ別']['合計サイズ（MB）'][ft]
                lines.append(f"  {ft}: {count}件 ({size} MB)")
            lines.append("")
            
            # サイズ統計
            lines.append("【サイズ統計】")
            size_stats = stats['サイズ統計']
            lines.append(f"  合計: {size_stats['合計サイズ（MB）']} MB")
            lines.append(f"  平均: {size_stats['平均サイズ（MB）']} MB")
            if size_stats['最大ファイル']:
                lines.append(f"  最大: {size_stats['最大ファイル']['名前']} ({size_stats['最大ファイル']['サイズ（MB）']} MB)")
            lines.append("")
            
            # 解析状況
            lines.append("【解析状況】")
            analysis = stats['解析状況']
            lines.append(f"  解析済み: {analysis['解析済みファイル数']}件")
            lines.append(f"  未解析: {analysis['未解析ファイル数']}件")
            lines.append(f"  解析率: {analysis['解析率（%）']}%")
            
            return "\n".join(lines)
        
        else:
            raise ValueError(f"未対応のフォーマット: {format}")