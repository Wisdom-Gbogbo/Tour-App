"""Core logic for the Trusted Tour Planner.

Python does the facts: the catalogue, prices, totals and limits.
"""

import csv

DATA_PATH = "data/activities.csv"
CATEGORIES = ["history", "food", "culture", "nature", "arts", "talks"]

DAILY_LIMIT_HOURS = 6   # most activity hours allowed in one day
MIN_DAYS = 1
MAX_DAYS = 5
MAX_PER_DAY = 3         # default; a lower number means "fewer activities"
MAX_BUDGET = 50000      # catches typing mistakes such as an extra zero


# 1. Load the catalogue -----------------------------------------------------
def load_activities(path=DATA_PATH):
    """Read the CSV into a list of dictionaries. Returns (activities, error)."""
    activities = []
    ids_seen = []
    try:
        with open(path, newline="", encoding="utf-8-sig") as file:  # utf-8-sig ignores the hidden marker some editors add
            for row in csv.DictReader(file):
                activity = {
                    "activity_id": row["activity_id"].strip(),
                    "destination": row["destination"].strip(),
                    "name": row["name"].strip(),
                    "category": row["category"].strip().lower(),
                    "estimated_price_ghs": float(row["estimated_price_ghs"]),
                    "duration_hours": float(row["duration_hours"]),
                }
                if activity["activity_id"] in ids_seen:
                    return [], "The catalogue has a duplicate activity ID."
                if activity["estimated_price_ghs"] <= 0 or activity["duration_hours"] <= 0:
                    return [], "Prices and durations in the catalogue must be above zero."
                ids_seen.append(activity["activity_id"])
                activities.append(activity)
    except FileNotFoundError:
        return [], "Activity catalogue not found. Check that data/activities.csv exists."
    except (KeyError, ValueError):
        return [], "The catalogue has a missing column or a non-numeric price or duration."

    if len(activities) == 0:
        return [], "The catalogue is empty."
    return activities, None


def get_destinations(activities):
    """List each destination once, in alphabetical order."""
    destinations = []
    for activity in activities:
        if activity["destination"] not in destinations:
            destinations.append(activity["destination"])
    return sorted(destinations)


# 2. Validate the traveller's input -----------------------------------------
def validate_preferences(activities, destination, days, interests, budget):
    """Return a list of error messages. An empty list means the input is valid."""
    errors = []

    if destination not in get_destinations(activities):
        errors.append("Choose a destination from the list.")
    if type(days) != int or days < MIN_DAYS or days > MAX_DAYS:
        errors.append(f"Days must be a whole number from {MIN_DAYS} to {MAX_DAYS}.")
    if len(interests) == 0:
        errors.append("Pick at least one interest.")
    for interest in interests:
        if interest not in CATEGORIES:
            errors.append(f"'{interest}' is not a valid interest.")
    if type(budget) not in (int, float) or budget <= 0 or budget > MAX_BUDGET:
        errors.append(f"Budget must be more than 0 and at most GHS {MAX_BUDGET:,}.")

    return errors


# 3. Filter the catalogue ---------------------------------------------------
def get_price(activity):
    return activity["estimated_price_ghs"]


def filter_activities(activities, destination, interests):
    """Keep activities in the destination that match an interest, cheapest first."""
    matches = []
    for activity in activities:
        if activity["destination"] == destination and activity["category"] in interests:
            matches.append(activity)
    matches.sort(key=get_price)
    return matches


# 4. Build the itinerary ----------------------------------------------------
def build_itinerary(candidates, interests, days, budget, max_per_day=MAX_PER_DAY):
    """Spread activities over the days. Returns a list with one list of activities per day."""
    # Take the cheapest activity of each interest in turn, so every interest is included
    ordered = []
    for round_number in range(len(candidates)):
        for interest in interests:
            for activity in candidates:
                if activity["category"] == interest and activity not in ordered:
                    ordered.append(activity)
                    break

    plan = []
    hours = []
    for day in range(days):
        plan.append([])
        hours.append(0)

    spent = 0
    for activity in ordered:
        price = activity["estimated_price_ghs"]
        length = activity["duration_hours"]
        if spent + price <= budget and length <= DAILY_LIMIT_HOURS:
            # Choose the day with the fewest hours that still has room
            best_day = None
            for day in range(days):
                has_room = len(plan[day]) < max_per_day and hours[day] + length <= DAILY_LIMIT_HOURS
                if has_room and (best_day is None or hours[day] < hours[best_day]):
                    best_day = day
            if best_day is not None:
                plan[best_day].append(activity)
                hours[best_day] += length
                spent += price
    return plan


# 5. Cost and check the itinerary -------------------------------------------
def calculate_costs(plan, budget):
    """Total each day and the whole trip, and check the budget and the daily hour limit."""
    day_results = []
    total = 0
    for activities in plan:
        cost = 0
        hours = 0
        for activity in activities:
            cost += activity["estimated_price_ghs"]
            hours += activity["duration_hours"]
        day_results.append({"cost": cost, "hours": hours, "within_limit": hours <= DAILY_LIMIT_HOURS})
        total += cost
    return {
        "days": day_results,
        "total": total,
        "budget": budget,
        "remaining": budget - total,
        "within_budget": total <= budget,
    }


# 6. Explain an impossible request ------------------------------------------
def explain_infeasible(candidates, destination, interests, budget):
    """Say clearly why no plan was possible, without inventing an activity."""
    if len(candidates) == 0:
        return f"The catalogue has no {', '.join(interests)} activities in {destination}. Try other interests."
    cheapest = candidates[0]  # candidates are sorted cheapest first
    if budget < cheapest["estimated_price_ghs"]:
        return (
            f"No plan is possible with GHS {budget:,.0f}. The cheapest matching activity is "
            f"'{cheapest['name']}' at an estimated GHS {cheapest['estimated_price_ghs']:,.0f} per person. "
            "The catalogue has no free or cheaper activity, and I will not invent one."
        )
    return "These activities could not fit your days and budget. Try more days or a higher budget."


# Quick test: run `python planner.py` -----------------------------------------
if __name__ == "__main__":
    activities, error = load_activities()
    if error:
        print(error)
    else:
        interests = ["history", "food"]
        candidates = filter_activities(activities, "Accra", interests)

        def show_trip(title, budget, max_per_day):
            print("---", title)
            plan = build_itinerary(candidates, interests, 2, budget, max_per_day)
            if plan[0] == [] and plan[1] == []:
                print(explain_infeasible(candidates, "Accra", interests, budget))
                return
            costs = calculate_costs(plan, budget)
            for number in range(len(plan)):
                day = costs["days"][number]
                print(f"Day {number + 1}: GHS {day['cost']:.0f}, {day['hours']} h, within limit: {day['within_limit']}")
                for activity in plan[number]:
                    print("   -", activity["name"])
            print(f"Total GHS {costs['total']:.0f} of {budget}, within budget: {costs['within_budget']}")

        show_trip("Normal: GHS 600", 600, 3)
        show_trip("Revise: GHS 300", 300, 3)
        show_trip("Revise: 1 activity a day", 600, 1)
        show_trip("Infeasible: GHS 1", 1, 3)
        print("---", validate_preferences(activities, "Atlantis", 9, [], -5))