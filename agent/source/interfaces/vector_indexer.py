"""
既存文書の自動ベクトル化ユーティリティ

Instance B: 既存32ファイルの自動ベクトル化機能
- 既存データベースから文書情報取得
- ファイル内容読み込み・前処理
- ベクトル化・インデックス作成
- バッチ処理・プログレス表示
"""

import os
import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime

from .vector_search_impl import ChromaVectorSearchPort, load_vector_search_config_from_env
from .data_models import DocumentMetadata, VectorSearchConfig
from ..database.new_repository import DatasetRepository, PaperRepository, PosterRepository, DatasetFileRepository

logger = logging.getLogger(__name__)


class VectorIndexer:
    """
    既存文書の自動ベクトル化クラス
    
    既存システム保護：
    - 既存データベースは読み取り専用アクセス
    - ベクトル化失敗時も既存システムに影響なし
    - プログレス表示で透明性確保
    """
    
    def __init__(self, vector_search_port: Optional[ChromaVectorSearchPort] = None):
        self.vector_search_port = vector_search_port or ChromaVectorSearchPort()
        self.dataset_repo = DatasetRepository()
        self.paper_repo = PaperRepository()
        self.poster_repo = PosterRepository()
        self.dataset_file_repo = DatasetFileRepository()
        
        # データディレクトリパス
        self.data_dir = Path(os.getenv('DATA_DIR_PATH', 'data'))
    
    async def initialize_vector_search(self, force_recreate: bool = False) -> bool:
        """ベクトル検索システム初期化"""
        try:
            config = load_vector_search_config_from_env()
            success = await self.vector_search_port.initialize_index(config, force_recreate)
            
            if success:
                logger.info("Vector search system initialized successfully")
            else:
                logger.warning("Vector search system initialization failed")
            
            return success
            
        except Exception as e:
            logger.error(f"Vector search initialization error: {e}")
            return False
    
    async def index_all_existing_documents(
        self, 
        batch_size: int = 5,
        categories: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        全既存文書のベクトル化実行
        
        Args:
            batch_size: バッチサイズ（同時処理数）
            categories: 対象カテゴリ（None=全て）
        
        Returns:
            Dict: 実行結果統計
        """
        
        start_time = datetime.now()
        results = {
            "total_documents": 0,
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "categories": {},
            "errors": [],
            "start_time": start_time.isoformat(),
            "end_time": None,
            "duration_seconds": 0
        }
        
        try:
            # ベクトル検索初期化確認
            if not self.vector_search_port.is_initialized:
                logger.info("Initializing vector search system...")
                init_success = await self.initialize_vector_search()
                if not init_success:
                    results["errors"].append("Failed to initialize vector search system")
                    return results
            
            # 対象カテゴリの設定
            target_categories = categories or ['dataset', 'paper', 'poster']
            
            # カテゴリ別処理
            for category in target_categories:
                logger.info(f"Processing category: {category}")
                
                if category == 'dataset':
                    category_results = await self._index_datasets(batch_size)
                elif category == 'paper':
                    category_results = await self._index_papers(batch_size)
                elif category == 'poster':
                    category_results = await self._index_posters(batch_size)
                else:
                    logger.warning(f"Unknown category: {category}")
                    continue
                
                # 結果統合
                results["categories"][category] = category_results
                results["total_documents"] += category_results["total"]
                results["successful"] += category_results["successful"]
                results["failed"] += category_results["failed"]
                results["skipped"] += category_results["skipped"]
                results["errors"].extend(category_results["errors"])
                
                logger.info(f"Category {category} completed: {category_results['successful']}/{category_results['total']} successful")
            
            # 実行時間計算
            end_time = datetime.now()
            results["end_time"] = end_time.isoformat()
            results["duration_seconds"] = (end_time - start_time).total_seconds()
            
            logger.info(f"Vector indexing completed: {results['successful']}/{results['total_documents']} documents indexed successfully")
            
            return results
            
        except Exception as e:
            logger.error(f"Vector indexing failed: {e}")
            results["errors"].append(f"General error: {str(e)}")
            return results
    
    async def _index_datasets(self, batch_size: int) -> Dict[str, Any]:
        """データセットのベクトル化"""
        results = {"total": 0, "successful": 0, "failed": 0, "skipped": 0, "errors": []}
        
        try:
            datasets = self.dataset_repo.find_all()
            results["total"] = len(datasets)
            
            if not datasets:
                logger.info("No datasets found for indexing")
                return results
            
            # バッチ処理
            for i in range(0, len(datasets), batch_size):
                batch = datasets[i:i + batch_size]
                batch_tasks = []
                
                for dataset in batch:
                    task = self._index_single_dataset(dataset)
                    batch_tasks.append(task)
                
                # バッチ実行
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                for j, result in enumerate(batch_results):
                    if isinstance(result, Exception):
                        results["failed"] += 1
                        results["errors"].append(f"Dataset {batch[j].name}: {str(result)}")
                    elif result:
                        results["successful"] += 1
                    else:
                        results["skipped"] += 1
                
                logger.info(f"Datasets batch {i//batch_size + 1} completed")
            
            return results
            
        except Exception as e:
            logger.error(f"Dataset indexing failed: {e}")
            results["errors"].append(f"Dataset processing error: {str(e)}")
            return results
    
    async def _index_papers(self, batch_size: int) -> Dict[str, Any]:
        """論文のベクトル化"""
        results = {"total": 0, "successful": 0, "failed": 0, "skipped": 0, "errors": []}
        
        try:
            papers = self.paper_repo.find_all()
            results["total"] = len(papers)
            
            if not papers:
                logger.info("No papers found for indexing")
                return results
            
            # バッチ処理
            for i in range(0, len(papers), batch_size):
                batch = papers[i:i + batch_size]
                batch_tasks = []
                
                for paper in batch:
                    task = self._index_single_paper(paper)
                    batch_tasks.append(task)
                
                # バッチ実行
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                for j, result in enumerate(batch_results):
                    if isinstance(result, Exception):
                        results["failed"] += 1
                        results["errors"].append(f"Paper {batch[j].file_name}: {str(result)}")
                    elif result:
                        results["successful"] += 1
                    else:
                        results["skipped"] += 1
                
                logger.info(f"Papers batch {i//batch_size + 1} completed")
            
            return results
            
        except Exception as e:
            logger.error(f"Paper indexing failed: {e}")
            results["errors"].append(f"Paper processing error: {str(e)}")
            return results
    
    async def _index_posters(self, batch_size: int) -> Dict[str, Any]:
        """ポスターのベクトル化"""
        results = {"total": 0, "successful": 0, "failed": 0, "skipped": 0, "errors": []}
        
        try:
            posters = self.poster_repo.find_all()
            results["total"] = len(posters)
            
            if not posters:
                logger.info("No posters found for indexing")
                return results
            
            # バッチ処理
            for i in range(0, len(posters), batch_size):
                batch = posters[i:i + batch_size]
                batch_tasks = []
                
                for poster in batch:
                    task = self._index_single_poster(poster)
                    batch_tasks.append(task)
                
                # バッチ実行
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                for j, result in enumerate(batch_results):
                    if isinstance(result, Exception):
                        results["failed"] += 1
                        results["errors"].append(f"Poster {batch[j].file_name}: {str(result)}")
                    elif result:
                        results["successful"] += 1
                    else:
                        results["skipped"] += 1
                
                logger.info(f"Posters batch {i//batch_size + 1} completed")
            
            return results
            
        except Exception as e:
            logger.error(f"Poster indexing failed: {e}")
            results["errors"].append(f"Poster processing error: {str(e)}")
            return results
    
    async def _index_single_dataset(self, dataset) -> bool:
        """単一データセットのベクトル化"""
        try:
            # DocumentMetadata作成
            document = DocumentMetadata(
                id=dataset.id,
                category='dataset',
                file_path='',  # データセットはディレクトリ
                file_name=dataset.name,
                file_size=dataset.total_size,
                created_at=dataset.created_at,
                updated_at=dataset.updated_at,
                title=dataset.name,
                summary=dataset.summary or ""
            )
            
            # 検索用コンテンツ作成（データセット説明とファイル情報）
            content_parts = [f"Dataset: {dataset.name}"]
            
            if dataset.summary:
                content_parts.append(f"Summary: {dataset.summary}")
            
            if dataset.description:
                content_parts.append(f"Description: {dataset.description}")
            
            # データセット内ファイル情報
            dataset_files = self.dataset_file_repo.find_by_dataset_id(dataset.id)
            if dataset_files:
                file_names = [f.file_name for f in dataset_files[:10]]  # 最初の10ファイル
                content_parts.append(f"Files: {', '.join(file_names)}")
            
            content = " ".join(content_parts)
            
            # ベクトル化実行
            success = await self.vector_search_port.index_document(document, content)
            
            if success:
                logger.debug(f"Dataset indexed: {dataset.name}")
            else:
                logger.warning(f"Dataset indexing failed: {dataset.name}")
            
            return success
            
        except Exception as e:
            logger.error(f"Dataset indexing error for {dataset.name}: {e}")
            raise e
    
    async def _index_single_paper(self, paper) -> bool:
        """単一論文のベクトル化"""
        try:
            # DocumentMetadata作成
            document = DocumentMetadata(
                id=paper.id,
                category='paper',
                file_path=paper.file_path,
                file_name=paper.file_name,
                file_size=paper.file_size,
                created_at=paper.created_at,
                updated_at=paper.updated_at,
                title=paper.title,
                summary=paper.abstract,
                authors=paper.authors,
                abstract=paper.abstract,
                keywords=paper.keywords
            )
            
            # 検索用コンテンツ作成
            content_parts = []
            
            if paper.title:
                content_parts.append(f"Title: {paper.title}")
            
            if paper.authors:
                content_parts.append(f"Authors: {paper.authors}")
            
            if paper.abstract:
                content_parts.append(f"Abstract: {paper.abstract}")
            
            if paper.keywords:
                content_parts.append(f"Keywords: {paper.keywords}")
            
            # ファイル内容読み込み（必要に応じて）
            file_content = self._read_file_content(paper.file_path)
            if file_content:
                content_parts.append(f"Content: {file_content[:1000]}")  # 最初の1000文字
            
            content = " ".join(content_parts)
            
            # ベクトル化実行
            success = await self.vector_search_port.index_document(document, content)
            
            if success:
                logger.debug(f"Paper indexed: {paper.file_name}")
            else:
                logger.warning(f"Paper indexing failed: {paper.file_name}")
            
            return success
            
        except Exception as e:
            logger.error(f"Paper indexing error for {paper.file_name}: {e}")
            raise e
    
    async def _index_single_poster(self, poster) -> bool:
        """単一ポスターのベクトル化"""
        try:
            # DocumentMetadata作成
            document = DocumentMetadata(
                id=poster.id,
                category='poster',
                file_path=poster.file_path,
                file_name=poster.file_name,
                file_size=poster.file_size,
                created_at=poster.created_at,
                updated_at=poster.updated_at,
                title=poster.title,
                summary=poster.abstract,
                authors=poster.authors,
                abstract=poster.abstract,
                keywords=poster.keywords
            )
            
            # 検索用コンテンツ作成
            content_parts = []
            
            if poster.title:
                content_parts.append(f"Title: {poster.title}")
            
            if poster.authors:
                content_parts.append(f"Authors: {poster.authors}")
            
            if poster.abstract:
                content_parts.append(f"Abstract: {poster.abstract}")
            
            if poster.keywords:
                content_parts.append(f"Keywords: {poster.keywords}")
            
            # ファイル内容読み込み（必要に応じて）
            file_content = self._read_file_content(poster.file_path)
            if file_content:
                content_parts.append(f"Content: {file_content[:1000]}")  # 最初の1000文字
            
            content = " ".join(content_parts)
            
            # ベクトル化実行
            success = await self.vector_search_port.index_document(document, content)
            
            if success:
                logger.debug(f"Poster indexed: {poster.file_name}")
            else:
                logger.warning(f"Poster indexing failed: {poster.file_name}")
            
            return success
            
        except Exception as e:
            logger.error(f"Poster indexing error for {poster.file_name}: {e}")
            raise e
    
    def _read_file_content(self, file_path: str) -> Optional[str]:
        """ファイル内容読み込み（エラー時はNone）"""
        try:
            if not file_path or not os.path.exists(file_path):
                return None
            
            # ファイルサイズチェック（大きすぎるファイルはスキップ）
            file_size = os.path.getsize(file_path)
            max_size = 10 * 1024 * 1024  # 10MB
            if file_size > max_size:
                logger.warning(f"File too large for content reading: {file_path} ({file_size} bytes)")
                return None
            
            # ファイル拡張子に基づく読み込み
            file_ext = Path(file_path).suffix.lower()
            
            if file_ext == '.pdf':
                # PDFは既存システムで解析済みのデータを使用（実際の内容読み込みはスキップ）
                return None
            
            elif file_ext in ['.txt', '.csv', '.json', '.jsonl']:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            
            else:
                logger.debug(f"Unsupported file type for content reading: {file_path}")
                return None
                
        except Exception as e:
            logger.warning(f"Failed to read file content: {file_path}, error: {e}")
            return None
    
    async def get_indexing_status(self) -> Dict[str, Any]:
        """ベクトル化状況取得"""
        try:
            # システム統計
            stats = await self.vector_search_port.get_index_stats()
            
            # カテゴリ別件数
            dataset_count = len(self.dataset_repo.find_all())
            paper_count = len(self.paper_repo.find_all())
            poster_count = len(self.poster_repo.find_all())
            
            total_documents = dataset_count + paper_count + poster_count
            
            return {
                "vector_index_stats": stats,
                "database_counts": {
                    "datasets": dataset_count,
                    "papers": paper_count,
                    "posters": poster_count,
                    "total": total_documents
                },
                "indexing_coverage": {
                    "indexed_documents": stats.get("total_documents", 0),
                    "total_documents": total_documents,
                    "coverage_percentage": (stats.get("total_documents", 0) / total_documents * 100) if total_documents > 0 else 0
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get indexing status: {e}")
            return {"error": str(e)}


# Convenience functions

async def index_all_documents(force_recreate: bool = False, batch_size: int = 5) -> Dict[str, Any]:
    """
    全文書の自動ベクトル化実行（コマンドライン用）
    
    Args:
        force_recreate: インデックス再作成
        batch_size: バッチサイズ
    
    Returns:
        Dict: 実行結果
    """
    indexer = VectorIndexer()
    
    if force_recreate:
        await indexer.initialize_vector_search(force_recreate=True)
    
    return await indexer.index_all_existing_documents(batch_size=batch_size)


async def get_vector_index_status() -> Dict[str, Any]:
    """ベクトルインデックス状況取得（コマンドライン用）"""
    indexer = VectorIndexer()
    await indexer.initialize_vector_search()
    return await indexer.get_indexing_status()


# Example usage
if __name__ == "__main__":
    import sys
    
    async def main():
        if len(sys.argv) > 1 and sys.argv[1] == "status":
            # 状況確認
            status = await get_vector_index_status()
            print("Vector Index Status:")
            print(f"  Indexed documents: {status['indexing_coverage']['indexed_documents']}")
            print(f"  Total documents: {status['indexing_coverage']['total_documents']}")
            print(f"  Coverage: {status['indexing_coverage']['coverage_percentage']:.1f}%")
        else:
            # 全文書インデックス作成
            print("Starting vector indexing for all documents...")
            results = await index_all_documents()
            print(f"Indexing completed: {results['successful']}/{results['total_documents']} successful")
            if results['errors']:
                print(f"Errors: {len(results['errors'])}")
    
    asyncio.run(main())