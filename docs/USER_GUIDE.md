# RAG Chatbot — User Guide

Welcome! This guide explains how to use the RAG Chatbot to upload your documents and ask questions about them. Two interfaces are available — both do the same thing, just with different looks.

---

## Table of Contents

1. [What the App Does](#1-what-the-app-does)
2. [Choosing Your Interface](#2-choosing-your-interface)
3. [Uploading Documents](#3-uploading-documents)
4. [Asking Questions](#4-asking-questions)
5. [Understanding the Answer](#5-understanding-the-answer)
6. [Settings and Controls](#6-settings-and-controls)
7. [Best Practices](#7-best-practices)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. What the App Does

You upload a document (PDF, Word file, text file, CSV, or Markdown). The app splits it into small pieces, converts each piece into a mathematical representation called a **vector**, and stores them.

When you ask a question, the app:
1. Converts your question into a vector
2. Finds the document pieces that are mathematically closest to your question
3. Sends those pieces + your question to a free AI model (Gemini or Groq)
4. Shows you the AI's answer along with which document pieces it used

This means answers are grounded in **your documents**, not just general AI knowledge.

---

## 2. Choosing Your Interface

### Option A — Streamlit UI (simpler)

Run: `streamlit run streamlit_app.py` → open http://localhost:8501

Best for: quick testing, running on a single machine.

### Option B — React UI (modern)

Run backend + frontend in two terminals → open http://localhost:5173

Best for: better visual experience, streaming word-by-word answers, modern design.

Both interfaces support the same features. This guide describes both — differences are noted where they exist.

---

## 3. Uploading Documents

### Supported file types

| Type | Extension | Notes |
|------|-----------|-------|
| PDF | `.pdf` | Text-based PDFs (not scanned images) |
| Word | `.docx` | Microsoft Word 2007 and newer |
| Text | `.txt` | Plain text, UTF-8 recommended |
| Markdown | `.md` | Markdown files |
| Spreadsheet | `.csv` | CSV data files |

### Streamlit UI — uploading

1. In the left sidebar, find **"Upload Documents"**
2. Click the upload area or drag files onto it
3. Select one or more files (multiple files supported)
4. Click **"Process Documents"** button
5. A progress bar shows processing status
6. When complete, your document appears in the **"Loaded Documents"** list

### React UI — uploading

1. In the left sidebar, find the upload area (dashed border)
2. Drag and drop files directly onto it, **or** click it to select files
3. Files are processed automatically — no extra button needed
4. The sidebar shows each document with its chunk count

### What happens during processing

```
Your file
    ↓
Text is extracted (PyMuPDF for PDF, python-docx for DOCX, etc.)
    ↓
Text is split into chunks of ~500 characters with 50-char overlap
    ↓
Each chunk is converted to a 384-dimension vector (locally, no internet needed)
    ↓
Vectors + text + metadata stored in ChromaDB on your machine
```

---

## 4. Asking Questions

### Streamlit UI

After uploading at least one document, a chat input appears at the bottom of the page. Type your question and press **Enter** or click the send button.

### React UI

The chat input is always visible at the bottom of the chat window. Type your question and press **Enter** or click the send (arrow) button. The answer **streams word-by-word** as it is generated — you do not need to wait for the full response.

### Example questions that work well

- *"Summarize the main points of this document"*
- *"What does the document say about [topic]?"*
- *"List all the key concepts mentioned"*
- *"What are the steps described in this guide?"*
- *"Explain [term] in simple language"*

---

## 5. Understanding the Answer

### Answer content

The AI answers based only on what is in your uploaded documents. If the information is not in the documents, it will say: *"I don't have enough information to answer this question."*

### Sources

Every answer comes with a **sources** section showing which document chunk(s) were used:

- **Streamlit:** Click the "📎 View X sources" expander below the answer
- **React UI:** Click the "📎 X sources" text below the bot message

Each source shows:
- The filename it came from
- The chunk number within that document

This lets you verify the answer came from your actual document.

### Streaming (React UI only)

In the React UI, the answer appears token by token — like ChatGPT. You can start reading before the full response is complete.

---

## 6. Settings and Controls

### AI Model Selection

Both UIs let you choose between two free AI models:

| Model | Provider | Best for |
|-------|----------|---------|
| **Gemini 2.5 Flash** | Google | Longer, more detailed answers |
| **Groq Llama 3.1** | Groq | Faster responses |

Switch models using the dropdown/buttons in the sidebar. The switch takes effect on your next question.

### Context Chunks (Top K)

Controls how many document pieces are retrieved and given to the AI.

- **Streamlit:** Slider labeled "Context chunks" in the sidebar
- **React UI:** Slider in the top bar of the chat window

| Setting | Effect |
|---------|--------|
| 1–2 | Fast, focused, may miss some details |
| 3–5 | Good balance (recommended) |
| 6–10 | More context, potentially more thorough answers |

### Clearing Data

- **Clear Chat:** Removes the conversation history from the screen (documents stay loaded)
- **Clear All Documents:** Removes all documents from ChromaDB. You will need to re-upload.

---

## 7. Best Practices

### For better answers

**Ask specific questions:**
```
❌ "Tell me about it"
✅ "What are the main features described in section 2?"
```

**Use words from the document:**
```
❌ "How much power does it use?"
✅ "What is the power consumption in watts?"
```

**Ask one thing at a time:**
```
❌ "What are the features and specifications and how is it installed?"
✅ "What are the main features?"  (then separately ask about specs and installation)
```

### For better uploads

- Use **text-based PDFs** — scanned/image PDFs cannot be read
- Keep files **under 10 MB** for fastest processing
- Well-structured documents (with headings and clear paragraphs) give better results than walls of text
- You can upload **multiple documents** — questions will search across all of them

### Document quality tips

```
❌ Poor structure:
"The device supports voltage. Current is also measured. There are many features."

✅ Good structure:
## Electrical Specifications
- Voltage: 85–264V AC
- Current: 0–100A
- Power Factor: > 0.95
```

---

## 8. Troubleshooting

### "Please upload documents from the sidebar to start chatting"

No documents have been uploaded yet. Go to the sidebar, upload at least one file, and wait for processing to complete.

### Answer says "I don't have enough information"

- The document might not contain the answer to your question
- Try rephrasing with different words
- Check that the correct document was uploaded

### Upload fails

- Check the file is a supported format (PDF, DOCX, TXT, MD, CSV)
- Check the file is not password-protected or corrupted
- PDFs must be text-based, not scanned images

### Gemini / Groq errors

- Check your API key is set in `.env`
- Try switching to the other model provider in the sidebar
- Check your internet connection

### React UI shows no response / connection error

- Make sure the FastAPI backend is running: `uvicorn backend.main:app --reload --port 8000`
- Refresh the browser page

### First startup is slow

Normal — the AI embedding model (~80MB) is downloaded once and cached. All subsequent startups are fast.

---

## Summary

| Task | Time needed |
|------|------------|
| First setup (install packages) | 5–10 minutes |
| Starting the app | 30–60 seconds (first time) / 5 seconds (after) |
| Uploading a document | 5–30 seconds depending on size |
| Getting an answer | 2–5 seconds |

**Workflow:** Upload document → type your question → read answer → check sources → ask follow-ups.