"""Scoring criteria for preparedness actions (all benefit-type, scored 1-5)."""

CRITERIA = {
    "impact": "Expected reduction in waterlogging damage / disruption",
    "urgency": "How time-critical the action is once rain is forecast",
    "lead_time": "How quickly it can be executed (5 = hours, 1 = weeks)",
    "affordability": "Inverse of cost (5 = negligible, 1 = very expensive)",
    "feasibility": "Institutional / logistical ease of execution",
}
