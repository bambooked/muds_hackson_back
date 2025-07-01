# Claude Code 実行指示書

## プロジェクト名
Research Data Management System

## プロジェクト概要
dataディレクトリ内の研究データ（論文、ポスター、データセット）を管理・要約するシステムを構築してください。

## 現在のディレクトリ構造
data/
├── datasets/  # CSV, JSON, JSONL, PDFファイル
├── paper/     # 論文PDFファイル
└── poster/    # ポスターPDFファイル

## 作成する基本構造
.
├── data/                  # 既存のデータディレクトリ
├── agent/
│   ├── source/
│   │   ├── database/      # データベース関連
│   │   ├── indexer/       # ファイルインデックス機能
│   │   ├── analyzer/      # Google Gemini API文書解析
│   │   ├── manager/       # データ管理・検索
│   │   ├── advisor/       # 研究相談・推薦機能
│   │   ├── statistics/    # 統計情報生成
│   │   └── ui/           # ユーザーインターフェース
│   ├── database/
│   │   └── research_data.db # SQLiteデータベース
│   ├── tests/             # テストファイル群
│   └── main.py           # メインアプリケーション
├── config.py             # 設定管理
├── .env                  # 環境変数設定
├── .env.example          # 環境変数のサンプル
├── pyproject.toml        # uv プロジェクト設定
├── README.md            # プロジェクト説明
└── api_docs.md          # API仕様書

## 主要機能要件

### 1. データベース管理 (database/)
- SQLite接続・初期化
- データモデル定義
- トランザクション管理

### 2. ファイルインデックス (indexer/)
- dataディレクトリの再帰的スキャン
- ファイルメタデータ抽出
- データベースへの登録

### 3. コンテンツ解析 (analyzer/)
- Google Gemini API連携
- PDF文書解析・要約
- データファイル（CSV/JSON/JSONL）構造解析
- 日本語・英語対応

### 4. データ管理 (manager/)
- ファイル検索・フィルタリング
- データベースCRUD操作
- ファイル更新・削除管理

### 5. 研究相談 (advisor/)
- ユーザークエリに基づく推薦
- 文書間類似度計算
- 研究方向性の提案

### 6. 統計情報 (statistics/)
- ファイル種別統計
- 研究分野分析
- 統計レポート生成

### 7. ユーザーインターフェース (ui/)
- コマンドラインメニュー
- 結果表示・フォーマット
- 入力処理

## 技術仕様

### 主要技術
- **Google Gemini API**: 文書解析・要約
- **SQLite**: データベース
- **Python**: メイン開発言語
- **uv**: パッケージ管理・仮想環境

### プロジェクト設定 (pyproject.toml)
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "research-data-management"
version = "0.1.0"
description = "Research Data Management System with Google Gemini API"
requires-python = ">=3.9"
dependencies = [
    "google-generativeai>=0.3.0",
    "pandas>=2.0.0",
    "PyPDF2>=3.0.0",
    "scikit-learn>=1.3.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "ruff>=0.1.0",
    "mypy>=1.0.0",
]

[project.scripts]
research-manager = "agent.main:main"

[tool.ruff]
line-length = 100
target-version = "py39"

[tool.pytest.ini_options]
testpaths = ["agent/tests"]
python_files = "test_*.py"
python_classes = "Test*"
python_functions = "test_*"
環境変数設定 (.env)
# Google Gemini API設定
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-1.5-pro

# データベース設定
DATABASE_PATH=agent/database/research_data.db

# データディレクトリ設定
DATA_DIR_PATH=data

# アプリケーション設定
LOG_LEVEL=INFO
MAX_FILE_SIZE_MB=100
SUPPORTED_EXTENSIONS=pdf,csv,json,jsonl
環境変数サンプル (.env.example)
# Google Gemini API設定
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-pro

# データベース設定
DATABASE_PATH=agent/database/research_data.db

# データディレクトリ設定
DATA_DIR_PATH=data

# アプリケーション設定
LOG_LEVEL=INFO
MAX_FILE_SIZE_MB=100
SUPPORTED_EXTENSIONS=pdf,csv,json,jsonl
データベース設計
sql-- files テーブル
CREATE TABLE files (
    id INTEGER PRIMARY KEY,
    file_path TEXT UNIQUE,
    file_name TEXT,
    file_type TEXT,
    category TEXT,  -- 'paper', 'poster', 'dataset'
    file_size INTEGER,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    indexed_at TIMESTAMP,
    summary TEXT,
    metadata TEXT,
    content_hash TEXT
);

-- research_topics テーブル
CREATE TABLE research_topics (
    id INTEGER PRIMARY KEY,
    file_id INTEGER,
    topic TEXT,
    relevance_score REAL,
    keywords TEXT,
    FOREIGN KEY (file_id) REFERENCES files (id)
);

-- analysis_results テーブル
CREATE TABLE analysis_results (
    id INTEGER PRIMARY KEY,
    file_id INTEGER,
    analysis_type TEXT,
    result_data TEXT,
    created_at TIMESTAMP,
    FOREIGN KEY (file_id) REFERENCES files (id)
);
メインアプリケーション機能 (agent/main.py)
コマンドラインインターフェース：

データインデックス作成/更新
ファイル検索・表示
新規データ登録
データ管理（更新・削除）
研究相談
統計情報表示
設定管理

Google Gemini API仕様

.envファイルでAPI_KEY管理
モデル: gemini-1.5-pro
レスポンス形式: JSON構造化出力
エラーハンドリング・リトライ機能
レート制限対応

完了条件（README.mdに記載）

SQLiteデータベースが正常に作成され、dataディレクトリの全ファイルがインデックス化されること
Google Gemini APIを使用した文書解析・要約機能が動作すること
メインメニューから全機能（データ検索、登録、管理、研究相談、統計）にアクセスできること
研究相談機能でデータセット・論文・ポスターの推薦が正常に動作すること
pytestを使ってテストカバレッジを80%以上にすること
関連ドキュメント（README.md、API仕様書）の作成完了

重要: 上記の全条件が満たされた場合のみ、コードレビューで完結とする
設計方針

各ファイルは適切な規模で実装（100行程度を目安とするが、機能が複雑な場合は柔軟に対応）
モジュール間の疎結合を重視
エラーハンドリングを適切に実装
日本語コメント・ドキュメントを含める
テスト駆動開発でテストカバレッジ80%以上

実装手順

プロジェクト初期化
bashuv init research-data-management
cd research-data-management

環境設定（.env, config.py, pyproject.toml）
プロジェクト構造作成
データベース設計・実装
各機能モジュール実装（適切なファイル分割で）
メインアプリケーション実装
テストコード作成・実行
ドキュメント作成
統合テスト・動作確認

uv コマンド例
bash# プロジェクト初期化
uv init research-data-management
cd research-data-management

# 環境設定
cp .env.example .env
# .envファイルを編集してAPI_KEYを設定

# 依存関係インストール
uv sync

# 開発用依存関係インストール
uv sync --dev

# 実行
uv run python agent/main.py

# テスト実行
uv run pytest agent/tests/ --cov=agent/source --cov-report=html

# コードフォーマット・リント
uv run ruff check agent/
uv run ruff format agent/

# 型チェック
uv run mypy agent/
注意点

Google Gemini APIキーの適切な管理
大量ファイル処理時のメモリ使用量
日本語文書の文字エンコーディング
API制限・エラー時の適切な処理
uvの仮想環境を適切に使用


実装開始: 上記仕様に従って、uvを使用したResearch Data Management Systemの実装を開始してください。機能別にモジュールを適切に分割し、保守性の高いコードベースを構築してください。