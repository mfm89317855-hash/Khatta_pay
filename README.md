---
title: Khatta Pay - Voice First AI Ledger
emoji: 🎙️
colorFrom: green
colorTo: emerald
sdk: gradio
sdk_version: 5.25.2
app_file: app.py
pinned: false
license: mit
---

# 🎙️ Khatta Pay (کھاتہ پے)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Ollama](https://img.shields.io/badge/Local%20LLM-Ollama%20(Qwen2.5)-orange.svg)](https://ollama.ai)
[![Whisper STT](https://img.shields.io/badge/Speech%20Recognition-Whisper%20%2F%20faster--whisper-green.svg)](https://github.com/SYSTRAN/faster-whisper)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

> **Offline-first, voice-powered AI ledger designed for retail shopkeepers (*dukandars*) across Pakistan and South Asia.**

Khatta Pay empowers small neighborhood grocery stores, kiryanas, and pharmacies to manage customer credit (*udhaar*), record payments, and track outstanding balances simply by speaking in **Urdu**, **Roman Urdu**, or **English** — with open-weight local AI models, zero cloud lock-in, and deterministic math.

---

## 📌 Table of Contents

- [The Problem](#-the-problem)
- [Our Solution](#-our-solution)
- [Key Features](#-key-features)
- [System Architecture](#-system-architecture)
- [Pakistani Retail Intelligence](#-pakistani-retail-intelligence)
- [Tech Stack](#-tech-stack)
- [Getting Started](#-getting-started)
- [Configuration](#-configuration)
- [Roadmap & Contributing](#-roadmap--contributing)
- [License](#-license)

---

## 🛑 The Problem

Millions of neighborhood retail shops in Pakistan operate on informal credit (*udhaar*), facing daily friction:

1. **Fragile Paper Registers ("Laal Khata")**: Misplaced books, torn pages, tea spills, and calculation disputes with customers.
2. **Cumbersome Mobile Apps**: Typing customer names and rupee amounts with dusty, busy hands during bazaar rush hours is frustrating and slow.
3. **Language Barriers**: Dukandars converse naturally in colloquial Urdu or Roman Urdu, making English-only smartphone forms difficult to adopt.
4. **Cloud Unreliability & Privacy Concerns**: Load shedding, spotty cellular networks, and expensive per-token cloud subscriptions make purely cloud-based AI impractical for grassroots retail.

---

## 💡 Our Solution

**Khatta Pay transforms spoken store interactions into verified ledger entries:**

```text
Shopkeeper speaks:  "Ahmed ko do kilo cheeni udhaar di, 400 rupay"
                         │
                         ▼ (Speech-to-Text)
Transcript:         "احمد کو دو کلو چینی ادھار دی 400 روپے"
                         │
                         ▼ (Ollama Local AI)
Extracted Intent:   ADD_CREDIT | Customer: Ahmed | Amount: Rs. 400 | Item: 2 kg sugar
                         │
                         ▼ (Confirmation Card)
Shopkeeper taps:    [ ✅ Tasdeeq Karein (Confirm & Save) ]
                         │
                         ▼ (ACID SQLite)
Ledger updated:     Ahmed's balance: Rs. 400 (Audited & Saved)
```

---

## ✨ Key Features

- 🎙️ **Voice-First Input**: Speak naturally using microphone or upload recorded audio clips.
- 🇵🇰 **Bilingual & Colloquial Support**: Handles spoken Urdu script, Roman Urdu (`"Ahmed ko 500 udhaar"`), and English.
- 🛡️ **Zero-Hallucination Balance Guarantee**: 
  > **Core Rule:** The LLM only interprets natural language. It NEVER computes balances.
  All financial totals, ledger histories, and debts are computed deterministically in an ACID SQLite database via SQL:
  $$\text{Balance} = \sum(\text{credit}) - \sum(\text{payment})$$
- 🤝 **Confirm-Before-Save Workflow**: The system never commits an entry without Duke confirmation. An interactive verification card allows instant adjustments before saving.
- 💻 **100% Local & Offline Capable**: Runs completely on CPU hardware using `faster-whisper` and local Ollama (`qwen2.5:3b`), keeping sensitive store financial data 100% private.
- ⚡ **Cloud Whisper Support**: Seamlessly switch to OpenAI Whisper API when connected to the internet for maximum transcription speed.

---

## 🏗️ System Architecture

```
                  ┌─────────────────────────────────────────┐
                  │      Shopkeeper Voice / Microphone      │
                  └────────────────────┬────────────────────┘
                                       │
                                       ▼
                  ┌─────────────────────────────────────────┐
                  │        Speech-to-Text (STT)             │
                  │   • OpenAI Whisper API (whisper-1)      │
                  │   • Local faster-whisper (CPU fallback) │
                  └────────────────────┬────────────────────┘
                                       │
                                       ▼
                  ┌─────────────────────────────────────────┐
                  │       Editable Transcript Box           │
                  └────────────────────┬────────────────────┘
                                       │
                 ┌─────────────────────┴─────────────────────┐
                 ▼                                           ▼
      ┌──────────────────────┐                    ┌──────────────────────┐
      │   Intent Classifier  │                    │   Entity Extractor   │
      │  (Local Ollama LLM)  │                    │  (Local Ollama LLM)  │
      └──────────┬───────────┘                    └──────────┬───────────┘
                 │                                           │
                 │              ┌────────────────────────────┘
                 ▼              ▼
      ┌──────────────────────────────────────────────────────┐
      │             Defensive Linguistic Harness             │
      │  • Pakistani Honorifics Stripper (bhai, sahab, sb)   │
      │  • RapidFuzz Customer Name Matcher                   │
      │  • Roman & Urdu Number Normalizer (char sau = 400)   │
      │  • Business Rules & Overpayment Sanity Checks        │
      └─────────────────────────┬────────────────────────────┘
                                │
                                ▼
      ┌──────────────────────────────────────────────────────┐
      │             CONFIRM-BEFORE-SAVE UI CARD              │
      │   [ Customer: Tariq | Rs. 500 | Type: Udhaar ]       │
      │       [ ✅ Confirm & Save ]   [ ❌ Cancel ]          │
      └─────────────────────────┬────────────────────────────┘
                                │ (On Confirmation)
                                ▼
      ┌──────────────────────────────────────────────────────┐
      │                 ACID SQLite Ledger                   │
      │       Transactions • Customers • Audit Trail         │
      └──────────────────────────────────────────────────────┘
```

---

## 🧠 Pakistani Retail Intelligence

Unlike generic LLM wrappers, Khatta Pay features custom heuristics tailored for Pakistani shop environments:

| Module | What It Solves |
| :--- | :--- |
| **`numbers.py`** | Converts Urdu numerals (`۰-۹`) and colloquial Roman Urdu expressions (`"dedh sau"` $\to 150$, `"dhai sau"` $\to 250$, `"hazaar"` $\to 1000$) and cross-validates against LLM outputs. |
| **`resolver.py`** | Strips Pakistani honorifics (`bhai`, `sahab`, `sb`, `chacha`, `baji`, `uncle`) and clitics (`ko`, `ne`) before performing fuzzy token matching. |
| **`validator.py`** | Enforces sanity caps (default 1,000,000 PKR), flags negative amounts, and detects overpayments. |
| **`summary.py`** | Generates instant shop summaries (daily turnover, top debtors, debt recovery reminder drafts). |

---

## 🛠️ Tech Stack

- **Backend / Core**: Python 3.10+, SQLite3
- **Local Speech-to-Text**: `faster-whisper` (CTranslate2, `int8` CPU quantization)
- **Cloud Speech-to-Text**: OpenAI Whisper API (`whisper-1`)
- **Language Intelligence**: [Ollama](https://ollama.ai) (`qwen2.5:3b` or `qwen3.8:27b`)
- **UI Framework**: Gradio / React + Vite
- **Fuzzy Matching**: `rapidfuzz`

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.10 or higher
- [Ollama](https://ollama.ai) installed and running locally
- (Optional) Git

### 2. Installation

```bash
# Clone the repository
git clone https://github.com/mfm89317855-hash/Khatta_pay.git
cd Khatta_pay

# Create and activate virtual environment
python -m venv .venv

# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Pull the Local Model
```bash
ollama run qwen2.5:3b
```

### 4. Configure Environment
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Your `.env` file should look like:
```env
OLLAMA_HOST="http://localhost:11434"
KHATATALK_MODEL="qwen2.5:3b"

# Optional: Add OpenAI API key for cloud Whisper STT
OPENAI_API_KEY="your-openai-api-key-here"
```

### 5. Launch the Application
```bash
python app.py
```
Open your browser and navigate to:
👉 **`http://localhost:7860`**

---

## 🧪 Testing

Run the test suite to ensure all linguistic rules and pipeline guards are working:

```bash
pytest tests/ -v
```

---

## 🗺️ Roadmap & Community Goals

We are building a community-driven movement to digitize local retail. Here is what we're working on:

- [ ] **Spoken Urdu Audio Feedback (TTS)**: Let the app speak answers back to the shopkeeper.
- [ ] **WhatsApp Invoice / Reminder Integration**: One-click sharing of formatted Urdu payment receipts.
- [ ] **Regional Dialect Fine-Tuning**: Benchmark and improve STT for Saraiki, Hindko, and Pashto accents.
- [ ] **Native Mobile App**: Lightweight Flutter / React Native wrapper for low-cost Android phones.
- [ ] **Thermal Receipt Printer Support**: Bluetooth ESC/POS printing for physical receipts.

---

## 🤝 Contributing

We welcome contributions from developers, researchers, and designers of all experience levels!

Please read our [**Contributing Guide (CONTRIBUTING.md)**](CONTRIBUTING.md) to learn how to:
1. Submit bug reports and feature requests.
2. Add new Urdu number idioms or honorific patterns.
3. Open high-quality pull requests.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details. Free for commercial, personal, and educational use.
