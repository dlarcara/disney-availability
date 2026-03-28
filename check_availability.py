#!/usr/bin/env python3
"""
Disney & Marriott Resort Availability Checker
Reads alerts.json, checks each alert, appends to results.json,
sends email alerts and (placeholder) SMS alerts when availability is found.
"""

import json
import os
import smtplib
import sys
import time
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

# ── Environment / Secrets ─────────────────────────────────────────────────────
GMAIL_USER     = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASS = os.environ.get("GMAIL_APP_PASS", "")
ALERT_EMAILS   = [e.strip() for e in os.environ.get("ALERT_EMAILS", GMAIL_USER).split(",") if e.strip()]
IS_TEST_RUN    = os.environ.get("TEST_RUN", "false").lower() == "true"

# ── Disney API ────────────────────────────────────────────────────────────────
DISNEY_API = "https://disneyworld.disney.go.com/availability-calendar/api/calendar"
DISNEY_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://disneyworld.disney.go.com/",
}

# ── Marriott API ──────────────────────────────────────────────────────────────
# Swan = MC069, Dolphin = MC070, Swan Reserve = MC903
MARRIOTT_PROPERTY_IDS = {
    "Swan":        "MC069",
    "Dolphin":     "MC070",
    "Swan Reserve":"MC903",
}
MARRIOTT_API = "https://www.marriott.com/search/availabilityCalendar.mi"
MARRIOTT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://www.marriott.com/",
}

DISNEY_OWNED = {"Contemporary", "Yacht Club", "Beach Club", "Polynesian",
                "Grand Floridian", "Wilderness Lodge", "Animal Kingdom Lodge",
                "Caribbean Beach", "Pop Century", "Art of Animation",
                "All-Star Movies", "All-Star Music", "All-Star Sports",
                "Old Key West", "Saratoga Springs", "BoardWalk"}


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# ── Disney Check ──────────────────────────────────────────────────────────────
def check_disney(check_in, check_out):
    """Returns dict of {hotel_name: availability_status}"""
    try:
        resp = requests.get(
            DISNEY_API,
            headers=DISNEY_HEADERS,
            params={"segment": "resort", "startDate": check_in, "endDate": check_out},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        # Disney returns a list; any date not "none" means availability
        available_dates = [
            entry["date"] for entry in data
            if entry.get("availability", "none") not in ("none", "sold_out", "")
        ]
        return {"available": len(available_dates) > 0, "dates": available_dates, "raw": data}
    except Exception as e:
        print(f"  Disney API error: {e}")
        return {"available": False, "dates": [], "error": str(e)}


def check_disney_hotels(hotels, check_in, check_out):
    """Check all Disney-owned hotels in one API call (shared availability calendar)."""
    disney_hotels = [h for h in hotels if h in DISNEY_OWNED]
    if not disney_hotels:
        return {}
    print(f"  Checking Disney API for: {', '.join(disney_hotels)}")
    result = check_disney(check_in, check_out)
    # Disney's calendar API is property-wide; we tag each hotel with the same result
    # For per-property checks, individual resort IDs would be needed
    return {hotel: result for hotel in disney_hotels}


# ── Marriott Check ────────────────────────────────────────────────────────────
def check_marriott_hotel(hotel, check_in, check_out):
    """Check a single Marriott property."""
    property_id = MARRIOTT_PROPERTY_IDS.get(hotel)
    if not property_id:
        return {"available": False, "error": f"No property ID for {hotel}"}
    try:
        params = {
            "propertyCode": property_id,
            "arrivalDate": check_in,
            "departureDate": check_out,
            "numberOfRooms": 1,
            "numberOfAdults": 2,
        }
        resp = requests.get(MARRIOTT_API, headers=MARRIOTT_HEADERS, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        available = data.get("availabilityStatus", "").upper() not in ("UNAVAILABLE", "CLOSED", "")
        return {"available": available, "raw": data}
    except Exception as e:
        print(f"  Marriott API error for {hotel}: {e}")
        return {"available": False, "error": str(e)}


def check_marriott_hotels(hotels, check_in, check_out):
    marriott_hotels = [h for h in hotels if h in MARRIOTT_PROPERTY_IDS]
    results = {}
    for hotel in marriott_hotels:
        print(f"  Checking Marriott API for: {hotel}")
        results[hotel] = check_marriott_hotel(hotel, check_in, check_out)
        time.sleep(1)  # be polite
    return results


# ── Notifications ─────────────────────────────────────────────────────────────
def send_email(subject, body_html, body_text):
    if not GMAIL_USER or not GMAIL_APP_PASS:
        print("  ⚠️  Gmail credentials not set — skipping email.")
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = GMAIL_USER
        msg["To"]      = ", ".join(ALERT_EMAILS)
        msg.attach(MIMEText(body_text, "plain"))
        msg.attach(MIMEText(body_html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_APP_PASS)
            smtp.sendmail(GMAIL_USER, ALERT_EMAILS, msg.as_string())
        print(f"  ✅ Email sent to: {', '.join(ALERT_EMAILS)}")
    except Exception as e:
        print(f"  ❌ Email error: {e}")


def send_sms(message):
    """
    SMS PLACEHOLDER — wire up Twilio here when ready.

    To activate:
      1. pip install twilio
      2. Add GitHub Secrets: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM, TWILIO_TO
      3. Uncomment the block below and remove the placeholder print.

    from twilio.rest import Client
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token  = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_FROM")
    to_number   = os.environ.get("TWILIO_TO")
    client = Client(account_sid, auth_token)
    client.messages.create(body=message, from_=from_number, to=to_number)
    """
    print(f"  📱 SMS placeholder — would have sent: {message[:80]}...")


def build_email(alert, found_hotels, is_test=False):
    check_in  = alert["check_in"]
    check_out = alert["check_out"]
    name      = alert["name"]

    if is_test:
        subject = f"✅ TEST — Disney Availability Checker is working!"
        intro   = "This is a test run to confirm your email integration is working."
    else:
        subject = f"🏰 Availability Found — {name}!"
        intro   = f"Availability was detected for your alert <strong>{name}</strong>."

    hotels_html = "".join(f"<li>{h}</li>" for h in found_hotels)
    body_html = f"""
    <div style="font-family:Georgia,serif;max-width:600px;margin:0 auto;padding:24px;">
      <h2 style="color:#1a1a2e;">🏰 Disney Availability Alert</h2>
      <p>{intro}</p>
      <table style="border-collapse:collapse;width:100%;margin:16px 0;">
        <tr><td style="padding:8px;color:#666;">Alert</td><td style="padding:8px;font-weight:bold;">{name}</td></tr>
        <tr style="background:#f9f9f9;"><td style="padding:8px;color:#666;">Check-in</td><td style="padding:8px;">{check_in}</td></tr>
        <tr><td style="padding:8px;color:#666;">Check-out</td><td style="padding:8px;">{check_out}</td></tr>
        <tr style="background:#f9f9f9;"><td style="padding:8px;color:#666;">Hotels with availability</td>
            <td style="padding:8px;"><ul style="margin:0;padding-left:16px;">{hotels_html}</ul></td></tr>
      </table>
      <a href="https://disneyworld.disney.go.com/resorts/"
         style="display:inline-block;background:#1a1a2e;color:white;padding:12px 24px;
                border-radius:6px;text-decoration:none;font-weight:bold;">
        Book Now →
      </a>
      <p style="margin-top:24px;font-size:12px;color:#999;">
        Sent by your Disney Availability Checker · 
        <a href="https://github.com" style="color:#999;">View Dashboard</a>
      </p>
    </div>
    """
    body_text = f"{intro}\nAlert: {name}\nCheck-in: {check_in}\nCheck-out: {check_out}\nHotels: {', '.join(found_hotels)}\nBook: https://disneyworld.disney.go.com/resorts/"
    return subject, body_html, body_text


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    alerts  = load_json("alerts.json")
    results = load_json("results.json")

    run_timestamp = datetime.now(timezone.utc).isoformat()
    run_summary   = {
        "timestamp": run_timestamp,
        "is_test":   IS_TEST_RUN,
        "alerts":    [],
    }

    print(f"\n{'='*60}")
    print(f"Disney Availability Checker — {run_timestamp}")
    print(f"Test run: {IS_TEST_RUN}")
    print(f"{'='*60}\n")

    for alert in alerts:
        if not alert.get("active", True):
            continue

        name      = alert["name"]
        hotels    = alert["hotels"]
        check_in  = alert["check_in"]
        check_out = alert["check_out"]

        print(f"▶ Alert: {name} ({check_in} → {check_out})")
        print(f"  Hotels: {', '.join(hotels)}")

        hotel_results = {}
        hotel_results.update(check_disney_hotels(hotels, check_in, check_out))
        hotel_results.update(check_marriott_hotels(hotels, check_in, check_out))

        available_hotels = [h for h, r in hotel_results.items() if r.get("available")]
        has_availability = len(available_hotels) > 0

        alert_result = {
            "name":              name,
            "check_in":          check_in,
            "check_out":         check_out,
            "hotels_checked":    hotels,
            "hotel_results":     {h: {"available": r.get("available", False), "error": r.get("error")}
                                  for h, r in hotel_results.items()},
            "available_hotels":  available_hotels,
            "has_availability":  has_availability,
        }
        run_summary["alerts"].append(alert_result)

        if has_availability:
            print(f"  🎉 AVAILABILITY FOUND: {', '.join(available_hotels)}")
            subject, body_html, body_text = build_email(alert, available_hotels, is_test=False)
            send_email(subject, body_html, body_text)
            send_sms(f"Disney Alert! {name}: {', '.join(available_hotels)} available {check_in}–{check_out}")
        else:
            print(f"  — No availability found.")

        if IS_TEST_RUN:
            print("  📧 Test run — sending test email regardless of availability...")
            subject, body_html, body_text = build_email(alert, hotels, is_test=True)
            send_email(subject, body_html, body_text)
            break  # Only test the first alert

        print()

    results.append(run_summary)
    save_json("results.json", results)
    print(f"\n✅ Run complete. Results saved to results.json.")


if __name__ == "__main__":
    main()
