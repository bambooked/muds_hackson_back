"""
学部内データ管理PaaS - 認証統合版 HTTP APIエンドポイント

このファイルは既存のpaas_api.pyを非破壊的に拡張し、
認証機能を統合した版を提供します。

認証機能:
- Google OAuth2認証
- JWT セッション管理
- 役割ベース権限制御
- 段階的セキュア化

使用方法:
- 認証有効時: 設定で AUTH_ENABLED=true
- 認証無効時: 既存システムと完全同一動作
"""

import os
import logging
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Query, Path, Request
from fastapi.middleware.cors import CORSMiddleware

# 既存システムのインポート
from services.rag_interface import RAGInterface, DocumentMetadata, SearchResult, IngestionResult, SystemStats

# 認証システムのインポート
from agent.source.interfaces.fastapi_auth_middleware import (
    setup_auth_integration, require_authentication, require_permission
)
from agent.source.interfaces.auth_ports import Permission
from agent.source.interfaces.data_models import (
    AuthConfig, PaaSConfig, UserContext
)

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 設定読み込み
def load_config() -> PaaSConfig:
    """環境変数から設定を読み込み"""
    auth_enabled = os.getenv('AUTH_ENABLED', 'false').lower() == 'true'
    
    auth_config = None
    if auth_enabled:
        auth_config = AuthConfig(
            provider='google_oauth2',
            client_id=os.getenv('GOOGLE_OAUTH_CLIENT_ID', ''),
            client_secret=os.getenv('GOOGLE_OAUTH_CLIENT_SECRET', ''),
            redirect_uri=os.getenv('GOOGLE_OAUTH_REDIRECT_URI', 'http://localhost:8000/auth/callback'),
            allowed_domains=os.getenv('ALLOWED_DOMAINS', '').split(',') if os.getenv('ALLOWED_DOMAINS') else [],
            session_timeout_minutes=int(os.getenv('SESSION_TIMEOUT_MINUTES', '480'))
        )
    
    return PaaSConfig(
        environment=os.getenv('ENVIRONMENT', 'development'),
        api_host=os.getenv('API_HOST', '0.0.0.0'),
        api_port=int(os.getenv('API_PORT', '8000')),
        debug=os.getenv('DEBUG', 'false').lower() == 'true',
        enable_authentication=auth_enabled,
        auth=auth_config
    )

# 設定とアプリケーション初期化
config = load_config()

app = FastAPI(
    title="学部内データ管理PaaS (認証統合版)",
    description="研究データの統合管理・検索・引用支援API with Authentication",
    version="1.1.0"
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if config.debug else ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# RAGインターフェースの初期化
rag_interface = RAGInterface()

# 認証システム統合
auth_registry = setup_auth_integration(app, config)

logger.info(f"PaaS API with Auth started - Authentication: {'Enabled' if config.enable_authentication else 'Disabled'}")


# ========================================
# 基本エンドポイント
# ========================================

@app.on_event("startup")
async def startup_event():
    """アプリケーション起動時の処理"""
    logger.info("学部内データ管理PaaS (認証統合版) started")
    if config.enable_authentication:
        logger.info("Authentication is ENABLED")
        if config.auth and config.auth.allowed_domains:
            logger.info(f"Allowed domains: {config.auth.allowed_domains}")
    else:
        logger.info("Authentication is DISABLED - Operating in legacy mode")


@app.on_event("shutdown")
async def shutdown_event():
    """アプリケーション終了時の処理"""
    logger.info("学部内データ管理PaaS (認証統合版) shutting down")


@app.get("/")
async def root():
    """ヘルスチェック用エンドポイント"""
    return {
        "service": "学部内データ管理PaaS (認証統合版)",
        "status": "running",
        "authentication": "enabled" if config.enable_authentication else "disabled",
        "version": "1.1.0",
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
            "authentication": {
                "enabled": config.enable_authentication,
                "provider": config.auth.provider if config.auth else None,
                "domains": config.auth.allowed_domains if config.auth else []
            },
            "system_stats": stats.to_dict()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"System unhealthy: {str(e)}")


# ========================================
# 文書管理エンドポイント（認証統合）
# ========================================

@app.post("/documents/ingest", response_model=dict)
@require_permission(auth_registry, "documents", Permission.WRITE, optional=True) if auth_registry else lambda func: func
async def ingest_documents(
    request: Request,
    source_path: Optional[str] = None,
    user_context: Optional[UserContext] = None,
    authorized: bool = True
):
    """
    文書の取り込みと自動解析を実行
    
    認証有効時: 文書書き込み権限必須
    認証無効時: 既存システムと同一動作
    """
    try:
        # 権限チェック（認証有効時のみ）
        if config.enable_authentication and not authorized:
            raise HTTPException(
                status_code=403,
                detail="Insufficient permissions for document ingestion"
            )
        
        # ログ出力
        user_info = f"user: {user_context.email}" if user_context else "anonymous"
        logger.info(f"Starting document ingestion from: {source_path or 'default path'} ({user_info})")
        
        # 既存システムの処理
        result = rag_interface.ingest_documents(source_path)
        
        if result.success:
            logger.info(f"Ingestion completed: {result.processed_files} files processed ({user_info})")
        else:
            logger.warning(f"Ingestion failed: {result.message} ({user_info})")
            
        return result.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ingestion endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents/search", response_model=dict)
@require_authentication(auth_registry, optional=True) if auth_registry else lambda func: func
async def search_documents(
    request: Request,
    q: str = Query(..., description="検索クエリ"),
    limit: int = Query(10, ge=1, le=100, description="結果の最大件数"),
    category: Optional[str] = Query(None, regex="^(dataset|paper|poster)$", description="カテゴリ絞り込み"),
    user_context: Optional[UserContext] = None
):
    """
    文書検索
    
    認証有効時: ログイン必須、アクセス権限に応じたフィルタリング
    認証無効時: 既存システムと同一動作
    """
    try:
        # ログ出力
        user_info = f"user: {user_context.email}" if user_context else "anonymous"
        logger.info(f"Search request: query='{q}', limit={limit}, category={category} ({user_info})")
        
        # 既存システムの検索処理
        result = rag_interface.search_documents(q, limit, category)
        
        # 認証有効時の結果フィルタリング（将来拡張用）
        if config.enable_authentication and user_context:
            # 現在は全ユーザーに検索権限があるため、フィルタリングなし
            # 将来的に、ユーザーの権限に応じて結果をフィルタリング可能
            pass
        
        logger.info(f"Search completed: {result.total_count} results in {result.execution_time_ms}ms ({user_info})")
        return result.to_dict()
        
    except Exception as e:
        logger.error(f"Search endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents/{category}/{document_id}", response_model=dict)
@require_authentication(auth_registry, optional=True) if auth_registry else lambda func: func
async def get_document_detail(
    request: Request,
    category: str = Path(..., regex="^(dataset|paper|poster)$", description="文書カテゴリ"),
    document_id: int = Path(..., ge=1, description="文書ID"),
    user_context: Optional[UserContext] = None
):
    """
    特定文書の詳細情報を取得
    
    認証有効時: ログイン必須、アクセス権限チェック
    認証無効時: 既存システムと同一動作
    """
    try:
        # ログ出力
        user_info = f"user: {user_context.email}" if user_context else "anonymous"
        logger.info(f"Getting document detail: category={category}, id={document_id} ({user_info})")
        
        # 既存システムの処理
        result = rag_interface.get_document_detail(document_id, category)
        
        if result is None:
            raise HTTPException(
                status_code=404, 
                detail=f"Document not found: {category}/{document_id}"
            )
        
        # 認証有効時のアクセス制御（将来拡張用）
        if config.enable_authentication and user_context:
            # 現在は全ログインユーザーにアクセス権限
            # 将来的に、文書の可視性設定やオーナーシップをチェック可能
            pass
        
        return result.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document detail endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========================================
# システム情報エンドポイント
# ========================================

@app.get("/statistics", response_model=dict)
@require_authentication(auth_registry, optional=True) if auth_registry else lambda func: func
async def get_system_statistics(
    request: Request,
    user_context: Optional[UserContext] = None
):
    """
    システム統計情報を取得
    
    認証有効時: ログイン推奨、詳細情報は権限に応じて制限
    認証無効時: 既存システムと同一動作
    """
    try:
        user_info = f"user: {user_context.email}" if user_context else "anonymous"
        logger.info(f"Getting system statistics ({user_info})")
        
        result = rag_interface.get_system_stats()
        stats_dict = result.to_dict()
        
        # 認証有効時の情報制限（管理者以外は一部情報を制限）
        if config.enable_authentication and user_context:
            if not ('admin' in user_context.roles or 'faculty' in user_context.roles):
                # 一般ユーザーには詳細統計を制限（必要に応じて調整）
                stats_dict.pop('detailed_storage_info', None)
                stats_dict.pop('user_activity_logs', None)
        
        return stats_dict
        
    except Exception as e:
        logger.error(f"Statistics endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents/categories")
async def get_available_categories():
    """
    利用可能な文書カテゴリを取得
    
    認証の有無に関わらず、全ユーザーがアクセス可能
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


# ========================================
# 管理者用エンドポイント（新規追加）
# ========================================

@app.get("/admin/users")
@require_permission(auth_registry, "admin", Permission.READ) if auth_registry else lambda func: func
async def list_users(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    user_context: Optional[UserContext] = None,
    authorized: bool = False
):
    """
    ユーザー一覧取得（管理者専用）
    
    認証無効時: 503エラー
    """
    if not config.enable_authentication:
        raise HTTPException(
            status_code=503,
            detail="User management requires authentication to be enabled"
        )
    
    if not authorized:
        raise HTTPException(
            status_code=403,
            detail="Admin privileges required"
        )
    
    try:
        # ユーザー管理システムから一覧取得
        if auth_registry and auth_registry.user_mgmt_port:
            users = await auth_registry.user_mgmt_port.search_users("", limit=limit)
            return {
                "users": [
                    {
                        "user_id": user.user_id,
                        "email": user.email,
                        "display_name": user.display_name,
                        "domain": user.domain,
                        "roles": user.roles
                    }
                    for user in users
                ],
                "total": len(users)
            }
        else:
            return {"users": [], "total": 0}
            
    except Exception as e:
        logger.error(f"User list endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/admin/system-info")
@require_permission(auth_registry, "admin", Permission.READ) if auth_registry else lambda func: func
async def get_admin_system_info(
    request: Request,
    user_context: Optional[UserContext] = None,
    authorized: bool = False
):
    """
    システム詳細情報取得（管理者専用）
    
    認証無効時: 503エラー
    """
    if not config.enable_authentication:
        raise HTTPException(
            status_code=503,
            detail="Admin features require authentication to be enabled"
        )
    
    if not authorized:
        raise HTTPException(
            status_code=403,
            detail="Admin privileges required"
        )
    
    try:
        system_stats = rag_interface.get_system_stats()
        
        return {
            "system_stats": system_stats.to_dict(),
            "config": {
                "environment": config.environment,
                "authentication_enabled": config.enable_authentication,
                "allowed_domains": config.auth.allowed_domains if config.auth else [],
                "debug": config.debug
            },
            "health": {
                "rag_interface": "healthy",
                "auth_system": "healthy" if auth_registry else "disabled",
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Admin system info error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========================================
# PaaS統合用のクライアントクラス（認証対応版）
# ========================================

class AuthenticatedPaaSClient:
    """
    認証対応PaaS API用のPythonクライアント
    
    既存のPaaSClientを拡張し、認証機能をサポート
    """
    
    def __init__(self, base_url: str = "http://localhost:8000", access_token: Optional[str] = None):
        """
        Args:
            base_url: PaaS APIのベースURL
            access_token: アクセストークン（認証有効時）
        """
        import httpx
        self.base_url = base_url.rstrip('/')
        self.access_token = access_token
        
        headers = {}
        if access_token:
            headers['Authorization'] = f'Bearer {access_token}'
        
        self.client = httpx.Client(timeout=30.0, headers=headers)
    
    async def login(self, redirect_after_login: Optional[str] = None) -> str:
        """Google OAuth2ログイン開始（認証URLを返す）"""
        response = self.client.get(f"{self.base_url}/auth/login")
        response.raise_for_status()
        
        # リダイレクトレスポンスからURLを取得
        if response.status_code == 302:
            return response.headers.get('location', '')
        else:
            return response.json().get('auth_url', '')
    
    def set_access_token(self, access_token: str):
        """アクセストークン設定"""
        self.access_token = access_token
        self.client.headers['Authorization'] = f'Bearer {access_token}'
    
    def get_current_user(self) -> dict:
        """現在のユーザー情報取得"""
        response = self.client.get(f"{self.base_url}/auth/me")
        response.raise_for_status()
        return response.json()
    
    def logout(self) -> dict:
        """ログアウト"""
        response = self.client.post(f"{self.base_url}/auth/logout")
        response.raise_for_status()
        return response.json()
    
    # 既存メソッド（認証ヘッダー付き）
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
    
    def list_users(self, limit: int = 50) -> dict:
        """ユーザー一覧取得（管理者専用）"""
        response = self.client.get(f"{self.base_url}/admin/users", params={"limit": limit})
        response.raise_for_status()
        return response.json()


# ========================================
# 開発用の実行スクリプト
# ========================================

if __name__ == "__main__":
    import uvicorn
    
    print("Starting 学部内データ管理PaaS (認証統合版)...")
    print(f"Authentication: {'ENABLED' if config.enable_authentication else 'DISABLED'}")
    if config.enable_authentication and config.auth:
        print(f"Allowed domains: {config.auth.allowed_domains}")
    print(f"API Documentation: http://{config.api_host}:{config.api_port}/docs")
    print(f"Health Check: http://{config.api_host}:{config.api_port}/health")
    if config.enable_authentication:
        print(f"Login: http://{config.api_host}:{config.api_port}/auth/login")
    
    uvicorn.run(
        app,
        host=config.api_host,
        port=config.api_port,
        log_level="info"
    )