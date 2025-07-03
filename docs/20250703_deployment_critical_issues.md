# 学部内データ管理PaaS - デプロイ阻害要因と必須改善課題

## 📋 このドキュメントの目的

このドキュメントは「なぜ」その改善が必要なのかと「何を」実装すべきかを明確にし、
将来のClaude Codeインスタンスが課題の本質を理解できるよう作成されています。

**重要**: 実装方法（HOW）ではなく、問題の本質（WHY）と要求仕様（WHAT）に焦点を当てています。

---

## 🎯 現在のシステムの根本的な問題

### 現状：概念実証（PoC）レベル
- 単一ユーザー・ローカル環境前提
- データの永続性が不安定
- 外部システムとの統合不可
- セキュリティ機能皆無

### 目標：学部内本番環境での運用
- 複数ユーザー同時利用
- Google Drive等外部ストレージ連携
- 永続的なデータ保存・検索
- 適切な認証・認可機能

---

## 🚨 Critical: デプロイ完全阻害要因

### 1. **Input Interface の不在**

#### **WHY この問題が致命的なのか**
- **現状**: ローカルファイルシステムのスキャンのみ対応
- **学部要件**: Google Drive上の分散データを統合管理したい
- **阻害要因**: 外部ストレージからのデータ取り込み手段が皆無

#### **WHAT 実装すべき機能**
```python
# 必要なInput Interface抽象化
class DocumentInputPort(ABC):
    """文書入力の抽象インターフェース"""
    
    @abstractmethod
    async def ingest_from_google_drive(self, folder_id: str) -> IngestionResult:
        """Google Driveフォルダから文書を取り込み"""
        
    @abstractmethod
    async def ingest_from_upload(self, files: List[UploadFile]) -> IngestionResult:
        """ファイルアップロードから文書を取り込み"""
        
    @abstractmethod
    async def get_ingestion_status(self, job_id: str) -> JobStatus:
        """取り込みジョブの進行状況を取得"""
```

#### **現実的制約**
- Google Drive APIの認証・権限設計
- 大容量ファイルの非同期処理
- 重複ファイルの検出・除外

### 2. **ベクトル検索の永続化問題**

#### **WHY この問題が致命的なのか**
- **現状**: SQLiteベースの揮発的検索機能
- **問題**: サーバー再起動のたびにベクトルインデックスが消失
- **学部要件**: 継続的なサービス提供と検索性能の維持
- **阻害要因**: 本番環境でのサービス継続性が保証できない

#### **WHAT 実装すべき機能**
```python
# 必要なVector Search抽象化
class VectorSearchPort(ABC):
    """ベクトル検索の抽象インターフェース"""
    
    @abstractmethod
    async def index_document(self, doc_id: str, content: str, metadata: dict) -> bool:
        """文書をベクトル化してインデックス"""
        
    @abstractmethod
    async def semantic_search(self, query: str, top_k: int) -> List[SearchResult]:
        """セマンティック検索実行"""
        
    @abstractmethod
    async def get_index_stats(self) -> IndexStats:
        """インデックス統計情報取得"""
```

#### **技術選択の根拠**
- **Qdrant**: HTTP API、Docker化容易、永続化対応
- **Chroma**: 組み込み可能、SQLiteより安定
- **pgvector**: PostgreSQL統合、既存データとの親和性

### 3. **認証・認可システムの完全不在**

#### **WHY この問題が致命的なのか**
- **現状**: 誰でも全データにアクセス可能
- **学部要件**: 研究データの適切なアクセス制御
- **法的リスク**: 個人情報・研究機密の漏洩可能性
- **阻害要因**: 本番環境でのセキュリティ要件を満たせない

#### **WHAT 実装すべき機能**
```python
# 必要なAuthentication抽象化
class AuthenticationPort(ABC):
    """認証の抽象インターフェース"""
    
    @abstractmethod
    async def authenticate_university_user(self, credentials: dict) -> Optional[User]:
        """大学アカウントでの認証"""
        
    @abstractmethod
    async def verify_access_permission(self, user: User, resource: str, action: str) -> bool:
        """リソースアクセス権限の確認"""
        
    @abstractmethod
    async def get_user_context(self, token: str) -> Optional[UserContext]:
        """トークンからユーザーコンテキスト取得"""
```

#### **学部固有要件**
- **Google OAuth2統合**: 既存の学部Googleアカウント活用
- **ドメイン制限**: `@university.ac.jp`等の学部ドメインのみ許可
- **役割ベース制御**: 教員・学生・ゲストでのアクセス権分離

---

## ⚠️ High Priority: スケーラビリティ阻害要因

### 4. **データベース層の単一実装依存**

#### **WHY 改善が必要なのか**
- **現状**: SQLite直接依存
- **問題**: 同時アクセス制限、スケールアウト不可
- **将来リスク**: ユーザー増加に対応できない

#### **WHAT 実装すべき抽象化**
```python
class DocumentStoragePort(ABC):
    """文書メタデータ永続化の抽象インターフェース"""
    
    @abstractmethod
    async def save_document(self, document: Document) -> Document:
        """文書メタデータ保存"""
        
    @abstractmethod
    async def find_documents(self, filter: DocumentFilter) -> List[Document]:
        """文書検索（メタデータベース）"""
```

### 5. **設定管理の環境依存**

#### **WHY 改善が必要なのか**
- **現状**: `.env`ファイルとハードコード混在
- **問題**: 環境間での設定差異、秘密情報の管理不備
- **デプロイ阻害**: 本番・ステージング・開発環境の分離不可

#### **WHAT 実装すべき設定体系**
```python
class PaaSConfiguration:
    """環境別設定の抽象化"""
    
    # 接続設定
    google_drive_credentials: GoogleDriveConfig
    vector_search_config: VectorSearchConfig
    database_config: DatabaseConfig
    
    # セキュリティ設定
    authentication_config: AuthConfig
    encryption_keys: EncryptionConfig
    
    # 運用設定
    monitoring_config: MonitoringConfig
    logging_config: LoggingConfig
```

---

## 📊 Medium Priority: 運用阻害要因

### 6. **モニタリング・ロギングの不在**

#### **WHY 必要なのか**
- **問題**: システム障害の原因特定不可
- **運用要件**: 利用状況の把握、パフォーマンス監視
- **改善効果**: 問題の早期発見、サービス品質向上

### 7. **バックアップ・災害復旧の不在**

#### **WHY 必要なのか**
- **リスク**: データ消失による研究活動への深刻な影響
- **学部要件**: 重要な研究データの確実な保護
- **法的要件**: データ保全義務

---

## 🔄 アーキテクチャ改善の方針

### 現在の密結合アーキテクチャ
```
UserInterface → [直接依存] → NewFileIndexer → SQLite
             → [直接依存] → NewFileAnalyzer → GeminiClient
             → [直接依存] → Repositories → ローカルファイル
```

### 目標：疎結合アーキテクチャ
```
PaaS API → RAGService → [Port/Adapter] → 実装選択可能
                     → DocumentInputPort → GoogleDrive/Upload
                     → VectorSearchPort → Qdrant/Chroma
                     → AuthenticationPort → GoogleOAuth2
                     → DocumentStoragePort → PostgreSQL/SQLite
```

### アーキテクチャ改善の効果
1. **実装の交換可能性**: ベンダーロックイン回避
2. **テストの容易性**: モック実装での単体テスト
3. **並行開発の促進**: インターフェース合意後の独立開発
4. **段階的移行**: 既存機能を維持したまま新機能追加

---

## 🎯 実装優先順位の判断基準

### Critical（デプロイ完全阻害）
1. **認証システム** - セキュリティリスクが最大
2. **Input Interface** - Google Drive連携なしでは学部要件を満たせない
3. **ベクトル検索永続化** - サービス継続性の基本要件

### High（スケーラビリティ阻害）
4. **データベース抽象化** - 将来のスケール要件
5. **設定管理改善** - 運用効率化

### Medium（運用品質向上）
6. **モニタリング** - 運用可視化
7. **バックアップ** - データ保全

---

## 💡 将来のClaude Codeインスタンスへの指針

### 実装時の判断基準
1. **疎結合の維持**: 新機能は必ずPort/Adapterパターンで実装
2. **既存機能の保護**: 新機能追加時の既存動作維持
3. **段階的移行**: 一度にすべてを変更せず、段階的な改善

### アーキテクチャ設計の原則
1. **依存性逆転**: 上位層が下位層の実装に依存しない
2. **単一責任**: 各モジュールは明確な責任を持つ
3. **オープン・クローズド**: 拡張に開放、修正に閉鎖

### コードレビューのチェックポイント
1. **新しい外部依存は抽象化されているか**
2. **設定はすべて環境変数化されているか**
3. **エラーハンドリングは適切に実装されているか**
4. **テストは実装と同時に作成されているか**

---

**最終更新**: 2025年7月3日  
**文書の性質**: WHY/WHAT中心、HOWは各実装時に決定