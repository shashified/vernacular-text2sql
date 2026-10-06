# Team guide: run your share of the evaluation

Groq's free tier gives each **account** 200,000 tokens per day. One account
can't finish a full evaluation in a day, so each of us runs **one language**
with our **own free Groq account**. The results already in the repo are skipped
automatically. You only run what's missing.

Time: ~15 min setup (once) + ~10 min running. Cost: ₹0.

| Person | Language flag |
|---|---|
| Teammate A | `--langs hi` (Hindi) |
| Teammate B | `--langs te` (Telugu) |
| Teammate C | `--langs hinglish` (Hinglish) |
| Teammate D | `--langs en` (English) |

---

## Step 1: Make your own Groq key (free, no card)

1. Go to **https://console.groq.com** and sign up with **your own** email/Google.
2. Left menu, **API Keys**, **Create API Key**, name it `idp`, copy it.
   It starts with `gsk_`. You only see it once, so paste it somewhere safe for now.
3. Never share your key in chat or commit it to GitHub.

> Use your own account. One person making several accounts to get around the
> limit breaks Groq's terms and can get keys banned.

## Step 2: Install Python and Git (skip if you already have them)

- **Mac:** open Terminal and run `python3 --version` and `git --version`.
  If either is missing, macOS will offer to install it. Click Install.
- **Windows:** install Python 3.11+ from https://www.python.org/downloads/
  (**tick "Add Python to PATH"** in the installer) and Git from https://git-scm.com/download/win.
  Use the **Git Bash** app for the commands below.

## Step 3: Download the project

```
git clone https://github.com/shashified/vernacular-text2sql.git
cd vernacular-text2sql
```

## Step 4: Set up the project's Python toolbox

Mac:
```
python3 -m venv .venv
source .venv/bin/activate
pip install openai python-dotenv pandas
```

Windows (Git Bash):
```
python -m venv .venv
source .venv/Scripts/activate
pip install openai python-dotenv pandas
```

You should now see `(.venv)` at the start of the line. If you open a new
Terminal later, `cd` into the folder and run the `source` line again.

## Step 5: Build the test database (~1 minute)

```
python scripts/build_agri_db.py
```

It should end with `crop_production   326,035 rows`.

## Step 6: Add your key

```
cp .env.example .env
```

Open `.env` in any text editor (Mac: `open -e .env`, Windows: `notepad .env`) and
replace `gsk_your_key_here` with your key. Leave the model line as it is
(`LLM_MODEL=qwen/qwen3.8-27b`). Everyone must use the same model. Save and close.

## Step 7: Run your language

Use your own flag from the table at the top. For example, for Hindi:

```
python scripts/run_eval.py --langs hi
```

- The first line says how many it will run and how many are **already saved**.
  The saved ones are the ones Shashank already ran.
- You'll see lines like `[3/34] ✓ agri_027 hi pipeline match`. ✗ is fine too.
  We are measuring, not hoping for all ✓.
- If it says **Stopped: the provider's rate limit was hit**, your daily quota is
  used up. Run the same command tomorrow and it continues where it stopped.
- If anything else goes wrong, screenshot the error and send it to Shashank.

## Step 8: Send back your results

Send Shashank this one file (WhatsApp/Drive/email is fine):

```
results/agri_qwen-qwen3.8-27b.jsonl
```

**Don't** send `.env`. It contains your key.

---

## For Shashank: combining everyone's files

Save each teammate's file in its own folder (they all have the same name):

```
results/incoming/hi/agri_qwen-qwen3.8-27b.jsonl
results/incoming/te/agri_qwen-qwen3.8-27b.jsonl
results/incoming/hinglish/agri_qwen-qwen3.8-27b.jsonl
results/incoming/en/agri_qwen-qwen3.8-27b.jsonl
```

Then:

```
python scripts/merge_results.py results/incoming/*/agri_qwen-qwen3.8-27b.jsonl
```

It keeps one answer per question/language/method, drops rate-limited attempts,
says what's still missing, and prints the combined results table.
