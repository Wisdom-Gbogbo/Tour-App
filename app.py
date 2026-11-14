import streamlit as stl

from ai_client import apply_revision, read_revision, write_reasons
from planner import (
    CATEGORIES,
    DAILY_LIMIT_HOURS,
    MAX_DAYS,
    MAX_PER_DAY,
    build_itinerary,
    calculate_costs,
    explain_infeasible,
    filter_activities,
    get_destinations,
    load_activities,
    validate_preferences,
)

stl.set_page_config(page_title="Trusted Tour Planner", page_icon=":compass:")

ESTIMATE_NOTE = "Prices are illustrative per-person estimates from a sample catalogue, not live listings."
EXCLUSION_NOTE = (
    "The budget covers listed activities only. Transport, meals outside listed experiences and "
    "accommodation are not included. Please verify opening hours, availability and travel times "
    "before you visit."
)


@stl.cache_data  # the catalogue is public and never changes, so load it once and remember it
def get_activities():
    return load_activities()


activities, load_error = get_activities()
if load_error:
    stl.error(load_error)
    stl.stop()


# Functions -------------------------------------------------------------------
def build_trip(prefs):
    """Validate, plan, cost, and ask the AI for wording. Returns a list of error messages."""
    errors = validate_preferences(
        activities, prefs["destination"], prefs["days"], prefs["interests"], prefs["budget"]
    )
    if len(errors) > 0:
        return errors

    candidates = filter_activities(activities, prefs["destination"], prefs["interests"])
    plan = build_itinerary(candidates, prefs["interests"], prefs["days"], prefs["budget"], prefs["max_per_day"])

    count = 0
    for day in plan:
        count += len(day)

    # Session state keeps our progress when Streamlit reruns the script
    stl.session_state["prefs"] = prefs
    stl.session_state["plan"] = plan
    stl.session_state["reasons"] = None
    stl.session_state["notice"] = ""
    stl.session_state["infeasible"] = ""
    stl.session_state["costs"] = None

    if count == 0:
        stl.session_state["infeasible"] = explain_infeasible(
            candidates, prefs["destination"], prefs["interests"], prefs["budget"]
        )
        return []

    stl.session_state["costs"] = calculate_costs(plan, prefs["budget"])
    with stl.spinner("Writing your itinerary..."):
        reasons, ai_error = write_reasons(prefs["interests"], plan)
    stl.session_state["reasons"] = reasons
    if ai_error:
        stl.session_state["notice"] = ai_error + " Showing the plan without AI wording."
    return []


def make_text(prefs, plan, costs, reasons):
    """Build the text for the download file."""
    lines = []
    lines.append("TRUSTED TOUR PLANNER")
    lines.append(f"{prefs['days']} day(s) in {prefs['destination']} | Interests: {', '.join(prefs['interests'])}")
    lines.append(f"Activities budget: GHS {prefs['budget']:,.0f} per person")
    lines.append(ESTIMATE_NOTE)
    lines.append("")
    for number in range(len(plan)):
        day = costs["days"][number]
        lines.append(f"DAY {number + 1}: GHS {day['cost']:,.0f}, {day['hours']} hours")
        if len(plan[number]) == 0:
            lines.append("  No activities fit this day.")
        for activity in plan[number]:
            lines.append(
                f"  [{activity['activity_id']}] {activity['name']}: "
                f"GHS {activity['estimated_price_ghs']:,.0f}, {activity['duration_hours']} hours"
            )
            if reasons:
                lines.append("      " + reasons[activity["activity_id"]])
        lines.append("")
    lines.append(f"TOTAL: GHS {costs['total']:,.0f} of GHS {costs['budget']:,.0f} (GHS {costs['remaining']:,.0f} remaining)")
    if reasons:
        lines.append("")
        lines.append(reasons["summary"])
    lines.append("")
    lines.append(EXCLUSION_NOTE)
    return "\n".join(lines)


def show_trip():
    """Display the saved plan, with the costs and checks that Python calculated."""
    prefs = stl.session_state["prefs"]
    plan = stl.session_state["plan"]
    costs = stl.session_state["costs"]
    reasons = stl.session_state["reasons"]

    stl.subheader(f"{prefs['days']} day(s) in {prefs['destination']}")
    stl.caption(
        f"Interests: {', '.join(prefs['interests'])} | Budget: GHS {prefs['budget']:,.0f} per person "
        f"| Up to {prefs['max_per_day']} activities a day"
    )

    if stl.session_state["infeasible"] != "":
        stl.warning(stl.session_state["infeasible"])
        stl.caption(EXCLUSION_NOTE)
        return

    if stl.session_state["notice"] != "":
        stl.warning(stl.session_state["notice"])

    for number in range(len(plan)):
        day = costs["days"][number]
        stl.markdown(f"**Day {number + 1}** - GHS {day['cost']:,.0f}, {day['hours']} hours")
        if day["within_limit"]:
            stl.caption(f"Within the {DAILY_LIMIT_HOURS}-hour daily limit")
        else:
            stl.error(f"Over the {DAILY_LIMIT_HOURS}-hour daily limit")
        if len(plan[number]) == 0:
            stl.write("No activities fit this day.")
        for activity in plan[number]:
            stl.write(
                f"- [{activity['activity_id']}] {activity['name']}: "
                f"GHS {activity['estimated_price_ghs']:,.0f}, {activity['duration_hours']} hours"
            )
            if reasons:
                stl.caption(reasons[activity["activity_id"]])

    column1, column2, column3 = stl.columns(3)
    column1.metric("Total cost", f"GHS {costs['total']:,.0f}")
    column2.metric("Budget", f"GHS {costs['budget']:,.0f}")
    column3.metric("Remaining", f"GHS {costs['remaining']:,.0f}")
    if costs["within_budget"]:
        stl.success("The plan is within your budget.")
    else:
        stl.error("The plan is over your budget.")

    if reasons:
        stl.info(reasons["summary"])
    stl.caption(ESTIMATE_NOTE)
    stl.caption(EXCLUSION_NOTE)

    stl.download_button(
        "Download itinerary (.txt)",
        make_text(prefs, plan, costs, reasons),
        file_name="trusted_tour_itinerary.txt",
    )


# Page ------------------------------------------------------------------------
stl.title("Trusted Tour Planner")
stl.write("Plan a trip from a small, curated catalogue of activities in and around Accra.")
stl.markdown(
    "1. Fill in the form and click **Build itinerary**.\n"
    "2. Check the costs and daily hours that Python calculated.\n"
    "3. Ask for a change, such as a lower budget or fewer activities.\n"
    "4. Download your itinerary."
)
stl.info("Example: 2 days in Accra, interested in history and food, with an activities budget of GHS 600 per person.")

destinations = get_destinations(activities)
destination = stl.selectbox("Destination", destinations, index=destinations.index("Accra"), key="destination")
days = stl.number_input("Number of days", min_value=1, max_value=MAX_DAYS, value=2, step=1, key="days")
interests = stl.multiselect("Interests", CATEGORIES, default=["history", "food"], key="interests")
budget = stl.number_input(
    "Activities budget per person (GHS)", min_value=0, max_value=100000, value=600, step=50, key="budget"
)

if stl.button("Build itinerary", type="primary"):
    stl.session_state["message"] = ""
    errors = build_trip(
        {"destination": destination, "days": days, "interests": interests, "budget": budget, "max_per_day": MAX_PER_DAY}
    )
    for error in errors:
        stl.error(error)

if "prefs" in stl.session_state:
    if stl.session_state.get("message", "") != "":
        stl.info(stl.session_state["message"])
    show_trip()

    stl.subheader("Revise your plan")
    request = stl.text_input(
        "Describe a change", placeholder="e.g. make it cheaper, or only 1 activity a day", key="revision_text"
    )
    if stl.button("Revise plan"):
        changes, error = read_revision(request)
        if error:
            stl.session_state["message"] = error
        else:
            new_prefs = apply_revision(stl.session_state["prefs"], changes)
            if new_prefs == stl.session_state["prefs"]:
                stl.session_state["message"] = "I could not find a change I can apply. Try: lower the budget to GHS 400."
            else:
                errors = build_trip(new_prefs)
                if len(errors) > 0:
                    stl.session_state["message"] = " ".join(errors)
                else:
                    stl.session_state["message"] = "Plan updated. Costs and checks were recalculated."
        stl.rerun()

    if stl.button("Reset"):
        for key in list(stl.session_state.keys()):
            del stl.session_state[key]
        stl.rerun()