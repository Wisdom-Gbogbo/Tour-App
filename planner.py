"""Core logic for the Trusted Tour Planner.

Python owns the facts: catalogue lookups, costs, totals and limit checks.
The AI only writes the wording around what these functions return.
"""

from pathlib import Path

import pandas as pd

DATA_PATH = Path("data/activities.csv")
REQUIRED_COLUMNS = [
    "activity_id",
    "destination",
    "name",
    "category",
    "estimated_price_ghs",
    "duration_hours",
]
CATEGORIES = ["history", "food", "culture", "nature", "arts", "talks"]

DAILY_LIMIT_HOURS = 6   # maximum activity hours per day
MIN_DAYS = 1
MAX_DAYS = 5
DEFAULT_MAX_PER_DAY = 3  # lower this to ask for "fewer activities"
MAX_BUDGET_GHS = 50000   # catches typos such as an extra zero


# ---------------------------------------------------------------------------
# 1. Load the catalogue
# ---------------------------------------------------------------------------
def load_activities(path=DATA_PATH):
    """Read the curated catalogue and make sure it is clean and complete."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Activity catalogue not found at {path}. "
            "Check that data/activities.csv exists."
        )
    try:
        df = pd.read_csv(path)
    except Exception as exc:
        raise ValueError(
            "The activity catalogue could not be read. Check the CSV format."
        ) from exc

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"The catalogue is missing columns: {', '.join(missing)}")

    df = df[REQUIRED_COLUMNS].copy()
    df["estimated_price_ghs"] = pd.to_numeric(df["estimated_price_ghs"], errors="coerce")
    df["duration_hours"] = pd.to_numeric(df["duration_hours"], errors="coerce")
    if df.isna().any().any():
        raise ValueError("The catalogue has empty or non-numeric values. Check every row.")
    if df["activity_id"].duplicated().any():
        raise ValueError("The catalogue has duplicate activity IDs.")
    if (df["estimated_price_ghs"] <= 0).any() or (df["duration_hours"] <= 0).any():
        raise ValueError("Prices and durations in the catalogue must be above zero.")

    df["destination"] = df["destination"].astype(str).str.strip()
    df["category"] = df["category"].astype(str).str.strip().str.lower()
    return df


# ---------------------------------------------------------------------------
# 2. Validate the traveller's preferences
# ---------------------------------------------------------------------------
def validate_preferences(activities, destination, days, interests, budget):
    """Return a list of error messages. An empty list means the input is valid."""
    errors = []

    destinations = sorted(activities["destination"].unique())
    if destination not in destinations:
        errors.append(f"Choose a destination from the catalogue: {', '.join(destinations)}.")

    if isinstance(days, bool) or not isinstance(days, int) or not MIN_DAYS <= days <= MAX_DAYS:
        errors.append(f"Number of days must be a whole number from {MIN_DAYS} to {MAX_DAYS}.")

    if not interests:
        errors.append("Pick at least one interest.")
    elif any(i not in CATEGORIES for i in interests):
        errors.append(f"Interests must come from: {', '.join(CATEGORIES)}.")

    try:
        budget_value = float(budget)
        if not 0 < budget_value <= MAX_BUDGET_GHS:
            errors.append(f"Budget must be more than GHS 0 and at most GHS {MAX_BUDGET_GHS:,}.")
    except (TypeError, ValueError):
        errors.append("Budget must be a number.")

    return errors


# ---------------------------------------------------------------------------
# 3. Filter the catalogue
# ---------------------------------------------------------------------------
def filter_activities(activities, destination, interests):
    """Keep only catalogue activities in the destination and chosen categories."""
    mask = (activities["destination"] == destination) & (
        activities["category"].isin(interests)
    )
    return (
        activities[mask]
        .sort_values(["estimated_price_ghs", "duration_hours"])
        .reset_index(drop=True)
    )


# ---------------------------------------------------------------------------
# 4. Build the itinerary
# ---------------------------------------------------------------------------
def build_itinerary(
    candidates,
    days,
    budget,
    daily_limit=DAILY_LIMIT_HOURS,
    max_per_day=DEFAULT_MAX_PER_DAY,
):
    """Spread catalogue activities over the days.

    Returns a list with one entry per day; each entry is a list of activity dicts.
    Activities are taken in turn from each category (cheapest first) so every
    interest is represented, and each goes on the day with the most free time.
    """
    # One queue per category, cheapest first (candidates are already sorted by price)
    queues = [
        group.to_dict("records")
        for _, group in candidates.groupby("category", sort=False)
    ]
    ordered = []
    while any(queues):
        for queue in queues:
            if queue:
                ordered.append(queue.pop(0))

    plan = [[] for _ in range(days)]
    hours = [0.0] * days
    spent = 0.0

    for activity in ordered:
        price = activity["estimated_price_ghs"]
        length = activity["duration_hours"]
        if spent + price > budget or length > daily_limit:
            continue
        open_days = [
            d for d in range(days)
            if len(plan[d]) < max_per_day and hours[d] + length <= daily_limit
        ]
        if not open_days:
            continue
        day = min(open_days, key=lambda d: hours[d])
        plan[day].append(activity)
        hours[day] += length
        spent += price

    return plan


# ---------------------------------------------------------------------------
# 5. Cost and check the itinerary
# ---------------------------------------------------------------------------
def calculate_costs(plan, budget, daily_limit=DAILY_LIMIT_HOURS):
    """Total each day and the whole trip, and check the budget and hour limit."""
    day_summaries = []
    for number, activities in enumerate(plan, start=1):
        cost = sum(a["estimated_price_ghs"] for a in activities)
        hours = sum(a["duration_hours"] for a in activities)
        day_summaries.append(
            {
                "day": number,
                "activity_ids": [a["activity_id"] for a in activities],
                "cost_ghs": cost,
                "hours": hours,
                "within_limit": hours <= daily_limit,
            }
        )

    total = sum(d["cost_ghs"] for d in day_summaries)
    return {
        "days": day_summaries,
        "total_cost_ghs": total,
        "budget_ghs": budget,
        "remaining_ghs": budget - total,
        "within_budget": total <= budget,
        "daily_limit_hours": daily_limit,
        "all_days_within_limit": all(d["within_limit"] for d in day_summaries),
    }


# ---------------------------------------------------------------------------
# 6. Explain an infeasible request
# ---------------------------------------------------------------------------
def explain_infeasible(candidates, destination, interests, budget,
                       daily_limit=DAILY_LIMIT_HOURS):
    """Give a clear reason when no plan can be built, without inventing activities."""
    if candidates.empty:
        return (
            f"The catalogue has no {', '.join(interests)} activities in {destination}. "
            "Try different interests or another destination."
        )

    usable = candidates[candidates["duration_hours"] <= daily_limit]
    if usable.empty:
        return (
            f"Every matching activity is longer than the {daily_limit}-hour daily limit, "
            "so none can be scheduled. Try different interests."
        )

    cheapest = usable.loc[usable["estimated_price_ghs"].idxmin()]
    if budget < cheapest["estimated_price_ghs"]:
        return (
            f"No plan is possible with a budget of GHS {budget:,.0f}. The cheapest matching "
            f"activity in the catalogue is '{cheapest['name']}' at an estimated "
            f"GHS {cheapest['estimated_price_ghs']:,.0f} per person. The catalogue has no "
            "cheaper or free activities, and I will not invent one. "
            "Try a higher budget."
        )

    return (
        "The matching activities could not be fitted within your days, budget and "
        "daily limit. Try more days, a higher budget or more interests."
    )


# ---------------------------------------------------------------------------
# Quick self-test: run `python planner.py`
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    catalogue = load_activities()
    print(f"Loaded {len(catalogue)} activities\n")

    def try_trip(destination, days, interests, budget, max_per_day=DEFAULT_MAX_PER_DAY):
        errors = validate_preferences(catalogue, destination, days, interests, budget)
        if errors:
            print("Invalid input:", errors)
            return
        candidates = filter_activities(catalogue, destination, interests)
        plan = build_itinerary(candidates, days, budget, max_per_day=max_per_day)
        if not any(plan):
            print(explain_infeasible(candidates, destination, interests, budget))
            return
        summary = calculate_costs(plan, budget)
        for day, info in zip(plan, summary["days"]):
            names = [a["name"] for a in day] or ["(no activities)"]
            print(f"Day {info['day']}: {info['cost_ghs']:.0f} GHS, {info['hours']} h, "
                  f"within limit: {info['within_limit']}")
            for n in names:
                print("   -", n)
        print(f"Total: {summary['total_cost_ghs']:.0f} of {budget} GHS, "
              f"within budget: {summary['within_budget']}")

    print("--- Normal: 2 days Accra, history + food, GHS 600 ---")
    try_trip("Accra", 2, ["history", "food"], 600)
    print("\n--- Revision: same trip, GHS 300 ---")
    try_trip("Accra", 2, ["history", "food"], 300)
    print("\n--- Revision: fewer activities (max 1 per day) ---")
    try_trip("Accra", 2, ["history", "food"], 600, max_per_day=1)
    print("\n--- Infeasible: GHS 1 ---")
    try_trip("Accra", 2, ["history", "food"], 1)
    print("\n--- Invalid input ---")
    try_trip("Atlantis", 9, [], -5)

