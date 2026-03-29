#!/usr/bin/env python3
"""
check_availability.py

Orchestrator — reads alerts.json, runs Disney + Marriott checkers,
appends results to results.json, sends email and SMS (placeholder) alerts.
"""

import asyncio
import json
import os
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from checkers.disney import check_disney_hotels
from checkers.marriott import check_marriott_hotels

# ── Environment / Secrets ─────────────────────────────────────────────────────
GMAIL_USER     = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASS = os.environ.get("GMAIL_APP_PASS", "")
ALERT_EMAILS   = [e.strip() for e in os.environ.get("ALERT_EMAILS", GMAIL_USER).split(",") if e.strip()]
IS_TEST_RUN    = os.environ.get("TEST_RUN", "false").lower() == "true"

DISNEY_OWNED = {
    "Contemporary", "Yacht Club", "Beach Club", "Polynesian",
    "Grand Floridian", "Wilderness Lodge", "Animal Kingdom Lodge",
    "Caribbean Beach", "Pop Century", "Art of Animation",
    "Old Key West", "Saratoga Springs", "BoardWalk",
}
MARRIOTT_OWNED = {"Swan", "Dolphin", "Swan Reserve"}


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


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
      3. Uncomment the block below

    from twilio.rest import Client
    client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
    client.messages.create(
        body=message,
        from_=os.environ["TWILIO_FROM"],
        to=os.environ["TWILIO_TO"]
    )
    """
    print(f"  📱 SMS placeholder — would have sent: {message[:80]}...")


def build_rooms_html(hotel_results):
    rows = ""
    for hotel, result in hotel_results.items():
        if not result.get("available"):
            continue
        for room in result.get("rooms", []):
            rows += f"""
            <tr>
              <td style="padding:8px;border-bottom:1px solid #eee;">{hotel}</td>
              <td style="padding:8px;border-bottom:1px solid #eee;">{room['name']}</td>
              <td style="padding:8px;border-bottom:1px solid #eee;text-align:right;">{room['avg_per_night']}/night</td>
              <td style="padding:8px;border-bottom:1px solid #eee;text-align:right;">{room['total']}</td>
            </tr>"""
    if not rows:
        return ""
    return f"""
    <table style="width:100%;border-collapse:collapse;margin:16px 0;font-size:13px;">
      <thead>
        <tr style="background:#f3f4f6;">
          <th style="padding:8px;text-align:left;">Resort</th>
          <th style="padding:8px;text-align:left;">Room Type</th>
          <th style="padding:8px;text-align:right;">Avg/Night</th>
          <th style="padding:8px;text-align:right;">Total</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>"""


def build_email(alert, hotel_results, is_test=False):
    name      = alert["name"]
    check_in  = alert["check_in"]
    check_out = alert["check_out"]
    available_hotels = [h for h, r in hotel_results.items() if r.get("available")]

    if is_test:
        subject    = "✅ TEST — Disney Availability Checker is working!"
        intro      = "This is a test run confirming your email integration works."
        rooms_html = ""
    else:
        subject    = f"🏰 Availability Found — {name}!"
        intro      = f"Availability was detected for your alert <strong>{name}</strong>."
        rooms_html = build_rooms_html(hotel_results)

    hotels_list = "".join(f"<li>{h}</li>" for h in (available_hotels or list(hotel_results.keys())))

    body_html = f"""
    <div style="font-family:Georgia,serif;max-width:620px;margin:0 auto;padding:24px;">
      <h2 style="color:#1a1a2e;">🏰 Disney Availability Alert</h2>
      <p>{intro}</p>
      <table style="border-collapse:collapse;width:100%;margin:16px 0;">
        <tr><td style="padding:8px;color:#666;width:120px;">Alert</td>
            <td style="padding:8px;font-weight:bold;">{name}</td></tr>
        <tr style="background:#f9f9f9;">
            <td style="padding:8px;color:#666;">Check-in</td>
            <td style="padding:8px;">{check_in}</td></tr>
        <tr><td style="padding:8px;color:#666;">Check-out</td>
            <td style="padding:8px;">{check_out}</td></tr>
        <tr style="background:#f9f9f9;">
            <td style="padding:8px;color:#666;">Available</td>
            <td style="padding:8px;"><ul style="margin:0;padding-left:16px;">{hotels_list}</ul></td></tr>
      </table>
      {rooms_html}
      <a href="https://disneyworld.disney.go.com/resorts/"
         style="display:inline-block;background:#1a1a2e;color:white;padding:12px 24px;
                border-radius:6px;text-decoration:none;font-weight:bold;margin-top:8px;">
        Book Now →
      </a>
      <p style="margin-top:24px;font-size:12px;color:#999;">Sent by your Disney Availability Checker</p>
    </div>"""

    body_text = (
        f"{'TEST — ' if is_test else ''}Disney Alert: {name}\n"
        f"Check-in: {check_in} | Check-out: {check_out}\n"
        f"Available: {', '.join(available_hotels or list(hotel_results.keys()))}\n"
        f"Book: https://disneyworld.disney.go.com/resorts/"
    )
    return subject, body_html, body_text


# ── Main ──────────────────────────────────────────────────────────────────────
async def main():
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

        disney_hotels   = [h for h in hotels if h in DISNEY_OWNED]
        marriott_hotels = [h for h in hotels if h in MARRIOTT_OWNED]

        hotel_results = {}

        if disney_hotels:
            disney_results = await check_disney_hotels(disney_hotels, check_in, check_out)
            hotel_results.update(disney_results)

        if marriott_hotels:
            marriott_results = check_marriott_hotels(marriott_hotels, check_in, check_out)
            hotel_results.update(marriott_results)

        available_hotels = [h for h, r in hotel_results.items() if r.get("available")]
        has_availability = len(available_hotels) > 0

        alert_result = {
            "name":             name,
            "check_in":         check_in,
            "check_out":        check_out,
            "hotels_checked":   hotels,
            "hotel_results":    {
                h: {
                    "available":  r.get("available", False),
                    "room_count": len(r.get("rooms", [])),
                    "error":      r.get("error"),
                }
                for h, r in hotel_results.items()
            },
            "available_hotels": available_hotels,
            "has_availability": has_availability,
        }
        run_summary["alerts"].append(alert_result)

        if has_availability:
            print(f"\n  🎉 AVAILABILITY FOUND: {', '.join(available_hotels)}")
            subject, body_html, body_text = build_email(alert, hotel_results, is_test=False)
            send_email(subject, body_html, body_text)
            send_sms(f"Disney Alert! {name}: {', '.join(available_hotels)} available {check_in}-{check_out}")
        else:
            print(f"  — No availability found.")

        if IS_TEST_RUN:
            print("\n  📧 Test run — sending test email...")
            subject, body_html, body_text = build_email(alert, hotel_results, is_test=True)
            send_email(subject, body_html, body_text)
            break

        print()

    results.append(run_summary)
    save_json("results.json", results)
    print(f"\n✅ Run complete. Results saved.")


if __name__ == "__main__":
    asyncio.run(main())
