# EKG Implementation Plan

**Status:** Draft

---

## 1. Proof of Concept Scope

The proof of concept will ingest four document types and demonstrate traversal, gap detection, and output generation from the resulting graph.

### 1.1 Source Documents

The minimum document set for a proof of concept:

- **Hazard Analysis (HA).** A table with keyed rows. Each row carries a hazard identifier, hazard description, consequence, risk ranking, and mitigation reference. The mitigation reference points to an SRS entry, a procedural control, or a mechanical safeguard.
- **Safety Requirements Specification (SRS).** Exported from Sistema. Contains performance levels, categories, diagnostic coverage, MTTF values, and block diagrams of the safety function architecture, all tied to specific devices by their drawing tags.
- **Failure Modes and Effects Analysis (FMEA).** A table with keyed rows. Each row carries a failure-mode identifier, equipment tag (from the drawing package), failure effect, system reaction, detection method, and SRS or SAT reference.
- **Electrical Drawings.** PDF exports from EPLAN or AutoCAD Electrical. Both tools embed an extensive device tree in the PDF, providing device tags, terminal designations, wire/cable numbers, signal types, and parent-child relationships in the device hierarchy as structured metadata.

These four documents span three of the four graph layers (justification, system, shared entity) and provide enough cross-references to demonstrate core traversals. The procedural layer (SATs) is intentionally absent. Every traversal that needs to reach a verification procedure will halt at the boundary and report the missing edge, which is itself a useful output: the set of SATs that need to be written, derived from the graph.

### 1.2 Required Document Set for a Full Project

Beyond the proof of concept, a complete project would add:

- **Site Acceptance Tests (SATs).** Keyed by SAT number. References FMEA entries, SRS entries, functional requirements, and equipment tags.
- **Factory Acceptance Tests (FATs).** Similar structure to SATs, executed at the vendor's facility.
- **Preventative Maintenance Procedures.** Keyed procedures referencing equipment tags and specifying inspection, test, and maintenance activities.
- **Validation Matrix.** The manually-constructed traceability document that the graph will generate as a query output.
- **I/O List.** Tabular mapping of PLC I/O channels to field devices. A subset of the information in the drawings, useful for cross-checking.
- **Bill of Materials (BOM).** Equipment list with part numbers, manufacturers, and specifications.
- **PLC Source Code.** IEC 61131-3 structured text or function block diagrams. Provides the logical layer: routines, signal reads/writes, system states.
- **P&IDs.** Process and instrumentation diagrams showing the process-level view of instrumentation.

## 2. Node Types

Five node types, one per source document type. Subtypes are properties on the node, not separate types. Validation rules branch on subtype.

### 2.1 HA Entry

Each row in the hazard analysis becomes an HA node. A single hazard ID may have multiple rows when multiple measures are applied to the same hazard. Each row represents a distinct hazard-measure pairing with its own residual risk assessment.

**Key:** Hazard ID + Measure number (e.g., HE-01.2/1, HE-01.2/2)

**Source columns:**
- ID (hazard identifier, e.g., HE-03.5)
- Hazard Category (e.g., Structural Integrity, Person slipping/falling)
- Type of hazard (e.g., Mechanical hazard)
- Potential consequence (e.g., impact, crush)
- Operating mode (e.g., Automatic)
- Use Case (e.g., Normal operation)
- Sub System (grouping, e.g., RV, Track - Pinch Rail, RV Unload/load station)
- Hazardous Situation
- Cause
- Hazardous Event
- Risk type (H or S)
- Assessment (narrative risk description)
- Initial Severity, Probability, Risk Level (pre-measure risk)
- No. (measure number within this hazard)
- Measure (the mitigation description)
- Type of Measure (D = design, PROC = procedural, FS = functional safety)
- Post-measure Severity, Probability, Risk Level (residual risk)
- Measure references (cross-references to documents implementing the measure, may contain multiple entries across multiple subsystems)

**Multi-reference handling:**

The measure reference column can contain a list of SRS entries, potentially spanning multiple subsystems. For example, HE-03.6 references "RCS SRS 14.1 to 14.16, VCS SRS 2, VCS SRS 4.1 to 4.6." The parser splits this field and creates one `mitigated_by` edge per SRS entry. The system prefix (RCS, VCS) is part of the SRS node key to distinguish entries across subsystems. A single measure (one mitigation description) may fan out to many SRS entries; this is one mitigation implemented through many requirements, not many mitigations.

**Validation rules:**
- Must have at least one `mitigated_by` edge to a measure reference.
- Every measure reference must resolve to a valid node (design document, procedure, or SRS entry depending on measure type).
- If Type of Measure is FS, every referenced SRS entry must itself be valid: implemented by devices on a SIF spine, verified by SATs. The HA node's validation depends on the validity of the SRS nodes it references. If any referenced SRS node fails its own validation, the HA node inherits that finding.
- If Type of Measure is PROC, must trace to a procedure that implements the measure.
- If Type of Measure is D, must trace to a design reference.
- Post-measure risk level must be lower than initial risk level.

### 2.2 SRS Entry

Each safety function specification becomes an SRS node. The source document may be a Word document authored to a project template or a Sistema export; the data is the same either way. Each SRS entry follows a consistent structure: a keyed safety function statement, an ISO 13849-1 analysis table, a subsystem chain with individual PFHD values, and a software design description.

**Key:** System prefix + SRS number (e.g., VCS SRS 1.1, RCS SRS 3.1). The system prefix (VCS, RCS) distinguishes SRS entries across subsystems within the same project.

**Source fields:**

*Safety function statement:* A single requirement statement (e.g., "The VCS shall cause a Category 1 stop of the propulsion and yaw actuators when the VStop pushbutton is pressed.")

*Analysis table (ISO 13849-1):*
- Severity (S1/S2)
- Frequency (F1/F2)
- Possibility (P1/P2)
- Required Performance Level (PLr)
- Required Safety Integrity (PL target)
- PFHD range (e.g., >= 10^-8 to < 10^-7)
- Reaction Time Requirement
- Mode (All, Automatic, Manual, etc.)

*Subsystem chain:* A table listing each subsystem in the safety function with its subsystem ID, description, and individual PFHD contribution. Subsystem IDs follow a typed prefix convention:
- SS-I (Input subsystems): field devices and sensors (e.g., SS-I05 Stop Pushbutton, SS-I15 Vehicle Positioning System)
- SS-L (Logic subsystems): safety processors and I/O modules (e.g., SS-L11 VCS TwinSAFE CPU, SS-L12 VCS Siemens F-CPU)
- SS-O (Output subsystems): safe state actuators (e.g., SS-O09 Propulsion System Safe State, SS-O10 Yaw System Safe State)
- SS-X (External subsystems): interfaces to other systems (e.g., SS-X01 Ride Vehicle Safe Linear Position)

Each subsystem ID resolves to a subsystem documented in Section 3 of the SRS, which in turn references specific hardware with part numbers (e.g., Beckhoff EL6910, Siemens 6ES7517-3FP00-0AB0). Those part numbers connect to Device nodes from the drawings.

*Safety function result:*
- Reaction Time achieved (e.g., 2310ms)
- PL Achieved (e.g., PLe)
- Total PFHD (sum of subsystem chain, e.g., 3.2E-8)

*Software design:* Narrative description of the signal flow through the safety function.

**Edges discovered from SRS:**
- Each subsystem ID in the subsystem chain references a device or set of devices. The subsystem ID (SS-I05, SS-L11, SS-O09) resolves to specific hardware documented in Section 3 of the SRS, which maps to Device nodes from the drawings through part numbers and device tags. The edge is `implemented_by` from the SRS node directly to the Device node, with the PFHD value as a property on the edge.
- The SRS node carries a `mitigates` edge from the HA entry that references it.

When an engineer looks at a Device node, they see the SRS entries that depend on it, the FMEA entries that document its failure modes, and the SATs that exercise it. The same device tag connects all three document types through the shared entity layer.

**Validation rules:**
- Must have at least one `mitigates` edge from an HA node.
- Must have a complete subsystem chain: at least one input device (SS-I), at least one logic device (SS-L), and at least one output device (SS-O), each resolving to a valid Device node in the drawings.
- Every device referenced in the subsystem chain must resolve to a valid Device node.
- PL Achieved must meet or exceed PLr.
- Total PFHD must fall within the required range.
- Must have at least one `verified_by` edge to a SAT node.

### 2.3 FMEA Entry

Each row in the FMEA becomes an FMEA node. A single FMEA row may reference multiple devices and multiple SATs, because the same failure mode can affect more than one instance of a device in the system. The parser creates one FMEA node per row and one edge per referenced device and per referenced SAT.

**Key:** FMEA entry number (e.g., ETS.DRVS.1.1)

**Subtypes:**
- **Safety FMEA entry.** At least one referenced device is on a SIF spine. Inherits SRS traceability obligation, SIL-rated detection coverage requirements, and fault-test-lifecycle SAT mandate.
- **Standard FMEA entry.** No referenced device is on a SIF spine. Requires a system reaction and detection method but does not carry safety function obligations.

Subtype is determined by the graph: if any device referenced in the FMEA row appears on a SIF spine in the drawing, the safety subtype applies.

**Source columns:**
- System (grouping, becomes a property or parent node)
- ID (the key)
- Tests (SAT references, may contain multiple, delimited)
- Item (device tag, resolves to Device node)
- Part Manufacturer, Part Number, Part Description (properties on the Device node, not the FMEA node)
- Function (property on the Device node or on the device-to-SIF-spine edge)
- Failure Mode, Potential Cause, Failure Consequences (properties on the FMEA node)
- Detection (property on the FMEA node, candidate for edge to a diagnostic in the logic layer)
- System Reaction (property on the FMEA node)
- OCC, SEV, DET, RPN (properties on the FMEA node)

**Validation rules (all subtypes):**
- Must have at least one `references_device` edge to a Device node.
- Must have a system reaction defined (required property).
- Must have either a detection method or an `addressed_by` edge to a preventative maintenance procedure.
- Every referenced device must have a corresponding SAT that exercises that specific device for this failure mode (correspondence check, not just edge count).

**Additional validation rules (safety subtype):**
- Must have a `references` edge to an SRS node.
- Must have a `tested_by` edge to a SAT node that follows the canonical fault test lifecycle.
- Diagnostic coverage must be consistent with the SRS entry's requirements.

### 2.4 Device

Each device in the drawing's enclosure legend tables becomes a Device node. Device labels conform to IEC 81346 reference designation standards: "+" prefixes denote locations or assemblies (+VCS-0102 = Vehicle Control Cabinet), "-" prefixes denote devices within that location (-CB4, -PS4, -FU04). Panel identifiers (-PNL1, -PNL2) are intermediate containers in the hierarchy. This convention is consistent across CAD tools that follow the standard, including EPLAN and AutoCAD Electrical.

**Key:** Device tag (e.g., +VCS-0102 -CB4, or shorthand CB4 within the context of its cabinet)

**Properties:**
- Device type
- Part number (from enclosure legend, e.g., SIE.5SJ4304-7HG42)
- Type number (e.g., 5SJ4304-7HG42)
- Manufacturer (e.g., SIE, WEI, PXC, MURR, ABB)
- Function text (from enclosure legend, e.g., "Motor Cooling Fan 1")
- Terminal designations
- Signal type
- Wire/cable references (from schematic cross-references)
- Drawing sheet reference (page number in the drawing set)
- Parent container (cabinet, panel, or assembly from EPLAN hierarchy)
- SIF spine membership (derived from the drawing topology)

**Validation rules:**
- Must appear on a current drawing (at least one `shown_on` edge to a drawing sheet).
- Must have at least one FMEA entry (at least one incoming `references_device` edge from an FMEA node).
- If on a SIF spine, must be exercised by at least one SAT (at least one incoming `exercises_device` edge from a SAT node).

### 2.5 SAT

Each site acceptance test becomes a SAT node.

**Key:** SAT number (e.g., SAT-201)

**Subtypes:**
- **FMEA-driven SAT.** Validates an FMEA failure mode's detection and mitigation. Must follow the canonical fault test lifecycle (initial conditions, fault injection, observation, safe state verification, reset, return to normal). Traces to at least one FMEA entry, and may also trace to an SRS entry if the failure mode is on a safety device.
- **Functional SAT.** Tests an input-output relationship from a functional requirement. Traces to a functional requirement or SRS entry.
- **ICD SAT.** Validates a signal crossing a system boundary. Traces to the interface control document and devices on both sides of the boundary.
- **Intermediate-state SAT.** Validates a permissive bit or logic state. Traces to the logic layer and the preconditions that drive the state. Required set generated from the precondition list.

**Properties:**
- SAT subtype
- Referenced FMEA entries
- Referenced SRS entries
- Referenced functional requirements
- Equipment tags exercised
- Pass/fail status
- Execution date

**Validation rules (all subtypes):**
- Must have at least one edge to a justification-layer node (FMEA entry, SRS entry, or functional requirement).
- Every equipment tag referenced must resolve to a valid Device node.
- Must have exactly one `tests_reaction` edge.

**Additional validation rules (FMEA-driven subtype):**
- Must follow the canonical fault test lifecycle template.
- Must have at least one `addresses` edge to an FMEA node.
- If the FMEA entry is a safety subtype, must also have a `references` edge to an SRS node.

## 3. Edges

Edges are discovered from cross-references in the source documents. Each edge carries provenance: the source document, the row or cell where the reference was found, and the document revision.

### 3.1 Edge Types

| Edge | From | To | Discovered in |
|------|------|----|---------------|
| `mitigated_by` | HA Entry | SRS Entry, Procedure, or Safeguard | HA mitigation column |
| `implemented_by` | SRS Entry | Device | SRS subsystem chain table (SS-I/L/O/X IDs resolved to devices) |
| `verified_by` | SRS Entry | SAT | SRS verification reference |
| `references_device` | FMEA Entry | Device | FMEA equipment tag column |
| `tested_by` | FMEA Entry | SAT | FMEA SAT reference column |
| `exercises_device` | SAT | Device | SAT equipment list |
| `addresses` | SAT | FMEA Entry | SAT FMEA reference |
| `references_srs` | SAT / FMEA Entry | SRS Entry | SAT/FMEA SRS reference column |
| `shown_on` | Device | Drawing Sheet | Drawing enclosure legend |
| `contained_in` | Device | Cabinet/Panel/Assembly | IEC 81346 hierarchy (+VCS-0102 > -PNL1 > -CB4) |
| `connected_to` | Device | Device | Drawing schematic cross-references |
| `reads_tag` | Routine/FB/POU | Tag (shared entity) | PLC project tag cross-references |
| `writes_tag` | Routine/FB/POU | Tag (shared entity) | PLC project tag cross-references |
| `calls` | Routine/FB/POU | Routine/FB/POU | PLC project call hierarchy |
| `mapped_to` | Tag (shared entity) | Device | PLC project I/O address to drawing terminal |

### 3.2 Edge Discovery

The ingestion parser reads each document, creates nodes from keyed rows, and creates edges from every cross-reference found in that row. Tag vocabulary is the resolution mechanism: "LT-2105" in the FMEA matches "LT-2105" on the drawing matches "LT-2105" in the SRS. Same string, same device node, edges from multiple documents converging on one shared entity.

Edges that should exist but are not found in the source documents are the gaps that node validation catches. An FMEA row with no equipment tag, an HA row with no mitigation reference: the absence of a cross-reference means the absence of an edge, and the validation rule that requires that edge reports the finding.

## 4. Validation Categories

Validation rules fall into two categories that produce different kinds of output and require different levels of human involvement.

### 4.1 Per-Node Validation (Automated)

Per-node validation checks whether a single node satisfies its own type's rules against its current edges and properties. These checks are deterministic: the node either has the required edges or it doesn't, the referenced device either exists on a current drawing or it doesn't, the SAT either follows the fault test lifecycle template or it doesn't.

Per-node findings are actionable. A missing edge means a missing artifact that needs to be authored. A stale reference means a document that needs to be updated. A format violation means a procedure that needs to be revised. The system reports pass/fail, and the engineer acts on the failures.

Examples: HA entry with no mitigation. FMEA entry with no system reaction. Device with no FMEA entry. SAT referencing a device that doesn't exist on a current drawing. FMEA entry referencing three devices but only two have covering SATs.

### 4.2 Neighborhood Validation (Engineer Review)

Neighborhood validation surfaces patterns that emerge from the relationships between nodes that share edges. The pattern itself is computable, but the disposition requires engineering judgment.

The primary case is overlap detection on induced fault actions. SATs are procedurally generated through atform, and the induced fault is a structured property in the data model, not free text. Two SATs that share the same device tag and the same induced fault property are an exact match. The detection is a straightforward property comparison: group SAT nodes by device tag and induced fault, and any group with more than one SAT is a convergence that gets flagged for engineer review.

This overlap detection moves upstream from post-authoring review to pre-generation. When EKG assembles the data models for a batch of SATs from FMEA entries, it can detect that two FMEA entries on the same device would produce SATs with the same induced fault before handing anything to atform. The engineer resolves it at that point: consolidate into one SAT that covers both failure modes, or differentiate the induced fault to make the tests genuinely distinct. Only after the engineer resolves the overlap do the SATs get generated.

Neighborhood findings are review items, not action items. The system presents the convergence pattern, the nodes involved, and the shared properties. The engineer reviews, confirms or resolves, and the disposition is recorded. The system does not auto-accept or auto-reject neighborhood findings.

## 5. Storage

### 5.1 Requirements

The storage layer must support:

- Typed nodes and edges with properties.
- Adjacency lookups in both directions (outgoing and incoming edges for a given node).
- Depth-first traversal along typed edge patterns.
- Human-readable keys (SAT-201, FM-LT2105-FAULT, HA-PRES-001) rather than surrogate IDs.
- Diff between graph states (before and after an ingest).
- The full graph for a project fits in memory (a few thousand nodes, tens of thousands of edges).

### 5.2 Options

**Graph database (Neo4j, Memgraph).** Native graph storage and query language (Cypher). Typed traversals are first-class operations. Overkill for the data volume but the query model is a direct fit.

**Relational database (SQLite, PostgreSQL).** Nodes as rows in a nodes table, edges as rows in an edges table. Adjacency lookups are joins. DFS is recursive queries. Human-readable keys are the primary key. Simple, portable, well-understood. SQLite in particular requires no server and travels with the application.

**In-memory graph library (NetworkX, igraph).** The graph lives in memory as a Python data structure. Traversal is native. Persistence is serialization to disk (JSON, pickle, or a git-tracked file). Simplest to prototype. No query language, but the traversals are short functions.

**Adjacency table as a flat file.** A CSV or JSON file with human-readable keys. Each row is an edge: source key, edge type, target key, provenance. Loadable into any tool. Git-trackable. The adjacency table is itself a lightweight traceability artifact.

### 5.3 Recommendation

For the proof of concept, start with an in-memory graph (NetworkX or similar) persisted as a git-tracked adjacency file. This gives you fast iteration, no infrastructure dependencies, portability (runs on a laptop at a commissioning site), and the adjacency table as a readable artifact. If the system grows to need concurrent access, query language, or persistence guarantees, migrate to SQLite or Neo4j. The node and edge classes are the same regardless of storage backend.

## 6. Ingestion Architecture

### 6.1 Source of Truth

A local git repository holds the source documents. Engineers author in their existing tools (EPLAN, AutoCAD Electrical, Excel, Word, Sistema) and commit documents to the repo. The git history provides document versioning. Each commit is an ingest event. The diff between commits identifies which files changed and which graph fragments need to be recomputed.

For teams using Confluence, a sync job pulls content from the Confluence API on a schedule or webhook, writes it to the local repo, and commits. The ingestion pipeline only reads from git. The git repo becomes the abstraction layer between where engineers work and where EKG reads. The repo is local, self-contained, and secure. No data leaves the infrastructure.

### 6.2 Parser Per Document Type

Each document type has its own parser. The parser reads the document, produces a set of nodes and edges with provenance, and returns them to the ingestion pipeline.

- **HA parser.** Reads keyed table rows from Excel or Word. Creates HA Entry nodes. Creates `mitigated_by` edges from the mitigation column.
- **SRS parser.** Reads safety function entries from a Word document or Sistema export. Each SRS entry is identified by its heading (e.g., "VCS SRS 1.1: Prevention of propulsion and yaw movement in case of VStop"). The parser extracts the safety function statement, the ISO 13849-1 analysis table, the subsystem chain with PFHD values, and the safety function result (PL achieved, reaction time, total PFHD). Creates SRS Entry nodes keyed by system prefix + SRS number. Subsystem IDs (SS-I05, SS-L11, SS-O09) in the chain are resolved to Device nodes through the part numbers and device tags documented in the subsystem sections. Creates `implemented_by` edges from the SRS node directly to each Device node, with the PFHD value as a property on the edge.
- **FMEA parser.** Reads keyed table rows from Excel or Word. Creates FMEA Entry nodes. Creates `references_device`, `produces_reaction`, `tested_by`, and `references_srs` edges from the relevant columns.
- **Drawing parser (EPLAN PDF).** EPLAN PDF exports contain structured text that provides the device inventory, hierarchy, and wiring topology without requiring OCR or image analysis. The parser extracts three categories of data:

  *Enclosure legend tables.* Each mounting panel page includes a table with columns for Item number, Device tag, Type number, Part number, Manufacturer, and Function text. These are the Device nodes. For example, panel +VCS-0102 -PNL1 lists CB4 (Siemens 5SJ4304-7HG42), CB5, T1 (Murr 86149), and so on. Each row becomes a Device node with the device tag as the key and the part number, manufacturer, and function as properties.

  *Device hierarchy from IEC 81346 reference designations.* IEC 81346 defines a structured naming convention for reference designations: "+" prefixes denote locations/assemblies (e.g., +VCS-0102 = Vehicle Control Cabinet), "-" prefixes denote devices within that location (e.g., -CB4, -PS4, -FU04). Panel identifiers like -PNL1, -PNL2, -PNL3 are intermediate containers. This standard is used by both EPLAN and AutoCAD Electrical. The parser builds the parent-child hierarchy from these prefixes: +VCS-0102 contains -PNL1 which contains -CB4. These become `contained_in` edges in the graph.

  *Cross-references as wiring topology.* Schematic pages carry signal references in a consistent format: "-24V_FU04 / &24VDC MULTILINE/607.1" means signal -24V_FU04 continues on page 607, zone 1 of the 24VDC MULTILINE section. Inter-cabinet references include the cabinet prefix: "+VCS-0101&PLC/487.5" means cabinet VCS-0101, PLC section, page 487, zone 5. Cable references (e.g., +VCS-0101-CBL170, UNITRONIC LiYCY (TP), 12x0.5, 10m, 50V) carry the cable identifier, type, conductor count, gauge, length, and voltage rating. Each cross-reference is an edge between Device nodes. These are parseable with pattern matching against EPLAN's consistent reference format.

  The same approach applies to AutoCAD Electrical PDF exports, which embed a similar device tree structure, though the naming conventions and cross-reference formats differ. A separate parser variant handles the AutoCAD format.

  For NFPA-standard drawings using ISA 5.1 tag conventions (e.g., LT-2105, FV-2101, PSH-3201), the tag format differs but the parsing principle is the same: tags are structured, consistent within a project, and appear in both the drawings and every other document that references the equipment. The graph layer is agnostic to the tag standard. The ingestion layer adapts to whichever convention the project uses.

- **PLC project parser.** PLC projects from Rockwell, Siemens, and Beckhoff contain program structure, tag definitions, I/O mappings, and safety program partitions in parseable formats. Each platform has its own export format:

  *Rockwell:* L5X export (XML). Contains controller-scoped and program-scoped tags, routines, I/O module configurations, and safety task/safety tags as a distinct partition.

  *Siemens:* TIA Portal PLCopenXML export or project archive. Contains organizational blocks, function blocks (FBs), data blocks (DBs), tag tables with I/O addresses, and the F-program (F-DBs, F-FBs) as the safety partition.

  *Beckhoff:* TwinCAT project files (XML-based within a Visual Studio solution). Contains POUs, GVLs, I/O mappings linked to EtherCAT device configurations, and the TwinSAFE configuration as a separate structured export.

  The parser extracts three categories of data from any of these formats:

  *Tag definitions and I/O mappings.* Tag names, data types, and I/O addresses. These resolve to Device nodes from the drawings through the I/O address (a PLC input mapped to a specific terminal on a specific I/O module is the same device shown on the drawing). Tag names also appear in the SAT templates as system_reaction_tags and monitored_tags, connecting the logical layer to the procedural layer.

  *Program structure.* Routines, function blocks, POUs, and the call hierarchy between them. These become nodes in the logical layer with `calls` edges between them. Signal reads and writes within a routine become `reads_tag` and `writes_tag` edges to the shared entity layer.

  *Safety program partition.* The safety task (Rockwell), F-program (Siemens), or TwinSAFE configuration (Beckhoff) is where the SRS safety functions are implemented. The parser identifies which function blocks or routines implement which safety functions, creating `implemented_by` edges from SRS nodes through to specific code elements. This is the logical layer's contribution to the end-to-end traversal from hazard to verification.

### 6.3 Re-ingestion and Diff

When a revised document is committed, the parser runs again on that document and produces a new set of graph fragments. The ingestion pipeline computes the diff against the previous graph state: nodes added, nodes removed, edges added, edges removed, properties changed. The diff triggers re-evaluation of validation rules on all affected nodes. New findings are the set of nodes or edges that now fail validation where they previously passed, or traversal paths that are now blocked where they previously completed.

## 7. Outputs

The graph generates outputs as query projections. Different audiences need different projections of the same underlying graph.

### 7.1 Validation Matrix

Organized by requirement or safety function. One row per obligation chain. Columns for each link in the chain (HA entry, SRS entry, devices, FMEA entries, SATs). Where the traversal from hazard to SAT completes on all-valid nodes and edges, the row is complete. Where it halts, the row shows the gap. This replaces the manually-constructed validation matrix.

### 7.2 Coverage Report

The set of all nodes where traversal halted. Organized by finding type: hazards without mitigations, SRS entries without SATs, FMEA entries without covering tests, devices not exercised by any procedure.

### 7.3 Blast Radius Report

Given a proposed change (a device relocation, a feature addition, a consolidation), the set of all nodes reachable from the changed node through cross-layer edges. Organized into affected document types so the engineer knows which artifacts need revision.

### 7.4 SAT Generation

SAT documents are rendered by [atform](https://github.com/jvalenzuela/atform), a purpose-built tool for generating structured acceptance test documents from data. EKG provides the data model; atform renders the documents.

When the graph identifies a missing SAT, it determines the SAT subtype from the failure mode and system reaction type, then assembles the data model from the graph: the FMEA entry (failure mode description, potential causes, effects), the device under test (reference designator, function), the SRS references, the expected system reactions (PLC tags with faultless and faulted states), monitored tags, preconditions, induced fault description, and HMI alarm message. The SAT subtype determines the procedure template and step structure. Typical subtypes include: fault leading to safe state, fault leading to warning, fault with no system reaction (detection-impossible), output module fault requiring power cycle, analog overrange, panel element fault, stop button fault with cycling requirement, and device-specific variants like dead man switch discrepancy detection. New templates can be created at any time for one-off situations. The graph ingests and tracks custom SATs the same way as templated ones.

Before handing data models to atform, EKG runs the overlap check described in section 4.2: group the pending SAT data models by device tag and induced fault property. Any group with more than one entry means multiple FMEA failure modes would produce SATs with the same physical test action on the same device. EKG flags these for engineer review. The engineer either consolidates the entries into a single SAT covering multiple failure modes or differentiates the induced fault to make the tests distinct. Only after the overlaps are resolved does EKG pass the data models to atform for rendering.

An interface layer between EKG and atform translates the graph's data model into atform's input format. The interface layer maps graph nodes and edge properties to the fields atform expects: test ID, title, purpose text, SRS reference list, FMEA reference list, area, mode, control system, system reaction tags with faultless/faulted test cases, monitored tags, preconditions, induced fault instructions, and HMI messages. The interface layer also selects the appropriate atform template based on the SAT subtype.

The engineer reviews the generated SAT, adjusts as needed, and signs off. The rendered SAT is committed to the git repo, ingested by the SAT parser, and its cross-references become edges in the graph, closing the coverage gap that prompted its generation.

### 7.5 Management of Change Report

For a proposed change, the blast radius report plus the validation matrix delta: which obligation chains were complete before the change and are now broken, which new obligation chains the change creates, and what new artifacts must be authored to discharge them.

### 7.6 Alarm Generation

The graph contains everything needed to generate alarm configurations: the FMEA node carries the failure mode, detection method, and system reaction. The device node carries the device tag and function. The SAT templates already reference HMI alarm messages. The alarm document is a projection of this data, structured for import into the target platform.

An interface layer per target platform translates the graph's alarm data into the platform-specific format:

- Rockwell: alarm object CSV for FactoryTalk
- Ignition: alarm pipeline XML or JSON
- Beckhoff: TwinCAT event configuration
- Siemens: TIA Portal HMI alarm table export

Each alarm entry carries the device tag, the alarm message text, the severity derived from the FMEA (OCC/SEV/DET), the triggering condition from the detection method, and the expected system reaction. The alarm doc is generated from the same FMEA and device data that drives the SATs, ensuring consistency between what the system detects, what the operator sees, and what the SAT verifies.

## 8. MCP Server

EKG exposes its graph operations as an MCP (Model Context Protocol) server. This allows any MCP-compatible client to query the graph without direct access to the storage layer.

### 8.1 Tools

- `get_node`: Look up a node by key. Returns the node's type, properties, and all edges.
- `get_edges`: Get all edges for a node, optionally filtered by edge type.
- `traverse`: DFS from a node along a typed edge pattern. Returns the path, halting on the first invalid node or edge.
- `validate_node`: Run validation rules on a node. Returns pass/fail per rule with the failing rule identified.
- `coverage_report`: Run coverage analysis from a starting set (all HA entries, all SRS entries, etc.). Returns the set of nodes where traversal halted.
- `blast_radius`: Given a node, enumerate all reachable nodes through cross-layer edges.
- `search_nodes`: Find nodes by property values or partial key match.

### 8.2 Clients

LanceLLMot connects to the EKG MCP server as the primary UI and chat interface. Parsival and merLLM can also connect to the same MCP server for ops dashboard integration and system control queries.

## 9. UI Architecture

The EKG UI is a component within LanceLLMot, scoped to a project.

### 9.1 Document Upload

LanceLLMot already handles document uploads. A tag at upload time routes the document: "EKG resource" sends it to the graph ingestion pipeline, "LLM resource" sends it to the chunker for chat context. The rest of the upload flow is unchanged.

### 9.2 Project EKG Interface

Each project has an EKG interface with tabs for each document type:

- **HA tab.** The hazard analysis table reconstituted from HA nodes in the graph. Each cell that contains a cross-reference (mitigation references, SRS references) is a clickable link that navigates to the referenced node's tab.
- **SRS tab.** SRS entries reconstituted from SRS nodes. Each entry shows its safety function statement, analysis table, subsystem chain, and achieved PL. Device tags in the subsystem chain link to the Device tab. SAT references link to the SAT library.
- **FMEA tab.** The FMEA table reconstituted from FMEA nodes. Equipment tags link to the Device tab. SAT references link to the SAT library. SRS references link to the SRS tab.
- **Device tab.** A table of all devices extracted from the drawings. Columns for device tag, type, part number, manufacturer, cabinet, panel, and drawing page. Click a device tag to see all edges: FMEA entries, SRS entries, SATs, PLC tags mapped to it. Click the drawing page reference to open the PDF to that page.
- **Drawings.** PDFs rendered in the browser. The drawings are not reconstituted from the graph. They are reference documents. The graph knows which device is on which page, so navigation from other tabs links directly to the correct drawing page.
- **Validation Matrix tab.** Generated as a query projection from the graph. One row per obligation chain. Cells are clickable: HA entries link to the HA tab, SRS entries to the SRS tab, SAT references open the PDF from the SAT library. Missing cells are highlighted as coverage gaps.
- **SAT Library.** A browsable index of SAT documents generated by atform and rendered as PDFs. Each SAT is indexed by the graph and linked from the validation matrix, the FMEA tab, and the SRS tab.

Every tab is a projection of the graph filtered by node type. Every cross-reference is a navigable link. The engineer sees familiar documents with hyperlinks between them, not a graph visualization.

### 9.3 Chat Interface

The chat sits alongside the tabbed interface. The engineer can ask questions that the tabs don't answer directly: "what's uncovered for VCS SRS 1.1," "what would break if I relocated this device," "which FMEA entries share the same SAT." Queries go through the MCP server and results come back in the chat.

The chat is a research tool, not an authoring tool. It helps engineers gather information from the graph to support their work, including SAT writing, but it does not modify the graph directly. SATs are authored through atform or by hand, committed to the repo, ingested by the parser, and then present in the graph. The chat accelerates the engineer's workflow without bypassing the ingestion pipeline.
