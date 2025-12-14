"""Network analysis API endpoints."""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional

from app.models import TopIntermediary, RedFlag, EntityResponse, OwnershipPath, PathNode, PathRelationship
from app.services.graph_service import GraphService

router = APIRouter()
graph_service = GraphService()


@router.get("/intermediaries/top", response_model=List[TopIntermediary])
async def get_top_intermediaries(
    limit: int = Query(default=10, ge=1, le=100, description="Number of results to return"),
):
    """
    Find intermediaries connected to the most entities.

    Returns the top intermediaries ranked by the number of entities they are connected to.
    """
    try:
        # Call the correct method name from GraphService
        intermediaries_data = graph_service.get_top_intermediaries(limit=limit)
        
        # Convert dicts to Pydantic models
        intermediaries = [
            TopIntermediary(
                intermediary_id=item["intermediary_id"],
                intermediary_name=item["name"],  # Map 'name' to 'intermediary_name'
                entity_count=item["entity_count"]
            )
            for item in intermediaries_data
        ]
        
        return intermediaries
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error finding top intermediaries: {str(e)}"
        )


@router.get("/redflags", response_model=List[RedFlag])
async def get_red_flags(
    min_entities: int = Query(
        default=2, ge=2, description="Minimum number of entities sharing an address"
    ),
    limit: int = Query(default=50, ge=1, le=200, description="Maximum number of results"),
):
    """
    Query for entities sharing the same address (potential shell company ring).

    Detects addresses where multiple entities are registered, which may indicate
    shell company networks or suspicious patterns.
    """
    try:
        # Call the correct method name from GraphService
        red_flags_data = graph_service.detect_red_flags(min_entities=min_entities, limit=limit)
        
        # Convert dicts to Pydantic models
        red_flags = []
        for flag_dict in red_flags_data:
            # Convert sample_entities (list of names) to EntityResponse objects
            # Note: The service returns entity names, so we create minimal EntityResponse objects
            entities = [
                EntityResponse(
                    id="",  # We don't have the ID from the service
                    name=entity_name if entity_name else None,
                    jurisdiction=None,
                    node_type="Entity"
                )
                for entity_name in flag_dict.get("sample_entities", [])
            ]
            
            red_flags.append(
                RedFlag(
                    address_id=flag_dict["address_id"],
                    address=flag_dict["address"],
                    entity_count=flag_dict["entity_count"],
                    entities=entities
                )
            )
        
        return red_flags
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error finding red flags: {str(e)}")


@router.get("/path/shortest", response_model=Optional[OwnershipPath])
async def get_shortest_path(
    start_node_id: str = Query(..., description="ID of the starting node"),
    end_node_id: str = Query(..., description="ID of the ending node"),
):
    """
    Find the shortest path between two nodes using Neo4j's shortestPath function.
    
    Returns the shortest path connecting the start and end nodes, or null if no path exists.
    """
    try:
        path_data = graph_service.get_shortest_path(start_node_id, end_node_id)
        
        if path_data is None:
            return None
        
        # Convert dict to Pydantic model
        nodes = [
            PathNode(
                id=node_dict["id"],
                labels=node_dict["labels"],
                properties=node_dict["properties"]
            )
            for node_dict in path_data["nodes"]
        ]
        
        relationships = [
            PathRelationship(
                type=rel_dict["type"],
                start_node=rel_dict["start_node"],
                end_node=rel_dict["end_node"],
                properties=rel_dict["properties"]
            )
            for rel_dict in path_data["relationships"]
        ]
        
        return OwnershipPath(
            nodes=nodes,
            relationships=relationships,
            length=path_data["length"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error finding shortest path: {str(e)}")


@router.get("/stats/centrality")
async def get_most_connected_officers(
    limit: int = Query(default=10, ge=1, le=100, description="Number of results to return"),
):
    """
    Find the most connected officers using centrality analysis.
    
    Returns officers ranked by their degree (number of entities they are connected to).
    This is a measure of network centrality - officers with higher degrees are more central
    in the offshore network.
    """
    try:
        officers_data = graph_service.get_most_connected_officers(limit=limit)
        
        return officers_data
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error finding most connected officers: {str(e)}"
        )
