import json
from typing import Dict, Any, Optional, List
import logging
import time

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from tools.config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger(__name__)


class GeminiClient:
    """Google Gemini APIクライアント"""
    
    def __init__(self):
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY が設定されていません")
        
        genai.configure(api_key=GEMINI_API_KEY)
        self.model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            generation_config={
                "temperature": 0.7,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 8192,
                "response_mime_type": "application/json",
            },
            safety_settings={
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            }
        )
        
        logger.info(f"Gemini クライアント初期化完了: モデル={GEMINI_MODEL}")
    
    def analyze_text(self, text: str, prompt_template: str, 
                    retry_count: int = 3) -> Optional[Dict[str, Any]]:
        """テキストを解析"""
        prompt = prompt_template.format(text=text)
        
        for attempt in range(retry_count):
            try:
                response = self.model.generate_content(prompt)
                
                if response.text:
                    # JSON形式で返されることを期待
                    try:
                        result = json.loads(response.text)
                        return result
                    except json.JSONDecodeError:
                        logger.warning("レスポンスがJSON形式ではありません")
                        return {"raw_response": response.text}
                else:
                    logger.warning("空のレスポンスが返されました")
                    
            except Exception as e:
                logger.error(f"Gemini API エラー (試行 {attempt + 1}/{retry_count}): {e}")
                if attempt < retry_count - 1:
                    time.sleep(2 ** attempt)  # エクスポネンシャルバックオフ
                else:
                    raise
        
        return None
    
    def analyze_file_content(self, file_path: str, file_content: str, 
                           file_type: str) -> Optional[Dict[str, Any]]:
        """ファイル内容を解析"""
        if file_type == "pdf":
            return self._analyze_pdf_content(file_content)
        elif file_type in ["csv", "json", "jsonl"]:
            return self._analyze_data_content(file_content, file_type)
        else:
            logger.warning(f"未対応のファイルタイプ: {file_type}")
            return None
    
    def _analyze_pdf_content(self, content: str) -> Optional[Dict[str, Any]]:
        """PDF文書を解析"""
        prompt_template = """
以下の文書を分析し、JSON形式で結果を返してください。

文書内容:
{text}

以下の形式で返してください:
{{
    "summary": "文書の要約（200文字以内）",
    "main_topics": ["主要なトピック1", "主要なトピック2", ...],
    "keywords": ["キーワード1", "キーワード2", ...],
    "language": "主要言語（japanese/english）",
    "document_type": "文書タイプ（paper/poster/report/other）",
    "research_field": "研究分野",
    "key_findings": ["主要な発見1", "主要な発見2", ...]
}}
"""
        return self.analyze_text(content, prompt_template)
    
    def _analyze_data_content(self, content: str, file_type: str) -> Optional[Dict[str, Any]]:
        """データファイルを解析"""
        prompt_template = """
以下のデータファイル（{file_type}形式）を分析し、JSON形式で結果を返してください。

データ内容（最初の部分）:
{text}

以下の形式で返してください:
{{
    "summary": "このデータセットは[データの内容・目的・特徴を説明]。（200文字以内）",
    "data_structure": "データ構造の説明",
    "columns": ["カラム名1", "カラム名2", ...],
    "row_count": "推定行数",
    "data_types": {{"カラム名": "データ型", ...}},
    "potential_use_cases": ["使用事例1", "使用事例2", ...],
    "data_quality_notes": "データ品質に関する注記"
}}

重要: summaryは必ず「このデータセットは」で始めてください。
"""
        prompt = prompt_template.format(text=content[:3000], file_type=file_type)
        return self.analyze_text(content, prompt)
    
    def analyze_dataset_collection(self, dataset_name: str, 
                                 file_contents: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
        """データセット全体（複数ファイル）を解析"""
        # ファイル内容をまとめる
        combined_content = f"データセット名: {dataset_name}\n\n"
        for i, file_info in enumerate(file_contents, 1):
            combined_content += f"ファイル{i}: {file_info['name']}\n"
            combined_content += f"内容: {file_info['content'][:1000]}\n\n"
        
        prompt_template = """
以下のデータセット全体を分析し、JSON形式で結果を返してください。

{text}

以下の形式で返してください:
{{
    "summary": "このデータセットは[データセット全体の内容・目的・特徴を総合的に説明]。（300文字以内）",
    "main_purpose": "データセットの主な目的",
    "data_types": ["データタイプ1", "データタイプ2", ...],
    "research_domains": ["研究領域1", "研究領域2", ...],
    "key_features": ["特徴1", "特徴2", ...],
    "potential_applications": ["応用例1", "応用例2", ...],
    "file_descriptions": {{"ファイル名": "説明", ...}}
}}

重要: summaryは必ず「このデータセットは」で始めてください。
"""
        return self.analyze_text(combined_content, prompt_template)
    
    def generate_research_advice(self, query: str, 
                               relevant_documents: list) -> Optional[Dict[str, Any]]:
        """研究アドバイスを生成"""
        docs_summary = "\n\n".join([
            f"文書{i+1}: {doc.get('title', 'タイトルなし')}\n"
            f"要約: {doc.get('summary', '要約なし')}\n"
            f"キーワード: {', '.join(doc.get('keywords', []))}"
            for i, doc in enumerate(relevant_documents[:5])
        ])
        
        prompt_template = """
ユーザーの研究相談:
{query}

関連する文書:
{docs_summary}

以下の形式でアドバイスを提供してください:
{{
    "advice": "研究アドバイス（500文字以内）",
    "recommended_approaches": ["推奨アプローチ1", "推奨アプローチ2", ...],
    "relevant_keywords": ["関連キーワード1", "関連キーワード2", ...],
    "next_steps": ["次のステップ1", "次のステップ2", ...],
    "potential_challenges": ["潜在的な課題1", "潜在的な課題2", ...]
}}
"""
        prompt = prompt_template.format(query=query, docs_summary=docs_summary)
        return self.analyze_text("", prompt)