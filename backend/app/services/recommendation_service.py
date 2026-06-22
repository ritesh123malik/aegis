def generate_recommendations(
    disruption_class: str,
    duration_min: float,
    corridor: str,
    event_cause: str,
    requires_road_closure: bool
) -> dict:
    # 1. Officers
    officers = 1
    # Fallback/Default mapped from disruption_class
    if disruption_class == "Critical":
        officers = 8
    elif disruption_class == "High":
        officers = 5
    elif disruption_class == "Medium":
        officers = 3

    if requires_road_closure:
        officers += 3

    # Scale slightly with duration (over 8 hours)
    if duration_min and duration_min > 480:
        officers += 2

    # 2. Barricades
    barricades = []
    if requires_road_closure or disruption_class in ["High", "Critical"]:
        barricades.append({"type": "Type-A Water-filled", "quantity": 15})
        barricades.append({"type": "Steel barricades", "quantity": 10})
    else:
        barricades.append({"type": "Traffic Cones", "quantity": 10})

    # 3. Diversions
    diversions = []
    if requires_road_closure:
        diversions.append({
            "from_intersection": f"{corridor} Entry" if corridor else "Disruption Point Entry",
            "to_intersection": f"{corridor} Exit" if corridor else "Disruption Point Exit",
            "status": "Active"
        })

    # 4. Signals requiring attention
    signals = []
    if corridor and corridor != "Non-corridor":
        signals.append(f"{corridor} Intersection 1")
        signals.append(f"{corridor} Intersection 2")

    return {
        "recommended_officers": officers,
        "recommended_barricades": barricades,
        "recommended_diversions": diversions,
        "signals_requiring_attention": signals
    }
