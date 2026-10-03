import json
import requests
import logging

logger = logging.getLogger(__name__)

def _call_custom_api(provider: str, api_key: str, base_url: str, model_name: str, prompt: str) -> str:
    """Helper function to call the appropriate AI provider."""
    if provider == 'Claude (Anthropic)':
        import anthropic
        try:
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model=model_name or "claude-3-haiku-20240307",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Error calling Anthropic API: {e}")
            raise
    elif provider == 'Gemini (Google)':
        import google.genai as genai
        try:
            client = genai.Client(api_key=api_key)
            model_to_use = model_name or 'gemini-3.8-flash'
            response = client.models.generate_content(
                model=model_to_use,
                contents=prompt
            )
            return response.text
        except Exception as e:
            logger.error(f"Error calling Google GenAI API: {e}")
            raise
    else:
        # Custom / Ollama (OpenAI compatible endpoint)
        try:
            headers = {'Content-Type': 'application/json'}
            if api_key:
                headers['Authorization'] = f'Bearer {api_key}'
            
            payload = {
                "model": model_name or "llama3",
                "messages": [{"role": "user", "content": prompt}],
                "stream": False
            }
            
            url = f"{base_url.rstrip('/')}/v1/chat/completions" if base_url else "http://localhost:11434/v1/chat/completions"
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data['choices'][0]['message']['content']
        except Exception as e:
            logger.error(f"Error calling Custom API: {e}")
            raise

def fetch_linkedin_data(linkedin_url: str, provider: str, api_key: str, base_url: str, model_name: str, pasted_text: str = '') -> dict:
    """
    Parses pasted LinkedIn profile text using AI to extract structured data.
    Since direct scraping is blocked, we rely on user-pasted text.
    
    Returns a dict with keys: certifications, achievements, skills, volunteer, courses.
    """
    empty_result = {
        "certifications": [],
        "achievements": [],
        "skills": [],
        "volunteer": [],
        "courses": []
    }
    
    if not pasted_text.strip():
        return empty_result
        
    prompt = f"""
You are an expert data extractor. I am providing you with copied text from a LinkedIn profile.
Extract the following sections into a JSON object with strictly these keys:
- "certifications": A list of strings representing certifications or licenses.
- "achievements": A list of strings representing honors, awards, or major accomplishments.
- "skills": A list of strings representing skills and endorsements.
- "volunteer": A list of strings representing volunteer experience.
- "courses": A list of strings representing completed courses.

If a section is not found or is empty, return an empty list for that key.
Only output the raw JSON object, without any markdown formatting like ```json ... ```. Do not include any explanatory text.

LinkedIn Text:
{pasted_text}
"""
    
    try:
        response_text = _call_custom_api(provider, api_key, base_url, model_name, prompt)
        
        # Try to parse JSON from response. Clean up potential markdown formatting.
        cleaned_text = response_text.strip()
        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text[7:]
        elif cleaned_text.startswith("```"):
            cleaned_text = cleaned_text[3:]
        if cleaned_text.endswith("```"):
            cleaned_text = cleaned_text[:-3]
            
        parsed_data = json.loads(cleaned_text.strip())
        
        # Ensure correct format and keys exist
        for key in empty_result.keys():
            if key not in parsed_data or not isinstance(parsed_data[key], list):
                parsed_data[key] = []
                
        return {k: parsed_data[k] for k in empty_result.keys()}
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from AI response: {e}\nResponse: {response_text}")
        return empty_result
    except Exception as e:
        logger.error(f"Error during AI data extraction: {e}")
        return empty_result

def generate_linkedin_enhancement_suggestions(profile: dict, linkedin_data: dict, provider: str, api_key: str, base_url: str, model_name: str) -> str:
    """
    Uses AI to suggest how to enhance the CV (stored in profile dict) with newly extracted LinkedIn data.
    Returns markdown text with suggestions.
    """
    prompt = f"""
You are an expert career coach and CV writer. I have a user's current CV profile data and newly extracted data from their LinkedIn profile.
Your task is to analyze both and suggest specific ways to enhance the CV using the new LinkedIn data.

Current CV Profile Data:
{json.dumps(profile, indent=2)}

Extracted LinkedIn Data:
{json.dumps(linkedin_data, indent=2)}

Provide your suggestions in markdown format. Be specific and actionable. 
For example, recommend adding specific skills to the CV's skills section, mentioning a certification in the summary, or incorporating volunteer work.
Highlight which items from the LinkedIn data are missing from the CV.
Do not output anything besides the markdown suggestions.
"""
    
    try:
        return _call_custom_api(provider, api_key, base_url, model_name, prompt)
    except Exception as e:
        logger.error(f"Error generating enhancement suggestions: {e}")
        return f"An error occurred while generating suggestions: {str(e)}"
