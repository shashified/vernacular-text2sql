# Review demo: how to run it

The demo is a website served by a small Python server. The site is already built
(`web/dist`), so you do **not** need Node.js to run it.

## One-time setup (inside the repo, with the venv on)

```
cd ~/claude/projects/idp/repo
source .venv/bin/activate
pip install fastapi uvicorn
```

The database must exist (`python scripts/build_agri_db.py` if you have never built it).

## Start it

```
python scripts/demo_server.py
```

Your browser opens http://localhost:8000. Stop with Ctrl+C.

## Two modes

| Mode | What it does | Needs |
|---|---|---|
| **Saved run** | Replays our Qwen3-8B evaluation for the 160 benchmark questions: Stage 1 is recomputed, the saved plan and SQL are executed again and compared with the reference answer and with the model-alone answer. Instant. | Nothing (works offline) |
| **Live model** | Sends any question to the model in `.env` (Groq) and shows each plan attempt, the checks, the SQL and the answer. "Ask the model directly" runs the baseline for comparison. | Internet + the Groq key in `.env` |

Use a different model file with `python scripts/demo_server.py --env .env.ollama`
(local Ollama is slow: a minute or two per answer).

## Tips for the panel

1. Start in **Saved run** and click the first Telugu example (groundnut in Gujarat): the model alone
   reads the crop as cotton and gets it wrong; the pipeline links వేరుశనగ to 'Groundnut' and is right.
2. The Telugu "top 3 sugarcane districts" example shows the same thing for a top-k query.
3. Then switch to **Live model** and let a reviewer type their own question.

## Editing the site (only if you change the design)

```
cd web
npm install
npm run dev        # http://localhost:5173, talks to the Python server on :8000
npm run build      # writes web/dist, which the Python server serves
```
