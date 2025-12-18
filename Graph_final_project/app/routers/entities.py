"""Entity-related API endpoints."""

from fastapi import APIRouter, HTTPException, Query
from typing import List

from app.models import OwnershipPath, PathNode, PathRelationship
from app.services.graph_service import GraphService

router = APIRouter()
graph_service = GraphService()


@router.get("/{entity_id}/ownership/paths", response_model=List[OwnershipPath])
async def get_ownership_paths(
    entity_id: str,
    max_length: int = Query(default=5, ge=1, le=10, description="Maximum path length"),
):
    """
    Trace ownership paths from Officers to a specific Entity.

    Returns all paths connecting Officers to the given Entity, up to the specified max_length.
    """
    try:
        # Call the correct method name from GraphService
        paths_data = graph_service.get_entity_ownership_paths(entity_id, max_depth=max_length)
        
        # Convert dicts to Pydantic models
        paths = []
        for path_dict in paths_data:
            # Convert nodes
            nodes = [
                PathNode(
                    id=node_dict["id"],
                    labels=node_dict["labels"],
                    properties=node_dict["properties"]
                )
                for node_dict in path_dict["nodes"]
            ]
            
            # Convert relationships
            relationships = [
                PathRelationship(
                    type=rel_dict["type"],
                    start_node=rel_dict["start_node"],
                    end_node=rel_dict["end_node"],
                    properties=rel_dict["properties"]
                )
                for rel_dict in path_dict["relationships"]
            ]
            
            paths.append(
                OwnershipPath(
                    nodes=nodes,
                    relationships=relationships,
                    length=path_dict["length"]
                )
            )
        
        return paths
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error finding ownership paths: {str(e)}")
