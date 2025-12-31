from __future__ import annotations

import json

from flask import Blueprint, jsonify, request
from flask_login import login_required

from models import ContactChannel, MessageTemplate, db
from services.ai_service import ai_service


api_templates_bp = Blueprint('api_templates', __name__, url_prefix='/api/templates')


@api_templates_bp.route('/generate', methods=['POST'])
@login_required
def generate_templates():
    payload = request.get_json(silent=True) or {}

    channel = payload.get('channel', 'whatsapp')
    language = payload.get('language', 'sq')
    industry = payload.get('industry', '')
    goal = payload.get('goal', 'book a 10-minute call')
    tone = payload.get('tone', 'friendly, concise')
    offer = payload.get('offer', 'a professional website package')
    count = int(payload.get('count', 3) or 3)
    save = bool(payload.get('save', False))
    category = payload.get('category')

    try:
        channel_enum = ContactChannel(channel)
    except ValueError:
        return jsonify({'error': 'Invalid channel'}), 400

    if count < 1 or count > 8:
        return jsonify({'error': 'count must be between 1 and 8'}), 400

    provider_name, provider_config = ai_service.get_active_provider()
    if not provider_name or not provider_config.get('api_key'):
        return jsonify({'error': 'No AI provider configured. Set GOOSEAI_API_KEY (or another provider key).'}), 400

    channel_rules = {
        'whatsapp': 'Conversational, can be 2-4 short lines, no more than 400 chars. No links unless requested.',
        'sms': 'Under 160 characters, no emojis, one CTA.',
        'email': 'Include a subject and a short body. Professional tone.'
    }

    prompt = f"""
You generate outreach message templates.

Return ONLY valid JSON (no markdown), in this schema:
{{
  "templates": [
    {{
      "name": "...",
      "subject": "..." | null,
      "content": "..."
    }}
  ]
}}

Constraints:
- Channel: {channel}
- Language: {language}
- Industry/category: {industry or category or 'general local business'}
- Goal: {goal}
- Offer: {offer}
- Tone: {tone}
- {channel_rules.get(channel, 'Keep it natural and short.')}
- Use placeholders: {{business_name}}, {{city}}, {{rating}} when relevant.
- Each template must be meaningfully different.

Generate {count} templates.
""".strip()

    raw = ai_service._generate_completion(prompt, provider_name, provider_config)
    if not raw:
        return jsonify({'error': 'AI generation failed'}), 502

    try:
        data = json.loads(raw)
    except Exception:
        start = raw.find('{')
        end = raw.rfind('}')
        if start == -1 or end == -1 or end <= start:
            return jsonify({'error': 'AI returned non-JSON output', 'raw': raw[:1000]}), 502
        try:
            data = json.loads(raw[start:end + 1])
        except Exception:
            return jsonify({'error': 'AI returned invalid JSON', 'raw': raw[:1000]}), 502

    templates = data.get('templates') if isinstance(data, dict) else None
    if not isinstance(templates, list) or not templates:
        return jsonify({'error': 'AI returned unexpected schema', 'raw': raw[:1000]}), 502

    saved = []
    out = []
    for t in templates[:count]:
        if not isinstance(t, dict):
            continue
        name = (t.get('name') or '').strip() or f"AI {channel.upper()} Template"
        subject = t.get('subject')
        content = (t.get('content') or '').strip()
        if not content:
            continue

        out.append({'name': name, 'subject': subject, 'content': content})

        if save:
            mt = MessageTemplate(
                name=name,
                channel=channel_enum,
                language=language,
                category=category or industry or None,
                subject=subject if channel_enum == ContactChannel.EMAIL else None,
                content=content,
                variant='A'
            )
            db.session.add(mt)
            saved.append(mt)

    if save and saved:
        db.session.commit()

    return jsonify({
        'provider': provider_name,
        'count': len(out),
        'saved_count': len(saved),
        'templates': out,
        'saved_ids': [t.id for t in saved] if saved else []
    })
