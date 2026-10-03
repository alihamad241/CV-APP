# 🤖 AI CV Optimizer

An AI-powered CV optimization tool built with Streamlit. Upload a PDF resume, paste a job description, and get instant ATS scoring, AI analysis, and a fully rewritten CV tailored to the job.

## Features

- 📄 PDF resume parsing
- 🤖 Multi-provider AI: **Gemini**, **Claude**, or **Ollama** (local)
- 📊 **ATS Score** with keyword matching, formatting analysis & improvement tips
- ✅ Match scoring (0–100) with matched & missing skills breakdown
- ✨ **AI CV Rewriter** — generates a tailored CV for any job description
- 👤 **Persistent Profile Store** — remembers your skills & experience across sessions
- 🔗 **LinkedIn Integration** — import certifications, achievements & courses
- 🔍 Optional job description bias checker
- 📥 Download rewritten CV as Markdown or Word (.docx)

## Getting Started

### 1. Clone the repo
```bash
git clone https://github.com/YOUR_USERNAME/cv-optimizer.git
cd cv-optimizer
```

### 2. Install dependencies
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Run the app
```bash
streamlit run app.py
```

Enter your API key (Gemini, Claude, or Ollama URL) in the sidebar.

## Deploy to Streamlit Cloud (Free)

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo
4. Set main file to `app.py`
5. Deploy — you'll get a shareable public URL

> Users enter their own API key in the sidebar, so no secrets are needed.

## Project Structure

```
cv-optimizer/
├── app.py                      # Main Streamlit UI (4 tabs)
├── utils/
│   ├── extractor.py            # PDF text extraction (PyMuPDF)
│   ├── analyzer.py             # AI analysis, ATS scoring, CV rewriting
│   ├── docx_generator.py       # Markdown → Word document converter
│   ├── profile_store.py        # Persistent user profile storage
│   └── linkedin_scraper.py     # LinkedIn data extraction via AI
├── requirements.txt
├── .gitignore
└── README.md
```

## Tech Stack

| Tool | Purpose |
|------|---------|
| Python | Core language |
| Streamlit | UI framework |
| PyMuPDF | PDF text extraction |
| Google GenAI SDK | Gemini API |
| Anthropic SDK | Claude API |
| python-docx | Word document generation |

## License

MIT
