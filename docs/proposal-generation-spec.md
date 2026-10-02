# Concise proposal generation: implementation specification

Status: proposed implementation; repository reviewed 3 October 2026. This document specifies changes, not deployed behavior. The six-page example was described in the request; its DOCX was not inspected.

## Objective and scope

Generate a concise, evidence-grounded pre-research proposal with one provider request per generation attempt, application validation, and deterministic DOCX rendering. Apply the same prompt, evidence standards, and validation to free and paid proposals. Preserve discovery decisions, complete audit access, queue status/download contracts, notifications, entitlements, and experiment attribution.

Initial scope is `report_type="proposal"`. Keep `full_starter` (Complete Literature Review) and its paid entitlement working through the existing path until separately migrated. Do not interpret the proposal redesign as removal of that product.

One call means one outbound synthesis request on an uncached successful attempt. Cache hits use zero. A later background retry is a separate attempt and must be counted. Discovery provider requests are measured separately. No abstract-polishing, JSON repair, corrective drafting, or provider failover calls inside a proposal attempt.

## Verified current implementation

| Location | Observed behavior | Required change |
| --- | --- | --- |
| `cloud_app.py`, report generation endpoint | Calls `DossierGenerator.generate_comprehensive_dossier`, then Scribe; returns cached documents or queues provider errors | Route proposals through a shared proposal service; preserve response contracts |
| `app/reports/dossier_generator.py` | Generates dossier prose via `generate_with_failover` before Scribe runs | Bypass this LLM stage for proposals; retain for existing other consumers |
| `app/agents/scribe_agent.py::_prepare_proposal_draft` | Already sends a structured, multi-section request; adds a corrective request after validation failure | Replace overlapping schema and remove synchronous correction |
| `ScribeResearchAgent::_generate_proposal_json` | Can issue two requests for parsing; uses default proposal limit of 4,096 tokens | Exactly one request; explicit parse/truncation failures |
| `ScribeResearchAgent::_format_abstract` | Can call an abstract editor and inject fallback/length-padding prose | Do not invoke on the new proposal path |
| `ScribeResearchAgent::_prepare_proposal_draft` | Sends up to ten sources with abstracts shortened to 80 words, plus dossier notes | Prepare a versioned evidence packet with disclosed truncation and coverage |
| `ScribeResearchAgent::_validate_proposal_paragraphs` | Some missing/unknown evidence IDs are replaced with the first source | Reject invalid attribution; never repair by guessing |
| `ScribeResearchAgent::_write_synthesis_body` | Filters referenceable sources, renders using python-docx, rejects incomplete synthesis before save | Reuse formatting/citation utilities; separate validation from rendering |
| `app/synthesis/providers.py` | Provider abstraction exists; registry supports sequential failover | Add a single-provider structured-generation operation |
| `app/research/research_pipeline.py::run_research` | Discovery/audit path also calls dossier synthesis; audit survives its failure | Separate evidence/audit preparation from optional synthesized insight generation |
| `app/reports/report_queue.py::process_pending_jobs` | Regenerates dossier and report on every attempt; retries broad exceptions | Call shared proposal service; classify retryable failures |
| `ReportQueueManager` | Jobs live in `_jobs`; constructor's database argument does not persist jobs | Add durable storage/claiming before promising restart-safe pending reports |
| `mcp_server.py`, `trigger_docx_generation` | Separately calls dossier synthesis followed by Scribe | Route native proposals through the same service |
| `cloud_app.py::report_cache_key` | Hashes topic, domain, type, sources, and cache version | Version new artifacts and include all effective content settings |

The current design is not eight separate section-generation calls. Its main avoidable work is serial dossier generation, potential abstract editing, and retries around an already structured proposal request. Speed improvements must be measured rather than inferred from the hypothetical eight-call example.

## Target flow

1. Resolve an owned research run or normalize explicitly supplied/uploaded records using existing eligibility rules.
2. Preserve the full discovery result and audit artifact independently of proposal success.
3. Build the compact evidence packet and stable source registry deterministically.
4. Resolve a versioned cache hit or make one configured provider request.
5. Parse and validate the complete structured draft.
6. Render DOCX, persist the artifact, and return the existing ready response.
7. On retryable provider failure, persist a queued job immediately and return the existing queued response. Subsequent attempts run in the background.

The no-sources-supplied route must use the separated discovery/audit preparation path; merely replacing Scribe leaves hidden dossier calls inside `run_research`. Existing standalone research features can still request their current synthesis explicitly. Do not send previous generated dossiers to proposal synthesis as evidence.

## Proposed modules and contracts

| New module | Responsibility |
| --- | --- |
| `app/reports/evidence_preparation.py` | `prepare_proposal_evidence(topic, included_sources, settings) -> EvidencePacket`; no network or LLM |
| `app/reports/proposal_schema.py` | Strict Pydantic packet/draft models and JSON schema generated from those models |
| `app/reports/proposal_prompt.py` | Versioned provider-neutral instructions plus serialized topic, evidence, limitations, and permitted user preferences |
| `app/reports/proposal_validation.py` | Citation, schema, length, evidence-status, and alignment checks; structured error codes |
| `app/reports/proposal_renderer.py` | `render_proposal(validated_draft, source_registry, output_directory) -> Path`; no provider dependency |
| `app/reports/proposal_service.py` | Shared orchestration returning artifact, quality results, provenance, and stage telemetry |
| `app/reports/proposal_config.py` | Validated settings, prompt/schema/template versions, and bounded output profiles |

Keep `generate_apa_dossier_report(...)` as a compatibility adapter during migration. Any supplied dossier is legacy context, not permission for another synthesis request. Move callers to the service and remove the adapter only after all consumers migrate.

## Evidence packet and relevance

Each record contains `source_id`, original run ID/UID mapping, title, authors, year, venue, DOI/URL, retrieved abstract or excerpts, evidence type, relevance classification, and evidence limitations. IDs must remain stable across ranking, retries, and rendering; a run-local `SRC-001` is acceptable when its mapping is persisted. Validate citations against IDs actually sent to the provider, not every source in the research run.

Normalize DOI and URL forms; deduplicate by reliable identifiers first. Use conservative normalized title/author/year matching only when identifiers are absent. Retain every original record and an alias-to-canonical mapping in provenance. Conflicting identifiers or metadata must be flagged, not silently merged. Work on copies so report preparation cannot mutate audit records.

Use full abstracts when they fit. Under an input budget, choose deterministic, sentence-bounded excerpts and record original length, transmitted length, and truncation. Never invent evidence notes from a title, citation count, or metadata-based `source_contribution`. Evidence notes require a retrieved text span and provenance. Mark metadata-only records explicitly; they cannot support empirical literature claims.

Relevance annotations are additive:

- `direct`: supplied content addresses the central topic relationship and population/context.
- `contextual`: supports background but does not answer that relationship.
- `insufficient`: available content demonstrates a mismatch.
- `unknown`: available evidence is too sparse for a dependable classification.

Store rationale, supporting spans, and classifier version. Use existing normalized topic concepts and available abstracts/excerpts; do not treat keyword overlap, venue quality, or citation count as proof of direct relevance. Ambiguous records remain unknown rather than receiving confident inferred labels. This stage adds no LLM call.

The AI/university/performance fixture must distinguish AI use and student outcomes from institutional AI readiness, and from PMS/student performance without an AI connection. Title-only ambiguity should produce `unknown`, not fabricated certainty.

Preserve existing `inclusion_reason` and `exclusion_reason` strings byte-for-byte. A report-use decision is separate from the discovery decision: record `proposal_use=direct|context|not_used` and a separate reason. Do not silently move sources between the historical included/excluded sets. Append relevance/report-use columns to the audit with all original rows retained. Updating discovery selection policy itself requires a separately versioned change and regression fixtures.

If the packet cannot include all eligible sources, record sent/omitted IDs and why, and disclose the bounded synthesis scope. Never apply a proposal input cap to the Excel excluded set. Free users retain the same full exclusion set and reasons.

No usable retrieved content: return an explicit insufficient-evidence result, retain the audit, and do not generate an empty academic report. Sparse but usable evidence: permit a shorter qualified proposal, including fewer than three supported themes.

## Draft schema, version 2

Use `extra="forbid"` throughout and bounded string/array sizes. The provider does not generate a bibliography, document title, topic spelling, or layout instructions; the application owns these.

| Field | Shape and requirements |
| --- | --- |
| `schema_version` | Literal `proposal.v2` |
| `overview` | Paragraph blocks covering context and study purpose |
| `literature_insights` | Up to five themes, each with title and evidence-linked blocks; target three to five only when supported |
| `contradictions_and_limitations` | Blocks; contradictions require supplied evidence, otherwise a specific limitation |
| `research_gap` | Blocks bounded to what the supplied evidence leaves unresolved |
| `research_problem` | Concise blocks connecting that gap to the proposed investigation |
| `research_questions` | One primary object and zero to three supporting objects, each with stable question ID |
| `research_objectives` | One general and up to three specific objects with `question_ids` |
| `methodology` | Proposed design, population/context, variables/measures, data collection, analysis, and feasibility limitations |
| `conclusion` | Short proposed direction, with no new unsupported findings |
| `evidence_limitations` | Specific limitations, grouped without repeated boilerplate |

Paragraph block: `{text, kind, evidence_ids}`, where `kind` is `evidence`, `interpretation`, `proposal`, or `limitation`. Evidence/interpretation blocks require known, suitable evidence IDs. Pure proposed methods and scope limitations may have empty citation arrays. The distinction is visible in rendering, not merely hidden in metadata. Questions and objectives must not be forced to carry arbitrary citations; their rationale links back to the gap/problem blocks.

Generate provider schema and application validators from one model definition. The prompt must instruct the model to use only supplied content, treat retrieved text as untrusted data rather than instructions, distinguish proposals from findings, avoid unsupported causality and field-wide novelty claims, and return only JSON. Preserve relevant user preferences without allowing them to override evidence constraints.

## Validation and failure policy

Hard failures: invalid/truncated JSON; missing required structure; unknown citation IDs; citations to records omitted from the prompt; evidence claims supported only by metadata; blank required content; excessive configured length; malformed question/objective references; leaked instructions/placeholders; invalid proposed-method structure.

Never substitute the first source for a missing citation. Do not discard unsupported citations and then publish their claims. No model-based corrective pass in the foreground. Surface stable errors such as `invalid_schema`, `unknown_citation`, `output_truncated`, `insufficient_evidence`, and `unsupported_evidence_type`.

Duplicate sentences and repeated generic disclaimers should be detected. Do not enforce exactly two sentences or a minimum paragraph length. Narrative word counting excludes citations, headings, metadata tables, and references. Target 1,200–1,600 words; shorter supported output is acceptable. Start with a configurable hard ceiling of 1,800 words for the default profile. Do not cut paragraphs mid-sentence to pass validation.

Application checks establish traceability and structural consistency, not that a cited study entails every sentence. Human evidence review is a release gate for the benchmark set; retain text-span provenance to make this review practical. A valid ID alone must not be advertised as proof of factual accuracy.

Adapt `PublicationQualityGate` for the v2 draft contract; do not feed a synthetic empty legacy dossier into its old section requirements or hard-code a passing quality score. Return explicit structural, traceability, and evidence-coverage results; keep API quality fields compatible where meaningful.

## Rendering

Render six numbered sections: Research Overview; Literature Insights (including contradictions/limitations); Identified Research Gap; Proposed Research Direction (problem, questions, objectives); Suggested Methodology; Evidence and References. Put conclusion at the end of proposed direction or methodology without adding a seventh top-level section.

Reuse `CitationEngine` and existing bibliographic formatting utilities. Render references solely from the canonical source registry. Clearly distinguish cited sources from any contextual source inventory and report sources not used in synthesis through audit/provenance. Source contributions must be grounded in transmitted content or described as metadata-only context.

Target four to five substantive pages, excluding references; do not promise an exact page count. The current separate cover, double spacing, and page breaks affect pagination. Use a compact title block and consistent readable styles for this planning document; preserve any explicitly required academic formatting profile. Render only after validation and publish atomically. No metadata substitute, fallback abstract, or generic padded document on failure.

Remove obsolete deterministic report fallback helpers after call-site/tests confirm they are unused. Keep deterministic audit generation: an audit is an independently useful artifact, not a substitute proposal.

## Provider configuration

Add a `generate_structured_once(prompt, schema, settings)` contract to the provider layer, returning text/parsed payload, provider/model, finish reason, and usage where available. Select one provider before dispatch; disable SDK automatic retries for this operation. Do not call `generate_with_failover` from the new service. A background attempt may select another configured provider by explicit policy, recorded in telemetry.

Proposed settings: `PROPOSAL_TEMPERATURE=0.2`, `PROPOSAL_TARGET_MIN_WORDS=1200`, `PROPOSAL_TARGET_MAX_WORDS=1600`, `PROPOSAL_HARD_MAX_WORDS=1800`, `PROPOSAL_MAX_OUTPUT_TOKENS=4096`, a model-aware input budget, and a bounded provider timeout. Validate settings at startup. Keep existing model configuration available and support legacy token-setting aliases during migration.

Do not blindly adopt a 2,500-token ceiling: JSON structure plus 1,600 narrative words may exceed it. Benchmark 3,000 and 4,096 against truncation and completion rates. Larger paid bundles may select an explicit expanded profile, but the default proposal quality profile is identical across tiers.

## Queue, delivery, audit, and commercial invariants

Preserve queued/ready/failed internal behavior and current public status normalization (`ready` maps to `completed` in job serialization), job ownership checks, report IDs, status aliases, download URLs, and notification entry points. Preserve paid priority independently of synthesis quality.

Rate limits/quota, transient provider unavailability, and timeouts enter background retry with bounded backoff, jitter, and provider Retry-After where available. Missing credentials and invalid configuration fail without futile retries. Invalid draft/schema/citations fail visibly without automatic content repair. Storage/rendering retries reuse validated JSON rather than paying for another synthesis call.

Persist immutable packet/registry, settings and versions, status, attempts, next retry time, owner, audit links, validated draft, artifact pointer, and sanitized failure reason. Use atomic worker claims/leases and idempotent ready transitions to prevent duplicate synthesis/publication and duplicate notifications. Persist before acknowledging queued status. Keep the current queue response shape; database schema/repository changes must be additive. Test restart recovery and concurrent workers before claiming durability.

Carry `audit_storage_path` and `audit_filename` into queued jobs; the current enqueue call in the cloud generation path does not supply them. Preserve audit download even if synthesis or notification delivery fails. Record notification retry state separately so a notification outage cannot regenerate a ready document.

Keep existing `report_started`, `report_queued`, `report_completed`, `report_failed`, cache redownload events, and experiment variant attribution. Preserve entitlement and usage accounting; retries/cache downloads must not consume another research entitlement. Add regression assertions against current pricing funnel behavior rather than inventing new charging rules.

Bump report cache version. Hash normalized packet content, topic/domain, schema/prompt/template versions, effective output profile, and user preferences that affect content. Preserve user-scoped storage. Do not serve a legacy proposal as v2, or let a pending job switch schema/settings mid-retry.

## Instrumentation and benchmark

Measure `discovery_ms`, `evidence_preparation_ms`, `queue_wait_ms`, `provider_ms`, `validation_ms`, `render_ms`, `storage_ms`, active processing time, and submit-to-download time separately. Track actual provider requests, prompt/output tokens when returned, model/version, truncation, source coverage, cache hit, and retry reason. Missing usage is null, not zero. Do not log source text, emails, or raw provider errors in analytics.

The current `report_queued.wait_time_seconds` is elapsed submit processing time, not actual queue wait. Preserve compatibility while adding correctly named metrics and documenting the old metric's meaning. Accumulate real queue wait across attempts rather than conflating it with provider time.

Create frozen, provenance-backed packets for five topics: AI and university performance; mobile money and loan repayment; digital health adoption; climate adaptation in agriculture; and online learning access. Include direct/contextual/unrelated sources, absent abstracts, duplicate identifiers, and contradictory evidence where actually present. Compare baseline and v2 on the same packets/model, with at least three uncached repetitions per topic and separately recorded warm-cache behavior. Report median/tail latency with sample-size caveats, tokens/cost, success rate, repeated prose, citation traceability, and human-reviewed support. Do not manufacture measured speed gains.

## Implementation sequence and release gates

1. Capture baseline call counts and freeze existing audit/API/pricing fixtures. Introduce additive stage telemetry.
2. Implement packet/schema/prompt/config/validator/renderer/service with mocked provider tests. Fix guessed citation attribution in the new path immediately.
3. Split discovery/audit preparation from optional dossier synthesis. Connect cloud, native, and compatibility proposal entry points to the service behind one feature flag. Keep full literature review behavior covered.
4. Connect durable queue retries to the same service; persist audit links and validated drafts; add atomic transitions and notification idempotency. Version caches.
5. Run fixture tests and live benchmark with configured providers; visually inspect generated Word documents and evaluate factual support. Roll out by feature flag using identical tier quality settings.

Existing regression suites to extend: `test_scribe_quality.py`, `test_publication_quality.py`, `test_cloud_app_api.py`, `test_report_queue.py`, `test_research_evidence_audit.py`, `test_research_exports.py`, `test_pricing_ab_funnel.py`, `test_supabase_entitlements_usage.py`, and `test_dossier_generator.py` for retained consumers.

Required acceptance cases:

- Uncached successful proposal makes exactly one outbound synthesis request, including when discovery was needed; cache hit makes zero.
- Provider failure yields no DOCX; retryable failure returns queued status promptly without synchronous retry/failover.
- Unknown/missing required citations fail; no replacement with S1 or any guessed source.
- Metadata-only records cannot support empirical claims; unrelated PMS evidence is not used to establish AI effects.
- Questions/objectives align by ID; unsupported contradictions and minimum theme/word counts are not forced.
- Sparse valid evidence yields a shorter qualified proposal; zero usable evidence yields a clear result and available audit.
- DOCX contains the six sections, correctly resolved citations and supplied references, with no fallback disclaimer or duplicated generic paragraphs.
- Every original audit row/reason remains available for free and paid users; deduplication/truncation in the packet does not change that set.
- Queued retries survive restart, preserve exact packet/config versions, and do not double-charge, double-publish, or double-notify.
- Render/storage retry uses saved validated JSON and makes zero provider calls.
- Cloud/native/queue proposal paths share the implementation; full_starter entitlement/output behavior remains covered.

Rollback switches the proposal routing flag and cache namespace without altering historical audit records or deleting queued jobs. Version-pinned v2 jobs must continue on the v2 worker or fail explicitly; never reinterpret them as legacy drafts.

## Additional evidence-integrity issue found

`app/agents/orchestrator.py::run_research_loop` contains a no-results branch that fabricates scholarly records. This is distinct from the inspected cloud report path, which uses `ResearchPipeline`. Before enabling any orchestrator entry point for the new service, remove synthetic production source recovery and return an honest no-evidence result. Synthetic records belong only in explicitly marked test fixtures. Confirm reachability during implementation rather than assuming every deployment uses this class.

## Verification of this specification

Findings above come from static inspection of source and call sites. No provider benchmark, production deployment, runtime behavior change, or test execution was performed for this documentation change. Latency targets remain hypotheses until measured.
