
# 学部内データ管理PaaS 統合利用例

from paas_api import PaaSClient

# 1. クライアント初期化
client = PaaSClient("http://your-paas-server:8000")

# 2. 文書検索（基本）
results = client.search_documents("機械学習", limit=10)
for doc in results['documents']:
    print(f"[{doc['category']}] {doc['title']}")
    print(f"要約: {doc['summary'][:100]}...")
    print(f"キーワード: {', '.join(doc['keywords'])}")
    print("-" * 40)

# 3. カテゴリ別検索
datasets = client.search_documents("環境", category="dataset")
papers = client.search_documents("バイアス", category="paper")

# 4. 特定文書の詳細取得
paper_detail = client.get_document("paper", document_id=1)
print(f"著者: {paper_detail['authors']}")
print(f"ファイルサイズ: {paper_detail['file_size']} bytes")

# 5. システム統計
stats = client.get_statistics()
print(f"データベース内の総文書数: {stats['total_documents']}")
print(f"解析完了率: {stats['analysis_completion_rate']:.1f}%")

# 6. 新しい文書の取り込み（管理者用）
result = client.ingest_documents()
print(f"取り込み完了: {result['processed_files']}件処理")
