# Chamber CLI

Private expert panels in your terminal.

Chamber CLI runs multi-agent AI discussions using local or remote models. Local-first by default — no cloud, no accounts, no telemetry. Remote providers available when you need them.

## Install

```bash
pipx install chamber-cli
```

Or with pip:

```bash
pip install chamber-cli
```

## Prerequisites

**Local mode** (default): Install [Ollama](https://ollama.com) and pull a model:

```bash
ollama pull llama3.1
```

**Remote mode**: Set an API key in your environment:

```bash
export CHAMBER_OPENAI_API_KEY="sk-..."       # OpenAI
export CHAMBER_ANTHROPIC_API_KEY="sk-ant-..."  # Anthropic
export CHAMBER_OPENROUTER_API_KEY="sk-or-..."  # OpenRouter
```

## Usage

```bash
# Interactive REPL (default)
chamber

# Start with a topic
chamber "What are the legal risks of publishing leaked documents?"

# One-shot mode (no REPL)
chamber "Compare Signal vs Session for whistleblowers" --one-shot

# Custom settings
chamber --model mistral --agents 4 --rounds 5
```

### Templates

Skip persona generation — use prebuilt expert panels:

```bash
# List available templates
chamber --list-templates

# Legal review with a document
chamber --template legal-review --doc contract.pdf "Review this contract"

# Code review
chamber --template code-review --doc diff.patch "Review these changes"

# Threat modeling
chamber --template threat-model "Analyze my SaaS app's attack surface"

# Red team an idea
chamber --template red-team "We should rewrite the backend in Rust"

# Structured debate
chamber --template debate "Is remote work better than in-office?"
```

### JSON Output

Structured output for scripting and CI/CD pipelines:

```bash
# Get JSON output
chamber "topic" --one-shot --format json

# Pipe to jq
chamber "topic" --one-shot --format json | jq .consensus

# Use in scripts
result=$(chamber "topic" --one-shot --format json)
echo "$result" | jq -r '.consensus.summary'
```

### Git-Aware Mode

Auto-ingest git diffs for code review:

```bash
# Review unstaged changes
chamber --git-diff --one-shot

# Review staged changes
chamber --git-staged --one-shot

# Review a PR (uses gh CLI if available)
chamber --git-pr 123 --one-shot

# Combine with JSON output
chamber --git-diff --one-shot --format json | jq .consensus.summary
```

### Session Resume

Continue a previously exported discussion:

```bash
# Export a session
chamber "topic"
> /save discussion.md

# Resume it later
chamber --resume discussion.md

# Resume in one-shot mode
chamber --resume discussion.md --one-shot

# Resume encrypted exports (prompts for passphrase)
chamber --resume discussion.enc
```

### Remote Providers

Use cloud models when local isn't enough:

```bash
# OpenAI
chamber --provider openai --model gpt-4o "topic"

# Anthropic
chamber --provider anthropic "topic"

# OpenRouter (access hundreds of models)
chamber --provider openrouter --model anthropic/claude-sonnet-4-20250514 "topic"

# With Tor proxy
chamber --provider openai --proxy socks5://localhost:9050 "topic"
```

### MCP Server Mode

Expose Chamber as an MCP server for Claude Code, Cursor, and other MCP clients:

```bash
# Install MCP support
pip install chamber-cli[mcp]

# Start the server
chamber --serve
```

Configure in your MCP client (e.g., Claude Code `config.json`):

```json
{
  "mcpServers": {
    "chamber": {
      "command": "chamber",
      "args": ["--serve"]
    }
  }
}
```

### Shell Completions

```bash
# Install tab completions for your shell
chamber --install-completions
```

## REPL Commands

| Command | Action |
|---------|--------|
| `/follow <text>` | Inject a follow-up into the next round |
| `/rounds <n>` | Set max rounds (1-5) |
| `/depth <level>` | Set depth: brief, standard, deep |
| `/doc <path>` | Load a document into the session |
| `/agents` | List current panel |
| `/export` | Export as markdown to stdout |
| `/export --encrypt` | Export with passphrase encryption |
| `/save <path>` | Save export to file |
| `/provider [name]` | Switch provider or show current |
| `/model [name]` | Switch model or show current |
| `/new` | Clear session, new topic |
| `/status` | Show provider, model, stats |
| `/update` | Check for updates |
| `/help` | Show help |
| `/quit` | Exit |

## Providers

| Provider | Type | Default Model |
|----------|------|--------------|
| Ollama | Local | llama3.1 |
| LM Studio | Local | (auto-detect) |
| OpenAI | Remote | gpt-4o |
| Anthropic | Remote | claude-sonnet-4-20250514 |
| OpenRouter | Remote | llama-3.1-8b-instruct |

## Privacy & Security

### What Chamber CLI does

- **Zero telemetry** — no analytics, no tracking, no phone-home
- **Zero disk writes** — sessions exist only in memory, destroyed on exit
- **No config files** — settings via flags and environment variables only
- **No shell history** — REPL input is not written to any history file
- **Encrypted export** — AES-256-GCM with passphrase when you choose to save
- **Minimal dependencies** — small, auditable dependency tree
- **Open source** — read every line of code yourself

### What Chamber CLI does NOT do

- No account system
- No API key storage
- No crash reporting
- No auto-updates
- No fingerprinting

### Threat Model

Chamber CLI is designed to keep your AI discussions private from third parties. Here is what it protects against and what it does not:

**Protected:**
- Third-party data collection (no network calls in local mode)
- Persistent data leakage (nothing written to disk by default)
- Session recovery after exit (memory is freed)

**Not protected:**
- A compromised operating system or keylogger
- Memory forensics on a running machine
- Shell history in one-shot mode (topics appear in shell history — use REPL mode or pipe from stdin: `echo "topic" | chamber --one-shot`)

**Remote mode:**
- Remote providers send data over the network — Chamber will warn you
- Use `--proxy socks5://localhost:9050` for Tor routing
- Verify the provider's privacy policy independently

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CHAMBER_PROVIDER` | `ollama` | Provider name |
| `CHAMBER_MODEL` | (provider default) | Model name |
| `CHAMBER_AGENTS` | `3` | Number of agents |
| `CHAMBER_ROUNDS` | `3` | Max rounds |
| `CHAMBER_OLLAMA_URL` | `http://localhost:11434` | Ollama server URL |
| `CHAMBER_LMSTUDIO_URL` | `http://localhost:1234` | LM Studio server URL |
| `CHAMBER_PROXY` | (none) | SOCKS5 proxy URL |
| `CHAMBER_OPENAI_API_KEY` | (none) | OpenAI API key |
| `CHAMBER_ANTHROPIC_API_KEY` | (none) | Anthropic API key |
| `CHAMBER_OPENROUTER_API_KEY` | (none) | OpenRouter API key |

## Docker

```bash
docker run --rm -it --network host ghcr.io/reeseysan/chamber-cli
```

## License

MIT
