"""Pydantic models for API responses."""

from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class EntityResponse(BaseModel):
    """Entity model for API responses."""

    id: str
    name: Optional[str] = None
    jurisdiction: Optional[str] = None
    node_type: str


class OfficerResponse(BaseModel):
    """Officer model for API responses."""

    id: str
    name: Optional[str] = None
    node_type: str = "Officer"


class IntermediaryResponse(BaseModel):
    """Intermediary model for API responses."""

    id: str
    name: Optional[str] = None
    node_type: str = "Intermediary"


class PathNode(BaseModel):
    """Node in a path."""

    id: str
    labels: List[str]
    properties: Dict[str, Any]


class PathRelationship(BaseModel):
    """Relationship in a path."""

    type: str
    start_node: str
    end_node: str
    properties: Dict[str, Any]


class OwnershipPath(BaseModel):
    """Ownership path from Officer to Entity."""

    nodes: List[PathNode]
    relationships: List[PathRelationship]
    length: int


class TopIntermediary(BaseModel):
    """Top intermediary with connection count."""

    intermediary_id: str
    intermediary_name: Optional[str]
    entity_count: int


class RedFlag(BaseModel):
    """Red flag detection result."""

    address_id: str
    address: Optional[str]
    entity_count: int
    entities: List[EntityResponse]

