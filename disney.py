"""
checkers/disney.py

Playwright-based availability checker for Disney-owned resorts.
Navigates to each resort's availability page, intercepts the API response,
and extracts room types, rates, and total prices.
"""

import asyncio
import json
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# ── Resort URL slugs ───────────────────────────────────────────────────────────
RESORT_SLUGS = {
    "Contemporary":       "contemporary-resort",
    "Yacht Club":         "yacht-club-resort",
    "Beach Club":         "beach-club-resort",
    "Polynesian":         "polynesian-village-resort",
    "Grand Floridian":    "grand-floridian-resort-and-spa",
    "Wilderness Lodge":   "wilderness-lodge-resort",
    "Animal Kingdom Lodge": "animal-kingdom-lodge",
    "Caribbean Beach":    "caribbean-beach-resort",
    "Pop Century":        "pop-century-resort",
    "Art of Animation":   "art-of-animation-resort",
    "Old Key West":       "old-key-west-resort",
    "Saratoga Springs":   "saratoga-springs-resort-and-spa",
    "BoardWalk":          "boardwalk-inn",
}

BASE_URL = "https://disneyworld.disney.go.com"

# Selector that appears when rooms are loaded
ROOM_CARD_SELECTOR = "[data-testid='room-card'], .roomCard, .resort-room-card, .room-offer-card"
NO_AVAIL_SELECTOR  = ".no-availability, .noAvailability, [data-testid='no-availability']"


async def check_resort(resort_name, check_in, check_out, adults=2):
    """
    Check a single Disney resort for availability.
    Returns a dict:
      {
        "available": bool,
        "rooms": [ { "name": str, "avg_per_night": str, "total": str } ],
        "error": str | None
      }
    """
    slug = RESORT_SLUGS.get(resort_name)
    if not slug:
        return {"available": False, "rooms": [], "error": f"No URL slug for '{resort_name}'"}

    url = (
        f"{BASE_URL}/resorts/{slug}/rates-rooms/"
        f"?checkIn={check_in}&checkOut={check_out}"
        f"&adults={adults}&children=0"
    )

    api_url_fragment = f"/wdw-resorts-details-api/api/v1/resort/{slug}/availability-and-prices/"
    captured_response = {}

    print(f"    🌐 Checking {resort_name} via Playwright...")
    print(f"       URL: {url}")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
            )
            page = await context.new_page()

            # Intercept the availability API response
            async def handle_response(response):
                if api_url_fragment in response.url:
                    try:
                        body = await response.json()
                        captured_response["data"] = body
                        print(f"       ✅ Captured API response for {resort_name}")
                    except Exception as e:
                        print(f"       ⚠️  Could not parse API response: {e}")

            page.on("response", handle_response)

            # Navigate and wait for network to settle
            try:
                await page.goto(url, wait_until="networkidle", timeout=60000)
            except PlaywrightTimeout:
                print(f"       ⚠️  Page load timed out for {resort_name}, checking captured data...")

            # Give interceptor a moment to finish
            await asyncio.sleep(3)
            await browser.close()

    except Exception as e:
        print(f"       ❌ Playwright error for {resort_name}: {e}")
        return {"available": False, "rooms": [], "error": str(e)}

    # ── Parse captured API response ───────────────────────────────────────────
    data = captured_response.get("data")
    if not data:
        print(f"       — No API response captured for {resort_name} (likely not open for these dates)")
        return {"available": False, "rooms": [], "error": None}

    rooms = parse_rooms(data)
    available = len(rooms) > 0

    print(f"       {'🎉' if available else '—'} {resort_name}: {len(rooms)} room type(s) found")
    return {"available": available, "rooms": rooms, "error": None}


def parse_rooms(data):
    """
    Extract room types, average nightly rate, and total price from the API response.
    Looks for offer objects that contain pricing and room components.
    """
    rooms = []
    seen_ids = set()

    # The API returns a flat dict of offer objects keyed by ID
    # We look for any object that has components with type="room" and pricing
    for key, offer in data.items():
        if not isinstance(offer, dict):
            continue

        # Must have room component
        components = offer.get("components", [])
        is_room = any(c.get("type") == "room" for c in components)
        if not is_room:
            continue

        # Must have pricing
        display_price = offer.get("displayPrice", {})
        base_price    = display_price.get("basePrice", {})
        total_price   = offer.get("totalPrice", {})

        if not base_price.get("subtotal"):
            continue

        offer_id = offer.get("id", key)
        if offer_id in seen_ids:
            continue
        seen_ids.add(offer_id)

        # Get room name from packageName or code
        name = offer.get("packageName") or offer.get("code") or f"Room {offer_id}"

        avg_per_night = f"${float(base_price['subtotal']):,.2f}"
        currency      = base_price.get("currency", "USD")

        total = ""
        if total_price.get("total"):
            total_val = float(total_price["total"])
            tax_val   = float(total_price.get("tax", 0))
            total     = f"${total_val:,.2f} (incl. ${tax_val:,.2f} tax)"

        rooms.append({
            "name":          name,
            "avg_per_night": avg_per_night,
            "total":         total,
            "currency":      currency,
        })

    # Sort by price
    rooms.sort(key=lambda r: float(r["avg_per_night"].replace("$", "").replace(",", "")))
    return rooms


async def check_disney_hotels(hotels, check_in, check_out):
    """
    Check multiple Disney resorts concurrently (up to 3 at a time).
    Returns dict of {hotel_name: result}
    """
    disney_hotels = [h for h in hotels if h in RESORT_SLUGS]
    if not disney_hotels:
        return {}

    results = {}
    # Run in small batches to avoid overloading
    batch_size = 3
    for i in range(0, len(disney_hotels), batch_size):
        batch = disney_hotels[i:i + batch_size]
        tasks = [check_resort(h, check_in, check_out) for h in batch]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        for hotel, result in zip(batch, batch_results):
            if isinstance(result, Exception):
                results[hotel] = {"available": False, "rooms": [], "error": str(result)}
            else:
                results[hotel] = result

    return results


# ── Standalone test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    async def test():
        results = await check_disney_hotels(
            ["Contemporary"],
            "2026-10-08",
            "2026-10-11",
        )
        print(json.dumps(results, indent=2))

    asyncio.run(test())
