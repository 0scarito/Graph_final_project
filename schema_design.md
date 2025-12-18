# Neo4j Graph Schema - Panama Papers Offshore Network

> **Version:** Neo4j 5.x Compatible  
> **Purpose:** Beneficial ownership tracing, intermediary detection, and offshore financial network analysis  
> **Dataset Context:** ICIJ Panama Papers leak containing ~11.5 million documents

---

## Node Labels

### Entity

**Purpose:** Abstract parent label representing any legal entity involved in offshore structures. Serves as a supertype for Company, Fund, and Trust distinctions while enabling polymorphic queries across all entity types.

**Properties:**
| Property | Data Type | Indexed | Constraints | Description |
|----------|-----------|---------|-------------|-------------|
| entity_id | String | ✅ Primary | UNIQUE, NOT NULL | ICIJ internal identifier (e.g., "10000001") |
| name | String | ✅ Full-text | NOT NULL | Legal or registered name |
| original_name | String | ❌ | — | Name in original script (non-Latin) |
| jurisdiction_code | String | ✅ | — | ISO 3166-1 alpha-3 or custom code (e.g., "BVI", "PAN") |
| incorporation_date | Date | ❌ | — | Date of legal formation |
| inactivation_date | Date | ❌ | — | Date entity became inactive/dissolved |
| struck_off_date | Date | ❌ | — | Date removed from registry |
| status | String | ✅ | — | Options: `Active`, `Inactive`, `Dissolved`, `Struck Off`, `Unknown` |
| entity_type | String | ✅ | — | Options: `Company`, `Trust`, `Fund`, `Foundation`, `Partnership`, `Other` |
| service_provider | String | ❌ | — | Originating law firm (e.g., "Mossack Fonseca") |
| source | String | ❌ | NOT NULL | Leak source: `Panama Papers`, `Paradise Papers`, `Pandora Papers` |
| countries_linked | List\<String\> | ❌ | — | Countries associated via addresses or officers |

---

### Person

**Purpose:** Represents natural persons who act as officers, shareholders, or beneficial owners. Critical for tracing ultimate beneficial ownership (UBO) and identifying politically exposed persons (PEPs).

**Properties:**
| Property | Data Type | Indexed | Constraints | Description |
|----------|-----------|---------|-------------|-------------|
| person_id | String | ✅ Primary | UNIQUE, NOT NULL | ICIJ internal identifier |
| full_name | String | ✅ Full-text | NOT NULL | Complete name as recorded |
| first_name | String | ❌ | — | Given name (parsed) |
| last_name | String | ✅ | — | Family name (for matching) |
| nationality | String | ✅ | — | ISO 3166-1 alpha-3 country code |
| country_of_residence | String | ❌ | — | Current residence country |
| date_of_birth | Date | ❌ | — | Birth date (often incomplete) |
| year_of_birth | Integer | ❌ | — | Birth year when full date unknown |
| is_pep | Boolean | ✅ | DEFAULT false | Politically Exposed Person flag |
| pep_details | String | ❌ | — | Political role/position if PEP |
| source | String | ❌ | NOT NULL | Leak source identifier |

---

### Company

**Purpose:** Specific subtype of Entity representing incorporated companies—the primary vehicle for offshore structures. Enables company-specific queries and regulatory classification.

**Properties:**
| Property | Data Type | Indexed | Constraints | Description |
|----------|-----------|---------|-------------|-------------|
| company_id | String | ✅ Primary | UNIQUE, NOT NULL | ICIJ identifier (may equal entity_id) |
| company_name | String | ✅ Full-text | NOT NULL | Registered company name |
| company_number | String | ✅ | — | Official registry number |
| company_type | String | ❌ | — | Options: `Ltd`, `LLC`, `Inc`, `SA`, `BV`, `GmbH`, etc. |
| jurisdiction_code | String | ✅ | NOT NULL | Registration jurisdiction |
| registered_agent | String | ❌ | — | Name of registered agent |
| share_capital | Float | ❌ | — | Authorized share capital |
| share_capital_currency | String | ❌ | — | ISO 4217 currency code |
| is_shell_company | Boolean | ✅ | DEFAULT false | Suspected shell company flag |
| incorporation_date | Date | ✅ | — | Date of incorporation |
| dissolution_date | Date | ❌ | — | Date of dissolution |
| status | String | ✅ | — | Options: `Active`, `Dormant`, `Dissolved`, `Struck Off` |

---

### Officer

**Purpose:** Represents roles held by persons or entities in companies (directors, secretaries, nominees). A linking concept that captures the temporal and functional aspects of corporate governance positions.

**Properties:**
| Property | Data Type | Indexed | Constraints | Description |
|----------|-----------|---------|-------------|-------------|
| officer_id | String | ✅ Primary | UNIQUE, NOT NULL | ICIJ identifier |
| role_type | String | ✅ | NOT NULL | Options: `Director`, `Secretary`, `Nominee Director`, `Nominee Shareholder`, `Protector`, `Beneficiary`, `Shareholder`, `Power of Attorney`, `Authorized Signatory` |
| name | String | ✅ Full-text | NOT NULL | Name as recorded in documents |
| is_corporate_officer | Boolean | ✅ | DEFAULT false | True if officer is a company (not natural person) |
| start_date | Date | ❌ | — | Appointment date |
| end_date | Date | ❌ | — | Resignation/termination date |
| status | String | ❌ | — | Options: `Active`, `Resigned`, `Removed`, `Unknown` |
| source_document | String | ❌ | — | Reference to source document |

---

### Intermediary

**Purpose:** Represents law firms, banks, accountants, and other professional enablers who create and manage offshore structures. Critical for detecting systemic facilitators and compliance failures.

**Properties:**
| Property | Data Type | Indexed | Constraints | Description |
|----------|-----------|---------|-------------|-------------|
| intermediary_id | String | ✅ Primary | UNIQUE, NOT NULL | ICIJ identifier |
| name | String | ✅ Full-text | NOT NULL | Firm/intermediary name |
| type | String | ✅ | — | Options: `Law Firm`, `Bank`, `Trust Company`, `Accountant`, `Financial Advisor`, `Corporate Service Provider`, `Other` |
| country_code | String | ✅ | — | Primary country of operation |
| address | String | ❌ | — | Business address |
| status | String | ❌ | — | Options: `Active`, `Closed`, `Sanctioned`, `Unknown` |
| entities_created_count | Integer | ❌ | — | Denormalized count (for ranking) |
| first_activity_date | Date | ❌ | — | Earliest known involvement |
| last_activity_date | Date | ❌ | — | Most recent activity |

---

### Address

**Purpose:** Represents physical and registered addresses. Enables geographic clustering analysis, identification of nominee addresses (many entities at one address), and sanctions screening by location.

**Properties:**
| Property | Data Type | Indexed | Constraints | Description |
|----------|-----------|---------|-------------|-------------|
| address_id | String | ✅ Primary | UNIQUE, NOT NULL | ICIJ identifier |
| full_address | String | ✅ Full-text | NOT NULL | Complete address string |
| address_line_1 | String | ❌ | — | Street address |
| address_line_2 | String | ❌ | — | Suite/floor/unit |
| city | String | ✅ | — | City name |
| state_province | String | ❌ | — | State or province |
| postal_code | String | ✅ | — | Postal/ZIP code |
| country_code | String | ✅ | NOT NULL | ISO 3166-1 alpha-3 |
| is_registered_office | Boolean | ❌ | DEFAULT false | Official registered address |
| is_nominee_address | Boolean | ✅ | DEFAULT false | Known nominee/mass registration address |
| entities_at_address | Integer | ❌ | — | Count of entities (denormalized) |

---

### Jurisdiction

**Purpose:** Reference node for tax havens and registration jurisdictions. Enables jurisdiction-based risk scoring, regulatory analysis, and geographic network mapping.

**Properties:**
| Property | Data Type | Indexed | Constraints | Description |
|----------|-----------|---------|-------------|-------------|
| jurisdiction_code | String | ✅ Primary | UNIQUE, NOT NULL | ISO code or custom (e.g., "BVI", "VGB") |
| name | String | ✅ | NOT NULL | Full jurisdiction name |
| country_code | String | ❌ | — | Parent country ISO code |
| region | String | ✅ | — | Geographic region: `Caribbean`, `Europe`, `Asia-Pacific`, etc. |
| is_tax_haven | Boolean | ✅ | DEFAULT false | OECD/EU blacklist status |
| secrecy_score | Integer | ❌ | — | Tax Justice Network score (0-100) |
| corporate_tax_rate | Float | ❌ | — | Nominal corporate tax rate |
| crs_participant | Boolean | ❌ | DEFAULT false | Common Reporting Standard participant |
| fatf_status | String | ❌ | — | Options: `Compliant`, `Grey List`, `Black List`, `Not Rated` |
| entity_count | Integer | ❌ | — | Total entities registered (denormalized) |

---

## Relationship Types

### OWNS

**Purpose:** Captures direct and indirect ownership stakes between entities. Essential for tracing beneficial ownership chains, identifying layered structures, and calculating effective ownership percentages through multi-hop traversals.

**Direction:** `(Entity|Person|Company) -[OWNS]-> (Entity|Company)`

**Properties:**
| Property | Data Type | Constraints | Description |
|----------|-----------|-------------|-------------|
| ownership_percentage | Float | 0.0-100.0 | Percentage of shares/interest held |
| share_count | Integer | — | Number of shares held |
| share_class | String | — | Class of shares (A, B, Ordinary, Preferred) |
| acquisition_date | Date | — | Date ownership acquired |
| end_date | Date | — | Date ownership ended |
| status | String | DEFAULT 'Active' | Options: `Active`, `Historical`, `Disputed` |
| is_beneficial | Boolean | DEFAULT false | True if beneficial (vs. legal) ownership |
| is_nominee | Boolean | DEFAULT false | Nominee arrangement flag |
| source_document | String | — | Reference to evidence document |

**Why Necessary:** Ownership is the fundamental relationship in offshore structures. Without it, beneficial ownership tracing is impossible. The `ownership_percentage` and `is_nominee` properties are critical for calculating effective control and identifying hidden ownership.

---

### CONTROLS

**Purpose:** Represents de facto control relationships that exist independently of formal ownership—through voting agreements, board control, or contractual arrangements. Captures the reality that ownership percentages often understate actual control.

**Direction:** `(Person|Entity|Company) -[CONTROLS]-> (Entity|Company)`

**Properties:**
| Property | Data Type | Constraints | Description |
|----------|-----------|-------------|-------------|
| control_type | String | NOT NULL | Options: `Board Majority`, `Voting Agreement`, `Contractual`, `De Facto`, `Protector Powers`, `Veto Rights` |
| control_percentage | Float | — | Effective control percentage if calculable |
| start_date | Date | — | Control relationship start |
| end_date | Date | — | Control relationship end |
| status | String | DEFAULT 'Active' | Options: `Active`, `Historical`, `Suspected` |
| evidence_strength | String | — | Options: `Confirmed`, `Probable`, `Suspected` |
| notes | String | — | Explanatory notes |

**Why Necessary:** Many offshore structures use trusts, foundations, or nominee arrangements where legal ownership is divorced from control. A person may own 0% of shares but control the entity through protector powers or board appointments. This relationship captures what OWNS cannot.

---

### HAS_ADDRESS

**Purpose:** Links entities, persons, and intermediaries to their associated addresses. Enables geographic analysis, identification of mass-registration addresses (red flags), and sanctions screening.

**Direction:** `(Entity|Person|Company|Intermediary|Officer) -[HAS_ADDRESS]-> (Address)`

**Properties:**
| Property | Data Type | Constraints | Description |
|----------|-----------|-------------|-------------|
| address_type | String | NOT NULL | Options: `Registered`, `Business`, `Residential`, `Correspondence`, `Former` |
| start_date | Date | — | Address valid from |
| end_date | Date | — | Address valid until |
| is_primary | Boolean | DEFAULT false | Primary/current address flag |
| source | String | — | Data source for this link |

**Why Necessary:** Address linkage is critical for (1) identifying nominee addresses where hundreds of entities share one location, (2) geographic clustering to find related entities, (3) sanctions and watchlist screening, and (4) verifying identity through address matching.

---

### REGISTERED_IN

**Purpose:** Links entities and companies to their jurisdiction of registration. Enables jurisdiction-based risk analysis, regulatory mapping, and identification of jurisdiction-shopping patterns.

**Direction:** `(Entity|Company) -[REGISTERED_IN]-> (Jurisdiction)`

**Properties:**
| Property | Data Type | Constraints | Description |
|----------|-----------|-------------|-------------|
| registration_number | String | — | Official registry number |
| registration_date | Date | — | Date of registration |
| registry_name | String | — | Name of registering authority |
| status | String | DEFAULT 'Active' | Options: `Active`, `Struck Off`, `Dissolved`, `Migrated` |
| migration_from | String | — | Previous jurisdiction if migrated |

**Why Necessary:** Jurisdiction choice is deliberate in offshore planning. This relationship enables analysis of which jurisdictions are favored by specific intermediaries, persons, or for specific purposes. The `migration_from` property tracks jurisdiction-hopping to avoid regulation.

---

### INVOLVED_IN

**Purpose:** Links persons and intermediaries to entities where they play a role. A general-purpose relationship that captures involvement beyond ownership—as directors, secretaries, agents, or other capacities.

**Direction:** `(Person|Intermediary|Officer) -[INVOLVED_IN]-> (Entity|Company)`

**Properties:**
| Property | Data Type | Constraints | Description |
|----------|-----------|-------------|-------------|
| role | String | NOT NULL | Options: `Director`, `Secretary`, `Nominee Director`, `Registered Agent`, `Protector`, `Enforcer`, `Settlor`, `Beneficiary`, `Authorized Signatory`, `Power of Attorney`, `Shareholder`, `Ultimate Beneficial Owner` |
| start_date | Date | — | Role start date |
| end_date | Date | — | Role end date |
| status | String | DEFAULT 'Active' | Options: `Active`, `Former`, `Unknown` |
| is_nominee | Boolean | DEFAULT false | Acting as nominee |
| appointed_by | String | — | Who appointed this person |

**Why Necessary:** This relationship captures the human element of corporate control. While OWNS and CONTROLS track stake-based relationships, INVOLVED_IN captures the operational roles. A person directing 50 companies as nominee director is a major red flag detectable only through this relationship.

---

### CREATED_BY

**Purpose:** Links entities to the intermediary (law firm, corporate service provider) that created them. Essential for intermediary risk profiling and detecting patterns of facilitation.

**Direction:** `(Entity|Company) -[CREATED_BY]-> (Intermediary)`

**Properties:**
| Property | Data Type | Constraints | Description |
|----------|-----------|-------------|-------------|
| creation_date | Date | — | Date entity was created |
| service_type | String | — | Options: `Incorporation`, `Registration`, `Continuation`, `Redomiciliation` |
| fee_currency | String | — | Currency of service fee |
| relationship_status | String | DEFAULT 'Active' | Options: `Active`, `Terminated`, `Transferred` |
| termination_date | Date | — | When relationship ended |

**Why Necessary:** Intermediaries are the gatekeepers of offshore structures. Analyzing which intermediaries create entities in which jurisdictions for which clients reveals systemic patterns. Mossack Fonseca's role in the Panama Papers was discovered through this relationship type.

---

### CONNECTED_TO

**Purpose:** A flexible relationship for capturing links that don't fit other categories—shared phone numbers, email domains, common beneficial owners inferred but not proven, or journalist-identified connections.

**Direction:** `(Entity|Person|Company|Address) -[CONNECTED_TO]-> (Entity|Person|Company|Address)`

**Properties:**
| Property | Data Type | Constraints | Description |
|----------|-----------|-------------|-------------|
| connection_type | String | NOT NULL | Options: `Shared Contact`, `Common Beneficial Owner`, `Family Relationship`, `Business Associate`, `Same Formation Batch`, `Linked Investigation`, `Shared Bank Account` |
| confidence | String | NOT NULL | Options: `Confirmed`, `High`, `Medium`, `Low`, `Suspected` |
| evidence | String | — | Description of evidence |
| source | String | — | Source of connection identification |
| discovered_date | Date | — | When connection was identified |

**Why Necessary:** Investigative analysis often reveals connections that aren't captured by formal corporate relationships. Shared email domains, phone numbers, or formation patterns suggest links that warrant investigation. This relationship preserves those insights.

---

### RELATED_TO

**Purpose:** Captures family and personal relationships between persons. Critical for identifying beneficial ownership through family nominees and tracing wealth across generations.

**Direction:** `(Person) -[RELATED_TO]-> (Person)`

**Properties:**
| Property | Data Type | Constraints | Description |
|----------|-----------|-------------|-------------|
| relationship_type | String | NOT NULL | Options: `Spouse`, `Parent`, `Child`, `Sibling`, `Extended Family`, `Business Partner`, `Associate` |
| confidence | String | DEFAULT 'Confirmed' | Options: `Confirmed`, `Probable`, `Suspected` |
| source | String | — | Source of relationship identification |

**Why Necessary:** Beneficial ownership is frequently hidden through family members. A politician's children or spouse may hold assets on their behalf. Without family relationships, these patterns are invisible to ownership analysis.

---

## Indexing Strategy

### Primary Indexes (Unique Constraints with Index)

These provide O(1) lookup for the most common access patterns:

```cypher
CREATE CONSTRAINT entity_id_unique FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE;
CREATE CONSTRAINT person_id_unique FOR (p:Person) REQUIRE p.person_id IS UNIQUE;
CREATE CONSTRAINT company_id_unique FOR (c:Company) REQUIRE c.company_id IS UNIQUE;
CREATE CONSTRAINT officer_id_unique FOR (o:Officer) REQUIRE o.officer_id IS UNIQUE;
CREATE CONSTRAINT intermediary_id_unique FOR (i:Intermediary) REQUIRE i.intermediary_id IS UNIQUE;
CREATE CONSTRAINT address_id_unique FOR (a:Address) REQUIRE a.address_id IS UNIQUE;
CREATE CONSTRAINT jurisdiction_code_unique FOR (j:Jurisdiction) REQUIRE j.jurisdiction_code IS UNIQUE;
```

### Full-Text Indexes (For Name Searching)

Essential for fuzzy matching and partial name searches:

```cypher
CREATE FULLTEXT INDEX entity_name_fulltext FOR (e:Entity) ON EACH [e.name, e.original_name];
CREATE FULLTEXT INDEX person_name_fulltext FOR (p:Person) ON EACH [p.full_name, p.first_name, p.last_name];
CREATE FULLTEXT INDEX company_name_fulltext FOR (c:Company) ON EACH [c.company_name];
CREATE FULLTEXT INDEX intermediary_name_fulltext FOR (i:Intermediary) ON EACH [i.name];
CREATE FULLTEXT INDEX address_fulltext FOR (a:Address) ON EACH [a.full_address, a.city];
```

### Range Indexes (For Filtering and Sorting)

Support common WHERE clauses and ORDER BY operations:

```cypher
CREATE INDEX entity_status_idx FOR (e:Entity) ON (e.status);
CREATE INDEX entity_type_idx FOR (e:Entity) ON (e.entity_type);
CREATE INDEX entity_jurisdiction_idx FOR (e:Entity) ON (e.jurisdiction_code);
CREATE INDEX company_jurisdiction_idx FOR (c:Company) ON (c.jurisdiction_code);
CREATE INDEX company_status_idx FOR (c:Company) ON (c.status);
CREATE INDEX company_incorporation_idx FOR (c:Company) ON (c.incorporation_date);
CREATE INDEX person_nationality_idx FOR (p:Person) ON (p.nationality);
CREATE INDEX person_pep_idx FOR (p:Person) ON (p.is_pep);
CREATE INDEX person_lastname_idx FOR (p:Person) ON (p.last_name);
CREATE INDEX officer_role_idx FOR (o:Officer) ON (o.role_type);
CREATE INDEX officer_corporate_idx FOR (o:Officer) ON (o.is_corporate_officer);
CREATE INDEX intermediary_type_idx FOR (i:Intermediary) ON (i.type);
CREATE INDEX intermediary_country_idx FOR (i:Intermediary) ON (i.country_code);
CREATE INDEX address_country_idx FOR (a:Address) ON (a.country_code);
CREATE INDEX address_city_idx FOR (a:Address) ON (a.city);
CREATE INDEX address_nominee_idx FOR (a:Address) ON (a.is_nominee_address);
CREATE INDEX jurisdiction_haven_idx FOR (j:Jurisdiction) ON (j.is_tax_haven);
CREATE INDEX jurisdiction_region_idx FOR (j:Jurisdiction) ON (j.region);
```

### Composite Indexes (For Multi-Property Queries)

Optimize common compound conditions:

```cypher
CREATE INDEX company_jurisdiction_status_idx FOR (c:Company) ON (c.jurisdiction_code, c.status);
CREATE INDEX entity_jurisdiction_type_idx FOR (e:Entity) ON (e.jurisdiction_code, e.entity_type);
CREATE INDEX person_nationality_pep_idx FOR (p:Person) ON (p.nationality, p.is_pep);
CREATE INDEX address_country_city_idx FOR (a:Address) ON (a.country_code, a.city);
```

### Relationship Property Indexes

For filtering relationship traversals:

```cypher
CREATE INDEX owns_status_idx FOR ()-[r:OWNS]-() ON (r.status);
CREATE INDEX involved_role_idx FOR ()-[r:INVOLVED_IN]-() ON (r.role);
CREATE INDEX involved_status_idx FOR ()-[r:INVOLVED_IN]-() ON (r.status);
```

---

## Query Risk Analysis

### Cartesian Product Risks

**Risk Level: CRITICAL**

The following query patterns can produce Cartesian products (explosive intermediate result sets):

#### 1. Unconnected Pattern Matches

```cypher
// DANGEROUS: Cartesian product between all entities and all persons
MATCH (e:Entity), (p:Person)
WHERE e.jurisdiction_code = 'BVI' AND p.nationality = 'RUS'
RETURN e, p
```

**Mitigation:** Always connect patterns or use explicit path relationships:

```cypher
// SAFE: Connected via relationship
MATCH (p:Person)-[:OWNS|CONTROLS*1..4]->(e:Entity)
WHERE e.jurisdiction_code = 'BVI' AND p.nationality = 'RUS'
RETURN p, e
```

#### 2. Multi-Hop Pathfinding Without Limits

```cypher
// DANGEROUS: Unbounded path exploration
MATCH path = (p:Person)-[:OWNS|CONTROLS*]->(e:Entity)
WHERE e.name CONTAINS 'Holdings'
RETURN path
```

**Mitigation:** Always bound variable-length paths:

```cypher
// SAFE: Bounded to 6 hops maximum
MATCH path = (p:Person)-[:OWNS|CONTROLS*1..6]->(e:Entity)
WHERE e.name CONTAINS 'Holdings'
RETURN path
LIMIT 1000
```

#### 3. Multiple Optional Matches

```cypher
// DANGEROUS: Cascading optionals create explosion
MATCH (e:Entity)
OPTIONAL MATCH (e)-[:HAS_ADDRESS]->(a:Address)
OPTIONAL MATCH (e)-[:REGISTERED_IN]->(j:Jurisdiction)
OPTIONAL MATCH (e)<-[:INVOLVED_IN]-(o:Officer)
OPTIONAL MATCH (e)<-[:OWNS]-(owner)
RETURN e, a, j, o, owner
```

**Mitigation:** Use subqueries or COLLECT for optional data:

```cypher
// SAFE: Aggregated optionals
MATCH (e:Entity)
OPTIONAL MATCH (e)-[:HAS_ADDRESS]->(a:Address)
WITH e, COLLECT(DISTINCT a) AS addresses
OPTIONAL MATCH (e)<-[:INVOLVED_IN]-(o:Officer)
WITH e, addresses, COLLECT(DISTINCT o) AS officers
RETURN e, addresses, officers
LIMIT 100
```

#### 4. All-Pairs Shortest Path

```cypher
// DANGEROUS: All pairs between two large sets
MATCH (p1:Person), (p2:Person)
WHERE p1.nationality = 'USA' AND p2.nationality = 'CHN'
MATCH path = shortestPath((p1)-[*]-(p2))
RETURN path
```

**Mitigation:** Start from specific nodes, use LIMIT, or pre-filter:

```cypher
// SAFER: Single source, bounded
MATCH (p1:Person {person_id: 'specific-id'})
MATCH (p2:Person) WHERE p2.nationality = 'CHN'
WITH p1, p2 LIMIT 100
MATCH path = shortestPath((p1)-[*..8]-(p2))
RETURN path
```

### High-Risk Query Patterns

| Pattern                      | Risk                | Mitigation                             |
| ---------------------------- | ------------------- | -------------------------------------- |
| `()-[*]->()`                 | Unbounded traversal | Use `*1..N` with N ≤ 10                |
| Multiple unconnected `MATCH` | Cartesian product   | Connect with relationships             |
| `MATCH (a), (b) WHERE...`    | Cartesian join      | Rewrite with explicit paths            |
| `shortestPath` between sets  | Explosive pairs     | Use WITH/LIMIT first                   |
| Deep ownership chains        | Memory exhaustion   | Limit depth to 6 hops                  |
| Full-text + path traversal   | Slow fan-out        | Filter by index first, traverse second |

### Recommended Depth Limits by Use Case

| Analysis Type                   | Max Hops | Rationale                               |
| ------------------------------- | -------- | --------------------------------------- |
| Direct beneficial ownership     | 1-2      | Immediate ownership is most relevant    |
| Layered structure detection     | 3-4      | Most offshore structures use 2-4 layers |
| Ultimate beneficial owner (UBO) | 4-6      | Regulatory standard is 4 layers         |
| Network clustering              | 2-3      | Shared addresses/officers               |
| Intermediary analysis           | 1-2      | Direct client relationships             |
| Deep investigation              | 6-8      | Exceptional cases only, with LIMIT      |

---

## Example Queries

### 1. Find Beneficial Ownership Chain

```cypher
// Trace ownership from a person through all layers
MATCH path = (p:Person {full_name: 'John Smith'})-[:OWNS|CONTROLS*1..6]->(e:Entity)
WHERE e.status = 'Active'
RETURN path
ORDER BY length(path) ASC
LIMIT 50
```

### 2. Identify Mass Registration Addresses

```cypher
// Find addresses with suspiciously many entities
MATCH (a:Address)<-[:HAS_ADDRESS]-(e:Entity)
WITH a, COUNT(e) AS entity_count
WHERE entity_count > 50
RETURN a.full_address, a.country_code, entity_count
ORDER BY entity_count DESC
LIMIT 20
```

### 3. Intermediary Risk Profile

```cypher
// Profile an intermediary's client base
MATCH (i:Intermediary {name: 'Mossack Fonseca'})<-[:CREATED_BY]-(e:Entity)
OPTIONAL MATCH (e)-[:REGISTERED_IN]->(j:Jurisdiction)
WITH i, j.jurisdiction_code AS jurisdiction, COUNT(e) AS entity_count
RETURN jurisdiction, entity_count
ORDER BY entity_count DESC
```

### 4. PEP Exposure Detection

```cypher
// Find entities connected to politically exposed persons
MATCH (pep:Person {is_pep: true})-[:OWNS|CONTROLS|INVOLVED_IN*1..3]->(e:Entity)
MATCH (e)-[:REGISTERED_IN]->(j:Jurisdiction {is_tax_haven: true})
RETURN pep.full_name, pep.pep_details, e.name, j.name AS jurisdiction
LIMIT 100
```

### 5. Shared Officer Network

```cypher
// Find persons who serve as officers in multiple companies
MATCH (p:Person)-[r:INVOLVED_IN]->(e:Entity)
WHERE r.role IN ['Director', 'Secretary', 'Nominee Director']
WITH p, COUNT(DISTINCT e) AS company_count, COLLECT(e.name)[0..5] AS sample_companies
WHERE company_count > 10
RETURN p.full_name, company_count, sample_companies
ORDER BY company_count DESC
LIMIT 50
```

---

## Data Model Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           PANAMA PAPERS GRAPH SCHEMA                             │
└─────────────────────────────────────────────────────────────────────────────────┘

  ┌──────────┐                                           ┌──────────────┐
  │  Person  │───────────RELATED_TO─────────────────────▶│   Person     │
  │          │                                           │              │
  └────┬─────┘                                           └──────────────┘
       │
       │ OWNS / CONTROLS / INVOLVED_IN
       ▼
  ┌──────────┐         CREATED_BY          ┌──────────────┐
  │  Entity  │◀────────────────────────────│ Intermediary │
  │          │                             │              │
  │ (Company)│                             └──────┬───────┘
  └────┬─────┘                                    │
       │                                          │
       │ OWNS                                     │ HAS_ADDRESS
       ▼                                          ▼
  ┌──────────┐                             ┌──────────────┐
  │  Entity  │─────────HAS_ADDRESS────────▶│   Address    │
  │          │                             │              │
  └────┬─────┘                             └──────────────┘
       │
       │ REGISTERED_IN
       ▼
  ┌──────────────┐
  │ Jurisdiction │
  │              │
  └──────────────┘


  ┌──────────┐
  │  Officer │──────────INVOLVED_IN───────▶ Entity / Company
  │          │
  └──────────┘


LEGEND:
────────▶  Directed relationship
◀────────  Incoming relationship
───────    Bidirectional or flexible
```

---

## Schema Validation Constraints

```cypher
// Ensure data integrity
CREATE CONSTRAINT entity_id_exists FOR (e:Entity) REQUIRE e.entity_id IS NOT NULL;
CREATE CONSTRAINT person_id_exists FOR (p:Person) REQUIRE p.person_id IS NOT NULL;
CREATE CONSTRAINT person_name_exists FOR (p:Person) REQUIRE p.full_name IS NOT NULL;
CREATE CONSTRAINT company_name_exists FOR (c:Company) REQUIRE c.company_name IS NOT NULL;
CREATE CONSTRAINT jurisdiction_code_exists FOR (j:Jurisdiction) REQUIRE j.jurisdiction_code IS NOT NULL;
CREATE CONSTRAINT address_country_exists FOR (a:Address) REQUIRE a.country_code IS NOT NULL;

// Relationship property constraints (Neo4j 5.x)
CREATE CONSTRAINT owns_percentage_range FOR ()-[r:OWNS]-()
  REQUIRE r.ownership_percentage >= 0 AND r.ownership_percentage <= 100;
```

---

## Version History

| Version | Date    | Changes               |
| ------- | ------- | --------------------- |
| 1.0     | 2024-01 | Initial schema design |

---

_Schema designed for ICIJ Panama Papers analysis. Compatible with Neo4j 5.x Enterprise and Community editions._
