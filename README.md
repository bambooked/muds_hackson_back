# Research Data Management System

Google Gemini APIを使用して研究データ（論文、ポスター、データセット）を管理・解析する完全LLM駆動の研究支援システムです。

## 主要機能

- **完全LLM駆動チャットインターフェース**: すべての応答をAIが動的生成（ハードコーディングなし）
- **カテゴリー別データ管理**: データセット、論文、ポスターを個別のテーブルで管理
- **自動ファイル解析**: 新規ファイル登録時にGoogle Gemini APIで自動解析・要約
- **データセット単位管理**: ディレクトリごとにデータセットとして管理（現在4データセット対応）
- **高度な検索機能**: 日本語対応のキーワード抽出とTF-IDF検索の統合
- **データベース検索・相談**: 登録済みリソースの検索と具体的な活用方法の提案
- **研究計画・相談**: 研究テーマの構造化、計画立案、方法論の支援
- **統計情報**: ファイル統計、解析率、カテゴリー別レポート
- **データ管理**: ファイル操作、メタデータ編集、重複防止機能

## プロジェクト構造

```
.
├── data/                      # 研究データディレクトリ
│   ├── datasets/             # CSV, JSON, JSONL ファイル（4データセット）
│   │   ├── esg/             # ESG関連データ（19ファイル、247MB）
│   │   ├── greendata/       # 環境排出量データ（2ファイル、1.6MB）
│   │   ├── jbbq/            # バイアス研究データ（5ファイル、44MB）
│   │   └── tv_efect/        # TV効果データ（2ファイル、0.2MB）
│   ├── paper/               # 論文PDFファイル（2件）
│   └── poster/              # ポスターPDFファイル（2件）
├── agent/
│   ├── source/
│   │   ├── database/        # データベース関連（新構造）
│   │   │   ├── connection.py    # データベース接続管理
│   │   │   ├── new_models.py    # 新データモデル
│   │   │   └── new_repository.py # 新リポジトリクラス
│   │   ├── indexer/         # ファイルインデックス機能
│   │   │   ├── new_indexer.py   # 新インデクサー（重複防止対応）
│   │   │   └── scanner.py       # ファイルスキャナー
│   │   ├── analyzer/        # Google Gemini API文書解析
│   │   │   ├── new_analyzer.py  # 新アナライザー
│   │   │   ├── gemini_client.py # Gemini APIクライアント（拡張版）
│   │   │   └── file_analyzer.py # ファイル解析（pypdf対応）
│   │   ├── advisor/         # 研究支援機能（拡張）
│   │   │   ├── enhanced_research_advisor.py # 拡張研究相談
│   │   │   ├── dataset_advisor.py # データセット解説
│   │   │   ├── research_visualizer.py # 研究構造化
│   │   │   └── research_advisor.py # 基本研究相談
│   │   ├── statistics/      # 統計情報生成
│   │   └── ui/             # ユーザーインターフェース
│   │       └── interface.py    # メインUI（完全LLM統合）
│   ├── database/
│   │   └── research_data.db # SQLiteデータベース（新構造）
│   ├── tests/              # テストファイル群
│   └── main.py            # メインアプリケーション
├── config.py              # 設定管理
├── .env                   # 環境変数設定
├── .env.example          # 環境変数のサンプル
├── pyproject.toml        # プロジェクト設定
├── CLAUDE.md             # プロジェクト実行指示書
└── README.md            # このファイル
```

## セットアップ

### 1. 環境変数の設定

.envファイルを編集してGoogle Gemini APIキーを設定:

```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-pro
DATABASE_PATH=agent/database/research_data.db
DATA_DIR_PATH=data
LOG_LEVEL=INFO
MAX_FILE_SIZE_MB=100
SUPPORTED_EXTENSIONS=pdf,csv,json,jsonl
```

### 2. 依存関係のインストール

#### uvを使用（推奨）

```bash
# プロジェクト依存関係をインストール
uv sync

# 開発用依存関係も含めてインストール
uv sync --dev
```

#### pipを使用

```bash
pip install google-generativeai pandas pypdf pycryptodome scikit-learn python-dotenv pytest
```

### 3. データディレクトリの準備

```bash
mkdir -p data/{datasets,paper,poster}
```

研究ファイルを適切なディレクトリに配置:
- 論文PDF → `data/paper/`
- ポスターPDF → `data/poster/`  
- データファイル → `data/datasets/` （データセット名のサブディレクトリに分類）

## 使用方法

### メインアプリケーションの起動

```bash
# Python直接実行
python agent/main.py

# uvを使用
uv run python agent/main.py
```

### メニュー操作

1. **データ更新**: ファイルをスキャンしてカテゴリー別テーブルに登録・自動解析
2. **データベース検索・相談**: 登録済みリソースの検索と活用支援（LLMチャット形式）
   - データセット・論文・ポスターの検索
   - 見つかったリソースの詳細解説
   - 具体的な活用方法とデータ分析手法の提案
3. **研究計画・相談**: 研究活動の計画立案と方法論支援（LLMチャット形式）
   - 研究テーマの構造化・可視化
   - 研究計画の段階的立案
   - 研究方法論の選択支援
   - 独創性評価と学術的価値の検討
4. **データ管理**: ファイル操作、メタデータ編集、重複防止
5. **統計情報**: カテゴリー別統計、解析率の表示
0. **設定**: 現在の設定の確認

### コマンドライン使用例

```bash
# データベース初期化とインデックス作成（新構造）
python -c "
from agent.source.ui.interface import UserInterface
ui = UserInterface()
ui.update_index()
"

# 解析統計確認
python -c "
from agent.source.ui.interface import UserInterface
ui = UserInterface()
summary = ui.analyzer.get_analysis_summary()
for category, stats in summary.items():
    print(f'{category}: {stats[\"analyzed\"]}/{stats[\"total\"]} ({stats[\"rate\"]})')
"
```

## 現在のシステム状況

### データベース構造（新設計）

現在は新しいカテゴリー別テーブル構造を使用:

#### datasetsテーブル
```sql
CREATE TABLE datasets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    file_count INTEGER DEFAULT 0,
    total_size INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    summary TEXT
);
```

#### papersテーブル
```sql
CREATE TABLE papers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT UNIQUE NOT NULL,
    file_name TEXT NOT NULL,
    file_size INTEGER,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    title TEXT,
    authors TEXT,
    abstract TEXT,
    keywords TEXT,
    content_hash TEXT
);
```

#### postersテーブル
```sql
CREATE TABLE posters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT UNIQUE NOT NULL,
    file_name TEXT NOT NULL,
    file_size INTEGER,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    title TEXT,
    authors TEXT,
    abstract TEXT,
    keywords TEXT,
    content_hash TEXT
);
```

#### dataset_filesテーブル
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

### 現在の統計（2025年7月4日更新）

実際のシステム統計:
- **総ファイル数**: 34件（全て登録・解析済み）
- **データセット**: 4個（100%解析済み）
- **論文**: 3件（100%解析済み）
- **ポスター**: 3件（100%解析済み）
- **データセットファイル**: 28件
- **合計サイズ**: 約293MB

### データセット詳細

| データセット | ファイル数 | サイズ | 要約 |
|-------------|-----------|--------|------|
| **esg** | 19ファイル | 247.22MB | このデータセットは、企業のサステナビリティに関する情報をまとめたもの... |
| **greendata** | 2ファイル | 1.65MB | このデータセットは、米国にある施設の環境排出量に関する情報を提供... |
| **jbbq** | 5ファイル | 43.99MB | このデータセットは、jbbqと名付けられ、社会におけるバイアスを反映した質問応答ペア... |
| **tv_efect** | 2ファイル | 0.17MB | このデータセットは、テレビCMの効果と視聴率の関係性を分析するために作成... |

### 論文・ポスター詳細

**論文（3件）**:
- `2322007.pdf`: 日本語の大規模言語モデル (LLM) における社会的なバイアスを分析...
- `5A-02.pdf`: Latent Dirichlet Allocation (LDA) を用いた自動タグ付け手法...
- `main-j.pdf`: PC作業中のまばたきを検出・分析し、UI/UXの改善に役立てる研究...

**ポスター（3件）**:
- `2322039.pdf`: LDAとLLMを用いた単一文書への新規タグ付け手法を提案...
- `2322007.pdf`: 大規模言語モデル(LLM)の出力におけるステレオタイプ的バイアスの低減...
- `5A-03.pdf`: 文書の自動タグ付け手法に関する研究...

## テスト

### テストの実行

```bash
# 全テストを実行
python -m pytest agent/tests/ -v

# uvを使用
uv run pytest agent/tests/ -v

# カバレッジ付きでテスト実行
python -m pytest agent/tests/ --cov=agent/source --cov-report=html
```

**注意**: 一部のテストは旧データベース構造を対象としているため、現在は新構造への移行完了を優先しています。

## 設定

### 環境変数

| 変数名 | 説明 | デフォルト値 |
|--------|------|-------------|
| `GEMINI_API_KEY` | Google Gemini APIキー | 必須 |
| `GEMINI_MODEL` | 使用するGeminiモデル | `gemini-1.5-pro` |
| `DATABASE_PATH` | データベースファイルパス | `agent/database/research_data.db` |
| `DATA_DIR_PATH` | データディレクトリパス | `data` |
| `LOG_LEVEL` | ログレベル | `INFO` |
| `MAX_FILE_SIZE_MB` | 最大ファイルサイズ(MB) | `100` |
| `SUPPORTED_EXTENSIONS` | サポートする拡張子 | `pdf,csv,json,jsonl` |

### Google Gemini API設定

1. [Google AI Studio](https://makersuite.google.com/app/apikey)でAPIキーを取得
2. `.env`ファイルに設定
3. API利用制限に注意

## 特徴的な機能

### 1. 完全LLM駆動チャットインターフェース
- すべての応答をGoogle Gemini APIが動的生成
- ハードコーディングされた応答を完全排除
- 継続的対話による深い研究支援

### 2. 高度な検索機能
- 日本語対応のキーワード抽出（助詞・動詞を適切に処理）
- TF-IDF検索とキーワード検索の統合
- 既存研究データベースを確実に参照・活用

### 3. 専門化された支援モード
- **データベース検索・相談**: 登録済みリソースの検索と活用に特化
- **研究計画・相談**: 研究テーマの構造化と計画立案に特化
- 各モードで最適化されたLLMプロンプト

### 4. 自動解析機能
- ファイル登録時に自動的にGoogle Gemini APIで解析
- データセットは「このデータセットは～」形式で要約生成
- 論文・ポスターはタイトル、著者、要約を抽出

### 5. データ品質管理
- 同一ファイル名の重複登録を防止
- content_hashによる内容重複検出
- カテゴリー別の最適化されたテーブル構造

## トラブルシューティング

### よくある問題

**1. ModuleNotFoundError**
```bash
# 依存関係を再インストール
uv sync
# または
pip install google-generativeai pandas pypdf pycryptodome scikit-learn python-dotenv pytest
```

**2. Google Gemini APIエラー**
- APIキーが正しく設定されているか確認
- API利用制限を確認
- ネットワーク接続を確認

**3. データベースエラー**
```bash
# データベースを再初期化（新構造）
rm -f agent/database/research_data.db
python -c "from agent.source.database.connection import db_connection; db_connection.initialize_database()"
```

**4. 解析がスキップされる場合**
- 既に解析済みのファイルは再解析されません
- 強制的に再解析したい場合は、メニューの「ファイル解析」機能を使用

## 完了条件（達成済み）

- ✅ SQLiteデータベースが正常に作成され、dataディレクトリの全ファイルがインデックス化される
- ✅ Google Gemini APIを使用した文書解析・要約機能が動作する
- ✅ データセット要約が「このデータセットは～」形式で生成される
- ✅ カテゴリー別テーブル構造（datasets、papers、posters）が実装される
- ✅ 自動解析機能が正常に動作する
- ✅ メインメニューから全機能にアクセスできる
- ✅ 研究相談機能が動作する
- ✅ 全てのファイルが解析済み（100%解析率）
- ✅ 完全LLM駆動のチャットインターフェース実装
- ✅ 日本語対応の高度な検索機能実装
- ✅ データベース参照機能の強化
- ✅ 専門化された支援モードの実装

## 技術仕様

- **言語**: Python 3.11+
- **パッケージ管理**: uv（推奨）またはpip
- **データベース**: SQLite（新カテゴリー別構造）
- **AI API**: Google Gemini 1.5 Pro
- **テストフレームワーク**: pytest
- **対応ファイル形式**: PDF, CSV, JSON, JSONL

## 関連リンク

- [Google Gemini API Documentation](https://ai.google.dev/)
- [uv Documentation](https://docs.astral.sh/uv/)
- [pypdf Documentation](https://pypdf.readthedocs.io/)
- [scikit-learn Documentation](https://scikit-learn.org/)
- [SQLite Documentation](https://www.sqlite.org/docs.html)

## 更新履歴

- **2025年7月4日**: 完全LLM駆動チャットインターフェース実装、検索機能改善、データベース参照強化
- **2025年7月4日**: PyPDF2からpypdfへ移行、重複ファイル対策実装
- **2025年7月1日**: カテゴリー別データベース構造実装、拡張研究支援機能追加