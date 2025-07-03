"""
学部内データ管理PaaS - HTTP APIエンドポイント

このファイルはRAGインターフェースをHTTP API化し、
外部システムからの利用を可能にします。
"""

from fastapi import FastAPI, HTTPException, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
import logging
from datetime import datetime

from rag_interface import RAGInterface, DocumentMetadata, SearchResult, IngestionResult, SystemStats

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPIアプリケーション初期化
app = FastAPI(
    title="学部内データ管理PaaS",
    description="研究データの統合管理・検索・引用支援API",
    version="1.0.0"
)

# CORS設定（開発用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番では適切に制限
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# RAGインターフェースの初期化
rag_interface = RAGInterface()


@app.on_event("startup")
async def startup_event():
    """アプリケーション起動時の処理"""
    logger.info("学部内データ管理PaaS started")


@app.on_event("shutdown")
async def shutdown_event():
    """アプリケーション終了時の処理"""
    logger.info("学部内データ管理PaaS shutting down")


@app.get("/")
async def root():
    """ヘルスチェック用エンドポイント"""
    return {
        "service": "学部内データ管理PaaS",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/health")
async def health_check():
    """詳細なヘルスチェック"""
    try:
        stats = rag_interface.get_system_stats()
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "system_stats": stats.to_dict()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"System unhealthy: {str(e)}")


@app.post("/documents/ingest", response_model=dict)
async def ingest_documents(source_path: Optional[str] = None):
    """
    文書の取り込みと自動解析を実行
    
    Args:
        source_path: 取り込み元パス（オプション）
        
    Returns:
        取り込み結果
    """
    try:
        logger.info(f"Starting document ingestion from: {source_path or 'default path'}")
        result = rag_interface.ingest_documents(source_path)
        
        if result.success:
            logger.info(f"Ingestion completed: {result.processed_files} files processed")
        else:
            logger.warning(f"Ingestion failed: {result.message}")
            
        return result.to_dict()
        
    except Exception as e:
        logger.error(f"Ingestion endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents/search", response_model=dict)
async def search_documents(
    q: str = Query(..., description="検索クエリ"),
    limit: int = Query(10, ge=1, le=100, description="結果の最大件数"),
    category: Optional[str] = Query(None, regex="^(dataset|paper|poster)$", description="カテゴリ絞り込み")
):
    """
    文書検索
    
    Args:
        q: 検索クエリ
        limit: 結果の最大件数
        category: カテゴリ絞り込み
        
    Returns:
        検索結果
    """
    try:
        logger.info(f"Search request: query='{q}', limit={limit}, category={category}")
        result = rag_interface.search_documents(q, limit, category)
        
        logger.info(f"Search completed: {result.total_count} results in {result.execution_time_ms}ms")
        return result.to_dict()
        
    except Exception as e:
        logger.error(f"Search endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents/{category}/{document_id}", response_model=dict)
async def get_document_detail(
    category: str = Path(..., regex="^(dataset|paper|poster)$", description="文書カテゴリ"),
    document_id: int = Path(..., ge=1, description="文書ID")
):
    """
    特定文書の詳細情報を取得
    
    Args:
        category: 文書カテゴリ
        document_id: 文書ID
        
    Returns:
        文書詳細情報
    """
    try:
        logger.info(f"Getting document detail: category={category}, id={document_id}")
        result = rag_interface.get_document_detail(document_id, category)
        
        if result is None:
            raise HTTPException(
                status_code=404, 
                detail=f"Document not found: {category}/{document_id}"
            )
        
        return result.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document detail endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/statistics", response_model=dict)
async def get_system_statistics():
    """
    システム統計情報を取得
    
    Returns:
        システム統計情報
    """
    try:
        logger.info("Getting system statistics")
        result = rag_interface.get_system_stats()
        return result.to_dict()
        
    except Exception as e:
        logger.error(f"Statistics endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents/categories")
async def get_available_categories():
    """
    利用可能な文書カテゴリを取得
    
    Returns:
        カテゴリ一覧
    """
    return {
        "categories": [
            {
                "id": "dataset",
                "name": "データセット",
                "description": "研究データセット（CSV、JSON等）"
            },
            {
                "id": "paper", 
                "name": "論文",
                "description": "学術論文（PDF）"
            },
            {
                "id": "poster",
                "name": "ポスター", 
                "description": "研究ポスター（PDF）"
            }
        ]
    }


# PaaS統合用のクライアントクラス
class PaaSClient:
    """
    PaaS API用のPythonクライアント
    
    外部システムから簡単にPaaS機能を利用するためのクライアント
    """
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        Args:
            base_url: PaaS APIのベースURL
        """
        import httpx
        self.base_url = base_url.rstrip('/')
        self.client = httpx.Client(timeout=30.0)
    
    def ingest_documents(self, source_path: Optional[str] = None) -> dict:
        """文書取り込みを実行"""
        params = {"source_path": source_path} if source_path else {}
        response = self.client.post(f"{self.base_url}/documents/ingest", params=params)
        response.raise_for_status()
        return response.json()
    
    def search_documents(self, query: str, limit: int = 10, category: Optional[str] = None) -> dict:
        """文書検索を実行"""
        params = {"q": query, "limit": limit}
        if category:
            params["category"] = category
        response = self.client.get(f"{self.base_url}/documents/search", params=params)
        response.raise_for_status()
        return response.json()
    
    def get_document(self, category: str, document_id: int) -> dict:
        """文書詳細を取得"""
        response = self.client.get(f"{self.base_url}/documents/{category}/{document_id}")
        response.raise_for_status()
        return response.json()
    
    def get_statistics(self) -> dict:
        """統計情報を取得"""
        response = self.client.get(f"{self.base_url}/statistics")
        response.raise_for_status()
        return response.json()


# 開発用の実行スクリプト
if __name__ == "__main__":
    import uvicorn
    
    print("Starting 学部内データ管理PaaS...")
    print("API Documentation: http://localhost:8000/docs")
    print("Health Check: http://localhost:8000/health")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")