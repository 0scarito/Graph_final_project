"""
Panama Papers API - Pydantic Models
====================================

Data models for FastAPI endpoints supporting offshore financial network analysis.

Model Categories:
    - Entity Models: Core offshore entities (companies, trusts, funds)
    - Person Models: Natural persons (beneficial owners, officers)
    - Relationship Models: Ownership and control relationships
    - Path Query Models: Graph traversal requests/responses
    - Network Analysis Models: GDS algorithm results
    - Search Models: Full-text and filtered search
    - Error Models: Standardized error responses

Pydantic Version: 2.x (with model_validator, field_validator)
Python Version: 3.11+

Usage:
    from models import EntityResponse, PathQuery, OwnershipRelation
    
    entity = EntityResponse(
        entity_id="ENT-001",
        name="Acme Holdings Ltd",
        jurisdiction_code="BVI",
        entity_type="Company",
        status="Active"
    )
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Annotated, Any, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


# ============================================================================
# ENUMS
# ============================================================================

class EntityType(str, Enum):
    """Types of offshore entities."""
    COMPANY = "Company"
    TRUST = "Trust"
    FUND = "Fund"
    FOUNDATION = "Foundation"
    PARTNERSHIP = "Partnership"
    OTHER = "Other"
    UNKNOWN = "Unknown"


class EntityStatus(str, Enum):
    """Entity lifecycle status."""
    ACTIVE = "Active"
    INACTIVE = "Inactive"
    DISSOLVED = "Dissolved"
    STRUCK_OFF = "Struck Off"
    UNKNOWN = "Unknown"


class RelationshipType(str, Enum):
    """Types of relationships between nodes."""
    OWNS = "OWNS"
    CONTROLS = "CONTROLS"
    INVOLVED_IN = "INVOLVED_IN"
    HAS_ADDRESS = "HAS_ADDRESS"
    REGISTERED_IN = "REGISTERED_IN"
    CREATED_BY = "CREATED_BY"
    CONNECTED_TO = "CONNECTED_TO"
    RELATED_TO = "RELATED_TO"


class RiskLevel(str, Enum):
    """Risk classification levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class OfficerRole(str, Enum):
    """Roles that officers can hold."""
    DIRECTOR = "Director"
    SECRETARY = "Secretary"
    NOMINEE_DIRECTOR = "Nominee Director"
    NOMINEE_SHAREHOLDER = "Nominee Shareholder"
    SHAREHOLDER = "Shareholder"
    BENEFICIARY = "Beneficiary"
    PROTECTOR = "Protector"
    SETTLOR = "Settlor"
    AUTHORIZED_SIGNATORY = "Authorized Signatory"
    POWER_OF_ATTORNEY = "Power of Attorney"
    OTHER = "Other"


# ============================================================================
# BASE CONFIGURATION
# ============================================================================

class BaseModelConfig(BaseModel):
    """Base model with common configuration."""
    
    model_config = ConfigDict(
        from_attributes=True,  # Support ORM models (SQLAlchemy, etc.)
        populate_by_name=True,  # Allow population by field name or alias
        str_strip_whitespace=True,  # Strip whitespace from strings
        validate_assignment=True,  # Validate on attribute assignment
        extra="ignore",  # Ignore extra fields during initialization
    )


# ============================================================================
# ENTITY MODELS
# ============================================================================

class EntityBase(BaseModelConfig):
    """
    Base entity model representing offshore entities.
    
    Entities include companies, trusts, funds, and foundations
    registered in offshore jurisdictions.
    
    Attributes:
        entity_id: Unique ICIJ identifier (e.g., "10000001")
        name: Registered legal name
        jurisdiction_code: ISO code or custom (e.g., "BVI", "PAN")
        entity_type: Classification (Company, Trust, Fund, etc.)
        status: Lifecycle status (Active, Dissolved, etc.)
    """
    
    entity_id: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Unique entity identifier from ICIJ database",
        examples=["10000001", "ENT-BVI-2010-001"]
    )
    
    name: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Registered legal name of the entity",
        examples=["Acme Holdings Ltd", "Global Ventures Inc"]
    )
    
    jurisdiction_code: Optional[str] = Field(
        default=None,
        max_length=10,
        description="Jurisdiction of registration (ISO or custom code)",
        examples=["BVI", "PAN", "CYM", "SGP"]
    )
    
    entity_type: EntityType = Field(
        default=EntityType.UNKNOWN,
        description="Type of offshore entity"
    )
    
    status: EntityStatus = Field(
        default=EntityStatus.UNKNOWN,
        description="Current lifecycle status"
    )
    
    @field_validator("jurisdiction_code")
    @classmethod
    def uppercase_jurisdiction(cls, v: Optional[str]) -> Optional[str]:
        """Ensure jurisdiction codes are uppercase."""
        return v.upper() if v else None
    
    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        """Clean and normalize entity name."""
        # Remove excessive whitespace
        return " ".join(v.split())


class EntityCreate(EntityBase):
    """
    Model for creating new entities.
    
    Extends EntityBase with optional creation-specific fields.
    """
    
    incorporation_date: Optional[date] = Field(
        default=None,
        description="Date of entity incorporation"
    )
    
    source: str = Field(
        default="Panama Papers",
        description="Data source (e.g., 'Panama Papers', 'Paradise Papers')"
    )
    
    original_name: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Name in original script (non-Latin)"
    )


class EntityUpdate(BaseModelConfig):
    """
    Model for updating existing entities.
    
    All fields optional - only provided fields are updated.
    """
    
    name: Optional[str] = Field(default=None, max_length=500)
    jurisdiction_code: Optional[str] = Field(default=None, max_length=10)
    entity_type: Optional[EntityType] = None
    status: Optional[EntityStatus] = None
    inactivation_date: Optional[date] = None
    struck_off_date: Optional[date] = None


class EntityResponse(EntityBase):
    """
    Entity response model with analytics data.
    
    Extends EntityBase with computed properties from GDS algorithms
    and additional metadata.
    
    Attributes:
        pagerank_score: Influence score from PageRank algorithm
        community_id: Community cluster assignment from Louvain
        degree_centrality: Number of direct connections
        risk_score: Calculated risk score (0-100)
        incorporation_date: Date of incorporation
    """
    
    # Analytics properties (from GDS algorithms)
    pagerank_score: Optional[float] = Field(
        default=None,
        ge=0,
        description="PageRank influence score (higher = more influential)"
    )
    
    community_id: Optional[int] = Field(
        default=None,
        description="Community cluster ID from Louvain algorithm"
    )
    
    degree_centrality: Optional[int] = Field(
        default=None,
        ge=0,
        description="Number of direct connections"
    )
    
    betweenness_score: Optional[float] = Field(
        default=None,
        ge=0,
        description="Betweenness centrality score"
    )
    
    # Risk assessment
    risk_score: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="Calculated risk score (0-100, higher = riskier)"
    )
    
    risk_level: Optional[RiskLevel] = Field(
        default=None,
        description="Risk classification"
    )
    
    # Additional metadata
    incorporation_date: Optional[date] = Field(
        default=None,
        description="Date of incorporation"
    )
    
    inactivation_date: Optional[date] = Field(
        default=None,
        description="Date entity became inactive"
    )
    
    source: Optional[str] = Field(
        default=None,
        description="Data source"
    )
    
    owner_count: Optional[int] = Field(
        default=None,
        ge=0,
        description="Number of direct owners"
    )
    
    subsidiary_count: Optional[int] = Field(
        default=None,
        ge=0,
        description="Number of owned entities"
    )


class EntitySummary(BaseModelConfig):
    """
    Minimal entity summary for lists and search results.
    
    Lightweight model for bulk responses.
    """
    
    entity_id: str
    name: str
    jurisdiction_code: Optional[str] = None
    entity_type: Optional[str] = None
    status: Optional[str] = None
    risk_level: Optional[RiskLevel] = None


# ============================================================================
# PERSON MODELS
# ============================================================================

class PersonBase(BaseModelConfig):
    """
    Base model for natural persons.
    
    Persons include beneficial owners, directors, shareholders,
    and other individuals connected to offshore entities.
    """
    
    person_id: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Unique person identifier"
    )
    
    full_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Full name as recorded"
    )
    
    nationality: Optional[str] = Field(
        default=None,
        max_length=10,
        description="Nationality (ISO country code)"
    )
    
    country_of_residence: Optional[str] = Field(
        default=None,
        max_length=10,
        description="Country of residence (ISO code)"
    )
    
    is_pep: bool = Field(
        default=False,
        description="Politically Exposed Person flag"
    )
    
    @field_validator("nationality", "country_of_residence")
    @classmethod
    def uppercase_country(cls, v: Optional[str]) -> Optional[str]:
        """Ensure country codes are uppercase."""
        return v.upper() if v else None


class PersonCreate(PersonBase):
    """Model for creating new persons."""
    
    first_name: Optional[str] = Field(default=None, max_length=100)
    last_name: Optional[str] = Field(default=None, max_length=100)
    date_of_birth: Optional[date] = None
    pep_details: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Political role/position if PEP"
    )
    source: str = Field(default="Panama Papers")


class PersonResponse(PersonBase):
    """Person response with analytics and connections."""
    
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    pep_details: Optional[str] = None
    
    # Analytics
    pagerank_score: Optional[float] = None
    community_id: Optional[int] = None
    
    # Connection counts
    entity_count: Optional[int] = Field(
        default=None,
        description="Number of connected entities"
    )
    
    # Risk
    risk_score: Optional[float] = Field(default=None, ge=0, le=100)
    risk_level: Optional[RiskLevel] = None


class PersonSummary(BaseModelConfig):
    """Minimal person summary."""
    
    person_id: str
    full_name: str
    nationality: Optional[str] = None
    is_pep: bool = False


# ============================================================================
# RELATIONSHIP MODELS
# ============================================================================

class RelationshipBase(BaseModelConfig):
    """
    Base relationship model.
    
    Represents directed relationships between nodes in the graph.
    """
    
    source_id: str = Field(
        ...,
        description="Source node identifier"
    )
    
    target_id: str = Field(
        ...,
        description="Target node identifier"
    )
    
    relationship_type: RelationshipType = Field(
        ...,
        description="Type of relationship"
    )
    
    start_date: Optional[date] = Field(
        default=None,
        description="Relationship start date"
    )
    
    end_date: Optional[date] = Field(
        default=None,
        description="Relationship end date"
    )
    
    status: Optional[str] = Field(
        default="Active",
        description="Relationship status"
    )
    
    @model_validator(mode="after")
    def validate_dates(self) -> "RelationshipBase":
        """Ensure end_date is after start_date."""
        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                raise ValueError("end_date must be after start_date")
        return self


class OwnershipRelation(RelationshipBase):
    """
    Ownership relationship with percentage.
    
    Represents direct or indirect ownership stakes between entities
    or from persons to entities.
    """
    
    relationship_type: RelationshipType = Field(
        default=RelationshipType.OWNS,
        description="Type of relationship (defaults to OWNS)"
    )
    
    ownership_percentage: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="Ownership percentage (0-100)"
    )
    
    share_count: Optional[int] = Field(
        default=None,
        ge=0,
        description="Number of shares held"
    )
    
    share_class: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Class of shares (A, B, Ordinary, Preferred)"
    )
    
    is_beneficial: bool = Field(
        default=False,
        description="True if beneficial (vs. legal) ownership"
    )
    
    is_nominee: bool = Field(
        default=False,
        description="True if nominee arrangement"
    )
    
    acquisition_date: Optional[date] = Field(
        default=None,
        description="Date ownership was acquired"
    )


class ControlRelation(RelationshipBase):
    """
    Control relationship (non-ownership control).
    
    Represents de facto control through voting agreements,
    board control, or contractual arrangements.
    """
    
    relationship_type: RelationshipType = Field(
        default=RelationshipType.CONTROLS
    )
    
    control_type: Optional[str] = Field(
        default=None,
        description="Type of control (Board Majority, Voting Agreement, etc.)"
    )
    
    control_percentage: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="Effective control percentage"
    )
    
    evidence_strength: Optional[str] = Field(
        default=None,
        description="Evidence level (Confirmed, Probable, Suspected)"
    )


class InvolvementRelation(RelationshipBase):
    """
    Officer/role involvement in an entity.
    
    Represents persons serving as directors, secretaries,
    or other corporate roles.
    """
    
    relationship_type: RelationshipType = Field(
        default=RelationshipType.INVOLVED_IN
    )
    
    role: OfficerRole = Field(
        ...,
        description="Role held in the entity"
    )
    
    is_nominee: bool = Field(
        default=False,
        description="Acting as nominee"
    )
    
    appointment_date: Optional[date] = Field(
        default=None,
        description="Date of appointment"
    )
    
    resignation_date: Optional[date] = Field(
        default=None,
        description="Date of resignation"
    )


class RelationshipResponse(RelationshipBase):
    """
    Relationship response with additional context.
    """
    
    source_name: Optional[str] = Field(
        default=None,
        description="Name of source node"
    )
    
    source_type: Optional[str] = Field(
        default=None,
        description="Type of source node (Entity, Person, etc.)"
    )
    
    target_name: Optional[str] = Field(
        default=None,
        description="Name of target node"
    )
    
    target_type: Optional[str] = Field(
        default=None,
        description="Type of target node"
    )
    
    # Additional properties depending on relationship type
    ownership_percentage: Optional[float] = None
    role: Optional[str] = None
    is_nominee: Optional[bool] = None


# ============================================================================
# PATH QUERY MODELS
# ============================================================================

class PathQuery(BaseModelConfig):
    """
    Query parameters for graph path finding.
    
    Used to find ownership chains, control paths, and connections
    between entities and beneficial owners.
    
    Attributes:
        source_entity_id: Starting entity for path search
        target_entity_id: Optional destination (None = find all paths)
        max_depth: Maximum path length (1-6 hops)
        relationship_types: Filter by relationship types
        include_persons: Include Person nodes in results
    """
    
    source_entity_id: str = Field(
        ...,
        description="Source entity ID to start path search"
    )
    
    target_entity_id: Optional[str] = Field(
        default=None,
        description="Target entity ID (optional, None = find all paths)"
    )
    
    max_depth: int = Field(
        default=4,
        ge=1,
        le=6,
        description="Maximum path depth (1-6 hops)"
    )
    
    min_depth: int = Field(
        default=1,
        ge=1,
        le=6,
        description="Minimum path depth"
    )
    
    relationship_types: Optional[list[RelationshipType]] = Field(
        default=None,
        description="Filter by relationship types (None = all types)"
    )
    
    include_persons: bool = Field(
        default=True,
        description="Include Person nodes in path results"
    )
    
    include_intermediaries: bool = Field(
        default=False,
        description="Include Intermediary nodes in results"
    )
    
    only_active: bool = Field(
        default=True,
        description="Only include active relationships"
    )
    
    limit: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum number of paths to return"
    )
    
    @model_validator(mode="after")
    def validate_depth_range(self) -> "PathQuery":
        """Ensure min_depth <= max_depth."""
        if self.min_depth > self.max_depth:
            raise ValueError("min_depth must be <= max_depth")
        return self


class PathNode(BaseModelConfig):
    """
    Node in a path result.
    """
    
    node_id: str = Field(..., description="Node identifier")
    name: str = Field(..., description="Node name")
    node_type: str = Field(..., description="Node label (Entity, Person, etc.)")
    jurisdiction_code: Optional[str] = None
    layer: int = Field(..., ge=0, description="Position in path (0 = source)")
    
    # Optional analytics
    risk_score: Optional[float] = None
    is_pep: Optional[bool] = None


class PathEdge(BaseModelConfig):
    """
    Edge/relationship in a path result.
    """
    
    source_id: str
    target_id: str
    relationship_type: str
    ownership_percentage: Optional[float] = None
    role: Optional[str] = None
    layer: int = Field(..., ge=0, description="Position in path")


class PathResult(BaseModelConfig):
    """
    Single path in response.
    """
    
    path_id: int = Field(..., description="Path identifier")
    depth: int = Field(..., ge=1, description="Path length in hops")
    nodes: list[PathNode] = Field(..., description="Ordered list of nodes")
    edges: list[PathEdge] = Field(..., description="Ordered list of edges")
    effective_ownership: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="Calculated effective ownership percentage"
    )
    risk_indicators: list[str] = Field(
        default_factory=list,
        description="Risk indicators found in path"
    )


class PathResponse(BaseModelConfig):
    """
    Response model for path queries.
    
    Contains all paths found matching the query criteria.
    """
    
    query: PathQuery = Field(..., description="Original query")
    path_count: int = Field(..., ge=0, description="Number of paths found")
    paths: list[PathResult] = Field(..., description="Path results")
    
    # Summary statistics
    average_depth: Optional[float] = Field(
        default=None,
        description="Average path depth"
    )
    
    max_depth_found: Optional[int] = Field(
        default=None,
        description="Maximum depth in results"
    )
    
    unique_entities: int = Field(
        default=0,
        ge=0,
        description="Number of unique entities in all paths"
    )
    
    unique_persons: int = Field(
        default=0,
        ge=0,
        description="Number of unique persons in all paths"
    )
    
    pep_count: int = Field(
        default=0,
        ge=0,
        description="Number of PEPs found in paths"
    )
    
    tax_haven_count: int = Field(
        default=0,
        ge=0,
        description="Number of tax haven jurisdictions crossed"
    )
    
    execution_time_ms: Optional[float] = Field(
        default=None,
        description="Query execution time in milliseconds"
    )


# ============================================================================
# NETWORK ANALYSIS MODELS
# ============================================================================

class CommunityMember(BaseModelConfig):
    """Member of a community cluster."""
    
    node_id: str
    name: str
    node_type: str
    jurisdiction_code: Optional[str] = None
    pagerank_score: Optional[float] = None
    is_pep: Optional[bool] = None


class CommunityResponse(BaseModelConfig):
    """
    Community detection result.
    
    Represents a cluster of related entities identified by
    the Louvain algorithm.
    
    Attributes:
        community_id: Unique community identifier
        members: List of entities in the community
        size: Number of members
        internal_density: How connected members are to each other
        risk_level: Overall risk assessment
    """
    
    community_id: int = Field(..., description="Community cluster ID")
    
    size: int = Field(..., ge=1, description="Number of members")
    
    members: list[CommunityMember] = Field(
        ...,
        description="Community members"
    )
    
    internal_density: Optional[float] = Field(
        default=None,
        ge=0,
        le=1,
        description="Internal connection density (0-1)"
    )
    
    modularity_contribution: Optional[float] = Field(
        default=None,
        description="Community's contribution to overall modularity"
    )
    
    # Jurisdiction analysis
    jurisdiction_count: int = Field(
        default=0,
        ge=0,
        description="Number of unique jurisdictions"
    )
    
    jurisdictions: list[str] = Field(
        default_factory=list,
        description="List of jurisdictions"
    )
    
    tax_haven_percentage: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="Percentage of members in tax havens"
    )
    
    # Risk assessment
    risk_score: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="Community risk score"
    )
    
    risk_level: RiskLevel = Field(
        default=RiskLevel.UNKNOWN,
        description="Risk classification"
    )
    
    risk_factors: list[str] = Field(
        default_factory=list,
        description="Identified risk factors"
    )
    
    # Notable members
    pep_count: int = Field(default=0, ge=0)
    pep_names: list[str] = Field(default_factory=list)
    top_influential: list[str] = Field(
        default_factory=list,
        description="Top members by PageRank"
    )


class InfluenceScore(BaseModelConfig):
    """
    Entity influence score from centrality algorithms.
    
    Represents how influential an entity is within the
    offshore network based on PageRank or other metrics.
    """
    
    entity_id: str = Field(..., description="Entity identifier")
    
    name: str = Field(..., description="Entity name")
    
    entity_type: Optional[str] = Field(
        default=None,
        description="Entity type"
    )
    
    jurisdiction_code: Optional[str] = Field(
        default=None,
        description="Jurisdiction"
    )
    
    # Scores
    pagerank_score: float = Field(
        ...,
        ge=0,
        description="PageRank score"
    )
    
    rank: int = Field(
        ...,
        ge=1,
        description="Rank by influence (1 = most influential)"
    )
    
    percentile: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="Percentile ranking"
    )
    
    # Additional centrality scores
    degree_centrality: Optional[int] = Field(
        default=None,
        description="Number of connections"
    )
    
    betweenness_score: Optional[float] = Field(
        default=None,
        description="Betweenness centrality"
    )
    
    eigenvector_score: Optional[float] = Field(
        default=None,
        description="Eigenvector centrality"
    )
    
    # Context
    community_id: Optional[int] = None
    is_tax_haven: Optional[bool] = None


class NetworkStats(BaseModelConfig):
    """
    Overall network statistics.
    """
    
    total_entities: int = Field(..., ge=0)
    total_persons: int = Field(..., ge=0)
    total_relationships: int = Field(..., ge=0)
    total_communities: int = Field(..., ge=0)
    
    # Jurisdiction breakdown
    jurisdiction_count: int = Field(default=0, ge=0)
    top_jurisdictions: list[dict[str, Any]] = Field(default_factory=list)
    
    # Risk summary
    high_risk_entities: int = Field(default=0, ge=0)
    pep_connections: int = Field(default=0, ge=0)
    
    # Graph metrics
    average_degree: Optional[float] = None
    graph_density: Optional[float] = None
    largest_community_size: Optional[int] = None


# ============================================================================
# SEARCH MODELS
# ============================================================================

class SearchQuery(BaseModelConfig):
    """
    Search query parameters.
    """
    
    query: str = Field(
        ...,
        min_length=2,
        max_length=200,
        description="Search term"
    )
    
    search_type: str = Field(
        default="all",
        description="Search type: all, entity, person, intermediary"
    )
    
    jurisdiction_code: Optional[str] = Field(
        default=None,
        description="Filter by jurisdiction"
    )
    
    entity_type: Optional[EntityType] = Field(
        default=None,
        description="Filter by entity type"
    )
    
    status: Optional[EntityStatus] = Field(
        default=None,
        description="Filter by status"
    )
    
    is_pep: Optional[bool] = Field(
        default=None,
        description="Filter for PEPs only"
    )
    
    min_risk_score: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="Minimum risk score filter"
    )
    
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum results"
    )
    
    offset: int = Field(
        default=0,
        ge=0,
        description="Pagination offset"
    )


class SearchResult(BaseModelConfig):
    """
    Individual search result.
    """
    
    node_id: str
    name: str
    node_type: str  # Entity, Person, Intermediary
    relevance_score: float = Field(..., ge=0, le=1)
    jurisdiction_code: Optional[str] = None
    status: Optional[str] = None
    risk_level: Optional[RiskLevel] = None
    is_pep: Optional[bool] = None
    
    # Snippet/context
    matched_field: Optional[str] = None
    snippet: Optional[str] = None


class SearchResponse(BaseModelConfig):
    """
    Search response with results and metadata.
    """
    
    query: str
    total_results: int = Field(..., ge=0)
    results: list[SearchResult]
    
    # Pagination
    limit: int
    offset: int
    has_more: bool
    
    # Facets (for filtering UI)
    jurisdiction_facets: Optional[list[dict[str, Any]]] = None
    type_facets: Optional[list[dict[str, Any]]] = None
    
    execution_time_ms: Optional[float] = None


# ============================================================================
# RED FLAG MODELS
# ============================================================================

class RedFlag(BaseModelConfig):
    """
    Individual red flag indicator.
    """
    
    flag_type: str = Field(
        ...,
        description="Type of red flag"
    )
    
    severity: RiskLevel = Field(
        ...,
        description="Severity level"
    )
    
    description: str = Field(
        ...,
        description="Human-readable description"
    )
    
    evidence: Optional[str] = Field(
        default=None,
        description="Supporting evidence"
    )
    
    related_entities: list[str] = Field(
        default_factory=list,
        description="Related entity IDs"
    )


class RedFlagAnalysis(BaseModelConfig):
    """
    Red flag analysis for an entity.
    """
    
    entity_id: str
    entity_name: str
    
    overall_risk_score: float = Field(..., ge=0, le=100)
    overall_risk_level: RiskLevel
    
    red_flags: list[RedFlag]
    flag_count: int = Field(..., ge=0)
    
    # Specific risk categories
    layering_depth: Optional[int] = None
    jurisdiction_count: Optional[int] = None
    pep_connections: int = Field(default=0, ge=0)
    circular_ownership: bool = False
    mass_registration_address: bool = False
    
    analysis_timestamp: datetime = Field(
        default_factory=datetime.utcnow
    )


# ============================================================================
# ERROR & RESPONSE MODELS
# ============================================================================

class ErrorDetail(BaseModelConfig):
    """
    Detailed error information.
    """
    
    field: Optional[str] = Field(
        default=None,
        description="Field that caused the error"
    )
    
    message: str = Field(
        ...,
        description="Error message"
    )
    
    code: Optional[str] = Field(
        default=None,
        description="Error code"
    )


class ErrorResponse(BaseModelConfig):
    """
    Standardized error response model.
    
    Used for all API error responses to ensure consistency.
    """
    
    status_code: int = Field(
        ...,
        ge=400,
        le=599,
        description="HTTP status code"
    )
    
    error: str = Field(
        ...,
        description="Error type"
    )
    
    detail: str = Field(
        ...,
        description="Human-readable error description"
    )
    
    errors: list[ErrorDetail] = Field(
        default_factory=list,
        description="List of detailed errors"
    )
    
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Error timestamp"
    )
    
    request_id: Optional[str] = Field(
        default=None,
        description="Request ID for tracing"
    )
    
    path: Optional[str] = Field(
        default=None,
        description="Request path"
    )


class HealthStatus(str, Enum):
    """Health check status values."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthCheckResponse(BaseModelConfig):
    """
    Health check response model.
    
    Reports API and dependency health status.
    """
    
    status: HealthStatus = Field(
        ...,
        description="Overall health status"
    )
    
    api_version: str = Field(
        ...,
        description="API version"
    )
    
    neo4j_connection: bool = Field(
        ...,
        description="Neo4j database connectivity"
    )
    
    neo4j_version: Optional[str] = Field(
        default=None,
        description="Neo4j server version"
    )
    
    gds_available: Optional[bool] = Field(
        default=None,
        description="GDS plugin availability"
    )
    
    uptime_seconds: Optional[float] = Field(
        default=None,
        ge=0,
        description="API uptime in seconds"
    )
    
    timestamp: datetime = Field(
        default_factory=datetime.utcnow
    )
    
    checks: dict[str, bool] = Field(
        default_factory=dict,
        description="Individual health checks"
    )


class PaginationMeta(BaseModelConfig):
    """
    Pagination metadata for list responses.
    """
    
    total: int = Field(..., ge=0, description="Total number of items")
    limit: int = Field(..., ge=1, description="Items per page")
    offset: int = Field(..., ge=0, description="Current offset")
    page: int = Field(..., ge=1, description="Current page number")
    total_pages: int = Field(..., ge=0, description="Total pages")
    has_next: bool = Field(..., description="Has next page")
    has_prev: bool = Field(..., description="Has previous page")


class PaginatedResponse(BaseModelConfig):
    """
    Generic paginated response wrapper.
    """
    
    data: list[Any] = Field(..., description="Response data")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")


# ============================================================================
# TYPE ALIASES FOR CONVENIENCE
# ============================================================================

# Common response types
EntityList = list[EntityResponse]
PersonList = list[PersonResponse]
RelationshipList = list[RelationshipResponse]
CommunityList = list[CommunityResponse]
InfluenceList = list[InfluenceScore]


# ============================================================================
# MODEL EXPORTS
# ============================================================================

__all__ = [
    # Enums
    "EntityType",
    "EntityStatus",
    "RelationshipType",
    "RiskLevel",
    "OfficerRole",
    "HealthStatus",
    
    # Entity Models
    "EntityBase",
    "EntityCreate",
    "EntityUpdate",
    "EntityResponse",
    "EntitySummary",
    
    # Person Models
    "PersonBase",
    "PersonCreate",
    "PersonResponse",
    "PersonSummary",
    
    # Relationship Models
    "RelationshipBase",
    "OwnershipRelation",
    "ControlRelation",
    "InvolvementRelation",
    "RelationshipResponse",
    
    # Path Models
    "PathQuery",
    "PathNode",
    "PathEdge",
    "PathResult",
    "PathResponse",
    
    # Network Analysis
    "CommunityMember",
    "CommunityResponse",
    "InfluenceScore",
    "NetworkStats",
    
    # Search Models
    "SearchQuery",
    "SearchResult",
    "SearchResponse",
    
    # Red Flag Models
    "RedFlag",
    "RedFlagAnalysis",
    
    # Error & Response Models
    "ErrorDetail",
    "ErrorResponse",
    "HealthCheckResponse",
    "PaginationMeta",
    "PaginatedResponse",
    
    # Type Aliases
    "EntityList",
    "PersonList",
    "RelationshipList",
    "CommunityList",
    "InfluenceList",
]
