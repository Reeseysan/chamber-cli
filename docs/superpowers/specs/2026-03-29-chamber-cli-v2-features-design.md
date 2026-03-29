# Chamber CLI v0.2 Features — Design Spec

> Depth modes, custom personas, document input, and structured consensus verdicts.

## Overview

Four features that address the primary feedback from v0.1: discussions lack depth, and the user experience needs more control and richer output.

**Codebase:** `~/chamber-cli` (Reeseysan/chamber-cli, private)
**Base version:** v0.1.0 (84 tests passing, 1,140 lines)

## Feature 1: Depth Modes

**Flag:** `--depth brief|standard|deep` (default: `standard`)

**REPL command:** `/depth brief|standard|deep`

**Word limits per depth level, escalating by round:**

| Depth | Round 1 | Round 2 | Round 3+ |
|-------|---------|---------|----------|
| brief | 100 | 150 | 200 |
| standard | 200 | 350 | 500 |
| deep | 400 | 600 | 800 |

Moderator summary length scales similarly: brief=100, standard=200, deep=300 words.

**Implementation:**
- `Config` gains a `depth` field (`"brief"`, `"standard"`, `"deep"`)
- `build_system_prompt()` in `persona.py` takes a `word_limit` parameter and injects the limit into the system prompt
- The orchestrator computes the word limit from `(depth, round_number)` and passes it when building the expert's context for each turn
- The moderator receives the depth level for summary length adjustment
- `CHAMBER_DEPTH` env var support
- `--depth` CLI flag
- `/depth` REPL command updates `config.depth` mid-session

## Feature 2: Custom Personas

**Two input methods, mutually exclusive:**

### CLI flags (role seeds)

```bash
chamber --persona "Maritime Lawyer" --persona "Tax Specialist" "Should we pursue this claim?"
```

The LLM generates full personas (name, expertise, system prompt) but is constrained to the specified roles. The persona generation prompt is modified to accept optional role seeds.

### JSON file (full control)

```bash
chamber --personas my-panel.json "Review this contract"
```

JSON format:
```json
[
  {
    "name": "Elena Voss",
    "role": "Maritime Lawyer",
    "expertise": "International shipping disputes and admiralty law",
    "avatar_emoji": "⚓"
  },
  {
    "name": "Marcus Webb",
    "role": "Tax Specialist",
    "expertise": "Offshore tax structures and compliance"
  }
]
```

- `name` is optional — auto-generated if omitted
- `system_prompt` is optional — built from role/expertise via `build_system_prompt()` if omitted
- `avatar_emoji` is optional — defaults to `"🧑‍💼"`
- `--persona` flags and `--personas` file are mutually exclusive
- If neither is provided, auto-generation works as before
- JSON file is validated: must be an array, each entry must have at least `role`
- JSON file size limit: 1MB

**Implementation:**
- `persona.py` gains `generate_personas_from_roles(roles, provider)` that seeds the LLM prompt with specific roles
- `persona.py` gains `load_personas_from_file(path)` that reads and validates JSON, builds system prompts for entries missing them
- CLI adds `--persona` (multiple) and `--personas` (single path) options
- REPL does not get a command for this — personas are set at discussion start

## Feature 3: Document Input

### Entry points

**CLI flag:**
```bash
chamber --doc contract.pdf "Review this for liability"
chamber --doc contract.pdf --doc amendment.docx "Compare these"
```

**Stdin pipe:**
```bash
cat brief.txt | chamber --one-shot "Analyze this"
```

Stdin detection: if stdin is not a TTY (i.e., data is piped), read it as a document. The piped content is treated as plain text. A topic argument is still required — stdin is the document, the argument is the question about it.

**REPL command:**
```
> /doc contract.pdf
Document loaded: contract.pdf (12,340 words)
```

### File handling

- 15MB hard cap per file, checked before reading
- Total document word cap: 50,000 words across all loaded documents
- If over the word cap, truncate with message: `"Document truncated to first 50,000 words (original: 78,000)"`
- Multiple documents are concatenated with `[DOCUMENT: filename]` headers

### Supported formats

| Format | Dependency | Install |
|--------|-----------|---------|
| `.txt`, `.md`, `.csv` | none | base |
| `.pdf` | `pymupdf` | `chamber-cli[docs]` |
| `.docx` | `python-docx` | `chamber-cli[docs]` |
| `.xlsx` | `openpyxl` | `chamber-cli[docs]` |

If user loads a format requiring `[docs]` extra without it installed:
```
PDF support requires: pip install chamber-cli[docs]
```

### How documents enter the discussion

Document text is injected into the session as a reference context, not repeated in every turn:
- Stored as `session.document_context: str` (new field on Session model)
- Formatted as `"[DOCUMENT: filename]\n\n<content>"` per document
- Prepended to each expert's system prompt: `"{system_prompt}\n\nReference documents:\n{document_context}"`
- The moderator also sees the document context for accurate summaries
- Document content stays in memory only — never written to disk

### New module: `chamber/document.py`

Responsibilities:
- `load_document(path) -> str` — detect format, extract text, enforce size limit
- `load_from_stdin() -> str` — read stdin, enforce size limit
- Format detection by file extension
- Graceful error on missing optional dependencies

## Feature 4: Better Consensus

**Depth-aware verdict format with three prompt templates:**

### Brief consensus

```
CONSENSUS REACHED
Experts agree that [summary]. Key recommendation: [action].
```

### Standard consensus

```
VERDICT: [one-sentence decision]

EXPERT POSITIONS:
  [name] ([role]): [stance] — confidence: [high/medium/low]

KEY ARGUMENTS:
  - [decisive point 1]
  - [decisive point 2]

DISSENTING VIEW:
  [minority position and why it didn't prevail]

RECOMMENDATION: [clear actionable next step]
```

### Deep consensus

```
VERDICT: [one-sentence decision]

EXPERT POSITIONS:
  [each expert: name, stance, confidence 1-10, reasoning summary]

KEY ARGUMENTS THAT SHAPED THE OUTCOME:
  [2-3 decisive reasoning points with detail]

DISSENTING VIEW:
  [what the minority argued and why it didn't prevail]

RECOMMENDATION:
  [clear actionable recommendation with reasoning]

RISK FACTORS:
  [what could change this conclusion]

NEXT STEPS:
  1. [concrete action]
  2. [concrete action]
  3. [concrete action]
```

**Implementation:**
- Three consensus prompt templates in `moderator.py`: `CONSENSUS_BRIEF`, `CONSENSUS_STANDARD`, `CONSENSUS_DEEP`
- `ModeratorAgent.check_consensus()` gains a `depth` parameter
- The orchestrator passes `config.depth` to the moderator
- Still uses `json_completion()` — the structured format lives in the `summary` field
- The REPL/CLI renders the summary as-is (newlines preserved)
- Moderator `summarize_round()` also receives depth for summary length scaling

## Files Changed

| File | Change |
|------|--------|
| `chamber/config.py` | Add `depth` field, `CHAMBER_DEPTH` env var |
| `chamber/models.py` | Add `document_context` field to Session |
| `chamber/persona.py` | Add `generate_personas_from_roles()`, `load_personas_from_file()`, word limit param to `build_system_prompt()` |
| `chamber/expert.py` | Inject document context into system prompt, accept word limit |
| `chamber/moderator.py` | Three consensus templates, depth-aware summary/consensus, document context |
| `chamber/orchestrator.py` | Compute word limits per round, pass depth + document context through |
| `chamber/repl.py` | Add `/depth` and `/doc` commands |
| `chamber/cli.py` | Add `--depth`, `--persona`, `--personas`, `--doc` flags, stdin detection |
| `chamber/document.py` | New module — file loading, format extraction, size enforcement |
| `pyproject.toml` | Add `[docs]` optional dependency group, bump version to 0.2.0 |

## Testing

- Unit tests for `document.py`: text/md/csv loading, size cap, truncation, missing dep error
- Unit tests for depth word limit calculation
- Unit tests for custom persona loading (JSON validation, role seeds)
- Unit tests for three consensus prompt formats
- Update privacy tests: document content must not persist to disk
- Integration: full session with document context
