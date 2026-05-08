# Engineering Knowledge Graph (EKG)

**Status:** Concept document

---

## 1. Problem Statement

The artifacts of an industrial control system (drawings, PLC code, P&IDs, I/O lists, FMEA, functional requirements, SRS, hazard analysis, FAT/SAT, preventative maintenance procedures) encode interrelated information about a single system. References to a given device, signal, requirement, or hazard appear in multiple artifacts, in inconsistent formats, with no shared structural index. Maintaining consistency between these artifacts is currently performed manually by experienced engineers, against documentation sets that change continuously through revision and management of change. Coverage gaps, traceability breaks, and revision drift accumulate silently and are typically detected at audit, at commissioning, or following an incident. The problem is most acute for safety instrumented systems, where standards mandate explicit traceability and the cost of gaps is highest, but the same structural problem applies to functional verification, constraint compliance, and any engineering activity with a network of cross-artifact obligations.

The cost of scattered documentation is felt most sharply at the end of a project, when SAT writing, systems changes, and documentation closeout converge under a compressed timeline. Writing a SAT is not difficult in itself. The difficulty is that the information needed to write it is distributed across five or more documents that do not reference each other in a navigable way. The engineer works with the FMEA in one window, the drawing in another, the SRS in a third, reconstructing which device gets which failure injected, what the expected reaction is, and whether the drawing being referenced is even current. Tools exist to streamline SAT formatting and templating, but they address the writing workflow, not the information gathering problem upstream of it. Meanwhile the drawings are still revising, the FMEA is still receiving new entries as commissioning reveals gaps, and the SRS may have changed based on field conditions. The engineer is writing SATs against a moving target, with no way to confirm that the information being written from is current and consistent across the full document set. This is not a tooling problem. It is a structural problem: the connections between artifacts exist only in the engineer's head, and the pressure to produce deliverables arrives at exactly the moment when those connections are changing fastest.

## 2. Why a Graph

A graph in the computer science sense is a set of items (nodes) connected by relationships (edges), where both the items and the relationships can carry types. Common examples: a road network is a graph of intersections connected by roads, where routing means finding a path through it; the web is a graph of pages connected by hyperlinks, where reachability means whether one page can be reached from another by following links. The operations of interest are traversal (following edges from one node to another) and reachability (whether a path of certain edge types exists between two nodes). EKG uses these operations across the documentation set, with each artifact's contents contributing nodes and edges to one connected structure.

An engineering verification effort is a network of obligations. Hazards obligate mitigations. Mitigations obligate verifications. Functional requirements obligate functional tests. FMEA failure modes obligate system reactions. System reactions obligate tests. Tests obligate exercised devices. Constraints obligate compliance evidence. Each obligation is structural: not "should probably be checked" but "the schema requires this relationship to exist or the verification claim is incomplete." The work of engineering verification is, in substantial part, the work of discharging these obligations and demonstrating that they have been discharged. Safety cases are the densest and most rigorous instance, but the structure generalizes.

Three properties of the obligation network distinguish it from simpler bookkeeping problems and rule out the data structures that would otherwise be sufficient.

The obligations cross between artifact types. A hazard lives in the HA. The SIF (safety instrumented function) that mitigates it lives in the SRS. The procedure that verifies the SIF is its own document. The device that the procedure exercises is in the drawings. The code that reads the device is in the PLC source. Five different artifacts, five different formats, authored by different people at different times, but a single obligation chain runs through all of them. A spreadsheet can record that the chain exists; it cannot navigate from one artifact to the next, follow the chain, and identify where it breaks.

The obligations are dense and overlapping. A single device participates in multiple SIFs. A single reaction is verified by multiple SATs because multiple failure modes converge on it. A single FMEA failure mode produces a system reaction that is tested by SATs, addressed by preventative maintenance procedures, detected by code diagnostics, and wired to specific devices. The cross-references are many-to-many. A linear traceability matrix flattens this into rows and columns and loses the relational structure that makes cross-cutting queries possible.

The obligations are not static. Drawings revise. Code revises. FMEAs revise. Procedures revise. Each revision changes which obligations are still discharged and which are now open. The diff between states is the set of new findings: what just broke, what just got covered, what is now incomplete that was complete yesterday. A spreadsheet must be re-walked manually to find these; a graph computes them as a query.

The graph is what is left when the data structure is required to match the structure of the work: cross-artifact navigation through typed obligation chains, many-to-many overlap with structural justification, and continuous re-evaluation as the underlying artifacts change. Tables are flat. Documents do not compose. Narrative is ambiguous. None of these support all three properties simultaneously. The graph does.

A second-order consequence follows from the structural choice. Once the graph is the model, the safety-case deliverables become projections of graph state rather than separately maintained documents. The traceability matrix is a query. The blast-radius analysis is a query. The coverage report is a query. Each is deterministic and carries its provenance back to specific edges and specific source documents. Fixes applied to the graph propagate to every projection that depends on them, which is the property that makes documentation drift reversible.

## 3. Proposed System

EKG (Engineering Knowledge Graph) is a proposed system of record that would represent the cross-artifact relationships of an engineering verification effort as a typed graph and operate on that graph to detect inconsistencies, generate derived deliverables, and propagate corrections. The application that drives the design is safety case management, where obligations are densest and standards mandate explicit traceability, but the schema and operations apply equally to functional verification and constraint compliance.

EKG will ingest authored artifacts from their source tools (CAD, IEC 61131-3 PLC sources, document files, spreadsheets) and construct graph fragments with provenance. The graph will support queries that correspond to standards-mandated traceability claims (IEC 61511, IEC 61508, ISO 13849, IEC 62061).

## 4. Conceptual Model

EKG will model the verification effort as four conceptual graph layers over a shared entity layer.

**Figure 1.** The four-layer conceptual model.

```mermaid
flowchart TB
    J["<b>Justification</b><br/>hazards, requirements,<br/>SIFs, FMEA, standards"]
    L["<b>Logical</b><br/>routines, statements,<br/>conditions, scan tasks"]
    S["<b>System</b><br/>devices, terminals,<br/>wires, panels, drawings"]
    P["<b>Procedural</b><br/>procedures, steps,<br/>evidence, templates"]
    E["<b>Shared entity layer</b><br/>tags, devices, signals,<br/>system states, setpoints"]

    J --- E
    L --- E
    S --- E
    P --- E

    style E fill:#F1EFE8,stroke:#5F5E5A,color:#2C2C2A
    style J fill:#EEEDFE,stroke:#534AB7,color:#26215C
    style L fill:#E1F5EE,stroke:#0F6E56,color:#04342C
    style S fill:#FAECE7,stroke:#993C1D,color:#4A1B0C
    style P fill:#FBEAF0,stroke:#993556,color:#4B1528
```

- **Justification graph.** Hazards, requirements, safety functions, FMEA failure modes, integrity targets, standards clauses. Source artifacts: HA (hazard analysis), SRS (safety requirements specification), FMEA (failure modes and effects analysis), standards library.
- **Logical graph.** Routines, statements, conditions, signals read and written, system states established and cleared. Source artifacts: PLC source files, HMI definitions.
- **System graph.** Devices, terminals, wires, cables, panels, drawing sheets, loops. Source artifacts: wiring diagrams, P&IDs, loop sheets, I/O lists, panel layouts.
- **Procedural graph.** Procedures, the steps that compose them, ordering and prerequisite relationships, evidence records, signoff blocks, step templates. The procedure is the verification unit; individual steps are constituents. Source artifacts: FAT (factory acceptance test), SAT (site acceptance test), LOTO (lockout/tagout), calibration, preventative maintenance procedures.
- **Shared entity layer.** Tags, devices, signals, terminals, system states, setpoints. Cross-artifact references resolve to these nodes via tag normalization.

The four layers are stored as a single graph with typed nodes and edges. Node and edge types are constrained by a schema that mirrors the standards' traceability requirements.

## 5. Ingestion

The artifacts that constitute an industrial control system's documentation set are not unstructured prose. They are tabular, keyed, and cross-referenced by design, because the standards and engineering practices that produce them demand it.

The hazard analysis is a table. Each row is keyed by a hazard identifier. Columns carry the hazard description, the consequence, the risk ranking, and the mitigation reference, typically a SIF or procedural control specified in the SRS. The FMEA is structured the same way: each row is keyed by a failure-mode identifier, with columns for the equipment tag (drawn from the drawing package), the failure effect, the system reaction, the detection method, and the SRS or SAT reference that addresses it. The SRS is a list of requirements and calculations, each referencing the actual equipment used in the design by the tags assigned in the drawings. The drawings themselves, whether drafted to NFPA or IEC conventions, are highly structured: device designations, terminal identifiers, wire numbers, and signal references follow defined schemas. Every other document in the set (FATs, SATs, validation matrices, preventative maintenance procedures) references back to these artifacts using the same tag vocabulary.

This means the primary ingestion path is deterministic parsing of structured data: reading keyed rows from tables, resolving tag references against the drawing package, and following explicit cross-references between documents. The graph fragments produced by ingestion carry provenance to the source artifact, row, and cell. Where artifacts contain free-text fields (notes columns in an FMEA, narrative descriptions in a hazard analysis), an LLM may assist in extracting structured content, but this is at the margins. The core of the ingestion pipeline operates on data that is already organized for exactly the kind of cross-referencing EKG formalizes.

Ingestion is not a one-time event. As a project progresses, artifacts revise: drawings update, FMEA rows are added, PLC code changes, procedures are rewritten. Each time a revised artifact is re-ingested, the parser produces a new set of graph fragments from that artifact. The difference between the previous graph state and the new one is a structured diff: nodes added, nodes removed, edges added, edges broken, edge validity changed. This diff is what makes it possible to ask "what did this revision break?" and "what does this proposed change affect?" The cascade and blast-radius operations described in section 8 are both computed from the diff that ingestion produces.

## 6. Cross-Layer Edges

Cross-layer edges encode the standards-mandated relationships between artifact contents. Examples:

- `verified_by` (justification → procedural): a requirement is verified by a procedure as a whole, not by individual steps within it.
- `mitigates` (justification → justification): a SIF mitigates a hazard.
- `produces_reaction` (justification → justification): an FMEA failure mode produces a system reaction.
- `tested_by` (justification → procedural): a system reaction is validated by a procedure step injecting the failure and observing the reaction.
- `reads_tag`, `writes_tag` (logical → shared): a code statement reads or writes a signal.
- `implements_signal` (system → shared): a device carries a signal.
- `exercises_device` (procedural → shared): a procedure step touches a device, contributing to procedure-level coverage.
- `requires_state`, `establishes_state` (procedural → shared): a step depends on or produces a system state.

A SIF spine is the set of devices, wiring, and logic that together implement a single safety instrumented function. It is the physical and logical path from the field sensor through the logic solver to the final element. Every device on the spine participates in the safety function, and every device on the spine must be individually verified.

Figure 2 shows one safety function's connections across all four layers via a single shared device.

**Figure 2.** Cross-layer connections for one safety function through a single shared device.

```mermaid
flowchart LR
    H["<b>HA</b><br/>HA-PRES-001<br/>overpressure"]
    R["<b>SRS</b><br/>SF-PRES-001<br/>SIL 3 trip"]
    Code["<b>PLC code</b><br/>R_TripLogic<br/>writes TRIP_CMD"]
    SAT["<b>SAT 201</b><br/>full procedure"]
    Step["<b>Step 201-007</b><br/>injects 2oo3 trip"]
    Tag["<b>LT-2105</b><br/>shared device"]
    Drawing["<b>Drawing</b><br/>Sheet 301"]

    H -- "mitigates" --> R
    R -- "verified_by" --> SAT
    SAT -- "contains" --> Step
    Step -- "exercises_device" --> Tag
    Code -- "reads_tag" --> Tag
    Drawing -- "implements_signal" --> Tag

    style Tag fill:#F1EFE8,stroke:#5F5E5A,color:#2C2C2A
    style H fill:#EEEDFE,stroke:#534AB7,color:#26215C
    style R fill:#EEEDFE,stroke:#534AB7,color:#26215C
    style Code fill:#E1F5EE,stroke:#0F6E56,color:#04342C
    style Drawing fill:#FAECE7,stroke:#993C1D,color:#4A1B0C
    style SAT fill:#FBEAF0,stroke:#993556,color:#4B1528
    style Step fill:#FBEAF0,stroke:#993556,color:#4B1528
```

### 6.1 What the Graph View Provides

Representing the verification effort as a typed graph, rather than as a list of documents and a mental model held in the heads of experienced engineers, gives the engineer queries and structural checks that are otherwise expensive or impractical to perform. The underlying mechanism is described in section 7: depth-first traversal that walks only valid nodes and edges, halting where validity fails. The point where the traversal stops is the finding. Three capabilities are worth naming concretely.

#### Redundancy Detection

When multiple SATs converge on the same physical action, the graph surfaces the convergence for review. Without the graph, this is invisible at the test-list level: each SAT looks complete on its own, with its own FMEA reference and its own observed reaction. With the graph, the convergence is structural: N SATs with `executes_action` edges to one Action node, and the engineer can see at a glance whether the tests are genuinely distinct (different FMEA modes routed through structurally different action paths) or duplicates wearing different hats. The decision (consolidate the SATs into one or differentiate them by a more specific physical action) is the engineer's. The graph's job is to make the question askable.

**Figure 3.** Multiple SATs converging on a shared action and reaction.

```mermaid
flowchart LR
    FM1["FMEA<br/>PSU failure"]
    FM2["FMEA<br/>wire break"]
    FM3["FMEA<br/>wire short<br/>to ground"]
    FM4["FMEA<br/>PLC input fail"]

    SAT1["SAT-PSU.1"]
    SAT2["SAT-PSU.2"]
    SAT3["SAT-PSU.3"]
    SAT4["SAT-PSU.4"]

    Action["<b>Action</b><br/>pull wire<br/>24V-PSU-1"]
    RX["<b>Reaction</b><br/>PSU fault alarm<br/>at PLC input"]

    FM1 -. "addressed by" .-> SAT1
    FM2 -. "addressed by" .-> SAT2
    FM3 -. "addressed by" .-> SAT3
    FM4 -. "addressed by" .-> SAT4

    SAT1 -- "executes_action" --> Action
    SAT2 -- "executes_action" --> Action
    SAT3 -- "executes_action" --> Action
    SAT4 -- "executes_action" --> Action

    SAT1 -- "tests_reaction" --> RX
    SAT2 -- "tests_reaction" --> RX
    SAT3 -- "tests_reaction" --> RX
    SAT4 -- "tests_reaction" --> RX

    style FM1 fill:#EEEDFE,stroke:#534AB7,color:#26215C
    style FM2 fill:#EEEDFE,stroke:#534AB7,color:#26215C
    style FM3 fill:#EEEDFE,stroke:#534AB7,color:#26215C
    style FM4 fill:#EEEDFE,stroke:#534AB7,color:#26215C
    style RX fill:#EEEDFE,stroke:#534AB7,color:#26215C
    style SAT1 fill:#FBEAF0,stroke:#993556,color:#4B1528
    style SAT2 fill:#FBEAF0,stroke:#993556,color:#4B1528
    style SAT3 fill:#FBEAF0,stroke:#993556,color:#4B1528
    style SAT4 fill:#FBEAF0,stroke:#993556,color:#4B1528
    style Action fill:#FBEAF0,stroke:#993556,color:#4B1528
```

In Figure 3, four FMEA modes for a 24V power supply alarm (PSU failure, wire break, wire short, PLC input failure) are each addressed by their own SAT. All four SATs perform the same physical operation (pull the wire). The graph shows the four-into-one convergence on both the Action node and the Reaction node simultaneously. The schema flags it; the engineer reviews whether to consolidate or to differentiate by physical action. The fan-out is structurally identical across many situations: distributed E-stop stations, transmitter loops, signal paths feeding shared response chains, and the same query surfaces redundancy in all of them.

#### Coverage Gap Detection

Coverage gap detection is a traversal that starts at a justification-layer node and attempts to reach the procedural layer along the required edge pattern. At each node along the way, the node's validation rules are evaluated (section 7.3). If a node fails its own rules (a missing edge, a broken equipment reference, a format violation), the traversal halts there, and the failing rule is the finding. If the traversal reaches the procedural layer with every node and edge valid along the way, the obligation chain is complete.

Some nodes generate their own required-edge sets from their architectural attributes. A permissive bit's precondition list determines its required SAT family; a voting architecture determines the required input-output relationships; a composite reaction's sub-behavior list determines the required verification steps within its covering SAT. These are validation rules on the node: the node's specification says what edges should exist, and the rule checks whether they do. An engineer asking "what hasn't been tested yet" gets a query result: the set of nodes where traversal halted.

**Figure 4.** Coverage of a permissive bit through composition: each input path verified by its own SAT, the bit-forced SAT verifying the output side.

```mermaid
flowchart LR
    SAT_a["SAT-DA.A<br/>restraint"]
    SAT_b["SAT-DA.B<br/>gate"]
    SAT_c["SAT-DA.C<br/>E-stop"]
    SAT_d["SAT-DA.D<br/>ready state"]
    SAT_n["SAT-DA.N<br/>operator key"]

    State["<b>State</b><br/>bit_DispatchAllowed"]

    SAT_force["SAT-DA.X<br/>force bit"]
    RX["<b>Reaction</b><br/>dispatch enabled"]

    SAT_a -- "clears_state" --> State
    SAT_b -- "clears_state" --> State
    SAT_c -- "clears_state" --> State
    SAT_d -- "clears_state" --> State
    SAT_n -- "clears_state" --> State

    State -- "drives_reaction" --> RX
    SAT_force -- "tests_reaction" --> RX

    style State fill:#E1F5EE,stroke:#0F6E56,color:#04342C
    style RX fill:#EEEDFE,stroke:#534AB7,color:#26215C
    style SAT_a fill:#FBEAF0,stroke:#993556,color:#4B1528
    style SAT_b fill:#FBEAF0,stroke:#993556,color:#4B1528
    style SAT_c fill:#FBEAF0,stroke:#993556,color:#4B1528
    style SAT_d fill:#FBEAF0,stroke:#993556,color:#4B1528
    style SAT_n fill:#FBEAF0,stroke:#993556,color:#4B1528
    style SAT_force fill:#FBEAF0,stroke:#993556,color:#4B1528
```

Figure 4 shows the dispatch-allowed bit on a ride system. The bit is high only when every precondition is satisfied (restraints locked, gates closed, no E-stop active, ride in ready state, operator key engaged) and the bit gates the dispatch action. The graph generates the required SAT set from the bit's precondition list: one SAT per precondition (verifying that disturbing it drops the bit) plus a bit-forced SAT (verifying that the dropped bit blocks dispatch). N preconditions yield at minimum N+1 required SATs, and the graph confirms each requirement has a covering test. A missing precondition SAT shows up immediately as a validation finding. So does the case where every precondition SAT is authored but no bit-forced SAT exists, the input-side verification is complete, the output-side is not, and the composition argument is broken. The schema flags it before the verification effort is signed off, not at audit.

#### Composition Queries

The same traversal mechanism lets the engineer ask the question that's hard to ask without a graph: how many ways does this state get triggered, and how many of them are verified? The query runs in either direction. On the input side it asks how many paths set or clear a bit, where each path is a separate traversal, and each must reach a valid SAT. On the output side, for a reaction that decomposes into sub-behaviors with their own intermediate observables, it asks how many of the reaction's constituent observations have valid traversal paths to covering tests. The engineer gets an authoritative answer to a question that previously required walking through the test plan, the FMEA, and the design specs in parallel.

The patterns shown so far, action redundancy and intermediate-state composition (input-side and output-side), are illustrative rather than exhaustive. Real verification efforts contain many more structural patterns: bypass and override paths, latched-state recovery sequences, mode-dependent enabling conditions, time-windowed behaviors, alarm hierarchies, sequence interlocks. Each has its own characteristic shape in the graph and its own node validation rules. The framework handles them all the same way (typed nodes and edges, propositional validation rules per node type, depth-first traversal that halts on invalidity), and the reader who has followed the patterns above should be able to recognize the shape of additional patterns when they encounter them in their own work.


## 7. Traversal, Validity, and Goal Structuring Notation

### 7.1 The Algorithm Is Depth-First Search

The operations described in section 6.1 (coverage gap detection, redundancy detection, composition queries) and the operations described in section 8 (blast radius, cascade, traceability generation) are all instances of the same underlying algorithm: depth-first search over typed edges.

The traversal walks only valid nodes and edges. At each node it visits, the node evaluates its own validation rules (section 7.3). At each edge it crosses, the edge evaluates its own validity predicate (section 7.2). If a node fails any of its rules, or an edge is invalid, the traversal stops there. The point where the traversal halts is the finding.

End-to-end validation of a verification claim means being able to traverse the graph from the justification-layer origin (a hazard, a failure mode, a requirement) all the way to the procedural-layer evidence (a SAT, a preventative maintenance procedure) on a path of exclusively valid nodes and edges. If the traversal completes, the claim is structurally supported. If it cannot complete, the claim is broken, and the engineer knows exactly where, because the traversal stopped at the node or edge that failed.

Coverage gap detection starts at a hazard node and walks depth-first along the typed edge pattern `mitigated_by → verified_by → exercises_device`. If a node along that path fails its validation rules (the SIF has no `verified_by` edge, or the SAT references a device that doesn't exist on a current drawing), the traversal halts and that failure is the finding. The FMEA chain works identically: start at a failure-mode node, walk `produces_reaction → tested_by`, halt on the first invalidity. Blast radius is depth-first search from a changed node, following all outgoing cross-layer edges, collecting every reachable node. Cascade is the same traversal triggered by the diff that ingestion produces.

Redundancy detection is the one case that works in the opposite direction: not a traversal from a starting node but an inspection of incoming edges at a target node. When an Action node has multiple incoming `executes_action` edges, multiple SATs converge on the same physical operation. This is a lookup on the node's incoming adjacency list, not a search.

### 7.2 Edge Validity

Every edge has a binary state: valid or invalid. The state is computed from the current revision status of the artifacts the edge depends on. A `verified_by` edge from a requirement to a procedure is valid only if the requirement is current, the procedure has been ingested at its current revision, and the requirement is referenced in the procedure's verification scope with provenance. An invalid edge halts traversal just as an invalid node does. The traversal cannot cross it, and the edge becomes the finding. Edge validity catches drift: relationships that were valid and broke as artifacts revised.

Figure 5 shows the two obligation chains side by side. On the hazard chain, HA-PRES-001 is mitigated by a SIF that is verified by a procedure. On the FMEA chain, failure mode FM-LT2105-FAULT produces a system reaction (force vote to trip) that is tested by a SAT step injecting the fault. HA-TEMP-001 has no mitigation; FM-PT3201-DRIFT has a documented reaction with no test exercising it. Both are structurally invalid at different points in their chains.

**Figure 5.** Hazard chain and FMEA chain validity, showing valid and invalid examples side by side.

```mermaid
flowchart LR
    subgraph Hazard["Hazard chain"]
        H1["<b>HA-PRES-001</b>"]
        SIF1["SIF-PRES-001"]
        SAT1["SAT 201"]
        H1 -- "mitigated_by" --> SIF1
        SIF1 -- "verified_by" --> SAT1

        H2["<b>HA-TEMP-001</b><br/>no mitigation"]
    end

    subgraph FMEA["FMEA chain"]
        FM1["<b>FM-LT2105-FAULT</b>"]
        Rx1["Reaction:<br/>force vote to trip"]
        Step1["SAT step 201-007<br/>injects fault"]
        FM1 -- "produces_reaction" --> Rx1
        Rx1 -- "tested_by" --> Step1

        FM2["<b>FM-PT3201-DRIFT</b>"]
        Rx2["Reaction:<br/>diagnostic alarm"]
        Missing(["no tested_by edge"])
        FM2 -- "produces_reaction" --> Rx2
        Rx2 -.-> Missing
    end

    style H1 fill:#EEEDFE,stroke:#534AB7,color:#26215C
    style SIF1 fill:#EEEDFE,stroke:#534AB7,color:#26215C
    style SAT1 fill:#FBEAF0,stroke:#993556,color:#4B1528
    style H2 fill:#FCEBEB,stroke:#A32D2D,color:#501313
    style FM1 fill:#EEEDFE,stroke:#534AB7,color:#26215C
    style Rx1 fill:#EEEDFE,stroke:#534AB7,color:#26215C
    style Step1 fill:#FBEAF0,stroke:#993556,color:#4B1528
    style FM2 fill:#EEEDFE,stroke:#534AB7,color:#26215C
    style Rx2 fill:#EEEDFE,stroke:#534AB7,color:#26215C
    style Missing fill:#FCEBEB,stroke:#A32D2D,color:#501313
```

Figure 6 shows a single edge transitioning from valid to invalid as a result of a drawing revision, breaking the path that depends on it.

**Figure 6.** Edge validity changing on drawing revision.

```mermaid
flowchart LR
    subgraph Before["Before drawing revision"]
        H1["Hazard"] -- "valid" --> R1["Requirement"]
        R1 -- "valid" --> SAT1["SAT procedure"]
        SAT1 -- "valid" --> D1["Device LT-2105"]
    end

    subgraph After["After drawing revision"]
        H2["Hazard"] -- "valid" --> R2["Requirement"]
        R2 -- "valid" --> SAT2["SAT procedure"]
        SAT2 -. "invalid" .-> D2["Device LT-2105"]
    end

    style H1 fill:#EEEDFE,stroke:#534AB7,color:#26215C
    style R1 fill:#EEEDFE,stroke:#534AB7,color:#26215C
    style SAT1 fill:#FBEAF0,stroke:#993556,color:#4B1528
    style D1 fill:#F1EFE8,stroke:#5F5E5A,color:#2C2C2A
    style H2 fill:#EEEDFE,stroke:#534AB7,color:#26215C
    style R2 fill:#EEEDFE,stroke:#534AB7,color:#26215C
    style SAT2 fill:#FBEAF0,stroke:#993556,color:#4B1528
    style D2 fill:#FCEBEB,stroke:#A32D2D,color:#501313
```

### 7.3 Node Self-Validation

Every node in the graph has a type, and every type carries validation rules. A node is valid when all of its type's rules evaluate to true against the node's current edges, attributes, and the validity of its referenced nodes. The rules are propositional: each one is a statement that is either true or false given the current graph state, and they compose: a node with five rules is valid only when all five are satisfied.

A SAT node illustrates how these rules build up. At minimum, a SAT must trace back to a justification (a functional requirement, a failure mode, an SRS entry, or some combination of the three). That is the first rule: does this SAT have at least one incoming edge from a justification-layer node? If the SAT references an SRS entry or an FMEA failure mode, a second rule applies: the SAT must follow the canonical fault test format, the nine-step lifecycle that walks through initial conditions, fault injection, observation, reset, and return to normal. A SAT that traces to a functional requirement but not to an SRS or FMEA entry may have a different structural template; the type of justification determines which format rules apply. A third rule checks the SAT's equipment references: every device tag named in the SAT must resolve to a valid node in the system layer (a device that exists on a current drawing, at the designated terminal, with the correct signal type). If any referenced device fails its own validation, the SAT inherits that invalidity.

The rules for a SAT node, then, are:

- The SAT must reference at least one justification-layer node (functional requirement, FMEA failure mode, or SRS entry).
- If the SAT references an SRS entry or FMEA failure mode, it must conform to the canonical fault test template.
- Every equipment tag referenced in the SAT must resolve to a valid device node in the system layer.
- The SAT must have exactly one `tests_reaction` edge identifying the system reaction it validates.

Each rule is independently evaluable and each produces a true/false result. The SAT node is valid when the conjunction of all its rules is true. A rule that fails is a finding, and the finding carries the specific rule that failed, so the engineer knows whether the problem is a missing justification reference, a format violation, or a broken equipment tag.

Other node types carry their own rule sets, and the same pattern of conditional rules applies. A hazard node must have a `mitigated_by` edge. That is the first rule. But the type of mitigation determines what further obligations follow. If the mitigation is a safety instrumented function, the hazard must also trace to an SRS entry specifying the function and to SATs verifying it. If the mitigation is a procedural control, the hazard must trace to the procedure that implements it. A mechanical safeguard may require only a design reference. The hazard node's rule set branches on mitigation type: the first rule is unconditional, the subsequent rules are conditional on what the first rule found. A device node must appear on a current drawing and must have at least one FMEA failure mode documented. An FMEA failure-mode node must have a `produces_reaction` edge and either a detection method or a preventative maintenance procedure. The rules are specific to each type but the evaluation machinery is the same: enumerate the rules, evaluate each against current graph state, report any that fail.

This is where the system's complexity lives, and where it scales. Adding a new validation rule to a node type is adding a new propositional check, not rewriting an algorithm. The rule set for a given node type can start simple and grow as the engineering team's understanding of what constitutes completeness deepens. A first implementation might check only that required edges exist. A later iteration might check that referenced documents are at current revision, that tag formats conform to project naming conventions, or that SIL ratings are consistent between the SRS entry and the SAT that verifies it. Each addition is a new rule on a node type, evaluated the same way as every other rule.

### 7.4 Goal Structuring Notation and the Justification Layer

Goal Structuring Notation (GSN) is a graphical notation developed at the University of York in the 1990s for presenting safety arguments as directed graphs. A GSN diagram connects top-level safety claims (goals) to sub-goals, strategies, contexts, assumptions, and evidence nodes. The notation is standardized and widely used in railway, automotive, nuclear, and aerospace safety cases. It is the established way to express the *argument* that a system is safe: the reasoning structure that connects a top-level claim ("the system is acceptably safe") through intermediate claims to the evidence that supports them.

EKG's justification layer (hazards, requirements, safety functions, FMEA failure modes, integrity targets) is modeling the same territory that GSN addresses, but from the artifact side rather than the argument side. GSN says: here is the argument structure that justifies the safety claim. EKG says: here is whether the evidence that argument depends on actually exists, is current, and is structurally complete. The two are complementary. A GSN goal node that claims "SIF-PRES-001 is verified" is supported by evidence that a SAT exists and has passed. EKG's traversal from the SIF node to the SAT node along `verified_by` edges is the structural check that confirms or denies whether that evidence is present.

EKG's justification layer should adopt GSN as the notation for its argument structure. The hazard and FMEA chains described above, and the obligation relationships between them, map naturally to GSN goal decomposition. Hazard nodes become top-level goals. Mitigation nodes become sub-goals. Verification nodes become evidence references. The validation rules that EKG evaluates at each node correspond to GSN's requirement that every goal be supported: a goal with no supporting evidence or sub-goal is an undischarged obligation in both frameworks. Adopting GSN gives the justification layer an established notation that auditors and safety assessors already understand, and it gives GSN practitioners a system that can automatically check whether the argument structure they have drawn is backed by current, complete evidence in the underlying artifacts.

## 8. Supported Operations

The following operations are derived from the traversal and node self-validation machinery described in section 7:

- **Coverage analysis.** Traverse from each justification-layer node toward the procedural layer. Nodes where traversal halts (because a validation rule fails or a required edge is missing) are the coverage gaps: hazards without mitigations, mitigations without verifications, FMEA failure modes without system reactions, system reactions without tests, devices not exercised by any procedure.
- **Cross-artifact consistency checking.** Identify references in one artifact (e.g., a tag in a SAT step) that do not resolve to current-revision content in another (e.g., the corresponding drawing).
- **Traceability matrix generation.** Render the standards-required traceability matrix as a query over current graph state rather than as a maintained document.
- **Blast radius analysis.** Given a proposed or executed change to an artifact, enumerate the set of all artifacts transitively affected through cross-layer edges.
- **Derived deliverable generation.** Produce SATs, preventative maintenance procedures, traceability matrices, and coverage reports as deterministic functions of current graph state.
- **Alarm configuration generation.** Produce platform-specific alarm documents from the same FMEA and device data that drives the SATs. Each alarm entry carries the device tag, the alarm message, the severity, the triggering condition from the FMEA's detection method, and the expected system reaction. Today, alarm configurations are maintained as a separate document, authored by hand, cross-referenced to the FMEA and the SATs manually. When an FMEA entry changes, the alarm document must be updated independently, and so must the SAT that verifies the alarm is displayed. Three separate documents maintained in parallel, describing the same information, with no structural guarantee that they agree. The graph eliminates this: the FMEA node, the alarm message, and the SAT that checks for it are all projections of the same data. A change to the failure mode or detection method propagates to both the alarm configuration and the SAT, because both are generated from the same graph state.
- **Causal walk-back.** Given a system reaction (e.g., a final element actuating), walk backward through the logical and shared layers to enumerate the causal contributors and their physical origins.
- **Cascade on revision.** When source artifacts revise, recompute affected node and edge validities and surface the differences as findings.

### 8.1 Cascade on Revision

The cascade operation will be the mechanism by which node and edge validation becomes continuous rather than episodic. Each ingest produces a new graph state; the diff against the previous state identifies which nodes and edges have changed. The validation rules on those nodes are re-evaluated, and any node that now fails a rule it previously passed, or any traversal path that is now blocked where it previously completed, is a new finding. Three representative cases:

*A new device appears in a drawing revision.* The drawing parser will discover a device node that did not exist in the previous graph state. Once the node is added to the shared entity layer, its validation rules will run against it. The device has no `produces_reaction` edges from any FMEA failure mode (no documented failure modes), no `exercises_device` edges from any procedure step (untested), and if it has been wired into the SIF spine in the logic layer, the SIF now fails its own validation because one of its devices is unverified. A single drawing change will produce multiple findings, each pointing at a different unfilled obligation.

*A device designation changes.* The drawing parser will see a new identifier (e.g., LT-2105 to LT-2105A). The tag normalizer will collapse common aliases (whitespace, hyphenation, case) but a deliberate redesignation is a real identity change and will produce a new node. The old node loses its drawing-side anchor (no `implements_signal` edge from any current drawing points to it), and any artifact still referencing the old name (PLC code, FMEA, SAT) now points at a node that fails its own validation rules. The new node fails because nothing else has caught up to it. Findings surface as "tag LT-2105 in PLC code does not resolve to a current device" and "device LT-2105A has no FMEA, no procedure, no code references."

*Logic or tag references change.* The PLC source parser will discover new `reads_tag` or `writes_tag` edges, or find that previous edges no longer exist. If a SIF's trip logic references a tag that was not previously on the SIF spine, validation rules will run against that tag: is there a procedure step exercising it, are there FMEA failure modes producing reactions for it, is it on a drawing. Each missing edge is a finding.

All three cases should be handled by the same mechanism. There should be no special-case logic for "device added" vs. "tag renamed" vs. "logic changed"; each is a difference between two graph states, and the validity checks will fire on whatever nodes and edges the diff touches.

Figure 7 shows the new-device case. Before the drawing revision, the graph contains the existing SIF spine. After ingest, LT-2110 is a new node; its validation rules will produce three findings simultaneously.

**Figure 7.** Cascade findings produced when a new device appears in a drawing revision.

```mermaid
flowchart LR
    Rev(["Drawing revision:<br/>LT-2110 added<br/>to SIF spine"])

    Rev --> F1["<b>Finding</b><br/>LT-2110 has no<br/>FMEA failure modes"]
    Rev --> F2["<b>Finding</b><br/>LT-2110 not exercised<br/>by any procedure"]
    Rev --> F3["<b>Finding</b><br/>SIF-PRES-001 spine<br/>now fails validation"]

    style Rev fill:#FAEEDA,stroke:#854F0B,color:#412402
    style F1 fill:#FCEBEB,stroke:#A32D2D,color:#501313
    style F2 fill:#FCEBEB,stroke:#A32D2D,color:#501313
    style F3 fill:#FCEBEB,stroke:#A32D2D,color:#501313
```

#### Replacement vs. Addition

A device added to a SIF spine and a device that *replaces* an existing device in a SIF spine produce the same shape of diff at the node level (one node added, possibly one node removed) but represent operationally different situations. A like-for-like replacement of LT-2105 with LT-2105B in the same vote role does not change the spine's structure; the role and its failure modes are already documented, and the engineering work is to rebind existing FMEA, procedure, and code references from the old device to the new one. The SIF's validation was satisfied before the replacement and remains satisfied after, provided the rebindings are made. Re-validation may not be required at all if the replacement is identical in function and calibration.

For EKG to distinguish replacement from addition, the schema must model SIF spines at the level of *roles* (vote-input positions, final-element positions, reset paths) and treat devices as instances bound to those roles. A change that preserves the role binding but changes the device instance is a replacement; a change that creates a new role with no prior occupant is an addition. The cascade operation should classify findings accordingly: a replacement will produce a single rebind finding ("primary vote role: LT-2105 replaced by LT-2105B; rebind FMEA, procedure, code references"); an addition will produce the structural-gap findings shown in Figure 7. EKG will present the classified change.

### 8.2 Late-Stage Change Management

The case where the cost of incomplete cross-artifact knowledge is highest is late-stage change: a change discovered at FAT, commissioning, PSSR, or after process introduction. By that point the artifact set is large, the cross-references have been built up over many revisions, and the engineering pressure is to ship. A change that an experienced engineer would handle correctly with three weeks of careful review must instead be handled in three days under schedule pressure, often by someone who wasn't present when the original references were authored. Missed downstream artifacts at this stage produce deviations at FAT, findings at PSSR, unplanned outages at startup, or, worst case, quiet inconsistencies in the safety case that surface only after an incident.

The blast-radius operation is the prospective counterpart to cascade: given a *proposed* change rather than an ingested one, the same edge traversals enumerate the artifacts that would be affected if the change were made. The structural answer it provides scales across the change types that show up in late-stage work.

**Device removal or relocation.** The simplest case. A device is removed or its identity changes (re-tagged, moved to a different I/O channel). Blast radius enumerates every artifact that references the device through any cross-layer edge: drawings showing the device, PLC code reading or writing its tag, FMEA entries naming it, SATs exercising it, PSSR checklist items referencing it, traceability matrix cells citing it. Figure 8 shows the case for a single I/O channel change.

**Figure 8.** Blast radius of a single I/O channel change.

```mermaid
flowchart LR
    Change(["Proposed change:<br/>LT-2105 moved to AI-4"])

    Change --> D1["Drawing<br/>Sheet 301"]
    Change --> D2["Drawing<br/>Sheet 201<br/>title block"]
    Change --> Code["PLC code<br/>I/O mapping"]
    Change --> FMEA["FMEA row 7<br/>diagnostic ref"]
    Change --> SAT["SAT 201<br/>re-execution"]
    Change --> PT["PM-201<br/>preventative maintenance"]
    Change --> RTM["RTM<br/>verification cell"]

    style Change fill:#FAEEDA,stroke:#854F0B,color:#412402
    style D1 fill:#FAECE7,stroke:#993C1D,color:#4A1B0C
    style D2 fill:#FAECE7,stroke:#993C1D,color:#4A1B0C
    style Code fill:#E1F5EE,stroke:#0F6E56,color:#04342C
    style FMEA fill:#EEEDFE,stroke:#534AB7,color:#26215C
    style SAT fill:#FBEAF0,stroke:#993556,color:#4B1528
    style PT fill:#FBEAF0,stroke:#993556,color:#4B1528
    style RTM fill:#EEEDFE,stroke:#534AB7,color:#26215C
```

**Feature addition.** A feature gap is discovered at commissioning, for example a missing alarm condition or a missing interlock. Adding a feature is structurally a small new justification chain: a new requirement (or a revision to an existing one), a new behavior in the logic, possibly a new device or a new use of an existing device, a new SAT verifying the new input-output relationship. Blast radius is less about *what existing artifacts are affected* and more about *what new artifacts must be authored to discharge the new obligations the feature creates*. The node self-validation machinery from section 7.3 handles this directly: the new requirement node fails its validation rules (no `verified_by` edge) until the SAT is authored. The new SAT fails its own rules (no `tests_reaction` edge) until the reaction is documented in the FMEA. The traversal from the new requirement cannot complete until every node along its path passes. The graph forces the new feature to be fully justified before it appears as complete.

**Feature consolidation and extension.** The hardest case. Two existing features are consolidated into one with extended scope, for example two separate high-pressure trips (one per vessel) consolidated into a single multi-vessel trip with shared logic, or a manual reset feature extended to include automatic reset under specific conditions. Consolidation is simultaneously a retirement and an addition: the old references must be retired without leaving orphan justifications, the new references must be added with full justification, and the relationship between old and new must be explicit so reviewers can trace what changed and why. Blast radius for consolidation has three components: the retirement set (artifacts referencing the old features that need updating to point at the consolidated feature), the addition set (new artifacts required for the extended scope), and the continuity set (artifacts that must explicitly document the consolidation as a change rather than silently absorbing it). Figure 9 shows the structure.

**Figure 9.** Blast radius of a feature consolidation: retirement, addition, and continuity sets.

```mermaid
flowchart LR
    Change(["Proposed change:<br/>SF-PRES-001 +<br/>SF-PRES-002<br/>consolidated to<br/>SF-PRES-003"])

    subgraph Retire["Retirement set"]
        OldR1["SRS entry<br/>SF-PRES-001"]
        OldR2["SRS entry<br/>SF-PRES-002"]
        OldSAT1["SAT-201"]
        OldSAT2["SAT-202"]
        OldFMEA["FMEA 201/202<br/>old refs"]
    end

    subgraph Add["Addition set"]
        NewR["SRS entry<br/>SF-PRES-003"]
        NewSAT["SAT-203<br/>multi-vessel cases"]
        NewFMEA["FMEA 203<br/>new failure modes"]
        NewCode["PLC code<br/>shared trip logic"]
    end

    subgraph Continuity["Continuity set"]
        MOC["MOC record<br/>change rationale"]
        RTM["RTM update<br/>old→new mapping"]
        HA["HA review<br/>scope confirmation"]
    end

    Change --> Retire
    Change --> Add
    Change --> Continuity

    style Change fill:#FAEEDA,stroke:#854F0B,color:#412402
    style OldR1 fill:#EEEDFE,stroke:#534AB7,color:#26215C
    style OldR2 fill:#EEEDFE,stroke:#534AB7,color:#26215C
    style OldSAT1 fill:#FBEAF0,stroke:#993556,color:#4B1528
    style OldSAT2 fill:#FBEAF0,stroke:#993556,color:#4B1528
    style OldFMEA fill:#EEEDFE,stroke:#534AB7,color:#26215C
    style NewR fill:#EEEDFE,stroke:#534AB7,color:#26215C
    style NewSAT fill:#FBEAF0,stroke:#993556,color:#4B1528
    style NewFMEA fill:#EEEDFE,stroke:#534AB7,color:#26215C
    style NewCode fill:#E1F5EE,stroke:#0F6E56,color:#04342C
    style MOC fill:#FBEAF0,stroke:#993556,color:#4B1528
    style RTM fill:#EEEDFE,stroke:#534AB7,color:#26215C
    style HA fill:#EEEDFE,stroke:#534AB7,color:#26215C
```

The retirement set is found by traversal from the old feature nodes. Every artifact with an edge to SF-PRES-001 or SF-PRES-002 needs review. The addition set is found by running validation rules on the new feature node. Every required relationship that doesn't yet exist is a finding. The continuity set is the harder one structurally: it requires the schema to know that consolidation is a *named change type* with its own required artifacts (MOC (management of change) documentation, traceability mapping, hazard analysis review) rather than just a sequence of additions and deletions. The schema can model this with a `consolidation` node type linking the old and new feature nodes, with required edges to MOC, RTM (requirements traceability matrix), and HA artifacts; the consolidation node's validation rules then surface any consolidation that lacks its required continuity artifacts.

In all three change types, the value is the same: instead of an experienced engineer trying to reconstruct the cross-reference set from memory under schedule pressure, blast radius produces it as a query result. The change can be executed with confidence that the affected artifact set is complete.
