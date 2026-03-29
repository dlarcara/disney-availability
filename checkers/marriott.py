"""
checkers/marriott.py

Marriott availability checker for Swan, Dolphin, and Swan Reserve.
Currently a placeholder — to be implemented with correct Marriott API or Playwright approach.
"""

# ── Property IDs ───────────────────────────────────────────────────────────────
MARRIOTT_PROPERTY_IDS = {
    "Swan":        "MC069",
    "Dolphin":     "MC070",
    "Swan Reserve": "MC903",
}


def check_marriott_hotels(hotels, check_in, check_out):
    """
    PLACEHOLDER — returns no availability for all Marriott hotels.
    Will be implemented once Disney checker is validated.
    """
    marriott_hotels = [h for h in hotels if h in MARRIOTT_PROPERTY_IDS]
    results = {}
    for hotel in marriott_hotels:
        print(f"    ⏭️  {hotel}: Marriott checker not yet implemented — skipping")
        results[hotel] = {
            "available": False,
            "rooms":     [],
            "error":     "Marriott checker not yet implemented",
        }
    return results
