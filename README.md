# Trusted Tour Planner

A Streamlit app that builds a day-by-day itinerary from a small, curated catalogue of activities in and around Accra, Ghana. The traveller sets preferences, gets a costed plan, then revises it in plain language (for example "make it cheaper") and downloads the result.

**Live app:** _add your Streamlit link here after deployment_
**GitHub:** https://github.com/Wisdom-Gbogbo/Tour-App
**AI provider:** OpenAI (default model `gpt-4o-mini`)

## How it works

Python does the facts and the AI does the wording.

- **Python** (`planner.py`) loads the catalogue, validates input, picks activities, adds up daily and trip costs, and checks the budget and the 6-hour daily limit.
- **AI** (`ai_client.py`) writes one short sentence per activity explaining why it fits the traveller's interests, plus a summary. It also reads revision requests like "lower the budget to GHS 400" into a small set of changes, which Python checks and applies.
- The AI never chooses activities and never writes prices or totals. Its text is rejected if it contains any number, and if it fails the check the app shows the plan without AI wording.

## Features

- Preference form: destination, number of days, interests and activities budget per person, all validated.
- Plans use only activities in `data/activities.csv`.
- Day-by-day itinerary with Python-calculated daily and trip costs and a daily-hours check.
- Revisions (lower budget, fewer activities, more days, different interests) that recalculate every total.
- A clear explanation when no plan is possible, without inventing an activity.
- Downloadable `.txt` itinerary with estimate and exclusion notes.
- Reset button; progress is kept in session state between reruns.

## Setup (Windows)

Requires Python 3.10 or newer and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/Wisdom-Gbogbo/Tour-App.git
cd Tour-App
uv venv
.venv\Scripts\activate
uv pip install -r requirements.txt
```

Create a file named `.env` in the project folder (copy `.env.example`) and add your OpenAI key:

```
OPENAI_API_KEY=your-key-here
```

Never commit `.env`; `.gitignore` already excludes it. When deployed, put the key in Streamlit secrets instead.

## Run

```bash
streamlit run app.py
```

To test the planning logic alone, without the AI: `python planner.py`

## Sample inputs

| Check | Input | Expected result |
|---|---|---|
| Normal journey | Accra, 2 days, history + food, GHS 600 | 4 activities, GHS 530, days of 3.5 h and 5 h, within budget and limit |
| Revision | After the plan above, type "make it cheaper" | Budget becomes GHS 480 and the plan and totals update together |
| Fewer activities | Type "only 1 activity a day" | At most one activity per day, totals recalculated |
| No feasible plan | Accra, history + food, GHS 1 | Explains the cheapest activity is GHS 100; no free activity is invented |
| Invalid input | No interests selected | "Pick at least one interest." |
| API failure | Remove or change `OPENAI_API_KEY`, then build a plan | Friendly warning; the Python-calculated plan still appears |

## Project files

| File | Purpose |
|---|---|
| `app.py` | Streamlit screens: form, itinerary, revision, reset, download |
| `planner.py` | Catalogue loading, validation, planning, costing, limit checks |
| `ai_client.py` | OpenAI calls, checks on AI output, revision parsing |
| `data/activities.csv` | Curated sample catalogue (21 activities) |
| `requirements.txt` | Python packages |
| `.env.example` | Shows the variable name for the API key |

## Boundaries

- Prices are **fictional, illustrative per-person estimates**, not live travel listings.
- The budget covers listed activities only. Transport, meals outside listed experiences and accommodation are excluded.
- The app does not know opening hours, live availability or travel times. Please verify details before visiting.

## Known limitations

- The catalogue is small (21 activities in Accra, Koforidua, Volta and Aburi), so some interest and budget combinations have few options.
- Every activity is treated as costing one fixed price per person, and all activities are assumed to fit in any order on a day.
- The AI check blocks numbers but cannot detect a sentence that mentions a place outside the catalogue. That is why the plan itself is always built by Python.
- The planner picks the cheapest activities first within each interest, so it does not search for the "best" combination for the budget.
- Revision requests are read one at a time, so the app does not remember earlier revision messages.
- After a revision, the form at the top still shows the original inputs; clicking **Build itinerary** starts again from the form.

## Contributor

Solo project by Wag (GitHub: Wisdom-Gbogbo): all code, catalogue, testing and deployment.