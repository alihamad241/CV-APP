import anthropic
import json
import re
import requests


def _call_custom_api(prompt: str, base_url: str, model_name: str, api_key: str = "", require_json: bool = True) -> str:
    """
    Send prompt to a custom OpenAI-compatible or native Ollama API.
    """
    url = base_url.rstrip('/')
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    if "/v1" in url or url.endswith("/api"):
        # OpenAI compatible endpoint
        target_url = f"{url}/chat/completions"
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "max_tokens": 2048,
            "temperature": 0.3
        }
        if require_json:
            payload["response_format"] = {"type": "json_object"}
            
        response = requests.post(target_url, headers=headers, json=payload, timeout=600)
        response.raise_for_status()
        res_json = response.json()
        return res_json["choices"][0]["message"]["content"]
    else:
        # Native Ollama endpoint
        target_url = f"{url}/api/chat"
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {
                "num_predict": 2048,
                "temperature": 0.3
            }
        }
        if require_json:
            payload["format"] = "json"
            
        response = requests.post(target_url, headers=headers, json=payload, timeout=600)
        response.raise_for_status()
        res_json = response.json()
        return res_json["message"]["content"]


def _call_gemini(prompt: str, api_key: str, model_name: str = "gemini-3.8-flash", require_json: bool = True) -> str:
    from google import genai
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model_name or 'gemini-3.8-flash',
        contents=prompt
    )
    return response.text


def analyze_resume(
    resume_text: str,
    job_description: str,
    provider: str = "Claude (Anthropic)",
    api_key: str = "",
    base_url: str = "",
    model_name: str = ""
) -> dict:
    """
    Send resume + job description to Claude or local Ollama and get back a structured analysis.
    Returns a dict with match score, skills, recommendation, etc.
    """
    prompt = f"""
You are an expert technical recruiter with 15+ years of experience screening candidates.
Analyze the resume against the job description below and return ONLY a valid JSON object.

JOB DESCRIPTION:
{job_description}

RESUME:
{resume_text}

Return a JSON object with exactly these fields:
{{
  "match_score": <integer 0-100>,
  "recommendation": "<one of: Strong Yes | Yes | Maybe | No>",
  "summary": "<2-sentence recruiter summary of the candidate>",
  "matched_skills": ["<skill1>", "<skill2>", ...],
  "missing_skills": ["<skill1>", "<skill2>", ...],
  "strengths": ["<strength1>", "<strength2>", "<strength3>"],
  "concerns": ["<concern1>", "<concern2>"],
  "experience_level": "<one of: Entry | Mid | Senior | Lead>"
}}

Be specific and honest. Do not include any text outside the JSON object.
"""

    if provider == "Claude (Anthropic)":
        # Anthropic client reads ANTHROPIC_API_KEY from environment or parameter
        if api_key:
            client = anthropic.Anthropic(api_key=api_key)
        else:
            client = anthropic.Anthropic()

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text
    elif provider == "Gemini (Google)":
        raw = _call_gemini(prompt, api_key, model_name=model_name)
    else:
        # Ollama / Custom API path
        raw = _call_custom_api(prompt, base_url, model_name, api_key)

    # Strip markdown code fences if present
    raw = re.sub(r"```json|```", "", raw).strip()

    result = json.loads(raw)
    return result


def check_job_description_bias(
    job_description: str,
    provider: str = "Claude (Anthropic)",
    api_key: str = "",
    base_url: str = "",
    model_name: str = ""
) -> dict:
    """
    Scan the job description for potentially biased language using Claude or local Ollama.
    """
    prompt = f"""
You are an expert in inclusive hiring practices. Analyze this job description for potentially biased language.

JOB DESCRIPTION:
{job_description}

Return ONLY a valid JSON object with these fields:
{{
  "bias_score": <integer 0-100, where 0 = no bias, 100 = highly biased>,
  "flagged_phrases": ["<phrase1>", "<phrase2>", ...],
  "suggestions": ["<suggestion1>", "<suggestion2>", ...],
  "overall_assessment": "<1-2 sentences>"
}}

Look for: gendered language, age bias, cultural exclusivity, unnecessary requirements.
Do not include any text outside the JSON object.
"""

    if provider == "Claude (Anthropic)":
        if api_key:
            client = anthropic.Anthropic(api_key=api_key)
        else:
            client = anthropic.Anthropic()

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text
    elif provider == "Gemini (Google)":
        raw = _call_gemini(prompt, api_key, model_name=model_name)
    else:
        # Ollama / Custom API path
        raw = _call_custom_api(prompt, base_url, model_name, api_key)

    raw = re.sub(r"```json|```", "", raw).strip()
    return json.loads(raw)


def generate_customized_resume(
    resume_text: str,
    job_description: str,
    provider: str = "Claude (Anthropic)",
    api_key: str = "",
    base_url: str = "",
    model_name: str = ""
) -> str:
    """
    Generate a customized version of the resume tailored to fit the job description.
    Returns the resume in standard Markdown format.
    """
    prompt = f"""
You are an expert resume writer and recruiter. Your goal is to customize the candidate's resume to match the job description as closely as possible.

JOB DESCRIPTION:
{job_description}

RESUME:
{resume_text}

Instructions for customization:
1. **Highlight Alignment**: Identify the key requirements, skills, and terminology in the job description and subtly integrate them into the resume summary, achievements, and skills section.
2. **Action Verbs & Impact**: Rephrase work experience bullet points to focus on the impact and outcomes relevant to this job description. Start bullet points with powerful action verbs.
3. **Restructure Skills**: Re-order or group the skills section so that the skills matching the job description are presented first.
4. **STRICT HONESTY POLICY**: 
   * Do NOT invent new jobs, change company names, change employment dates, or fabricate degrees or certifications.
   * Do NOT claim skills that the candidate has absolutely no background in, but rather optimize the framing of their *actual* experience and matching skills.
   * Focus entirely on highlighting, rephrasing, and aligning existing experience.
5. **Formatting**: Return the customized resume in clean, readable, professional Markdown format. Do not add any conversational text before or after the resume—return ONLY the markdown resume itself.
"""

    if provider == "Claude (Anthropic)":
        if api_key:
            client = anthropic.Anthropic(api_key=api_key)
        else:
            client = anthropic.Anthropic()

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text
    elif provider == "Gemini (Google)":
        raw = _call_gemini(prompt, api_key, model_name=model_name, require_json=False)
    else:
        # Ollama / Custom API path (require_json=False)
        raw = _call_custom_api(prompt, base_url, model_name, api_key, require_json=False)

    return raw.strip()


def calculate_ats_score(
    resume_text: str,
    job_description: str,
    provider: str = "Claude (Anthropic)",
    api_key: str = "",
    base_url: str = "",
    model_name: str = ""
) -> dict:
    """
    Evaluate the resume from an ATS (Applicant Tracking System) perspective against the job description.
    """
    prompt = f"""
You are an expert ATS (Applicant Tracking System) simulation engine and technical recruiter.
Evaluate the given resume against the job description from an ATS perspective.

JOB DESCRIPTION:
{job_description}

RESUME:
{resume_text}

Return ONLY a valid JSON object with exactly these fields:
{{
  "ats_score": <integer 0-100>,
  "keyword_match_pct": <integer 0-100>,
  "formatting_score": <integer 0-100>,
  "section_completeness": <integer 0-100>,
  "keyword_matches": ["<keyword1>", "<keyword2>", ...],
  "missing_keywords": ["<keyword1>", "<keyword2>", ...],
  "formatting_issues": ["<issue1>", "<issue2>", ...],
  "section_feedback": {{
    "contact": "<feedback>",
    "summary": "<feedback>",
    "experience": "<feedback>",
    "education": "<feedback>",
    "skills": "<feedback>"
  }},
  "improvement_tips": ["<tip1>", "<tip2>", ...]
}}

Do not include any text outside the JSON object.
"""

    if provider == "Claude (Anthropic)":
        if api_key:
            client = anthropic.Anthropic(api_key=api_key)
        else:
            client = anthropic.Anthropic()

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text
    elif provider == "Gemini (Google)":
        raw = _call_gemini(prompt, api_key, model_name=model_name)
    else:
        raw = _call_custom_api(prompt, base_url, model_name, api_key)

    raw = re.sub(r"```json|```", "", raw).strip()
    return json.loads(raw)


def rewrite_resume_for_job(
    resume_text: str,
    job_description: str,
    stored_profile: dict = None,
    linkedin_data: dict = None,
    provider: str = "Claude (Anthropic)",
    api_key: str = "",
    base_url: str = "",
    model_name: str = ""
) -> str:
    """
    Generate an enhanced customized version of the resume incorporating stored profile and LinkedIn data.
    """
    stored_profile_str = json.dumps(stored_profile, indent=2) if stored_profile else "None provided"
    linkedin_data_str = json.dumps(linkedin_data, indent=2) if linkedin_data else "None provided"

    prompt = f"""
You are an expert resume writer and recruiter. Customize the candidate's resume to best fit the job description, leveraging their full background profile and LinkedIn data.

JOB DESCRIPTION:
{job_description}

CURRENT RESUME:
{resume_text}

STORED PROFILE (Historical skills & experience):
{stored_profile_str}

LINKEDIN DATA (Certifications & achievements):
{linkedin_data_str}

Instructions for customization:
1. **Incorporate Broad Experience**: Use the STORED PROFILE and LINKEDIN DATA to enhance the resume, adding relevant certifications, achievements, or past experiences that match the job description.
2. **Highlight Alignment**: Identify the key requirements in the job description and subtly integrate them into the resume summary, achievements, and skills section.
3. **Action Verbs & Impact**: Rephrase work experience bullet points to focus on the impact and outcomes relevant to this job description.
4. **STRICT HONESTY POLICY**: 
   * Do NOT invent new jobs, change company names, change employment dates, or fabricate degrees or certifications.
   * Only use facts from the CURRENT RESUME, STORED PROFILE, or LINKEDIN DATA.
   * Do NOT claim skills that the candidate has absolutely no background in.
5. **Formatting**: Return the customized resume in clean, readable, professional Markdown format. Do not add any conversational text before or after the resume—return ONLY the markdown resume itself.
"""

    if provider == "Claude (Anthropic)":
        if api_key:
            client = anthropic.Anthropic(api_key=api_key)
        else:
            client = anthropic.Anthropic()

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2500,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text
    elif provider == "Gemini (Google)":
        raw = _call_gemini(prompt, api_key, model_name=model_name, require_json=False)
    else:
        raw = _call_custom_api(prompt, base_url, model_name, api_key, require_json=False)

    return raw.strip()
