"""
データセット詳細解説機能
ユーザーの質問に応じたデータセットの詳細説明と活用提案
"""

from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

from ..database.new_repository import DatasetRepository, DatasetFileRepository
from ..analyzer.gemini_client import GeminiClient

logger = logging.getLogger(__name__)


class DatasetAdvisor:
    """データセット詳細解説機能を提供するクラス"""
    
    def __init__(self):
        self.dataset_repo = DatasetRepository()
        self.dataset_file_repo = DatasetFileRepository()
        self.gemini_client = GeminiClient()
    
    def explain_dataset(self, dataset_name: str, user_question: str = "") -> Dict[str, Any]:
        """データセットの詳細解説"""
        try:
            # データセット情報を取得
            datasets = self.dataset_repo.find_all()
            target_dataset = None
            
            for dataset in datasets:
                if dataset.name.lower() == dataset_name.lower():
                    target_dataset = dataset
                    break
            
            if not target_dataset:
                return {
                    "error": f"データセット '{dataset_name}' が見つかりません",
                    "available_datasets": [ds.name for ds in datasets]
                }
            
            # データセットファイル情報を取得
            dataset_files = self.dataset_file_repo.find_by_dataset_id(target_dataset.id)
            
            # 基本情報を構築
            basic_info = self._build_dataset_basic_info(target_dataset, dataset_files)
            
            # ユーザーの質問がある場合はGemini APIで詳細解説を生成
            detailed_explanation = ""
            if user_question:
                detailed_explanation = self._generate_detailed_explanation(
                    target_dataset, dataset_files, user_question
                )
            
            # 分析手法の提案
            analysis_suggestions = self._suggest_analysis_methods(target_dataset, dataset_files)
            
            # 活用事例の提案
            use_case_suggestions = self._suggest_use_cases(target_dataset, dataset_files)
            
            return {
                "dataset_name": target_dataset.name,
                "basic_info": basic_info,
                "detailed_explanation": detailed_explanation,
                "analysis_suggestions": analysis_suggestions,
                "use_case_suggestions": use_case_suggestions,
                "files_info": self._format_files_info(dataset_files),
                "metadata": {
                    "file_count": target_dataset.file_count,
                    "total_size": target_dataset.total_size,
                    "created_at": target_dataset.created_at,
                    "updated_at": target_dataset.updated_at
                }
            }
            
        except Exception as e:
            logger.error(f"データセット解説エラー: {e}")
            return {
                "error": "データセット解説の生成中にエラーが発生しました",
                "details": str(e)
            }
    
    def _build_dataset_basic_info(self, dataset, dataset_files: List) -> Dict[str, Any]:
        """データセットの基本情報を構築"""
        file_types = {}
        total_files = len(dataset_files)
        
        for file in dataset_files:
            file_type = file.file_type
            if file_type not in file_types:
                file_types[file_type] = 0
            file_types[file_type] += 1
        
        return {
            "name": dataset.name,
            "description": dataset.description,
            "summary": dataset.summary,
            "total_files": total_files,
            "file_types": file_types,
            "total_size_mb": round(dataset.total_size / (1024 * 1024), 2) if dataset.total_size else 0,
            "structure": self._analyze_dataset_structure(dataset_files)
        }
    
    def _analyze_dataset_structure(self, dataset_files: List) -> Dict[str, Any]:
        """データセット構造を分析"""
        structure = {
            "file_extensions": {},
            "file_sizes": [],
            "naming_patterns": []
        }
        
        for file in dataset_files:
            # ファイル拡張子
            ext = file.file_name.split('.')[-1].lower() if '.' in file.file_name else 'no_extension'
            if ext not in structure["file_extensions"]:
                structure["file_extensions"][ext] = 0
            structure["file_extensions"][ext] += 1
            
            # ファイルサイズ
            if file.file_size:
                structure["file_sizes"].append(file.file_size)
            
            # 命名パターン（簡易分析）
            name_pattern = self._extract_naming_pattern(file.file_name)
            if name_pattern not in structure["naming_patterns"]:
                structure["naming_patterns"].append(name_pattern)
        
        # 統計情報を追加
        if structure["file_sizes"]:
            structure["size_stats"] = {
                "min_size": min(structure["file_sizes"]),
                "max_size": max(structure["file_sizes"]),
                "avg_size": sum(structure["file_sizes"]) / len(structure["file_sizes"])
            }
        
        return structure
    
    def _extract_naming_pattern(self, filename: str) -> str:
        """ファイル名のパターンを抽出（簡易版）"""
        if filename.isdigit() or filename.replace('.', '').isdigit():
            return "numeric"
        elif any(char.isdigit() for char in filename):
            return "alphanumeric"
        else:
            return "alphabetic"
    
    def _generate_detailed_explanation(self, dataset, dataset_files: List, user_question: str) -> str:
        """詳細解説をGemini APIで生成"""
        try:
            # データセット情報をまとめる
            dataset_summary = dataset.summary or dataset.description or "詳細情報なし"
            
            # Gemini APIを呼び出し
            explanation = self.gemini_client.analyze_dataset_context(
                dataset.name, 
                dataset_summary, 
                user_question
            )
            
            return explanation or "詳細解説の生成に失敗しました"
            
        except Exception as e:
            logger.error(f"詳細解説生成エラー: {e}")
            return f"解説生成中にエラーが発生しました: {str(e)}"
    
    def _suggest_analysis_methods(self, dataset, dataset_files: List) -> List[Dict[str, Any]]:
        """分析手法を提案"""
        suggestions = []
        
        # ファイルタイプに基づく提案
        file_types = set(file.file_type for file in dataset_files)
        
        if 'csv' in file_types:
            suggestions.extend([
                {
                    "method": "記述統計分析",
                    "description": "データの基本的な統計情報を把握",
                    "tools": ["pandas", "numpy", "matplotlib"],
                    "difficulty": "初級"
                },
                {
                    "method": "相関分析",
                    "description": "変数間の関係性を分析",
                    "tools": ["pandas", "seaborn", "scipy"],
                    "difficulty": "初級"
                },
                {
                    "method": "機械学習モデリング",
                    "description": "予測モデルの構築と評価",
                    "tools": ["scikit-learn", "pandas", "matplotlib"],
                    "difficulty": "中級"
                }
            ])
        
        if 'json' in file_types or 'jsonl' in file_types:
            suggestions.extend([
                {
                    "method": "テキストマイニング",
                    "description": "テキストデータからの知識抽出",
                    "tools": ["NLTK", "spaCy", "scikit-learn"],
                    "difficulty": "中級"
                },
                {
                    "method": "感情分析",
                    "description": "テキストの感情や意見を分析",
                    "tools": ["transformers", "VADER", "TextBlob"],
                    "difficulty": "中級"
                }
            ])
        
        if 'pdf' in file_types:
            suggestions.extend([
                {
                    "method": "文書分析",
                    "description": "PDF文書の内容分析と要約",
                    "tools": ["PyPDF2", "NLTK", "spaCy"],
                    "difficulty": "中級"
                }
            ])
        
        # データセット名に基づく特化提案
        dataset_name_lower = dataset.name.lower()
        
        if 'esg' in dataset_name_lower:
            suggestions.append({
                "method": "ESG評価分析",
                "description": "環境・社会・ガバナンス指標の分析",
                "tools": ["pandas", "plotly", "scikit-learn"],
                "difficulty": "中級"
            })
        
        if 'bias' in dataset_name_lower or 'jbbq' in dataset_name_lower:
            suggestions.append({
                "method": "バイアス検出分析",
                "description": "データセット内のバイアスパターンの検出",
                "tools": ["pandas", "matplotlib", "fairlearn"],
                "difficulty": "上級"
            })
        
        return suggestions
    
    def _suggest_use_cases(self, dataset, dataset_files: List) -> List[Dict[str, Any]]:
        """活用事例を提案"""
        use_cases = []
        
        # データセット名に基づく活用事例
        dataset_name_lower = dataset.name.lower()
        
        if 'esg' in dataset_name_lower:
            use_cases.extend([
                {
                    "title": "企業のサステナビリティ評価",
                    "description": "ESG指標を用いた企業の持続可能性評価システムの構築",
                    "research_field": "経営学・環境学",
                    "complexity": "中級"
                },
                {
                    "title": "投資判断支援システム",
                    "description": "ESGデータを活用した責任投資の意思決定支援",
                    "research_field": "金融工学",
                    "complexity": "上級"
                }
            ])
        
        if 'green' in dataset_name_lower:
            use_cases.extend([
                {
                    "title": "環境排出量予測モデル",
                    "description": "施設の環境負荷予測とオプティマイゼーション",
                    "research_field": "環境工学",
                    "complexity": "中級"
                }
            ])
        
        if 'bias' in dataset_name_lower or 'jbbq' in dataset_name_lower:
            use_cases.extend([
                {
                    "title": "AI公平性評価システム",
                    "description": "機械学習モデルのバイアス検出と軽減",
                    "research_field": "機械学習・倫理学",
                    "complexity": "上級"
                },
                {
                    "title": "社会的バイアス研究",
                    "description": "質問応答システムにおける社会的偏見の分析",
                    "research_field": "社会学・計算機科学",
                    "complexity": "上級"
                }
            ])
        
        if 'tv' in dataset_name_lower:
            use_cases.extend([
                {
                    "title": "メディア効果分析",
                    "description": "テレビCMの効果測定と最適化",
                    "research_field": "マーケティング・メディア学",
                    "complexity": "中級"
                }
            ])
        
        # 汎用的な活用事例
        file_types = set(file.file_type for file in dataset_files)
        
        if 'csv' in file_types:
            use_cases.append({
                "title": "データ可視化ダッシュボード",
                "description": "インタラクティブなデータ可視化システムの構築",
                "research_field": "データサイエンス",
                "complexity": "初級"
            })
        
        return use_cases
    
    def _format_files_info(self, dataset_files: List) -> List[Dict[str, Any]]:
        """ファイル情報をフォーマット"""
        return [
            {
                "file_name": file.file_name,
                "file_type": file.file_type,
                "file_size": file.file_size,
                "file_size_mb": round(file.file_size / (1024 * 1024), 3) if file.file_size else 0,
                "indexed_at": file.indexed_at
            }
            for file in dataset_files
        ]
    
    def get_all_datasets_overview(self) -> Dict[str, Any]:
        """全データセットの概要を取得"""
        try:
            datasets = self.dataset_repo.find_all()
            
            overview = {
                "total_datasets": len(datasets),
                "total_files": sum(ds.file_count for ds in datasets),
                "total_size_mb": sum(ds.total_size for ds in datasets if ds.total_size) / (1024 * 1024),
                "datasets": []
            }
            
            for dataset in datasets:
                dataset_files = self.dataset_file_repo.find_by_dataset_id(dataset.id)
                file_types = {}
                
                for file in dataset_files:
                    if file.file_type not in file_types:
                        file_types[file.file_type] = 0
                    file_types[file.file_type] += 1
                
                overview["datasets"].append({
                    "name": dataset.name,
                    "description": dataset.description,
                    "file_count": dataset.file_count,
                    "file_types": file_types,
                    "size_mb": round(dataset.total_size / (1024 * 1024), 2) if dataset.total_size else 0,
                    "has_summary": bool(dataset.summary)
                })
            
            return overview
            
        except Exception as e:
            logger.error(f"データセット概要取得エラー: {e}")
            return {
                "error": "データセット概要の取得に失敗しました",
                "details": str(e)
            }
    
    def search_datasets_by_keyword(self, keyword: str) -> List[Dict[str, Any]]:
        """キーワードでデータセットを検索"""
        try:
            datasets = self.dataset_repo.find_all()
            matching_datasets = []
            
            keyword_lower = keyword.lower()
            
            for dataset in datasets:
                # 検索対象テキストを構築
                search_text = f"{dataset.name} {dataset.description or ''} {dataset.summary or ''}".lower()
                
                if keyword_lower in search_text:
                    dataset_files = self.dataset_file_repo.find_by_dataset_id(dataset.id)
                    
                    matching_datasets.append({
                        "name": dataset.name,
                        "description": dataset.description,
                        "summary": dataset.summary,
                        "file_count": dataset.file_count,
                        "file_types": list(set(file.file_type for file in dataset_files)),
                        "relevance": search_text.count(keyword_lower)  # 簡易関連度
                    })
            
            # 関連度順にソート
            matching_datasets.sort(key=lambda x: x["relevance"], reverse=True)
            
            return matching_datasets
            
        except Exception as e:
            logger.error(f"データセット検索エラー: {e}")
            return []