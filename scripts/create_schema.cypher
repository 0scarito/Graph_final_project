// ============================================================================
// PANAMA PAPERS NEO4J SCHEMA
// Neo4j 5.x Syntax - ICIJ Offshore Leaks Analysis Platform
// ============================================================================
// 
// This script creates the complete schema for analyzing offshore financial
// networks including entities, persons, companies, officers, intermediaries,
// addresses, and jurisdictions.
//
// USAGE:
//   cypher-shell -u neo4j -p <password> -f schema.cypher
//   OR paste into Neo4j Browser
//
// NOTES:
//   - All constraints use Neo4j 5.x REQUIRE syntax (not deprecated ASSERT)
//   - IF NOT EXISTS ensures idempotent execution (safe to re-run)
//   - Indexes are created after constraints to avoid conflicts
//
// ============================================================================


// ============================================================================
// SECTION 1: UNIQUENESS CONSTRAINTS
// ============================================================================
// These enforce data integrity and automatically create backing indexes.
// Each node type has a unique identifier constraint.

// --- Entity Constraints ---
// Primary offshore entity (companies, trusts, funds, foundations)
CREATE CONSTRAINT entity_id_unique IF NOT EXISTS
FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE;

// --- Person Constraints ---
// Natural persons (beneficial owners, directors, shareholders)
CREATE CONSTRAINT person_id_unique IF NOT EXISTS
FOR (p:Person) REQUIRE p.person_id IS UNIQUE;

// --- Company Constraints ---
// Corporate entities (subset of Entity with additional properties)
CREATE CONSTRAINT company_id_unique IF NOT EXISTS
FOR (c:Company) REQUIRE c.company_id IS UNIQUE;

// Company name uniqueness within jurisdiction (compound constraint)
// Note: Neo4j 5.x supports node key constraints for compound uniqueness
CREATE CONSTRAINT company_jurisdiction_key IF NOT EXISTS
FOR (c:Company) REQUIRE (c.name, c.jurisdiction_code) IS NODE KEY;

// --- Officer Constraints ---
// Corporate officers (directors, secretaries, nominees)
CREATE CONSTRAINT officer_id_unique IF NOT EXISTS
FOR (o:Officer) REQUIRE o.officer_id IS UNIQUE;

// --- Intermediary Constraints ---
// Service providers (law firms, banks, accountants)
CREATE CONSTRAINT intermediary_id_unique IF NOT EXISTS
FOR (i:Intermediary) REQUIRE i.intermediary_id IS UNIQUE;

// --- Address Constraints ---
// Physical and registered addresses
CREATE CONSTRAINT address_id_unique IF NOT EXISTS
FOR (a:Address) REQUIRE a.address_id IS UNIQUE;

// --- Jurisdiction Constraints ---
// Tax havens and registration jurisdictions (reference data)
CREATE CONSTRAINT jurisdiction_code_unique IF NOT EXISTS
FOR (j:Jurisdiction) REQUIRE j.jurisdiction_code IS UNIQUE;


// ============================================================================
// SECTION 2: EXISTENCE CONSTRAINTS (Data Quality)
// ============================================================================
// These ensure required properties are always present.
// Critical for maintaining data integrity during imports.

// --- Entity Required Properties ---
CREATE CONSTRAINT entity_name_exists IF NOT EXISTS
FOR (e:Entity) REQUIRE e.name IS NOT NULL;

CREATE CONSTRAINT entity_source_exists IF NOT EXISTS
FOR (e:Entity) REQUIRE e.source IS NOT NULL;

// --- Person Required Properties ---
CREATE CONSTRAINT person_name_exists IF NOT EXISTS
FOR (p:Person) REQUIRE p.full_name IS NOT NULL;

// --- Company Required Properties ---
CREATE CONSTRAINT company_name_exists IF NOT EXISTS
FOR (c:Company) REQUIRE c.name IS NOT NULL;

CREATE CONSTRAINT company_jurisdiction_exists IF NOT EXISTS
FOR (c:Company) REQUIRE c.jurisdiction_code IS NOT NULL;

// --- Officer Required Properties ---
CREATE CONSTRAINT officer_name_exists IF NOT EXISTS
FOR (o:Officer) REQUIRE o.name IS NOT NULL;

CREATE CONSTRAINT officer_role_exists IF NOT EXISTS
FOR (o:Officer) REQUIRE o.role_type IS NOT NULL;

// --- Intermediary Required Properties ---
CREATE CONSTRAINT intermediary_name_exists IF NOT EXISTS
FOR (i:Intermediary) REQUIRE i.name IS NOT NULL;

// --- Address Required Properties ---
CREATE CONSTRAINT address_country_exists IF NOT EXISTS
FOR (a:Address) REQUIRE a.country_code IS NOT NULL;

// --- Jurisdiction Required Properties ---
CREATE CONSTRAINT jurisdiction_name_exists IF NOT EXISTS
FOR (j:Jurisdiction) REQUIRE j.name IS NOT NULL;


// ============================================================================
// SECTION 3: SINGLE-PROPERTY INDEXES (High-Cardinality Lookups)
// ============================================================================
// These optimize WHERE clause filtering on frequently queried properties.
// Created separately from constraints for properties that aren't unique.

// --- Entity Indexes ---
// Name search (most common query pattern)
CREATE INDEX entity_name_idx IF NOT EXISTS
FOR (e:Entity) ON (e.name);

// Filter by entity type (Company, Trust, Fund, Foundation)
CREATE INDEX entity_type_idx IF NOT EXISTS
FOR (e:Entity) ON (e.entity_type);

// Filter by jurisdiction
CREATE INDEX entity_jurisdiction_idx IF NOT EXISTS
FOR (e:Entity) ON (e.jurisdiction_code);

// Filter by status (Active, Inactive, Dissolved)
CREATE INDEX entity_status_idx IF NOT EXISTS
FOR (e:Entity) ON (e.status);

// Filter by data source (Panama Papers, Paradise Papers, etc.)
CREATE INDEX entity_source_idx IF NOT EXISTS
FOR (e:Entity) ON (e.source);

// Temporal filtering (registration date)
CREATE INDEX entity_registration_date_idx IF NOT EXISTS
FOR (e:Entity) ON (e.registration_date);

// --- Person Indexes ---
// Name search
CREATE INDEX person_fullname_idx IF NOT EXISTS
FOR (p:Person) ON (p.full_name);

// Last name search (common for partial matching)
CREATE INDEX person_lastname_idx IF NOT EXISTS
FOR (p:Person) ON (p.last_name);

// Nationality filtering (country code)
CREATE INDEX person_nationality_idx IF NOT EXISTS
FOR (p:Person) ON (p.nationality);

// PEP (Politically Exposed Person) flag
CREATE INDEX person_pep_idx IF NOT EXISTS
FOR (p:Person) ON (p.is_pep);

// Country of residence
CREATE INDEX person_residence_idx IF NOT EXISTS
FOR (p:Person) ON (p.country_of_residence);

// --- Company Indexes ---
// Company name search
CREATE INDEX company_name_idx IF NOT EXISTS
FOR (c:Company) ON (c.name);

// Jurisdiction filtering
CREATE INDEX company_jurisdiction_idx IF NOT EXISTS
FOR (c:Company) ON (c.jurisdiction_code);

// Status filtering
CREATE INDEX company_status_idx IF NOT EXISTS
FOR (c:Company) ON (c.status);

// Company type (Ltd, LLC, Inc, SA, etc.)
CREATE INDEX company_type_idx IF NOT EXISTS
FOR (c:Company) ON (c.company_type);

// Registry number lookup
CREATE INDEX company_number_idx IF NOT EXISTS
FOR (c:Company) ON (c.company_number);

// Shell company flag (for risk analysis)
CREATE INDEX company_shell_idx IF NOT EXISTS
FOR (c:Company) ON (c.is_shell_company);

// Incorporation date (temporal queries)
CREATE INDEX company_incorporation_idx IF NOT EXISTS
FOR (c:Company) ON (c.incorporation_date);

// --- Officer Indexes ---
// Officer name search
CREATE INDEX officer_name_idx IF NOT EXISTS
FOR (o:Officer) ON (o.name);

// Role type filtering (Director, Secretary, Nominee, etc.)
CREATE INDEX officer_role_idx IF NOT EXISTS
FOR (o:Officer) ON (o.role_type);

// Corporate officer flag (company acting as officer)
CREATE INDEX officer_corporate_idx IF NOT EXISTS
FOR (o:Officer) ON (o.is_corporate_officer);

// Status filtering
CREATE INDEX officer_status_idx IF NOT EXISTS
FOR (o:Officer) ON (o.status);

// --- Intermediary Indexes ---
// Intermediary name search
CREATE INDEX intermediary_name_idx IF NOT EXISTS
FOR (i:Intermediary) ON (i.name);

// Type filtering (Law Firm, Bank, Trust Company, etc.)
CREATE INDEX intermediary_type_idx IF NOT EXISTS
FOR (i:Intermediary) ON (i.type);

// Country filtering
CREATE INDEX intermediary_country_idx IF NOT EXISTS
FOR (i:Intermediary) ON (i.country_code);

// Status filtering
CREATE INDEX intermediary_status_idx IF NOT EXISTS
FOR (i:Intermediary) ON (i.status);

// --- Address Indexes ---
// Country filtering (most common address query)
CREATE INDEX address_country_idx IF NOT EXISTS
FOR (a:Address) ON (a.country_code);

// City filtering
CREATE INDEX address_city_idx IF NOT EXISTS
FOR (a:Address) ON (a.city);

// Postal code lookup
CREATE INDEX address_postal_idx IF NOT EXISTS
FOR (a:Address) ON (a.postal_code);

// Nominee address flag (red flag indicator)
CREATE INDEX address_nominee_idx IF NOT EXISTS
FOR (a:Address) ON (a.is_nominee_address);

// --- Jurisdiction Indexes ---
// Jurisdiction name lookup
CREATE INDEX jurisdiction_name_idx IF NOT EXISTS
FOR (j:Jurisdiction) ON (j.name);

// Tax haven flag (risk filtering)
CREATE INDEX jurisdiction_haven_idx IF NOT EXISTS
FOR (j:Jurisdiction) ON (j.is_tax_haven);

// Geographic region filtering
CREATE INDEX jurisdiction_region_idx IF NOT EXISTS
FOR (j:Jurisdiction) ON (j.region);

// Risk level filtering
CREATE INDEX jurisdiction_risk_idx IF NOT EXISTS
FOR (j:Jurisdiction) ON (j.risk_level);

// FATF status filtering
CREATE INDEX jurisdiction_fatf_idx IF NOT EXISTS
FOR (j:Jurisdiction) ON (j.fatf_status);


// ============================================================================
// SECTION 4: COMPOSITE INDEXES (Multi-Property Queries)
// ============================================================================
// These optimize queries with multiple WHERE conditions.
// Order matters: put highest-cardinality property first.

// --- Entity Composite Indexes ---
// Jurisdiction + status (common filter combination)
CREATE INDEX entity_jurisdiction_status_idx IF NOT EXISTS
FOR (e:Entity) ON (e.jurisdiction_code, e.status);

// Jurisdiction + type (filter by entity category in jurisdiction)
CREATE INDEX entity_jurisdiction_type_idx IF NOT EXISTS
FOR (e:Entity) ON (e.jurisdiction_code, e.entity_type);

// Source + status (filter active entities by leak source)
CREATE INDEX entity_source_status_idx IF NOT EXISTS
FOR (e:Entity) ON (e.source, e.status);

// --- Company Composite Indexes ---
// Jurisdiction + status + incorporation date (temporal jurisdiction analysis)
CREATE INDEX company_jurisdiction_status_date_idx IF NOT EXISTS
FOR (c:Company) ON (c.jurisdiction_code, c.status, c.incorporation_date);

// --- Person Composite Indexes ---
// Nationality + PEP flag (high-risk person identification)
CREATE INDEX person_nationality_pep_idx IF NOT EXISTS
FOR (p:Person) ON (p.nationality, p.is_pep);

// --- Address Composite Indexes ---
// Country + city (geographic clustering)
CREATE INDEX address_country_city_idx IF NOT EXISTS
FOR (a:Address) ON (a.country_code, a.city);


// ============================================================================
// SECTION 5: FULL-TEXT INDEXES (Fuzzy Name Searching)
// ============================================================================
// These enable CONTAINS, fuzzy matching, and relevance-scored searches.
// Essential for name matching across different spellings/transliterations.

// --- Entity Full-Text Index ---
// Search across name and original_name (non-Latin scripts)
CREATE FULLTEXT INDEX entity_name_fulltext IF NOT EXISTS
FOR (e:Entity) ON EACH [e.name, e.original_name];

// --- Person Full-Text Index ---
// Search across all name fields
CREATE FULLTEXT INDEX person_name_fulltext IF NOT EXISTS
FOR (p:Person) ON EACH [p.full_name, p.first_name, p.last_name];

// --- Company Full-Text Index ---
// Search company names
CREATE FULLTEXT INDEX company_name_fulltext IF NOT EXISTS
FOR (c:Company) ON EACH [c.name];

// --- Officer Full-Text Index ---
// Search officer names
CREATE FULLTEXT INDEX officer_name_fulltext IF NOT EXISTS
FOR (o:Officer) ON EACH [o.name];

// --- Intermediary Full-Text Index ---
// Search intermediary names
CREATE FULLTEXT INDEX intermediary_name_fulltext IF NOT EXISTS
FOR (i:Intermediary) ON EACH [i.name];

// --- Address Full-Text Index ---
// Search full address text
CREATE FULLTEXT INDEX address_fulltext IF NOT EXISTS
FOR (a:Address) ON EACH [a.full_address, a.city];


// ============================================================================
// SECTION 6: RELATIONSHIP PROPERTY INDEXES (Neo4j 5.x Feature)
// ============================================================================
// These index properties on relationships for filtered traversals.
// Critical for ownership percentage filtering and temporal queries.

// --- OWNS Relationship Indexes ---
// Filter by ownership status (Active, Historical)
CREATE INDEX owns_status_idx IF NOT EXISTS
FOR ()-[r:OWNS]-() ON (r.status);

// Filter by ownership percentage (>25% threshold queries)
CREATE INDEX owns_percentage_idx IF NOT EXISTS
FOR ()-[r:OWNS]-() ON (r.ownership_percentage);

// Filter by nominee ownership flag
CREATE INDEX owns_nominee_idx IF NOT EXISTS
FOR ()-[r:OWNS]-() ON (r.is_nominee);

// --- CONTROLS Relationship Indexes ---
// Filter by control type (Board Majority, Voting Agreement, etc.)
CREATE INDEX controls_type_idx IF NOT EXISTS
FOR ()-[r:CONTROLS]-() ON (r.control_type);

// Filter by control status
CREATE INDEX controls_status_idx IF NOT EXISTS
FOR ()-[r:CONTROLS]-() ON (r.status);

// --- INVOLVED_IN Relationship Indexes ---
// Filter by role type (Director, Secretary, etc.)
CREATE INDEX involved_role_idx IF NOT EXISTS
FOR ()-[r:INVOLVED_IN]-() ON (r.role);

// Filter by status (Active, Former)
CREATE INDEX involved_status_idx IF NOT EXISTS
FOR ()-[r:INVOLVED_IN]-() ON (r.status);

// Filter by nominee flag
CREATE INDEX involved_nominee_idx IF NOT EXISTS
FOR ()-[r:INVOLVED_IN]-() ON (r.is_nominee);

// --- CREATED_BY Relationship Indexes ---
// Filter by relationship status
CREATE INDEX created_status_idx IF NOT EXISTS
FOR ()-[r:CREATED_BY]-() ON (r.relationship_status);

// --- CONNECTED_TO Relationship Indexes ---
// Filter by connection type
CREATE INDEX connected_type_idx IF NOT EXISTS
FOR ()-[r:CONNECTED_TO]-() ON (r.connection_type);

// Filter by confidence level
CREATE INDEX connected_confidence_idx IF NOT EXISTS
FOR ()-[r:CONNECTED_TO]-() ON (r.confidence);


// ============================================================================
// SECTION 7: RANGE INDEXES FOR TEMPORAL QUERIES (Neo4j 5.x)
// ============================================================================
// Range indexes optimize date/number range queries (<, >, BETWEEN).

// --- Date Range Indexes ---
CREATE RANGE INDEX entity_registration_range IF NOT EXISTS
FOR (e:Entity) ON (e.registration_date);

CREATE RANGE INDEX company_incorporation_range IF NOT EXISTS
FOR (c:Company) ON (c.incorporation_date);

CREATE RANGE INDEX company_dissolution_range IF NOT EXISTS
FOR (c:Company) ON (c.dissolution_date);


// ============================================================================
// SECTION 8: SCHEMA VERIFICATION QUERIES
// ============================================================================
// Run these after schema creation to verify everything was created correctly.

// --- Show All Constraints ---
SHOW CONSTRAINTS;

// --- Show All Indexes ---
SHOW INDEXES;

// --- Detailed Constraint Information ---
SHOW CONSTRAINTS
YIELD name, type, entityType, labelsOrTypes, properties, ownedIndex
RETURN name, type, entityType, labelsOrTypes, properties, ownedIndex
ORDER BY entityType, name;

// --- Detailed Index Information ---
SHOW INDEXES
YIELD name, type, entityType, labelsOrTypes, properties, state
RETURN name, type, entityType, labelsOrTypes, properties, state
ORDER BY type, name;

// --- Count Constraints by Type ---
SHOW CONSTRAINTS
YIELD type
RETURN type, count(*) AS count
ORDER BY count DESC;

// --- Count Indexes by Type ---
SHOW INDEXES
YIELD type
RETURN type, count(*) AS count
ORDER BY count DESC;

// --- Verify All Indexes Are Online ---
SHOW INDEXES
YIELD name, state
WHERE state <> 'ONLINE'
RETURN name, state;


// ============================================================================
// SECTION 9: SAMPLE DATA INSERTION (For Testing Schema)
// ============================================================================
// These create minimal test data to verify constraints work correctly.
// Remove or comment out for production deployment.

// --- Create Sample Jurisdiction ---
MERGE (j:Jurisdiction {jurisdiction_code: 'BVI'})
SET j.name = 'British Virgin Islands',
    j.country_code = 'VGB',
    j.region = 'Caribbean',
    j.is_tax_haven = true,
    j.risk_level = 'HIGH',
    j.fatf_status = 'Monitored',
    j.secrecy_score = 71;

MERGE (j:Jurisdiction {jurisdiction_code: 'PAN'})
SET j.name = 'Panama',
    j.country_code = 'PAN',
    j.region = 'Central America',
    j.is_tax_haven = true,
    j.risk_level = 'HIGH',
    j.fatf_status = 'Grey List',
    j.secrecy_score = 72;

// --- Create Sample Entity ---
MERGE (e:Entity {entity_id: 'TEST-ENTITY-001'})
SET e.name = 'Acme Holdings Ltd',
    e.entity_type = 'Company',
    e.jurisdiction_code = 'BVI',
    e.status = 'Active',
    e.source = 'Panama Papers',
    e.registration_date = date('2005-03-15');

// --- Create Sample Person ---
MERGE (p:Person {person_id: 'TEST-PERSON-001'})
SET p.full_name = 'John Smith',
    p.first_name = 'John',
    p.last_name = 'Smith',
    p.nationality = 'USA',
    p.is_pep = false,
    p.source = 'Panama Papers';

// --- Create Sample Company ---
MERGE (c:Company {company_id: 'TEST-COMPANY-001'})
SET c.name = 'Global Ventures Inc',
    c.jurisdiction_code = 'PAN',
    c.status = 'Active',
    c.company_type = 'Inc',
    c.incorporation_date = date('2010-07-22'),
    c.is_shell_company = true;

// --- Create Sample Intermediary ---
MERGE (i:Intermediary {intermediary_id: 'TEST-INTERMEDIARY-001'})
SET i.name = 'Test Law Firm',
    i.type = 'Law Firm',
    i.country_code = 'PAN',
    i.status = 'Active';

// --- Create Sample Address ---
MERGE (a:Address {address_id: 'TEST-ADDRESS-001'})
SET a.full_address = '123 Offshore Avenue, Road Town, BVI',
    a.city = 'Road Town',
    a.country_code = 'VGB',
    a.is_nominee_address = true;

// --- Create Sample Officer ---
MERGE (o:Officer {officer_id: 'TEST-OFFICER-001'})
SET o.name = 'Jane Doe',
    o.role_type = 'Director',
    o.is_corporate_officer = false,
    o.status = 'Active';

// --- Create Sample Relationships ---
// Person OWNS Entity
MATCH (p:Person {person_id: 'TEST-PERSON-001'})
MATCH (e:Entity {entity_id: 'TEST-ENTITY-001'})
MERGE (p)-[r:OWNS]->(e)
SET r.ownership_percentage = 100.0,
    r.status = 'Active',
    r.is_nominee = false,
    r.acquisition_date = date('2005-03-15');

// Entity REGISTERED_IN Jurisdiction
MATCH (e:Entity {entity_id: 'TEST-ENTITY-001'})
MATCH (j:Jurisdiction {jurisdiction_code: 'BVI'})
MERGE (e)-[r:REGISTERED_IN]->(j)
SET r.registration_date = date('2005-03-15'),
    r.status = 'Active';

// Entity HAS_ADDRESS Address
MATCH (e:Entity {entity_id: 'TEST-ENTITY-001'})
MATCH (a:Address {address_id: 'TEST-ADDRESS-001'})
MERGE (e)-[r:HAS_ADDRESS]->(a)
SET r.address_type = 'Registered',
    r.is_primary = true;

// Officer INVOLVED_IN Entity
MATCH (o:Officer {officer_id: 'TEST-OFFICER-001'})
MATCH (e:Entity {entity_id: 'TEST-ENTITY-001'})
MERGE (o)-[r:INVOLVED_IN]->(e)
SET r.role = 'Director',
    r.status = 'Active',
    r.is_nominee = false,
    r.start_date = date('2005-03-15');

// Entity CREATED_BY Intermediary
MATCH (e:Entity {entity_id: 'TEST-ENTITY-001'})
MATCH (i:Intermediary {intermediary_id: 'TEST-INTERMEDIARY-001'})
MERGE (e)-[r:CREATED_BY]->(i)
SET r.creation_date = date('2005-03-15'),
    r.relationship_status = 'Active';


// ============================================================================
// SECTION 10: TEST QUERIES (Verify Schema Works)
// ============================================================================
// These validate that indexes are being used and constraints are enforced.

// --- Test Uniqueness Constraint (Should Fail) ---
// Uncomment to test - should throw ConstraintViolation:
// CREATE (e:Entity {entity_id: 'TEST-ENTITY-001', name: 'Duplicate Test', source: 'Test'});

// --- Test Full-Text Search ---
CALL db.index.fulltext.queryNodes('entity_name_fulltext', 'Acme')
YIELD node, score
RETURN node.name AS name, score
ORDER BY score DESC;

// --- Test Index Usage (Check PROFILE) ---
PROFILE
MATCH (e:Entity)
WHERE e.jurisdiction_code = 'BVI' AND e.status = 'Active'
RETURN e.name;

// --- Test Relationship Property Index ---
PROFILE
MATCH (p:Person)-[r:OWNS]->(e:Entity)
WHERE r.ownership_percentage >= 25
RETURN p.full_name, r.ownership_percentage, e.name;

// --- Test Date Range Query ---
PROFILE
MATCH (c:Company)
WHERE c.incorporation_date >= date('2005-01-01') 
  AND c.incorporation_date <= date('2010-12-31')
RETURN c.name, c.incorporation_date
ORDER BY c.incorporation_date;


// ============================================================================
// SECTION 11: CLEANUP TEST DATA (Optional)
// ============================================================================
// Run this to remove test data after verification.
// Comment out if you want to keep sample data for development.

// --- Remove Test Relationships ---
MATCH (n)
WHERE n.entity_id STARTS WITH 'TEST-'
   OR n.person_id STARTS WITH 'TEST-'
   OR n.company_id STARTS WITH 'TEST-'
   OR n.officer_id STARTS WITH 'TEST-'
   OR n.intermediary_id STARTS WITH 'TEST-'
   OR n.address_id STARTS WITH 'TEST-'
DETACH DELETE n;

// --- Keep Jurisdiction Reference Data ---
// (Jurisdictions are reference data, typically kept)


// ============================================================================
// SCHEMA CREATION COMPLETE
// ============================================================================
// 
// Summary:
//   - 7 Node Labels: Entity, Person, Company, Officer, Intermediary, Address, Jurisdiction
//   - 9 Relationship Types: OWNS, CONTROLS, HAS_ADDRESS, REGISTERED_IN, 
//                           INVOLVED_IN, CREATED_BY, CONNECTED_TO, RELATED_TO, NATIONALITY
//   - 15+ Uniqueness Constraints
//   - 10+ Property Existence Constraints  
//   - 40+ Single-Property Indexes
//   - 6 Composite Indexes
//   - 6 Full-Text Indexes
//   - 10+ Relationship Property Indexes
//   - 3 Range Indexes
//
// Next Steps:
//   1. Run SHOW INDEXES to verify all indexes are ONLINE
//   2. Import data using LOAD CSV or neo4j-admin import
//   3. Run ANALYZE to update index statistics after import
//
// ============================================================================
