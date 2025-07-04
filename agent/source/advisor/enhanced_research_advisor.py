"""
拡張研究相談機能
新しいカテゴリー別データベース構造に対応した研究相談システム
"""

import json
from typing import List, Dict, Any, Optional, Tuple
import logging
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

from ..database.new_repository import DatasetRepository, PaperRepository, PosterRepository, DatasetFileRepository
from ..analyzer.gemini_client import GeminiClient

logger = logging.getLogger(__name__)


class EnhancedResearchAdvisor:
    """拡張研究相談機能を提供するクラス"""
    
    def __init__(self):
        self.dataset_repo = DatasetRepository()
        self.paper_repo = PaperRepository()
        self.poster_repo = PosterRepository()
        self.dataset_file_repo = DatasetFileRepository()
        self.gemini_client = GeminiClient()
        
        # 会話履歴管理
        self.conversation_history: List[Dict[str, Any]] = []
        
    def start_research_chat(self, user_query: str) -> Dict[str, Any]:
        """研究相談チャットを開始"""
        logger.info(f"研究相談チャット開始: {user_query}")
        
        # 会話履歴をクリア
        self.conversation_history = []
        
        # 初期アドバイスを生成
        return self._process_research_query(user_query, is_initial=True)
    
    def continue_research_chat(self, user_query: str) -> Dict[str, Any]:
        """研究相談チャットを継続"""
        logger.info(f"研究相談チャット継続: {user_query}")
        
        return self._process_research_query(user_query, is_initial=False)
    
    def _process_research_query(self, query: str, is_initial: bool = False) -> Dict[str, Any]:
        """研究クエリを処理"""
        try:
            # 1. 関連文書の検索
            similar_docs = self._find_similar_documents_enhanced(query)
            
            # 2. データセット関連情報の取得
            relevant_datasets = self._find_relevant_datasets(query)
            
            # 3. 研究アイディアの言語化支援
            idea_structuring = self._structure_research_idea(query)
            
            # 4. 独自性評価
            originality_assessment = self._assess_research_originality(query, similar_docs)
            
            # 5. 研究計画立案支援
            research_plan = self._generate_research_plan(query, similar_docs, relevant_datasets)
            
            # 6. プロンプトを構築してGemini APIで総合的なアドバイスを生成
            advice_response = self._generate_comprehensive_advice(
                query, similar_docs, relevant_datasets, idea_structuring, 
                originality_assessment, research_plan, is_initial
            )
            
            # 7. 会話履歴に追加
            conversation_entry = {
                "timestamp": datetime.now().isoformat(),
                "user_query": query,
                "response": advice_response,
                "similar_docs": similar_docs,
                "relevant_datasets": relevant_datasets
            }
            self.conversation_history.append(conversation_entry)
            
            return advice_response
            
        except Exception as e:
            logger.error(f"研究クエリ処理エラー: {e}")
            return {
                "advice": "申し訳ございません。システムエラーが発生しました。再度お試しください。",
                "research_structure": {},
                "originality_score": 0,
                "research_plan": {},
                "related_documents": [],
                "relevant_datasets": [],
                "next_actions": ["システム管理者に連絡する"]
            }
    
    def _find_similar_documents_enhanced(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """拡張された類似文書検索"""
        documents = []
        doc_metadata = []
        
        # 論文の検索
        papers = self.paper_repo.find_all()
        for paper in papers:
            if paper.abstract or paper.title:
                doc_text = f"{paper.title or ''} {paper.authors or ''} {paper.abstract or ''} {paper.keywords or ''}"
                documents.append(doc_text)
                doc_metadata.append({
                    "type": "paper",
                    "id": paper.id,
                    "title": paper.title,
                    "authors": paper.authors,
                    "abstract": paper.abstract,
                    "keywords": paper.keywords,
                    "file_name": paper.file_name,
                    "file_path": paper.file_path
                })
        
        # ポスターの検索
        posters = self.poster_repo.find_all()
        for poster in posters:
            if poster.abstract or poster.title:
                doc_text = f"{poster.title or ''} {poster.authors or ''} {poster.abstract or ''} {poster.keywords or ''}"
                documents.append(doc_text)
                doc_metadata.append({
                    "type": "poster",
                    "id": poster.id,
                    "title": poster.title,
                    "authors": poster.authors,
                    "abstract": poster.abstract,
                    "keywords": poster.keywords,
                    "file_name": poster.file_name,
                    "file_path": poster.file_path
                })
        
        # データセットの検索
        datasets = self.dataset_repo.find_all()
        for dataset in datasets:
            if dataset.summary or dataset.description:
                doc_text = f"{dataset.name} {dataset.description or ''} {dataset.summary or ''}"
                documents.append(doc_text)
                doc_metadata.append({
                    "type": "dataset",
                    "id": dataset.id,
                    "name": dataset.name,
                    "description": dataset.description,
                    "summary": dataset.summary,
                    "file_count": dataset.file_count,
                    "total_size": dataset.total_size
                })
        
        if not documents:
            return []
        
        try:
            # キーワードベース検索も追加（フォールバック）
            keyword_results = []
            important_keywords = self._extract_meaningful_keywords(query)
            
            for i, doc_text in enumerate(documents):
                score = 0
                for keyword in important_keywords:
                    if keyword in doc_text.lower():
                        score += 1
                
                if score > 0:
                    metadata = doc_metadata[i].copy()
                    metadata["similarity_score"] = score * 0.3  # キーワードマッチングスコア
                    keyword_results.append(metadata)
            
            # TF-IDFベクトル化と類似度計算
            vectorizer = TfidfVectorizer(max_features=200, stop_words='english')
            all_texts = documents + [query]
            tfidf_matrix = vectorizer.fit_transform(all_texts)
            
            query_vector = tfidf_matrix[-1]
            doc_vectors = tfidf_matrix[:-1]
            similarities = cosine_similarity(query_vector, doc_vectors).flatten()
            
            # 上位k件を取得（閾値を下げる）
            top_indices = similarities.argsort()[-top_k:][::-1]
            
            tfidf_results = []
            for idx in top_indices:
                if similarities[idx] > 0.05:  # 閾値を下げた
                    metadata = doc_metadata[idx].copy()
                    metadata["similarity_score"] = float(similarities[idx])
                    tfidf_results.append(metadata)
            
            # キーワード結果とTF-IDF結果を統合
            all_results = keyword_results + tfidf_results
            
            # 重複削除（IDベース）
            seen_ids = set()
            unique_results = []
            for result in all_results:
                result_id = f"{result['type']}_{result['id']}"
                if result_id not in seen_ids:
                    seen_ids.add(result_id)
                    unique_results.append(result)
            
            # スコア順にソート
            unique_results.sort(key=lambda x: x["similarity_score"], reverse=True)
            
            return unique_results[:top_k]
            
        except Exception as e:
            logger.error(f"類似文書検索エラー: {e}")
            return []
    
    def _find_relevant_datasets(self, query: str) -> List[Dict[str, Any]]:
        """関連データセットの検索（改善版）"""
        datasets = self.dataset_repo.find_all()
        relevant_datasets = []
        
        # キーワード抽出の改善
        important_keywords = self._extract_meaningful_keywords(query)
        
        for dataset in datasets:
            # データセット情報をテキスト化
            dataset_text = f"{dataset.name} {dataset.description or ''} {dataset.summary or ''}".lower()
            
            # データセットファイル情報も取得
            dataset_files = self.dataset_file_repo.find_by_dataset_id(dataset.id)
            
            # 関連度スコア計算（改良版）
            relevance_score = 0
            
            # 重要キーワードでの完全一致
            for keyword in important_keywords:
                if keyword in dataset_text:
                    relevance_score += 3  # 高スコア
            
            # データセット名での部分一致
            if any(keyword in dataset.name.lower() for keyword in important_keywords):
                relevance_score += 5  # 最高スコア
            
            # 元のクエリでの部分一致もチェック（フォールバック）
            query_lower = query.lower()
            for word in query_lower.split():
                if len(word) > 2 and word in dataset_text:  # 短すぎる単語は除外
                    relevance_score += 1
            
            if relevance_score > 0:
                relevant_datasets.append({
                    "dataset_id": dataset.id,
                    "name": dataset.name,
                    "description": dataset.description,
                    "summary": dataset.summary,
                    "file_count": dataset.file_count,
                    "total_size": dataset.total_size,
                    "files": [{"file_name": f.file_name, "file_type": f.file_type} for f in dataset_files],
                    "relevance_score": relevance_score
                })
        
        # 関連度順にソート
        relevant_datasets.sort(key=lambda x: x["relevance_score"], reverse=True)
        return relevant_datasets[:5]
    
    def _extract_meaningful_keywords(self, text: str) -> List[str]:
        """意味のあるキーワードを抽出"""
        import re
        
        # 一般的でない単語を抽出
        stopwords = {
            # 日本語助詞・動詞・形容詞など
            'に', 'を', 'が', 'は', 'で', 'と', 'の', 'だ', 'である', 'です', 'ます', 'した', 'する', 'される',
            'から', 'まで', 'より', 'など', 'こと', 'もの', 'について', 'に関する', 'がしたい', 'したい',
            # 英語一般語
            'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'about'
        }
        
        # 英数字混合キーワードを抽出（ESG, AI, MLなど）
        keywords = []
        
        # 3文字以上の英数字キーワードを抽出
        english_keywords = re.findall(r'[A-Za-z0-9]{2,}', text)
        keywords.extend([kw.lower() for kw in english_keywords])
        
        # 2文字以上の日本語キーワードを抽出
        japanese_keywords = re.findall(r'[あ-ん]{2,}|[ア-ン]{2,}|[一-龯]{2,}', text)
        keywords.extend(japanese_keywords)
        
        # ストップワードを除去
        meaningful_keywords = [kw for kw in keywords if kw not in stopwords and len(kw) >= 2]
        
        return list(set(meaningful_keywords))  # 重複除去
    
    def _structure_research_idea(self, query: str) -> Dict[str, Any]:
        """研究アイディアの構造化"""
        return {
            "research_question": f"「{query}」に関する研究課題の明確化が必要",
            "methodology_suggestions": [
                "定量的分析アプローチ",
                "定性的分析アプローチ",
                "混合研究法アプローチ"
            ],
            "potential_variables": [],
            "theoretical_framework": "関連理論の調査が必要",
            "scope_definition": "研究範囲の明確化が重要"
        }
    
    def _assess_research_originality(self, query: str, similar_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """研究の独自性評価"""
        if not similar_docs:
            originality_score = 0.9
            assessment = "新規性が高い可能性があります"
        elif len(similar_docs) <= 2:
            originality_score = 0.7
            assessment = "ある程度の新規性が期待できます"
        else:
            originality_score = 0.4
            assessment = "既存研究との差別化が重要です"
        
        return {
            "originality_score": originality_score,
            "assessment": assessment,
            "similar_research_count": len(similar_docs),
            "differentiation_suggestions": [
                "新しい視点からのアプローチ",
                "異なる手法の適用",
                "対象範囲の拡張または特化"
            ]
        }
    
    def _generate_research_plan(self, query: str, similar_docs: List[Dict[str, Any]], 
                              relevant_datasets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """研究計画立案支援"""
        return {
            "phase1": {
                "title": "文献調査・理論的基盤構築",
                "duration": "2-3週間",
                "activities": [
                    "関連文献の詳細レビュー",
                    "理論的フレームワークの構築",
                    "研究仮説の設定"
                ]
            },
            "phase2": {
                "title": "データ収集・準備",
                "duration": "1-2週間", 
                "activities": [
                    "利用可能なデータセットの評価",
                    "データ前処理",
                    "分析手法の選定"
                ]
            },
            "phase3": {
                "title": "分析・検証",
                "duration": "3-4週間",
                "activities": [
                    "データ分析の実行",
                    "結果の解釈",
                    "仮説の検証"
                ]
            },
            "phase4": {
                "title": "結果取りまとめ・発表",
                "duration": "2-3週間",
                "activities": [
                    "結果の整理",
                    "論文・発表資料の作成",
                    "ピアレビューの実施"
                ]
            },
            "available_datasets": [ds["name"] for ds in relevant_datasets],
            "estimated_duration": "8-12週間"
        }
    
    def _generate_comprehensive_advice(self, query: str, similar_docs: List[Dict[str, Any]], 
                                     relevant_datasets: List[Dict[str, Any]], 
                                     idea_structuring: Dict[str, Any],
                                     originality_assessment: Dict[str, Any],
                                     research_plan: Dict[str, Any],
                                     is_initial: bool) -> Dict[str, Any]:
        """総合的なアドバイスを生成"""
        
        # 会話の文脈を考慮
        context = ""
        if not is_initial and self.conversation_history:
            recent_history = self.conversation_history[-2:]  # 最近の2つの会話
            context = "前回の相談内容: " + "; ".join([h["user_query"] for h in recent_history])
        
        # Gemini APIに送るプロンプトを構築
        prompt = self._build_research_advice_prompt(
            query, similar_docs, relevant_datasets, idea_structuring,
            originality_assessment, research_plan, context
        )
        
        # Gemini APIでアドバイス生成
        try:
            advice_text = self.gemini_client.generate_research_advice_enhanced(prompt)
            if not advice_text:
                advice_text = self._generate_fallback_advice(query)
        except Exception as e:
            logger.error(f"Gemini API呼び出しエラー: {e}")
            advice_text = self._generate_fallback_advice(query)
        
        return {
            "advice": advice_text,
            "research_structure": idea_structuring,
            "originality_assessment": originality_assessment,
            "research_plan": research_plan,
            "related_documents": similar_docs,
            "relevant_datasets": relevant_datasets,
            "next_actions": self._suggest_next_actions(query, similar_docs, relevant_datasets),
            "conversation_id": len(self.conversation_history),
            "context_maintained": not is_initial
        }
    
    def _build_research_advice_prompt(self, query: str, similar_docs: List[Dict[str, Any]], 
                                    relevant_datasets: List[Dict[str, Any]], 
                                    idea_structuring: Dict[str, Any],
                                    originality_assessment: Dict[str, Any],
                                    research_plan: Dict[str, Any],
                                    context: str) -> str:
        """研究アドバイス用プロンプトを構築"""
        
        prompt = f"""あなたは経験豊富な研究アドバイザーです。以下の研究相談に対して、具体的で実践的なアドバイスを提供してください。

【研究相談内容】
{query}

{f"【前回の相談との関連】{context}" if context else ""}

【利用可能な関連研究】
{self._format_similar_docs_for_prompt(similar_docs)}

【利用可能なデータセット】
{self._format_datasets_for_prompt(relevant_datasets)}

【独自性評価】
- スコア: {originality_assessment['originality_score']:.1f}/1.0
- 評価: {originality_assessment['assessment']}
- 類似研究数: {originality_assessment['similar_research_count']}件

【提案する研究計画フェーズ】
{self._format_research_plan_for_prompt(research_plan)}

以下の観点で具体的なアドバイスを提供してください：
1. 研究アプローチの具体的な提案
2. 既存研究との差別化ポイント
3. 利用すべきデータセットと分析手法
4. 研究の実現可能性と課題
5. 次に取るべき具体的なアクション

アドバイスは研究者の立場に立って、実践的で行動につながる内容にしてください。"""
        
        return prompt
    
    def _format_similar_docs_for_prompt(self, similar_docs: List[Dict[str, Any]]) -> str:
        """類似文書をプロンプト用にフォーマット"""
        if not similar_docs:
            return "関連する研究は見つかりませんでした。"
        
        formatted = []
        for doc in similar_docs:
            if doc["type"] == "paper":
                formatted.append(f"- 論文: {doc.get('title', doc['file_name'])} (著者: {doc.get('authors', '不明')})")
            elif doc["type"] == "poster":
                formatted.append(f"- ポスター: {doc.get('title', doc['file_name'])} (著者: {doc.get('authors', '不明')})")
            elif doc["type"] == "dataset":
                formatted.append(f"- データセット: {doc['name']}")
        
        return "\n".join(formatted)
    
    def _format_datasets_for_prompt(self, datasets: List[Dict[str, Any]]) -> str:
        """データセットをプロンプト用にフォーマット"""
        if not datasets:
            return "関連するデータセットは見つかりませんでした。"
        
        formatted = []
        for ds in datasets:
            files_info = f"({ds['file_count']}ファイル)" if ds['file_count'] else ""
            formatted.append(f"- {ds['name']} {files_info}: {ds.get('summary', ds.get('description', '詳細不明'))}")
        
        return "\n".join(formatted)
    
    def _format_research_plan_for_prompt(self, plan: Dict[str, Any]) -> str:
        """研究計画をプロンプト用にフォーマット"""
        formatted = []
        for phase_key, phase_info in plan.items():
            if phase_key.startswith("phase"):
                formatted.append(f"{phase_info['title']} ({phase_info['duration']})")
        
        return "\n".join(formatted)
    
    def _generate_fallback_advice(self, query: str) -> str:
        """フォールバックアドバイス"""
        return f"""「{query}」に関する研究について、以下のアプローチをお勧めします：

1. **文献調査の実施**
   - 関連するキーワードでより広範囲な文献検索を行う
   - 最新の研究動向を把握する

2. **研究課題の明確化**
   - 具体的な研究問題を定義する
   - 研究の目的と意義を明確にする

3. **手法の検討** 
   - 研究対象と目的に適した分析手法を選択する
   - 利用可能なデータとリソースを評価する

4. **実現可能性の評価**
   - 時間的・資源的制約を考慮した計画を立案する
   - リスクと対策を検討する

より具体的なアドバイスのために、研究の詳細や背景についてお聞かせください。"""
    
    def _suggest_next_actions(self, query: str, similar_docs: List[Dict[str, Any]], 
                            relevant_datasets: List[Dict[str, Any]]) -> List[str]:
        """次のアクションを提案"""
        actions = []
        
        if similar_docs:
            actions.append(f"関連研究{len(similar_docs)}件の詳細な分析を実施する")
        
        if relevant_datasets:
            actions.append(f"関連データセット{len(relevant_datasets)}件の詳細な調査を行う")
        
        actions.extend([
            "研究課題をより具体的に定義する",
            "研究計画書の初版を作成する",
            "指導教員や同僚との議論を行う",
            "関連分野の専門家にヒアリングを実施する"
        ])
        
        return actions
    
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """会話履歴を取得"""
        return self.conversation_history
    
    def export_consultation_report(self) -> Dict[str, Any]:
        """相談内容をレポート形式でエクスポート"""
        if not self.conversation_history:
            return {"error": "相談履歴がありません"}
        
        return {
            "consultation_date": datetime.now().isoformat(),
            "total_queries": len(self.conversation_history),
            "conversation_summary": [
                {
                    "query": entry["user_query"],
                    "timestamp": entry["timestamp"],
                    "key_recommendations": entry["response"].get("next_actions", [])
                }
                for entry in self.conversation_history
            ],
            "overall_research_focus": self._extract_research_focus(),
            "recommended_resources": self._extract_recommended_resources()
        }
    
    def _extract_research_focus(self) -> str:
        """研究フォーカスを抽出"""
        if not self.conversation_history:
            return "不明"
        
        # 簡易的な実装：最初の質問をベースにする
        return self.conversation_history[0]["user_query"]
    
    def _extract_recommended_resources(self) -> List[str]:
        """推奨リソースを抽出"""
        resources = set()
        
        for entry in self.conversation_history:
            # 関連文書
            for doc in entry.get("similar_docs", []):
                if doc["type"] == "paper":
                    resources.add(f"論文: {doc.get('title', doc['file_name'])}")
                elif doc["type"] == "poster":
                    resources.add(f"ポスター: {doc.get('title', doc['file_name'])}")
            
            # データセット
            for ds in entry.get("relevant_datasets", []):
                resources.add(f"データセット: {ds['name']}")
        
        return list(resources)