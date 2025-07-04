from typing import Dict, Any, List, Optional
import logging
from pathlib import Path
from datetime import datetime

from .scanner import FileScanner
from ..database.new_repository import (
    DatasetRepository, PaperRepository, PosterRepository, DatasetFileRepository
)
from ..database.new_models import Dataset, Paper, Poster, DatasetFile

logger = logging.getLogger(__name__)


class NewFileIndexer:
    """新しいデータベース構造に対応したファイルインデクサー"""
    
    def __init__(self, auto_analyze: bool = True):
        self.scanner = FileScanner()
        self.dataset_repo = DatasetRepository()
        self.paper_repo = PaperRepository()
        self.poster_repo = PosterRepository()
        self.dataset_file_repo = DatasetFileRepository()
        self.auto_analyze = auto_analyze
        
        # 循環インポートを避けるため
        self._analyzer = None
    
    @property
    def analyzer(self):
        """アナライザーの遅延初期化"""
        if self._analyzer is None and self.auto_analyze:
            try:
                from ..analyzer.new_analyzer import NewFileAnalyzer
                self._analyzer = NewFileAnalyzer()
            except ImportError as e:
                logger.warning(f"アナライザーのインポートに失敗: {e}")
                self.auto_analyze = False
        return self._analyzer
    
    def index_all_files(self) -> Dict[str, Any]:
        """全ファイルをカテゴリー別テーブルにインデックス化"""
        logger.info("新しい構造でファイルのインデックス化を開始します")
        
        # ディレクトリをスキャン
        scanned_files = self.scanner.scan_directory()
        
        results = {
            "datasets": 0,
            "papers": 0,
            "posters": 0,
            "dataset_files": 0,
            "errors": 0,
            "details": []
        }
        
        # カテゴリー別に分類
        dataset_files_by_name = {}
        papers = []
        posters = []
        
        for file_obj in scanned_files:
            if file_obj.category == "datasets":
                dataset_name = self.scanner._get_dataset_name(Path(file_obj.file_path))
                if dataset_name:
                    if dataset_name not in dataset_files_by_name:
                        dataset_files_by_name[dataset_name] = []
                    dataset_files_by_name[dataset_name].append(file_obj)
            elif file_obj.category == "paper":
                papers.append(file_obj)
            elif file_obj.category == "poster":
                posters.append(file_obj)
        
        # データセットを処理
        for dataset_name, files in dataset_files_by_name.items():
            try:
                dataset_id = self._process_dataset(dataset_name, files)
                if dataset_id:
                    results["datasets"] += 1
                    results["dataset_files"] += len(files)
                    results["details"].append({
                        "action": "dataset_created",
                        "name": dataset_name,
                        "files": len(files)
                    })
                else:
                    results["errors"] += 1
            except Exception as e:
                logger.error(f"データセット処理エラー: {dataset_name}, {e}")
                results["errors"] += 1
        
        # 論文を処理
        for paper_file in papers:
            try:
                if self._process_paper(paper_file):
                    results["papers"] += 1
                    results["details"].append({
                        "action": "paper_created",
                        "file": paper_file.file_name
                    })
                else:
                    results["errors"] += 1
            except Exception as e:
                logger.error(f"論文処理エラー: {paper_file.file_name}, {e}")
                results["errors"] += 1
        
        # ポスターを処理
        for poster_file in posters:
            try:
                if self._process_poster(poster_file):
                    results["posters"] += 1
                    results["details"].append({
                        "action": "poster_created",
                        "file": poster_file.file_name
                    })
                else:
                    results["errors"] += 1
            except Exception as e:
                logger.error(f"ポスター処理エラー: {poster_file.file_name}, {e}")
                results["errors"] += 1
        
        logger.info(
            f"インデックス化完了: "
            f"データセット={results['datasets']}, "
            f"論文={results['papers']}, "
            f"ポスター={results['posters']}, "
            f"エラー={results['errors']}"
        )
        
        return results
    
    def _process_dataset(self, dataset_name: str, files: List) -> Optional[int]:
        """データセットを処理"""
        # 既存データセットをチェック
        existing_dataset = self.dataset_repo.find_by_name(dataset_name)
        
        if existing_dataset:
            dataset_id = existing_dataset.id
            logger.info(f"既存データセットを使用: {dataset_name}")
        else:
            # 新規データセット作成
            total_size = sum(f.file_size for f in files)
            dataset = Dataset(
                name=dataset_name,
                file_count=len(files),
                total_size=total_size
            )
            created_dataset = self.dataset_repo.create(dataset)
            dataset_id = created_dataset.id
            logger.info(f"新規データセットを作成: {dataset_name}")
        
        # データセットファイルを登録
        for file_obj in files:
            existing_file = self.dataset_file_repo.find_by_path(file_obj.file_path)
            if not existing_file:
                dataset_file = DatasetFile(
                    dataset_id=dataset_id,
                    file_path=file_obj.file_path,
                    file_name=file_obj.file_name,
                    file_type=file_obj.file_type,
                    file_size=file_obj.file_size,
                    created_at=file_obj.created_at,
                    updated_at=file_obj.updated_at,
                    content_hash=file_obj.content_hash
                )
                self.dataset_file_repo.create(dataset_file)
        
        # 自動解析を実行（未解析の場合のみ）
        if self.auto_analyze and self.analyzer:
            dataset_to_check = existing_dataset if existing_dataset else self.dataset_repo.find_by_id(dataset_id)
            if not dataset_to_check.summary:  # 未解析の場合のみ
                try:
                    logger.info(f"データセットの自動解析を開始: {dataset_name}")
                    self.analyzer.analyze_dataset(dataset_id)
                except Exception as e:
                    logger.warning(f"データセット自動解析に失敗: {dataset_name}, {e}")
        
        return dataset_id
    
    def _process_paper(self, file_obj) -> bool:
        """論文を処理"""
        existing_paper = self.paper_repo.find_by_path(file_obj.file_path)
        
        if existing_paper:
            logger.info(f"論文は既に登録済み: {file_obj.file_name}")
            paper_to_analyze = existing_paper
        else:
            paper = Paper(
                file_path=file_obj.file_path,
                file_name=file_obj.file_name,
                file_size=file_obj.file_size,
                created_at=file_obj.created_at,
                updated_at=file_obj.updated_at,
                content_hash=file_obj.content_hash
            )
            
            paper_to_analyze = self.paper_repo.create(paper)
        
        # 自動解析を実行（未解析の場合のみ）
        if self.auto_analyze and self.analyzer and paper_to_analyze.id:
            if not paper_to_analyze.abstract:  # 未解析の場合のみ
                try:
                    logger.info(f"論文の自動解析を開始: {file_obj.file_name}")
                    self.analyzer.analyze_paper(paper_to_analyze.id)
                except Exception as e:
                    logger.warning(f"論文自動解析に失敗: {file_obj.file_name}, {e}")
        
        return True
    
    def _process_poster(self, file_obj) -> bool:
        """ポスターを処理"""
        existing_poster = self.poster_repo.find_by_path(file_obj.file_path)
        
        if existing_poster:
            logger.info(f"ポスターは既に登録済み: {file_obj.file_name}")
            poster_to_analyze = existing_poster
        else:
            poster = Poster(
                file_path=file_obj.file_path,
                file_name=file_obj.file_name,
                file_size=file_obj.file_size,
                created_at=file_obj.created_at,
                updated_at=file_obj.updated_at,
                content_hash=file_obj.content_hash
            )
            
            poster_to_analyze = self.poster_repo.create(poster)
        
        # 自動解析を実行（未解析の場合のみ）
        if self.auto_analyze and self.analyzer and poster_to_analyze.id:
            if not poster_to_analyze.abstract:  # 未解析の場合のみ
                try:
                    logger.info(f"ポスターの自動解析を開始: {file_obj.file_name}")
                    self.analyzer.analyze_poster(poster_to_analyze.id)
                except Exception as e:
                    logger.warning(f"ポスター自動解析に失敗: {file_obj.file_name}, {e}")
        
        return True
    
    def get_index_status(self) -> Dict[str, Any]:
        """インデックスの状態を取得"""
        datasets = self.dataset_repo.find_all()
        papers = self.paper_repo.find_all()
        posters = self.poster_repo.find_all()
        
        total_dataset_files = 0
        total_dataset_size = 0
        
        for dataset in datasets:
            total_dataset_files += dataset.file_count
            total_dataset_size += dataset.total_size
        
        status = {
            "total_datasets": len(datasets),
            "total_papers": len(papers),
            "total_posters": len(posters),
            "total_dataset_files": total_dataset_files,
            "datasets": [
                {
                    "name": d.name,
                    "files": d.file_count,
                    "size_mb": round(d.total_size / (1024 * 1024), 2),
                    "summary": d.summary
                }
                for d in datasets
            ],
            "papers": [
                {
                    "name": p.file_name,
                    "title": p.title,
                    "authors": p.authors
                }
                for p in papers
            ],
            "posters": [
                {
                    "name": p.file_name,
                    "title": p.title,
                    "authors": p.authors
                }
                for p in posters
            ]
        }
        
        return status