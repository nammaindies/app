# dogbase v1 — design spec

**Date:** 2026-07-10 · **Revised:** 2026-07-12 (v2 schema + thin slicing)
**Status:** Draft for review
**Companion docs:** `dogbase-build.md` (build foundations — stack, guardrails), `foundations-conversation-2026-07-09.md` (north star). Schema visual: `assets/dogbase-schema.html` / `assets/dogbase-er-v2.mmd`.

This spec defines the **full v1 architecture** and slices it into **eight thin, independently-shippable slices**, each of which becomes its own implementation plan. It carries the stack and north star from the companion docs by reference and does not re-derive them. What this document adds:

- the v2 data model (Fable-reviewed) and its load-bearing invariant
- the architectural decisions locked on 2026-07-12
- thin slice boundaries with per-slice scope + acceptance criteria
- component interfaces / contracts
- an explicit risks / assumptions section

---

## 1. What v1 is (and is not)

**v1, fully built, delivers:** a dog is photographed (by a clinic, then by the public over WhatsApp), stored as a sighting (photos + geo + time + hashed observer); embedded asynchronously; matched against nearby individuals under a geo/time prior; linked automatically at high confidence or routed to a feeder for confirmation; named by a human when someone recognizes it; carried into a longitudinal record that a Belgaum vet can read; surfaced publicly only as an aggregate heatmap + population estimate with confidence intervals; and scored for re-ID accuracy against Soulmates ground truth.

**v1 is NOT** (from `dogbase-build.md` §9): GPU / real-time embedding; Elasticsearch / Redis / microservices; public per-dog profile or location pages; an admin console beyond pilot needs; gait/video signal; a street nose-print pipeline.

**The core bet** (unchanged): open-set individual re-identification with a strong geo/time prior. Everything else is deliberately boring plumbing so effort concentrates there.

---

## 2. Architecture at a glance

One Lightsail VM; one Postgres doing triple duty (relational + PostGIS + pgvector); Python + FastAPI; photos in S3/Lightsail buckets (key in DB, never blob); a Postgres-backed job table for async work. See `dogbase-build.md` §2–§3 for rationale.

```
intake clients (swappable, all speak POST /sighting):
  upload script · mobile webapp · WhatsApp (via hermes-agent infra) · Meta Cloud API
        │
        ▼
   Ingest API (FastAPI) ── writes ──▶ sightings + photos ──▶ jobs("embed")
                                                                  │
                                                    Embed worker (async, CPU)
                                                    writes embeddings (per model/crop)
                                                                  │
                                                    Match worker: geo-prefilter → vector-rank
                                                                  │
                                          writes match_proposals (EVERY link, incl. auto)
                                                                  │
                                     ┌────────────────────────────┴───────────────────┐
                                     ▼                                                  ▼
                        auto-confirm (score < τ_hi)                   route to feeder → confirmations
                                     └──────────────┬───────────────────────────────────┘
                                                    ▼
                       promote sightings.individual_id + match_status  (CACHE)
                                                    │
                        ┌───────────────────────────┴───────────────────────────┐
                        ▼                                                          ▼
             public_read role                                        internal (authed) role
             aggregate views only                                    individuals, clinical_records,
             heatmap + population w/ CI                               Belgaum validation harness
```

### 2.1 Two API surfaces, enforced by two Postgres roles

The public/aggregate vs. internal/individual split is a **structural boundary from the first migration**, not an application-layer promise:

- **`public_read` role** — granted access *only* to aggregate views (ward-level rollups; nothing exposing `individual_id` or raw `geog`). Powers the unauthenticated heatmap + population endpoints. A bug in a public endpoint physically cannot leak a dog's location, because its DB role cannot see one.
- **Internal (authed) role** — individual records, clinical data, the feeder confirmation flow, the Soulmates/Belgaum views, the validation harness.

### 2.1b Intake is a stable contract, clients are swappable

`POST /sighting` (photo(s) + geo + time + observer) is the intake boundary — the `IntakeAdapter` seam. Every intake client hits it and nothing downstream cares which one: an **upload script** (bulk Belgaum clinic photos), a **mobile webapp** (the dogfooding client — camera + precise browser GPS), a **WhatsApp** channel (reusing the Dognosis **hermes-agent** platform infra — Baileys-based, private/allowlisted, note anti-automation fragility), or the eventual official **Meta Cloud API** for public intake. WhatsApp photos strip EXIF, so those clients must supply geo via a shared pin and stamp `geo_source` accordingly (D7); the webapp supplies precise GPS automatically. Adding a client never touches the schema.

### 2.2 Data model (v2)

Full schema in `assets/dogbase-schema.html`. Tables: `observers`, `sightings`, `photos`, `embeddings`, `individuals`, `match_proposals`, `confirmations`, `clinical_records`, `areas`, `jobs`.

**The load-bearing invariant — caches vs. event log:**

> `sightings.individual_id` and `sightings.match_status` are **caches of the latest accepted decision**, recomputable from `match_proposals` + `confirmations`. **Every** link decision — including automatic high-confidence ones — writes a `match_proposals` row (`method`, `status`, `score`, `resolved_by=NULL` for auto). A human verdict writes a `confirmations` row (a training label; `proposal_id=NULL` means unprompted recognition — a feeder spontaneously naming a dog).

This is what makes merges, splits, threshold recalibration, and "why does the system believe sighting X is Kaju?" all answerable — and what makes recognition-as-love and recognition-as-label the same row. Consequences threaded through the slices below.

The nullable `sightings.individual_id` is the "empty slot": every sighting starts anonymous and is promoted NULL → set only on an accepted decision. Population estimation never waits on promotion; individual records do.

---

## 3. Decisions locked (2026-07-12)

These are settled; implementation plans assume them.

| # | Decision | Why |
|---|---|---|
| D1 | **Event log for all links.** `individual_id`/`match_status` are caches; `match_proposals`+`confirmations` are truth. | Auditability, merges, splits-for-free, retraining data. The one real added plumbing cost — accepted. |
| D2 | **`photos` split from `sightings`** (1→n). | Multi-shot sightings = free re-ID signal. Sighting-level match score = `min(distance)` across photos (write into the Slice 4 match contract). |
| D3 | **`embeddings` split from `photos`** (1→n by `(photo_id, model)`, `UNIQUE`). Carries `dim` + nullable `bbox`. | Re-embed back-catalog as cheap insert; head-to-head model comparison (the Belgaum harness); `bbox` keeps the multi-dog-crop door open without a future destructive migration. |
| D4 | **pgvector: untyped `vec` + per-model partial expression indexes**; store L2-normalized; **no HNSW until ~100k rows** (geo-prefilter → exact scan is faster *and* lossless at pilot scale). `halfvec` when storage bites. | An ANN index can't be built on an untyped vector column; this is the documented escape hatch. Bites at migration time if missed. |
| D5 | **UUIDv7 PKs everywhere.** | Sequential IDs leak (enumerable `individual_id` in confirmation URLs = privacy hole + free census). Also makes multi-instance clinic/street merge free. |
| D6 | **`phone_hash` = HMAC with server-side secret**, not plain SHA-256. Plus `contact_enc` (encrypted) for *consented* feeder/clinic observers. | A 10-digit space is reversible; and you can't message a hash to route proposals. Encrypted contact is a consent decision — approved. |
| D7 | **Geo/time provenance on `sightings`:** `geo_source`, `geo_accuracy_m`, `captured_at` vs `reported_at`; `phash` as forwarded-image tripwire. | WhatsApp strips EXIF; forwarded images carry the wrong dog + wrong location. The re-ID prior is only as good as its inputs. |
| D8 | **`review_status` junk gate** on sightings (`pending\|valid\|rejected`); estimator filters on it. | Crowdsourced intake = cats, memes, pranks; protects the public number. |
| D9 | **`clinical_records.sighting_id`** (nullable FK) + `external_ref`. | A clinic visit *is* a sighting; intake photo = ground truth. This column wires the Belgaum validation harness and the "sterilized 6mo ago, spotted 3 streets away" dream. |
| D10 | **Enums = `text` + CHECK**, never native Postgres enums. `updated_at` on every mutable table. `observers.deleted_at` soft-delete (DPDP), with sightings kept + observer link severed. | Cheap evolution; audit; lawful deletion. |
| D11 | **Named-by provenance:** `individuals.named_by`/`named_at`, `created_by_observer`/`created_via`. | A name with a namer is a relationship, not a label. |

**Extensibility note:** nullable columns and new attach-by-nullable-FK tables are non-breaking additions; `attrs jsonb` on `sightings`/`individuals` is the escape hatch for uncertain fields (promote to typed columns once proven). New re-ID signals (gait, nose-print, fine-tuned models) are new `embeddings.model` rows or new `match_proposals.method` values — they add evidence without re-plumbing identity. The *spine* (`sighting→photos→embeddings`, nullable `individual_id`, caches-vs-event-log) is the part deliberately locked down.

---

## 4. Slices

Thin, stacked, each independently shippable and each its own implementation plan. **This order supersedes the earlier five-milestone / "live-pipeline-first, Belgaum-last" plan** — see §5.1 for why the reorder resolves the biggest risk rather than deferring it. Slice boundaries are open to challenge at the review gate.

Every slice ships **slice 1's full migration** — the whole schema exists from day one (design for scale); later slices light up the tables they need.

### Slice 1 — Collect & store (foundation)
**Build:** full v2 migration (all tables); S3 photo storage; the `create_sighting` ingest path; a small **upload script** to load photos + GPS + time by hand (Belgaum clinic photos on day one); the `jobs` table; **two Postgres roles** (D1-adjacent guardrail) and **HMAC `phone_hash`** (D6) in from the start.
**Writes:** `observers`, `sightings`, `photos`, `jobs`. No individuals, no linking, no name, no ML, no WhatsApp.
**Done when:** migration applies clean on fresh Postgres+PostGIS+pgvector with all indexes; a sighting with ≥1 photo can be created via API/script and read back; `phone_hash` is HMAC; `public_read` role exists and cannot see `individual_id`/raw `geog`.

### Slice 2 — Mobile webapp intake (private dogfooding)
**Build:** a minimal authed mobile web page — camera capture → precise **browser geolocation** + timestamp → `POST /sighting`. Login gated to Akash first, then a small allowlist of trusted testers. `geo_source='device_gps'`, high `geo_accuracy_m` confidence. No public onboarding, no safety-reply flow (that's the public slice).
**Value:** unblocks capturing real Bangalore street dogs immediately, with the cleanest possible geo — the data that feeds manual ID (Slice 3) and the ML (Slice 4). First real intake client on the stable `POST /sighting` contract (§2.1b).
**Done when:** Akash can, from a phone, photograph a dog and have a sighting with accurate GPS + time land in `sightings`/`photos`; access is authed; observers stored with HMAC `phone_hash`.

### Slice 3 — Individuals & manual identity (Belgaum value, still no ML)
**Build:** create/read `individuals`; **manually** link a sighting to an individual and name it (`named_by`/`named_at`); write `clinical_records` (incl. `sighting_id` link, D9); the internal authed view. Manual links/names go through the event log (D1): a manual assertion writes a `confirmations` row with `proposal_id=NULL`.
**Value:** gives Soulmates a working longitudinal per-dog record immediately, with zero ML.
**Done when:** a vet can enter "this photo is Kaju, spayed today," and later retrieve Kaju's full sighting + clinical history through the internal API; every link is reconstructable from the event log.

### Slice 4 — Embed + candidate retrieval (ML core)
**Build:** embed worker (MegaDescriptor/DINOv2 via `wildlife-tools`, CPU/async) writing `embeddings` (D3, D4); the geo-prefilter → vector-rank query with sighting-level `min(distance)` aggregation (D2); the threshold decision writing `match_proposals` for **every** outcome (D1); provisional thresholds (§5.1). Self-supervised label mining (`dogbase-build.md` §6) available as a training source.
**Done when:** a new sighting produces embeddings + a ranked candidate list scoped by geo/time (verified index use via `EXPLAIN`); each decision branch writes the correct `match_proposals` (+ auto-`confirmations`) rows; thresholds are marked provisional.

### Slice 5 — Proposal → confirm loop (human-in-the-loop)
**Build:** route `proposed` matches to a feeder whose `home_geog`+`home_radius_m` covers the sighting (needs `contact_enc`, D6); confirm/reject UI (minimal — a link); promotion of the cache on accept; **merges** (rewrite `sightings`/`clinical_records` to survivor, leave events; `CHECK status='merged' ⇔ merged_into set`; one-hop max) and **splits** (a corrective `verdict='different'` — free from D1).
**Done when:** a feeder verdict writes `confirmations` (with `proposal_id`) and correctly promotes/re-points; a merge preserves full history and is auditable.

### Slice 6 — Public intake (WhatsApp)
**Build:** the public-facing intake client behind the same `POST /sighting` contract (§2.1b). First implementation reuses the Dognosis **hermes-agent** platform infra (a separate instance: own gateway container + own paired WhatsApp number + persona + a skill that forwards photos to dogbase) — Baileys-based, so **note the anti-automation fragility** (rate-limit/jitter; a dead/unpaired number breaks intake). Official **Meta Cloud API** is the more robust option for scale, deferred to this slice's plan. Plus the public-only concerns: safety-first first reply (photograph from a distance, never approach); geo via shared pin with `geo_source` stamped (D7); `review_status` junk gate (D8); face/plate/house-number stripping with documented position.
**Done when:** a WhatsApp media message yields a stored photo + sighting + embed job; first reply is the safety instruction; provenance + review fields populate; the ingest contract is unchanged from the webapp's.

### Slice 7 — Public heatmap + population estimate
**Build:** `public_read`-backed aggregate views; `GET /heatmap` (density; coverage overlay later); `GET /population?ward=…` **never returning a point number without its CI**; effort/coverage-metadata capture; mark-resight estimator; `areas` (ward polygons) populated. Sampling-bias correction **not** claimed solved (§5.2).
**Done when:** heatmap renders aggregate density (MapLibre/Leaflet); population endpoint always carries a CI; no public endpoint exposes individual identity/location.

### Slice 8 — Belgaum validation harness
**Build:** labeled set from clinic intake photos (via `clinical_records.sighting_id`, D9); score DINOv2 zero-shot, MegaDescriptor zero-shot, MegaDescriptor+geo/time prior → rank-1/rank-5, verification ROC; emit the same-dog vs different-dog distance distribution to **calibrate Slice 4's provisional thresholds**.
**Done when:** a reproducible harness outputs rank-1/5 + ROC per method and a recommended threshold set replacing the provisional values; result is stated as the scope-deciding number (given ~N nearby dogs, what accuracy can appearance hit).

---

## 5. Risks & assumptions

### 5.1 Re-ID viability — now validated *before* the public firehose
The earlier plan built the live street pipeline first and validated re-ID last, leaving match thresholds ungrounded. The reordered slices dissolve this: **Slice 1's upload script loads real Belgaum ground-truth data, Slice 4 builds the ML on it, and Slice 8 can validate/calibrate before Slice 6 opens WhatsApp to the public.** Residual: Slice 4 thresholds are still written before Slice 8 formally calibrates them, so they ship **provisional**, with an early distance-distribution sanity check as soon as the embed step exists. Pressure-release valve unchanged: this ordering is the review-gate decision.

### 5.2 Sampling bias is a real research task, not solved in v1
Opportunistic crowdsourcing over-samples friendly/photogenic/high-traffic dogs; a naive estimator is *confidently* biased, not merely noisy. Slice 7 captures effort/coverage metadata and publishes caveated estimates with CIs; it does not claim to correct the bias. Detection-probability modelling / stratification is future work. `review_status` (D8) keeps junk out of the number.

### 5.3 The geo/time prior's inputs may be garbage (WhatsApp)
EXIF stripping, shared-pin vs. capture location, message-received vs. capture time, and forwarded images all corrupt the prior the whole bet leans on. Mitigated by provenance columns (D7) and the `phash` forwarded-image tripwire — but the model must treat low-confidence provenance accordingly. Belgaum data (clean, semi-controlled) is where thresholds get calibrated precisely because street provenance is noisy.

### 5.4 WhatsApp intake is the fiddliest real-world piece
Deferred to Slice 6 and isolated behind the `POST /sighting` contract (§2.1b) — the webapp (Slice 2) is the dogfooding client, so nothing depends on WhatsApp working early. The first WhatsApp implementation reuses hermes-agent/Baileys infra, which is fragile (anti-automation blocks, unofficial API); the official Meta Cloud API is the robust path for scale, chosen in that slice's plan.

---

## 6. Guardrails (threaded as per-slice acceptance criteria)

| Guardrail | Enforced at |
|---|---|
| `phone_hash` = HMAC+secret, never raw numbers | Slice 1 |
| Two Postgres roles; `public_read` sees only aggregate views | Slice 1 (roles) + Slice 7 (views) |
| Consent-gated encrypted feeder contact | Slice 5 |
| UUIDv7 PKs (no enumerable IDs in URLs) | Slice 1 |
| DPDP soft-delete; sighting kept, observer link severed | Slice 1 (schema) + when deletion path is built |
| Webapp intake gated to an authed allowlist | Slice 2 |
| Safety-first first contact | Slice 6 |
| Face/plate/house-number stripping, documented position | Slice 6 |
| Estimates always carry uncertainty (CI) | Slice 7 |
| Open code (MIT) ≠ open data (restricted) | project-level, designed in from start |

---

## 7. Build sequence summary

| Slice | Delivers | Depends on |
|---|---|---|
| 1 | Full migration, S3, ingest API + upload script, roles, HMAC | — |
| 2 | Mobile webapp intake (dogfooding, clean GPS) | 1 |
| 3 | Individuals, manual linking + naming, clinical records, internal view | 1 |
| 4 | Embed worker, candidate retrieval, threshold decision (event log) | 1 (schema), 3 (individuals to match against) |
| 5 | Feeder proposal→confirm, merges/splits | 4 |
| 6 | Public WhatsApp intake (hermes-agent infra / Meta Cloud API), safety reply, provenance, junk gate | 1 |
| 7 | Aggregate heatmap, coverage capture, population estimate w/ CI | 1 (sightings), 4 (resight signal) |
| 8 | Belgaum re-ID validation + threshold calibration | 4 (embeddings), 3 (clinical ground truth) |

Each slice proceeds to its own `writing-plans` implementation plan, one at a time.
