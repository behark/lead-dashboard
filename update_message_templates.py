"""
Update all leads with the new, better WhatsApp message template.
The new template is proven to get more responses.
"""
import urllib.parse
from app import create_app
from models import db, Lead

# NEW IMPROVED MESSAGE TEMPLATE
# This template got LH Beauty to respond!
def generate_new_message(lead):
    """Generate the improved message for a lead."""
    name = lead.name or "there"
    rating = lead.rating or 5.0

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
    """Convert phone to WhatsApp format (e.g., 38344406405)"""
    if not phone:
        return None

    # Remove all non-digit characters except +
    clean = ''.join(c for c in phone if c.isdigit() or c == '+')
    clean = clean.replace('+', '')

    # Handle Kosovo numbers
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


def update_all_leads():
    """Update all leads with the new message template."""
    app = create_app()

    with app.app_context():
        leads = Lead.query.all()
        total = len(leads)
        updated = 0
        skipped = 0

        print(f"🚀 Updating {total} leads with new message template...\n")

        for i, lead in enumerate(leads, 1):
            if not lead.phone:
                skipped += 1
                continue

            # Generate new message
            new_message = generate_new_message(lead)
            new_whatsapp_link = generate_whatsapp_link(lead.phone, new_message, lead.country)

            if new_whatsapp_link:
                lead.first_message = new_message
                lead.whatsapp_link = new_whatsapp_link
                updated += 1

                if i % 100 == 0:
                    db.session.commit()
                    print(f"  Progress: {i}/{total} leads processed...")
            else:
                skipped += 1

        db.session.commit()

        print(f"\n✅ Done!")
        print(f"   Updated: {updated} leads")
        print(f"   Skipped: {skipped} leads (no phone)")
        print(f"\n📱 New message preview:")
        print("-" * 50)
        sample_lead = Lead.query.filter(Lead.phone.isnot(None)).first()
        if sample_lead:
            print(generate_new_message(sample_lead))
        print("-" * 50)


def preview_changes():
    """Preview changes without applying them."""
    app = create_app()

    with app.app_context():
        leads = Lead.query.filter(Lead.phone.isnot(None)).limit(3).all()

        print("📋 PREVIEW - New message format:\n")
        print("=" * 60)

        for lead in leads:
            print(f"\n🏢 {lead.name}")
            print(f"📞 {lead.phone}")
            print(f"⭐ {lead.rating}")
            print("\n📝 NEW MESSAGE:")
            print("-" * 40)
            print(generate_new_message(lead))
            print("-" * 40)
            print()


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--preview':
        preview_changes()
    else:
        print("⚠️  This will update ALL leads with the new message template.")
        print("   Run with --preview first to see the changes.")
        print()
        confirm = input("Type 'yes' to proceed: ").strip().lower()

        if confirm == 'yes':
            update_all_leads()
        else:
            print("Cancelled.")
