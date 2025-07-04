# Research Data Management System - デプロイ準備改善タスク一覧

このドキュメントは、Research Data Management Systemを本番環境にデプロイするために必要な改善タスクを整理したものです。
各タスクはClaude Codeが効率的に実装できるよう、具体的なファイルパスと実装内容を含めて記載しています。

## 🎯 タスク実行時の重要事項

1. **既存機能を壊さない**: 各タスクは既存の機能を維持しながら実装してください
2. **段階的実装**: 各フェーズは独立して実装可能です
3. **テスト重視**: 新機能には必ずテストを追加してください
4. **ドキュメント更新**: 実装後は必ずCLAUDE.mdを更新してください

---

## Phase 1: セキュリティ基盤構築 🔐

### Task 1.1: 認証システムの実装
**優先度**: Critical
**工数見積もり**: 3-4日

**実装内容**:
```
1. agent/source/auth/ ディレクトリを新規作成
2. 以下のモジュールを実装:
   - auth/models.py: Userモデル（id, username, password_hash, role, created_at）
   - auth/authentication.py: ログイン/ログアウト、パスワードハッシュ化
   - auth/authorization.py: ロールベースアクセス制御（viewer/editor/admin）
   - auth/session.py: セッション管理
3. データベーステーブル追加:
   - users テーブル
   - sessions テーブル
4. 既存のUIに認証を統合:
   - agent/main.py: ログイン画面の追加
   - agent/source/ui/interface.py: 各機能に権限チェック追加
```

**必要な依存関係**:
- bcrypt: パスワードハッシュ化
- PyJWT: トークン生成（APIアクセス用）

**テスト作成**:
- agent/tests/test_auth.py: 認証機能の単体テスト
- agent/tests/test_authorization.py: 権限チェックのテスト

### Task 1.2: APIキー管理の強化
**優先度**: Critical
**工数見積もり**: 1-2日

**実装内容**:
```
1. agent/source/security/ ディレクトリを新規作成
2. security/secrets.py を実装:
   - 環境変数からの暗号化されたキー読み込み
   - キーの暗号化/復号化機能
   - メモリ内でのキー保護
3. config.py の更新:
   - ENCRYPTED_API_KEY のサポート
   - キー暗号化用のマスターキー管理
4. agent/source/analyzer/gemini_client.py の更新:
   - セキュアなAPIキー取得メソッドの使用
```

**オプション（推奨）**:
- AWS Secrets Manager統合
- HashiCorp Vault統合

### Task 1.3: 入力検証とサニタイゼーション
**優先度**: High
**工数見積もり**: 2日

**実装内容**:
```
1. agent/source/validation/ ディレクトリを新規作成
2. validation/validators.py を実装:
   - ファイルパス検証（パストラバーサル防止）
   - SQLインジェクション防止の追加検証
   - ファイルタイプ検証の強化
3. 各モジュールへの統合:
   - indexer/scanner.py: パス検証の追加
   - database/new_repository.py: 入力パラメータの検証
   - ui/interface.py: ユーザー入力の検証
```

---

## Phase 2: スケーラビリティ改善 📈

### Task 2.1: PostgreSQL移行
**優先度**: High
**工数見積もり**: 4-5日

**実装内容**:
```
1. agent/source/database/adapters/ ディレクトリを新規作成
2. データベースアダプター実装:
   - adapters/base.py: 抽象基底クラス
   - adapters/sqlite_adapter.py: 既存SQLite実装の移行
   - adapters/postgresql_adapter.py: PostgreSQL実装
3. database/connection.py の更新:
   - DATABASE_TYPE環境変数でアダプター選択
   - 接続プーリングの実装（PostgreSQL用）
4. database/new_repository.py の更新:
   - SQL方言の違いを吸収
   - パラメータプレースホルダーの抽象化
5. マイグレーションスクリプト作成:
   - scripts/migrate_to_postgresql.py
```

**必要な依存関係**:
- psycopg2-binary: PostgreSQL接続
- alembic: データベースマイグレーション

### Task 2.2: クラウドストレージ統合
**優先度**: High
**工数見積もり**: 3-4日

**実装内容**:
```
1. agent/source/storage/ ディレクトリを新規作成
2. ストレージアダプター実装:
   - storage/base.py: ストレージインターフェース
   - storage/local_storage.py: 既存のローカルファイルシステム
   - storage/s3_storage.py: AWS S3統合
   - storage/azure_storage.py: Azure Blob Storage統合（オプション）
3. config.py の更新:
   - STORAGE_TYPE設定（local/s3/azure）
   - クラウドストレージ認証情報
4. 各モジュールの更新:
   - indexer/scanner.py: ストレージアダプター使用
   - analyzer/file_analyzer.py: ファイル読み込みの抽象化
```

**必要な依存関係**:
- boto3: AWS S3アクセス
- azure-storage-blob: Azure Blob Storage（オプション）

### Task 2.3: 非同期処理とジョブキュー
**優先度**: Medium
**工数見積もり**: 3日

**実装内容**:
```
1. agent/source/workers/ ディレクトリを新規作成
2. ワーカー実装:
   - workers/base_worker.py: ワーカー基底クラス
   - workers/indexing_worker.py: インデックス作成の非同期化
   - workers/analysis_worker.py: ファイル解析の非同期化
3. agent/source/queue/ ディレクトリを新規作成:
   - queue/job_queue.py: ジョブキュー管理
   - queue/job_models.py: ジョブ定義
4. データベーステーブル追加:
   - jobs テーブル（ジョブ管理）
   - job_results テーブル（実行結果）
```

**必要な依存関係**:
- celery: 分散タスクキュー
- redis: メッセージブローカー

### Task 2.4: メモリ効率の改善
**優先度**: Medium
**工数見積もり**: 2日

**実装内容**:
```
1. agent/source/utils/streaming.py を新規作成:
   - ファイルのストリーミング読み込み
   - チャンクベースのハッシュ計算
   - ジェネレーターベースのデータ処理
2. 各モジュールの更新:
   - indexer/scanner.py: ストリーミングハッシュ計算
   - analyzer/file_analyzer.py: 大容量ファイルの分割処理
   - database/new_repository.py: ページネーション実装
```

---

## Phase 3: インフラストラクチャ準備 🏗️

### Task 3.1: Docker化
**優先度**: High
**工数見積もり**: 2日

**実装内容**:
```
1. プロジェクトルートに以下のファイルを作成:
   - Dockerfile: マルチステージビルド
   - docker-compose.yml: 開発環境用
   - docker-compose.prod.yml: 本番環境用
   - .dockerignore: 不要ファイルの除外
2. scripts/docker/ ディレクトリを作成:
   - docker/entrypoint.sh: コンテナ起動スクリプト
   - docker/healthcheck.py: ヘルスチェック
```

**Dockerfile要件**:
- Python 3.11ベースイメージ
- 非rootユーザーでの実行
- 最小限の依存関係のみインストール

### Task 3.2: Web API実装
**優先度**: High
**工数見積もり**: 4-5日

**実装内容**:
```
1. agent/api/ ディレクトリを新規作成
2. FastAPI実装:
   - api/main.py: FastAPIアプリケーション
   - api/routers/: エンドポイント定義
     - routers/auth.py: 認証エンドポイント
     - routers/datasets.py: データセットCRUD
     - routers/papers.py: 論文CRUD
     - routers/analysis.py: 解析エンドポイント
   - api/dependencies.py: 共通依存関係
   - api/middleware.py: 認証ミドルウェア
3. api/schemas/: Pydanticモデル
   - リクエスト/レスポンススキーマ定義
```

**必要な依存関係**:
- fastapi: Web APIフレームワーク
- uvicorn: ASGIサーバー
- pydantic: データバリデーション

### Task 3.3: ロギングとモニタリング
**優先度**: Medium
**工数見積もり**: 2-3日

**実装内容**:
```
1. agent/source/logging/ ディレクトリを新規作成
2. 構造化ロギング実装:
   - logging/structured_logger.py: JSON形式のロガー
   - logging/metrics.py: メトリクス収集
   - logging/tracing.py: 分散トレーシング
3. 各モジュールへの統合:
   - 全モジュールに構造化ロギング追加
   - パフォーマンスメトリクスの収集
   - エラートラッキング
```

**必要な依存関係**:
- structlog: 構造化ロギング
- prometheus-client: メトリクス収集
- opentelemetry: 分散トレーシング（オプション）

---

## Phase 4: 運用準備 🚀

### Task 4.1: バックアップとリカバリ
**優先度**: High
**工数見積もり**: 2日

**実装内容**:
```
1. scripts/backup/ ディレクトリを作成
2. バックアップスクリプト:
   - backup/database_backup.py: データベースバックアップ
   - backup/file_backup.py: ファイルバックアップ
   - backup/restore.py: リストアスクリプト
3. スケジューラー設定:
   - backup/scheduler.py: 定期バックアップ
```

### Task 4.2: CI/CDパイプライン
**優先度**: Medium
**工数見積もり**: 2日

**実装内容**:
```
1. .github/workflows/ ディレクトリを作成（GitHub Actions使用時）
2. ワークフロー定義:
   - workflows/test.yml: 自動テスト
   - workflows/build.yml: Dockerイメージビルド
   - workflows/deploy.yml: デプロイメント
3. scripts/deployment/ ディレクトリ:
   - deployment/health_check.py: デプロイ後の確認
   - deployment/rollback.py: ロールバックスクリプト
```

### Task 4.3: 設定管理の改善
**優先度**: Medium
**工数見積もり**: 1-2日

**実装内容**:
```
1. config/ ディレクトリを作成
2. 環境別設定:
   - config/base.py: 共通設定
   - config/development.py: 開発環境
   - config/production.py: 本番環境
   - config/testing.py: テスト環境
3. 設定検証:
   - config/validator.py: 起動時の設定検証
```

### Task 4.4: ドキュメント整備
**優先度**: Low
**工数見積もり**: 2日

**実装内容**:
```
1. docs/ ディレクトリに追加:
   - docs/deployment.md: デプロイメント手順
   - docs/api_reference.md: API仕様書
   - docs/operations.md: 運用手順書
   - docs/troubleshooting.md: トラブルシューティング
2. コード内ドキュメント:
   - 各モジュールにdocstring追加
   - 型ヒントの完全化
```

---

## 実装推奨順序

1. **Week 1-2**: Phase 1（セキュリティ基盤）
   - 認証なしでは本番環境は危険すぎるため最優先

2. **Week 3-4**: Phase 2のTask 2.1, 2.2
   - PostgreSQL移行とクラウドストレージは並行実装可能

3. **Week 5**: Phase 3のTask 3.1, 3.2
   - Docker化とAPI実装で外部公開の準備

4. **Week 6**: Phase 2のTask 2.3, 2.4 + Phase 4
   - 非同期処理と運用準備で本番対応完了

## 実装時の注意事項

### Claude Codeへの指示
1. **既存コードの理解**: 実装前に必ず関連ファイルを読み込んでください
2. **テスト駆動開発**: 新機能は先にテストを書いてから実装してください
3. **段階的マイグレーション**: 一度にすべてを変更せず、段階的に移行してください
4. **後方互換性**: 可能な限り既存の機能を維持してください

### 設定の管理
```python
# 新機能はすべて環境変数でON/OFF可能にする
ENABLE_AUTHENTICATION = os.getenv("ENABLE_AUTHENTICATION", "false").lower() == "true"
ENABLE_CLOUD_STORAGE = os.getenv("ENABLE_CLOUD_STORAGE", "false").lower() == "true"
```

### エラーハンドリング
```python
# 新機能の失敗が既存機能に影響しないようにする
try:
    # 新機能の処理
    pass
except NewFeatureError:
    logger.warning("新機能でエラーが発生しましたが、処理を継続します")
    # フォールバック処理
```

---

最終更新日: 2025年7月3日