"""
Demo script to test GooseAI integration
"""
import os
from services.ai_service import ai_service

def test_gooseai_integration():
    """Test basic GooseAI functionality"""
    
    # Test 1: Simple message variation
    print("Testing message variation...")
    test_lead = {
        'name': 'Salon Bella',
        'city': 'Prishtina',
        'rating': '4.8',
        'category': 'salon'
    }
    
    original_msg = "Pershendetje 👋\n\nPashe {business_name} ne Google - {rating}⭐, po beni shkelqyeshem!"
    
    variation = ai_service.generate_message_variation(original_msg, test_lead)
    if variation:
        print(f"✓ Variation generated: {variation}")
    else:
        print("✗ Failed to generate variation (check API key)")
    
    # Test 2: Lead scoring
    print("\nTesting lead scoring...")
    score = ai_service.score_lead(test_lead)
    if score:
        print(f"✓ Lead scored: {score}/100")
    else:
        print("✗ Failed to score lead")
    
    # Test 3: Channel optimization
    print("\nTesting channel optimization...")
    msg = "We offer web development services. Contact us for more info!"
    
    sms_optimized = ai_service.optimize_message_for_channel(msg, 'sms')
    whatsapp_optimized = ai_service.optimize_message_for_channel(msg, 'whatsapp')
    
    if sms_optimized:
        print(f"✓ SMS optimized: {sms_optimized}")
    if whatsapp_optimized:
        print(f"✓ WhatsApp optimized: {whatsapp_optimized}")
    
    # Test 4: Follow-up generation
    print("\nTesting follow-up generation...")
    follow_up = ai_service.generate_follow_up_message(
        original_msg, 3, test_lead
    )
    if follow_up:
        print(f"✓ Follow-up generated: {follow_up}")
    else:
        print("✗ Failed to generate follow-up")

if __name__ == '__main__':
    print("GooseAI Integration Test")
    print("========================")
    
    # Check if API key is configured
    if not os.getenv('GOOSEAI_API_KEY'):
        print("⚠️  No GOOSEAI_API_KEY found in environment")
        print("Set your API key in .env file:")
        print("GOOSEAI_API_KEY=your-actual-api-key-here")
        exit(1)
    
    test_gooseai_integration()