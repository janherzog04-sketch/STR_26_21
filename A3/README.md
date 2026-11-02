# From laptop to GitHub: group work with VS Code

## Summary

**Title:** Working together on IFC tools with GitHub and VS Code

**Description:** Connect VS Code to GitHub and use it as a group: clone, commit, sync, solve merge conflicts and work in branches – while keeping IFC models and personal file paths out of your repository.

---

## Who is this for?

| | |
|---|---|
| **Focus area** | All focus areas (example from Structures, group 21) |
| **Role / level** | Analyst – Level 1 *(you can run a Python script, you have never used Git in a team)* |
| **BIM use** | Every A4 tool – the code must be on GitHub, the IFC model must not |
| **Learning need owner** | *(name of the group that proposed the need)* |
| **Prerequisite** | Course tutorial *Introduction to scripting with IfcOpenShell in system environment* (Python, VS Code and IfcOpenShell installed) |
| **Time** | ~45 minutes, best done **in pairs** |
| **Video** | *(link to YouTube / DTU video)* |

## Learning objectives

After this tutorial you can …

1. connect VS Code to your GitHub account and clone your group repository,
2. use the Source Control panel: stage, commit, sync (pull + push),
3. keep the IFC model and your personal model path out of the repository (`.gitignore`, `config.py`),
4. solve a merge conflict in VS Code when two people edited the same line,
5. work on a branch and merge it back with a pull request,
6. follow a few simple team rules that prevent most problems.

## Why this tutorial?

The course tutorial shows how to run IfcOpenShell **on your own laptop**. A4 is group work and has to be
submitted **as a GitHub repository**. That is where most groups lose time:

| Problem | What happens |
|---|---|
| Code is shared by e-mail / Teams | Nobody knows which `main.py` is the latest one. |
| Everyone has a different model path | Every `git pull` overwrites your path → `FileNotFoundError`. |
| The IFC model is pushed to GitHub | The assignment forbids it; files > 100 MB are rejected and block the push. |
| Two people edited the same file | "Merge conflict" – and nobody knows what to click. |
| Push is rejected | "Updates were rejected because the remote contains work that you do not have locally." |

You don't need the terminal for any of this – VS Code has everything built in.

---

## Part 1 – Connect VS Code to GitHub (once per laptop)

### 1.1 Install Git

VS Code uses Git in the background, it does not include it.

- **Windows:** download from [git-scm.com](https://git-scm.com/downloads) and keep the default options.
  The installer includes the *Git Credential Manager*, which handles the GitHub login for you.
- **macOS:** open a terminal and run `git --version` – macOS offers to install it.

Restart VS Code afterwards. If the Source Control panel (`Ctrl+Shift+G`) still says *"Download Git"*, Git is not found.

### 1.2 Tell Git who you are

Every commit is signed with a name and an e-mail. Use the e-mail of your GitHub account. In the VS Code terminal
(`Ctrl+ö` on a German keyboard, ``Ctrl+` `` on an English one):

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

### 1.3 Sign in to GitHub

Click the **Accounts** icon (bottom left, the person symbol) → **Sign in with GitHub** → confirm in the browser.
From now on, VS Code can clone, push and pull without asking for a password.

> A GitHub **password does not work** for pushing from the command line anymore. The browser login (or a personal
> access token) replaces it. If a password prompt appears, cancel it and sign in through VS Code.

---

## Part 2 – Create or join the group repository

### Option A: one person creates the repository

1. On [github.com](https://github.com): **New repository** → name (e.g. `STR_26_21`) → **Add a README** → choose
   the `.gitignore` template **Python**.
2. **Settings → Collaborators → Add people** – add your group members. They get an invitation by e-mail and have
   to **accept** it before they can push.

### Option B: everybody else clones it

1. In VS Code: `Ctrl+Shift+P` → **Git: Clone** → **Clone from GitHub** → pick the repository.
2. Choose a local folder – **not** inside OneDrive/iCloud/Dropbox (sync tools and Git fight over the same files).
3. **Open** the cloned repository when VS Code asks.

### Already have a local folder with code?

Open the folder in VS Code → Source Control panel → **Publish to GitHub** → choose *private* or *public*.
VS Code asks which files to include – **untick any `.ifc` file!**

---

## Part 3 – Keep the model and your path out of Git

Do this **before the first commit** with code in it.

### 3.1 `.gitignore`

Git ignores every file that matches a line in `.gitignore`. Add at least:

```gitignore
# IFC models: too big, not ours to publish, not part of the assignment
*.ifc
*.ifczip

# Your personal settings (path to the model on YOUR laptop)
config.py

# Python environment and cache files
.venv/
__pycache__/
.ipynb_checkpoints/

# Output of your tool (re-create it by running the script)
output/
```

The full version is in [`template/.gitignore`](template/.gitignore).

**Check it in VS Code:** ignored files are shown **greyed out** in the Explorer and never appear in the Source
Control panel. Copy an `.ifc` file into the folder – if it shows up under *Changes*, your `.gitignore` is wrong.

### 3.2 One path per person: `config_example.py` → `config.py`

The course tutorial warns about absolute and relative paths. In a group there is a second problem: your absolute
path is not your partner's. So the path goes into a file that is **not shared**:

| File | On GitHub? | Content |
|---|---|---|
| `config_example.py` | yes | template: `MODEL_PATH = r"C:\Users\YourName\...\model.ifc"` |
| `config.py` | **no** (in `.gitignore`) | your real path |

```python
# main.py – identical for everybody
from config import MODEL_PATH
model = ifcopenshell.open(MODEL_PATH)
```

After cloning, each person copies `config_example.py` → `config.py` once and writes their own path in it.
Then run [`template/check_setup.py`](template/check_setup.py) – it tells you in plain words if Python,
IfcOpenShell, `config.py` or the model file is missing.

### 3.3 Too late – the model is already committed?

Remove it from Git, but keep it on your disk:

```bash
git rm --cached path/to/model.ifc
git commit -m "Remove IFC model from repository"
```

> The file is still in the **old commits**. If it is bigger than 100 MB, GitHub keeps rejecting the push. Ask for
> help before you experiment with the history.

---

## Part 4 – The daily workflow in VS Code

Open the **Source Control** panel (`Ctrl+Shift+G`, the branch icon on the left).

```
 ┌───────────────────────────────┐
 │ SOURCE CONTROL                │
 │ ┌───────────────────────────┐ │
 │ │ Message (Ctrl+Enter)      │ │  ← 3. describe what you did
 │ └───────────────────────────┘ │
 │ [ ✓ Commit ]                  │  ← 4. save a snapshot locally
 │ ▾ Staged Changes              │
 │     main.py            M      │  ← 2. files that go into the commit
 │ ▾ Changes                     │
 │     slab_info.py       M   +  │  ← 1. click + to stage a file
 │     README.md          U   +  │
 └───────────────────────────────┘
   M = modified, U = untracked (new), D = deleted
```

| Step | In VS Code | What it means |
|---|---|---|
| **Pull** | **Sync Changes** button, or `…` → *Pull* | get your partners' commits |
| **Stage** | `+` next to a file | choose what goes into the next commit |
| **Commit** | write a message → **✓ Commit** | save a snapshot **on your laptop** |
| **Push** | **Sync Changes** button | upload your commits to GitHub |

**Commit ≠ upload.** After *Commit* your work is still only on your laptop. Only *Sync Changes* (or *Push*)
puts it on GitHub. The number next to the sync icon in the status bar (bottom left, e.g. `↓1 ↑2`) shows how many
commits are waiting to be pulled / pushed.

Click a changed file in the panel to see a **side-by-side diff** of what you changed – check it before committing.

### Good commit messages

| Not helpful | Helpful |
|---|---|
| `update` | `Add span calculation from Qto_SlabBaseQuantities` |
| `fix` | `Skip filler strips shorter than 1 m` |
| `asdf` | `Move model path to config.py` |

Rule of thumb: *"If applied, this commit will …"* + your message.

---

## Part 5 – Merge conflicts

A conflict happens when you and your partner changed **the same lines** of a file and both committed. Git
cannot decide which version is right, so it asks you. Typical message after *Sync Changes*:
*"Merge conflict in main.py"*.

VS Code marks the conflicting block:

```python
<<<<<<< HEAD (Current Change)
NAME_FILTER = "KLH"
=======
NAME_FILTER = "RC"
>>>>>>> origin/main (Incoming Change)
```

Above the block you can click:

| Option | Keeps |
|---|---|
| **Accept Current Change** | your version |
| **Accept Incoming Change** | your partner's version |
| **Accept Both Changes** | both, one after the other (then clean up by hand) |
| **Compare Changes** | shows both side by side |

For bigger conflicts click **Resolve in Merge Editor** (bottom right of the file) – a three-pane view with
*Incoming*, *Current* and the *Result*.

When every conflict in the file is solved:

1. save the file,
2. stage it (`+`),
3. **Commit** (the message is filled in for you) → **Sync Changes**.

> **Talk to each other.** The person who solves the conflict decides which code survives. If in doubt, call the
> person who wrote the other version.

**Jupyter notebooks** (`.ipynb`) are JSON files with outputs and images inside – conflicts in them are very hard
to solve. Agree that only one person edits a notebook at a time, and clear the outputs before committing
(`…` → *Clear All Outputs*).

---

## Part 6 – Branches and pull requests (optional, recommended)

Instead of everybody working on `main`, each person works on their own **branch** and merges it when it works.
`main` always stays runnable – important for the submission.

1. Click the branch name in the **status bar** (bottom left, `main`) → **Create new branch…** → e.g. `uls-checks`.
2. Work and commit as usual.
3. Source Control panel → **Publish Branch**.
4. On GitHub a yellow banner appears: **Compare & pull request** → describe the change → **Create pull request**.
5. Your partner reviews the changes on GitHub → **Merge pull request**.
6. Back in VS Code: switch to `main` (status bar) → **Sync Changes**.

A pull request is also a good place for the peer feedback: comments are attached to the exact lines of code.

---

## Part 7 – Team rules that prevent most problems

1. **Pull before you start working.** Every time.
2. **Commit small and often** – one step of your BPMN diagram, not "everything from this week".
3. **Push at the end of every session**, even if it is not finished (on a branch).
4. **Split the work by files**, not by lines: e.g. one person `ifc_extract.py`, one person `checks.py`;
   `main.py` only imports them.
5. **Never commit** `.ifc`, `config.py`, `.venv/`, outputs.
6. **Don't edit a file in the GitHub web editor** while a partner is working on it locally.

---

## Exercises (peer test, in pairs)

Please do these with a partner and tell us in your feedback where you got stuck.

1. **Clone and set up.** Person A creates a repository from our [`template/`](template/) and adds person B as
   collaborator. B clones it in VS Code, creates `config.py` and runs `python check_setup.py`.
2. **Proof that Git ignores it.** Both copy an `.ifc` file into the folder. Does it appear in the Source Control panel?
3. **First round trip.** A changes the print text in `main.py`, commits and syncs. B pulls and runs `main.py`.
4. **Provoke a conflict.** Both change the same line, e.g. `NAME_FILTER` in `main.py` (one writes `"KLH"`, the other `"RC"`). Both
   commit. A syncs first, then B syncs → solve the conflict in VS Code.
5. **Branch.** B creates the branch `my-feature`, adds a function, publishes the branch and opens a pull request.
   A merges it on GitHub. Both end on an up-to-date `main`.

## Troubleshooting

| Message / problem | Cause | Fix |
|---|---|---|
| Source Control says *"Download Git"* | Git not installed or not found | Install Git, restart VS Code |
| *"Make sure you configure your user.name and user.email"* | Git doesn't know who you are | Part 1.2 |
| *"Permission denied"* / 403 on push | Not invited as collaborator, or invitation not accepted | Owner: Settings → Collaborators; you: accept the e-mail invitation |
| *"Updates were rejected because the remote contains work…"* | Partner pushed before you | **Sync Changes** (pull first), solve conflicts, push again |
| *"File … exceeds GitHub's file size limit of 100 MB"* | IFC model was committed | Part 3.3 |
| `.ifc` still shows up in Changes | It was committed before `.gitignore` existed | `git rm --cached <file>.ifc` |
| `ModuleNotFoundError: No module named 'config'` after cloning | `config.py` is (correctly) not on GitHub | Copy `config_example.py` → `config.py` |
| Files appear twice / weird changes in a OneDrive folder | Cloud sync and Git interfere | Clone into a folder outside OneDrive |

## Checklist for your A4 repository

- [ ] All group members are collaborators and have cloned the repository in VS Code
- [ ] `.gitignore` with `*.ifc`, `config.py`, `.venv/`, `__pycache__/`, `output/`
- [ ] No `.ifc` file and no `config.py` on GitHub (check on github.com, not only locally)
- [ ] `config_example.py` and a README that says how to create `config.py`
- [ ] `main` runs after a fresh clone (test it on a partner's laptop)
- [ ] Commit history with readable messages

## Files in this tutorial

```
tutorial/
│   README.md               ← this tutorial
└── template/               ← copy this into a new repository
        .gitignore
        config_example.py   ← copy to config.py, add your model path
        check_setup.py      ← 1-minute check after cloning
        requirements.txt
        main.py             ← short entry point
        slab_info.py        ← example module
```

## Further reading

- [VS Code – Source Control overview](https://code.visualstudio.com/docs/sourcecontrol/overview)
- [VS Code – Working with GitHub](https://code.visualstudio.com/docs/sourcecontrol/github)
- [GitHub – Inviting collaborators](https://docs.github.com/en/account-and-profile/setting-up-and-managing-your-personal-account-on-github/managing-access-to-your-personal-repositories/inviting-collaborators-to-a-personal-repository)
- [Git – gitignore documentation](https://git-scm.com/docs/gitignore)
