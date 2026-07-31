# AI Technical Interviewer

A live, adaptive, spoken technical interview backend — not a chatbot with a
Q&A list bolted on. It runs a multi-agent loop (interviewer → evaluator →
adaptive difficulty → interviewer again) on top of an LLM, speaks questions
aloud with ElevenLabs, transcribes spoken answers with Whisper, persists the
full session to MongoDB, and produces a scored PDF feedback report at the end.

## Why this isn't "just another chatbot"

- **The interviewer reacts, it doesn't script.** Every candidate answer is
  scored by a separate evaluator agent (correctness, depth, communication,
  confidence) *before* the interviewer decides what to say next. A vague
  answer triggers a follow-up; a strong answer moves the topic on or
  escalates difficulty.
- **Difficulty is adaptive**, not fixed. `app/services/scoring.py` walks an
  easy → medium → hard ladder based on a rolling read of answer quality.
- **Evaluation and coaching are separated from conversation.** The
  interviewer agent only ever produces the next thing to *say*. The
  evaluator scores. The feedback agent writes the final report. Three
  prompts, three responsibilities — easy to tune independently.
- **It's a real backend**, not a prompt in a wrapper: typed schemas, a
  repository layer over MongoDB, retryable LLM/TTS calls, structured
  logging, health checks, Docker, and tests.

## Architecture

```
Candidate ──▶ POST /interviews/start
                   │
                   ▼
         InterviewerAgent.opening_question()  ──▶ ElevenLabs (speech)
                   │
                   ▼
Candidate speaks ──▶ POST /interviews/{id}/answer (audio or text)
                   │
                   ▼
         WhisperService.transcribe()  (if audio)
                   │
                   ▼
         EvaluatorAgent.evaluate_answer()
           - correctness / depth / communication / confidence (0-10)
           - is_weak_or_vague flag drives follow-up vs. new question
                   │
                   ▼
         scoring.next_difficulty()  (adaptive ladder)
                   │
                   ▼
         InterviewerAgent.next_turn()  ──▶ ElevenLabs (speech)
                   │
                   ▼
         ... loop until MAX_QUESTIONS_PER_INTERVIEW ...
                   │
                   ▼
         POST /feedback/{id}/generate
           - FeedbackAgent aggregates full transcript + scores
           - deterministic score fallback if narrative generation fails
           - PDF built with reportlab, downloadable via /feedback/{id}/pdf
                   │
                   ▼
         Everything persisted in MongoDB (interviews collection)
```

### Directory layout

```
ai-technical-interviewer/
├── app/
│   ├── api/            # FastAPI routers (interview, feedback, upload, health)
│   ├── core/            # config, logging, auth, prompt templates
│   ├── agents/           # interviewer / evaluator / feedback agents
│   ├── services/         # ElevenLabs, LLM, Whisper, scoring, PDF report
│   ├── db/               # Mongo connection + repository + Pydantic models
│   ├── schemas/          # API request/response contracts
│   └── main.py           # FastAPI app + router wiring + lifespan
├── tests/                 # pytest unit tests (scoring logic, health)
├── Dockerfile
├── docker-compose.yml     # api + mongo + mongo-express
├── Makefile
└── .env.example
```

## Quick start

### Option A — Docker (recommended)

```bash
cp .env.example .env
# fill in GEMINI_API_KEY (or OPENAI_API_KEY) and ELEVENLABS_API_KEY
docker compose up --build
```

- API: http://localhost:8000/docs
- Mongo Express (DB viewer): http://localhost:8081 (admin/admin)

### Option B — Local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit it, and point MONGO_URI at a local/Atlas instance
make dev                # uvicorn --reload on :8000
```

### Run tests

```bash
make test
```

The included unit tests cover the deterministic scoring/difficulty logic
without needing live API keys. Full end-to-end flow tests need live (or
mocked) LLM/ElevenLabs/Mongo — swap in `unittest.mock.AsyncMock` on
`get_llm_service()` / `get_elevenlabs_service()` for CI.

## API walkthrough

**1. Start an interview**

```bash
curl -X POST localhost:8000/api/v1/interviews/start \
  -H "Content-Type: application/json" \
  -d '{
    "candidate_name": "Kruthika",
    "role": "AI/ML Engineer",
    "experience_level": "junior",
    "focus_areas": ["RAG systems", "python", "system design"]
  }'
```

Returns `interview_id`, a `session_token` (bearer token scoped to this
interview), the first question's text, and base64 MP3 audio.

**2. Submit an answer** (text or base64 audio — both supported)

```bash
curl -X POST localhost:8000/api/v1/interviews/<id>/answer \
  -H "Authorization: Bearer <session_token>" \
  -H "Content-Type: application/json" \
  -d '{"answer_text": "I would use a token bucket algorithm..."}'
```

Returns the evaluator's scores for that answer, the next question (text +
audio), the updated difficulty, and whether the interview is now `is_final`.

**3. Generate the feedback report**

```bash
curl -X POST localhost:8000/api/v1/feedback/<id>/generate
curl localhost:8000/api/v1/feedback/<id>/pdf -o report.pdf
```

## Configuration notes

- `LLM_PROVIDER` switches between `gemini` (default) and `openai` — same code
  path, just set the matching API key and model in `.env`. Gemini's
  `response_mime_type="application/json"` is used to get strict JSON back
  from the interviewer/evaluator/feedback agents.
- `TRANSCRIBE_PROVIDER=local` runs `faster-whisper` on CPU inside the
  container instead of calling OpenAI's hosted Whisper — useful if you don't
  want to pay per-transcription, at the cost of first-run model download time.
- `MAX_QUESTIONS_PER_INTERVIEW` / `DIFFICULTY_LEVELS` control interview
  length and the adaptive difficulty ladder.
- If `ELEVENLABS_API_KEY` is unset, the API still works — it just returns
  `null` for audio fields and the interview proceeds text-only. Useful for
  developing the orchestration logic without burning ElevenLabs credits.

## What to point people at in a demo / portfolio writeup

- **AI orchestration**: three cooperating agents with distinct, narrow
  responsibilities and strict-JSON contracts between them (`app/core/prompts.py`,
  `app/agents/`).
- **Backend engineering**: typed schemas end-to-end, a repository pattern
  over Mongo instead of route handlers touching collections directly,
  retry/backoff on external API calls, structured logging, global exception
  handling, health/readiness probes.
- **API design**: session-token auth scoped per-interview so a frontend
  candidate flow can't read/mutate another candidate's session; clean
  separation between the conversational loop (`/interviews`) and the
  post-hoc scoring artifact (`/feedback`).
- **Persistence**: full transcript + per-answer evaluation stored in Mongo,
  so a report can always be regenerated from source data rather than cached
  blindly.
- **Deployment**: multi-service `docker-compose` (API, Mongo, Mongo Express),
  container healthcheck, `Makefile` for the common dev loop.




