# From laptop to GitHub: group work with VS Code

## Summary

**Title:** Working together on IFC tools with GitHub and VS Code

**Description:** Connect VS Code to GitHub and use it as a group: clone, commit, sync, solve merge conflicts and work in branches – while keeping IFC models and personal file paths out of your repository.

---

## Who is this for?

| | |
|---|---|
| **Focus area** | All focus areas |
| **Role / level** | Analyst – Level 1 *(you can run a Python script, you have never used Git in a team)* |
| **BIM use** | Every A4 tool – the code must be on GitHub, the IFC model must not |
| **Learning need owner** | STR_26_21 |
| **Prerequisite** | Course tutorial *Introduction to scripting with IfcOpenShell in system environment* (Python, VS Code and IfcOpenShell installed) |

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
| Two people edited the same file | "Merge conflict" – and nobody knows what to do. |
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

### 1.2 Sign in to GitHub

Click the **Accounts** icon (bottom left, the person symbol) → **Sign in with GitHub** → confirm in the browser.
From now on, VS Code can clone, push and pull without asking for a password.

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
Then run the check_setup.py – it tells you in plain words if Python,
IfcOpenShell, `config.py` or the model file is missing.

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

---

## Part 6 – Branches and pull requests (optional, recommended)

Instead of everybody working on `main`, each person works on their own **branch** and merges it when it works.
`main` always stays runnable – important for the submission.

1. Click the branch name in the **status bar** (bottom left, `main`) → **Create new branch…**.
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
```
