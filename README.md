# 研究データ管理システム - Webアプリケーション

Google Drive連携 & AI研究相談機能付きWebアプリケーション

## 概要

Google Drive連携とAI（Google Gemini）を活用した研究相談機能を備えた、完全なWebベースの研究データ管理システムです。研究者が論文、ポスター、データセットを効率的に管理し、リアルタイムでAI相談を受けられます。

## 主要機能

### 🌐 **Webアプリケーション**
- **FastAPI**ベースの高性能WebAPI
- **レスポンシブWebUI**: TailwindCSSを使用したモダンなインターフェース
- **リアルタイム同期**: Google Driveとの自動同期機能
- **バックグラウンド処理**: 非同期でのファイル処理

### ☁️ **Google Drive連携**
- **自動ファイル同期**: Google Driveの`data`フォルダから自動インポート
- **サービスアカウント認証**: セキュアなAPI連携
- **フォルダ構造対応**: datasets/paper/posterフォルダの自動識別
- **バックアップ機能**: 自動バックアップ作成とストレージ管理

### 🤖 **AI研究相談**
- **完全LLM駆動**: Google Gemini APIによる動的な研究アドバイス
- **コンテキスト検索**: 既存データベースを参照した的確な助言
- **研究計画支援**: プロジェクト計画から実行まで包括的サポート
- **関連文書提示**: 質問に関連する論文・データセットを自動抽出

### 🔍 **高度な検索機能**
- **統合検索**: 論文、ポスター、データセットを横断検索
- **TF-IDF検索**: 高精度なキーワードマッチング
- **フィルタリング**: カテゴリー別の絞り込み検索
- **リアルタイム結果**: 即座に検索結果を表示

### 📊 **データ管理**
- **自動メタデータ抽出**: ファイルから自動的に情報を抽出
- **統計ダッシュボード**: 登録データの統計情報をリアルタイム表示
- **重複防止**: UNIQUE制約による重複登録防止

## 技術スタック

### バックエンド
- **FastAPI**: 高性能WebAPIフレームワーク
- **SQLite**: 軽量データベース
- **Google APIs**: Drive API, Gemini API
- **scikit-learn**: 機械学習・検索機能

### フロントエンド
- **HTML5/CSS3/JavaScript**: モダンWeb技術
- **TailwindCSS**: ユーティリティファーストCSSフレームワーク
- **Font Awesome**: アイコンライブラリ
- **Jinja2**: テンプレートエンジン

### インフラ・統合
- **Google Drive API**: クラウドストレージ連携
- **OAuth 2.0**: セキュアな認証
- **JWT**: セッション管理
- **uvicorn**: ASGI サーバー

## クイックスタート

### 1. 依存関係のインストール

```bash
# 基本依存関係
pip install -r requirements.txt

# Webアプリ用依存関係  
pip install -r requirements_web.txt
```

### 2. 環境設定

```bash
# 環境変数設定
cp .env.local.example .env

# 必須項目を編集
# GEMINI_API_KEY=your_gemini_api_key
# GOOGLE_DRIVE_CREDENTIALS_PATH=client_secret.json
# GOOGLE_DRIVE_FOLDER_ID=your_folder_id
```

### 3. Google Drive設定

1. [Google Cloud Console](https://console.cloud.google.com/)でサービスアカウント作成
2. Drive APIを有効化
3. サービスアカウントキー（JSON）をダウンロード
4. Google Driveでデータフォルダをサービスアカウントと共有

### 4. Webアプリ起動

```bash
# Webアプリケーション起動
uvicorn web_app:app --host 0.0.0.0 --port 8000 --reload
```

### 5. アクセス

ブラウザで http://localhost:8000 にアクセス

## API エンドポイント

### システム状態
- `GET /api/status` - システム状態確認
- `GET /api/google-drive/status` - Google Drive状態確認

### データ同期
- `POST /api/sync/google-drive` - Google Drive同期実行

### 検索・相談
- `POST /api/search` - 研究データ検索
- `POST /api/consultation` - AI研究相談

## 機能詳細

### Google Drive同期
```javascript
// 同期実行例
{
  "folder_type": "all"  // "all", "papers", "posters", "datasets"
}
```

### AI研究相談
```javascript
// 相談リクエスト例
{
  "query": "機械学習を使ったデータ分析について相談したい",
  "consultation_type": "database"  // "general", "database", "planning"
}
```

### 検索機能
```javascript
// 検索リクエスト例
{
  "query": "深層学習",
  "search_type": "papers"  // "all", "papers", "posters", "datasets"
}
```

## プロジェクト構造

```
muds_hackson_back/
├── web_app.py                 # メインWebアプリケーション
├── templates/
│   └── index.html            # フロントエンドUI
├── agent/source/
│   ├── integrations/         # クラウド連携機能
│   │   ├── google_drive.py   # Google Drive API
│   │   ├── auth.py          # 認証システム
│   │   └── vector_search.py  # ベクトル検索（オプション）
│   ├── database/            # データベース関連
│   ├── advisor/             # AI相談機能
│   └── analyzer/            # ファイル解析
├── .env                     # 環境設定
├── requirements_web.txt     # Web依存関係
└── README.md               # このファイル
```

## 設定オプション

### 基本設定
- `GEMINI_API_KEY`: Google Gemini APIキー（必須）
- `DATABASE_PATH`: SQLiteデータベースパス
- `DATA_DIR_PATH`: ローカルデータディレクトリ

### Google Drive設定
- `ENABLE_GOOGLE_DRIVE`: Google Drive連携有効化
- `GOOGLE_DRIVE_CREDENTIALS_PATH`: 認証ファイルパス
- `GOOGLE_DRIVE_FOLDER_ID`: 対象フォルダID

### パフォーマンス設定
- `CHAT_HISTORY_LIMIT`: チャット履歴保持数
- `MAX_RESPONSE_LENGTH`: AI応答最大長
- `SIMILARITY_THRESHOLD`: 検索類似度閾値

## トラブルシューティング

### Google Drive連携エラー
1. サービスアカウントの権限確認
2. フォルダ共有設定の確認
3. APIキーの有効性確認

### AI相談が動作しない
1. Gemini APIキーの確認
2. ネットワーク接続の確認
3. リクエスト制限の確認

### 検索結果が出ない
1. データベース内容の確認
2. 検索キーワードの確認
3. 同期状態の確認

## ライセンス

研究・教育目的での利用を前提としています。

## 貢献

プルリクエストやイシューの報告を歓迎します。

---

**Google Drive連携 & AI研究相談で、研究データ管理を革新しましょう！** 🚀