# 研究データ基盤システム

ローカルデータベースベースの研究データ管理・検索・相談システムです。Google Gemini APIを活用した高度なデータ解析機能を提供します。

## 🚀 主な機能

### データ基盤機能
- **データ蓄積**: 研究データの自動インデックス化とメタデータ抽出
- **データ管理**: データの検索、更新、削除、エクスポート
- **ファイル処理**: PDF、JSON、テキストファイルの自動解析
- **全文検索**: 高速な検索とフィルタリング

### 研究相談機能
- **AI相談**: Google Gemini APIによる研究相談とアドバイス
- **データ推薦**: ユーザーのニーズに基づくデータ推薦
- **類似検索**: 関連データの自動検出
- **トレンド分析**: 研究分野のトレンド分析

### API機能
- **REST API**: データ操作、検索、アップロード
- **Web UI**: ブラウザからのアクセス
- **CLI**: コマンドライン操作

## 📁 システム構成

```
agent/
├── main.py                    # メインシステム
├── config.py                  # 設定管理
├── database_handler.py        # データベース操作
├── data_manager.py           # データ管理
├── file_processor.py         # ファイル処理
├── metadata_extractor.py     # メタデータ抽出
├── search_engine.py          # 検索エンジン
├── api/                      # API層
│   ├── data_api.py           # データ操作API
│   ├── search_api.py         # 検索API
│   └── upload_api.py         # アップロードAPI
├── consultation/             # 研究相談機能
│   ├── advisor.py            # AI相談
│   └── recommender.py        # データ推薦
├── database/                 # データベース
│   └── research_data.db      # SQLiteデータベース
└── source/                   # ソースファイル
    └── uploads/              # アップロードファイル
```

## 🛠️ セットアップ

### 1. 依存関係のインストール

```bash
pip install -r agent/requirements.txt
```

### 2. Google Gemini API設定

環境変数でAPIキーを設定：

```bash
export GEMINI_API_KEY="your_gemini_api_key_here"
```

または `.env` ファイルを作成：

```bash
# .env
GEMINI_API_KEY=your_gemini_api_key_here
```

### 3. Google Gemini APIキーの取得手順

1. [Google AI Studio](https://makersuite.google.com/) にアクセス
2. Googleアカウントでログイン
3. 「Get API key」をクリック
4. 新しいAPIキーを作成
5. 取得したAPIキーを環境変数に設定

### 4. 初期データの登録

既存の `data/` ディレクトリがある場合、自動的にインデックス化：

```bash
# CLIモードで起動（初期化あり）
python -m agent.main

# または直接初期化
python -m agent.main init data/
```

## 💻 使用方法

### CLIモード

```bash
python -m agent.main
```

メニューから機能を選択：
1. データを探す
2. データを登録する  
3. データを管理する
4. 研究相談をする
5. システム統計を見る

### Webサーバーモード

```bash
python -m agent.main web
```

ブラウザで `http://localhost:5000` にアクセス

### 設定確認

```bash
python -m agent.main config
```

## 🔌 API仕様

### データ操作API

- `POST /api/data` - データ登録
- `GET /api/data/{data_id}` - データ取得
- `PUT /api/data/{data_id}` - データ更新
- `DELETE /api/data/{data_id}` - データ削除
- `POST /api/data/batch` - 一括登録
- `POST /api/data/export` - データエクスポート

### 検索API

- `GET /api/search` - データ検索
- `GET /api/search/similar/{data_id}` - 類似検索
- `GET /api/search/trending` - トレンド取得
- `POST /api/search/advanced` - 高度な検索

### アップロードAPI

- `POST /api/upload` - ファイルアップロード
- `POST /api/upload/multiple` - 複数ファイルアップロード
- `POST /api/upload/url` - URLからダウンロード

### 相談・推薦API

- `POST /api/consultation` - 研究相談
- `GET /api/recommendations` - データ推薦

## 📊 データベース仕様

### SQLiteテーブル構造

```sql
-- 研究データテーブル
CREATE TABLE research_data (
    data_id TEXT PRIMARY KEY,
    data_type TEXT NOT NULL,          -- dataset, paper, poster
    title TEXT NOT NULL,
    summary TEXT,
    research_field TEXT,
    created_date TEXT,
    file_path TEXT,
    metadata TEXT,                    -- JSON形式
    indexed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 検索履歴テーブル  
CREATE TABLE search_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
);
```

## 🔍 検索機能

### 基本検索

```bash
# キーワード検索
curl "http://localhost:5000/api/search?query=機械学習"

# フィルタ検索
curl "http://localhost:5000/api/search?data_type=dataset&research_field=自然言語処理"
```

### 高度な検索

- フレーズ検索: `"機械学習 データセット"`
- 検索演算子: `AND`, `OR`, `NOT`
- ファセット検索: データタイプ・研究分野での絞り込み
- ソート: 関連度、更新日、タイトル

## 🤖 研究相談機能

### 相談タイプ

1. **データセット相談**: 研究に適したデータセットの推薦
2. **研究アイデア相談**: 論文・ポスターの推薦と関連研究の提案
3. **一般相談**: 研究全般についてのアドバイス

### 相談例

```bash
curl -X POST http://localhost:5000/api/consultation \
  -H "Content-Type: application/json" \
  -d '{"query": "自然言語処理のデータセットを探しています", "type": "dataset"}'
```

## 📈 推薦機能

### 推薦タイプ

- **類似ベース**: 既存データとの類似性による推薦
- **分野ベース**: 研究分野での推薦
- **タイプベース**: データタイプでの推薦
- **トレンドベース**: 最近注目されているデータの推薦
- **協調フィルタリング**: ユーザーの履歴に基づく推薦

## 🧪 テスト

### テストの実行

```bash
# 全テストの実行
pytest agent/tests/

# カバレッジ付きテスト
pytest --cov=agent --cov-report=html

# 特定テストの実行
pytest agent/tests/test_database.py
```

### テストカバレッジ目標

- **全体カバレッジ**: 80%以上
- **コア機能**: 90%以上
- **API機能**: 85%以上

## ⚙️ 設定

### 環境変数

| 変数名 | 説明 | デフォルト値 |
|--------|------|-------------|
| `GEMINI_API_KEY` | Google Gemini APIキー | - |
| `RESEARCH_DB_PATH` | データベースファイルパス | `agent/database/research_data.db` |
| `API_HOST` | APIサーバーホスト | `0.0.0.0` |
| `API_PORT` | APIサーバーポート | `5000` |
| `MAX_FILE_SIZE` | 最大ファイルサイズ(bytes) | `52428800` (50MB) |
| `UPLOAD_FOLDER` | アップロード先フォルダ | `agent/source/uploads` |

## 🔒 セキュリティ

- APIキーの環境変数管理
- ファイルアップロードの制限
- SQLインジェクション対策
- ファイル拡張子チェック

## 📝 開発

### コード品質

```bash
# フォーマット
black agent/

# リント
flake8 agent/

# 型チェック
mypy agent/
```

### 新機能追加

1. 適切なモジュールに機能を実装
2. テストを作成
3. APIエンドポイントを追加（必要に応じて）
4. ドキュメントを更新

## ✅ 完了条件

### システム動作確認

1. **データベース作成**: SQLiteデータベースが正常に作成される
2. **データインデックス化**: `data/` ディレクトリの全ファイルがインデックス化される
3. **Gemini API**: 文書解析・要約機能が動作する
4. **メインメニュー**: 全機能（検索、登録、管理、相談、統計）にアクセス可能
5. **研究相談**: データセット・論文・ポスターの推薦が正常動作
6. **テストカバレッジ**: 80%以上のテストカバレッジ

### 確認コマンド

```bash
# システム起動テスト
python -m agent.main config

# データ初期化テスト
python -m agent.main init data/

# Webサーバーテスト
python -m agent.main web

# API動作テスト
curl http://localhost:5000/api/system/status

# テスト実行
pytest --cov=agent
```

## 🆘 トラブルシューティング

### よくある問題

1. **Gemini APIエラー**: APIキーの設定を確認
2. **データベースエラー**: 権限とディスクスペースを確認
3. **ファイルアップロードエラー**: ファイルサイズと拡張子を確認
4. **検索結果が空**: データが正常にインデックス化されているか確認

### ログ確認

```bash
# システムログ
tail -f agent/logs/system.log

# エラーログ
grep ERROR agent/logs/system.log
```

## 📞 サポート

- 技術的な問題: システムログを確認
- 機能要望: GitHubのIssueを作成
- 設定変更: `agent/config.py` を編集

---

**注意**: このシステムはローカル環境での利用を想定しています。本番環境での利用時は、セキュリティ設定を追加で検討してください。