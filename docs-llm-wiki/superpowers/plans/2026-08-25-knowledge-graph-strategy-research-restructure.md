# Knowledge Graph Strategy Research Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the WiFi MAC knowledge-graph research around evidence-derived code knowledge, documentation/domain knowledge, and bidirectional code-document linking strategies, with every market solution analyzed through both Agent question flows.

**Architecture:** The research uses a “2+1” capability model rather than an implementation architecture: code knowledge and documentation/domain knowledge are the two knowledge assets, and bidirectional code-document linking is the required connective capability. Agent interaction is evaluated as two end-to-end processes—natural language to source evidence, and source anchor to flow/domain explanation—while products may appear in every capability category they actually support.

**Tech Stack:** Markdown, Git, ripgrep, primary papers, AI-company technical publications, and official open-source project materials.

**Spec:** `docs/superpowers/specs/2026-08-25-knowledge-graph-strategy-research-restructure-design.md`

## Global Constraints

- Read the spec completely before editing any research document.
- Use only primary papers, AI-company technical publications, official project documentation, standards, and immutable official repository materials as evidence.
- Prefer recent evidence, but retain older canonical sources when they still define a tool or method.
- Keep every quantitative claim adjacent to its sample, task, baseline, metric, evidence ownership, and limitation.
- Treat first-party project measurements as first-party evidence; do not restate them as independent validation.
- Do not run WiFiDemo candidate experiments in this work; record unresolved questions in the Benchmark backlog.
- Do not announce a winning product or architecture without the later Benchmark.
- The main classification is code knowledge, documentation/domain knowledge, and code-document linking; Agent query orchestration is a comparison dimension, not a fourth knowledge category.
- Code knowledge contains lightweight structural indexing and deep program analysis as subtypes of the same Agent-facing problem.
- LLM-Wiki/WiCER remain as document-knowledge strategies; generic Skill and memory systems are excluded unless a concrete product directly links them to graph nodes or code evidence.
- A project may appear in multiple categories; do not force Graphify, Understand Anything, RepoDoc, or GitNexus into one exclusive product bucket.
- Remove the eight-layer, A/B backbone, and A0/A1/B0/B1 framing from current research conclusions and matrices; keep historical specs and plans unchanged.
- Preserve `docs/research/wifi-mac-repository-design-considerations.md` byte-for-byte.
- Preserve the distinction between verified source facts, project claims, research synthesis, and unknown/Benchmark-required conclusions.
- Use `apply_patch` for all file edits.
- Run `git diff --check` before every task commit and before final publication.

## File Map

- `docs/research/source-ledger.md` — primary-source records and the evidence basis for the 2+1 capability argument.
- `docs/research/solution-inventory.md` — category-specific strategy analysis and repeatable product cards.
- `docs/research/code-domain-linkage.md` — observable code-document link strategies and bidirectional Agent paths.
- `docs/research/evidence-matrix.md` — cross-product capability matrix without architecture-layer mapping.
- `docs/research/benchmark-backlog.md` — future tests for the two end-to-end Agent question flows.
- `docs/research/wifi-mac-knowledge-architecture-paper.md` — reader-facing paper with the approved reasoning sequence.
- `docs/research/audit-report.md` — recomputed evidence counts, scope, link checks, and unresolved limitations.
- `docs/research/wifidemo-workload-casebook.md` — unchanged workload evidence unless a path reference must be corrected.
- `docs/research/wifi-mac-repository-design-considerations.md` — historical source, unchanged.

---

### Task 1: Establish the Evidence Basis for the 2+1 Capability Model

**Files:**
- Modify: `docs/research/source-ledger.md`
- Inspect: `docs/research/wifi-mac-knowledge-architecture-paper.md`
- Inspect: `docs/research/solution-inventory.md`

**Interfaces:**
- Consumes: existing S001–S040 records and the inclusion rules in the approved spec.
- Produces: verified source records and a capability-evidence map used by Tasks 2–6.

- [ ] **Step 1: Run the pre-change evidence test**

Run:

```bash
rg -n -e "2\+1" -e "RepoDoc" -e "Repository Intelligence Graph" docs/research/source-ledger.md
```

Expected: no complete 2+1 evidence map and no verified RepoDoc/RIG records; the command may return no matches or only incidental text.

- [ ] **Step 2: Re-open the primary sources used for the capability argument**

Verify the original pages, not search snippets:

```text
S001 Agent Retrieval Bench — https://arxiv.org/abs/2607.24882
S002 CORE-Bench — https://arxiv.org/abs/2606.11864
S003 ContextBench — https://arxiv.org/abs/2602.05892
S007 CodeGraph official repository/docs — https://github.com/colbymchenry/codegraph
S009 Understand Anything official repository — https://github.com/Egonex-AI/Understand-Anything
S015 Joern official repository/docs — https://github.com/joernio/joern
S021 Graphify official repository/docs — https://github.com/Graphify-Labs/graphify
S023 WiCER — https://arxiv.org/abs/2605.07068
S039 codebadger — https://arxiv.org/abs/2603.24837
S041 RepoDoc — https://arxiv.org/abs/2604.26523
S042 Repository Intelligence Graph — https://arxiv.org/abs/2601.10112
```

For GitHub projects, record the full current commit SHA and access date `2026-08-25`; do not cite mutable search-result text as the evidence record.

- [ ] **Step 3: Add S041 and S042 using the existing ledger schema**

Add complete records containing title, date, source type, publisher/authors, direct URL, immutable artifact where available, study object, sample, Agent/model, baseline, metric, relevant numbers, limitations, first-party/independent status, intended paper use, and verification state.

S041 must state RepoDoc’s three-stage strategy—RepoKG construction, module clustering, and graph-grounded cross-referenced documentation with incremental updates—without treating its author evaluation as WiFi MAC evidence.

S042 must state RIG’s deterministic evidence-backed repository architecture map and its reported Agent evaluation conditions, while separating build/dependency mapping from full C program behavior or domain-document knowledge.

- [ ] **Step 4: Refresh the capability-relevant fields of existing records**

Update S007, S009, S021, and S039 only where the newly opened primary material adds directly relevant information:

```text
CodeGraph: natural-language/explore request -> indexed symbols/call paths -> source context
Understand Anything: deterministic structure -> LLM semantic/domain/flow assets
Graphify: code + docs -> graph/community/report/wiki; EXTRACTED/INFERRED/AMBIGUOUS provenance
codebadger: high-level MCP navigation/slice/taint/dataflow tools over Joern
```

Do not replace older frozen measurement contexts with current README headline values unless the measurement protocol and version are also updated.

- [ ] **Step 5: Add a 2+1 capability-evidence map**

Add a short ledger index that maps evidence to conclusions:

```text
Code knowledge need <- S001/S002/S003 + S007/S015/S039/S042
Document/domain knowledge need <- S009/S021/S023/S041
Bidirectional link need <- S009/S021/S041 plus their explicit code/document anchors
```

The map must say that the “mature solution requires all three” statement is a research synthesis from converging evidence, not a sentence directly claimed by one source.

- [ ] **Step 6: Verify source records and quantitative context**

Run:

```bash
rg -n -e "^### S041" -e "^### S042" -e "2\+1" -e "first-party" -e "限制" docs/research/source-ledger.md
rg -n -e "427" -e "27%" -e "35%" -e "RepoKG" -e "module clustering" docs/research/source-ledger.md
git diff --check
```

Expected: S041/S042 and the capability map are present; every retained number appears with sample/protocol and limitation context; whitespace check passes.

- [ ] **Step 7: Commit the evidence foundation**

```bash
git add docs/research/source-ledger.md
git commit -m "docs: ground knowledge graph capability model"
```

---

### Task 2: Reorganize Market Solutions by Knowledge-Building Strategy

**Files:**
- Modify: `docs/research/solution-inventory.md`
- Read: `docs/research/source-ledger.md`

**Interfaces:**
- Consumes: Task 1 source records and the spec’s unified ten-field product card.
- Produces: category-specific product evidence consumed by the matrix and paper.

- [ ] **Step 1: Run the pre-change organization test**

Run:

```bash
rg -n -e "八层架构骨架" -e "骨架层" -e "A0" -e "代码知识建立策略" -e "文档与领域知识建立策略" docs/research/solution-inventory.md
```

Expected: old eight-layer/bone terminology is present and the approved three-category organization is absent or incomplete.

- [ ] **Step 2: Replace the opening classification and reading rules**

Define the inventory’s unit of analysis as a capability strategy, not an exclusive product family. State the two Agent question flows and explain that products may recur across sections.

Delete the current eight-layer mapping and Agent/source axes when they only serve layer classification. Retain source ownership and evidence quality as fields in every product card.

- [ ] **Step 3: Build the code-knowledge section**

Organize two subtypes under one heading:

```text
Lightweight structural index:
  lexical/vector/RepoMap as baselines
  Codebase-Memory
  CodeGraph
  GitNexus
  SCIP/Serena as supporting navigation facilities

Deep program analysis graph:
  Joern
  codebadger as Agent-facing Joern use
  CodeQL/QLCoder
  Fraunhofer CPG
  Clang/Kythe/SVF/Frama-C/PhASAR/Semgrep as engines or specialist references
```

For each highlighted solution, describe both directions: how a natural-language request becomes code evidence, and how a code anchor can or cannot be expanded into a process explanation.

- [ ] **Step 4: Build the document/domain-knowledge section**

Organize three strategies:

```text
Existing-document ingestion: README, ADR/RFC, specifications, PDFs
Code-graph-driven generation: Graphify, Understand Anything, RepoDoc, GitNexus process/community
Multi-document Wiki compilation: LLM-Wiki/WiCER
```

State which outputs are raw sources, generated summaries, reports, Wiki pages, domain/flow/step nodes, or cross-referenced documents. Do not treat generated text as verified code behavior.

- [ ] **Step 5: Add cross-category product cards**

Graphify, Understand Anything, RepoDoc, and GitNexus must appear in every section where they provide evidence-backed capability. Each occurrence must focus on that category and link to the project’s full card rather than duplicating generic license/activity text.

Each full card must answer the spec’s ten fields, including the exact Agent path for both directions and the current C/WiFi MAC unknowns.

- [ ] **Step 6: Remove generic Skill/memory product analysis**

Delete H04–H07 style standalone ranking of RepoMem, Copilot Memory, progressive Skills, and Specification-as-Skill from the market-solution classification. Preserve only concise evidence-bound notes when they explain an interface, a document source, a negative context result, or a later Benchmark control.

- [ ] **Step 7: Verify the new inventory**

Run:

```bash
rg -n -e "代码知识建立策略" -e "轻量结构索引" -e "深度程序分析图" -e "文档与领域知识建立策略" -e "代码—文档链接" docs/research/solution-inventory.md
rg -n -e "Graphify" -e "Understand Anything" -e "RepoDoc" -e "CodeGraph" -e "Joern" -e "codebadger" -e "LLM-Wiki" docs/research/solution-inventory.md
rg -n -e "八层架构骨架" -e "骨架层" -e "A0" -e "A1" -e "B0" -e "B1" docs/research/solution-inventory.md
git diff --check
```

Expected: all three capability categories and representative products are present; the final legacy-term search returns no current-classification matches; whitespace check passes.

- [ ] **Step 8: Commit the strategy inventory**

```bash
git add docs/research/solution-inventory.md
git commit -m "docs: classify knowledge graph construction strategies"
```

---

### Task 3: Reframe Code-Document Linking Around Observable Strategies

**Files:**
- Modify: `docs/research/code-domain-linkage.md`
- Read: `docs/research/solution-inventory.md`
- Read: `docs/research/source-ledger.md`

**Interfaces:**
- Consumes: the category cards and verified link behavior from Tasks 1–2.
- Produces: a strategy comparison and two bidirectional paths used by the matrix, paper, and Benchmark.

- [ ] **Step 1: Run the pre-change linkage test**

Run:

```bash
rg -n -e "最小实体集合" -e "CodeEvidence" -e "DomainEvidence" -e "显式引用链接" -e "代码结构派生链接" docs/research/code-domain-linkage.md
```

Expected: schema/contract detail dominates and the five approved observable link strategies are not yet the document’s main organization.

- [ ] **Step 2: Replace the implementation-contract opening**

Open with the two user-visible directions:

```text
domain question -> document concept -> code entity -> current source evidence
code entity -> structural/behavior graph -> process/domain node -> readable document
```

Explain that putting code and documents in one database is not sufficient; the link must be queryable in both directions and expose its evidence/derivation.

- [ ] **Step 3: Compare the five link strategies**

Create one table with rows:

```text
explicit document-to-code reference
code-structure-derived process link
rule-derived domain link
LLM-inferred candidate link
claim/source/citation evidence link
```

Columns must include producer, supported direction, granularity, confidence/authority, update behavior, representative projects, and failure mode.

- [ ] **Step 4: Add representative project walkthroughs**

Show how Graphify, Understand Anything, RepoDoc, Joern/codebadger plus external documentation, and LLM-Wiki plus an external code graph realize or fail to realize both directions.

Keep Target/revision/source location only as evidence requirements needed to avoid stale or cross-build answers; remove schema-heavy implementation prescriptions that do not distinguish market strategies.

- [ ] **Step 5: Define the minimum trustworthy answer contract**

For natural-language-to-code answers require: interpreted concept, retrieved candidates, relation path, final file/symbol/source span, revision/Target where applicable, and uncertainty.

For code-to-flow answers require: starting code anchor, graph relations used, grouping/synthesis method, generated flow/document node, supporting code references, source documents, and freshness status.

- [ ] **Step 6: Verify the linkage study**

Run:

```bash
rg -n -e "显式文档" -e "结构派生" -e "规则派生" -e "LLM" -e "claim" -e "双向" docs/research/code-domain-linkage.md
rg -n -e "Graphify" -e "Understand Anything" -e "RepoDoc" -e "codebadger" -e "LLM-Wiki" docs/research/code-domain-linkage.md
git diff --check
```

Expected: five link strategies, both directions, representative projects, and answer contracts are present; whitespace check passes.

- [ ] **Step 7: Commit the linkage strategy study**

```bash
git add docs/research/code-domain-linkage.md
git commit -m "docs: compare bidirectional code document links"
```

---

### Task 4: Rebuild the Capability Matrix and Future Benchmark

**Files:**
- Modify: `docs/research/evidence-matrix.md`
- Modify: `docs/research/benchmark-backlog.md`
- Read: `docs/research/wifidemo-workload-casebook.md`

**Interfaces:**
- Consumes: category-specific product cards and the minimum answer contracts from Tasks 2–3.
- Produces: a cross-category market comparison and executable future evaluation questions for Task 5.

- [ ] **Step 1: Run the pre-change matrix test**

Run:

```bash
rg -n -e "八层覆盖" -e "A0" -e "A1" -e "B0" -e "B1" docs/research/evidence-matrix.md docs/research/benchmark-backlog.md
```

Expected: old layer and four-arm terminology is present.

- [ ] **Step 2: Define matrix columns around observed capabilities**

Use one row per project/strategy and these columns:

```text
lightweight structural code knowledge
deep behavioral/program knowledge
existing-document ingestion
generated process/domain documentation
code -> document link
document -> code link
natural-language -> source process
source -> flow/domain process
incremental/freshness behavior
Agent interface
public evidence strength
C/WiFi MAC evidence and unknowns
```

Use evidence states such as `verified capability`, `project claim`, `architecturally plausible`, `unsupported`, and `unknown`; do not compute an aggregate score.

- [ ] **Step 3: Populate cross-category rows**

Include at least CodeGraph, Codebase-Memory, GitNexus, Joern, codebadger, CodeQL/QLCoder, Graphify, Understand Anything, RepoDoc, and LLM-Wiki/WiCER. A row may show capability in several categories.

- [ ] **Step 4: Reorganize B01–B15 under the two question flows**

Preserve the existing IDs where the test purpose remains useful, but remove A0/A1/B0/B1 as the compared arms.

Group future tests as:

```text
Flow Q1 — natural language -> concrete source evidence
  retrieval, symbol resolution, Target disambiguation, call/reference expansion,
  deep dataflow when required, evidence precision, abstention, cost

Flow Q2 — concrete source anchor -> process/domain explanation
  relation expansion, event/indirect-call handling, module/process grouping,
  document generation, bidirectional citations, freshness, human correctness
```

Define candidate conditions by enabled strategy capabilities—for example plain Agent tools, lightweight code graph, deep program graph, code graph plus documentation, and code graph plus generated/linked documentation—without claiming these are exhaustive architectures.

- [ ] **Step 5: Retain independent outcome dimensions**

Report separately:

```text
fact/source accuracy
retrieval efficiency and context cost
flow/document faithfulness
link coverage and bidirectionality
freshness/update cost
final Agent answer correctness
```

Do not hide Target leakage, missing evidence, or hallucinated process steps in one score.

- [ ] **Step 6: Verify matrix and backlog**

Run:

```bash
rg -n -e "自然语言" -e "具体源码" -e "代码知识" -e "文档/领域" -e "双向" docs/research/evidence-matrix.md docs/research/benchmark-backlog.md
rg -n -e "CodeGraph" -e "Joern" -e "Graphify" -e "Understand Anything" -e "RepoDoc" -e "LLM-Wiki" docs/research/evidence-matrix.md
rg -n -e "八层" -e "A0" -e "A1" -e "B0" -e "B1" docs/research/evidence-matrix.md docs/research/benchmark-backlog.md
rg -c "^\| B[0-9][0-9] " docs/research/benchmark-backlog.md
git diff --check
```

Expected: capability matrix and Q1/Q2 Benchmark groups are present; old architecture terms return no current matches; B01–B15 remain identifiable or every retired ID is explicitly accounted for; whitespace check passes.

- [ ] **Step 7: Commit the matrix and Benchmark**

```bash
git add docs/research/evidence-matrix.md docs/research/benchmark-backlog.md
git commit -m "docs: align benchmark with agent knowledge flows"
```

---

### Task 5: Rewrite the Reader-Facing Paper

**Files:**
- Modify: `docs/research/wifi-mac-knowledge-architecture-paper.md`
- Read: `docs/research/source-ledger.md`
- Read: `docs/research/solution-inventory.md`
- Read: `docs/research/code-domain-linkage.md`
- Read: `docs/research/evidence-matrix.md`
- Read: `docs/research/benchmark-backlog.md`
- Preserve: `docs/research/wifi-mac-repository-design-considerations.md`

**Interfaces:**
- Consumes: all verified research artifacts from Tasks 1–4.
- Produces: the final coherent paper and its local evidence links.

- [ ] **Step 1: Run the pre-change paper structure test**

Run:

```bash
rg -n "^## " docs/research/wifi-mac-knowledge-architecture-paper.md
rg -n -e "四条独立调研主线" -e "八层参考骨架" -e "A0" -e "A1" -e "B0" -e "B1" docs/research/wifi-mac-knowledge-architecture-paper.md
```

Expected: the rejected four-line/eight-layer/four-arm structure is present.

- [ ] **Step 2: Write the abstract and two-question opening**

The abstract must state that the paper studies knowledge-building strategies, not internal implementation layers or a predetermined product winner.

Section 1 must define both end-to-end questions with concrete input/output:

```text
natural-language engineering question -> file/symbol/source evidence
source anchor -> call/data/event relations -> process/domain explanation with citations
```

- [ ] **Step 3: Insert the required evidence-derived bridge before category analysis**

Section 2 must explicitly argue:

```text
retrieval studies show code candidate acquisition is necessary but insufficient;
code graph/program analysis provides structural and behavioral evidence but not domain meaning;
document/Wiki generation provides explanation but is lossy without code grounding;
therefore mature Agent assistance needs code knowledge + document/domain knowledge + bidirectional links.
```

Support each premise with nearby S-IDs/direct primary links, evidence ownership, numbers only where samples and limitations are given, and a sentence identifying the final 2+1 statement as research synthesis.

- [ ] **Step 4: Write the three strategy chapters**

Use the approved sequence:

```text
Section 3 — code knowledge: lightweight structural index vs deep program analysis
Section 4 — document/domain knowledge: ingestion, graph-driven generation, Wiki compilation
Section 5 — code-document link strategies and freshness
```

Discuss CodeGraph and Joern in the same code-knowledge chapter. Repeat Graphify, Understand Anything, RepoDoc, and GitNexus where their evidence crosses categories.

- [ ] **Step 5: Write the project matrix and two Agent process comparisons**

Section 6 summarizes the cross-category matrix without total scores.

Section 7 walks representative products through both directions. Each walkthrough must identify what is precomputed, what the Agent queries, how candidates expand, what source/document evidence returns, what is inferred, and where the process stops or remains unknown.

- [ ] **Step 6: Write WiFi MAC applicability, Benchmark, threats, and conclusion**

Keep W01–W08 as workload evidence and evaluation constraints, not as an eight-layer architecture derivation.

State obvious exclusions and unknowns, then reference the Q1/Q2 Benchmark backlog. The conclusion must summarize capability coverage and open questions, not choose a winner.

- [ ] **Step 7: Remove obsolete mainline concepts**

Remove independent Skill/memory discussion, eight-layer mappings, A/B backbones, A0/A1/B0/B1, and any conclusion that treats MCP, storage, provenance schema, or a deep-analysis engine as the top-level market classification.

- [ ] **Step 8: Verify paper structure, citations, and local links**

Run:

```bash
rg -n "^## " docs/research/wifi-mac-knowledge-architecture-paper.md
rg -n -e "代码知识" -e "文档与领域知识" -e "代码—文档链接" -e "自然语言" -e "具体代码" docs/research/wifi-mac-knowledge-architecture-paper.md
rg -n -e "CodeGraph" -e "Joern" -e "codebadger" -e "Graphify" -e "Understand Anything" -e "RepoDoc" -e "LLM-Wiki" docs/research/wifi-mac-knowledge-architecture-paper.md
rg -n -e "四条独立调研主线" -e "八层" -e "A0" -e "A1" -e "B0" -e "B1" docs/research/wifi-mac-knowledge-architecture-paper.md
git diff --check
```

Expected: the ten-section approved reasoning order and representative projects are present; obsolete terms return no current matches; local Markdown links resolve; whitespace check passes.

- [ ] **Step 9: Commit the rewritten paper**

```bash
git add docs/research/wifi-mac-knowledge-architecture-paper.md
git commit -m "docs: rewrite knowledge graph strategy paper"
```

---

### Task 6: Recompute the Audit and Run Final Verification

**Files:**
- Modify: `docs/research/audit-report.md`
- Inspect: all `docs/research/*.md`
- Preserve: `docs/research/wifi-mac-repository-design-considerations.md`

**Interfaces:**
- Consumes: final Tasks 1–5 documents.
- Produces: a reproducible audit, clean Git state, and a publishable research branch.

- [ ] **Step 1: Recompute counts from files, not previous prose**

Run and record actual outputs:

```bash
rg -c "^### S[0-9][0-9][0-9] " docs/research/source-ledger.md
rg -c "状态：claim-verified" docs/research/source-ledger.md
rg -c "^\| B[0-9][0-9] " docs/research/benchmark-backlog.md
rg -n -e "CodeGraph" -e "Joern" -e "Graphify" -e "Understand Anything" -e "RepoDoc" -e "LLM-Wiki" docs/research/evidence-matrix.md
```

Do not reuse the old 40/14/15 counts unless the fresh output independently matches them.

- [ ] **Step 2: Audit the required bridge argument**

Verify that the paper’s classification bridge contains:

```text
retrieval evidence -> code knowledge requirement
code graph/program analysis evidence -> behavioral evidence boundary
document/Wiki evidence -> domain explanation requirement and loss risk
cross-project evidence -> bidirectional link requirement
explicit label that the 2+1 conclusion is research synthesis
```

- [ ] **Step 3: Audit cross-category treatment and exclusions**

Verify Graphify, Understand Anything, and RepoDoc occur in all applicable categories; CodeGraph and Joern share the code-knowledge category; LLM-Wiki/WiCER remain document strategies; generic Skill/memory no longer appear as ranked solutions.

- [ ] **Step 4: Audit numbers and source ownership**

Scan all paper numbers and confirm every result is supported by a claim-verified record with sample, baseline, metric, first-party/independent status, and limitation.

Run:

```bash
rg -n -e "%" -e "倍" -e "个样本" -e "个仓" docs/research/wifi-mac-knowledge-architecture-paper.md
rg -n -e "第一方" -e "独立" -e "作者实验" -e "限制" docs/research/wifi-mac-knowledge-architecture-paper.md docs/research/source-ledger.md
```

- [ ] **Step 5: Audit current-document terminology and paths**

Run:

```bash
rg -n -e "八层架构" -e "A0" -e "A1" -e "B0" -e "B1" docs/research/wifi-mac-knowledge-architecture-paper.md docs/research/solution-inventory.md docs/research/evidence-matrix.md docs/research/benchmark-backlog.md
rg -n -e "research.md" -e "目标代码仓注意事项.md" docs/research
```

Expected: no obsolete current-classification or old-path matches. Historical specs/plans are outside this check and remain unchanged.

- [ ] **Step 6: Verify the historical note by Git blob identity**

Run:

```bash
git rev-parse "3015105de36e55e8fc7041e0a256f98476964382:目标代码仓注意事项.md"
git rev-parse "HEAD:docs/research/wifi-mac-repository-design-considerations.md"
```

Expected: both commands print the same blob object ID.

- [ ] **Step 7: Update the audit report with actual results**

Rewrite `docs/research/audit-report.md` to record the new source counts, capability categories, cross-category project coverage, numeric audit, link audit, unchanged note blob, no-experiment scope, and remaining unknowns.

- [ ] **Step 8: Run final repository verification**

Run:

```bash
git diff --check
git status --short
rg -n "^## " docs/research/wifi-mac-knowledge-architecture-paper.md
rg -n -e "代码知识" -e "文档与领域知识" -e "代码—文档链接" docs/research/wifi-mac-knowledge-architecture-paper.md docs/research/solution-inventory.md docs/research/evidence-matrix.md
rg -n -e "unknown" -e "Benchmark" docs/research/wifi-mac-knowledge-architecture-paper.md docs/research/evidence-matrix.md docs/research/benchmark-backlog.md
```

Expected: no whitespace errors, only intended research/audit changes before commit, approved structure present, and unresolved claims remain explicitly unknown or Benchmark-required.

- [ ] **Step 9: Commit the audit**

```bash
git add docs/research/audit-report.md
git commit -m "docs: audit strategy-centered knowledge graph research"
```

- [ ] **Step 10: Verify the committed branch**

Run:

```bash
git status --short --branch
git log --oneline --decorate -8
git diff --check main..HEAD
```

Expected: clean research worktree, intentional documentation commits only, and no whitespace errors relative to `main`.
