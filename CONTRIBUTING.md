# Contributing to Khatta Pay (کھاتہ پے)

First off, thank you for considering contributing to **Khatta Pay**! 🎉 

Khatta Pay is an open-source, voice-first AI ledger built to empower millions of neighborhood retail shopkeepers (*dukandars*) with automated, offline-first accounting in Urdu, Roman Urdu, and English. 

Contributions from developers, linguistic experts, and designers around the world make this project possible.

---

## 🌟 Ways to Contribute

There are many ways you can help improve Khatta Pay:
- **Linguistic Models & Prompt Engineering**: Enhance Roman Urdu and colloquial regional Urdu intent classification.
- **Speech-to-Text (STT)**: Add support for fine-tuned regional dialect speech models (e.g., Saraiki, Pashto, Punjabi accents).
- **Frontend / UI / UX**: Enhance Gradio UI, mobile responsiveness, or the React/Vite web interface.
- **TTS (Text-to-Speech)**: Add natural Urdu spoken voice feedback for hands-free shopkeeper interaction.
- **Bug Fixes & Tests**: Write unit tests for linguistic edge cases, number normalization, and SQL edge cases.
- **Documentation**: Improve setup guides, translate documentation, or add video demos.

---

## 🛠️ Development Setup

### 1. Clone the Repository
```bash
git clone https://github.com/mfm89317855-hash/Khatta_pay.git
cd Khatta_pay
```

### 2. Set Up Virtual Environment
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Edit `.env` to configure your local Ollama endpoint (`http://localhost:11434`) and optional OpenAI Whisper API key.

### 5. Run the Local Model
Ensure you have [Ollama](https://ollama.ai) installed and pull the lightweight model:
```bash
ollama run qwen2.5:3b
```

### 6. Launch the App
```bash
python app.py
```
Open [http://localhost:7860](http://localhost:7860) in your web browser.

---

## 🧪 Running Tests

Ensure all tests pass before opening a Pull Request:
```bash
pytest tests/
```

---

## 🌿 Contribution Workflow

1. **Fork the Repository** on GitHub.
2. **Create a Feature Branch**:
   ```bash
   git checkout -b feature/amazing-feature
   ```
3. **Commit your Changes**:
   ```bash
   git commit -m "feat: add support for regional colloquial numbers"
   ```
4. **Push to Your Branch**:
   ```bash
   git push origin feature/amazing-feature
   ```
5. **Open a Pull Request (PR)**:
   - Provide a clear description of the feature or bugfix.
   - Include screenshots or audio test samples if you made UI/voice changes.

---

## 📜 Code of Conduct

- Be respectful, inclusive, and welcoming to all contributors.
- Keep security in mind: never commit API keys or private financial data.
- Respect the core design rule: **The LLM interprets language; the database computes balances.**

Thank you for helping empower local businesses with accessible AI! ❤️
