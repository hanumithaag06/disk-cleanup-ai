<div align="center">

<br/>

# 💾 Disk Cleanup Recommender

### A Human-in-the-Loop AI System for Smart Disk Management — running entirely on your machine.

<br/>

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Ollama](https://img.shields.io/badge/Ollama-Local%20LLM-black?style=flat-square&logo=ollama&logoColor=white)](https://ollama.ai)
[![Qwen2.5](https://img.shields.io/badge/Qwen2.5-3B-orange?style=flat-square)](https://huggingface.co/Qwen)
[![Discord.py](https://img.shields.io/badge/Discord.py-2.0+-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discordpy.readthedocs.io)
[![ReportLab](https://img.shields.io/badge/ReportLab-PDF-red?style=flat-square)](https://www.reportlab.com)
[![License](https://img.shields.io/badge/License-MIT-22c55e?style=flat-square)](LICENSE)

<br/>

> **The AI recommends. You approve. Nothing is deleted without your confirmation.**

<br/>

[Features](#-features) · [Architecture](#-architecture) · [Discord Workflow](#-discord-workflow) · [Setup](#-setup) · [Configuration](#-configuration)

<br/>

---

</div>

## What is this?

**Disk Cleanup AI** is a tool-using AI agent that scans your disk, classifies files using a local LLM, and surfaces recommendations through an interactive Discord bot — pausing at every destructive step until you explicitly approve.

No cloud. No data leaving your machine. No files touched without your click.

<br/>

---

## Features

<br/>

| | Feature | Description |
|---|---|---|
| 🤖 | **Local LLM Classification** | Qwen2.5:3B via Ollama classifies every file with a decision, confidence score, and plain-English reason |
| 💬 | **Discord Approval Workflow** | Interactive button-driven UI — review, approve, restore, or permanently delete without leaving Discord |
| 🔁 | **Duplicate Detection** | SHA-256 content hashing identifies exact copies before the LLM runs — zero tokens wasted |
| 🧠 | **Smart Caching** | Previously classified files are reused on re-scan — LLM only sees what changed |
| 🗑️ | **Recycle Bin** | Approved files move to `deleted_files/` first — fully reversible before permanent deletion |
| 📊 | **PDF Audit Reports** | Full classification report auto-generated and sent to Discord after every session |
| ⚙️ | **Custom Thresholds** | Set your own inactivity cutoff in days — the LLM adapts its reasoning accordingly |
| 🔒 | **Auth Gate** | Every button interaction is verified against a single authorized Discord user ID |

<br/>

---

## Architecture

<br/>

```
┌─────────────────────────────────────────────────────────────┐
│                        Discord Bot                          │
│                      /start command                         │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    scanner.py                               │
│   Collects: name · path · size · extension · age · category │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│               Duplicate Detection (scanner.py)              │
│                                                             │
│   Group by size → SHA-256 hash → keep newest                │
│   Duplicates: SAFE_DELETE at 99% confidence                 │
│   Bypasses LLM entirely                                     │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│               classifier.py → Ollama (Qwen2.5:3b)           │
│                                                             │
│   Cache check → Batch prompt → LLM response                 │
│   Safety overrides applied post-LLM                         │
│   Cache updated                                             │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                Discord Results Embed                        │
│                                                             │
│   🔁 Duplicates   🗑️ Safe to delete                        │
│   ✅ Keep         ⚠️ Manual review                          │
└───────────────┬─────────────────────────────────────────────┘
                │
                ▼  [ Move to recycle bin ]
┌───────────────────────────────────────┐
│   cleanup.py                          │
│   shutil.move → deleted_files/        │
│   log_deletion() → deletion_log.json  │
└───────────┬───────────────────────────┘
            │
    ┌───────┴──────────┐
    ▼                  ▼
[ Restore ]     [ Permanently delete ]
    │                  │
    └────────┬─────────┘
             ▼
┌────────────────────────┐
│   PDF Report           │
│   Sent to Discord      │
└────────────────────────┘
```

<br/>

---

## LLM Integration

<br/>

### Input — what the model receives per file

```json
{
  "name": "temp_434.tmp",
  "category": "temporary",
  "extension": ".tmp",
  "days_since_last_access": 930
}
```

### Output — what the model returns

```json
{
  "name": "temp_434.tmp",
  "decision": "SAFE_DELETE",
  "confidence": 0.95,
  "reason": "Temporary file not accessed for 930 days."
}
```

### Safety overrides applied after LLM

These rules enforce correctness regardless of what the model says:

| Condition | Result |
|---|---|
| Accessed within threshold | Force → `KEEP` |
| Temporary · past threshold | Force → `SAFE_DELETE` |
| Archive · past 2× threshold | Force → `SAFE_DELETE` |
| Document · past 3× threshold | Force → `SAFE_DELETE` |
| Exact duplicate (any age) | Force → `SAFE_DELETE` · confidence 0.99 |

<br/>

---

## Duplicate Detection

<br/>

```
All scanned files
       │
       ▼
  Group by size          ←  O(n) — different sizes cannot be duplicates
       │
       ▼
  SHA-256 hash           ←  only files sharing a size are hashed
       │
       ▼
  Group by hash
       │
       ▼
  Keep newest            ←  lowest days_since_last_access wins
  Mark rest SAFE_DELETE  ←  99% confidence, reason = "Exact duplicate of X"
       │
       ▼
  Duplicates skip LLM    ←  no tokens spent, no latency added
```

<br/>

---

## Discord Workflow

<br/>

### Step 1 — Start

```
💾 Disk Cleanup Recommender
AI-powered file analysis — choose a mode to begin.

[ 🤖 Agent threshold analysis ]  [ ⚙️ Custom threshold ]  [ ✖️ Cancel ]
```

### Step 2 — Review results

```
🤖 AI analysis complete
16 files analysed · 4 suggested for deletion · 0.01 GB recoverable

🔁 Duplicates — 1 file(s)
  notes_888_copy.txt
  > Exact copy of notes_888.txt

🗑️ Safe to delete — 3 file(s)
  temp_434.tmp
  > Confidence: ██████████ 98%

✅ Keep — 12 file(s)
  archive_646.zip — 95% confidence

[ 🗑️ Move suggested files to recycle bin ]  [ ✖️ Cancel ]
```

### Step 3 — Recycle bin actions

```
🗑️ Files moved to recycle bin
4 files moved · Space freed: 0.01 GB

[ ♻️ Restore files ]  [ 🗑️ Permanently delete ]  [ ✖️ Cancel ]
```

### Step 4 — Permanent delete confirmation

```
⚠️ Confirm permanent deletion
This cannot be undone. You have 60 seconds to confirm.

[ ⚠️ Confirm — delete permanently ]  [ ✖️ Cancel ]
```

After any terminal action the bot generates and sends a **PDF report** directly to the channel.

<br/>

---

## Project Structure

<br/>

```
disk-cleanup-ai/
│
├── main.py                          # Entry point
│
├── src/
│   ├── discord_bot.py               # Discord UI · button views · PDF generation
│   ├── scanner.py                   # Folder scan + duplicate detection (SHA-256)
│   ├── classifier.py                # Ollama LLM classification + cache logic
│   ├── cleanup.py                   # Move · restore · permanent delete
│   ├── cache_manager.py             # Classification cache read / write
│   ├── batch_processor.py           # File batching for LLM calls
│   ├── logger.py                    # JSON deletion audit log
│   ├── models.py                    # FileEntry dataclass
│   ├── config.py                    # Environment variables and constants
│   ├── report_generator.py          # Cleanup report helpers
│   └── summary.py                   # Scan summary utilities
│
├── data/
│   └── classification_cache.json    # LLM result cache
│
├── logs/
│   └── deletion_log.json            # Audit log of all deletions
│
├── reports/                         # Generated PDF reports
├── monitored_folder/                # Folder being monitored
├── deleted_files/                   # Recycle bin
│
├── demo_files_creator.py            # Generates test files with random ages
├── .env
├── requirements.txt
└── README.md
```

<br/>

---

## Setup

<br/>

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.ai) installed locally
- A Discord bot token — [create one here](https://discord.com/developers/applications)

<br/>

### 1. Clone

```bash
git clone https://github.com/your-username/disk-cleanup-ai.git
cd disk-cleanup-ai/disk_clean_up
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Pull the model

```bash
ollama pull qwen2.5:3b
```

### 4. Configure environment

Create `.env` inside `disk_clean_up/`:

```env
DISCORD_BOT_TOKEN=your_bot_token_here
DISCORD_CHANNEL_ID=your_channel_id_here
AUTHORIZED_USER_ID=your_discord_user_id_here

OLLAMA_MODEL=qwen2.5:3b
THRESHOLD_DAYS=180
MIN_FILE_SIZE_KB=100
BATCH_SIZE=50
CACHE_REANALYSIS_DAYS=15
```

### 5. Generate test files (optional)

```bash
python demo_files_creator.py
```

### 6. Start Ollama

```bash
ollama serve
```

### 7. Run

```bash
python main.py
```

Then open Discord and run `/start` in your configured channel.

<br/>

---

## Configuration

<br/>

| Variable | Default | Description |
|---|---|---|
| `THRESHOLD_DAYS` | `180` | Files older than this are SAFE\_DELETE candidates |
| `MIN_FILE_SIZE_KB` | `100` | Files smaller than this are skipped |
| `BATCH_SIZE` | `50` | Files sent to LLM per API call |
| `CACHE_REANALYSIS_DAYS` | `15` | Re-classify if access time shifted by more than N days |
| `OLLAMA_MODEL` | `qwen2.5:3b` | Ollama model used for classification |

<br/>

---

## Safety Design

<br/>

| Mechanism | Implementation |
|---|---|
| Human approval gate | No file moves without an explicit button click |
| Recycle bin first | All deletions go to `deleted_files/` — fully reversible |
| Two-step permanent delete | Separate confirmation with 60-second timeout |
| Mutex buttons | Once one action fires, all others disable immediately |
| LLM safety overrides | Hard rules correct model decisions for edge cases |
| Auth check | Every interaction verifies `AUTHORIZED_USER_ID` |
| Audit log | Every deletion written to `logs/deletion_log.json` |

<br/>

---

## Tech Stack

<br/>

| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| LLM Runtime | Ollama |
| LLM Model | Qwen2.5:3B |
| Bot Framework | discord.py 2.0+ |
| PDF Generation | ReportLab |
| File Operations | pathlib · shutil |
| Caching | JSON (local file) |
| Audit Logging | JSON (local file) |
| Config | python-dotenv |

<br/>

---

## Roadmap

<br/>

- [ ] Per-file approve / reject (not just bulk)
- [ ] Scheduled automatic scans
- [ ] Feedback learning loop — corrections improve future classifications
- [ ] Multi-folder monitoring
- [ ] Slack and Microsoft Teams integration
- [ ] Cloud storage support — S3 · Azure Blob · GCS

<br/>

---

<div align="center">

Built with Python · Powered by Ollama · Controlled through Discord

**MIT License** · Contributions welcome

</div>
