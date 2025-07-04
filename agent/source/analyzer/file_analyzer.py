import json
from pathlib import Path
from typing import Dict, Any, Optional
import logging
import PyPDF2
import pandas as pd

from .gemini_client import GeminiClient
from ..database.models import File, AnalysisResult
from ..database.repository import FileRepository, AnalysisResultRepository

logger = logging.getLogger(__name__)


class FileAnalyzer:
    """ファイル内容を解析するクラス"""
    
    def __init__(self):
        self.gemini_client = GeminiClient()
        self.file_repo = FileRepository()
        self.analysis_repo = AnalysisResultRepository()
    
    def analyze_file(self, file_id: int, force: bool = False) -> Optional[Dict[str, Any]]:
        """ファイルを解析"""
        # ファイル情報を取得
        file_obj = self.file_repo.find_by_id(file_id)
        if not file_obj:
            logger.error(f"ファイルが見つかりません: ID={file_id}")
            return None
        
        # 既存の解析結果をチェック
        if not force:
            existing_result = self.analysis_repo.find_latest_by_file_id(
                file_id, "content_analysis"
            )
            if existing_result:
                logger.info(f"既存の解析結果を使用: {file_obj.file_name}")
                return json.loads(existing_result.result_data)
        
        # ファイル内容を読み込み
        content = self._read_file_content(file_obj)
        if not content:
            return None
        
        # Gemini APIで解析
        logger.info(f"ファイルを解析中: {file_obj.file_name}")
        analysis_result = self.gemini_client.analyze_file_content(
            file_obj.file_path, content, file_obj.file_type
        )
        
        if analysis_result:
            # 解析結果を保存
            self._save_analysis_result(file_obj, analysis_result)
            
            # ファイルの要約を更新
            if "summary" in analysis_result:
                file_obj.summary = analysis_result["summary"]
                self.file_repo.update(file_obj)
        
        return analysis_result
    
    def _read_file_content(self, file_obj: File) -> Optional[str]:
        """ファイル内容を読み込み"""
        file_path = Path(file_obj.file_path)
        
        if not file_path.exists():
            logger.error(f"ファイルが存在しません: {file_path}")
            return None
        
        try:
            if file_obj.file_type == "pdf":
                return self._read_pdf(file_path)
            elif file_obj.file_type == "csv":
                return self._read_csv(file_path)
            elif file_obj.file_type in ["json", "jsonl"]:
                return self._read_json(file_path)
            else:
                logger.error(f"未対応のファイルタイプ: {file_obj.file_type}")
                return None
                
        except Exception as e:
            logger.error(f"ファイル読み込みエラー: {file_path}, {e}")
            return None
    
    def _read_pdf(self, file_path: Path) -> Optional[str]:
        """PDFファイルを読み込み"""
        try:
            text_content = []
            
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                for page_num, page in enumerate(pdf_reader.pages):
                    try:
                        text = page.extract_text()
                        if text:
                            text_content.append(f"--- ページ {page_num + 1} ---\n{text}")
                    except Exception as e:
                        logger.warning(f"ページ読み込みエラー: ページ {page_num + 1}, {e}")
            
            return "\n\n".join(text_content)
            
        except Exception as e:
            logger.error(f"PDF読み込みエラー: {file_path}, {e}")
            return None
    
    def _read_csv(self, file_path: Path) -> Optional[str]:
        """CSVファイルを読み込み"""
        try:
            # 最初の部分だけ読み込む
            df = pd.read_csv(file_path, nrows=100)
            
            content = f"CSVファイル: {file_path.name}\n"
            content += f"カラム数: {len(df.columns)}\n"
            content += f"行数（サンプル）: {len(df)}\n\n"
            content += f"カラム: {', '.join(df.columns)}\n\n"
            content += "データサンプル:\n"
            content += df.head(10).to_string()
            
            return content
            
        except Exception as e:
            logger.error(f"CSV読み込みエラー: {file_path}, {e}")
            return None
    
    def _read_json(self, file_path: Path) -> Optional[str]:
        """JSON/JSONLファイルを読み込み"""
        try:
            content_preview = []
            
            with open(file_path, 'r', encoding='utf-8') as f:
                if file_path.suffix == '.jsonl':
                    # JSONL: 各行がJSONオブジェクト
                    lines = f.readlines()[:100]  # 最初の100行
                    content_preview.append(f"JSONLファイル: {file_path.name}")
                    content_preview.append(f"総行数（推定）: {len(lines)}")
                    
                    for i, line in enumerate(lines[:5]):
                        try:
                            obj = json.loads(line)
                            content_preview.append(f"\n行 {i+1}:")
                            content_preview.append(json.dumps(obj, indent=2, ensure_ascii=False))
                        except:
                            pass
                else:
                    # 通常のJSON
                    data = json.load(f)
                    content_preview.append(f"JSONファイル: {file_path.name}")
                    
                    # データ構造の概要を作成
                    if isinstance(data, list):
                        content_preview.append(f"配列サイズ: {len(data)}")
                        if data:
                            content_preview.append("\n最初の要素:")
                            content_preview.append(json.dumps(data[0], indent=2, ensure_ascii=False))
                    else:
                        content_preview.append("\nデータ構造:")
                        content_preview.append(json.dumps(data, indent=2, ensure_ascii=False)[:2000])
            
            return "\n".join(content_preview)
            
        except Exception as e:
            logger.error(f"JSON読み込みエラー: {file_path}, {e}")
            return None
    
    def _save_analysis_result(self, file_obj: File, analysis_result: Dict[str, Any]):
        """解析結果を保存"""
        result = AnalysisResult(
            file_id=file_obj.id,
            analysis_type="content_analysis",
            result_data=json.dumps(analysis_result, ensure_ascii=False)
        )
        
        self.analysis_repo.create(result)
        logger.info(f"解析結果を保存: {file_obj.file_name}")
    
    def batch_analyze(self, file_ids: list = None, force: bool = False) -> Dict[str, Any]:
        """複数ファイルを一括解析"""
        if file_ids is None:
            # 全ファイルを対象
            files = self.file_repo.find_all()
            file_ids = [f.id for f in files]
        
        results = {
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "details": []
        }
        
        for file_id in file_ids:
            try:
                result = self.analyze_file(file_id, force)
                if result:
                    results["success"] += 1
                    results["details"].append({
                        "file_id": file_id,
                        "status": "success"
                    })
                else:
                    results["failed"] += 1
                    results["details"].append({
                        "file_id": file_id,
                        "status": "failed"
                    })
            except Exception as e:
                results["failed"] += 1
                results["details"].append({
                    "file_id": file_id,
                    "status": "error",
                    "error": str(e)
                })
                logger.error(f"ファイル解析エラー: ID={file_id}, {e}")
        
        return results