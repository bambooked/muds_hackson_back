# Claude Code 実行指示書

## プロジェクト名
Research Data Management System

## プロジェクト概要
dataディレクトリ内の研究データ（論文、ポスター、データセット）を管理・要約するシステムです。Google Gemini APIを使用して文書を自動解析し、カテゴリー別のデータベース構造で効率的に管理します。

## 現在のシステム状況（2025年7月1日更新）

### 実装済み機能
- ✅ **新データベース構造**: カテゴリー別テーブル（datasets、papers、posters、dataset_files）
- ✅ **自動ファイル解析**: 登録時にGoogle Gemini APIで自動解析
- ✅ **データセット単位管理**: ディレクトリごとにデータセットとして管理
- ✅ **要約形式統一**: データセット要約を「このデータセットは～」形式で生成
- ✅ **完全解析**: 全32ファイルが100%解析済み
- ✅ **カテゴリー別UI**: 検索、解析、統計機能がカテゴリー別に対応

### 現在のデータ状況
```
総ファイル数: 32件（全て解析済み）
├── データセット: 4個（100%解析済み）
│   ├── esg: 19ファイル (247.22MB) - 企業サステナビリティ
│   ├── greendata: 2ファイル (1.65MB) - 環境排出量データ
│   ├── jbbq: 5ファイル (43.99MB) - バイアス研究データ
│   └── tv_efect: 2ファイル (0.17MB) - TV効果データ
├── 論文: 2件（100%解析済み）
│   ├── 2322007.pdf - 日本語LLMバイアス分析
│   └── 5A-02.pdf - LDAタグ付け手法
└── ポスター: 2件（100%解析済み）
    ├── 2322039.pdf - LDA/LLMタグ付け提案
    └── 2322007.pdf - LLMバイアス低減
```

## 現在のディレクトリ構造
```
.
├── data/                          # 研究データディレクトリ
│   ├── datasets/                 # データセット（4個）
│   │   ├── esg/                 # ESG関連（19ファイル）
│   │   ├── greendata/           # 環境データ（2ファイル）
│   │   ├── jbbq/                # バイアス研究（5ファイル）
│   │   └── tv_efect/            # TV効果（2ファイル）
│   ├── paper/                   # 論文PDF（2件）
│   └── poster/                  # ポスターPDF（2件）
├── agent/
│   ├── source/
│   │   ├── database/            # データベース関連（新構造）
│   │   │   ├── connection.py        # 接続管理
│   │   │   ├── new_models.py        # 新データモデル ✅
│   │   │   └── new_repository.py    # 新リポジトリ ✅
│   │   ├── indexer/             # ファイルインデックス機能
│   │   │   ├── new_indexer.py       # 新インデクサー ✅
│   │   │   └── scanner.py           # ファイルスキャナー
│   │   ├── analyzer/            # Google Gemini API文書解析
│   │   │   ├── new_analyzer.py      # 新アナライザー ✅
│   │   │   ├── gemini_client.py     # Gemini APIクライアント
│   │   │   └── file_analyzer.py     # ファイル解析
│   │   ├── manager/             # データ管理・検索（旧構造）
│   │   ├── advisor/             # 研究相談・推薦機能（旧構造）
│   │   ├── statistics/          # 統計情報生成（旧構造）
│   │   └── ui/                 # ユーザーインターフェース
│   │       └── interface.py         # メインUI（新構造対応済み） ✅
│   ├── database/
│   │   └── research_data.db    # SQLiteデータベース（新構造）
│   ├── tests/                  # テストファイル群（旧構造）
│   └── main.py                # メインアプリケーション
├── config.py                  # 設定管理
├── .env                      # 環境変数設定
├── .env.example             # 環境変数のサンプル
├── pyproject.toml          # uv プロジェクト設定
├── README.md              # プロジェクト説明（更新済み）
└── CLAUDE.md             # このファイル
```

## 新データベース設計（実装済み）

### datasetsテーブル
```sql
CREATE TABLE datasets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,            -- データセット名
    description TEXT,                     -- 説明
    file_count INTEGER DEFAULT 0,         -- ファイル数
    total_size INTEGER DEFAULT 0,         -- 総サイズ
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    summary TEXT                          -- Gemini生成要約（「このデータセットは～」形式）
);
```

### papersテーブル
```sql
CREATE TABLE papers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT UNIQUE NOT NULL,
    file_name TEXT NOT NULL,
    file_size INTEGER,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    title TEXT,                           -- Gemini抽出タイトル
    authors TEXT,                         -- Gemini抽出著者
    abstract TEXT,                        -- Gemini生成要約
    keywords TEXT,                        -- Gemini抽出キーワード
    content_hash TEXT
);
```

### postersテーブル
```sql
CREATE TABLE posters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT UNIQUE NOT NULL,
    file_name TEXT NOT NULL,
    file_size INTEGER,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    title TEXT,                           -- Gemini抽出タイトル
    authors TEXT,                         -- Gemini抽出著者
    abstract TEXT,                        -- Gemini生成要約
    keywords TEXT,                        -- Gemini抽出キーワード
    content_hash TEXT
);
```

### dataset_filesテーブル
```sql
CREATE TABLE dataset_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id INTEGER NOT NULL,
    file_path TEXT UNIQUE NOT NULL,
    file_name TEXT NOT NULL,
    file_type TEXT,
    file_size INTEGER,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    content_hash TEXT,
    FOREIGN KEY (dataset_id) REFERENCES datasets (id)
);
```

## 技術仕様

### 主要技術
- **Google Gemini API**: 文書解析・要約（gemini-1.5-pro）
- **SQLite**: データベース（新カテゴリー別構造）
- **Python 3.11+**: メイン開発言語
- **uv**: パッケージ管理・仮想環境

### 依存関係 (pyproject.toml)
```toml
[project]
name = "research-data-management"
version = "0.1.0"
description = "Research Data Management System with Google Gemini API"
requires-python = ">=3.11"
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
```

## 環境変数設定 (.env)
```env
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
```

## メインアプリケーション機能 (agent/main.py)

### 実装済みメニュー機能
1. **データインデックスの更新**: 
   - 新インデクサー（NewFileIndexer）使用
   - カテゴリー別自動登録・解析
   - 100%自動解析完了済み

2. **ファイル検索**: 
   - カテゴリー別検索（データセット/論文/ポスター）
   - キーワード検索対応
   - 新UI（interface.py）で実装済み

3. **ファイル解析**: 
   - カテゴリー別解析選択
   - 個別解析・一括解析
   - 新アナライザー（NewFileAnalyzer）使用

4. **研究相談**: 
   - 簡易キーワードベース検索
   - 関連文書推薦機能

5. **統計情報表示**: 
   - カテゴリー別統計
   - 解析率表示
   - 全体概要表示

6. **データ管理**: 
   - カテゴリー別削除機能
   - メタデータ更新
   - エクスポート機能

7. **設定**: 現在設定の表示

## Google Gemini API仕様

### データセット解析プロンプト
```
重要: summaryは必ず「このデータセットは」で始めてください。

以下の形式で返してください:
{
    "summary": "このデータセットは[データセット全体の内容・目的・特徴を総合的に説明]。（300文字以内）",
    "main_purpose": "データセットの主な目的",
    "data_types": ["データタイプ1", "データタイプ2", ...],
    "research_domains": ["研究領域1", "研究領域2", ...],
    "key_features": ["特徴1", "特徴2", ...],
    "potential_applications": ["応用例1", "応用例2", ...],
    "file_descriptions": {"ファイル名": "説明", ...}
}
```

### 論文・ポスター解析プロンプト
```
以下の形式で返してください:
{
    "summary": "文書の要約（200文字以内）",
    "main_topics": ["主要なトピック1", "主要なトピック2", ...],
    "keywords": ["キーワード1", "キーワード2", ...],
    "language": "主要言語（japanese/english）",
    "document_type": "文書タイプ（paper/poster/report/other）",
    "research_field": "研究分野",
    "key_findings": ["主要な発見1", "主要な発見2", ...]
}
```

## 完了条件（全て達成済み）

### ✅ 基本機能
- SQLiteデータベースが正常に作成され、dataディレクトリの全ファイルがインデックス化されること
- Google Gemini APIを使用した文書解析・要約機能が動作すること
- メインメニューから全機能（データ検索、登録、管理、研究相談、統計）にアクセスできること

### ✅ 新要件達成
- データベース構造をカテゴリー別テーブル（datasets、papers、posters）に分離
- データセット解析の出力形式を「このデータセットは～」に統一
- ファイル解析の自動実行機能
- データセット単位でのファイル管理（4データセット対応）

### ✅ 解析完了状況
- データセット: 4/4 (100%) 解析済み
- 論文: 2/2 (100%) 解析済み  
- ポスター: 2/2 (100%) 解析済み
- 全ファイル: 32/32 (100%) 登録・解析済み

## 実行コマンド例

### uvを使用（推奨）
```bash
# 環境セットアップ
uv sync --dev

# アプリケーション実行
uv run python agent/main.py

# テスト実行（一部旧構造のため要更新）
uv run pytest agent/tests/ --cov=agent/source --cov-report=html

# コードフォーマット・リント
uv run ruff check agent/
uv run ruff format agent/

# 型チェック
uv run mypy agent/
```

### 直接実行例
```bash
# インデックス更新
python -c "
from agent.source.ui.interface import UserInterface
ui = UserInterface()
ui.update_index()
"

# 統計確認
python -c "
from agent.source.ui.interface import UserInterface
ui = UserInterface()
summary = ui.analyzer.get_analysis_summary()
for category, stats in summary.items():
    print(f'{category}: {stats[\"analyzed\"]}/{stats[\"total\"]} ({stats[\"rate\"]})')
"
```

## 今後の拡張可能性

### 未実装・改善可能な機能
1. **manager, advisor, statistics モジュール**: 新構造への完全移行
2. **テストスイート**: 新データベース構造に対応したテストケース作成
3. **高度な研究相談機能**: TF-IDF以上の類似度計算
4. **API公開**: RESTful APIインターフェース
5. **Web UI**: フロントエンド実装

### 技術的改善点
1. **エラーハンドリング**: より詳細なエラー処理
2. **パフォーマンス**: 大量ファイル処理の最適化
3. **セキュリティ**: APIキー管理の強化
4. **ロギング**: より詳細なログ出力

## 注意事項

### 重要な実装済み機能
- **自動解析**: ファイル登録時に自動的にGemini APIで解析実行
- **カテゴリー別管理**: データセット、論文、ポスターを別テーブルで管理
- **要約形式統一**: データセット要約は必ず「このデータセットは～」で開始
- **100%解析完了**: 全32ファイルが解析済み

### 保守・運用
- Gemini API制限・エラー時の適切な処理実装済み
- 大量ファイル処理時のメモリ使用量最適化済み
- 日本語文書の文字エンコーディング対応済み
- uvの仮想環境を適切に使用

### データベース状態
現在のデータベースは新構造（カテゴリー別テーブル）で、全データが移行・解析完了済み。旧構造（filesテーブル）は使用されていません。

---

**実装状況**: 新データベース構造への完全移行・自動解析機能・データセット要約形式統一・100%解析完了 ✅

システムは要求仕様を完全に満たしており、実用可能な状態です。