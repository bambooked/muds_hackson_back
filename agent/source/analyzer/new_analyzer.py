from typing import Dict, Any, Optional, List
import json
from pathlib import Path
import logging

from .gemini_client import GeminiClient
from .file_analyzer import FileAnalyzer
from ..database.new_repository import (
    DatasetRepository, PaperRepository, PosterRepository, DatasetFileRepository
)

logger = logging.getLogger(__name__)


class NewFileAnalyzer:
    """新しいデータベース構造に対応したファイル解析クラス"""
    
    def __init__(self):
        self.gemini_client = GeminiClient()
        self.file_analyzer = FileAnalyzer()
        self.dataset_repo = DatasetRepository()
        self.paper_repo = PaperRepository()
        self.poster_repo = PosterRepository()
        self.dataset_file_repo = DatasetFileRepository()
    
    def analyze_dataset(self, dataset_id: int) -> Optional[Dict[str, Any]]:
        """データセット全体を解析し、「このデータセットは～」形式で要約"""
        dataset = self.dataset_repo.find_by_id(dataset_id)
        if not dataset:
            logger.error(f"データセットが見つかりません: ID={dataset_id}")
            return None
        
        # データセット内のファイルを取得
        dataset_files = self.dataset_file_repo.find_by_dataset_id(dataset_id)
        
        if not dataset_files:
            logger.warning(f"データセット内にファイルがありません: {dataset.name}")
            return None
        
        # 各ファイルの内容を読み込み
        file_contents = []
        for file in dataset_files[:5]:  # 最大5ファイルを解析
            content = self._read_file_content(file.file_path, file.file_type)
            if content:
                file_contents.append({
                    'name': file.file_name,
                    'content': content
                })
        
        if not file_contents:
            logger.warning(f"読み込み可能なファイルがありません: {dataset.name}")
            return None
        
        # Gemini APIでデータセット全体を解析
        logger.info(f"データセット解析中: {dataset.name}")
        analysis_result = self.gemini_client.analyze_dataset_collection(
            dataset.name, file_contents
        )
        
        if analysis_result and "summary" in analysis_result:
            # データセットのsummaryを更新
            dataset.summary = analysis_result["summary"]
            dataset.description = analysis_result.get("main_purpose", "")
            self.dataset_repo.update(dataset)
            
            logger.info(f"データセット解析完了: {dataset.name}")
            logger.info(f"要約: {analysis_result['summary'][:100]}...")
        
        return analysis_result
    
    def analyze_paper(self, paper_id: int) -> Optional[Dict[str, Any]]:
        """論文を解析"""
        paper = self.paper_repo.find_by_id(paper_id)
        if not paper:
            logger.error(f"論文が見つかりません: ID={paper_id}")
            return None
        
        # ファイル内容を読み込み
        content = self._read_file_content(paper.file_path, "pdf")
        if not content:
            return None
        
        # Gemini APIで論文を解析
        logger.info(f"論文解析中: {paper.file_name}")
        analysis_result = self.gemini_client._analyze_pdf_content(content)
        
        if analysis_result:
            # 論文情報を更新
            paper.title = analysis_result.get("title", paper.file_name)
            paper.abstract = analysis_result.get("summary", "")
            paper.keywords = ", ".join(analysis_result.get("keywords", []))
            self.paper_repo.update(paper)
            
            logger.info(f"論文解析完了: {paper.file_name}")
        
        return analysis_result
    
    def analyze_poster(self, poster_id: int) -> Optional[Dict[str, Any]]:
        """ポスターを解析"""
        poster = self.poster_repo.find_by_id(poster_id)
        if not poster:
            logger.error(f"ポスターが見つかりません: ID={poster_id}")
            return None
        
        # ファイル内容を読み込み
        content = self._read_file_content(poster.file_path, "pdf")
        if not content:
            return None
        
        # Gemini APIでポスターを解析
        logger.info(f"ポスター解析中: {poster.file_name}")
        analysis_result = self.gemini_client._analyze_pdf_content(content)
        
        if analysis_result:
            # ポスター情報を更新
            poster.title = analysis_result.get("title", poster.file_name)
            poster.abstract = analysis_result.get("summary", "")
            poster.keywords = ", ".join(analysis_result.get("keywords", []))
            self.poster_repo.update(poster)
            
            logger.info(f"ポスター解析完了: {poster.file_name}")
        
        return analysis_result
    
    def _read_file_content(self, file_path: str, file_type: str) -> Optional[str]:
        """ファイル内容を読み込み（既存のfile_analyzerを使用）"""
        try:
            # 既存のfile_analyzerのメソッドを使用
            if file_type == "pdf":
                return self.file_analyzer._read_pdf(Path(file_path))
            elif file_type == "csv":
                return self.file_analyzer._read_csv(Path(file_path))
            elif file_type in ["json", "jsonl"]:
                return self.file_analyzer._read_json(Path(file_path))
            else:
                logger.warning(f"未対応のファイルタイプ: {file_type}")
                return None
        except Exception as e:
            logger.error(f"ファイル読み込みエラー: {file_path}, {e}")
            return None
    
    def get_analysis_summary(self) -> Dict[str, Any]:
        """解析状況のサマリーを取得"""
        datasets = self.dataset_repo.find_all()
        papers = self.paper_repo.find_all()
        posters = self.poster_repo.find_all()
        
        analyzed_datasets = sum(1 for d in datasets if d.summary)
        analyzed_papers = sum(1 for p in papers if p.abstract)
        analyzed_posters = sum(1 for p in posters if p.abstract)
        
        return {
            "datasets": {
                "total": len(datasets),
                "analyzed": analyzed_datasets,
                "rate": f"{analyzed_datasets/len(datasets)*100:.1f}%" if datasets else "0%"
            },
            "papers": {
                "total": len(papers),
                "analyzed": analyzed_papers,
                "rate": f"{analyzed_papers/len(papers)*100:.1f}%" if papers else "0%"
            },
            "posters": {
                "total": len(posters),
                "analyzed": analyzed_posters,
                "rate": f"{analyzed_posters/len(posters)*100:.1f}%" if posters else "0%"
            }
        }