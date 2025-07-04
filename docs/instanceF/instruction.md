# Instance F: Core API統合・修正 - 実装指示書

## 🎯 ミッション概要

**WHY**: 現在のシステムは機能豊富だが、APIレイヤーで実装が不完全な部分が存在する。特に`RAGInterface`の一部メソッドが未実装で、認証システムも独立したまま統合されていない。これらを完成させることで、フロントエンドや外部システムから利用可能な完全なAPIサービスとなる。

**WHAT**: RAGInterfaceの未実装メソッドを完成させ、Google OAuth2 + JWT認証システムを統合し、SwaggerUIでテスト可能な完全なAPI基盤を構築する。

**HOW**: 段階的にRepository層、認証層、API層を修正し、開発用ログイン機能を追加してテスト可能な状態にする。

## 📋 実装タスク一覧

### **タスク F1: Repository層の不足メソッド実装** [最優先]

#### 現在の問題
```bash
# 以下のエラーが発生中
services.rag_interface - ERROR - Search failed: 'DatasetRepository' object has no attribute 'search_by_keyword'
services.rag_interface - ERROR - Failed to get system stats: 'DatasetRepository' object has no attribute 'count_all'
```

#### 実装対象ファイル
`agent/source/database/new_repository.py`

#### 実装内容

**DatasetRepositoryクラスに追加:**
```python
def search_by_keyword(self, keyword: str) -> List[Dataset]:
    """データセットをキーワード検索"""
    query = """
    SELECT * FROM datasets 
    WHERE name LIKE ? OR description LIKE ? OR summary LIKE ?
    ORDER BY updated_at DESC
    """
    keyword_pattern = f"%{keyword}%"
    params = (keyword_pattern, keyword_pattern, keyword_pattern)
    rows = self.db.fetch_all(query, params)
    return [Dataset.from_dict(dict(row)) for row in rows]

def count_all(self) -> int:
    """全データセット数を取得"""
    query = "SELECT COUNT(*) FROM datasets"
    result = self.db.fetch_one(query)
    return result[0] if result else 0

def find_all(self) -> List[Dataset]:
    """全データセットを取得"""
    query = "SELECT * FROM datasets ORDER BY updated_at DESC"
    rows = self.db.fetch_all(query)
    return [Dataset.from_dict(dict(row)) for row in rows]
```

**PaperRepositoryクラスに追加:**
```python
def search_by_keyword(self, keyword: str) -> List[Paper]:
    """論文をキーワード検索（既存のsearch()メソッドのエイリアス）"""
    return self.search(keyword)

def count_all(self) -> int:
    """全論文数を取得"""
    query = "SELECT COUNT(*) FROM papers"
    result = self.db.fetch_one(query)
    return result[0] if result else 0

def find_all(self) -> List[Paper]:
    """全論文を取得"""
    query = "SELECT * FROM papers ORDER BY indexed_at DESC"
    rows = self.db.fetch_all(query)
    return [Paper.from_dict(dict(row)) for row in rows]
```

**PosterRepositoryクラスに追加:**
```python
def search_by_keyword(self, keyword: str) -> List[Poster]:
    """ポスターをキーワード検索（既存のsearch()メソッドのエイリアス）"""
    return self.search(keyword)

def count_all(self) -> int:
    """全ポスター数を取得"""
    query = "SELECT COUNT(*) FROM posters"
    result = self.db.fetch_one(query)
    return result[0] if result else 0

def find_all(self) -> List[Poster]:
    """全ポスターを取得"""
    query = "SELECT * FROM posters ORDER BY indexed_at DESC"
    rows = self.db.fetch_all(query)
    return [Poster.from_dict(dict(row)) for row in rows]
```

#### 検証方法
```bash
uv run python -c "
from services.rag_interface import RAGInterface
rag = RAGInterface()
result = rag.search_documents('test', limit=5)
stats = rag.get_system_stats()
print(f'検索: {result.total_count}件, 統計: {stats.total_documents}件')
"
```

### **タスク F2: 開発用認証エンドポイント実装** [高優先度]

#### 実装対象ファイル
`services/api/paas_api.py`

#### 実装内容

**必要なインポート追加:**
```python
import jwt
from datetime import datetime, timedelta
from typing import Optional
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends, HTTPException
```

**セキュリティスキーム定義:**
```python
security = HTTPBearer()
```

**開発用認証エンドポイント追加:**
```python
@app.get("/api/auth/dev-login", tags=["auth"])
async def dev_login(email: str = "test@university.ac.jp"):
    """
    開発用ログイン（本番では無効化）
    
    SwaggerUIでのテスト用に、JWTトークンを直接発行します。
    """
    if os.getenv("ENVIRONMENT") == "production":
        raise HTTPException(status_code=404, detail="Not found")
    
    # 開発用JWTトークン生成
    jwt_payload = {
        "user_id": f"dev_user_{hash(email) % 10000}",
        "email": email,
        "name": "開発用ユーザー",
        "exp": datetime.utcnow() + timedelta(hours=24),
        "iat": datetime.utcnow()
    }
    
    jwt_secret = os.getenv("JWT_SECRET_KEY", "development_secret_key_for_testing_only")
    jwt_token = jwt.encode(jwt_payload, jwt_secret, algorithm="HS256")
    
    return {
        "access_token": jwt_token,
        "token_type": "bearer",
        "expires_in": 86400,
        "user": {
            "email": email,
            "name": "開発用ユーザー"
        }
    }

@app.get("/api/auth/verify", tags=["auth"])
async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    JWTトークン検証エンドポイント
    """
    try:
        jwt_secret = os.getenv("JWT_SECRET_KEY", "development_secret_key_for_testing_only")
        payload = jwt.decode(credentials.credentials, jwt_secret, algorithms=["HS256"])
        
        return {
            "valid": True,
            "user": {
                "user_id": payload.get("user_id"),
                "email": payload.get("email"),
                "name": payload.get("name"),
                "exp": payload.get("exp")
            }
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="トークンが期限切れです")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="無効なトークンです")
```

**認証ヘルパー関数追加:**
```python
async def get_current_user_optional(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """JWT認証（オプショナル）"""
    if not credentials:
        return None
    
    try:
        jwt_secret = os.getenv("JWT_SECRET_KEY", "development_secret_key_for_testing_only")
        payload = jwt.decode(credentials.credentials, jwt_secret, algorithms=["HS256"])
        
        return {
            "user_id": payload["user_id"],
            "email": payload["email"],
            "name": payload["name"]
        }
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """JWT認証（必須）"""
    try:
        jwt_secret = os.getenv("JWT_SECRET_KEY", "development_secret_key_for_testing_only")
        payload = jwt.decode(credentials.credentials, jwt_secret, algorithms=["HS256"])
        
        return {
            "user_id": payload["user_id"],
            "email": payload["email"],
            "name": payload["name"]
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="トークンが期限切れです")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="無効なトークンです")
```

### **タスク F3: 検索API強化** [高優先度]

#### 実装対象ファイル
`services/api/paas_api.py`

#### 実装内容

**強化された検索エンドポイント:**
```python
@app.post("/api/documents/search", tags=["documents"])
async def search_documents_enhanced(
    query: str,
    category: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
    current_user = Depends(get_current_user_optional)
):
    """
    統合文書検索API
    
    Args:
        query: 検索クエリ
        category: カテゴリフィルタ ('dataset', 'paper', 'poster')
        limit: 取得件数制限
        offset: オフセット（ページネーション用）
        current_user: 認証ユーザー（オプション）
        
    Returns:
        検索結果とページネーション情報
    """
    try:
        # カテゴリフィルタリング対応
        search_result = rag_interface.search_documents(
            query=query,
            limit=limit + offset,  # オフセット分も含めて取得
            category=category
        )
        
        # ページネーション対応
        total_count = search_result.total_count
        documents = search_result.documents[offset:offset+limit]
        
        return {
            "documents": [doc.to_dict() for doc in documents],
            "pagination": {
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total_count
            },
            "query": query,
            "category": category,
            "execution_time_ms": search_result.execution_time_ms,
            "authenticated": current_user is not None
        }
        
    except Exception as e:
        logger.error(f"Search API error: {e}")
        raise HTTPException(status_code=500, detail=f"検索エラー: {str(e)}")

@app.get("/api/documents/{document_id}", tags=["documents"])
async def get_document_detail(
    document_id: int,
    category: str,
    current_user = Depends(get_current_user_optional)
):
    """
    文書詳細取得API
    
    Args:
        document_id: 文書ID
        category: カテゴリ ('dataset', 'paper', 'poster')
        current_user: 認証ユーザー（オプション）
        
    Returns:
        文書詳細情報
    """
    try:
        document = rag_interface.get_document_detail(document_id, category)
        if not document:
            raise HTTPException(status_code=404, detail="文書が見つかりません")
        
        result = document.to_dict()
        result["accessed_by"] = current_user["email"] if current_user else "anonymous"
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document detail API error: {e}")
        raise HTTPException(status_code=500, detail=f"文書取得エラー: {str(e)}")
```

**認証必須のテストエンドポイント:**
```python
@app.get("/api/protected/test", tags=["auth"])
async def protected_test(current_user = Depends(get_current_user)):
    """
    認証必須テストエンドポイント
    
    SwaggerUIでの認証テスト用
    """
    return {
        "message": "認証成功！",
        "user": current_user,
        "timestamp": datetime.now().isoformat()
    }
```

### **タスク F4: SwaggerUI認証設定** [中優先度]

#### 実装対象ファイル
`services/api/paas_api.py`

#### 実装内容

**FastAPIアプリケーション設定更新:**
```python
from fastapi.openapi.utils import get_openapi

app = FastAPI(
    title="研究データ管理API",
    description="""
    Google Drive連携による研究データの統合管理・検索・AI解析API
    
    ## 認証について
    - `/api/auth/dev-login` で開発用JWTトークンを取得
    - 右上の「Authorize」ボタンでトークンを設定
    - 認証が必要なエンドポイントをテスト可能
    
    ## 使用方法
    1. `/api/auth/dev-login` を実行してトークンを取得
    2. 「Authorize」ボタンをクリック
    3. 取得したトークンを入力
    4. 認証必須エンドポイントをテスト
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "auth", "description": "認証関連エンドポイント"},
        {"name": "documents", "description": "文書管理・検索"},
        {"name": "system", "description": "システム情報・ヘルスチェック"}
    ]
)

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
        
    openapi_schema = get_openapi(
        title="研究データ管理API",
        version="1.0.0",
        description="Google Drive連携による研究データの統合管理・検索・AI解析API",
        routes=app.routes,
    )
    
    # SwaggerUI用の認証設定
    openapi_schema["components"]["securitySchemes"] = {
        "HTTPBearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWTトークンを入力してください。dev-loginエンドポイントで取得可能です。"
        }
    }
    
    # グローバルセキュリティ設定（全エンドポイントで利用可能）
    openapi_schema["security"] = [{"HTTPBearer": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
```

### **タスク F5: エラーハンドリング統一** [中優先度]

#### 実装対象ファイル
`services/api/paas_api.py`

#### 実装内容

**統一エラーハンドリング:**
```python
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

class APIError(Exception):
    def __init__(self, message: str, status_code: int = 500, error_code: str = None):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code

@app.exception_handler(APIError)
async def api_error_handler(request, exc: APIError):
    """統一APIエラーレスポンス"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": exc.message,
                "code": exc.error_code,
                "timestamp": datetime.now().isoformat(),
                "path": str(request.url)
            }
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request, exc: RequestValidationError):
    """バリデーションエラーハンドリング"""
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "message": "リクエストの形式が正しくありません",
                "details": exc.errors(),
                "timestamp": datetime.now().isoformat(),
                "path": str(request.url)
            }
        }
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc: StarletteHTTPException):
    """HTTP例外ハンドリング"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": exc.detail,
                "timestamp": datetime.now().isoformat(),
                "path": str(request.url)
            }
        }
    )
```

## 🧪 テスト手順

### **段階1: Repository層テスト**
```bash
# F1完了後
uv run python -c "
from services.rag_interface import RAGInterface
rag = RAGInterface()
result = rag.search_documents('test', limit=5)
stats = rag.get_system_stats()
print(f'検索: {result.total_count}件, 統計: {stats.total_documents}件')
"
```

### **段階2: APIサーバー起動**
```bash
uv run python services/api/paas_api.py
```

### **段階3: SwaggerUIでの認証テスト**
1. `http://localhost:8000/docs` にアクセス
2. `/api/auth/dev-login` を実行してトークンを取得
3. 右上の **"Authorize"** ボタンをクリック
4. 取得したトークンを入力（`Bearer ` プレフィックスは不要）
5. `/api/protected/test` で認証テスト
6. `/api/documents/search` で検索API テスト

### **段階4: curl/Postmanでの詳細テスト**
```bash
# トークン取得
curl -X GET "http://localhost:8000/api/auth/dev-login?email=researcher@university.ac.jp"

# 環境変数に設定
export JWT_TOKEN="取得したトークン"

# 認証ありAPI呼び出し
curl -X POST "http://localhost:8000/api/documents/search" \
     -H "Authorization: Bearer $JWT_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"query": "機械学習", "limit": 5, "category": "paper"}'

# 認証なしAPIテスト
curl -X POST "http://localhost:8000/api/documents/search" \
     -H "Content-Type: application/json" \
     -d '{"query": "機械学習", "limit": 5}'
```

## ⚠️ 重要な注意事項

### **1. 非破壊的実装**
- 既存コードの変更は最小限に
- 新機能は既存機能に影響しない形で追加
- 設定による機能切り替えを維持

### **2. セキュリティ**
- 開発用ログインは本番環境で無効化
- JWT秘密鍵は環境変数で管理
- 本番環境では適切な認証フローに置き換え

### **3. エラーハンドリング**
- 全ての例外を適切にキャッチ
- ユーザーフレンドリーなエラーメッセージ
- ログ出力でデバッグ情報を記録

### **4. テスト駆動**
- 各実装完了後に必ずテスト実行
- SwaggerUIでの動作確認
- エラーケースのテスト

## 📊 成功基準

✅ **Repository層**: `search_by_keyword()`, `count_all()`, `find_all()` が正常動作  
✅ **認証システム**: SwaggerUIでJWT認証が利用可能  
✅ **検索API**: 強化された検索エンドポイントが動作  
✅ **エラーハンドリング**: 統一されたエラーレスポンス  
✅ **OpenAPI仕様**: SwaggerUIで完全なAPI仕様が表示  

## ⏱️ 推定工数

- **F1 (Repository実装)**: 2-3時間
- **F2 (開発用認証)**: 3-4時間  
- **F3 (検索API強化)**: 2-3時間
- **F4 (SwaggerUI設定)**: 1-2時間
- **F5 (エラーハンドリング)**: 1-2時間

**合計**: 約1日（9-14時間）

---

**Instance F完了により、Google Drive連携やベクトル検索等の他機能開発のためのしっかりとしたAPI基盤が整います。**