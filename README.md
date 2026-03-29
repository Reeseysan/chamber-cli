# Chamber CLI

Private expert panels in your terminal.

Chamber CLI runs multi-agent AI discussions entirely on your machine using local models. No cloud, no accounts, no telemetry.

## Install

```bash
pipx install chamber-cli
```

Or with pip:

```bash
pip install chamber-cli
```

## Prerequisites

Install [Ollama](https://ollama.com) and pull a model:

```bash
ollama pull llama3.1
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

## REPL Commands

| Command | Action |
|---------|--------|
| `/follow <text>` | Inject a follow-up into the next round |
| `/rounds <n>` | Set max rounds (1-5) |
| `/agents` | List current panel |
| `/export` | Export as markdown to stdout |
| `/export --encrypt` | Export with passphrase encryption |
| `/save <path>` | Save export to file |
| `/new` | Clear session, new topic |
| `/status` | Show provider, model, stats |
| `/quit` | Exit |

## Providers

| Provider | Type | Default Port |
|----------|------|-------------|
| Ollama | Local | localhost:11434 |
| LM Studio | Local | localhost:1234 |

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

**Remote mode (future):**
- Remote providers send data over the network
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

## Docker

```bash
docker run --rm -it --network host ghcr.io/reeseysan/chamber-cli
```

## License

MIT
