"""
AI service for lead dashboard - integrates with various LLM providers
"""
import os
import requests
import json
from flask import current_app
from typing import Optional, Dict, Any


class AIService:
    """Unified AI service for multiple providers"""
    
    def __init__(self):
        self.providers = {
            'gooseai': {
                'api_key': os.getenv('GOOSEAI_API_KEY'),
                'base_url': 'https://api.goose.ai/v1',
                'model': os.getenv('GOOSEAI_MODEL', 'gpt-neo-1-3b'),
                'headers': lambda key: {'Authorization': f'Bearer {key}'}
            },
            'openai': {
                'api_key': os.getenv('OPENAI_API_KEY'),
                'base_url': 'https://api.openai.com/v1',
                'model': os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo'),
                'headers': lambda key: {'Authorization': f'Bearer {key}'}
            },
            'anthropic': {
                'api_key': os.getenv('ANTHROPIC_API_KEY'),
                'base_url': 'https://api.anthropic.com/v1',
                'model': os.getenv('ANTHROPIC_MODEL', 'claude-3-sonnet-20240229'),
                'headers': lambda key: {'x-api-key': key, 'anthropic-version': '2023-06-01'}
            }
        }
    
    def get_active_provider(self):
        """Get first available provider with API key"""
        for name, config in self.providers.items():
            if config['api_key']:
                return name, config
        return None, {}
    
    def generate_message_variation(self, original_message: str, lead_data: Dict[str, Any]) -> Optional[str]:
        """Generate a personalized variation of a message"""
        provider_name, provider_config = self.get_active_provider()
        
        if not provider_name or not provider_config.get('api_key'):
            return None
        
        prompt = f"""
        Create a personalized message variation based on this template:
        
        Original: {original_message}
        
        Lead context:
        - Business: {lead_data.get('name', 'N/A')}
        - City: {lead_data.get('city', 'N/A')}
        - Rating: {lead_data.get('rating', 'N/A')}
        - Category: {lead_data.get('category', 'N/A')}
        
        Make it more personal and engaging. Keep the same structure but add specific details.
        Return only the message, no extra text.
        """
        
        return self._generate_completion(prompt, provider_name, provider_config)
    
    def score_lead(self, lead_data: Dict[str, Any]) -> Optional[int]:
        """AI-powered lead scoring"""
        provider_name, provider_config = self.get_active_provider()
        
        if not provider_name or not provider_config.get('api_key'):
            return None
        
        prompt = f"""
        Score this lead from 0-100 for conversion likelihood:
        
        Lead data:
        - Business: {lead_data.get('name', 'N/A')}
        - City: {lead_data.get('city', 'N/A')}
        - Rating: {lead_data.get('rating', 'N/A')}
        - Category: {lead_data.get('category', 'N/A')}
        - Has website: {lead_data.get('website', 'No')}
        
        Consider:
        - Higher ratings = better prospects
        - No website = needs help (good prospect)
        - Category demand in area
        - Business quality indicators
        
        Return only a number from 0-100.
        """
        
        result = self._generate_completion(prompt, provider_name, provider_config)
        try:
            return int(result.strip()) if result else None
        except ValueError:
            return None
    
    def generate_follow_up_message(self, previous_message: str, days_since_contact: int, lead_data: Dict[str, Any]) -> Optional[str]:
        """Generate contextual follow-up message"""
        provider_name, provider_config = self.get_active_provider()
        
        if not provider_name or not provider_config.get('api_key'):
            return None
        
        prompt = f"""
        Generate a follow-up message for this lead:
        
        Previous message: {previous_message}
        Days since contact: {days_since_contact}
        Lead: {lead_data.get('name', 'N/A')} in {lead_data.get('city', 'N/A')}
        Category: {lead_data.get('category', 'N/A')}
        
        Guidelines:
        - Brief and friendly
        - Reference time passed naturally
        - Add new value proposition
        - Clear call to action
        - Under 160 characters for SMS, conversational for WhatsApp
        
        Return only the message.
        """
        
        return self._generate_completion(prompt, provider_name, provider_config)
    
    def optimize_message_for_channel(self, message: str, channel: str) -> Optional[str]:
        """Optimize message for specific channel (SMS vs WhatsApp vs Email)"""
        provider_name, provider_config = self.get_active_provider()
        
        if not provider_name or not provider_config.get('api_key'):
            return None
        
        guidelines = {
            'sms': "Under 160 characters, clear CTA, minimal emojis",
            'whatsapp': "Conversational, can use emojis, multiple paragraphs OK",
            'email': "Professional format, proper subject line needed"
        }
        
        prompt = f"""
        Optimize this message for {channel.upper()}:
        
        Original: {message}
        
        Channel requirements: {guidelines.get(channel, 'Keep it natural')}
        
        Return only the optimized message.
        """
        
        return self._generate_completion(prompt, provider_name, provider_config)
    
    def _generate_completion(self, prompt: str, provider_name: str, provider_config: Dict[str, Any]) -> Optional[str]:
        """Generate completion using specified provider"""
        try:
            if provider_name == 'anthropic':
                return self._anthropic_completion(prompt, provider_config)
            elif provider_name == 'openai':
                return self._openai_completion(prompt, provider_config)
            else:
                return self._gooseai_completion(prompt, provider_config)
        except Exception as e:
            print(f"AI service error ({provider_name}): {e}")
            return None
    
    def _gooseai_completion(self, prompt: str, config: Dict[str, Any]) -> Optional[str]:
        """GooseAI completion using engines endpoint"""
        data = {
            "prompt": prompt,
            "max_tokens": 150,
            "temperature": 0.7
        }
        
        response = requests.post(
            f"{config['base_url']}/engines/{config['model']}/completions",
            headers=config['headers'](config['api_key']),
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()['choices'][0]['text'].strip()
        else:
            print(f"GooseAI error: {response.status_code} - {response.text}")
            return None
    
    def _openai_completion(self, prompt: str, config: Dict[str, Any]) -> Optional[str]:
        """OpenAI completion"""
        data = {
            "model": config['model'],
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 150,
            "temperature": 0.7
        }
        
        response = requests.post(
            f"{config['base_url']}/chat/completions",
            headers=config['headers'](config['api_key']),
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content'].strip()
        else:
            print(f"OpenAI error: {response.status_code} - {response.text}")
            return None
    
    def _anthropic_completion(self, prompt: str, config: Dict[str, Any]) -> Optional[str]:
        """Anthropic completion"""
        data = {
            "model": config['model'],
            "max_tokens": 150,
            "messages": [{"role": "user", "content": prompt}]
        }
        
        response = requests.post(
            f"{config['base_url']}/messages",
            headers=config['headers'](config['api_key']),
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()['content'][0]['text'].strip()
        else:
            print(f"Anthropic error: {response.status_code} - {response.text}")
            return None


# Global instance
ai_service = AIService()