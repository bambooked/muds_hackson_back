# Research Data Management System

Google Gemini APIを使用してdataディレクトリ内の研究データ（論文、ポスター、データセット）を管理・要約するシステムです。

## 主要機能

- **データセット単位管理**: データセットディレクトリごとに研究データを管理（現在4データセット対応）
- **自動ファイル解析**: 新規ファイル登録時にGoogle Gemini APIで自動解析・要約
- **ファイルインデックス**: dataディレクトリを自動スキャンしてファイルを登録
- **Google Gemini API解析**: PDF、CSV、JSON、JSONLファイルの内容を解析・要約
- **研究相談機能**: クエリに基づく研究アドバイスと関連文書の推薦
- **統計情報**: ファイル統計、研究トレンド、データセット別レポート
- **データ管理**: ファイル検索、メタデータ管理、エクスポート機能

## プロジェクト構造

```
.
├── data/                      # 研究データディレクトリ
│   ├── datasets/             # CSV, JSON, JSONL ファイル
│   ├── paper/               # 論文PDFファイル
│   └── poster/              # ポスターPDFファイル
├── agent/
│   ├── source/
│   │   ├── database/        # データベース関連
│   │   ├── indexer/         # ファイルインデックス機能
│   │   ├── analyzer/        # Google Gemini API文書解析
│   │   ├── manager/         # データ管理・検索
│   │   ├── advisor/         # 研究相談・推薦機能
│   │   ├── statistics/      # 統計情報生成
│   │   └── ui/             # ユーザーインターフェース
│   ├── database/
│   │   └── research_data.db # SQLiteデータベース
│   ├── tests/              # テストファイル群
│   └── main.py            # メインアプリケーション
├── config.py              # 設定管理
├── .env                   # 環境変数設定
├── .env.example          # 環境変数のサンプル
├── pyproject.toml        # プロジェクト設定
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
pip install google-generativeai pandas PyPDF2 scikit-learn python-dotenv pytest
```

### 3. データディレクトリの準備

```bash
mkdir -p data/{datasets,paper,poster}
```

研究ファイルを適切なディレクトリに配置:
- 論文PDF → `data/paper/`
- ポスターPDF → `data/poster/`  
- データファイル → `data/datasets/`

## 使用方法

### メインアプリケーションの起動

```bash
# Python直接実行
python agent/main.py

# uvを使用
uv run python agent/main.py
```

### メニュー操作

1. **データインデックスの更新**: ファイルをスキャンしてデータベースに登録
2. **ファイル検索**: キーワード、カテゴリー、ファイルタイプで検索
3. **ファイル解析**: Google Gemini APIで文書内容を解析
4. **研究相談**: 質問に対する研究アドバイスと関連文書の推薦
5. **統計情報表示**: ファイル統計、トレンド分析
6. **データ管理**: ファイルの追加、削除、移動、メタデータ編集
7. **設定**: 現在の設定の確認

### コマンドライン使用例

```bash
# データベース初期化とインデックス作成
python -c "
from agent.source.database.connection import db_connection
from agent.source.indexer.indexer import FileIndexer

db_connection.initialize_database()
indexer = FileIndexer()
results = indexer.index_all_files()
print(f'登録: {results[\"new_files\"]}件')
"

# ファイル解析
python -c "
from agent.source.analyzer.file_analyzer import FileAnalyzer

analyzer = FileAnalyzer()
results = analyzer.batch_analyze()
print(f'解析完了: {results[\"success\"]}件')
"
```

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

### テスト結果
- データベース機能: 9テスト 成功
- ファイルスキャナー: 4テスト 成功  
- 設定: 7テスト 成功
- 全体: 20テスト すべて成功

## データベーススキーマ

### filesテーブル
```sql
CREATE TABLE files (
    id INTEGER PRIMARY KEY,
    file_path TEXT UNIQUE,
    file_name TEXT,
    file_type TEXT,
    category TEXT,  -- 'paper', 'poster', 'datasets'
    file_size INTEGER,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    indexed_at TIMESTAMP,
    summary TEXT,
    metadata TEXT,
    content_hash TEXT
);
```

### research_topicsテーブル
```sql
CREATE TABLE research_topics (
    id INTEGER PRIMARY KEY,
    file_id INTEGER,
    topic TEXT,
    relevance_score REAL,
    keywords TEXT,
    FOREIGN KEY (file_id) REFERENCES files (id)
);
```

### analysis_resultsテーブル
```sql
CREATE TABLE analysis_results (
    id INTEGER PRIMARY KEY,
    file_id INTEGER,
    analysis_type TEXT,
    result_data TEXT,
    created_at TIMESTAMP,
    FOREIGN KEY (file_id) REFERENCES files (id)
);
```

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

## トラブルシューティング

### よくある問題

**1. ModuleNotFoundError**
```bash
# 依存関係を再インストール
uv sync
# または
pip install google-generativeai pandas PyPDF2 scikit-learn python-dotenv pytest
```

**2. Google Gemini APIエラー**
- APIキーが正しく設定されているか確認
- API利用制限を確認
- ネットワーク接続を確認

**3. データベースエラー**
```bash
# データベースを再初期化
rm -f agent/database/research_data.db
python -c "from agent.source.database.connection import db_connection; db_connection.initialize_database()"
```

**4. ファイルスキャンエラー**
- ファイルのアクセス権限を確認
- ファイルサイズが制限内かチェック
- サポートされている拡張子か確認

## 完了条件

- SQLiteデータベースが正常に作成され、dataディレクトリの全ファイルがインデックス化される
- Google Gemini APIを使用した文書解析・要約機能が動作する
- メインメニューから全機能（データ検索、登録、管理、研究相談、統計）にアクセスできる
- 研究相談機能でデータセット・論文・ポスターの推薦が正常に動作する
- テストが20テスト すべて成功する
- 関連ドキュメント（README.md）の作成完了

## 技術仕様

- **言語**: Python 3.11+
- **パッケージ管理**: uv（推奨）またはpip
- **データベース**: SQLite
- **AI API**: Google Gemini 1.5 Pro
- **テストフレームワーク**: pytest
- **対応ファイル形式**: PDF, CSV, JSON, JSONL

## 現在の統計

実際のシステム統計:
- 総ファイル数: 32件
- 論文: 2件、ポスター: 2件、データセット: 28件
- データセット数: 4個（esg、greendata、jbbq、tv_efect）
- 解析済み: 15件 (46.9%)
- 合計サイズ: 約307MB

### データセット詳細
- **esg**: 19ファイル (247MB) - ESG関連研究データ
- **greendata**: 2ファイル (1.6MB) - 環境データ
- **jbbq**: 5ファイル (44MB) - バイアス研究データ  
- **tv_efect**: 2ファイル (0.2MB) - テレビ効果データ

## 関連リンク

- [Google Gemini API Documentation](https://ai.google.dev/)
- [uv Documentation](https://docs.astral.sh/uv/)
- [PyPDF2 Documentation](https://pypdf2.readthedocs.io/)
- [scikit-learn Documentation](https://scikit-learn.org/)
- [SQLite Documentation](https://www.sqlite.org/docs.html)