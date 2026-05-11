"""
Topic service for Nexus.
Builds and queries a hierarchical topic tree.
"""

import re
from typing import Dict, List, Optional

import numpy as np

from core.config import get_settings
from core.logger import get_logger
from db.repositories.topic_repo import TopicRepository
from ingestion.embedder import embedding_model

logger = get_logger(__name__)
settings = get_settings()


class TopicService:
    def __init__(self, db):
        self.db = db
        self.repo = TopicRepository(db)

    def ensure_root(self) -> str:
        root = self.repo.get_root()
        if root:
            return root.id

        root = self.repo.create(
            name="root",
            parent_id=None,
            level=0,
            path="root"
        )
        return root.id

    def build_for_document(
        self,
        doc_id: str,
        original_filename: str,
        text: str
    ) -> Dict[str, List[str]]:
        root_id = self.ensure_root()
        topic_label = self._derive_topic_label(original_filename, text)
        topic_node = self._find_or_create_topic(root_id, topic_label)
        doc_node = self._create_doc_node(topic_node, doc_id, original_filename)

        ancestors = [root_id, topic_node.id, doc_node.id]
        return {
            "doc_topic_id": doc_node.id,
            "topic_ancestors": ancestors
        }

    def resolve_query_topic(self, question: str) -> Optional[str]:
        root = self.repo.get_root()
        if not root:
            return None

        topics = self.repo.get_children(root.id)
        if not topics:
            return None

        query_vec = np.array(
            embedding_model.embed_text(question),
            dtype=np.float32
        )

        best_id = None
        best_score = 0.0
        for t in topics:
            if not t.embedding:
                t.embedding = embedding_model.embed_text(t.name)
                self.db.flush()
            t_vec = np.array(t.embedding, dtype=np.float32)
            score = float(np.dot(query_vec, t_vec))
            if score > best_score:
                best_score = score
                best_id = t.id

        if best_id and best_score >= settings.QUERY_TOPIC_THRESHOLD:
            logger.info(
                "query_topic_resolved",
                topic_id=best_id,
                score=round(best_score, 4)
            )
            return best_id

        return None

    def delete_by_doc_id(self, doc_id: str) -> int:
        return self.repo.delete_by_doc_id(doc_id)

    def clear_all(self) -> int:
        return self.repo.delete_all()

    def _find_or_create_topic(self, root_id: str, label: str):
        topics = self.repo.get_children(root_id)
        label_vec = np.array(
            embedding_model.embed_text(label),
            dtype=np.float32
        )

        best = None
        best_score = 0.0
        for t in topics:
            if not t.embedding:
                continue
            t_vec = np.array(t.embedding, dtype=np.float32)
            score = float(np.dot(label_vec, t_vec))
            if score > best_score:
                best_score = score
                best = t

        if best and best_score >= settings.TOPIC_SIM_THRESHOLD:
            return best

        topic = self.repo.create(
            name=label,
            parent_id=root_id,
            level=1,
            path="root"
        )
        topic.path = f"root/{topic.id}"
        topic.embedding = label_vec.tolist()
        self.db.flush()
        return topic

    def _create_doc_node(self, parent_topic, doc_id: str, name: str):
        node = self.repo.create(
            name=name,
            parent_id=parent_topic.id,
            level=2,
            path=f"{parent_topic.path}/{doc_id}",
            doc_id=doc_id
        )
        return node

    def _derive_topic_label(self, filename: str, text: str) -> str:
        base = self._clean_filename(filename)
        if not text:
            return base

        lines = [l.strip() for l in text.splitlines() if l.strip()]
        for line in lines[:15]:
            if 3 <= len(line.split()) <= 10 and line.isprintable():
                return line

        return base

    def _clean_filename(self, filename: str) -> str:
        name = re.sub(r"\.[^.]+$", "", filename)
        name = re.sub(r"[_\-]+", " ", name)
        name = re.sub(r"\s+", " ", name).strip()
        return name or "document"
