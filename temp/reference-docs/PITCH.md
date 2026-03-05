# VREDA.ai — Pitch Deck

## One-Liner
**VREDA.ai is a compiler for the scientific method** — upload a research paper, get back working code, verified results, and a manuscript. Automatically.

---

## The Problem

Scientific research has a massive execution bottleneck:

- **70% of a researcher's time** goes to low-value work: setting up environments, debugging code, cross-referencing papers, manually verifying calculations
- **Reproducibility crisis**: 70%+ of published research cannot be reproduced (Nature, 2016)
- **$28B/year wasted** on irreproducible preclinical research alone (Freedman et al., PLOS Biology)
- PhD students spend **2-4 years** learning tooling before producing original research
- Papers are written in natural language but experiments run in code — the translation is manual, error-prone, and slow

**The gap**: Scientific knowledge is trapped in PDFs. Nobody is turning papers into running, verified code at scale.

---

## The Solution: VREDA.ai

VREDA is a **General-Purpose Scientific Operating System** — a multi-agent AI pipeline that automates the full research cycle:

```
Research Question -> Literature Review -> Code Generation -> Execution -> Verification -> Discovery Pack
```

### What the user does:
1. Upload a paper (or describe a research question)
2. Click "Run Quest"
3. Wait ~10 minutes

### What VREDA delivers:
A **Discovery Pack** — a verified artifact bundle:
- **Manuscript**: Human-readable research report with citations
- **Code Repository**: Working Python/Julia code that reproduces the experiment
- **Verification Log**: Mathematical and physical validation certificate

### How it works (Four Rooms Architecture):
1. **The Strategist** decomposes the research goal into steps and estimates compute cost
2. **The Librarian** searches 200M+ papers, extracts relevant protocols and parameters
3. **The Coder** writes experiment code, executes in a secure sandbox, and self-corrects errors
4. **The Verifier** validates results against physical laws, dimensional analysis, and statistical tests

Each agent checks the others' work. The system produces *verified science*, not just chat responses.

---

## Why Now?

Three converging forces make this possible in 2026:

1. **LLMs can write research-grade code** — GPT-5, Claude 4, Gemini 2.0 can generate correct Python for complex experiments
2. **Secure sandboxes exist** — E2B, Modal provide cloud Linux environments where AI can safely execute arbitrary code
3. **200M+ papers are searchable via API** — Semantic Scholar and arXiv provide free, structured access to all of science

Two years ago, none of these existed at sufficient quality. Two years from now, someone else will build this.

---

## Market

### Primary Market: Research Acceleration
- 8M+ researchers worldwide
- $2.4T global R&D spending (UNESCO, 2024)
- Growing at 5% annually

### Target Users (Launch):
- **PhD students** — reduce time-to-first-result from months to days
- **Postdocs** — accelerate paper production for career advancement
- **Industry R&D teams** — rapid prototyping of published methods
- **Citizen scientists** — democratize access to research tools

### Expansion:
- **Biotech**: Drug discovery pipeline acceleration
- **Climate tech**: Materials simulation and validation
- **FinTech**: Quantitative research reproduction
- **Education**: Interactive research methodology teaching

---

## Competitive Landscape

| Player | What they do | What's missing |
|--------|-------------|---------------|
| **ChatGPT / Claude** | General-purpose chat | No execution, no verification, no literature search |
| **Elicit / Consensus** | Literature search | No code generation, no execution |
| **GitHub Copilot** | Code completion | No scientific context, no verification |
| **Wolfram Alpha** | Symbolic math | Not general-purpose, no paper understanding |
| **Jupyter AI** | AI in notebooks | Manual workflow, no orchestration |

**VREDA's moat**: We're the only system that connects ALL four stages — literature -> code -> execution -> verification. Everyone else does one piece.

---

## Business Model

### Phase 1: Freemium (Launch)
- **Free tier**: 5 Quests/month, basic Discovery Packs
- **Pro ($29/mo)**: 50 Quests/month, priority execution, longer papers
- **Team ($99/mo)**: Shared workspace, collaboration, API access

### Phase 2: Enterprise (6+ months post-launch)
- **Enterprise ($499+/mo)**: Custom models, private data, SSO, compliance
- **API access**: $0.50-2.00 per Quest for programmatic use

### Unit Economics (at scale):
- Cost per Quest: ~$0.30-0.50 (LLM tokens + sandbox compute)
- Revenue per Quest (Pro): ~$0.58 ($29/50 quests)
- **Gross margin: ~40-60%**

---

## Traction & Current State

### Built (as of Feb 2026):
- Full-stack web app: Next.js 16 + React 19 + Supabase
- User auth, conversation management
- PDF upload -> text extraction -> embedding -> RAG chat
- Strategist agent (generates Research Manifests)
- Secure, hardened codebase (centralized config, error handling, validation, retry logic)

### Working demo:
- Upload a research paper
- Ask questions about it with full context (RAG)
- Get a structured Research Manifest with methodology, findings, and hypotheses

### Next 6 weeks (to fundable demo):
- Literature discovery (Semantic Scholar + arXiv integration)
- Code execution sandbox (E2B)
- First end-to-end: paper in -> working code out

---

## Team

- **Founder**: Building full-time. Architecture, product, and engineering.
- **AI Co-builder**: Claude (Anthropic) — pair programming, system design, execution

### Hiring plan (post-funding):
1. **Agentic AI Engineer** — LangGraph orchestration, agent loop optimization
2. **Scientific Domain Expert (PhD)** — verification logic, domain-specific prompts
3. **Product Engineer** — frontend, UX, user research

---

## The Ask

### Pre-seed: $250K-500K
- 12 months runway for 3-person team
- Cover API costs at scale (~$500/mo for 1000 users)
- Launch public beta

### Use of funds:
- 60% — Engineering team (2 hires)
- 20% — Infrastructure (API costs, hosting)
- 10% — User research & domain validation
- 10% — Legal, compliance, ops

---

## Vision: Where This Goes

**Year 1**: Researchers upload papers, get verified code. Product-market fit.

**Year 2**: VREDA becomes the standard tool for reproducibility. Universities adopt for methodology courses. Integration with Jupyter, Overleaf, Zotero.

**Year 3**: VREDA generates novel hypotheses. Not just reproducing existing research, but proposing new experiments based on gaps in the literature. The system becomes a *co-scientist*.

**The endgame**: Every research lab has a VREDA instance. Scientific discovery is 10x faster because the AI handles execution while humans focus on what they're best at — asking the right questions.

---

## Key Metrics to Track

| Metric | What it measures | Target (6 months) |
|--------|-----------------|-------------------|
| Quests completed | Core usage | 500/month |
| Quest success rate | Quality | >70% produce valid code |
| Verification pass rate | Reliability | >80% of results verified |
| Time to Discovery Pack | Speed | <15 minutes average |
| User retention (monthly) | Stickiness | >40% |
| NPS | Satisfaction | >50 |

---

*"The Scientific Method hasn't been upgraded since Francis Bacon. VREDA is the upgrade."*
