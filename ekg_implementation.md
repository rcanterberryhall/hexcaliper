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

### 1.3 Format-Agnostic Schema

The schema is invariant against the authoring format. Each upstream document type's parser is a pluggable text-in adapter; the graph layer is the durable middle. When the team migrates an authoring tool — for example, moving HA from Excel to Confluence, or swapping Sistema for an alternative ISO 13849 calculator — only the parser changes. The schema, validation rules, edges, queries, and outputs are unchanged. The PoC is built against the formats the team currently authors in (Excel for HA and FMEA, PDF for SRS narrative and drawings, Sistema SSM for the safety function calculations, atform Python for SATs), but no schema commitment depends on those choices.

## 2. Node Types

Five node types, one per source document type. Subtypes are properties on the node, not separate types. Validation rules branch on subtype.

### 2.1 HA Entry

Each row in the hazard analysis becomes an HA Entry node. A single hazard ID may have multiple rows when multiple measures are applied to the same hazard. Each row represents a distinct hazard-measure pairing with its own residual risk assessment.

**Key:** Hazard ID + Measure number (e.g., HE-01.2/1, HE-01.2/2)

**Source columns** (per the `3.7.5 HA` data sheet):
- ID (hazard identifier, e.g., HE-03.5)
- Hazard Category (e.g., Structural Integrity, Person slipping/falling)
- Type of hazard (e.g., Mechanical hazard)
- Potential consequence (e.g., impact, crush)
- Operating mode (e.g., Automatic, Manual)
- Use Case (e.g., Normal operation)
- Sub System (grouping, e.g., RV, Track - Pinch Rail, RV Unload/load station)
- Hazardous Situation
- Cause
- Hazardous Event
- Risk type — one of:
  - **H** — Harm to people
  - **E** — Equipment damage
  - **S** — Show impact
- Assessment (narrative risk description)
- Initial Severity, Probability, Risk Level (pre-measure risk)
- No. (measure number within this hazard)
- Measure (the mitigation description)
- Type of Measure — one of:
  - **D** — by Design
  - **FS** — Functional Safety
  - **W** — Warning notice
  - **OM** — Note in the operating or maintenance instructions
  - **PPE** — Personal protective equipment
  - **PROC** — Procedural / organizational protective measure
- Post-measure Severity, Probability, Risk Level (residual risk)
- Responsible / New Assessment
- Measure Implemented — cross-reference to the document or register entry that implements the measure. The reference target depends on Type of Measure:

  | Type of Measure | Measure Implemented references |
  |---|---|
  | D | design reference (drawing detail, calc, BOM line) |
  | FS | SRS Entry |
  | W | warning placard / signage register |
  | OM | O&M manual section |
  | PPE | PPE specification |
  | PROC | procedure document (LOTO, calibration, PM, operating) |

  May contain multiple entries delimited by comma; each becomes its own `mitigated_by` edge.

**Multi-reference handling:**

The Measure Implemented column can contain a list of references, potentially spanning multiple subsystems. For example, HE-03.6 references "RCS SRS 14.1 to 14.16, VCS SRS 2, VCS SRS 4.1 to 4.6." The parser splits this field and creates one `mitigated_by` edge per reference. The subsystem prefix (RCS, VCS) is part of the SRS Entry key to distinguish entries across subsystems. A single measure (one mitigation description) may fan out to many references — this is one mitigation implemented through many entries, not many mitigations.

**Validation scope:**

EKG validates HA Entries whose Type of Measure is **FS** (Functional Safety). FS measures have the multi-document obligation chain — HA → SRS Entry → subsystem chain → SAT — that the graph is designed to traverse. The other measure types (D, W, OM, PPE, PROC) are ingested for completeness so the HA Entry exists in the graph and its properties are queryable, but their validation is the domain of mechanical engineering, document control, and organizational processes, not EKG.

**Validation rules (FS-type entries only):**

- The HA Entry must have at least one `mitigated_by` edge to an SRS Entry. (ISO 13849-1:2015 §4 risk reduction allocation.)
- Every referenced SRS Entry must resolve to a valid SRS Entry node.
- The SRS Entry inherits validation: implemented by devices on the subsystem chain, verified by SATs. If any referenced SRS Entry fails its own validation, the HA Entry inherits that finding.
- Post-measure risk level must be lower than initial risk level. (ISO 12100 risk reduction principle.)

For non-FS entries, the HA Entry is recorded in the graph but no further EKG-side validation is performed.

### 2.2 SRS Entry

Each safety function specification becomes an SRS Entry node. The content — narrative engineering rationale plus the ISO 13849 architecture and PFHD calculation — is authored outside EKG, in whatever tooling the engineer prefers (Sistema directly, Confluence, Word, or hand-authored). EKG ingests the resulting artifact(s) and parses both *requirement* properties (PLr, S/F/P inputs, hazardous situation refs, reaction time required) and *implementation* properties (subsystem chain, achieved PL, achieved PFHD, MTTFD per channel) onto the SRS Entry node. Whether the two halves are authored as one combined document or as separate cross-referenced artifacts is the engineer's choice; EKG ingests them, it does not perform a parser-level merge.

**Key:** System prefix + SRS number (e.g., VCS SRS 1.1, RCS SRS 3.1). The system prefix (VCS, RCS) distinguishes SRS Entries across subsystems within the same project.

**Source fields — narrative structure (22-section template per entry):**

The narrative SRS document follows a 22-section, 4-level deep template per entry (50+ entries in a typical project SRS). Each section maps to one or more properties on the SRS Entry node:

| Section | Properties |
|---|---|
| 1 — ISO header | created_date, author, project_name, applicable_documents, status |
| 2 — Versions | version_history (date, author, change, who/why, comment) |
| 3 — Hazardous Situation | hazard_situation_refs (the SRS-side of the HA→SRS join: lists hazard IDs the SRS mitigates) |
| 4 — Triggering Event | triggering_event |
| 5 — Reaction | reaction_definition, stop_category (e.g., Cat 1 per IEC 60204-1), reaction_time_required |
| 6 — Performance Level Required | risk_severity (S1/S2), risk_frequency (F1/F2), risk_possibility (P1/P2), plr — ISO 13849-1:2015 Annex A risk graph |
| 7 — Safe State | safe_state_description |
| 8 — Frequency of the Request | frequency_of_request |
| 9 — Interfaces to other SRS Entries | interfaces_with_srs (list of SRS Entry refs — produces SRS↔SRS edges) |
| 10 — Interfaces to other machine functions | interfaces_with_machine_functions |
| 11 — Interfaces to ancillary systems | interfaces_with_ancillary |
| 12 — Interfaces to the Operator | operator_interface (HMI element, push button, key switch, etc.) |
| 13 — Necessary Start Interlocks | start_interlocks (table of conditions with required state) |
| 14 — Behavior in the event of an error | error_behavior |
| 15 — Operating Environment | operating_environment |
| 16 — Operating modes with active/deactivated SF | active_in_modes (list of project mode strings — e.g., Off, Maintenance, Automatic, Recovery) |
| 17 — Life cycle | lifecycle_scope |
| 18 — Reason for the FS solution | fs_rationale (why functional safety, not mechanical or procedural) |
| 19 — Implementation | required_category (ISO 13849-1 Cat 1–4, §6.2), required_dcavg (§4.5.3), required_mttfd (§4.5.2) |
| 20 — Hardware Selection | hw_sensors, hw_logic, hw_actuators (candidate device classes per subsystem position) |
| 21 — Verification | pl_achieved, reaction_time_achieved (with stage breakdown: Sensors, Input, Comm, Logic, Output, Actuators, Reaction Time Motion); reaction_time_for_multiple_faults |
| 22 — Validation References | validation_refs (links to validation matrices, FAT/SAT documents) |

**Source fields — Sistema computational structure:**

The Sistema project export carries the ISO 13849 architecture computationally. Fields complement the narrative properties above:

*Analysis table (ISO 13849-1:2015 Annex A risk graph):*
- Severity (S1/S2)
- Frequency (F1/F2)
- Possibility (P1/P2)
- Required Performance Level (PLr)
- PFHD range corresponding to PLr (per Table 3)
- Reaction Time Requirement
- Mode (All, Automatic, Manual, etc.)

*Subsystem chain (ISO 13849-1:2015 §4.5):* a table listing each subsystem with subsystem ID, description, and individual PFHD contribution. Subsystem IDs follow a typed prefix convention:

- **SS-I** (Input subsystems): field devices and sensors (e.g., SS-I05 Stop Pushbutton, SS-I15 Vehicle Positioning System)
- **SS-L** (Logic subsystems): safety processors and I/O modules (e.g., SS-L11 VCS TwinSAFE CPU, SS-L12 VCS Siemens F-CPU)
- **SS-O** (Output subsystems): safe state actuators (e.g., SS-O09 Propulsion System Safe State, SS-O10 Yaw System Safe State)
- **SS-X** (External subsystems): interfaces to other systems (e.g., SS-X01 Ride Vehicle Safe Linear Position)

Each subsystem ID resolves to a subsystem documented elsewhere in the SRS, which references specific hardware by manufacturer + part number (e.g., Beckhoff EL6910, Siemens 6ES7517-3FP00-0AB0). Those part numbers connect to Device nodes from the drawings.

*Safety function result (ISO 13849-1:2015 §4.5.4):*
- Reaction Time achieved (e.g., 2310 ms)
- PL Achieved (e.g., PLe)
- Total PFHD (sum of subsystem chain contributions, e.g., 3.2 × 10⁻⁸)

*Software design:* narrative description of signal flow through the safety function.

**Edges discovered from SRS:**

- Each subsystem ID in the subsystem chain produces an `implemented_by` edge from the SRS Entry to a Device node, with the subsystem position (e.g., SS-I05) and PFHD value as edge properties.
- Section 9 interface references produce `interfaces_with` edges to other SRS Entries.
- Section 3 Hazardous Situation references identify the HA Entries that mitigate to this SRS Entry — the same `mitigated_by` edges that the HA's Measure Implemented column produces, but expressed from the SRS side. The two should match; mismatches are cross-document consistency findings.

**Validation rules:**

- Must have at least one incoming `mitigated_by` edge from an HA Entry. (ISO 13849-1:2015 §4 risk reduction allocation.)
- Must have a complete subsystem chain — at least one SS-I subsystem, one SS-L subsystem, and one SS-O subsystem, each resolving to a valid Device node. (ISO 13849-1:2015 §4.5.1 architecture.)
- Every device referenced in the subsystem chain must resolve to a valid Device node.
- PL Achieved must meet or exceed PLr. (ISO 13849-1:2015 §4.5.4.)
- Total PFHD must fall within the required range for the PL. (ISO 13849-1:2015 Table 3.)
- Must have at least one `verified_by` edge to a SAT. (ISO 13849-1:2015 §8 validation; ISO 13849-2:2012.)
- The Hazardous Situation cross-reference (section 3) must be consistent with the HA's Measure Implemented column — every HA Entry referencing this SRS Entry should appear in the Hazardous Situation list, and vice versa.

### 2.3 FMEA Entry (Controls FMEA)

Each row in the Controls FMEA master sheet becomes an FMEA Entry node. One device with multiple failure modes produces multiple FMEA Entry rows for the same device.

**Key:** FMEA entry number (e.g., ETS.DRVS.1.1). The hierarchical format `<System>.<SubSystem>.<Group>.<Row>` groups failure modes by device and subsystem.

**Subtypes:**

- **Safety FMEA Entry** — when (a) the referenced Device is on a subsystem chain (SS-I/L/O/X) of any SRS Entry (derived via `implemented_by`), OR (b) the engineer has set `safety_relevant: true` on the entry. SEV ≥ 8 is flagged for engineer review as a candidate for `safety_relevant` designation but does not trigger safety subtype on its own.
- **Standard FMEA Entry** — neither path. Carries failure-mode and reaction properties; not subject to ISO 13849-2 testing obligations.

**Source columns** (per the `Controls FMEA` master sheet):

- Deleted (soft-delete flag)
- System (top-level subsystem code: ETS, RCS, VCS, etc.)
- ID
- Tests (SAT references; produces `tested_by` edges)
- Test Notes
- Item (device tag, resolves to Device node)
- First Item (canonical instance when one row applies to a class of identical devices)
- Part Manufacturer, Part Number, Part Description (properties of the referenced Device, source of truth in the drawing package)
- Function
- Failure Mode
- Potential Cause
- Failure Consequences
- Detection (free-form prose)
- System Reaction (e.g., "Cat 1 stop of motion," "trip to safe state," "diagnostic alarm")
- OCC, SEV, DET (integers 1–10 per the project's Evaluation Scheme)
- RPN (OCC × SEV × DET)
- GTG (engineer sign-off on the analysis row)
- Notes

Workbook-specific columns (`FailureModeGUID`, `Device Count`) are read for parser hints but not stored as schema properties.

**Schema-only properties** (set on the FMEA Entry node, not parsed from the workbook):

- `safety_relevant: bool` — engineer flag. Default false. Triggers safety subtype regardless of subsystem-chain membership.
- `disposition: {value: "test" | "accept" | "defer", note: <text>}` — engineer's decision for standard-subtype entries with no `tested_by` coverage.

**Validation rules — all subtypes:**

- Must have at least one `references_device` edge to a Device node.
- System Reaction must be a non-empty property.
- Must have either a Detection property or an `addressed_by` edge to a preventative maintenance procedure. (IEC 61508-2 §7.4.5.)
- RPN must equal OCC × SEV × DET.
- OCC, SEV, DET must each be integers in [1, 10].

**Validation rules — safety subtype:**

- Must have at least one `tested_by` edge to a SAT (parsed from the Tests column). Absence is a finding. (ISO 13849-2:2012.)
- The addressed SAT must conform to the canonical fault test lifecycle for its (fault_class, reaction_class).
- Diagnostic coverage must be consistent with the parent SRS Entry's required DC. (ISO 13849-1:2015 §4.5.3.) The SRS Entry is reached via `references_device` → Device → `implemented_by`-inverse → SRS Entry; no direct edge is parsed.

**Coverage audit — standard subtype:**

Standard-subtype FMEA Entries without a `tested_by` edge are surfaced in the §7 coverage report with their SEV, RPN, system_reaction, and `disposition`. Open gaps (no `disposition`, no `tested_by`) are coverage gaps, not findings.

### 2.3b Mechanical FMEA Entry

Each row in the `Mechanical FMEA` sheet becomes a Mechanical FMEA Entry node. Sibling type to FMEA Entry with a different schema: hierarchical key, pre/post planned-action values, no device tag.

**Key:** Mechanical FMEA entry ID.

**Source columns** (per the `Mechanical FMEA` sheet):

- ID
- Sub System
- Assembly
- Sub Assembly
- Component
- Failure Cause
- O (Occurrence, 1–10)
- Failure
- D (Detection, 1–10)
- Failure Consequences
- S (Severity, 1–10)
- Comment
- RPN (O × S × D)
- Planned Action
- O', D', S' (post-action values)
- RPN' (post-action RPN)
- Requirements List ID

**Validation rules:**

- O, D, S, O', D', S' must each be integers in [1, 10].
- RPN must equal O × S × D; RPN' must equal O' × S' × D'.
- RPN' must be lower than RPN. (ISO 12100 risk reduction principle.)
- For S ≥ 8: Planned Action must be non-empty; RPN' must show meaningful reduction.

Mechanical FMEA Entries do not traverse into the safety-case chain in v1. The Requirements register they reference is not yet ingested.

### 2.4 Device

Each device in the drawing's enclosure legend becomes a Device node. The drawing tag convention varies by project; the schema is convention-agnostic. The parser declares which convention it read.

| Convention | Tag examples | Hierarchy |
|---|---|---|
| IEC 81346-2 | `+VSD-0104 -CB1`, `+VCS-0102 -PNL1 -RF2` | `+<location>` cabinet/assembly, `-<device>` within, intermediate containers as `-PNL1`, `-PNL2`. Common in EPLAN and European-market drawings. |
| ISA-5.1 / NFPA 79 | `LT-2105`, `FV-2101`, `PSH-3201`, `TT-1301` | Function-letter prefix (L=level, F=flow, P=pressure, T=temperature, H=high), trailing 4-digit number is the loop/point ID. Common in North American industrial drawings. |

**Key:** Device tag, in the convention used by the source drawing.

**Properties:**

- `tag` — the device tag in the source convention.
- `tag_convention` — `"IEC 81346"` | `"ISA 5.1"` | ... (set by the parser).
- `manufacturer` — abbreviation per the enclosure legend (SIE, ABB, MURR, etc.).
- `part_number` — e.g., `SIE.3LD9200-5C`.
- `type_number` — e.g., `3LD9200-5C` (without manufacturer prefix).
- `function_text` — e.g., "Motor Cooling Fan 1".
- `function_short` — short label derived from `function_text` for use in SAT prose (consumed as `reference_designator.component.function_short` by SAT templates).
- `terminal_designations` — list of terminals on this device.
- `signal_type` — for I/O devices: DI, DO, AI, AO, safety DI, safety DO, EtherCAT, etc.
- `parent_container` — the cabinet, panel, or assembly that contains this device.

**Sub-components:**

A single device tag in the legend can have multiple item rows when the device is a composition of parts (e.g., a disconnect with handle + main switch + lockable shaft + replacement modification, or a circuit breaker with base + auxiliary contact). The Device node aggregates them:

- `sub_components: [{item_number, type_number, part_number, manufacturer, function_text, notes}, ...]`

**Edges:**

- `shown_on` (Device → Drawing Sheet) — from drawing page references.
- `contained_in` (Device → Cabinet / Panel / Assembly) — from drawing hierarchy.
- `wired_to` (Device → Device) — from schematic wire tags. Edge keyed by wire tag; properties include source/destination terminal designations, signal name, voltage, and gauge.
- `cabled_to` (Device → Device) — from schematic cable tags. Edge keyed by cable tag; properties include conductor count, type, length, and voltage rating. Multiple wire-edges may share a cable via the `cable` property linking back to the cable tag.
- `mapped_to` (Tag → Device) — from PLC I/O addressing.

**Validation rules:**

- Must appear on a current drawing (at least one `shown_on` edge).
- Device tag must conform to its declared `tag_convention`.
- If the Device is on a subsystem chain of any SRS Entry (incoming `implemented_by` edge), it must have at least one incoming `exercises_device` edge from a SAT. (ISO 13849-2:2012.)

### 2.5 SAT

Each site acceptance test becomes a SAT node. atform is the canonical SAT format and the only render target; hand-written SATs in other formats (legacy Word `.docx`, rendered PDFs from prior projects or other tooling) are ingested for completeness but are expected either to conform to atform's hierarchical numbering and slot in alongside atform-authored tests, or to be converted to atform Python. The SAT parser handles atform Python (`rsd.py`, `mcc.py`, `station_*.py`), Word `.docx`, and text-bearing PDF.

**Key:** `numbering_position` — an N-tuple of integers conforming to the project's numbering schema (§2.6). The SAT's atform-rendered ID (`1.1.74.2`, `18.2.146`, etc.) is the dotted form of this tuple. Every SAT carries a stable `numbering_position`; the rendered dotted ID is a presentation projection of it.

**Numbering position semantics.** The top N-1 components of the tuple are *declared*: each binds to a project-level table or a graph property defined by the numbering schema (e.g., level 1 = chapter, looked up from a chapter table; level 3 = device, looked up via a per-chapter cabinet-block allocation). The bottom component is *position-with-reserved-slots*: each device-class (or other deepest-level container) carries a slot declaration listing the canonical test variants in order, and atform's auto-numbering assigns the bottom component as the test's position within that slot sequence. A reserved slot whose SAT has not been authored is held in place by `atform.skip_test()`, which increments atform's test counter without rendering anything — so reserved slots cost a counter increment, not a TOC entry, and a SAT that was previously reserved slots into the same number when later authored.

This separation — top N-1 declared, bottom position-with-reservations — is what gives EKG the property the project actually needs: stable IDs across re-emission, late additions in the right place, no manual collision-checking, no renumbering when a previously-reserved slot is filled.

Although the design is anchored to atform here, the underlying numbering machinery — declared upper levels, slot reservation at the bottom level, position-driven auto-numbering — is a general pattern. Any well-developed SAT writing program with hierarchical IDs and slot-holding semantics could serve as the render target by writing a new emitter against the same numbering schema (§2.6). The schema is renderer-agnostic; atform is this project's chosen consumer.

**Procedure shape taxonomy:** SATs come in a known variety of procedure shapes. The shape is identified by a `(fault_class, reaction_class[, device_class])` tuple — EKG-side metadata that informs which factory function emits the procedure list when EKG generates the SAT input. Manually-authored SATs and SATs using project-specific custom patterns may not match any predefined tuple.

| Axis | Description |
|---|---|
| `fault_class` | Whether the fault persists after injection or self-clears. The procedure lifecycle differs accordingly. |
| `reaction_class` | What the system does in response — safe state, warning, no reaction, etc. |
| `device_class` (optional) | A device-specific refinement of the procedure when the fault-injection method depends on the device type (e.g., process-meter wiring for an analog input, dual-channel verification for safety-rated push buttons). |

Specific values within each axis are project-defined; each project maintains its own set of factory functions or hand-authored shapes that correspond to entries in the tuple. EKG records the tuple on the SAT node so it knows which factory to invoke when emitting the procedure list.

**SAT data model:**

| Field | Description |
|---|---|
| `numbering_position` | N-tuple of integers; the SAT's identity in the project numbering schema (§2.6). Primary key. |
| `test_id` | Dotted-form rendering of `numbering_position` (e.g., `1.1.74.2`). Presentation projection, not an independent field — derived at render time. |
| `title` | |
| `skipped` + `comment` | Skip flag with reason |
| `purpose` | Generated from canonical pattern |
| `procedure_pattern` | EKG-side identifier for the procedure shape — a `(fault_class, reaction_class[, device_class])` tuple value, or `manual` if the SAT was hand-authored without a recognized pattern |
| `srs_references[]` → `{name}` | SRS Entry refs |
| `fmea_references[]` → `{id}` | FMEA Entry refs |
| `area` | Physical area |
| `rcs_mode`, `ssc_mode` | Operating mode at system and sub-system levels |
| `control_system`, `additional_control_systems[]` | |
| `failure_mode` → `{potential_failure_mode, potential_causes}` | Joined from FMEA Entry |
| `reference_designator` → `{id, component: {function_short}}` | Joined from Device |
| `induced_fault`, `induced_fault_detailed_instruction` | Physical action description |
| `system_reaction_tags[]` → `{tag, test_cases: {faultless: {description, value}, faulted: {description, value}}}` | PLC tags whose values change between faultless and faulted |
| `monitored_tags[]` | Same shape; verify-but-don't-expect-change |
| `preconditions[]` | Preconditions to verify before fault induction |
| `hmi_message` | Alarm text shown on HMI |
| `comment` | Trailing notes |
| `test_note_tag_reference_tests[]` → `(plc_tag, referenced_test)` | Cross-SAT dependency arcs |

The SAT data model is a join view across FMEA Entry, Device, SRS Entry, PLC Tag, and Mode nodes. SAT-authored fields are: `title`, `induced_fault`, `induced_fault_detailed_instruction`, `preconditions`, `hmi_message`, `comment`, `area`, `rcs_mode`, `ssc_mode`, and the `test_cases.faultless` / `test_cases.faulted` values per tag. The `numbering_position` is composed by the project numbering schema (§2.6) — never freely chosen by the SAT author. Other fields are pulled from upstream nodes at render time.

**Edges:**

- `addresses` (SAT → FMEA Entry) — one per `fmea_references` entry.
- `references_srs` (SAT → SRS Entry) — one per `srs_references` entry.
- `exercises_device` (SAT → Device) — derived from `reference_designator.id`.
- `exercises_tag` (SAT → Tag) — one per `system_reaction_tags` or `monitored_tags` entry.
- `depends_on_test` (SAT → SAT) — one per `test_note_tag_reference_tests` entry.

**Validation rules:**

- Must reference at least one justification-layer node (FMEA Entry, SRS Entry, or functional requirement). (ISO 13849-1:2015 §8; ISO 13849-2:2012.)
- If the SAT addresses a safety-subtype FMEA Entry, it must conform to the canonical fault test lifecycle template for its (fault_class, reaction_class). (ISO 13849-2:2012.)
- The `reference_designator` must resolve to a valid Device node.
- Every PLC tag in `system_reaction_tags` and `monitored_tags` must resolve to a valid Tag node.
- The `induced_fault` must be non-empty for FMEA-driven SATs.
- The `hmi_message` must match the corresponding alarm config entry.

**EKG generation states (EKG → atform input):**

When EKG processes a SAT-shaped node, it emits one entry per slot in the device's slot declaration (§2.6) in canonical order. Each slot resolves to one of:

1. SAT data exists with a recognized `procedure_pattern` → EKG calls the corresponding factory function to emit the procedure list, wrapped in an `atform.add_test(...)` call.
2. SAT data exists, no recognized pattern → EKG emits `atform.add_test(procedure=[...])` with a generic step list assembled from the data model.
3. Slot is reserved by the schema but no SAT is authored yet → EKG emits `atform.skip_test()`. The slot's position in the counter is held without rendering anything; when the SAT is later authored, the `skip_test()` is replaced by `add_test(...)` and the test ID stays the same.
4. SAT is manually authored → EKG ingests the existing `atform.add_test()` call from the project's `.py` files via the AST parser. EKG does not re-emit it.

The walk-the-slot-declaration pattern is what makes `numbering_position` stable across re-emission: every authored or reserved slot has a fixed position in the section, every emission produces the same atform counter sequence, and atform assigns the same IDs every time.

**EKG ↔ atform integration:**

EKG's own source never imports atform — EKG runs without atform installed. The boundary is text-based in both directions:

- **Emission (EKG → atform):** EKG generates `.py` files containing `atform.add_test()` calls as text. atform reads/runs those files as part of its normal operation. Hand-authored modules coexist with EKG-generated modules in the same project.
- **Ingestion (atform-authored SAT → EKG):** EKG's SAT parser walks the Python AST of existing atform `.py` files (e.g., `rsd.py`, `mcc.py`) and extracts `atform.add_test(...)` calls into the SAT data model. The parser reads source as text; it does not import or execute atform.

The SAT parser handles three input formats: atform Python (AST walk), Word `.docx` (python-docx), and PDF (text-based extraction with layout-aware structure recovery — covers atform-rendered output, Word-exported SATs, and any text-bearing PDF; scanned image-only PDFs are out of scope without OCR). Parser and emitter are independent — adding a new authoring format adds a parser, and porting to a different SAT renderer adds an emitter; neither changes the schema.

Project-level configuration in `main.py` stays hand-managed.

### 2.6 Project Numbering Schema

EKG does not prescribe a numbering scheme. Any scheme a project chooses is valid, provided two conditions hold:

1. **The scheme is documented** — declared in the project's numbering schema, a config artifact version-controlled alongside the source documents. The schema is the canonical record of what each component of `numbering_position` represents and how it is composed from graph state.
2. **The deepest level conforms to atform's rules** — because atform is the render target. atform fixes a small number of constraints at the deepest level (everything above the deepest level is fully project-flexible):

   - `atform.set_id_depth(N)` declares the maximum depth.
   - `atform.section(level, id=N, title=...)` opens a section at any non-deepest level with an explicitly assigned ID. EKG always emits explicit IDs at non-deepest levels — implicit auto-incrementing of sections is fragile under reordering.
   - `atform.add_test(...)` adds a test at the deepest level, auto-incremented within the current section. atform owns the deepest-level component; EKG cannot assign it directly.
   - `atform.skip_test()` increments the deepest-level counter without rendering. This is how slots are reserved for late additions without disturbing surrounding numbering, and it is the only mechanism for stable deepest-level IDs across re-emission. Reserved slots cost a counter increment, not a TOC entry.

These are the rules every project's scheme has to live within. Anything else — what level 1 represents, whether level 3 is a device or a category ordinal, whether the schema uses 2 levels or 4, where blocks of reserved IDs sit, what 900-series prefixes mean — is the project's call.

**Schema declaration.** A project's schema declares:

- `levels: N` — matches `atform.set_id_depth(N)`.
- For each level, a **source binding** describing how that level's component is composed from graph state and project tables.
- Bindings can be **global** (the same source applies to every value of the parent levels) or **per-pair** (the source for level 3 differs depending on the level-1 and level-2 values). Per-pair bindings are how hybrid schemes work — different categories within the same chapter can use level 3 and level 4 differently.

**Source types** are a toolbox EKG provides; the project picks per level (or per pair) which to use:

- **`project_table`** — look up the component in a project-level table keyed by SAT or connected-node attributes (system → chapter, safety function → category, etc.).
- **`graph_property`** — read the component directly from a property on the SAT or a connected node when integer-keyed designations already exist in the graph.
- **`block_allocation`** — allocate IDs in contiguous blocks per a project-defined key (cabinet, subsystem, area). Block size sets per-key capacity; gaps between blocks reserve growth room.
- **`ordinal`** — auto-incremented within parent context, with optional starting offset (used by 905's `(1, 11, *)` which starts level-3 at 31).
- **`slot_declaration`** — see below. The standard binding for the deepest level when device-class-specific test variants apply.

**Slot declaration (deepest level).** When the deepest level binds via `slot_declaration`, the project declares an ordered list of test variants per slot-class (typically a device-class, though other slot-classes are valid). Each entry carries a marker:

| Marker | Meaning |
|---|---|
| `REQUIRED` | Every member of this slot-class must have this test authored. Missing SAT is a coverage finding. |
| `OPTIONAL` | Test exists for some members, not others. No finding if absent. |
| `CONDITIONAL` | Applies only when a stated condition holds (e.g., "device is on a SIF spine"). Finding only if condition holds and SAT is absent. |
| `RESERVED` | Tail slots produced by the reservation rule. No expected SAT. |

EKG walks the slot declaration in canonical order at emission time. Each slot becomes either `atform.add_test(...)` (authored) or `atform.skip_test()` (not authored). The deepest-level component falls out of the walk position — atform assigns it.

**Reservation: round-up-to-power-of-10.** A slot-class with N declared variants has its reservation set to the smallest power of 10 ≥ N. Classes with 1–9 variants get 10 total slots; classes with 10–99 get 100; etc. Tail slots are emitted as `skip_test()` — counter position held, no TOC entry. When N escalates to 100, the tens-digit gains free organizational meaning (variants 1–9 = electrical fault types, 10–19 = mechanical, 20–29 = communication, etc.).

**Composition.**

- *On ingest:* an existing SAT carries an explicit numbering position (from its atform section/test sequence, its `.docx` title, or its PDF page header). The schema validates the position by reading each level's source against the SAT's graph state and confirming the result matches the SAT's declared component. Mismatches are §4 schema-conformance findings — and apply equally to atform-authored, hand-written, and PDF-only SATs. Hand-written tests do not get an exemption from the schema.
- *On new SAT:* EKG composes the position from graph state plus the schema. For a missing SAT identified by the FMEA chain, every component is determinable before the SAT is authored. Engineers see the assigned ID up front (§7.x Required Tests projection).

**Renderer-agnosticism.** The schema describes IDs and slot semantics; it does not bind to atform's API. atform is this project's chosen render target, and atform's deepest-level rules are the constraints the schema design respects. Another SAT writing program with hierarchical IDs and slot-holding semantics could serve as a target by writing a new emitter against the same schema, with no schema changes — provided the new program supports the same deepest-level constraints (positional auto-numbering + slot reservation).

**Worked example: 905 project.** The 905 project uses a hybrid 4-level scheme. Levels 1 and 2 are global `project_table` bindings — chapter from system + test campaign, category from safety function or named category. Levels 3 and 4 vary per (chapter, category) pair:

- **`(1, 1, *, *)` device-component tests** — level 3 uses `block_allocation` per cabinet (50-slot blocks: `+RCS-0100` at 1, `+OCC-0110` at 50, `+RSD-0111` at 74). Level 4 uses `slot_declaration` per device-class (DSC class has variant `.1` = stuck-at-low; CR class has variant `.3` = stuck-at-low with variants 1 and 2 reserved or non-applicable). The all-`.3` pattern in 1.1.18–37 reflects this — CR-class slot declarations leave variants 1 and 2 as RESERVED/CONDITIONAL and only variant 3 is authored.

- **`(1, 2..17, *)` functional-category tests** — level 3 uses `ordinal` with category-defined offsets (e.g., `(1, 11, *)` starts at 31). Level 4 is unused (depth-3).

- **`(12, 901..)` and `(18, 902..)` 900-series blocks** — level 2 reserves a 900-series range for late-added categories (CV monitoring, LiDAR, RV upgrade jumpers, ICD mapping, pull tests). The level-3+ bindings within each 900-series category vary; some return to the device-component pattern (`(12, 901, *, *)`), some use ordinal with their own offsets.

Bring-up against the existing master list validates the schema by reproducing every existing dotted ID; gaps and mismatches are bring-up findings (orphan IDs in the master list, missing SATs in the FMEA chain, ingested SATs that don't compose against any declared binding).

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
| `references_srs` | SAT | SRS Entry | SAT SRS reference column (FMEA→SRS is derived via FMEA→Device→SRS, not parsed) |
| `shown_on` | Device | Drawing Sheet | Drawing enclosure legend |
| `contained_in` | Device | Cabinet/Panel/Assembly | IEC 81346 hierarchy (+VCS-0102 > -PNL1 > -CB4) |
| `wired_to` | Device | Device | Schematic wire tags between device terminals |
| `cabled_to` | Device | Device | Schematic cable tags between devices (often spanning cabinets) |
| `reads_tag` | Routine/FB/POU | Tag (shared entity) | PLC project tag cross-references |
| `writes_tag` | Routine/FB/POU | Tag (shared entity) | PLC project tag cross-references |
| `calls` | Routine/FB/POU | Routine/FB/POU | PLC project call hierarchy |
| `mapped_to` | Tag (shared entity) | Device | PLC project I/O address to drawing terminal |

### 3.2 Edge Discovery

The ingestion parser reads each document, creates nodes from keyed rows, and creates edges from every cross-reference found in that row. Tag vocabulary is the resolution mechanism: "LT-2105" in the FMEA matches "LT-2105" on the drawing matches "LT-2105" in the SRS. Same string, same device node, edges from multiple documents converging on one shared entity.

Edges that should exist but are not found in the source documents are the gaps that node validation catches. An FMEA row with no equipment tag, an HA row with no mitigation reference: the absence of a cross-reference means the absence of an edge, and the validation rule that requires that edge reports the finding.

## 4. Validation Categories

Validation rules produce findings. A finding identifies a node, an edge, or a relationship that doesn't match what the node-type schema or a cross-document rule expects. Every finding — per-node, neighborhood, or cross-document — is an engineer-review item at this stage. The system records the finding, the engineer dispositions it, and the disposition is recorded. The system does not auto-accept or auto-reject. As patterns emerge in how findings get dispositioned, EKG will learn which classes can be resolved automatically; until then, the engineer is the arbiter.

**Standards framework.** EKG validation rules are grounded in:

- **ISO 13849-1:2015** and **ISO 13849-2:2012** — primary anchor; safety-related parts of control systems for machinery (PLr / PL achieved / PFHD / category, subsystem chain, fault test lifecycle).
- **IEC 61508** — foundational functional-safety standard for E/E/PE safety-related systems; ISO 13849 is aligned with it.
- **IEC 61511** — sector-specific functional-safety standard (process industry safety instrumented systems); applies to control aspects with continuous-mode safety functions.
- **ISO 12100:2010** — parent risk-assessment standard for machinery (risk-reduction hierarchy, post-measure residual risk). Applicable as the document from which ISO 13849's risk-reduction allocation derives.

Where a rule is mandated by one of these standards, the rule cites the clause. Rules without a citation are project conventions internal to EKG.

### 4.1 Per-Node Validation

Per-node validation checks whether a single node satisfies its own type's rules against its current edges and properties. The check is deterministic: the node either has the required edges or it doesn't, the referenced device either exists on a current drawing or it doesn't, the SAT either follows the fault test lifecycle template or it doesn't.

Per-node findings name the node, the rule that didn't hold, and the related nodes. A missing edge points to a missing artifact that needs to be authored; a stale reference points to a document that needs to be updated; a format violation points to a procedure that needs to be revised.

Examples: HA Entry with no mitigation. FMEA Entry with no system reaction. Device with no FMEA Entry. SAT referencing a device that doesn't exist on a current drawing. FMEA Entry referencing three devices but only two have covering SATs.

#### 4.1.1 Schema Conformance

Every node must conform to its type's schema (§2). The schema declares which properties are required, which are optional, and which shapes or enumerations they must satisfy. Schema-conformance findings identify nodes missing required properties, properties of the wrong shape, or properties whose values fall outside the schema's enumeration. Schemas are declared in YAML. Schema conformance is project-internal — the schema is EKG's own representation contract, not an obligation imposed by an external standard.

#### 4.1.2 Type-Dispatched Rule Packs

Some node types subtype on a property, and the rule pack to apply varies by subtype. A type-dispatched node first satisfies the schema-conformance check (which selects the subtype), then the dispatch table picks the rule pack to run.

**HA Entry — dispatched on Type of Measure.** §2.1 documents the six values (D, FS, W, OM, PPE, PROC). The values map to the ISO 12100:2010 risk-reduction hierarchy:

- **D (by Design)** — inherently safe design (ISO 12100:2010 §6.2). Rule pack: schema conformance; `Measure Implemented` resolves to a valid design artifact (drawing detail, calculation, BOM line).
- **FS (Functional Safety)** — safeguards via safety-related control system (ISO 12100:2010 §6.3; ISO 13849-1:2015 §4 risk reduction allocation). Full chain rule pack: at least one `mitigated_by` edge to a valid SRS Entry, transitive validation through the SRS chain (devices on the subsystem chain, SATs verifying the SRS), post-measure risk level lower than initial (ISO 12100 risk-reduction principle), and reciprocity with the SRS's Hazardous Situation listing (§4.3).
- **W (Warning notice)** — information for use (ISO 12100:2010 §6.4). Rule pack: schema conformance; reference resolves to a valid signage / placard register entry.
- **OM (Note in O&M)** — information for use (ISO 12100:2010 §6.4). Rule pack: schema conformance; reference resolves to a valid O&M manual section.
- **PPE** — information for use, PPE category (ISO 12100:2010 §6.4). Rule pack: schema conformance; reference resolves to a valid PPE specification.
- **PROC (Procedural / organizational)** — complementary protective measure (ISO 12100:2010 §6.4). Rule pack: schema conformance; reference resolves to a valid procedure document (LOTO, calibration, PM, operating).

Only FS entries get the full obligation-chain check. Non-FS rule packs verify schema conformance and reference existence; substantive validation of the design artifact, signage, manual, PPE specification, or procedure is outside EKG's scope and remains the domain of the disciplines that own those artifact types (mechanical engineering, document control, organizational processes).

**FMEA Entry — dispatched on safety classification.** §2.3 defines two paths for classification as a Safety FMEA Entry:

- **Structural** — the referenced Device is on the subsystem chain (SS-I/L/O/X) of any SRS Entry, derived from the Device's incoming `implemented_by` edges. Automatic at ingest. Grounded in ISO 13849-1:2015 §4.5 (subsystem architecture): every device on the SRS subsystem chain participates in the safety function, and its failure modes carry ISO 13849-2:2012 testing obligations.
- **Explicit** — the engineer has set `safety_relevant: true` on the entry. Project convention. Covers cases the structural path misses — devices that contribute to a safety function via a non-Sistema-modeled path, or devices whose safety relevance the engineer wants to assert irrespective of the structural derivation.

Either path classifies the entry as Safety FMEA, subject to the safety rule pack (system reaction defined, SAT coverage required, fault test lifecycle conformance per ISO 13849-2:2012). Neither path classifies the entry as Standard FMEA, subject to a lighter rule pack: failure-mode and reaction properties only, no testing obligations.

SEV ≥ 8 is not a third path. It produces a finding for engineer review when the entry is not classified safety: "FMEA Entry has SEV ≥ 8 but is not classified safety; engineer should confirm or set `safety_relevant: true`." The finding flags potential under-classification; the engineer either reclassifies or accepts the standard subtype with rationale recorded. Project convention — IEC 60812 (FMEA methodology) does not prescribe a safety-classification threshold.

### 4.2 Neighborhood Validation

Neighborhood validation surfaces patterns that emerge from the relationships between nodes that share edges. The pattern itself is computable, but the disposition requires engineering judgment.

The primary case is overlap detection on induced fault actions. SATs are procedurally generated through atform, and the induced fault is a structured property in the data model, not free text. Two SATs that share the same device tag and the same induced fault property are an exact match. The detection is a straightforward property comparison: group SAT nodes by device tag and induced fault, and any group with more than one SAT is a convergence that gets flagged for engineer review.

This overlap detection moves upstream from post-authoring review to pre-generation. When EKG assembles the data models for a batch of SATs from FMEA Entries, it can detect that two FMEA Entries on the same device would produce SATs with the same induced fault before handing anything to atform. The engineer resolves it at that point: consolidate into one SAT that covers both failure modes, or differentiate the induced fault to make the tests genuinely distinct. Only after the engineer resolves the overlap do the SATs get generated.

Neighborhood findings are review items, not action items. The system presents the convergence pattern, the nodes involved, and the shared properties. The engineer reviews, confirms or resolves, and the disposition is recorded.

### 4.3 Cross-Document Reciprocity

When two artifacts reference each other from opposite directions, the references must agree. Mismatches surface as findings naming both sides and the inconsistent reference.

**HA↔SRS reciprocity.** Each FS-type HA Entry's `mitigated_by` edge (set from the HA's `Measure Implemented` column) names an SRS Entry. The SRS Entry's section 3 Hazardous Situation listing names the HA Entries the SRS mitigates. The two views must agree:

- Every `mitigated_by` edge from HA to SRS should appear as a hazard-situation reference on the SRS.
- Every hazard-situation reference on the SRS should be reciprocated by a `mitigated_by` edge from the named HA.

Either-side-only references produce findings. The engineer resolves by adding the missing reference on whichever side, or by removing the reference on the side that had it incorrectly. ISO 13849-1:2015 §4 requires risk-reduction allocation to be traceable from hazard to safety function; the reciprocity check is the project-convention mechanism that makes that traceability mechanically verifiable across the two source artifacts (HA worksheet and SRS document).

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
- **SRS parser.** Reads safety function entries from a Word document, Confluence-exported HTML, or Sistema export. Each SRS entry is identified by its heading (e.g., "VCS SRS 1.1: Prevention of propulsion and yaw movement in case of VStop"). The parser extracts the safety function statement, the ISO 13849-1 analysis table, the subsystem chain with PFHD values, and the safety function result (PL achieved, reaction time, total PFHD). Creates SRS Entry nodes keyed by system prefix + SRS number. Subsystem IDs (SS-I05, SS-L11, SS-O09) in the chain are resolved to Device nodes through the part numbers and device tags documented in the subsystem sections. Creates `implemented_by` edges from the SRS node directly to each Device node, with the PFHD value as a property on the edge.
- **Confluence parser.** Engineers using Confluence as their authoring tool work in their existing wiki; the sync job (§6.1) writes synced page content into the git repo, and the Confluence parser turns the synced content (HTML or storage-format export) into Entry nodes. The parser recognizes Confluence page structure (page title, heading hierarchy, tables, page-properties macros) and dispatches to the appropriate node-type handler — SRS Entry, HA Entry, or other — based on page metadata or path. Placeholder; the full specification depends on the team's Confluence content shape and is deferred until that shape is finalized.
- **FMEA parser.** Reads keyed table rows from the master Controls FMEA sheet (34 columns including Tests, Test Notes, Detection, System Reaction). Creates FMEA Entry nodes with `system_reaction`, `failure_consequences`, and `detection` as properties. Creates `references_device` edges from the Item / equipment-tag column and `tested_by` edges from the Tests column. Does not parse `references_srs` — the FMEA→SRS path is derived via the two-hop traversal FMEA→Device→SRS.
- **Mechanical FMEA parser.** Reads the separate `Mechanical FMEA` sheet (20 columns, hierarchical key System / Sub System / Assembly / Sub Assembly / Component, pre/post planned-action OCC/DET/SEV/RPN). Creates Mechanical FMEA Entry nodes (sibling node type to FMEA Entry, different schema, no device-tag join — failures live at the assembly level where there is no `+...-device` reference designator).
- **Drawing parser (PDF).** Drawing packages encode the graph structure directly: every device, wire, and cable in the project carries a unique tag. Devices become nodes; wires and cables become edges between the devices they connect. The parser extracts device tags as Device node keys and wire/cable tags as edge identifiers on the corresponding connections. Format conventions (IEC 81346 `+VCS-0102 -CB4`, NFPA `31MCB1`, ISA 5.1 `LT-2105`, or any project-internal scheme) determine how the parser *recognizes* tags but not how the graph *stores* them — uniqueness within a project is sufficient regardless of convention. Both EPLAN and AutoCAD Electrical produce structured-text PDF exports; text is extracted directly without OCR.

  *Device extraction from BOM and legend tables (required).* Each row of the BOM or a per-panel legend table becomes a Device node keyed by its device tag, with part number, manufacturer, and description as properties. Column layouts vary by CAD tool and project; the parser uses a column-mapping rule per layout.

  *Wire and cable edges from schematic pages.* Schematic pages show wires and cables connecting devices, each tagged uniquely (e.g., wire `11081`, cable `+VCS-0101-CBL170`). The parser emits a `wired_to` or `cabled_to` edge between the connected Device nodes, keyed by the wire or cable tag, with the source and destination terminal designations as edge properties. Wire edges carry signal name, voltage, and gauge; cable edges carry conductor count, type, length, and voltage rating when available. Because tags are unique, the same wire or cable shown on multiple schematic pages resolves to one edge, not multiple.

  *Cross-reference resolution.* Schematic pages cross-reference tags across pages and cabinets. EPLAN uses notation like "-24V_FU04 / &24VDC MULTILINE/607.1"; AutoCAD Electrical uses page-zone notation in a different syntax (e.g., "from 12-25"). Cross-reference notation is parsing input, not graph structure — it tells the parser that a tag continues elsewhere; the resolved tag is what becomes the edge identity.

  *Device hierarchy (when prefix-encoded).* When device tags use IEC 81346 prefix encoding (e.g., +VCS-0102 contains -PNL1 contains -CB4), the parser emits `contained_in` edges from the prefix structure. Tags without prefix encoding (NFPA, ISA 5.1) don't carry hierarchy in the tag string; for those projects, hierarchy is either absent or derived from a separate panel-layout sheet.

- **PLC project parser.** PLC projects from Rockwell, Siemens, and Beckhoff contain program structure, tag definitions, I/O mappings, and safety program partitions in parseable formats. Each platform has its own export format:

  *Rockwell:* L5X export (XML). Contains controller-scoped and program-scoped tags, routines, I/O module configurations, and safety task/safety tags as a distinct partition.

  *Siemens:* TIA Portal PLCopenXML export or project archive. Contains organizational blocks, function blocks (FBs), data blocks (DBs), tag tables with I/O addresses, and the F-program (F-DBs, F-FBs) as the safety partition.

  *Beckhoff:* TwinCAT project files (XML-based within a Visual Studio solution). Contains POUs, GVLs, I/O mappings linked to EtherCAT device configurations, and the TwinSAFE configuration as a separate structured export.

  The parser extracts three categories of data from any of these formats:

  *Tag definitions and I/O mappings.* Tag names, data types, and I/O addresses. These resolve to Device nodes from the drawings through the I/O address (a PLC input mapped to a specific terminal on a specific I/O module is the same device shown on the drawing). Tag names also appear in the SAT templates as system_reaction_tags and monitored_tags, connecting the logical layer to the procedural layer.

  *Program structure.* Routines, function blocks, POUs, and the call hierarchy between them. These become nodes in the logical layer with `calls` edges between them. Signal reads and writes within a routine become `reads_tag` and `writes_tag` edges to the shared entity layer.

  *Safety program partition.* The safety task (Rockwell), F-program (Siemens), or TwinSAFE configuration (Beckhoff) is where the SRS safety functions are implemented. The parser identifies which function blocks or routines implement which safety functions, creating `implemented_by` edges from SRS nodes through to specific code elements. This is the logical layer's contribution to the end-to-end traversal from hazard to verification.

- **SAT parser.** Handles three input formats — atform Python, Word `.docx`, and text-bearing PDF — and produces SAT nodes with the data model from §2.5 plus the edges (`addresses`, `references_srs`, `exercises_device`, `exercises_tag`, `depends_on_test`).

  *atform Python (AST walk).* The parser walks the AST of each module (`mcc.py`, `rsd.py`, etc.) in source order, simulating atform's section / test / skip counters: tracks `set_id_depth(N)` from `main.py`, opens or jumps sections on each `section(level, id=, ...)` call, increments the deepest-level counter on `add_test(...)` and `skip_test()` calls. Each `add_test` call yields a SAT node with its `numbering_position` set to the current (level_1, level_2, …, level_N) tuple. The parser does not import or execute atform — it reads the source as text via `ast`. SAT-authored fields (title, induced_fault, preconditions, hmi_message, test_cases) are extracted from the `add_test` call arguments; computed fields are joined from upstream nodes at validation time.

  *Word `.docx` (python-docx).* Reads headings and structured sections to recover the SAT's `numbering_position` (declared in the title or a header field) and the SAT-authored fields (procedure steps, references, expected behavior). Less structured than atform Python; parser may need per-template hints when heading conventions vary.

  *PDF (layout-aware text extraction).* Reads atform-rendered output, Word-exported SATs, and any text-bearing PDF. Recovers `numbering_position` from the rendered title block and procedure steps from the body. Scanned image-only PDFs are out of scope without OCR. Useful for ingesting legacy SATs where source isn't recoverable.

  Across all three formats, the parser validates the ingested `numbering_position` against the project numbering schema (§2.6) — schema-conformance findings are produced when the position doesn't compose against a declared binding.

### 6.3 Re-ingestion and Diff

When a revised document is committed, the parser runs again on that document and produces a new set of graph fragments. The ingestion pipeline computes the diff against the previous graph state: nodes added, nodes removed, edges added, edges removed, properties changed. The diff triggers re-evaluation of validation rules on all affected nodes. New findings are the set of nodes or edges that now fail validation where they previously passed, or traversal paths that are now blocked where they previously completed.

## 7. Outputs

The graph generates outputs as query projections. Different audiences need different projections of the same underlying graph.

### 7.1 Validation Matrix

The validation matrix is the master coverage artifact. Auditors use it to confirm that every safety function has a complete subsystem chain with Devices and SATs at every architectural position and that the architectural decomposition matches Sistema's. EKG generates the matrix as a multi-sheet projection of graph state.

**Sheet tiers.** The matrix contains four tiers of sheets:

1. **Index sheets** — project orientation and revision history.
2. **Reliance Matrix** — one row per SRS Entry, with columns for `validation_use` (`Full Validation` / `Fully Validated` / `Not Considered` / `Replaced`), `validation_review` (`Complete` / `In Progress` / etc.), and `validation_details` (free-form notes, typically constraints or deferrals). These columns are SRS-Entry-level properties EKG carries; the sheet is a flat projection of them.
3. **Per-system SF Validation sheets** — one per system, each a hierarchical projection of every SRS Entry in that system (structure described below). The per-system sheets are the core of the matrix and the largest by row count.
4. **Functional grouping sheets** and **project-specific sheets** — flat projections of SATs filtered by category. Categories are derived from the SAT's `numbering_position` plus user-defined groupings that may cross level boundaries.

**Per-system SF Validation sheet structure.** Each sheet is a sequence of SF blocks. One block per SRS Entry, with hierarchical row structure:

- **SF header row** — SRS title and testing-requirement marker (e.g., `Diagnostic`).
- **Chain element label rows** — `Input:` / `Logic:` / `Output:` — top-level decomposition matching the Sistema subsystem position (SS-I / SS-L / SS-O). Derived from grouping the SRS Entry's outgoing `implemented_by` edges by `subsystem_role`.
- **Sistema sub-block groupings** — within each chain element, `implemented_by` edges are further grouped by architectural sub-element (one sub-block per Sistema-defined unit, separated by a blank row). Sub-grouping requires Sistema integration; until the Sistema parser is in place, sub-grouping uses the Device's `parent_assembly` property as a proxy.
- **SAT rows** — within each sub-block, one row per SAT verifying any Device in that sub-block. The SAT row carries `numbering_position` (dotted form), title, and function descriptor (Device.function or per-SAT property). Composed by walking `tested_by`-inverse from the Device's FMEA Entries to enumerate verifying SATs.

**Composition summary.** The matrix derives mechanically from graph state — the Reliance Matrix from SRS Entry properties, the per-system sheets from `implemented_by` and `tested_by` edge traversals, the grouping sheets from `numbering_position`-based filters. Coverage state is always current with graph state; no hand-curation lag. The engineer-review part is the disposition of incomplete chains, not the matrix generation itself.

### 7.2 Coverage Report

The set of all nodes where traversal halted. Organized by finding type: hazards without mitigations, SRS entries without SATs, FMEA entries without covering tests, devices not exercised by any procedure.

### 7.3 Blast Radius Report

Given a proposed change (a device relocation, a feature addition, a consolidation), the set of all nodes reachable from the changed node through cross-layer edges. Organized into affected document types so the engineer knows which artifacts need revision.

### 7.4 SAT Generation

SAT documents are rendered by [atform](https://github.com/jvalenzuela/atform), a Python framework that produces PDF acceptance test documents via reportlab. EKG provides the data model as Python source containing `atform.add_test(...)` calls; atform reads and runs that source to produce the PDFs. atform has no template selector — the procedure list passed to `add_test(procedure=[...])` *is* the SAT-shape mechanism.

Emission walks the project's numbering schema (§2.6). For each chapter, EKG emits an `atform.section(1, id=…, title=…)` call, then descends per the schema's per-pair bindings — emitting `section(2, …)` and `section(3, …)` as the bindings dictate, with explicit IDs at every non-deepest level. At the deepest level, EKG walks the slot declaration (when the binding is `slot_declaration`) or the ordinal sequence (when `ordinal`), and emits one entry per slot in canonical order:

- **Authored SAT, recognized `procedure_pattern`:** EKG dispatches to the corresponding factory function, which emits the procedure list, wrapped in an `atform.add_test(...)` call.
- **Authored SAT, no recognized pattern:** EKG emits `atform.add_test(procedure=[...])` with a generic step list assembled from the data model.
- **Slot reserved by the schema, no SAT authored:** EKG emits `atform.skip_test()`. The deepest-level counter advances; nothing is rendered in the TOC. When the SAT is later authored, the `skip_test()` is replaced by `add_test(...)` and the SAT slots into the same `numbering_position` that the schema reserved for it.
- **Manually authored SAT (atform Python, hand-edited):** EKG does not re-emit the test. The SAT is already in the source; EKG ingests it via the SAT parser.

For each `procedure_pattern`, the procedure-list factory is project-defined (`fault_class`, `reaction_class`[, `device_class`] tuple → factory function). Common patterns ship as canonical factories; project-specific patterns are added by the engineering team without changing EKG's emitter.

Before emitting, EKG runs the overlap check described in section 4.2: group the pending SAT data models by `(reference_designator.id, induced_fault)`. Any group with more than one entry means multiple FMEA failure modes would produce SATs with the same physical fault injection on the same device. EKG flags these for engineer review. The engineer either consolidates the entries into a single SAT covering multiple failure modes or differentiates the induced fault to make the tests distinct. Only after the overlaps are resolved does EKG emit the `.py` source.

The boundary is text-based and runtime-independent: EKG never imports atform, and atform never imports EKG. EKG generates `.py` files containing `atform.add_test()` calls; atform reads them as part of its own run. Hand-authored atform modules (`common.py`, `rsd.py`, etc.) and EKG-generated modules coexist in the same atform project; `main.py` imports both and atform does not distinguish.

The engineer reviews the generated SAT, adjusts as needed, and signs off. The rendered SAT is committed to the git repo, ingested by the SAT parser (AST walk over the atform Python source), and its cross-references become edges in the graph, closing the coverage gap that prompted its generation.

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

### 7.7 Required Tests Projection

The required-tests projection is the gaps-first output that drives SAT authoring. It lists every SAT the FMEA chain identifies as required but not yet authored, with the SAT's `numbering_position` already composed by the project numbering schema (§2.6). Each row carries the dotted ID, the device or test target, the slot-declaration variant marker (REQUIRED / OPTIONAL / CONDITIONAL), the FMEA Entry the SAT addresses, and the SRS Entry it verifies.

The list is the engineer's pre-authoring worksheet. The engineer sees `1.1.74.2 +RSD-0111-PBPL1 — REQUIRED — addresses ETS.RSD.7.3 — verifies VCS-SRS-1.1` and authors against the assigned ID.

### 7.8 Master Test List Projection

The master test list — the directory of every SAT the project owns — is generated from the graph as a CSV (or any tabular format the project consumes). Columns include `numbering_position` (dotted form), title, device, FMEA reference, SRS reference, slot-declaration marker, authoring status (authored / reserved / required-not-authored), and any project-specific properties.

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
