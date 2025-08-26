# JuristRuBot 🇷🇺⚖️  
AI-powered legal assistant for Russian law  

## Overview  
**JuristRuBot** is a Telegram bot that helps users navigate Russian law.  
It answers legal questions in plain language, provides references to relevant codes and articles (e.g., КоАП РФ, УК РФ, ГК РФ), and guides users with step-by-step instructions.  

Key features:  
- 🎙️ **Voice input** — send your question by voice, the bot will transcribe and process it.  
- 💬 **Text input** — up to 1000 characters per request.  
- 📚 **Legal context** — automatic qualification of norms (code, article, part).  
- 🔎 **Smart search** — queries refined into short legal search requests.  
- ⚡ **Fast answers** — concise, practical explanations of “what to do next.”  
- 🔐 **Privacy** — no storage of personal conversations.  

---

## Tech Stack  
- **Python 3.12**  
- **aiogram** (Telegram bot framework)  
- **OpenAI GPT models** (legal query refinement & answers)  
- **Whisper** (speech-to-text)  
- **SearXNG** (optional metasearch integration for context)  
- **Docker + systemd** (deployment on server)  

---

## Usage  
1. Start a chat with the bot in Telegram.  
2. Ask your question in text (≤ 1000 characters) or voice.  
3. Get references to relevant Russian law articles + step-by-step guidance.  

---

## Example Queries  
- *“What to do if my wallet was stolen?”*  
- *“Responsibility for drunk driving under КоАП РФ?”*  
- *“Grounds for terminating a rental contract early?”*  

---

## Deployment  

Clone repository and set up environment variables in `.env`:

```bash
git clone https://github.com/YOUR_USERNAME/JuristRuBot.git
cd JuristRuBot
cp .env.example .env
nano .env   # add TELEGRAM_TOKEN, OPENAI_API_KEY, etc.
