import json
import os
import pathlib
from datetime import datetime
from typing import Dict, Any, List

def _get_profile_path() -> pathlib.Path:
    """Get the path to the user profile JSON file, creating directory if needed."""
    profile_dir = pathlib.Path.home() / ".cv_app"
    profile_dir.mkdir(parents=True, exist_ok=True)
    return profile_dir / "user_profile.json"

def _get_empty_profile() -> Dict[str, Any]:
    """Return a completely empty but structurally valid profile."""
    return {
        "name": "",
        "email": "",
        "phone": "",
        "location": "",
        "summary": "",
        "skills": [],
        "experience": [],
        "education": [],
        "certifications": [],
        "achievements": [],
        "linkedin_url": "",
        "linkedin_data": {},
        "last_updated": datetime.now().isoformat()
    }

def load_profile() -> Dict[str, Any]:
    """Load profile from disk, return empty profile dict if it doesn't exist."""
    path = _get_profile_path()
    if not path.exists():
        return _get_empty_profile()
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            profile = json.load(f)
            # Ensure all keys exist
            empty = _get_empty_profile()
            for k, v in empty.items():
                if k not in profile:
                    profile[k] = v
            return profile
    except Exception as e:
        print(f"Error loading profile: {e}")
        return _get_empty_profile()

def save_profile(profile: Dict[str, Any]) -> None:
    """Save profile to disk."""
    path = _get_profile_path()
    try:
        profile["last_updated"] = datetime.now().isoformat()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving profile: {e}")

def merge_cv_data(existing_profile: Dict[str, Any], new_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Intelligently merge new CV data into existing profile without losing data.
    New data overwrites simple fields if present, appends to lists (deduplicating).
    """
    merged = existing_profile.copy()
    
    # Overwrite simple fields if new data has them and they are not empty
    for field in ["name", "email", "phone", "location", "summary", "linkedin_url"]:
        if new_data.get(field):
            merged[field] = new_data[field]
            
    # Merge dict fields
    if new_data.get("linkedin_data"):
        if not merged.get("linkedin_data"):
            merged["linkedin_data"] = {}
        merged["linkedin_data"].update(new_data["linkedin_data"])

    # Merge skills (deduplicate, case-insensitive match but preserve original case)
    if new_data.get("skills"):
        existing_skills_lower = {s.lower() for s in merged.get("skills", [])}
        for skill in new_data["skills"]:
            if skill.lower() not in existing_skills_lower:
                merged.setdefault("skills", []).append(skill)
                existing_skills_lower.add(skill.lower())

    # Merge simple string lists
    for field in ["certifications", "achievements"]:
        if new_data.get(field):
            existing_items_lower = {i.lower() for i in merged.get(field, [])}
            for item in new_data[field]:
                if item.lower() not in existing_items_lower:
                    merged.setdefault(field, []).append(item)
                    existing_items_lower.add(item.lower())

    # Merge experience
    if new_data.get("experience"):
        existing_exp = merged.get("experience", [])
        for new_exp in new_data["experience"]:
            # Check if this experience already exists (match by company and title)
            match_found = False
            for i, exist_exp in enumerate(existing_exp):
                if (exist_exp.get("company", "").lower() == new_exp.get("company", "").lower() and 
                    exist_exp.get("title", "").lower() == new_exp.get("title", "").lower()):
                    # Match found, update fields if empty, merge bullets
                    match_found = True
                    if not exist_exp.get("dates") and new_exp.get("dates"):
                        existing_exp[i]["dates"] = new_exp["dates"]
                    
                    # Merge bullets
                    exist_bullets = set(exist_exp.get("bullets", []))
                    for b in new_exp.get("bullets", []):
                        if b not in exist_bullets:
                            existing_exp[i].setdefault("bullets", []).append(b)
                            exist_bullets.add(b)
                    break
            
            if not match_found:
                existing_exp.append(new_exp)
        merged["experience"] = existing_exp

    # Merge education
    if new_data.get("education"):
        existing_edu = merged.get("education", [])
        for new_edu in new_data["education"]:
            # Check if this education already exists (match by institution and degree)
            match_found = False
            for i, exist_edu in enumerate(existing_edu):
                if (exist_edu.get("institution", "").lower() == new_edu.get("institution", "").lower() and 
                    exist_edu.get("degree", "").lower() == new_edu.get("degree", "").lower()):
                    match_found = True
                    if not exist_edu.get("dates") and new_edu.get("dates"):
                        existing_edu[i]["dates"] = new_edu["dates"]
                    if not exist_edu.get("details") and new_edu.get("details"):
                        existing_edu[i]["details"] = new_edu["details"]
                    break
            
            if not match_found:
                existing_edu.append(new_edu)
        merged["education"] = existing_edu
        
    merged["last_updated"] = datetime.now().isoformat()
    return merged

def extract_profile_from_text(resume_text: str, provider: str, api_key: str, base_url: str, model_name: str) -> Dict[str, Any]:
    """
    Use AI to extract structured profile data from resume text.
    Calls appropriate provider and returns dict matching the profile schema.
    """
    prompt = f"""
Please extract the following resume text into a structured JSON format. 
Return ONLY valid JSON and nothing else. Ensure the keys and structure exactly match this schema:
{{
  "name": "string",
  "email": "string",
  "phone": "string",
  "location": "string",
  "summary": "string",
  "skills": ["string", "string"],
  "experience": [
    {{
      "company": "string",
      "title": "string",
      "dates": "string",
      "bullets": ["string", "string"]
    }}
  ],
  "education": [
    {{
      "institution": "string",
      "degree": "string",
      "dates": "string",
      "details": "string"
    }}
  ],
  "certifications": ["string"],
  "achievements": ["string"],
  "linkedin_url": "string"
}}

Resume Text:
{resume_text}
"""
    
    response_text = ""
    
    try:
        if provider == 'Claude (Anthropic)':
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model=model_name or "claude-3-haiku-20240307",
                max_tokens=4000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            response_text = response.content[0].text
            
        elif provider == 'Gemini (Google)':
            import google.genai as genai
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model_name or 'gemini-3.8-flash',
                contents=prompt
            )
            response_text = response.text
            
        else:
            # Ollama / Custom Provider
            import requests
            url = f"{base_url.rstrip('/')}/api/generate"
            payload = {
                "model": model_name,
                "prompt": prompt,
                "stream": False,
                "format": "json"
            }
            res = requests.post(url, json=payload)
            res.raise_for_status()
            response_text = res.json().get("response", "")
            
        # Clean up response text to find JSON
        response_text = response_text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
            
        response_text = response_text.strip()
        
        extracted_data = json.loads(response_text)
        return extracted_data
    except Exception as e:
        print(f"Error extracting profile: {e}")
        return {}

def get_profile_summary(profile: Dict[str, Any]) -> str:
    """Return a human-readable summary of the stored profile."""
    lines = []
    
    name = profile.get("name", "Unknown User")
    lines.append(f"Profile: {name}")
    
    contact = []
    if profile.get("email"): contact.append(profile["email"])
    if profile.get("phone"): contact.append(profile["phone"])
    if profile.get("location"): contact.append(profile["location"])
    if contact:
        lines.append(f"Contact: {' | '.join(contact)}")
        
    if profile.get("summary"):
        lines.append("\nSummary:")
        lines.append(profile["summary"])
        
    skills = profile.get("skills", [])
    if skills:
        lines.append("\nSkills:")
        # Wrap skills
        lines.append(", ".join(skills))
        
    exp = profile.get("experience", [])
    if exp:
        lines.append(f"\nExperience ({len(exp)} roles):")
        for e in exp:
            title = e.get("title", "")
            company = e.get("company", "")
            dates = e.get("dates", "")
            lines.append(f"- {title} at {company} ({dates})")
            
    edu = profile.get("education", [])
    if edu:
        lines.append(f"\nEducation ({len(edu)} degrees):")
        for e in edu:
            deg = e.get("degree", "")
            inst = e.get("institution", "")
            lines.append(f"- {deg} from {inst}")
            
    if profile.get("last_updated"):
        try:
            dt = datetime.fromisoformat(profile["last_updated"])
            lines.append(f"\nLast Updated: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
        except:
            pass
            
    return "\n".join(lines)
