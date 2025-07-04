import json
from typing import List, Dict, Any, Optional
import logging
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

from ..database.repository import FileRepository, AnalysisResultRepository
from ..database.new_repository import DatasetRepository, PaperRepository, PosterRepository, DatasetFileRepository
from ..analyzer.gemini_client import GeminiClient

logger = logging.getLogger(__name__)


class ResearchAdvisor:
    """研究相談機能を提供するクラス"""
    
    def __init__(self):
        # 旧構造（互換性維持）
        self.file_repo = FileRepository()
        self.analysis_repo = AnalysisResultRepository()
        
        # 新構造（カテゴリー別）
        self.dataset_repo = DatasetRepository()
        self.paper_repo = PaperRepository()
        self.poster_repo = PosterRepository()
        self.dataset_file_repo = DatasetFileRepository()
        
        self.gemini_client = GeminiClient()
    
    def find_similar_documents(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """クエリに類似した文書を検索"""
        # 全ファイルとその解析結果を取得
        all_files = self.file_repo.find_all()
        if not all_files:
            logger.warning("インデックスされたファイルがありません")
            return []
        
        # 文書のテキスト表現を作成
        documents = []
        file_mapping = {}
        
        for idx, file in enumerate(all_files):
            # 解析結果を取得
            analysis_result = self.analysis_repo.find_latest_by_file_id(
                file.id, "content_analysis"
            )
            
            if analysis_result:
                try:
                    result_data = json.loads(analysis_result.result_data)
                    # 文書の特徴を結合
                    doc_text = self._create_document_representation(file, result_data)
                    documents.append(doc_text)
                    file_mapping[idx] = file
                except Exception as e:
                    logger.error(f"解析結果の読み込みエラー: {file.file_name}, {e}")
            else:
                # 解析結果がない場合は基本情報のみ
                doc_text = f"{file.file_name} {file.category} {file.summary or ''}"
                documents.append(doc_text)
                file_mapping[idx] = file
        
        if not documents:
            logger.warning("解析済みの文書がありません")
            return []
        
        # TF-IDFベクトル化
        try:
            vectorizer = TfidfVectorizer(max_features=100)
            # クエリを含めてベクトル化
            all_texts = documents + [query]
            tfidf_matrix = vectorizer.fit_transform(all_texts)
            
            # クエリベクトルと文書ベクトルの類似度を計算
            query_vector = tfidf_matrix[-1]
            doc_vectors = tfidf_matrix[:-1]
            similarities = cosine_similarity(query_vector, doc_vectors).flatten()
            
            # 上位k件を取得
            top_indices = similarities.argsort()[-top_k:][::-1]
            
            results = []
            for idx in top_indices:
                if similarities[idx] > 0:  # 類似度が0より大きいもののみ
                    file = file_mapping[idx]
                    analysis_result = self.analysis_repo.find_latest_by_file_id(
                        file.id, "content_analysis"
                    )
                    
                    result_data = {}
                    if analysis_result:
                        try:
                            result_data = json.loads(analysis_result.result_data)
                        except:
                            pass
                    
                    results.append({
                        "file_id": file.id,
                        "file_name": file.file_name,
                        "category": file.category,
                        "similarity_score": float(similarities[idx]),
                        "summary": result_data.get("summary", file.summary),
                        "keywords": result_data.get("keywords", []),
                        "file_path": file.file_path
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"類似文書検索エラー: {e}")
            return []
    
    def _create_document_representation(self, file, analysis_result: Dict[str, Any]) -> str:
        """文書の特徴表現を作成"""
        parts = [
            file.file_name,
            file.category,
            analysis_result.get("summary", ""),
            " ".join(analysis_result.get("main_topics", [])),
            " ".join(analysis_result.get("keywords", [])),
            analysis_result.get("research_field", ""),
            " ".join(analysis_result.get("key_findings", []))
        ]
        
        return " ".join(filter(None, parts))
    
    def provide_research_advice(self, query: str) -> Dict[str, Any]:
        """研究相談を提供"""
        # 関連文書を検索
        similar_docs = self.find_similar_documents(query, top_k=5)
        
        if not similar_docs:
            return {
                "advice": "関連する文書が見つかりませんでした。より具体的なキーワードで検索してください。",
                "recommended_approaches": [],
                "relevant_keywords": [],
                "next_steps": ["データベースに文書を追加する", "検索キーワードを変更する"],
                "related_documents": []
            }
        
        # Gemini APIでアドバイスを生成
        advice_result = self.gemini_client.generate_research_advice(query, similar_docs)
        
        if advice_result:
            advice_result["related_documents"] = similar_docs
            return advice_result
        else:
            # フォールバック
            return {
                "advice": f"'{query}'に関連する{len(similar_docs)}件の文書が見つかりました。これらの文書を参考に研究を進めることをお勧めします。",
                "recommended_approaches": ["関連文書の詳細な分析", "キーワードの拡張検索"],
                "relevant_keywords": self._extract_common_keywords(similar_docs),
                "next_steps": ["関連文書を読む", "追加の文献調査を行う"],
                "related_documents": similar_docs
            }
    
    def _extract_common_keywords(self, documents: List[Dict[str, Any]]) -> List[str]:
        """文書群から共通キーワードを抽出"""
        all_keywords = []
        for doc in documents:
            all_keywords.extend(doc.get("keywords", []))
        
        # 頻度をカウント
        keyword_counts = {}
        for keyword in all_keywords:
            keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
        
        # 頻度順にソート
        sorted_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)
        
        # 上位のキーワードを返す
        return [keyword for keyword, count in sorted_keywords[:10] if count > 1]
    
    def recommend_by_category(self, category: str, limit: int = 10) -> List[Dict[str, Any]]:
        """カテゴリー別の推薦"""
        files = self.file_repo.find_all(category=category)
        
        recommendations = []
        for file in files[:limit]:
            analysis_result = self.analysis_repo.find_latest_by_file_id(
                file.id, "content_analysis"
            )
            
            result_data = {}
            if analysis_result:
                try:
                    result_data = json.loads(analysis_result.result_data)
                except:
                    pass
            
            recommendations.append({
                "file_id": file.id,
                "file_name": file.file_name,
                "summary": result_data.get("summary", file.summary),
                "keywords": result_data.get("keywords", []),
                "research_field": result_data.get("research_field", ""),
                "file_path": file.file_path
            })
        
        return recommendations
    
    def get_research_trends(self) -> Dict[str, Any]:
        """研究トレンドを分析"""
        all_files = self.file_repo.find_all()
        
        trends = {
            "total_documents": len(all_files),
            "by_category": {},
            "popular_keywords": {},
            "research_fields": {}
        }
        
        all_keywords = []
        all_fields = []
        
        for file in all_files:
            # カテゴリー別集計
            category = file.category
            if category not in trends["by_category"]:
                trends["by_category"][category] = 0
            trends["by_category"][category] += 1
            
            # 解析結果から情報を抽出
            analysis_result = self.analysis_repo.find_latest_by_file_id(
                file.id, "content_analysis"
            )
            
            if analysis_result:
                try:
                    result_data = json.loads(analysis_result.result_data)
                    all_keywords.extend(result_data.get("keywords", []))
                    field = result_data.get("research_field")
                    if field:
                        all_fields.append(field)
                except:
                    pass
        
        # キーワードの集計
        for keyword in all_keywords:
            if keyword not in trends["popular_keywords"]:
                trends["popular_keywords"][keyword] = 0
            trends["popular_keywords"][keyword] += 1
        
        # 研究分野の集計
        for field in all_fields:
            if field not in trends["research_fields"]:
                trends["research_fields"][field] = 0
            trends["research_fields"][field] += 1
        
        # 上位のみを保持
        trends["popular_keywords"] = dict(
            sorted(trends["popular_keywords"].items(), 
                  key=lambda x: x[1], reverse=True)[:20]
        )
        trends["research_fields"] = dict(
            sorted(trends["research_fields"].items(), 
                  key=lambda x: x[1], reverse=True)[:10]
        )
        
        return trends