"""
Topic repository for Project Nexus.
Manages hierarchical topic nodes.
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from core.logger import get_logger
from db.models import TopicNode

logger = get_logger(__name__)


class TopicRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_root(self) -> Optional[TopicNode]:
        return self.db.query(TopicNode).filter(
            TopicNode.parent_id.is_(None)
        ).first()

    def get_children(self, parent_id: str) -> List[TopicNode]:
        return self.db.query(TopicNode).filter(
            TopicNode.parent_id == parent_id
        ).all()

    def get_by_id(self, topic_id: str) -> Optional[TopicNode]:
        return self.db.query(TopicNode).filter(
            TopicNode.id == topic_id
        ).first()

    def get_by_doc_id(self, doc_id: str) -> Optional[TopicNode]:
        return self.db.query(TopicNode).filter(
            TopicNode.doc_id == doc_id
        ).first()

    def create(
        self,
        name: str,
        parent_id: Optional[str],
        level: int,
        path: str,
        doc_id: Optional[str] = None,
        embedding: Optional[List[float]] = None
    ) -> TopicNode:
        node = TopicNode(
            name=name,
            parent_id=parent_id,
            level=level,
            path=path,
            doc_id=doc_id,
            embedding=embedding
        )
        self.db.add(node)
        self.db.flush()
        logger.info(
            "topic_node_created",
            topic_id=node.id,
            name=name,
            level=level,
            parent_id=parent_id,
            doc_id=doc_id
        )
        return node

    def delete_by_doc_id(self, doc_id: str) -> int:
        count = self.db.query(TopicNode).filter(
            TopicNode.doc_id == doc_id
        ).delete(synchronize_session=False)
        self.db.flush()
        if count:
            logger.info("topic_node_deleted", doc_id=doc_id)
        return count

    def delete_all(self) -> int:
        count = self.db.query(TopicNode).delete(synchronize_session=False)
        self.db.flush()
        logger.info("topic_nodes_deleted_all", count=count)
        return count
