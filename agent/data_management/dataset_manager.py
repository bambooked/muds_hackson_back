"""
データセット管理機能
ディレクトリ単位でのデータセット管理とLLMによる自動タグ付け・説明生成
"""
import os
import json
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..database_handler import DatabaseHandler
from ..processing.file_processor import FileProcessor
from ..processing.gemini_analyzer import GeminiAnalyzer
from ..config import Config


class DatasetManager:
    """ディレクトリベースのデータセット管理クラス"""
    
    def __init__(self, db_handler: DatabaseHandler, config: Optional[Config] = None):
        """
        データセットマネージャの初期化
        
        Args:
            db_handler: データベースハンドラ
            config: 設定オブジェクト
        """
        self.db_handler = db_handler
        self.config = config or Config()
        self.file_processor = FileProcessor(config)
        self.gemini_analyzer = GeminiAnalyzer(config)
        
        # データセット用テーブルの初期化
        self._init_dataset_tables()
    
    def _init_dataset_tables(self):
        """データセット用テーブルの初期化"""
        with self.db_handler.get_connection() as conn:
            cursor = conn.cursor()
            
            # データセットテーブル
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS datasets (
                    dataset_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    directory_path TEXT UNIQUE NOT NULL,
                    description TEXT,
                    tags TEXT,  -- JSON形式
                    research_field TEXT,
                    data_type TEXT,
                    file_count INTEGER DEFAULT 0,
                    total_size INTEGER DEFAULT 0,
                    llm_generated_summary TEXT,
                    llm_generated_tags TEXT,  -- JSON形式
                    quality_score REAL,
                    complexity_level TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # データセット内ファイルテーブル
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dataset_files (
                    file_id TEXT PRIMARY KEY,
                    dataset_id TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    file_type TEXT,
                    file_size INTEGER,
                    role TEXT,  -- main, supporting, metadata など
                    description TEXT,
                    FOREIGN KEY (dataset_id) REFERENCES datasets (dataset_id)
                )
            """)
            
            # インデックス作成
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_dataset_tags ON datasets(tags)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_dataset_field ON datasets(research_field)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_dataset_type ON datasets(data_type)")
            
            conn.commit()
    
    def register_dataset(self, directory_path: str, 
                        custom_name: str = None,
                        custom_description: str = None) -> Dict[str, Any]:
        """
        ディレクトリをデータセットとして登録
        
        Args:
            directory_path: ディレクトリパス
            custom_name: カスタム名（指定しない場合はディレクトリ名）
            custom_description: カスタム説明
        
        Returns:
            登録結果
        """
        if not os.path.isdir(directory_path):
            return {
                'success': False,
                'error': f'ディレクトリが見つかりません: {directory_path}'
            }
        
        try:
            # ディレクトリの分析
            directory_analysis = self._analyze_directory(directory_path)
            
            # データセット名の決定
            dataset_name = custom_name or os.path.basename(directory_path)
            
            # LLMによる自動分析
            llm_analysis = self._generate_llm_analysis(directory_analysis, custom_description)
            
            # データセットIDの生成
            dataset_id = self._generate_dataset_id(directory_path)
            
            # データセット情報の構築
            dataset_info = {
                'dataset_id': dataset_id,
                'name': dataset_name,
                'directory_path': os.path.abspath(directory_path),
                'description': custom_description or llm_analysis.get('description', ''),
                'tags': json.dumps(llm_analysis.get('tags', []), ensure_ascii=False),
                'research_field': llm_analysis.get('research_field', '不明'),
                'data_type': llm_analysis.get('data_type', 'dataset'),
                'file_count': directory_analysis['file_count'],
                'total_size': directory_analysis['total_size'],
                'llm_generated_summary': llm_analysis.get('summary', ''),
                'llm_generated_tags': json.dumps(llm_analysis.get('llm_tags', []), ensure_ascii=False),
                'quality_score': llm_analysis.get('quality_score', 0.5),
                'complexity_level': llm_analysis.get('complexity', 'moderate')
            }
            
            # データベースに登録
            self._save_dataset(dataset_info, directory_analysis['files'])
            
            return {
                'success': True,
                'dataset_id': dataset_id,
                'name': dataset_name,
                'message': f'データセット "{dataset_name}" を登録しました',
                'analysis': llm_analysis
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'データセット登録エラー: {str(e)}'
            }
    
    def _analyze_directory(self, directory_path: str) -> Dict[str, Any]:
        """
        ディレクトリの構造とファイルを分析
        
        Args:
            directory_path: ディレクトリパス
        
        Returns:
            分析結果
        """
        analysis = {
            'directory_path': directory_path,
            'files': [],
            'file_count': 0,
            'total_size': 0,
            'file_types': {},
            'structure': []
        }
        
        for root, dirs, files in os.walk(directory_path):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                relative_path = os.path.relpath(file_path, directory_path)
                
                # ファイル情報の取得
                file_info = {
                    'file_path': file_path,
                    'relative_path': relative_path,
                    'file_name': file_name,
                    'file_size': os.path.getsize(file_path),
                    'file_type': os.path.splitext(file_name)[1].lower(),
                    'modified_time': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
                }
                
                # ファイルの役割を推定
                file_info['role'] = self._infer_file_role(file_name, relative_path)
                
                # ファイル内容のプレビュー（テキストファイルの場合）
                if file_info['file_type'] in ['.txt', '.md', '.json', '.csv']:
                    try:
                        file_info['content_preview'] = self.file_processor.get_content_preview(file_path, 300)
                    except:
                        file_info['content_preview'] = ''
                
                analysis['files'].append(file_info)
                analysis['file_count'] += 1
                analysis['total_size'] += file_info['file_size']
                
                # ファイル拡張子の集計
                ext = file_info['file_type']
                analysis['file_types'][ext] = analysis['file_types'].get(ext, 0) + 1
        
        return analysis
    
    def _infer_file_role(self, file_name: str, relative_path: str) -> str:
        """
        ファイルの役割を推定
        
        Args:
            file_name: ファイル名
            relative_path: 相対パス
        
        Returns:
            ファイルの役割
        """
        file_name_lower = file_name.lower()
        
        # README系
        if 'readme' in file_name_lower:
            return 'documentation'
        
        # データファイル
        if file_name_lower in ['train.csv', 'test.csv', 'validation.csv']:
            return 'main_data'
        
        # メタデータ
        if 'metadata' in file_name_lower or 'meta' in file_name_lower:
            return 'metadata'
        
        # 設定ファイル
        if file_name_lower.endswith(('.json', '.yaml', '.yml', '.config')):
            return 'configuration'
        
        # ドキュメント
        if file_name_lower.endswith(('.md', '.txt', '.pdf', '.doc', '.docx')):
            return 'documentation'
        
        # データファイル
        if file_name_lower.endswith(('.csv', '.jsonl', '.tsv', '.parquet')):
            return 'data'
        
        # 画像・媒体ファイル
        if file_name_lower.endswith(('.jpg', '.jpeg', '.png', '.gif', '.mp4', '.wav')):
            return 'media'
        
        return 'other'
    
    def _generate_llm_analysis(self, directory_analysis: Dict[str, Any], 
                              custom_description: str = None) -> Dict[str, Any]:
        """
        LLMによるデータセットの自動分析
        
        Args:
            directory_analysis: ディレクトリ分析結果
            custom_description: カスタム説明
        
        Returns:
            LLM分析結果
        """
        if not self.gemini_analyzer.is_available():
            # LLMが利用できない場合のフォールバック
            return {
                'description': custom_description or 'データセットの説明が生成できませんでした',
                'tags': ['dataset'],
                'research_field': '不明',
                'data_type': 'dataset',
                'summary': 'LLM分析が利用できません',
                'llm_tags': [],
                'quality_score': 0.5,
                'complexity': 'moderate'
            }
        
        try:
            # プロンプトの構築
            prompt = self._build_dataset_analysis_prompt(directory_analysis, custom_description)
            
            # Gemini APIの呼び出し
            response = self.gemini_analyzer.model.generate_content(prompt)
            
            # レスポンスの解析
            return self._parse_dataset_analysis_response(response.text)
            
        except Exception as e:
            print(f"LLM分析エラー: {e}")
            return {
                'description': custom_description or 'データセットの自動分析に失敗しました',
                'tags': ['dataset'],
                'research_field': '不明',
                'data_type': 'dataset',
                'summary': f'分析エラー: {str(e)}',
                'llm_tags': [],
                'quality_score': 0.5,
                'complexity': 'moderate'
            }
    
    def _build_dataset_analysis_prompt(self, directory_analysis: Dict[str, Any], 
                                     custom_description: str = None) -> str:
        """
        データセット分析用のプロンプトを構築
        
        Args:
            directory_analysis: ディレクトリ分析結果
            custom_description: カスタム説明
        
        Returns:
            プロンプト文字列
        """
        # ファイル構造の要約
        file_summary = []
        for file_info in directory_analysis['files'][:20]:  # 最初の20ファイルのみ
            file_summary.append({
                'name': file_info['file_name'],
                'type': file_info['file_type'],
                'role': file_info['role'],
                'size_mb': round(file_info['file_size'] / (1024 * 1024), 2),
                'preview': file_info.get('content_preview', '')[:200]
            })
        
        custom_desc_text = f"\nユーザー提供の説明: {custom_description}" if custom_description else ""
        
        prompt = f"""
以下のディレクトリ構造とファイル内容を分析して、データセットの情報を生成してください：

ディレクトリパス: {directory_analysis['directory_path']}
総ファイル数: {directory_analysis['file_count']}
総サイズ: {round(directory_analysis['total_size'] / (1024 * 1024), 2)} MB
ファイル拡張子別統計: {directory_analysis['file_types']}{custom_desc_text}

ファイル詳細（最初の20件）:
{json.dumps(file_summary, ensure_ascii=False, indent=2)}

以下の形式でJSON応答を生成してください：

{{
  "description": "データセットの1行説明（例：JBBQ - 日本語質問応答ベンチマークデータセット、年齢・性別・障害状況等の属性情報を含む）",
  "summary": "データセットの短い要約（50文字以内）",
  "research_field": "研究分野（機械学習、自然言語処理、データサイエンス、コンピュータビジョン、医療AI、ロボティクス、バイオインフォマティクス、統計学、経済学など）",
  "data_type": "データタイプ（dataset、training_data、test_data、benchmark、survey_dataなど）",
  "tags": ["主要なタグ1", "主要なタグ2", "主要なタグ3"],
  "llm_tags": ["LLMが推奨する検索用タグ1", "LLMが推奨する検索用タグ2", "LLMが推奨する検索用タグ3"],
  "quality_score": 0.8,
  "complexity": "simple/moderate/complex",
  "potential_use_cases": ["利用用途1", "利用用途2", "利用用途3"]
}}

重要な指示：
- descriptionは必ず1行で、データセットの内容が明確に分かる説明にしてください
- ファイル名から内容を推測し、具体的で検索しやすい説明を作成してください
- 例：「ESGレポート分析データセット - 企業の環境・社会・ガバナンス情報を含むPDFファイル集」
"""
        return prompt
    
    def _parse_dataset_analysis_response(self, response_text: str) -> Dict[str, Any]:
        """
        データセット分析レスポンスを解析
        
        Args:
            response_text: レスポンステキスト
        
        Returns:
            解析結果
        """
        json_data = self.gemini_analyzer._extract_json_from_text(response_text)
        
        if not json_data:
            return {
                'description': 'データセット分析の解析に失敗しました',
                'tags': ['dataset'],
                'research_field': '不明',
                'data_type': 'dataset',
                'summary': 'LLM応答の解析エラー',
                'llm_tags': [],
                'quality_score': 0.5,
                'complexity': 'moderate'
            }
        
        # データの正規化
        result = {
            'description': str(json_data.get('description', ''))[:500],
            'summary': str(json_data.get('summary', ''))[:200],
            'research_field': str(json_data.get('research_field', '不明')),
            'data_type': str(json_data.get('data_type', 'dataset')),
            'tags': json_data.get('tags', [])[:10],
            'llm_tags': json_data.get('llm_tags', [])[:10],
            'quality_score': float(json_data.get('quality_score', 0.5)),
            'complexity': str(json_data.get('complexity', 'moderate')),
            'potential_use_cases': json_data.get('potential_use_cases', [])[:5]
        }
        
        return result
    
    def _generate_dataset_id(self, directory_path: str) -> str:
        """データセットIDを生成"""
        # ディレクトリパスからハッシュを生成
        hash_object = hashlib.md5(directory_path.encode())
        return f"ds_{hash_object.hexdigest()[:12]}"
    
    def _save_dataset(self, dataset_info: Dict[str, Any], files: List[Dict[str, Any]]):
        """
        データセット情報をデータベースに保存
        
        Args:
            dataset_info: データセット情報
            files: ファイル情報リスト
        """
        with self.db_handler.get_connection() as conn:
            cursor = conn.cursor()
            
            # データセット情報の保存
            cursor.execute("""
                INSERT OR REPLACE INTO datasets 
                (dataset_id, name, directory_path, description, tags, research_field, 
                 data_type, file_count, total_size, llm_generated_summary, 
                 llm_generated_tags, quality_score, complexity_level, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                dataset_info['dataset_id'],
                dataset_info['name'],
                dataset_info['directory_path'],
                dataset_info['description'],
                dataset_info['tags'],
                dataset_info['research_field'],
                dataset_info['data_type'],
                dataset_info['file_count'],
                dataset_info['total_size'],
                dataset_info['llm_generated_summary'],
                dataset_info['llm_generated_tags'],
                dataset_info['quality_score'],
                dataset_info['complexity_level'],
                datetime.now().isoformat()
            ))
            
            # 既存のファイル情報を削除
            cursor.execute("DELETE FROM dataset_files WHERE dataset_id = ?", 
                         (dataset_info['dataset_id'],))
            
            # ファイル情報の保存
            for file_info in files:
                file_id = f"{dataset_info['dataset_id']}_{hashlib.md5(file_info['file_path'].encode()).hexdigest()[:8]}"
                
                cursor.execute("""
                    INSERT INTO dataset_files 
                    (file_id, dataset_id, file_path, file_name, file_type, 
                     file_size, role, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    file_id,
                    dataset_info['dataset_id'],
                    file_info['file_path'],
                    file_info['file_name'],
                    file_info['file_type'],
                    file_info['file_size'],
                    file_info['role'],
                    file_info.get('content_preview', '')[:500]
                ))
            
            conn.commit()
    
    def search_datasets(self, query: str = "", 
                       research_field: str = None,
                       data_type: str = None,
                       tags: List[str] = None,
                       limit: int = 20) -> List[Dict[str, Any]]:
        """
        データセットを検索
        
        Args:
            query: 検索クエリ
            research_field: 研究分野
            data_type: データタイプ
            tags: タグリスト
            limit: 取得件数
        
        Returns:
            検索結果
        """
        with self.db_handler.get_connection() as conn:
            cursor = conn.cursor()
            
            sql = "SELECT * FROM datasets WHERE 1=1"
            params = []
            
            if query:
                sql += " AND (name LIKE ? OR description LIKE ? OR llm_generated_summary LIKE ?)"
                query_pattern = f"%{query}%"
                params.extend([query_pattern, query_pattern, query_pattern])
            
            if research_field:
                sql += " AND research_field LIKE ?"
                params.append(f"%{research_field}%")
            
            if data_type:
                sql += " AND data_type = ?"
                params.append(data_type)
            
            if tags:
                for tag in tags:
                    sql += " AND (tags LIKE ? OR llm_generated_tags LIKE ?)"
                    tag_pattern = f"%{tag}%"
                    params.extend([tag_pattern, tag_pattern])
            
            sql += " ORDER BY updated_at DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(sql, params)
            
            results = []
            for row in cursor.fetchall():
                dataset = dict(row)
                # JSONフィールドをパース
                if dataset.get('tags'):
                    dataset['tags'] = json.loads(dataset['tags'])
                if dataset.get('llm_generated_tags'):
                    dataset['llm_generated_tags'] = json.loads(dataset['llm_generated_tags'])
                
                results.append(dataset)
            
            return results
    
    def get_dataset_by_id(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """
        データセットIDでデータセットを取得
        
        Args:
            dataset_id: データセットID
        
        Returns:
            データセット情報
        """
        with self.db_handler.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM datasets WHERE dataset_id = ?", (dataset_id,))
            row = cursor.fetchone()
            
            if row:
                dataset = dict(row)
                # JSONフィールドをパース
                if dataset.get('tags'):
                    dataset['tags'] = json.loads(dataset['tags'])
                if dataset.get('llm_generated_tags'):
                    dataset['llm_generated_tags'] = json.loads(dataset['llm_generated_tags'])
                
                # ファイル情報も取得
                cursor.execute("SELECT * FROM dataset_files WHERE dataset_id = ?", (dataset_id,))
                dataset['files'] = [dict(file_row) for file_row in cursor.fetchall()]
                
                return dataset
            
            return None
    
    def update_dataset_tags(self, dataset_id: str, new_tags: List[str]) -> Dict[str, Any]:
        """
        データセットのタグを更新
        
        Args:
            dataset_id: データセットID
            new_tags: 新しいタグリスト
        
        Returns:
            更新結果
        """
        try:
            with self.db_handler.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE datasets 
                    SET tags = ?, updated_at = ?
                    WHERE dataset_id = ?
                """, (
                    json.dumps(new_tags, ensure_ascii=False),
                    datetime.now().isoformat(),
                    dataset_id
                ))
                
                if cursor.rowcount > 0:
                    conn.commit()
                    return {
                        'success': True,
                        'message': 'タグを更新しました'
                    }
                else:
                    return {
                        'success': False,
                        'error': 'データセットが見つかりません'
                    }
                    
        except Exception as e:
            return {
                'success': False,
                'error': f'タグ更新エラー: {str(e)}'
            }
    
    def get_all_tags(self) -> List[str]:
        """
        全データセットのタグを取得
        
        Returns:
            タグリスト
        """
        with self.db_handler.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT tags, llm_generated_tags FROM datasets")
            
            all_tags = set()
            for row in cursor.fetchall():
                # ユーザータグ
                if row['tags']:
                    try:
                        tags = json.loads(row['tags'])
                        all_tags.update(tags)
                    except:
                        pass
                
                # LLM生成タグ
                if row['llm_generated_tags']:
                    try:
                        llm_tags = json.loads(row['llm_generated_tags'])
                        all_tags.update(llm_tags)
                    except:
                        pass
            
            return sorted(list(all_tags))