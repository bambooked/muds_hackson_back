# プロダクションデプロイ戦略 - ハッカソンから本格運用へ

**作成日**: 2025年7月3日  
**対象**: ハッカソン完成版から本格的な学部内PaaS運用への移行

---

## 🎯 デプロイ要件分析

### 外部サービス統合（必須4サービス）
1. **Google Drive API** - 文書取り込み
2. **Google OAuth2** - 学部アカウント認証  
3. **Qdrant Cloud** - ベクトル検索（ChromaDBから移行）
4. **Render** - Webホスティング

### 内部アーキテクチャ変更
1. **Docker化** - コンテナベースデプロイ
2. **PostgreSQL移行** - SQLiteからPostgreSQLへ

---

## 🏗️ アーキテクチャ優位性分析

### ✅ 既存設計の優秀性
現在のPort/Adapterパターンにより、以下が**ゼロコスト**で切り替え可能：

```python
# 現在：開発環境
VectorSearchConfig(
    provider='chroma',
    host='localhost',
    persist_directory='./agent/vector_db'
)

# 本番：Qdrant Cloud
VectorSearchConfig(
    provider='qdrant',
    host='your-cluster.qdrant.io',
    api_key=os.getenv('QDRANT_API_KEY')
)
```

**設定変更のみ**でプロバイダー切り替え完了。実装コード変更不要。

### 🔄 分離されたレイヤー
```
Render Hosting
  ↓
Docker Container
  ↓
FastAPI Application
  ↓
Port/Adapter Layer（抽象化済み）
  ├─ VectorSearchPort → Qdrant Cloud
  ├─ AuthenticationPort → Google OAuth2  
  ├─ GoogleDrivePort → Google Drive API
  └─ DatabasePort → PostgreSQL
```

---

## 📋 外部サービス設定詳細

### 1. Google Cloud Console設定

#### 1.1 Google Drive API
```bash
# 必要なAPI有効化
gcloud services enable drive.googleapis.com
gcloud services enable oauth2.googleapis.com

# サービスアカウント作成
gcloud iam service-accounts create paas-drive-service \
  --display-name="PaaS Drive Integration"

# 権限付与（最小権限の原則）
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:paas-drive-service@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/drive.readonly"
```

#### 1.2 Google OAuth2設定
```yaml
# OAuth2 Client設定
redirect_uris:
  - "https://your-app.onrender.com/auth/callback"
  - "http://localhost:8000/auth/callback"  # 開発用

authorized_domains:
  - "your-app.onrender.com"
  - "university.ac.jp"

scopes:
  - "openid"
  - "email" 
  - "profile"
  - "https://www.googleapis.com/auth/drive.readonly"
```

### 2. Qdrant Cloud設定

#### 2.1 クラスター作成
```bash
# Qdrant Cloud Dashboard
1. クラスター作成（Tokyo リージョン推奨）
2. API Key取得
3. Cluster URL取得
4. Collection設定：
   - Name: research_documents
   - Vector size: 384 (sentence-transformers/all-MiniLM-L6-v2)
   - Distance: Cosine
```

#### 2.2 移行スクリプト
```python
# ChromaDB → Qdrant移行
class ChromaToQdrantMigrator:
    async def migrate_vectors(self):
        # 既存ChromaDBからベクトル抽出
        chroma_client = chromadb.PersistentClient(path="./agent/vector_db")
        collection = chroma_client.get_collection("research_documents")
        
        # Qdrant Cloudにアップロード
        qdrant_client = QdrantClient(
            host=os.getenv('QDRANT_HOST'),
            api_key=os.getenv('QDRANT_API_KEY')
        )
        
        # バッチ移行処理
        # 既存実装のVectorSearchPortで透過的に処理
```

### 3. Render設定

#### 3.1 サービス設定
```yaml
# render.yaml
services:
  - type: web
    name: research-paas
    env: python
    buildCommand: "uv sync"
    startCommand: "uv run python paas_api_with_auth.py"
    plan: starter
    envVars:
      - key: PAAS_ENVIRONMENT
        value: production
      - key: DATABASE_URL
        fromDatabase:
          name: research-db
          property: connectionString
      - key: QDRANT_HOST
        value: your-cluster.qdrant.io
      - key: QDRANT_API_KEY
        sync: false  # Manual secret
```

#### 3.2 PostgreSQL Database
```yaml
# Render PostgreSQL
databases:
  - name: research-db
    databaseName: research_paas
    user: paas_user
    plan: starter
```

---

## 🐳 Docker化戦略

### Dockerfile（マルチステージビルド）
```dockerfile
# Build stage
FROM python:3.11-slim as builder

WORKDIR /app
COPY pyproject.toml uv.lock ./

# Install uv and dependencies
RUN pip install uv
RUN uv sync --no-dev

# Production stage  
FROM python:3.11-slim as production

WORKDIR /app

# Copy dependencies from builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy application code
COPY agent/ ./agent/
COPY paas_api_with_auth.py ./
COPY enhanced_rag_interface.py ./
COPY config.py ./

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Non-root user
RUN groupadd -r paas && useradd -r -g paas paas
USER paas

EXPOSE 8000
CMD ["python", "paas_api_with_auth.py"]
```

### Docker Compose（開発環境）
```yaml
# docker-compose.yml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - PAAS_ENVIRONMENT=development
      - DATABASE_URL=postgresql://paas:password@db:5432/research_paas
      - QDRANT_HOST=qdrant
    depends_on:
      - db
      - qdrant
    volumes:
      - ./data:/app/data

  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: research_paas
      POSTGRES_USER: paas
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage

volumes:
  postgres_data:
  qdrant_data:
```

---

## 🗄️ データベース移行戦略

### 1. PostgreSQL対応（設定のみで完了）

#### 既存Repository抽象化活用
```python
# agent/source/database/connection.py（拡張）
class DatabaseConnection:
    def __init__(self):
        database_url = os.getenv('DATABASE_URL')
        
        if database_url and database_url.startswith('postgresql://'):
            # PostgreSQL接続
            self.engine = create_engine(database_url)
            self.db_type = 'postgresql'
        else:
            # SQLite接続（既存）
            self.engine = create_engine(f'sqlite:///{database_path}')
            self.db_type = 'sqlite'
```

#### 2. スキーマ移行スクリプト
```python
# migration/sqlite_to_postgresql.py
class DatabaseMigrator:
    async def migrate_to_postgresql(self):
        # 1. PostgreSQLにスキーマ作成
        await self._create_postgresql_schema()
        
        # 2. SQLiteからデータ抽出
        sqlite_data = await self._extract_sqlite_data()
        
        # 3. PostgreSQLにデータ挿入
        await self._insert_postgresql_data(sqlite_data)
        
        # 4. インデックス作成
        await self._create_indexes()
```

---

## 🚀 デプロイメントフロー

### Phase 1: 開発環境Docker化
```bash
# 1. Docker環境構築
docker-compose up -d

# 2. データベース移行テスト
uv run python migration/test_postgresql_migration.py

# 3. 機能テスト
docker-compose exec app python test_paas_integration.py
```

### Phase 2: Qdrant移行
```bash
# 1. Qdrant Cloud設定
export QDRANT_HOST=your-cluster.qdrant.io
export QDRANT_API_KEY=your-api-key

# 2. ベクトル移行
uv run python migration/chroma_to_qdrant.py

# 3. 検索性能確認
uv run python test_vector_search.py
```

### Phase 3: 本番デプロイ
```bash
# 1. Render設定
render deploy --service research-paas

# 2. データベース初期化
render run --service research-paas python migration/init_production_db.py

# 3. Google API設定
render env set GOOGLE_OAUTH_CLIENT_ID=your-client-id
render env set GOOGLE_DRIVE_CREDENTIALS_JSON=your-credentials

# 4. ヘルスチェック
curl https://your-app.onrender.com/health
```

---

## 📊 環境別設定管理

### 設定ファイル階層
```
config/
├── base.py              # 共通設定
├── development.py       # 開発環境
├── staging.py          # ステージング環境
└── production.py       # 本番環境
```

### 本番環境設定例
```python
# config/production.py
class ProductionConfig(BaseConfig):
    # データベース
    DATABASE_URL = os.getenv('DATABASE_URL')  # Render PostgreSQL
    
    # ベクトル検索
    VECTOR_SEARCH_PROVIDER = 'qdrant'
    QDRANT_HOST = os.getenv('QDRANT_HOST')
    QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')
    
    # 認証
    GOOGLE_OAUTH_CLIENT_ID = os.getenv('GOOGLE_OAUTH_CLIENT_ID')
    GOOGLE_OAUTH_CLIENT_SECRET = os.getenv('GOOGLE_OAUTH_CLIENT_SECRET')
    ALLOWED_DOMAINS = ['university.ac.jp']
    
    # セキュリティ
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
```

---

## 🔒 セキュリティ強化

### 1. 秘密情報管理
```bash
# Render Secrets設定
render env set JWT_SECRET_KEY=your-jwt-secret
render env set GOOGLE_OAUTH_CLIENT_SECRET=your-oauth-secret
render env set QDRANT_API_KEY=your-qdrant-key
render env set GEMINI_API_KEY=your-gemini-key
```

### 2. HTTPS/TLS設定
```python
# 本番用SSL設定
if os.getenv('PAAS_ENVIRONMENT') == 'production':
    app.add_middleware(
        HTTPSRedirectMiddleware
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=['your-app.onrender.com', 'university.ac.jp']
    )
```

---

## 📈 運用・監視

### 1. ヘルスチェック強化
```python
# 本番用ヘルスチェック
@app.get("/health")
async def health_check():
    checks = {
        'database': await check_database_health(),
        'qdrant': await check_qdrant_health(),
        'google_apis': await check_google_api_health(),
        'existing_system': await check_existing_system_health()
    }
    
    overall_status = 'healthy' if all(checks.values()) else 'degraded'
    return {'status': overall_status, 'checks': checks}
```

### 2. ログ・メトリクス
```python
# 構造化ログ
import structlog

logger = structlog.get_logger()
logger.info("Document search", user_id=user.id, query=query, results_count=len(results))
```

---

## 🧪 段階的移行プラン

### Week 1: インフラ準備
- [ ] Google Cloud Console設定
- [ ] Qdrant Cloud設定  
- [ ] Render アカウント設定
- [ ] Docker化完了

### Week 2: データ移行
- [ ] PostgreSQL移行テスト
- [ ] ベクトルデータ移行
- [ ] 統合テスト

### Week 3: 本番デプロイ
- [ ] ステージング環境構築
- [ ] 本番環境デプロイ
- [ ] パフォーマンステスト

### Week 4: 運用開始
- [ ] ユーザートレーニング
- [ ] 監視設定
- [ ] バックアップ設定

---

## 💰 コスト見積もり

### 外部サービス（月額）
- **Render**: $7-20 (Starter〜Professional)
- **Qdrant Cloud**: $25-100 (1Mベクトル〜)
- **Google APIs**: $0-50 (使用量ベース)
- **PostgreSQL**: $7 (Render Starter)

**合計**: $39-177/月（使用量次第）

### 既存設計の効果
Port/Adapterパターンにより：
- ✅ **開発工数**: 80%削減（設定変更のみ）
- ✅ **移行リスク**: 最小化（段階的切り替え）
- ✅ **保守性**: 各サービス独立して更新可能

---

**結論**: 現在のアーキテクチャ設計により、本格的なプロダクションデプロイは**設定中心の移行**で実現可能。実装変更はほぼ不要で、インフラ設定とデータ移行に集中できる。