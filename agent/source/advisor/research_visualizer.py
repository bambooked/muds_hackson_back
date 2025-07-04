"""
研究テーマ構造化・可視化機能
研究アイディアの構造化、関係性の可視化、研究計画の視覚的表現
"""

from typing import Dict, Any, List, Optional, Tuple
import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ResearchVisualizer:
    """研究テーマ構造化・可視化機能を提供するクラス"""
    
    def __init__(self):
        self.research_structures = {}  # 構造化された研究テーマの保存
    
    def structure_research_theme(self, research_query: str, context_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """研究テーマを構造化"""
        try:
            # 研究テーマの基本構造を作成
            structure = {
                "theme_id": self._generate_theme_id(research_query),
                "original_query": research_query,
                "created_at": datetime.now().isoformat(),
                "structure": {
                    "research_question": self._extract_research_question(research_query),
                    "domain": self._identify_research_domain(research_query),
                    "methodology": self._suggest_methodology(research_query),
                    "objectives": self._define_objectives(research_query),
                    "scope": self._define_scope(research_query),
                    "variables": self._identify_variables(research_query),
                    "theoretical_framework": self._suggest_theoretical_framework(research_query)
                },
                "relationships": self._analyze_component_relationships(research_query),
                "visualization_data": self._prepare_visualization_data(research_query),
                "context": context_data or {}
            }
            
            # 構造化データを保存
            self.research_structures[structure["theme_id"]] = structure
            
            return structure
            
        except Exception as e:
            logger.error(f"研究テーマ構造化エラー: {e}")
            return {
                "error": "研究テーマの構造化に失敗しました",
                "details": str(e)
            }
    
    def _generate_theme_id(self, query: str) -> str:
        """研究テーマIDを生成"""
        import hashlib
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        query_hash = hashlib.md5(query.encode()).hexdigest()[:8]
        return f"theme_{timestamp}_{query_hash}"
    
    def _extract_research_question(self, query: str) -> Dict[str, Any]:
        """研究課題を抽出・明確化"""
        # キーワード分析
        keywords = self._extract_keywords(query)
        
        # 疑問詞の検出
        question_words = ["何", "なぜ", "どのように", "いつ", "どこで", "誰が", "どの程度"]
        has_question_word = any(word in query for word in question_words)
        
        # 研究課題の構造化
        return {
            "primary_question": query if has_question_word else f"「{query}」に関する研究課題は何か？",
            "sub_questions": self._generate_sub_questions(query, keywords),
            "question_type": self._classify_question_type(query),
            "clarity_level": "high" if has_question_word else "medium",
            "keywords": keywords
        }
    
    def _extract_keywords(self, text: str) -> List[str]:
        """キーワードを抽出（簡易版）"""
        # 基本的なキーワード抽出
        import re
        
        # 日本語と英語のキーワードを抽出
        japanese_keywords = re.findall(r'[あ-ん]{2,}|[ア-ン]{2,}|[一-龯]{2,}', text)
        english_keywords = re.findall(r'[A-Za-z]{3,}', text)
        
        # 一般的でない単語をフィルタリング
        common_words = ["について", "に関する", "である", "です", "ます", "こと", "もの", "the", "and", "of", "to", "in"]
        
        keywords = []
        for keyword in japanese_keywords + english_keywords:
            if keyword.lower() not in common_words and len(keyword) >= 2:
                keywords.append(keyword)
        
        return list(set(keywords))[:10]  # 上位10個
    
    def _generate_sub_questions(self, main_query: str, keywords: List[str]) -> List[str]:
        """サブクエスチョンを生成"""
        sub_questions = []
        
        # キーワードベースのサブクエスチョン
        for keyword in keywords[:3]:
            sub_questions.extend([
                f"{keyword}の定義と特徴は何か？",
                f"{keyword}にはどのような要因が影響するか？",
                f"{keyword}を測定する方法は何か？"
            ])
        
        # 汎用的なサブクエスチョン
        sub_questions.extend([
            "先行研究では何が明らかになっているか？",
            "現在の理論的枠組みは何か？",
            "実証的な検証は可能か？"
        ])
        
        return sub_questions[:5]  # 上位5個
    
    def _classify_question_type(self, query: str) -> str:
        """質問タイプを分類"""
        if any(word in query for word in ["効果", "影響", "関係", "相関"]):
            return "因果関係・効果分析"
        elif any(word in query for word in ["分類", "カテゴリ", "タイプ"]):
            return "分類・カテゴリ分析"
        elif any(word in query for word in ["予測", "予想", "将来"]):
            return "予測・予想分析"
        elif any(word in query for word in ["比較", "違い", "差"]):
            return "比較分析"
        elif any(word in query for word in ["なぜ", "理由", "原因"]):
            return "説明・理由分析"
        else:
            return "記述・探索的分析"
    
    def _identify_research_domain(self, query: str) -> Dict[str, Any]:
        """研究領域を特定"""
        domains = {
            "computer_science": ["AI", "機械学習", "アルゴリズム", "プログラミング", "データ", "システム"],
            "business": ["経営", "マーケティング", "企業", "ビジネス", "戦略", "組織"],
            "psychology": ["心理", "認知", "行動", "感情", "学習", "発達"],
            "sociology": ["社会", "集団", "文化", "コミュニティ", "制度", "社会学"],
            "economics": ["経済", "市場", "価格", "金融", "投資", "消費"],
            "environment": ["環境", "気候", "生態", "持続可能", "エネルギー", "汚染"],
            "education": ["教育", "学習", "指導", "カリキュラム", "学校", "授業"],
            "health": ["健康", "医療", "病気", "治療", "予防", "ヘルスケア"]
        }
        
        query_lower = query.lower()
        domain_scores = {}
        
        for domain, keywords in domains.items():
            score = sum(1 for keyword in keywords if keyword in query_lower)
            if score > 0:
                domain_scores[domain] = score
        
        if domain_scores:
            primary_domain = max(domain_scores, key=domain_scores.get)
            return {
                "primary": primary_domain,
                "secondary": [domain for domain, score in domain_scores.items() if domain != primary_domain],
                "confidence": domain_scores[primary_domain] / len(domains[primary_domain])
            }
        else:
            return {
                "primary": "interdisciplinary",
                "secondary": [],
                "confidence": 0.1
            }
    
    def _suggest_methodology(self, query: str) -> Dict[str, Any]:
        """研究手法を提案"""
        methodologies = {
            "quantitative": {
                "methods": ["統計分析", "実験計画法", "回帰分析", "因子分析"],
                "keywords": ["測定", "統計", "数値", "データ", "分析", "実験"]
            },
            "qualitative": {
                "methods": ["インタビュー", "観察法", "事例研究", "エスノグラフィー"],
                "keywords": ["理解", "解釈", "質的", "事例", "インタビュー", "観察"]
            },
            "mixed": {
                "methods": ["混合研究法", "順次説明戦略", "並行三角測量"],
                "keywords": ["混合", "複合", "多角的", "総合的"]
            },
            "theoretical": {
                "methods": ["文献レビュー", "理論構築", "メタ分析"],
                "keywords": ["理論", "概念", "モデル", "フレームワーク"]
            }
        }
        
        query_lower = query.lower()
        method_scores = {}
        
        for method_type, info in methodologies.items():
            score = sum(1 for keyword in info["keywords"] if keyword in query_lower)
            if score > 0:
                method_scores[method_type] = score
        
        # デフォルトの提案
        if not method_scores:
            method_scores["mixed"] = 1
        
        primary_method = max(method_scores, key=method_scores.get)
        
        return {
            "primary_approach": primary_method,
            "suggested_methods": methodologies[primary_method]["methods"],
            "alternative_approaches": [method for method in method_scores.keys() if method != primary_method],
            "rationale": f"「{query}」の内容に基づいて{primary_method}アプローチを推奨"
        }
    
    def _define_objectives(self, query: str) -> Dict[str, Any]:
        """研究目的を定義"""
        objectives = {
            "primary": f"「{query}」に関する理解を深める",
            "secondary": [
                "既存の知識体系への貢献",
                "実践的な応用可能性の検討",
                "理論的枠組みの拡張"
            ],
            "measurable_outcomes": [
                "研究課題に対する明確な答えの提示",
                "新しい知見や洞察の発見",
                "実証的データに基づく結論"
            ]
        }
        
        return objectives
    
    def _define_scope(self, query: str) -> Dict[str, Any]:
        """研究範囲を定義"""
        return {
            "temporal_scope": "未定義（研究期間の明確化が必要）",
            "geographical_scope": "未定義（対象地域の明確化が必要）",
            "population_scope": "未定義（対象母集団の明確化が必要）",
            "conceptual_boundaries": f"「{query}」に直接関連する概念と現象",
            "limitations": [
                "データの利用可能性による制約",
                "時間的・資源的制約",
                "既存研究の制限事項"
            ],
            "inclusion_criteria": "研究目的に直接関連する要素",
            "exclusion_criteria": "研究範囲外の周辺的要素"
        }
    
    def _identify_variables(self, query: str) -> Dict[str, Any]:
        """変数を特定"""
        keywords = self._extract_keywords(query)
        
        return {
            "dependent_variables": [f"{keywords[0]} (結果変数)" if keywords else "未特定"],
            "independent_variables": [f"{keyword} (説明変数)" for keyword in keywords[1:3]] if len(keywords) > 1 else ["未特定"],
            "control_variables": ["年齢", "性別", "その他の人口統計学的変数"],
            "moderating_variables": ["未特定（追加調査が必要）"],
            "mediating_variables": ["未特定（理論的検討が必要）"],
            "measurement_scales": "研究設計時に決定"
        }
    
    def _suggest_theoretical_framework(self, query: str) -> Dict[str, Any]:
        """理論的枠組みを提案"""
        domain = self._identify_research_domain(query)
        
        frameworks = {
            "computer_science": ["情報処理理論", "システム理論", "認知科学理論"],
            "business": ["組織理論", "戦略理論", "マーケティング理論"],
            "psychology": ["認知理論", "行動理論", "発達理論"],
            "sociology": ["社会システム理論", "社会構築主義", "制度理論"],
            "economics": ["市場理論", "ゲーム理論", "行動経済学"],
            "environment": ["生態系理論", "持続可能性理論", "環境心理学"],
            "interdisciplinary": ["システム理論", "複雑性理論", "学際的アプローチ"]
        }
        
        primary_domain = domain.get("primary", "interdisciplinary")
        suggested_frameworks = frameworks.get(primary_domain, frameworks["interdisciplinary"])
        
        return {
            "primary_theories": suggested_frameworks,
            "theoretical_gaps": "文献レビューで特定する必要あり",
            "conceptual_model": "理論的枠組みに基づいて構築",
            "hypotheses": "理論に基づいて仮説を設定",
            "literature_review_focus": f"{primary_domain}分野の主要理論"
        }
    
    def _analyze_component_relationships(self, query: str) -> Dict[str, Any]:
        """コンポーネント間の関係を分析"""
        return {
            "research_question_methodology": "研究課題が手法選択を決定",
            "domain_theory": "研究領域が理論的枠組みを規定",
            "objectives_scope": "研究目的が研究範囲を制限",
            "variables_measurement": "変数が測定方法を決定",
            "theory_hypotheses": "理論が仮説を導出",
            "relationship_strength": {
                "strong": ["研究課題-手法", "領域-理論"],
                "moderate": ["目的-範囲", "変数-測定"],
                "weak": ["理論-仮説（要検討）"]
            }
        }
    
    def _prepare_visualization_data(self, query: str) -> Dict[str, Any]:
        """可視化用データを準備"""
        keywords = self._extract_keywords(query)
        
        # ノードとエッジの定義（グラフ構造用）
        nodes = [
            {"id": "research_question", "label": "研究課題", "type": "primary", "size": 20},
            {"id": "methodology", "label": "研究手法", "type": "method", "size": 15},
            {"id": "theory", "label": "理論的枠組み", "type": "theory", "size": 15},
            {"id": "objectives", "label": "研究目的", "type": "goal", "size": 12},
            {"id": "scope", "label": "研究範囲", "type": "boundary", "size": 12},
            {"id": "variables", "label": "変数", "type": "variable", "size": 10}
        ]
        
        # キーワードノードを追加
        for i, keyword in enumerate(keywords[:5]):
            nodes.append({
                "id": f"keyword_{i}",
                "label": keyword,
                "type": "keyword",
                "size": 8
            })
        
        edges = [
            {"from": "research_question", "to": "methodology", "weight": 3},
            {"from": "research_question", "to": "theory", "weight": 2},
            {"from": "research_question", "to": "objectives", "weight": 3},
            {"from": "objectives", "to": "scope", "weight": 2},
            {"from": "methodology", "to": "variables", "weight": 2},
            {"from": "theory", "to": "variables", "weight": 1}
        ]
        
        # キーワードとのエッジ
        for i in range(min(5, len(keywords))):
            edges.append({
                "from": "research_question",
                "to": f"keyword_{i}",
                "weight": 1
            })
        
        return {
            "graph": {
                "nodes": nodes,
                "edges": edges
            },
            "timeline": self._create_research_timeline(),
            "hierarchy": self._create_concept_hierarchy(keywords),
            "matrix": self._create_relationship_matrix()
        }
    
    def _create_research_timeline(self) -> List[Dict[str, Any]]:
        """研究タイムラインを作成"""
        start_date = datetime.now()
        
        phases = [
            {"phase": "文献調査", "duration": 3, "description": "既存研究の調査と理論的背景の理解"},
            {"phase": "研究設計", "duration": 2, "description": "研究方法と計画の詳細化"},
            {"phase": "データ収集", "duration": 4, "description": "実証データの収集"},
            {"phase": "データ分析", "duration": 3, "description": "収集データの分析と解釈"},
            {"phase": "結果検討", "duration": 2, "description": "結果の解釈と議論"},
            {"phase": "論文執筆", "duration": 4, "description": "研究成果の文書化"}
        ]
        
        timeline = []
        current_date = start_date
        
        for phase in phases:
            end_date = current_date + timedelta(weeks=phase["duration"])
            timeline.append({
                "phase": phase["phase"],
                "start_date": current_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "duration_weeks": phase["duration"],
                "description": phase["description"]
            })
            current_date = end_date
        
        return timeline
    
    def _create_concept_hierarchy(self, keywords: List[str]) -> Dict[str, Any]:
        """概念階層を作成"""
        return {
            "root": "研究テーマ",
            "level1": keywords[:2] if len(keywords) >= 2 else ["主要概念"],
            "level2": keywords[2:5] if len(keywords) >= 5 else ["副次概念"],
            "level3": keywords[5:] if len(keywords) > 5 else ["関連概念"]
        }
    
    def _create_relationship_matrix(self) -> List[List[float]]:
        """関係性マトリックスを作成"""
        # 簡易的な関係性マトリックス（6x6）
        components = ["research_question", "methodology", "theory", "objectives", "scope", "variables"]
        matrix = []
        
        # 予定義された関係性スコア
        predefined_relationships = {
            (0, 1): 0.9,  # research_question - methodology
            (0, 2): 0.7,  # research_question - theory
            (0, 3): 0.8,  # research_question - objectives
            (1, 5): 0.6,  # methodology - variables
            (2, 5): 0.5,  # theory - variables
            (3, 4): 0.7   # objectives - scope
        }
        
        for i in range(len(components)):
            row = []
            for j in range(len(components)):
                if i == j:
                    row.append(1.0)  # 自己関係は1.0
                elif (i, j) in predefined_relationships:
                    row.append(predefined_relationships[(i, j)])
                elif (j, i) in predefined_relationships:
                    row.append(predefined_relationships[(j, i)])
                else:
                    row.append(0.1)  # デフォルトの低い関係性
            matrix.append(row)
        
        return matrix
    
    def generate_visual_summary(self, theme_id: str) -> Dict[str, Any]:
        """視覚的サマリーを生成"""
        if theme_id not in self.research_structures:
            return {"error": "指定された研究テーマが見つかりません"}
        
        structure = self.research_structures[theme_id]
        
        return {
            "theme_id": theme_id,
            "summary_type": "visual",
            "components": {
                "overview": {
                    "title": structure["structure"]["research_question"]["primary_question"],
                    "domain": structure["structure"]["domain"]["primary"],
                    "methodology": structure["structure"]["methodology"]["primary_approach"],
                    "complexity": self._assess_complexity(structure)
                },
                "key_relationships": structure["relationships"]["relationship_strength"],
                "timeline_summary": {
                    "total_duration": f"{sum(phase['duration_weeks'] for phase in structure['visualization_data']['timeline'])}週間",
                    "critical_phases": ["文献調査", "データ収集", "データ分析"]
                },
                "visualization_elements": {
                    "primary_nodes": len([n for n in structure["visualization_data"]["graph"]["nodes"] if n["type"] == "primary"]),
                    "total_connections": len(structure["visualization_data"]["graph"]["edges"]),
                    "hierarchy_levels": len(structure["visualization_data"]["hierarchy"]) - 1
                }
            },
            "generated_at": datetime.now().isoformat()
        }
    
    def _assess_complexity(self, structure: Dict[str, Any]) -> str:
        """研究の複雑性を評価"""
        complexity_factors = [
            len(structure["structure"]["variables"]["independent_variables"]),
            len(structure["structure"]["methodology"]["suggested_methods"]),
            len(structure["structure"]["theoretical_framework"]["primary_theories"]),
            len(structure["visualization_data"]["graph"]["nodes"])
        ]
        
        total_complexity = sum(complexity_factors)
        
        if total_complexity < 10:
            return "低"
        elif total_complexity < 20:
            return "中"
        else:
            return "高"
    
    def export_structure(self, theme_id: str, format_type: str = "json") -> Optional[str]:
        """構造化データをエクスポート"""
        if theme_id not in self.research_structures:
            return None
        
        structure = self.research_structures[theme_id]
        
        if format_type == "json":
            return json.dumps(structure, ensure_ascii=False, indent=2)
        elif format_type == "summary":
            return self._create_text_summary(structure)
        else:
            return None
    
    def _create_text_summary(self, structure: Dict[str, Any]) -> str:
        """テキストサマリーを作成"""
        summary_parts = []
        
        summary_parts.append(f"# 研究テーマ構造化サマリー")
        summary_parts.append(f"**作成日時**: {structure['created_at']}")
        summary_parts.append(f"**元クエリ**: {structure['original_query']}")
        summary_parts.append("")
        
        summary_parts.append("## 研究課題")
        summary_parts.append(f"- **主要課題**: {structure['structure']['research_question']['primary_question']}")
        summary_parts.append(f"- **課題タイプ**: {structure['structure']['research_question']['question_type']}")
        summary_parts.append("")
        
        summary_parts.append("## 研究領域・手法")
        summary_parts.append(f"- **主要領域**: {structure['structure']['domain']['primary']}")
        summary_parts.append(f"- **推奨手法**: {structure['structure']['methodology']['primary_approach']}")
        summary_parts.append("")
        
        summary_parts.append("## 研究目的")
        summary_parts.append(f"- **主目的**: {structure['structure']['objectives']['primary']}")
        
        return "\n".join(summary_parts)
    
    def get_all_structures(self) -> List[Dict[str, Any]]:
        """すべての構造化データの概要を取得"""
        return [
            {
                "theme_id": theme_id,
                "original_query": structure["original_query"],
                "created_at": structure["created_at"],
                "domain": structure["structure"]["domain"]["primary"],
                "methodology": structure["structure"]["methodology"]["primary_approach"]
            }
            for theme_id, structure in self.research_structures.items()
        ]