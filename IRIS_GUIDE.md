# IRIS — Interactive Research Ideation System
### Integrated into VREDA · V1 Guide

---

## What is IRIS?

IRIS is an AI-powered research hypothesis generator built on **Monte Carlo Tree Search (MCTS)**. You give it a research paper (arXiv URL) or a research topic, and it iteratively generates, reviews, retrieves literature for, and refines research hypotheses using a tree of idea nodes — each scored across 5 dimensions.

**Stack:**
- **Frontend:** Next.js 16 (React 19) — `apps/web/`
- **Backend:** Flask + Python 3.11 — `services/hypothesis-room/iris/`
- **LLM:** Gemini 2.5 Flash Lite (via LiteLLM)
- **Literature Retrieval:** ScholarQA (Semantic Scholar + full-text search over 8M+ papers)

---

## Quick Start

### 1. Start the IRIS Flask Backend

```bash
cd services/hypothesis-room/iris
source .venv/bin/activate
python server_wrapper.py
```

The backend starts on **http://127.0.0.1:5001**. You should see:
```
* Running on http://127.0.0.1:5001
```

> **Always restart the backend when you pull new changes to `app.py`.**

### 2. Start the Next.js Frontend

```bash
cd apps/web
npm run dev
```

Opens at **http://localhost:3000**

### 3. Open IRIS

- Go to `http://localhost:3000`
- Click **IRIS** from the VREDA dashboard

The left sidebar will show **● Connected** (green dot) when the Flask backend is reachable.

---

## Environment Variables

Create `apps/web/.env.local`:
```env
IRIS_BACKEND_URL=http://127.0.0.1:5001
```

Create `services/hypothesis-room/iris/.env`:
```env
GEMINI_API_KEY=your_gemini_api_key_here
SEMANTIC_SCHOLAR_API_KEY=your_s2_key_here   # optional but recommended
```

---

## UI Layout

```
┌─────────────────┬──────────────────────────────────────┬───────────────────┐
│   LEFT SIDEBAR  │         CENTER — CHAT & TOOLS        │   RIGHT SIDEBAR   │
│                 │                                      │                   │
│  Sessions tab   │  Toolbar: Auto | Generate | Retrieve │  Research Brief   │
│  Literature tab │           | Judge | History | Tree   │  Score + bars     │
│                 │           | Reset                    │  Full idea text   │
│  Hypothesis     │                                      │  Review feedback  │
│  history list   │  Current Research Proposal (sticky)  │  Fix / Ignore     │
│                 │                                      │  buttons          │
│  New Session    │  Chat messages                       │                   │
│  button         │                                      │  Generate Review  │
│                 │  Input bar                           │  Retrieve button  │
└─────────────────┴──────────────────────────────────────┴───────────────────┘
```

---

## Every Button — What It Does

### Left Sidebar

| Element | Action | Backend Call |
|---------|--------|-------------|
| **Sessions tab** | Shows all generated hypothesis versions for this session, newest first. Click any card to open full detail modal | None |
| **Literature tab** | Shows your literature search Q&A history + search bar | None |
| **Session card** | Click → opens full-detail modal with score bars, complete text, "Restore" button | None |
| **New Session** | Clears all state (idea, scores, history, chat) and resets the IRIS backend | `POST /api/reset` |
| **Search bar (Literature tab)** | Searches 8M+ papers via ScholarQA and shows synthesized answer | `POST /api/iris/retrieve-knowledge` → Flask `/api/query_knowledge` |
| **Attach (📎)** | Upload a local PDF or .txt file as paper context | `POST /api/iris/upload` → Flask `/api/upload` |

---

### Center Toolbar

#### **← VREDA**
Returns to the VREDA main dashboard. No backend call.

---

#### **Auto**
Toggles auto-generation mode. When ON, IRIS runs a **Generate** step automatically every 10 seconds, continuously exploring the MCTS tree without you needing to click anything.

- **ON:** Calls `POST /api/iris/step` with `{ action: "generate", use_mcts: true }` every 10s
- **OFF:** Stops the interval
- Pauses automatically if the backend returns an error

---

#### **Generate**
Runs one MCTS step: selects the best node in the current tree, evaluates it, expands a child using one of the actions (`generate`, `review_and_refine`, `retrieve_and_refine`, `refresh_idea`), and back-propagates the score.

- **Backend:** `POST /api/iris/step` → Flask `/api/step` with `{ action: "generate", use_mcts: true }`
- **What happens inside Flask:**
  1. UCT algorithm picks the best unexplored node
  2. Runs `generate` or `review_and_refine` or `retrieve_and_refine` via the IdeationAgent (LLM)
  3. Scores the new idea via ReviewAgent (another LLM call)
  4. Adds new node to the MCTS tree
  5. Returns `{ idea, review_scores, average_score, review_feedback }`
- **Result:** New hypothesis appears in Research Brief + Sessions history

---

#### **Retrieve**
Searches relevant literature for the current idea and refines the hypothesis with that knowledge.

- **Backend:** `POST /api/iris/step` → Flask `/api/step` with `{ action: "retrieve_and_refine", use_mcts: true }`
- **What happens inside Flask:**
  1. IdeationAgent generates a search query from the current idea
  2. ScholarQA searches 8M+ papers (Semantic Scholar API + full-text)
  3. IdeationAgent refines the idea using the retrieved paper sections
  4. ReviewAgent scores the refined idea
  5. New MCTS node created
- **Time:** ~60–120 seconds (ScholarQA pipeline is multi-step)

---

#### **Judge**
Runs a unified review of the current idea across all 5 dimensions without changing the idea itself. Populates the review panel with scores AND text feedback.

- **Backend:** `POST /api/iris/step` → Flask `/api/step` with `{ action: "judge", use_mcts: true }`
- **What happens:** ReviewAgent calls the LLM once with the full unified review prompt → parses scores + text feedback for all 5 dimensions
- **Result:** Score bars update, review feedback text appears in the bottom of the Research Brief

---

#### **History (N)**
Toggles a collapsible panel in the center column showing mini-cards for all N hypothesis versions generated this session. Click any card → full detail modal.

- No backend call
- N = number of distinct hypothesis versions generated

---

#### **Tree**
Toggles a visual representation of the MCTS tree — shows nodes, actions, and scores.

- **Backend:** `GET /api/iris/tree` → Flask `/api/tree`
- Nodes shown as expandable/collapsible tree with action labels and score values

---

#### **Reset**
Full session reset: clears all frontend state (idea, scores, chat, history) AND resets the Flask backend global state (knowledge chunks, MCTS tree, chat messages).

- **Backend:** `POST /api/iris/reset` → Flask `/api/reset`
- Use this before starting a completely new research topic

---

### Right Sidebar (Research Brief)

#### **Score: X/10**
Overall weighted average across 5 dimensions. Color coded:
- 🟢 Green: ≥ 7.0
- 🟡 Amber: 5.0–6.9
- 🔴 Red: < 5.0

#### **Score Bars (Clarity / Effectiveness / Feasibility / Impact / Novelty)**
Per-dimension scores from the last ReviewAgent call. Updated by Generate, Judge, or Fix actions.

#### **Idea Text (scrollable)**
The current hypothesis rendered as formatted sections:
- `# Title` — large heading
- `## Proposed Method` — section heading
- `## Experiment Plan` — section heading
- Bullet lists and numbered steps rendered properly

#### **Review Feedback Bar** (bottom of brief)
Shows per-aspect score + text feedback from the last Judge call.
- **← Prev / Next →** — navigate between the 5 review dimensions
- **✓ (Fix)** — sends this aspect's feedback to the IdeationAgent to improve that specific weakness
  - **Backend:** `POST /api/iris/improve-idea` → Flask `/api/improve_idea` with `{ idea, accepted_reviews: [{ aspect, feedback, score }] }`
  - Creates a new MCTS node with the improved idea
- **✕ (Ignore)** — dismisses this aspect's feedback, moves to next

#### **Generate Review** (blue button, bottom)
Same as the toolbar **Judge** button — runs unified review.
- **Backend:** `POST /api/iris/step` with `{ action: "judge" }`

#### **Retrieve** (bottom, outline button)
Same as toolbar **Retrieve** — searches literature and refines idea.
- **Backend:** `POST /api/iris/step` with `{ action: "retrieve_and_refine" }`

#### **↺ (Refresh icon)**
Generates a completely new approach to the same research goal — different methodology, different angle.
- **Backend:** `POST /api/iris/step` with `{ action: "refresh_idea" }`
- Does NOT build on the current idea — starts fresh from the root research goal

---

### Chat Input Bar

The main way to start a session or give feedback.

| Input type | What happens |
|-----------|-------------|
| **arXiv URL** (e.g. `https://arxiv.org/abs/2502.09858`) | Resets session, loads paper metadata via arXiv XML API (no PDF download), stores in IRIS knowledge, generates paper-grounded hypothesis |
| **Research topic** (plain text, no URL) | Generates hypothesis directly from the text using query-only mode |
| **Feedback text** (after first idea exists) | Improves current idea using your specific instructions |
| **New arXiv URL** (mid-session) | Resets everything and starts fresh with new paper |

**Backend flow for arXiv URL:**
1. `POST /api/iris/reset` — clear old state
2. `POST /api/iris/load-arxiv` → fetches metadata from `export.arxiv.org/api/query`
3. `POST /api/iris/chat` with `{ content: intent, force_init: true }` → generates paper-grounded hypothesis

---

## MCTS Actions Explained

IRIS uses Monte Carlo Tree Search to explore the hypothesis space. Each node in the tree is a hypothesis state with a score.

| Action | What the LLM does | Typical score change |
|--------|-------------------|---------------------|
| `generate` | Generates a new hypothesis from the research goal | Baseline |
| `generate_from_paper` | Generates grounded in the loaded paper's abstract + content | Higher relevance |
| `review_and_refine` | Reviews the 3 lowest-scoring dimensions, then refines | +0.2–0.5 |
| `retrieve_and_refine` | Retrieves 10 papers via ScholarQA, refines with evidence | +0.3–0.8 |
| `refresh_idea` | Completely new approach, sibling node in tree | Variable |
| `judge` | Review-only, no idea change | Scores only |

---

## Session Workflow (Recommended)

```
1. Paste arXiv URL in chat → "Generate novel hypotheses from this paper"
   └─ IRIS loads paper, generates first hypothesis, auto-scores it

2. Click "Generate Review" (or toolbar Judge)
   └─ See all 5 dimension scores + text feedback

3. Use "Fix" on low-scoring aspects
   └─ IRIS improves the specific weakness

4. Click "Retrieve" 
   └─ IRIS finds relevant papers and strengthens the hypothesis

5. Toggle "Auto" 
   └─ IRIS keeps exploring automatically (every 10s)

6. Browse Sessions tab on left
   └─ See all versions with scores, click to view full detail

7. Click a history version → "Restore this version"
   └─ Brings back any previous hypothesis

8. "New Session" when done
   └─ Full reset, ready for next topic
```

---

## API Reference (Flask Backend on port 5001)

| Route | Method | Purpose |
|-------|--------|---------|
| `/healthz` | GET | Health check — returns `{ status: "ok" }` |
| `/api/chat` | POST | Initial idea generation or feedback processing |
| `/api/step` | POST | MCTS action (generate/judge/retrieve_and_refine/refresh_idea/review_and_refine) |
| `/api/add_knowledge` | POST | Store paper text + abstract in knowledge store |
| `/api/knowledge` | GET | List all loaded knowledge chunks |
| `/api/reset` | POST | Clear all session state |
| `/api/tree` | GET | Get MCTS tree as JSON |
| `/api/idea` | GET | Get current idea text |
| `/api/improve_idea` | POST | Improve idea with accepted review feedback |
| `/api/upload` | POST | Upload PDF/text file as paper context |

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| **● Connecting…** (amber dot) | Flask backend not running | Run `python server_wrapper.py` |
| **MCTS exploration already in progress** | Previous step still running | Wait a few seconds, or click Reset |
| **Score: 1.0/10 on all dimensions** | Error occurred during generation | Check Flask terminal for traceback, restart backend |
| **Blank Research Brief** | Idea returned empty from LLM | Click Generate again — LLM occasionally returns empty |
| **Retrieve error: No retrieved knowledge** | Old code path — should be fixed in V1 | Restart frontend (`npm run dev`) |
| **Paper load error: Not a valid arXiv URL** | URL format wrong | Use `https://arxiv.org/abs/XXXX.XXXXX` format |
| **Steps take forever** | `retrieve_and_refine` running ScholarQA | Normal — can take 60–120s, check Flask logs |
| **Ideas not grounded in paper** | Backend not restarted after fix | Restart Flask backend |

---

## Project Structure

```
vreda-iris-integrated/
├── apps/web/                          # Next.js frontend
│   └── src/
│       ├── app/api/iris/              # Next.js proxy routes to Flask
│       │   ├── chat/route.ts          # /api/iris/chat
│       │   ├── step/route.ts          # /api/iris/step (MCTS actions)
│       │   ├── load-arxiv/route.ts    # /api/iris/load-arxiv
│       │   ├── reset/route.ts         # /api/iris/reset
│       │   ├── improve-idea/route.ts  # /api/iris/improve-idea
│       │   └── ...
│       ├── components/iris/
│       │   └── IrisPage.tsx           # Main IRIS UI component
│       ├── lib/
│       │   └── iris-proxy.ts          # Proxy helper (Flask ↔ Next.js)
│       └── types/iris.ts              # TypeScript types
│
└── services/hypothesis-room/iris/     # Flask backend
    ├── app.py                         # All Flask routes + MCTS orchestration
    ├── server_wrapper.py              # Entry point (/healthz + CORS)
    ├── config/config.yaml             # Models, MCTS params, logging
    └── src/
        ├── agents/
        │   ├── ideation.py            # IdeationAgent — LLM hypothesis generation
        │   ├── review.py              # ReviewAgent — 5-dimension scoring
        │   ├── prompts.py             # All LLM prompt templates
        │   └── structured_review.py  # Per-aspect structured review
        ├── mcts/
        │   ├── node.py                # MCTSNode + MCTSState
        │   └── tree.py                # MCTS algorithm (UCT)
        └── retrieval_api/
            └── scholarqa/             # ScholarQA literature retrieval pipeline
```

---

## Git Push Checklist

Before pushing, verify these files are NOT committed (already in `.gitignore`):

```bash
# Check what will be committed
git status

# These should NOT appear in git status:
# - apps/web/.env.local          (API keys)
# - services/.../iris/.env       (API keys)
# - apps/web/node_modules/       (dependencies)
# - apps/web/.next/              (build cache)
# - services/.../iris/.venv/     (Python venv)
# - services/.../iris/uploads/   (user uploads)
# - services/.../iris/logs/      (runtime logs)
# - services/.../iris/results/   (generated results)
```

If `.env` files show up: `git rm --cached path/to/.env`

**Recommended commit message for V1:**
```
feat: IRIS V1 — paper-grounded hypothesis generation with MCTS

- Full IRIS UI: sessions sidebar, score bars, review feedback panel
- arXiv paper loading via metadata API (no PDF download)  
- MCTS exploration: generate, judge, retrieve_and_refine, refresh_idea
- Hypothesis history with full-detail modal
- IdeaRenderer: formatted markdown output (no more raw JSON)
- Fixed: file_type bug (paper context was never used)
- Fixed: Retrieve button routing to /api/step
- Fixed: review_feedback now returned from all endpoints
- Fixed: NameError time variable in ScholarQA utils
```
