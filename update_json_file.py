"""
Update leads_data.json with the new message template.
This ensures future imports/deployments have the correct message.
"""
import json
import urllib.parse
from pathlib import Path


def generate_new_message(lead):
    """Generate the improved message for a lead."""
    name = lead.get('name', 'there')
    rating = lead.get('rating', 5.0) or 5.0

    # Handle rating display
    if rating == int(rating):
        rating_str = f"{int(rating)}.0"
    else:
        rating_str = f"{rating}"

    message = f"""Përshëndetje {name}! 👋

Jam Behari, pashë që keni vlerësime super ({rating_str}⭐) në Google. Bravo për punën!

Kam përgatitur një ide se si mund t'i thjeshtoni rezervimet për klientët tuaj përmes një faqeje mobile që lidhet direkt me WhatsApp.

A dëshironi t'ua dërgoj linkun ta shihni si mund të duket salloni juaj online?
(Është dhuratë - demo falas për t'ju treguar mundësitë)"""

    return message


def format_phone_for_whatsapp(phone, country="Kosovo"):
    """Convert phone to WhatsApp format."""
    if not phone:
        return None

    clean = ''.join(c for c in phone if c.isdigit() or c == '+')
    clean = clean.replace('+', '')

    if clean.startswith('383'):
        return clean
    elif clean.startswith('0'):
        return '383' + clean[1:]
    elif len(clean) == 9 and clean.startswith('4'):
        return '383' + clean

    return clean


def generate_whatsapp_link(phone, message, country="Kosovo"):
    """Generate WhatsApp link with encoded message."""
    formatted_phone = format_phone_for_whatsapp(phone, country)
    if not formatted_phone:
        return None

    encoded_message = urllib.parse.quote(message)
    return f"https://wa.me/{formatted_phone}?text={encoded_message}"


def update_json_file(json_path='leads_data.json'):
    """Update the JSON file with new messages."""
    path = Path(json_path)

    if not path.exists():
        print(f"❌ File not found: {json_path}")
        return

    # Read existing data
    with open(path, 'r', encoding='utf-8') as f:
        leads = json.load(f)

    print(f"📂 Loaded {len(leads)} leads from {json_path}")

    updated = 0
    for lead in leads:
        if not lead.get('phone'):
            continue

        new_message = generate_new_message(lead)
        new_link = generate_whatsapp_link(
            lead.get('phone'),
            new_message,
            lead.get('country', 'Kosovo')
        )

        if new_link:
            lead['first_message'] = new_message
            lead['whatsapp_link'] = new_link
            updated += 1

    # Write back
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(leads, f, ensure_ascii=False, indent=2)

    print(f"✅ Updated {updated} leads in {json_path}")


if __name__ == '__main__':
    update_json_file('leads_data.json')
