# Git Workflow Guide — Vernacular Text-to-SQL

A practical reference for working on this repo, solo now and with the team later.
Skim once, then use the cheat sheet at the bottom day to day.

---

## 1. The mental model

Git has three places your code can live:

```
Working directory  --add-->  Staging area  --commit-->  Local repo history  --push-->  GitHub (remote)
     (your files)              (what's about              (your commits)            (shared with team)
                                 to be committed)
```

- **Working directory** — the actual files you're editing.
- **Staging area** — a holding pen for changes you're about to save as a commit. `git add` puts things here.
- **Local history** — `git commit` takes what's staged and saves it as a permanent checkpoint, on your machine only.
- **Remote (GitHub)** — `git push` sends your local commits there; `git pull` brings down commits others made.

Nothing leaves your laptop until you `push`. You can commit as often as you like without affecting anyone else.

---

## 2. Daily workflow (the 90% case)

This is the loop you'll run almost every time you sit down to work:

```bash
git status                       # what's changed since my last commit?
git pull                         # get any changes teammates pushed
# ...edit files...
git add .                        # stage everything you changed
git status                       # (optional) double-check what's staged
git commit -m "short description of what changed"
git push
```

**When to run each:**

| Command | When |
|---|---|
| `git status` | Before you do anything, and before every commit — habit, not optional. Shows what's modified/staged. |
| `git pull` | First thing when you open the terminal to start working, especially once teammates are pushing too. |
| `git add .` | After you've made a chunk of related changes you're happy with. `git add <file>` to stage just one file instead of everything. |
| `git commit -m "..."` | Once staged changes represent one logical unit of work — "added the schema-linking retriever", not "fixed typo, then more typo, then actually fixed it". |
| `git push` | After committing, whenever you want your work backed up / visible to teammates. Don't hoard commits locally for days. |

**Commit message style:** short, present-tense, specific.
- Good: `"Add aggregation-aware plan validator"`, `"Fix schema retrieval for Tamil questions"`
- Avoid: `"update"`, `"fix"`, `"wip"`, `"asdf"`

---

## 3. Branches — for once the team is actively coding together

Right now, working alone on `main` directly is fine. Once your 4 teammates are also pushing code, working directly on `main` means you'll constantly step on each other. Switch to **one branch per piece of work**:

```bash
git checkout -b schema-linking-retrieval     # create + switch to a new branch
# ...work, add, commit as usual on this branch...
git push -u origin schema-linking-retrieval  # push the branch itself (first time)
```

Then open a **Pull Request (PR)** on GitHub from that branch into `main`, so someone (or you) can look at the diff before it merges. This is the standard team workflow:

```bash
git checkout main
git pull                                    # make sure main is up to date
git checkout -b <your-feature-branch>
# work, commit
git push -u origin <your-feature-branch>
# open a PR on github.com, merge it there once reviewed
git checkout main
git pull                                    # bring the merged change back down
```

**Suggested branch names for your 4 stages:** `schema-linking`, `aggregation-generation`, `evidence-integration`, `eval-harness`, `demo-ui` — matching your role split in the project README.

---

## 4. Checking things before you commit

```bash
git status              # which files changed, staged vs. not
git diff                # exact line-by-line changes, NOT yet staged
git diff --staged       # exact changes that WILL go into the next commit
git log --oneline       # compact history of past commits
```

Run `git diff` before `git add` if you're not sure what you actually changed — cheaper than committing something wrong and fixing it after.

---

## 5. Undoing mistakes

| Situation | Command |
|---|---|
| Changed a file, want to discard the edit (not staged yet) | `git checkout -- <file>` |
| Already ran `git add`, want to unstage (keep the edit) | `git restore --staged <file>` |
| Committed, but the message/content of the *last* commit was wrong, and you haven't pushed yet | `git commit --amend -m "corrected message"` |
| Want to see an old version of a file without losing current work | `git log --oneline` (find the commit), then `git show <commit-hash>:<file>` |
| Pushed something bad and need to fully revert it | `git revert <commit-hash>` (safe — adds a new commit undoing it, doesn't rewrite history) |

Avoid `git reset --hard` and force-pushing over shared branches once teammates are pulling from them — those rewrite history and will break everyone else's copy. `--force` is only safe on a repo/branch nobody else has pulled yet (like your very first push tonight).

---

## 6. Handling the errors you'll actually hit

**`! [rejected] ... (fetch first)`**
The remote has commits you don't have locally (someone else pushed, or GitHub auto-created a README).
```bash
git pull                                    # merges remote changes in
# resolve any conflicts (see below), then:
git push
```

**Merge conflict** (git pull or a PR merge says files conflict)
Git marks the conflicting section directly in the file:
```
<<<<<<< HEAD
your version
=======
their version
>>>>>>> branch-name
```
Open the file, manually pick/combine the right content, delete the `<<<<<<<`/`=======`/`>>>>>>>` markers, then:
```bash
git add <the file you fixed>
git commit          # completes the merge
git push
```

**`remote: Repository not found`**
The repo doesn't exist yet at that URL, or the name/owner is wrong — create it on github.com first, or fix the URL with `git remote set-url origin <correct-url>`.

---

## 7. Quick reference

```bash
git status                          # what changed
git pull                            # get latest from GitHub
git add .                           # stage all changes
git add <file>                      # stage one file
git commit -m "message"             # save staged changes as a checkpoint
git push                            # send commits to GitHub
git log --oneline                   # see commit history
git checkout -b <branch-name>       # create + switch to new branch
git checkout main                   # switch back to main
git diff                            # see unstaged changes
```

**Rule of thumb:** `status` often, `add`+`commit` in small logical chunks, `push` every time you commit (don't let local work pile up unpushed), `pull` before you start working each session.
