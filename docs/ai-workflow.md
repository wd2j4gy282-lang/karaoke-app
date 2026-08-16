# AI-Assisted Software Delivery Workflow

**Purpose:** Define a reusable workflow for using an AI planning/chat surface for planning, requirements, documentation, and review, while using an AI implementation surface (e.g. Claude Code, Cowork, or another repository-capable tool) for repository inspection, implementation, testing, and maintenance.

**Applies to:** Any software project, regardless of industry, technology stack, architecture, deployment model, or product type.

**Status:** Reusable project template
**Recommended path:** `docs/ai-workflow.md`

---

## 1. Operating model

This project uses two complementary AI roles.

### Planning surface (Claude Chat or equivalent)

The planning surface is the primary planning, requirements, product-thinking, documentation, and review partner.

It should primarily:

- understand the project and its goals
- clarify ideas and ambiguous requests
- identify users, stakeholders, and problems
- define desired outcomes
- challenge unnecessary complexity
- distinguish MVP requirements from later enhancements
- analyse product, business, technical, security, privacy, and operational trade-offs
- define user journeys and workflows
- define business rules
- define roles and permissions
- define data requirements
- identify architectural implications
- identify integration requirements
- create feature specifications
- create testable acceptance criteria
- document important decisions
- prepare implementation briefs for the implementation surface
- review implementation output against approved requirements

The planning surface should not assume that a project is:

- a web application
- a mobile application
- a SaaS product
- multi-tenant
- commercial
- customer-facing
- built with a particular language or framework

The planning surface should not begin with implementation code unless explicitly requested.

The planning surface may produce complete Markdown content ready to save into the repository, but must not claim that a file was created, changed, committed, deployed, or implemented unless there is evidence that the action occurred.

### Implementation surface (Claude Code, Cowork, or equivalent)

The implementation surface is the primary repository implementation tool.

It should primarily:

- inspect the repository
- read repository instructions and documentation
- understand the existing codebase
- identify established patterns
- propose implementation plans
- edit code and repository files
- create and update database migrations
- add and update tests
- run development commands
- run formatting, linting, type-checking, tests, and builds
- review diffs
- debug implementation problems
- maintain implementation-linked documentation
- verify implementation against approved specifications

The central principle is:

> The planning surface defines, challenges, and documents what should be built and why. The implementation surface reads the approved repository documentation, implements it, validates it, and keeps implementation-linked documentation current.

---

## 2. Repository documentation model

Use the following structure where useful:

```text
/
├── CLAUDE.md
├── README.md
└── docs/
    ├── README.md
    ├── ai-workflow.md
    ├── product/
    │   ├── vision.md
    │   ├── users.md
    │   ├── business-model.md
    │   ├── terminology.md
    │   └── roadmap.md
    ├── architecture/
    │   ├── overview.md
    │   ├── data-model.md
    │   ├── integrations.md
    │   └── security-and-privacy.md
    ├── features/
    │   ├── README.md
    │   └── feature-name.md
    ├── research/
    │   └── research-topic.md
    ├── decisions/
    │   ├── README.md
    │   └── 001-example-decision.md
    ├── operations/
    │   ├── environments.md
    │   ├── deployment.md
    │   └── incident-response.md
    └── templates/
        ├── feature-template.md
        └── decision-template.md
```

This structure is optional and adaptable.

Create only documents that provide current value. Avoid empty files, duplicated information, and documentation that nobody will maintain.

Project-specific documents may be added when needed, including:

- `accessibility.md`
- `analytics.md`
- `api-contracts.md`
- `compliance.md`
- `content-model.md`
- `disaster-recovery.md`
- `infrastructure.md`
- `machine-learning.md`
- `migration-plan.md`
- `multi-tenancy.md`
- `payments.md`
- `performance.md`

---

## 3. Documentation authority

When repository documentation is available, read `docs/README.md` first.

Unless the project defines a different hierarchy, use this authority order:

1. The user's latest explicit instruction
2. An approved feature specification under `docs/features/`
3. An accepted decision under `docs/decisions/`
4. Architecture documentation under `docs/architecture/`
5. Product documentation under `docs/product/`
6. Existing tests
7. Existing implementation
8. Research documents
9. Informal notes
10. Assumptions

Do not silently resolve meaningful conflicts.

When sources disagree:

- identify the conflict
- explain its practical impact
- identify which source currently has greater authority
- recommend a resolution
- identify which documents should be updated

Important distinctions:

- Research is evidence, not an approved requirement.
- A roadmap item is an intention, not an implementation specification.
- Existing code shows current behaviour, but current behaviour is not automatically desired behaviour.
- Passing tests demonstrate tested behaviour, but do not automatically prove that the intended product requirement is complete or correct.

---

## 4. Purpose of each Markdown file

### `CLAUDE.md`

This is the permanent repository instruction file for the implementation surface.

It should contain stable instructions such as:

- repository structure
- required reading
- coding conventions
- architectural constraints
- verified development commands
- testing expectations
- security requirements
- documentation maintenance rules
- prohibited changes
- definition of done
- completion-report requirements

Do not place detailed feature requirements in `CLAUDE.md`. Put those under `docs/features/`.

Do not turn `CLAUDE.md` into a copy of all repository documentation. Keep it focused on durable implementation instructions and link to authoritative documents.

### `README.md`

Use the root README as a concise introduction to the repository.

It should normally include:

- what the project is
- current status
- main technology stack
- prerequisites
- installation instructions
- how to run the project
- essential development commands
- links to detailed documentation

Do not duplicate the entire product or architecture documentation in the root README.

### `docs/README.md`

Treat this as the documentation index and authority map.

It should explain:

- what each documentation directory contains
- which document is authoritative for each topic
- document status conventions
- links to active documents
- which documents are drafts
- which documents are approved
- which documents are superseded or archived
- each document's context tier and a short "use for" note, where the project uses a context-tier model (see section 25 for the tier model)

Update it whenever documentation is:

- created
- renamed
- moved
- superseded
- archived

### `docs/product/vision.md`

Use this to define:

- product or system purpose
- target users or audience
- main problem being solved
- value proposition
- product principles
- strategic goals
- important boundaries
- explicitly excluded areas

When assessing a feature, explain:

- which problem it solves
- who benefits
- how it supports the vision
- whether it belongs in the current release or MVP
- whether it introduces unnecessary scope
- whether it conflicts with existing principles

Do not rewrite the vision merely to justify a proposed feature.

### `docs/product/users.md`

Use this to define:

- user groups
- personas or roles
- user goals
- user pain points
- technical ability
- accessibility needs
- context of use
- differences between user workflows

For each feature, identify:

- primary user
- secondary users
- administrators or operators affected
- user goal
- relevant permissions
- accessibility considerations

Do not create one generic workflow when different roles need different experiences or permissions.

### `docs/product/business-model.md`

Use this when relevant to document:

- subscriptions
- paid plans
- licensing
- usage-based pricing
- advertising
- commissions
- transactions
- marketplaces
- enterprise contracts
- premium features
- trials
- internal cost allocation
- other commercial rules

Clearly distinguish:

- approved business rules
- working assumptions
- possible ideas
- unresolved commercial questions

For non-commercial projects, omit this document or replace it with a more relevant document such as:

- `funding-model.md`
- `operating-model.md`
- `service-model.md`

### `docs/product/terminology.md`

Use this as the approved glossary.

Use approved terms consistently in:

- specifications
- interface labels
- API discussions
- database discussions
- user stories
- acceptance criteria
- reports
- implementation briefs

When a new term is required:

- define it
- explain how it differs from existing terms
- identify whether the glossary needs updating

Avoid using multiple names for the same concept unless they intentionally represent different meanings.

### `docs/product/roadmap.md`

Use this for prioritisation and sequencing.

It may contain categories such as:

- Now
- Next
- Later
- Not planned

Do not treat roadmap placement as implementation approval.

Before the implementation surface implements a roadmap item, create or update an approved feature specification.

### `docs/architecture/overview.md`

Use this to document:

- applications and services
- frontend and backend boundaries
- databases
- authentication
- hosting
- infrastructure
- storage
- background processing
- integrations
- data flows
- deployment boundaries
- external dependencies

Before recommending a new service, framework, or architectural approach:

- explain the problem being solved
- compare it with the current architecture
- identify costs and trade-offs
- identify migration impact
- identify operational impact
- identify security implications
- determine whether a decision record is required

Do not recommend technology merely because it is popular or familiar.

### `docs/architecture/data-model.md`

Use this when a project has meaningful persistent data.

Document:

- entities
- records
- fields
- relationships
- ownership
- validation
- lifecycle
- retention
- source-of-truth rules
- indexing
- searchability
- migrations
- data imports or exports

Clearly separate:

- confirmed current structures
- proposed changes
- assumptions
- open questions

The implementation surface should update this document when implementation materially changes the conceptual data model.

### `docs/architecture/integrations.md`

Use this for external systems and services.

For each integration, document:

- purpose
- responsibilities
- data exchanged
- authentication method
- event or webhook behaviour
- retry behaviour
- failure handling
- timeout expectations
- idempotency requirements
- rate limits
- privacy implications
- environment-variable names

Never place real secrets, credentials, private keys, or access tokens in documentation.

Do not invent API capabilities. Verify current official documentation when necessary.

### `docs/architecture/security-and-privacy.md`

Use this for features involving:

- authentication
- authorization
- accounts
- personal information
- financial information
- health information
- children's information
- private communications
- uploads
- exports
- analytics
- administration
- audit logs
- secrets
- external integrations

Consider:

- least-privilege access
- trusted authorization boundaries
- data minimisation
- consent
- sensitive-data classification
- logging restrictions
- analytics restrictions
- retention
- deletion
- exports
- secret management
- privileged access
- incident response
- applicable laws and standards

Never place live credentials or real sensitive data in Markdown files.

### `docs/features/*.md`

Treat an approved feature file as the main behavioural specification for that feature.

Each feature file should normally contain:

- status
- product or system area
- primary user
- purpose
- problem
- scope
- out of scope
- assumptions
- dependencies
- user journeys
- functional requirements
- business rules
- permissions
- data requirements
- interface requirements
- error and empty states
- security and privacy
- integrations
- notifications
- analytics
- performance and reliability
- acceptance criteria
- rollout and rollback
- open questions
- related documents
- implementation brief

When discussing an existing feature:

1. Read the complete specification.
2. Check its status.
3. Review its open questions.
4. Review linked decisions.
5. Review linked architecture documents.
6. Separate approved current behaviour from the proposed change.
7. Update the existing specification instead of creating a duplicate.

Do not remove or weaken an approved requirement without explicitly identifying the proposed change.

A specification must be understandable without relying on planning-chat history.

### `docs/research/*.md`

Use research as supporting evidence.

Research may include:

- market research
- competitor findings
- user feedback
- usability findings
- technology investigation
- performance investigation
- API research
- data-source research
- proof-of-concept findings
- operational observations

Separate:

- verified facts
- observations
- hypotheses
- recommendations
- approved decisions

Do not transform a competitor feature, technical possibility, or user suggestion into an approved requirement without evaluation.

The implementation surface must not implement research ideas unless they are included in an approved specification or explicit task.

### `docs/decisions/*.md`

Use decision records for important product, architecture, security, data, or operational decisions.

A decision record should include:

- status
- context
- decision
- alternatives considered
- consequences
- related files or documents

Create a decision record when the decision is:

- difficult to reverse
- system-wide
- security-sensitive
- operationally significant
- expensive to change later
- likely to affect future development

Do not create a decision record for every minor coding choice.

Treat accepted decisions as constraints unless explicitly revisited.

### `docs/operations/*.md`

Use these documents for:

- environments
- configuration
- deployments
- database migrations
- backups
- monitoring
- alerting
- recovery
- rollbacks
- production support
- incident response
- release processes
- scheduled tasks
- operational ownership

For high-risk features, include rollout and rollback requirements.

The implementation surface should update these documents when operational behaviour changes.

### `docs/templates/feature-template.md`

Use this when creating feature specifications.

Do not omit relevant sections simply because they have not yet been discussed.

Mark sections as:

- not applicable
- assumption
- open question
- to be confirmed

where appropriate.

### `docs/templates/decision-template.md`

Use this for new decision records.

Document the reason and context for the decision, not only the final technology or approach selected.

---

## 5. Feature-planning workflow for the planning surface

When a feature or change is proposed, use the following stages.

### Stage 1: Understand

Identify:

- affected product, service, or system
- primary user
- secondary users
- user or business problem
- desired outcome
- related existing functionality
- relevant documentation
- assumptions
- unresolved decisions
- likely dependencies
- current constraints

Do not begin by writing implementation code.

### Stage 2: Challenge

Assess:

- whether the feature is necessary now
- whether a simpler solution exists
- whether it duplicates existing capability
- whether it belongs in the current release
- technical complexity
- operational burden
- maintenance burden
- security risk
- privacy risk
- architectural impact
- integration impact
- migration impact
- performance implications
- accessibility implications
- edge cases
- failure states

Challenge unnecessary complexity respectfully.

Do not accept vague goals without translating them into observable outcomes.

### Stage 3: Define

Produce clear:

- purpose
- scope
- out-of-scope boundaries
- user journeys
- functional requirements
- business rules
- permission rules
- data requirements
- validation rules
- interface requirements
- loading states
- empty states
- error states
- success states
- accessibility requirements
- security requirements
- privacy requirements
- integration behaviour
- analytics requirements
- performance requirements
- acceptance criteria
- open questions

Avoid vague words such as:

- easy
- intuitive
- modern
- fast
- scalable
- secure
- flexible
- seamless
- user-friendly
- robust

Translate them into testable requirements.

### Stage 4: Document

When the feature is approved, create a complete Markdown specification suitable for:

```text
docs/features/<lowercase-kebab-case-feature-name>.md
```

Use stable requirement identifiers where useful:

- `FR-01` for functional requirements
- `BR-01` for business rules
- `PERM-01` for permissions
- `DATA-01` for data requirements
- `SEC-01` for security requirements
- `PRIV-01` for privacy requirements
- `INT-01` for integration requirements
- `OPS-01` for operational requirements
- `PERF-01` for performance requirements
- `AC-01` for acceptance criteria

Include repository-relative links to related documentation.

The specification must stand alone without requiring the implementation surface to read the planning conversation.

### Stage 5: Approval

Use these default statuses unless the project defines others:

- Idea
- Researching
- Draft
- Ready for review
- Approved for implementation
- In implementation
- Implemented
- Superseded
- Archived

Only mark a specification `Approved for implementation` after its scope and requirements are clearly approved.

Do not mark a feature `Implemented` solely because the implementation surface reports completion. Check implementation against repository evidence, tests, and acceptance criteria where possible.

### Stage 6: Handoff to the implementation surface

Every approved feature specification should end with a section named:

```text
Implementation brief
```

That section should include:

- exact documents to read
- implementation objective
- approved scope
- prohibited changes
- relevant requirements
- required validation
- migration considerations
- security considerations
- integration considerations
- operational considerations
- documentation that may need updating
- unresolved questions the implementation surface must not guess

Also provide a ready-to-paste implementation-surface prompt naming the exact feature file.

---

## 6. Standard feature specification template

Use this structure unless the project has a better established template:

```markdown
# [Feature name]

**Status:** Draft
**System or product area:**
**Primary user:**
**Owner:**
**Last updated:** YYYY-MM-DD
**Related documents:**

## 1. Purpose

## 2. Problem

## 3. Users and roles

## 4. Scope

## 5. Out of scope

## 6. Assumptions

## 7. Dependencies

## 8. User journeys or workflows

## 9. Functional requirements

## 10. Business rules

## 11. Permissions and authorization

## 12. Data requirements

## 13. Interface or API requirements

## 14. Notifications and communications

## 15. Integrations

## 16. Security and privacy

## 17. Analytics and measurement

## 18. Performance and reliability

## 19. Acceptance criteria

## 20. Rollout and rollback

## 21. Open questions

## 22. Related decisions

## 23. Implementation brief
```

Acceptance criteria should cover relevant cases such as:

- normal operation
- invalid input
- empty data
- loading behaviour
- unauthorized access
- forbidden access
- external-service failure
- partial failure
- duplicate requests
- concurrency
- responsive behaviour
- accessibility
- performance
- migration impact
- rollback behaviour

Use Given/When/Then wording when it improves clarity.

Do not force irrelevant sections onto a project. Mark them not applicable or omit them when there is a clear project-specific reason.

---

## 7. Documentation maintenance rules

When new information appears, determine which existing document should be updated.

Prefer:

- updating the authoritative document
- adding repository-relative links
- keeping each decision in one authoritative place
- referencing that decision elsewhere
- updating an existing feature specification rather than creating a duplicate

Avoid:

- duplicated requirements
- contradictory summaries
- multiple documents claiming authority
- copying the full architecture into every feature specification
- storing temporary brainstorming as approved documentation
- rewriting product requirements merely to match incomplete implementation

When a document changes materially, consider updating:

- status
- last-updated date
- related links
- `docs/README.md`
- related feature documents
- related architecture documents
- related decision records
- related operations documents

Clearly distinguish:

- confirmed facts
- approved decisions
- proposals
- assumptions
- open questions

---

## 8. Expectations for `CLAUDE.md`

The top-level `CLAUDE.md` should instruct the implementation surface to:

- read `docs/README.md`
- read `docs/ai-workflow.md`
- read the relevant feature specification
- read linked architecture and decision documents
- inspect existing code before editing
- follow established repository patterns
- avoid unrelated refactoring
- preserve approved out-of-scope boundaries
- verify development commands rather than inventing them
- run formatting, linting, type-checking, tests, and builds
- update affected documentation
- report deviations from approved specifications
- report assumptions
- report unresolved risks
- avoid exposing secrets
- enforce authorization at trusted boundaries
- review migrations carefully
- review the final diff
- provide a clear completion report
- report project-context impact (see section 25)

The planning surface should help create and maintain these instructions but should not assume the implementation surface followed them without evidence.

---

## 9. Standard implementation prompt

Use this prompt after a feature specification is approved and saved in the repository:

```text
Implement the approved feature defined in:

docs/features/[FEATURE-FILE].md

Read before editing:

- CLAUDE.md
- docs/README.md
- docs/ai-workflow.md
- the complete feature specification
- every product, architecture, and decision document linked by that specification
- the relevant existing code, configuration, schema, and tests

Before implementation:

1. Confirm that the specification status is Approved for implementation.
2. Summarize the intended behaviour.
3. Map each acceptance criterion to likely code changes and tests.
4. Identify conflicts between the specification, documentation, and current code.
5. Identify data, migration, security, privacy, integration, performance, and operational impacts.
6. Present a concise implementation plan.
7. Do not resolve documented open questions by guessing.

During implementation:

- remain within the approved scope
- preserve out-of-scope boundaries
- follow established repository conventions
- avoid unrelated refactoring
- add or update tests with the implementation
- handle relevant normal, loading, empty, invalid, unauthorized, and failure states
- enforce authorization at a trusted boundary
- update affected documentation according to CLAUDE.md

Before completion:

- run the verified formatting, linting, type-checking, testing, and build commands
- review the final diff critically
- check every acceptance criterion
- check for secret exposure
- review database changes for existing-data and rollback risks
- verify permissions and security boundaries
- confirm that documentation agrees with the implementation

Completion report:

- implementation summary
- acceptance-criteria results
- files changed
- migrations created or changed
- tests added or changed
- commands run and outcomes
- documentation updated
- deviations from the approved specification
- assumptions
- unresolved risks
- manual validation still required
- project-context impact (see section 25)
```

Adapt this prompt to the actual repository. Do not require irrelevant activities merely because they appear in the generic template.

---

## 10. Reviewing implementation output

When reviewing an implementation summary, diff, pull request, or changed files, compare it with:

- approved feature specification
- acceptance criteria
- product goals
- user needs
- business rules
- permissions
- security requirements
- privacy requirements
- data-model documentation
- architecture decisions
- integration requirements
- operational requirements

Do not merely repeat the implementation surface's summary.

Look for:

- missing requirements
- incorrect assumptions
- unnecessary complexity
- scope creep
- missing error states
- missing authorization
- unsafe migrations
- inadequate tests
- stale documentation
- inaccessible interface behaviour
- performance regressions
- security regressions
- mismatch between intended behaviour and implementation

Clearly identify:

- what appears complete
- what is incomplete
- what cannot be verified
- what should be corrected
- what should be tested manually
- whether the feature appears ready for release

Base the review on evidence, not confidence or writing quality.

---

## 11. Security and privacy expectations

For sensitive functionality:

- deny access by default where appropriate
- enforce authorization on the server, service, or database boundary
- do not rely solely on hidden interface elements
- minimise sensitive data
- avoid sensitive data in logs
- avoid sensitive data in analytics
- avoid real personal information in tests
- avoid real credentials in documentation
- use environment variables or an approved secret manager
- preserve auditability for privileged actions
- test unauthorized and forbidden access

Use requirements appropriate to the project's actual risk level.

Do not invent legal or compliance requirements. Identify when specialist legal, security, or compliance review may be required.

---

## 12. External integration expectations

For external integrations:

- define which system owns each responsibility
- verify the current official API contract
- define authentication and authorization
- consider timeouts and retries
- consider rate limits
- consider duplicate and out-of-order events
- use idempotent handling where appropriate
- distinguish temporary from permanent failures
- avoid exposing provider secrets to clients
- identify monitoring and alerting needs
- document configuration names without secret values
- test failure behaviour
- define reconciliation where systems may become inconsistent

Do not assume a browser redirect, client response, or local state is authoritative when the external provider supplies a trusted server-side confirmation mechanism.

---

## 13. Database and migration expectations

For changes involving persistent data:

- identify affected entities
- identify existing-data impact
- identify migration and backfill requirements
- consider deployment ordering
- consider compatibility during rollout
- consider rollback
- review indexes and constraints
- assess performance implications
- avoid destructive changes without explicit approval
- avoid silently discarding data
- update data-model documentation when the conceptual model changes

Do not require database-specific work when the project does not use a database.

---

## 14. User-interface expectations

For user-facing features, consider where relevant:

- desktop and mobile behaviour
- keyboard navigation
- accessible labels
- focus management
- loading states
- empty states
- validation states
- error states
- success feedback
- destructive-action confirmation
- responsive layout
- localization
- date, time, number, and currency formats
- slow or unreliable network conditions

Follow the repository's existing design system and component patterns unless a change is explicitly approved.

---

## 15. API and service expectations

For API or service changes, consider where relevant:

- request and response contracts
- authentication
- authorization
- validation
- error formats
- status codes
- pagination
- filtering
- sorting
- versioning
- rate limiting
- retries
- idempotency
- backward compatibility
- observability
- data privacy
- documentation
- contract tests

Do not introduce breaking changes without making them explicit.

---

## 16. Performance and reliability expectations

When performance or reliability matters, define measurable expectations such as:

- response-time targets
- throughput
- memory constraints
- payload limits
- startup time
- availability
- retry limits
- timeout behaviour
- recovery behaviour
- graceful degradation

Do not use "fast," "scalable," or "reliable" as sufficient requirements.

Do not optimise prematurely without identifying a real constraint or measurement.

---

## 17. Dependencies and refactoring

Do not recommend or add a dependency when the existing stack reasonably solves the problem.

Before recommending a new dependency, consider:

- purpose
- existing alternatives
- maintenance status
- security history
- licensing
- runtime impact
- bundle impact
- operational impact
- exit or replacement cost

Do not combine feature implementation with a broad refactor unless the refactor is necessary and explicitly included in scope.

Prefer bounded, reviewable changes.

---

## 18. Standard delivery workflow

Use this workflow for each meaningful feature:

```text
1. Discuss the idea on the planning surface.
2. The planning surface reads the relevant Markdown project sources.
3. The planning surface clarifies the user or business problem.
4. The planning surface identifies constraints, dependencies, and risks.
5. The planning surface challenges unnecessary scope.
6. The planning surface creates or updates the feature specification.
7. The specification is reviewed and approved.
8. The approved file is saved under docs/features/ in the repository.
9. The specification is committed to version control.
10. The implementation surface is instructed to read CLAUDE.md and the feature file.
11. The implementation surface inspects, plans, implements, tests, and updates documentation.
12. The implementation diff and validation results are reviewed.
13. The planning surface checks the result against the specification and acceptance criteria.
14. Remaining defects or deviations are returned to the implementation surface as bounded tasks.
```

The repository version of each document is authoritative for the implementation surface.

Any copy of a document living in an AI planning tool is planning context and may become stale unless refreshed or connected to the latest repository content.

Use statuses, last-updated dates, and repository-relative links to reduce confusion.

---

## 19. Response requirements for the planning surface

When answering product, planning, or feature questions:

- identify relevant documents by path
- separate confirmed information from proposals
- identify assumptions
- identify open questions
- explain conflicts
- recommend a preferred approach
- avoid treating every option as equally good
- state which documents should be created or updated
- preserve prior approved decisions unless there is a clear reason to revisit them

When producing a finished feature specification or document:

- provide complete Markdown
- make it understandable without conversation history
- identify its intended repository path
- include a status
- include relevant links
- include an implementation brief when approved

When preparing a handoff:

- provide a complete ready-to-paste implementation-surface prompt
- name the exact feature file
- identify the documents the implementation surface must read
- state what the implementation surface must not guess

When reviewing implementation:

- base the review on evidence
- distinguish confirmed issues from possible risks
- identify what cannot be verified
- map findings back to requirements and acceptance criteria

---

*Sections 1–19 above are the original generic core. Sections 20–25 below extend*
*it with patterns refined through real project use: surface separation, view*
*synchronisation, authorship conventions, handover discipline, and context*
*orchestration. They remain generic and reusable. A specific project's own*
*specifics — naming, tooling choices, domain playbooks that have actually*
*emerged — belong in a project-specific addendum starting at section 26*
*onward, rather than edited into sections 1–25.*

---

## 20. Operating surfaces

A project typically uses several distinct surfaces, each with one job:

- **Planning surface** — brainstorm, research, pressure-test, lock decisions.
  Nothing is real until it is written into a repository document.
- **Repository documentation** — the source of truth. Wins over chat history
  and over any supplementary view, always.
- **Implementation surface** (e.g. Claude Code, Cowork, or another
  repository-capable tool) — implementation. Reads the docs before any task,
  holds commits locally pending explicit go-ahead unless the project defines
  otherwise, and never pushes without it.
- **Data files** (if the project has externally-sourced data) — sourced and
  verified on the planning surface, never interpreted or edited by the
  implementation surface. Its role there is mechanical: place, import,
  verify — never judge content. Hand over as file downloads rather than
  pasted text once volume makes prose handovers slow or error-prone.
- **Supplementary visual or interactive view** (optional) — a rendering of
  canonical documents for at-a-glance status (e.g. a generated roadmap
  board, a dashboard). A view, not a source of truth. See section 21.

Adapt this list to the project. Not every project needs a data-files surface
or a supplementary view.

## 21. View synchronisation

If a project uses a supplementary visual or interactive view generated from
canonical documents:

The planning surface has no live visibility into the view once it is
generated and opened elsewhere (e.g. in a browser). It only knows what it
baked in when it last generated the view.

Two distinct sync directions follow:

- **Refresh the view from the docs** — safe to do any time, since canonical
  documents are readable. But it resets the view to a clean baseline:
  anything changed only in the view since the last refresh is lost, because
  the planning surface never saw it.
- **Bring live view-state back to the planning surface** — only via an
  explicit export mechanism (e.g. a snapshot or file), brought back into the
  conversation. This is also how view state survives moving to a new
  planning session.

**Rule of thumb: export before requesting a refresh, if there are changes
worth keeping.**

**Treat an export as a discovery mechanism, not an update mechanism.** If an
export reveals a real change — a status update, a new note — write that
change into the actual canonical document it was generated from. The
canonical document is what changed; the view is only how the change was
noticed. Do not treat the view itself as newly canonical just because it
revealed current information.

Verify a view still renders or parses correctly after any multi-part edit to
it — a small formatting error can break the whole thing silently.

## 22. Who authors what

Most documents are drafted on the planning surface and applied via a scoped
handover to the implementation surface. Two categories are naturally
different:

- **Implementation-linked history** (e.g. a progress log) — the
  implementation surface is the natural author. It knows what it built,
  when, and what the diff contained; the planning surface was not present
  for those details.
- **Lessons-learned / retrospective records** — authored by whichever
  surface hit the problem. Append in the same unit of work as the fix, not
  deferred to later.

## 23. Domain playbooks — do not create speculatively

A domain playbook is a mandatory procedure for a recurring, quality-critical
area, typically with its own domain-specific "do not repeat" log.

**Create one only once such a domain has actually emerged from real
experience**, not in advance. Writing one speculatively means guessing at a
standard instead of encoding a learned one.

## 24. Handover types

- **Doc-only handovers** (create or edit documentation only, no code/schema/
  configuration changes) are safe to run immediately.
- **Build handovers** (any code, schema, or configuration change) carry the
  full review discipline defined in `CLAUDE.md`.
- **Never mix the two in one handover** — mixing them means a routine doc
  update cannot be distinguished from a risky code change in the diff.

A build handover still updates the affected documentation as part of the
same unit of work. That is not a separate doc-only handover deferred to
later. A build is not done until the docs reflect it.

## 25. Context orchestration and tiers

Distinguish documentation by how it's loaded into chat/task context, not
just by directory. Four layers are involved:

- **Project instructions** — durable behavioural rules for the planning
  surface itself (e.g. "propose a decision before marking it Decided," "cite
  decision IDs"). Kept short, in the planning tool's instructions field —
  not an uploaded file.
- **Permanent project knowledge (Tier 1)** — compact orientation, synced
  live from the repository rather than manually re-uploaded, where the
  planning tool supports it.
- **Repository documentation** — the complete, canonical source of truth.
  Always authoritative; anything copied into a planning surface is a view of
  it and may go stale.
- **Task context (Tier 2 / Tier 3)** — the small, specific subset one
  dispatched task actually needs.

**Tier 1 — compact, durable, portfolio-level.** Typically:

- the documentation index / authority map
- this workflow document
- product or system vision
- current roadmap or priority snapshot
- the decisions log
- a high-level architecture overview

Keep Tier 1 small enough to stay reliably fully in context rather than
depending on retrieval — portfolio-level reasoning needs the complete
picture, not a fragment of it.

**Tier 2 — active task context.** Loaded only for the specific task that
needs it, never added to the planning surface's permanent knowledge:

- the active feature specification
- detailed architecture documents (data model, integrations,
  security-and-privacy) — kept dispatched-only, not permanent orientation,
  since they grow field-by-field and mostly serve technical planning and
  implementation, not portfolio-level reasoning
- domain playbooks and operational/environment documents relevant to the
  task at hand

**Tier 3 — evidence and history.** Used only for investigation or audit,
never as standing authority:

- research documents
- progress logs, lessons-learned
- superseded specifications, archived documents

Tier 3 evidence must not silently override Tier 1 or Tier 2 authority —
research is evidence, not an approved requirement.

**Do not create a duplicate master-context document.** Avoid a large
all-in-one context file that copies the vision, roadmap, architecture, and
decisions into one place. It becomes stale, contradictory, and a second
source of truth to maintain. A short orientation summary is fine only if it
stays navigational — pointing to authoritative sources rather than
restating them.

**Who creates Tier 2 documents, and when.** The planning-surface role
authors them, same as everything else — but in a dedicated dispatched task
seeded with only what that task needs, not in the ongoing Tier 1
conversation. The Tier 1 conversation authorizes the work and later
receives only a short status summary back, not the document's full content.
The same "don't create speculatively" rule as domain playbooks (section 23)
applies.

**The planning surface is a role, not one continuous thread.** Continuity
lives in the Tier 1 documents and the planning tool's own project memory,
not in an unbroken conversation. Rotate to a new conversation when a thread
gets long or a phase closes — a new conversation in the same project
inherits Tier 1 knowledge automatically, so nothing is lost by rotating.

**Keeping project knowledge current.** Refresh or resync Tier 1 project
knowledge when a change touches vision, roadmap sequencing, the
architecture overview, or an accepted decision — not for
implementation-only changes, formatting, or routine log entries.
Regardless of how current project knowledge looks, don't treat it as a live
source for facts like what's actually deployed, current database contents,
or whether a migration ran — verify those directly against the repository
or the live system when a decision depends on them.