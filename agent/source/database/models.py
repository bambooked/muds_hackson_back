from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any
import json


@dataclass
class File:
    """ファイル情報を表すデータクラス"""
    id: Optional[int] = None
    file_path: str = ""
    file_name: str = ""
    file_type: str = ""
    category: str = ""
    file_size: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    indexed_at: Optional[datetime] = None
    summary: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    content_hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "id": self.id,
            "file_path": self.file_path,
            "file_name": self.file_name,
            "file_type": self.file_type,
            "category": self.category,
            "file_size": self.file_size,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "indexed_at": self.indexed_at.isoformat() if self.indexed_at else None,
            "summary": self.summary,
            "metadata": json.dumps(self.metadata) if self.metadata else None,
            "content_hash": self.content_hash
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "File":
        """辞書から作成"""
        if data.get("created_at"):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        if data.get("indexed_at"):
            data["indexed_at"] = datetime.fromisoformat(data["indexed_at"])
        if data.get("metadata") and isinstance(data["metadata"], str):
            data["metadata"] = json.loads(data["metadata"])
        return cls(**data)


@dataclass
class ResearchTopic:
    """研究トピック情報を表すデータクラス"""
    id: Optional[int] = None
    file_id: int = 0
    topic: str = ""
    relevance_score: float = 0.0
    keywords: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "id": self.id,
            "file_id": self.file_id,
            "topic": self.topic,
            "relevance_score": self.relevance_score,
            "keywords": self.keywords
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResearchTopic":
        """辞書から作成"""
        return cls(**data)


@dataclass
class AnalysisResult:
    """解析結果を表すデータクラス"""
    id: Optional[int] = None
    file_id: int = 0
    analysis_type: str = ""
    result_data: str = ""
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "id": self.id,
            "file_id": self.file_id,
            "analysis_type": self.analysis_type,
            "result_data": self.result_data,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnalysisResult":
        """辞書から作成"""
        if data.get("created_at"):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        return cls(**data)