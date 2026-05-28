# VECTRIX™ — AKSHAYVIPRA EL-MEC Design Platform
## VECTOMEC™ Bucket Elevator Module — Full-Stack Breakdown

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    VECTRIX™ DESIGN PLATFORM                         │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  REACT FRONTEND  (Vite + React 18 + Recharts)  :3000         │  │
│  │                                                              │  │
│  │  App.jsx  ←── module switcher (Bucket Elevator / Screw)      │  │
│  │    │                                                         │  │
│  │    └── BucketElevatorPage.jsx                                │  │
│  │          ├── InputSidebar.jsx      ← controlled inputs       │  │
│  │          ├── ElevatorSchematic.jsx ← live SVG diagram        │  │
│  │          ├── KpiGrid.jsx           ← 12 KPI cards            │  │
│  │          ├── ChartsPanel.jsx       ← 4 Recharts views        │  │
│  │          ├── OptimizerPanel.jsx    ← grid-search optimizer   │  │
│  │          ├── ComponentPanel.jsx    ← Belt/Shaft/Drive tabs   │  │
│  │          ├── ChecksPanel.jsx       ← warnings + summary      │  │
│  │          └── SaveLoadModal.jsx     ← SQLite persist          │  │
│  │                                                              │  │
│  │  hooks/useElevatorCalc.js  ← debounced state + API calls     │  │
│  │  api/client.js             ← fetch wrapper                   │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                            │ HTTP/JSON (proxied /api/*)             │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  FASTAPI BACKEND  (Uvicorn)  :8000                           │  │
│  │                                                              │  │
│  │  main.py                                                     │  │
│  │    POST /api/bucket-elevator/calculate  ← full CEMA solve    │  │
│  │    POST /api/bucket-elevator/optimize   ← grid optimizer     │  │
│  │    GET  /api/materials                  ← material DB        │  │
│  │    GET  /api/bucket-series              ← bucket DB          │  │
│  │    POST /api/designs/save               ← persist design     │  │
│  │    GET  /api/designs                    ← list designs       │  │
│  │    GET  /api/designs/{id}               ← load design        │  │
│  │    DELETE /api/designs/{id}             ← delete design      │  │
│  │                                                              │  │
│  │  calculations.py  ← CEMA physics engine                      │  │
│  │    belt_speed()          centrifugal_ratio()                  │  │
│  │    calc_capacity()       discharge_trajectory()               │  │
│  │    calc_power()          calc_tension()                       │  │
│  │    calc_shaft()          calc_bearing_life()                  │  │
│  │    select_motor()        select_bucket_auto()                 │  │
│  │    solve_elevator()      run_optimizer()                      │  │
│  │                                                              │  │
│  │  models.py    ← Pydantic request/response schemas            │  │
│  │  database.py  ← SQLite connection + schema init              │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                            │                                        │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  SQLITE DATABASE  (vectrix.db)                               │  │
│  │                                                              │  │
│  │  designs          — saved design records (all modules)       │  │
│  │    id, module, name, project, inputs_json, results_json,     │  │
│  │    notes, created_at, updated_at                             │  │
│  │                                                              │  │
│  │  custom_materials — user-added material overrides            │  │
│  │  calc_log         — optional audit trail                     │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
vectrix/
├── backend/
│   ├── main.py             ← FastAPI app, all routes
│   ├── calculations.py     ← CEMA physics engine (all formulas)
│   ├── models.py           ← Pydantic schemas
│   ├── database.py         ← SQLite init + connection
│   ├── requirements.txt
│   └── vectrix.db          ← auto-created on first run
│
└── frontend/
    ├── index.html
    ├── vite.config.js
    ├── package.json
    └── src/
        ├── main.jsx
        ├── App.jsx                      ← platform shell + module switcher
        ├── tokens.css                   ← all design tokens + shared CSS
        ├── api/
        │   └── client.js                ← fetch wrappers for all endpoints
        ├── hooks/
        │   └── useElevatorCalc.js       ← debounced state + API calls
        ├── pages/
        │   └── BucketElevatorPage.jsx   ← full page layout
        └── components/
            ├── InputSidebar.jsx         ← sections A–D input panel
            ├── ElevatorSchematic.jsx    ← live SVG cross-section
            ├── KpiGrid.jsx              ← 12-card KPI grid
            ├── ChartsPanel.jsx          ← Speed Sweep, Fill, Traj, Tension
            ├── OptimizerPanel.jsx       ← optimizer + ranked table
            ├── ComponentPanel.jsx       ← Belt/Bucket/Shaft/Drive tabs
            ├── ChecksPanel.jsx          ← engineering checks + summary
            └── SaveLoadModal.jsx        ← SQLite save/load UI
```

---

## Setup & Run

### Backend

```bash
cd vectrix/backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
# API docs: http://localhost:8000/docs
```

### Frontend

```bash
cd vectrix/frontend
npm install
npm run dev
# App: http://localhost:3000
```

---

## Key Calculations (CEMA Standard)

| Formula | Equation |
|---|---|
| Belt speed | `v = π·D·n / 60` |
| Capacity | `Q = (v/s) · Vb · η · ρ · 3.6` |
| Lift power | `P_lift = Q·H / 367` |
| Total power | `P_total = (P_lift + P_frict) · Km` |
| Belt tension | `T1 = F_eff · e^(μθ) / (e^(μθ) - 1)` |
| Shaft diameter | `d = (16T / π·τ)^(1/3)` |
| Centrifugal ratio | `CR = v² / (r·g)` |
| Bearing L10 | `L10 = (C/P)³ · 10⁶ / (60·n)` |

---

## Integrating Into Your Screw Conveyor Platform

The design database is **module-agnostic**. Your screw conveyor designs and
bucket elevator designs share the same `designs` table, keyed by `module`.

To add the bucket elevator to your existing React app:

```jsx
// In your existing platform root:
import BucketElevatorPage from "./vectrix/frontend/src/pages/BucketElevatorPage";

// Add a tab/route for it:
{activeModule === "bucket_elevator" && <BucketElevatorPage />}
```

To add to your existing FastAPI app, simply mount the router:

```python
# In your existing main.py:
from vectrix.backend.main import app as elevator_app
app.mount("/elevator", elevator_app)
```

Or copy-paste the individual route functions and calculations into your
existing backend — they are fully self-contained with no external dependencies
beyond FastAPI and Pydantic.

---

## Optimizer Objectives

| Objective | What it minimizes |
|---|---|
| `power` | Total drive power (kW) |
| `tension` | Belt tight-side tension T₁ (kN) |
| `motor` | Selected motor frame size (kW) |
| `balanced` | Composite score: power + tension + discharge quality |

Search space: 8 bucket series × 13 RPM steps × 7 fill steps = **728 candidates**  
Constraint: Q ≥ Q_required AND 0.5 ≤ v ≤ 3.0 m/s  
Returns top 20 ranked feasible solutions.

---

*VECTRIX™ · AKSHAYVIPRA EL-MEC · VECTOMEC™ Bucket Elevator Module v1.0*
