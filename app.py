import streamlit as st
import sys
import os

sys.path.append(os.path.dirname(__file__))

from utils.extractor import extract_text_from_pdf
from utils.analyzer import (
    analyze_resume, check_job_description_bias, generate_customized_resume,
    calculate_ats_score, rewrite_resume_for_job
)
from utils.docx_generator import markdown_to_docx
from utils.profile_store import (
    load_profile, save_profile, merge_cv_data,
    extract_profile_from_text, get_profile_summary
)
from utils.linkedin_scraper import fetch_linkedin_data, generate_linkedin_enhancement_suggestions

# ── Session State Initialization ──────────────────────────────────────────────
defaults = {
    "analysis_results": None,
    "bias_results": None,
    "resume_text": None,
    "customized_resume": None,
    "ats_results": None,
    "rewritten_resume": None,
    "linkedin_data": None,
    "linkedin_suggestions": None,
    "profile_extracted": False,
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI CV Optimizer",
    page_icon="🤖",
    layout="wide",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .score-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 20px;
        border-radius: 12px;
        text-align: center;
        margin-bottom: 16px;
    }
    .ats-box {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        color: white;
        padding: 20px;
        border-radius: 12px;
        text-align: center;
        margin-bottom: 16px;
    }
    .ats-sub-box {
        background: #f9fafb;
        padding: 14px;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 8px;
    }
    .score-number { font-size: 3rem; font-weight: 800; }
    .score-label { font-size: 0.9rem; opacity: 0.85; }

    .badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 999px;
        font-size: 0.8rem;
        font-weight: 600;
        margin: 3px;
    }
    .badge-green  { background: #d1fae5; color: #065f46; }
    .badge-red    { background: #fee2e2; color: #991b1b; }
    .badge-yellow { background: #fef3c7; color: #92400e; }
    .badge-blue   { background: #dbeafe; color: #1e40af; }
    .badge-purple { background: #ede9fe; color: #5b21b6; }

    .rec-strong-yes { color: #065f46; font-weight: 700; font-size: 1.2rem; }
    .rec-yes        { color: #1d4ed8; font-weight: 700; font-size: 1.2rem; }
    .rec-maybe      { color: #92400e; font-weight: 700; font-size: 1.2rem; }
    .rec-no         { color: #991b1b; font-weight: 700; font-size: 1.2rem; }

    .profile-card {
        background: #f0fdf4;
        border: 1px solid #bbf7d0;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 12px;
    }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.title("🤖 AI CV Optimizer")
st.caption("Powered by Gemini / Claude / Ollama · Upload a CV, get ATS scores, rewrite for any job, and leverage your LinkedIn profile")
st.divider()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")

    provider = st.selectbox(
        "AI Provider",
        options=["Gemini (Google)", "Claude (Anthropic)", "Ollama / Custom Server"],
        index=0,
        help="Select the AI backend."
    )

    api_key = ""
    base_url = ""
    model_name = ""

    if provider == "Gemini (Google)":
        api_key = st.text_input(
            "Gemini API Key",
            type="password",
            value=os.environ.get("GOOGLE_API_KEY", ""),
            help="Get yours at aistudio.google.com"
        )
        model_name = st.selectbox(
            "Gemini Model",
            options=[
                # ── Latest Flash (fast & cheap) ──
                "gemini-3.8-flash",
                "gemini-3.7-flash",
                "gemini-3.6-flash",
                "gemini-3.5-flash",
                # ── Pro (highest quality) ──
                "gemini-3.1-pro-preview",
                # ── Lite (ultra-fast, lightweight) ──
                "gemini-3.5-flash-lite",
                "gemini-3.1-flash-lite",
                # ── Stable / Older ──
                "gemini-2.0-flash",
            ],
            index=0,
            help="Switch models if one is overloaded. Flash = fast & cheap, Pro = highest quality, Lite = ultra-fast."
        )
        if api_key:
            os.environ["GOOGLE_API_KEY"] = api_key
    elif provider == "Claude (Anthropic)":
        api_key = st.text_input(
            "Anthropic API Key",
            type="password",
            value=os.environ.get("ANTHROPIC_API_KEY", ""),
            help="Get yours at console.anthropic.com"
        )
        if api_key:
            os.environ["ANTHROPIC_API_KEY"] = api_key
    else:
        base_url = st.text_input(
            "Ollama / Server URL",
            value="http://100.76.120.83:11434",
            help="E.g., http://localhost:11434 for local, or http://100.x.y.z:11434 for Tailscale"
        )
        model_name = st.text_input(
            "Model Name",
            value="phi3:mini",
            help="E.g., llama3, mistral, qwen2.5, phi3, etc."
        )
        api_key = st.text_input(
            "API Key (Optional)",
            type="password",
            help="Optional token if your custom endpoint is behind an authenticated reverse proxy"
        )

    st.divider()
    check_bias = st.toggle("🔍 Bias check on job description", value=False,
                            help="Scan the job description for biased language")

    # ── Stored Profile Section ────────────────────────────────────────────────
    st.divider()
    st.header("👤 Stored Profile")
    profile = load_profile()
    if profile.get("name"):
        st.markdown(f'<div class="profile-card"><strong>{profile["name"]}</strong><br>'
                    f'<small>{profile.get("email", "")} · {profile.get("location", "")}</small><br>'
                    f'<small>{len(profile.get("skills", []))} skills · '
                    f'{len(profile.get("experience", []))} roles · '
                    f'{len(profile.get("certifications", []))} certs</small></div>',
                    unsafe_allow_html=True)
        with st.expander("📋 Full Profile Details"):
            st.text(get_profile_summary(profile))
        if st.button("🗑️ Clear Profile", use_container_width=True):
            from utils.profile_store import _get_profile_path
            path = _get_profile_path()
            if path.exists():
                path.unlink()
            st.success("Profile cleared!")
            st.rerun()
    else:
        st.caption("No profile stored yet. Upload a CV and it will be saved automatically.")

    st.divider()
    st.markdown("**How it works**")
    st.markdown("""
1. Upload a PDF CV  
2. Paste the job description  
3. Click **Analyze** for match + ATS score  
4. **Rewrite** your CV for the specific job  
5. Connect LinkedIn for extra data  
""")

# ── Main Tabs ─────────────────────────────────────────────────────────────────
tab_analyze, tab_rewrite, tab_linkedin, tab_profile = st.tabs([
    "📊 Analyze & ATS Score", "✨ Rewrite CV", "🔗 LinkedIn", "👤 My Profile"
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: ANALYZE & ATS SCORE
# ══════════════════════════════════════════════════════════════════════════════
with tab_analyze:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📄 CV / Resume")
        uploaded_file = st.file_uploader("Upload PDF", type=["pdf"], key="analyze_upload")
        if uploaded_file:
            st.success(f"✅ {uploaded_file.name} uploaded")

    with col2:
        st.subheader("📋 Job Description")
        job_description = st.text_area(
            "Paste the full job description here",
            height=260,
            placeholder="e.g. We are looking for a Machine Learning Engineer with 3+ years experience in Python, PyTorch...",
            key="analyze_jd"
        )

    st.divider()

    analyze_btn = st.button("🚀 Analyze Resume + ATS Score", type="primary", use_container_width=True)

    if analyze_btn:
        # Validation
        if provider == "Gemini (Google)" and not api_key:
            st.error("⚠️ Please enter your Gemini API key in the sidebar.")
            st.stop()
        if provider == "Claude (Anthropic)" and not api_key and not os.environ.get("ANTHROPIC_API_KEY"):
            st.error("⚠️ Please enter your Anthropic API key in the sidebar.")
            st.stop()
        if provider == "Ollama / Custom Server" and not base_url.strip():
            st.error("⚠️ Please enter your Ollama Server URL.")
            st.stop()
        if provider == "Ollama / Custom Server" and not model_name.strip():
            st.error("⚠️ Please enter a Model Name.")
            st.stop()

        if not uploaded_file:
            st.error("⚠️ Please upload a CV PDF.")
            st.stop()
        if not job_description.strip():
            st.error("⚠️ Please paste a job description.")
            st.stop()

        # Extract PDF text
        with st.spinner("📖 Reading CV..."):
            try:
                resume_text = extract_text_from_pdf(uploaded_file)
                if not resume_text:
                    st.error("❌ Could not extract text from this PDF. It may be a scanned image.")
                    st.stop()
            except ValueError as e:
                st.error(f"❌ {e}")
                st.stop()

        # Auto-extract and store profile
        with st.spinner("👤 Extracting profile data from CV..."):
            try:
                extracted = extract_profile_from_text(
                    resume_text=resume_text,
                    provider=provider,
                    api_key=api_key,
                    base_url=base_url,
                    model_name=model_name
                )
                if extracted:
                    current_profile = load_profile()
                    merged = merge_cv_data(current_profile, extracted)
                    save_profile(merged)
                    st.session_state["profile_extracted"] = True
            except Exception as e:
                st.warning(f"⚠️ Could not extract profile data: {e}")

        # Analyze with AI
        provider_label = provider.split(" ")[0]
        with st.spinner(f"🤖 Analyzing with {provider_label}..."):
            try:
                result = analyze_resume(
                    resume_text=resume_text,
                    job_description=job_description,
                    provider=provider,
                    api_key=api_key,
                    base_url=base_url,
                    model_name=model_name
                )
            except Exception as e:
                st.error(f"❌ Analysis failed: {e}")
                st.stop()

        # ATS Score
        with st.spinner(f"📊 Calculating ATS score..."):
            try:
                ats_result = calculate_ats_score(
                    resume_text=resume_text,
                    job_description=job_description,
                    provider=provider,
                    api_key=api_key,
                    base_url=base_url,
                    model_name=model_name
                )
            except Exception as e:
                st.warning(f"⚠️ ATS scoring failed: {e}")
                ats_result = None

        # Optional bias check
        bias_result = None
        if check_bias:
            with st.spinner("🔍 Checking job description for bias..."):
                try:
                    bias_result = check_job_description_bias(
                        job_description=job_description,
                        provider=provider,
                        api_key=api_key,
                        base_url=base_url,
                        model_name=model_name
                    )
                except Exception as e:
                    st.warning(f"Bias check failed — continuing without it. (Error: {e})")

        # Store results in session state for persistence
        st.session_state["resume_text"] = resume_text
        st.session_state["analysis_results"] = result
        st.session_state["ats_results"] = ats_result
        st.session_state["bias_results"] = bias_result
        st.session_state["customized_resume"] = None
        st.session_state["rewritten_resume"] = None

    # ── Display Results ───────────────────────────────────────────────────────
    if st.session_state["analysis_results"] is not None:
        result = st.session_state["analysis_results"]
        bias_result = st.session_state["bias_results"]
        ats_result = st.session_state["ats_results"]
        resume_text = st.session_state["resume_text"]

        if st.session_state.get("profile_extracted"):
            st.success("👤 Profile data extracted and saved from your CV!")
            st.session_state["profile_extracted"] = False

        st.divider()
        st.subheader("📊 Analysis Results")

        # ── ATS Score Section ─────────────────────────────────────────────────
        if ats_result:
            ats_col_main, ats_col_details = st.columns([1, 3])

            with ats_col_main:
                ats_score = ats_result.get("ats_score", 0)
                st.markdown(f"""
                <div class="ats-box">
                    <div class="score-number">{ats_score}</div>
                    <div class="score-label">ATS Score / 100</div>
                </div>
                """, unsafe_allow_html=True)
                st.progress(ats_score / 100)

            with ats_col_details:
                sub1, sub2, sub3 = st.columns(3)
                with sub1:
                    kw_pct = ats_result.get("keyword_match_pct", 0)
                    color = "#065f46" if kw_pct >= 70 else "#92400e" if kw_pct >= 40 else "#991b1b"
                    st.markdown(f"""
                    <div class="ats-sub-box">
                        <div style="font-size:1.5rem; font-weight:700; color:{color}">{kw_pct}%</div>
                        <div style="font-size:0.75rem; color:#6b7280">Keyword Match</div>
                    </div>
                    """, unsafe_allow_html=True)
                with sub2:
                    fmt_score = ats_result.get("formatting_score", 0)
                    color = "#065f46" if fmt_score >= 70 else "#92400e" if fmt_score >= 40 else "#991b1b"
                    st.markdown(f"""
                    <div class="ats-sub-box">
                        <div style="font-size:1.5rem; font-weight:700; color:{color}">{fmt_score}</div>
                        <div style="font-size:0.75rem; color:#6b7280">Formatting</div>
                    </div>
                    """, unsafe_allow_html=True)
                with sub3:
                    sec_score = ats_result.get("section_completeness", 0)
                    color = "#065f46" if sec_score >= 70 else "#92400e" if sec_score >= 40 else "#991b1b"
                    st.markdown(f"""
                    <div class="ats-sub-box">
                        <div style="font-size:1.5rem; font-weight:700; color:{color}">{sec_score}</div>
                        <div style="font-size:0.75rem; color:#6b7280">Section Completeness</div>
                    </div>
                    """, unsafe_allow_html=True)

                # Keyword matches & missing
                kw_col1, kw_col2 = st.columns(2)
                with kw_col1:
                    st.markdown("**🎯 Matched Keywords**")
                    kw_matches = ats_result.get("keyword_matches", [])
                    if kw_matches:
                        badges = " ".join([f'<span class="badge badge-green">{k}</span>' for k in kw_matches])
                        st.markdown(badges, unsafe_allow_html=True)
                    else:
                        st.caption("None detected")
                with kw_col2:
                    st.markdown("**🚫 Missing Keywords**")
                    kw_missing = ats_result.get("missing_keywords", [])
                    if kw_missing:
                        badges = " ".join([f'<span class="badge badge-red">{k}</span>' for k in kw_missing])
                        st.markdown(badges, unsafe_allow_html=True)
                    else:
                        st.caption("None — great coverage!")

            # ATS detailed feedback expander
            with st.expander("📋 Detailed ATS Feedback"):
                # Section feedback
                section_fb = ats_result.get("section_feedback", {})
                if section_fb:
                    for section, feedback in section_fb.items():
                        st.markdown(f"**{section.title()}:** {feedback}")

                # Formatting issues
                fmt_issues = ats_result.get("formatting_issues", [])
                if fmt_issues:
                    st.markdown("**⚠️ Formatting Issues:**")
                    for issue in fmt_issues:
                        st.markdown(f"- {issue}")

                # Improvement tips
                tips = ats_result.get("improvement_tips", [])
                if tips:
                    st.markdown("**💡 Improvement Tips:**")
                    for tip in tips:
                        st.markdown(f"- {tip}")

            st.divider()

        # ── Match Score Section ───────────────────────────────────────────────
        top_left, top_mid, top_right = st.columns([1, 1, 2])

        with top_left:
            score = result.get("match_score", 0)
            st.markdown(f"""
            <div class="score-box">
                <div class="score-number">{score}</div>
                <div class="score-label">Match Score / 100</div>
            </div>
            """, unsafe_allow_html=True)
            st.progress(score / 100)

        with top_mid:
            rec = result.get("recommendation", "—")
            rec_class = {
                "Strong Yes": "rec-strong-yes",
                "Yes": "rec-yes",
                "Maybe": "rec-maybe",
                "No": "rec-no",
            }.get(rec, "rec-maybe")

            st.markdown("**Recommendation**")
            st.markdown(f'<div class="{rec_class}">{rec}</div>', unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("**Experience Level**")
            st.markdown(f"🏷️ {result.get('experience_level', '—')}")

        with top_right:
            st.markdown("**Recruiter Summary**")
            st.info(result.get("summary", ""))

        st.divider()

        # Skills section
        skill_col1, skill_col2 = st.columns(2)

        with skill_col1:
            st.markdown("**✅ Matched Skills**")
            matched = result.get("matched_skills", [])
            if matched:
                badges = " ".join([f'<span class="badge badge-green">{s}</span>' for s in matched])
                st.markdown(badges, unsafe_allow_html=True)
            else:
                st.caption("None found")

        with skill_col2:
            st.markdown("**❌ Missing Skills**")
            missing = result.get("missing_skills", [])
            if missing:
                badges = " ".join([f'<span class="badge badge-red">{s}</span>' for s in missing])
                st.markdown(badges, unsafe_allow_html=True)
            else:
                st.caption("None — great match!")

        st.divider()

        # Strengths & concerns
        detail_col1, detail_col2 = st.columns(2)

        with detail_col1:
            st.markdown("**💪 Strengths**")
            for s in result.get("strengths", []):
                st.markdown(f"- {s}")

        with detail_col2:
            st.markdown("**⚠️ Concerns**")
            concerns = result.get("concerns", [])
            if concerns:
                for c in concerns:
                    st.markdown(f"- {c}")
            else:
                st.caption("No major concerns")

        # Bias check results
        if bias_result:
            st.divider()
            st.subheader("🔍 Job Description Bias Check")

            b_col1, b_col2 = st.columns([1, 3])
            with b_col1:
                bias_score = bias_result.get("bias_score", 0)
                color = "#065f46" if bias_score < 30 else "#92400e" if bias_score < 60 else "#991b1b"
                st.markdown(f"""
                <div style="text-align:center; padding:16px; background:#f9fafb; border-radius:10px">
                    <div style="font-size:2rem; font-weight:800; color:{color}">{bias_score}</div>
                    <div style="font-size:0.8rem; color:#6b7280">Bias Score / 100</div>
                </div>
                """, unsafe_allow_html=True)

            with b_col2:
                st.markdown(f"**Assessment:** {bias_result.get('overall_assessment', '')}")
                flagged = bias_result.get("flagged_phrases", [])
                if flagged:
                    st.markdown("**Flagged phrases:** " + " ".join(
                        [f'<span class="badge badge-yellow">{p}</span>' for p in flagged]
                    ), unsafe_allow_html=True)
                suggestions = bias_result.get("suggestions", [])
                if suggestions:
                    st.markdown("**Suggestions:**")
                    for s in suggestions:
                        st.markdown(f"- {s}")

        # Raw resume text expander
        with st.expander("🔎 View extracted CV text"):
            st.text(resume_text)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: REWRITE CV
# ══════════════════════════════════════════════════════════════════════════════
with tab_rewrite:
    st.subheader("✨ AI CV Rewriter")
    st.markdown(
        "Generate a tailored, ATS-friendly version of your CV optimized for a specific job description. "
        "This leverages your **stored profile data** and **LinkedIn achievements** for the best results."
    )

    rewrite_col1, rewrite_col2 = st.columns(2)

    with rewrite_col1:
        st.markdown("**📄 CV / Resume**")
        rewrite_upload = st.file_uploader("Upload PDF", type=["pdf"], key="rewrite_upload")
        if rewrite_upload:
            st.success(f"✅ {rewrite_upload.name} uploaded")
        elif st.session_state.get("resume_text"):
            st.info("💡 Using CV from the Analyze tab")

    with rewrite_col2:
        st.markdown("**📋 Job Description**")
        rewrite_jd = st.text_area(
            "Paste the job description",
            height=200,
            placeholder="Paste the job description you want to tailor your CV for...",
            key="rewrite_jd"
        )

    # Options
    st.divider()
    use_profile = st.checkbox("📁 Use stored profile data", value=True,
                                help="Include all historical skills and experience from your stored profile")
    use_linkedin = st.checkbox("🔗 Use LinkedIn data", value=True,
                                help="Include certifications and achievements from your LinkedIn profile")

    st.divider()

    if st.session_state.get("rewritten_resume"):
        st.success("✅ Rewritten CV generated!")

        dl_md_col, dl_docx_col, space_col = st.columns([1, 1, 2])
        with dl_md_col:
            st.download_button(
                label="📥 Download Markdown (.md)",
                data=st.session_state["rewritten_resume"],
                file_name="tailored_cv.md",
                mime="text/markdown",
                use_container_width=True
            )
        with dl_docx_col:
            try:
                docx_bytes = markdown_to_docx(st.session_state["rewritten_resume"])
                st.download_button(
                    label="📥 Download MS Word (.docx)",
                    data=docx_bytes,
                    file_name="tailored_cv.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"❌ Failed to compile Word Document: {e}")

        with st.expander("📝 View & Copy Rewritten CV", expanded=True):
            st.markdown(st.session_state["rewritten_resume"])
            st.divider()
            st.text_area("Raw Markdown (for copying):", value=st.session_state["rewritten_resume"], height=400)

        if st.button("🪄 Re-generate", use_container_width=True, key="regen_rewrite"):
            st.session_state["rewritten_resume"] = None
            st.rerun()
    else:
        rewrite_btn = st.button("🪄 Rewrite My CV", type="primary", use_container_width=True)
        if rewrite_btn:
            # Validation
            if provider == "Gemini (Google)" and not api_key:
                st.error("⚠️ Please enter your Gemini API key in the sidebar.")
                st.stop()
            if provider == "Claude (Anthropic)" and not api_key and not os.environ.get("ANTHROPIC_API_KEY"):
                st.error("⚠️ Please enter your Anthropic API key in the sidebar.")
                st.stop()

            # Get resume text
            r_text = None
            if rewrite_upload:
                with st.spinner("📖 Reading CV..."):
                    try:
                        r_text = extract_text_from_pdf(rewrite_upload)
                    except ValueError as e:
                        st.error(f"❌ {e}")
                        st.stop()
            elif st.session_state.get("resume_text"):
                r_text = st.session_state["resume_text"]

            if not r_text:
                st.error("⚠️ Please upload a CV or analyze one first in the Analyze tab.")
                st.stop()
            if not rewrite_jd.strip():
                st.error("⚠️ Please paste a job description.")
                st.stop()

            # Gather profile and LinkedIn data
            stored = load_profile() if use_profile else None
            li_data = None
            if use_linkedin:
                profile = load_profile()
                li_data = profile.get("linkedin_data") if profile.get("linkedin_data") else None

            provider_label = provider.split(" ")[0]
            with st.spinner(f"✨ Rewriting your CV with {provider_label}..."):
                try:
                    rewritten = rewrite_resume_for_job(
                        resume_text=r_text,
                        job_description=rewrite_jd,
                        stored_profile=stored,
                        linkedin_data=li_data,
                        provider=provider,
                        api_key=api_key,
                        base_url=base_url,
                        model_name=model_name
                    )
                    st.session_state["rewritten_resume"] = rewritten
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Failed to rewrite CV: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3: LINKEDIN
# ══════════════════════════════════════════════════════════════════════════════
with tab_linkedin:
    st.subheader("🔗 LinkedIn Profile Integration")
    st.markdown(
        "Import your LinkedIn certificates, achievements, skills, and courses "
        "to enrich your CV rewrites. Since LinkedIn blocks direct scraping, "
        "you'll need to paste your profile text."
    )

    st.info(
        "**How to get your LinkedIn data:**\n"
        "1. Go to your LinkedIn profile page\n"
        "2. Scroll down to load all sections\n"
        "3. Select all text (Ctrl+A) and copy (Ctrl+C)\n"
        "4. Paste it in the text area below"
    )

    linkedin_url = st.text_input(
        "LinkedIn Profile URL",
        placeholder="https://www.linkedin.com/in/your-profile",
        help="Your LinkedIn profile URL (stored for reference)"
    )

    linkedin_text = st.text_area(
        "Paste your LinkedIn profile text here",
        height=300,
        placeholder="Paste the full text from your LinkedIn profile page...",
        key="linkedin_text"
    )

    st.divider()

    if st.session_state.get("linkedin_data"):
        li_data = st.session_state["linkedin_data"]
        st.success("✅ LinkedIn data extracted and saved!")

        li_cols = st.columns(3)
        with li_cols[0]:
            st.markdown("**🏆 Certifications**")
            certs = li_data.get("certifications", [])
            if certs:
                for c in certs:
                    st.markdown(f"- {c}")
            else:
                st.caption("None found")

        with li_cols[1]:
            st.markdown("**🌟 Achievements**")
            achievements = li_data.get("achievements", [])
            if achievements:
                for a in achievements:
                    st.markdown(f"- {a}")
            else:
                st.caption("None found")

        with li_cols[2]:
            st.markdown("**📚 Courses**")
            courses = li_data.get("courses", [])
            if courses:
                for c in courses:
                    st.markdown(f"- {c}")
            else:
                st.caption("None found")

        # Skills and Volunteer
        li_cols2 = st.columns(2)
        with li_cols2[0]:
            st.markdown("**🛠️ Skills**")
            skills = li_data.get("skills", [])
            if skills:
                badges = " ".join([f'<span class="badge badge-blue">{s}</span>' for s in skills])
                st.markdown(badges, unsafe_allow_html=True)
            else:
                st.caption("None found")

        with li_cols2[1]:
            st.markdown("**🤝 Volunteer**")
            volunteer = li_data.get("volunteer", [])
            if volunteer:
                for v in volunteer:
                    st.markdown(f"- {v}")
            else:
                st.caption("None found")

        # Enhancement suggestions
        st.divider()
        if st.button("💡 Get CV Enhancement Suggestions", use_container_width=True):
            profile = load_profile()
            with st.spinner("Generating suggestions..."):
                try:
                    suggestions = generate_linkedin_enhancement_suggestions(
                        profile=profile,
                        linkedin_data=li_data,
                        provider=provider,
                        api_key=api_key,
                        base_url=base_url,
                        model_name=model_name
                    )
                    st.session_state["linkedin_suggestions"] = suggestions
                except Exception as e:
                    st.error(f"❌ Error: {e}")

        if st.session_state.get("linkedin_suggestions"):
            st.subheader("💡 Enhancement Suggestions")
            st.markdown(st.session_state["linkedin_suggestions"])

        if st.button("🔄 Re-import LinkedIn Data", use_container_width=True):
            st.session_state["linkedin_data"] = None
            st.session_state["linkedin_suggestions"] = None
            st.rerun()

    else:
        extract_li_btn = st.button("🔍 Extract LinkedIn Data", type="primary", use_container_width=True)
        if extract_li_btn:
            if not linkedin_text.strip():
                st.error("⚠️ Please paste your LinkedIn profile text.")
                st.stop()

            if provider == "Gemini (Google)" and not api_key:
                st.error("⚠️ Please enter your Gemini API key in the sidebar.")
                st.stop()
            if provider == "Claude (Anthropic)" and not api_key:
                st.error("⚠️ Please enter your API key in the sidebar.")
                st.stop()

            with st.spinner("🔍 Extracting data from LinkedIn text..."):
                try:
                    li_data = fetch_linkedin_data(
                        linkedin_url=linkedin_url,
                        provider=provider,
                        api_key=api_key,
                        base_url=base_url,
                        model_name=model_name,
                        pasted_text=linkedin_text
                    )
                    st.session_state["linkedin_data"] = li_data

                    # Save to profile
                    profile = load_profile()
                    if linkedin_url:
                        profile["linkedin_url"] = linkedin_url
                    profile["linkedin_data"] = li_data

                    # Also merge LinkedIn skills and certs into profile
                    merge_data = {
                        "skills": li_data.get("skills", []),
                        "certifications": li_data.get("certifications", []),
                        "achievements": li_data.get("achievements", []),
                    }
                    merged = merge_cv_data(profile, merge_data)
                    save_profile(merged)

                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Failed to extract LinkedIn data: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4: MY PROFILE
# ══════════════════════════════════════════════════════════════════════════════
with tab_profile:
    st.subheader("👤 My Stored Profile")
    st.markdown(
        "This profile is automatically built from all CVs you upload. "
        "It stores your complete career history, skills, and credentials. "
        "When you rewrite a CV, this data is used to pull in relevant experience "
        "you might have left out."
    )

    profile = load_profile()

    if not profile.get("name"):
        st.info("📭 No profile data yet. Upload a CV in the **Analyze** tab to get started!")
    else:
        # Contact info
        st.markdown("### 📇 Contact Information")
        p_col1, p_col2, p_col3, p_col4 = st.columns(4)
        with p_col1:
            st.metric("Name", profile.get("name", "—"))
        with p_col2:
            st.metric("Email", profile.get("email", "—"))
        with p_col3:
            st.metric("Phone", profile.get("phone", "—"))
        with p_col4:
            st.metric("Location", profile.get("location", "—"))

        # Summary
        if profile.get("summary"):
            st.markdown("### 📝 Professional Summary")
            st.info(profile["summary"])

        # Skills
        st.markdown("### 🛠️ Skills")
        skills = profile.get("skills", [])
        if skills:
            badges = " ".join([f'<span class="badge badge-blue">{s}</span>' for s in skills])
            st.markdown(badges, unsafe_allow_html=True)
        else:
            st.caption("No skills recorded yet")

        # Experience
        st.markdown("### 💼 Experience")
        experience = profile.get("experience", [])
        if experience:
            for exp in experience:
                with st.expander(f"**{exp.get('title', 'Role')}** at {exp.get('company', 'Company')} — {exp.get('dates', '')}"):
                    for bullet in exp.get("bullets", []):
                        st.markdown(f"- {bullet}")
        else:
            st.caption("No experience recorded yet")

        # Education
        st.markdown("### 🎓 Education")
        education = profile.get("education", [])
        if education:
            for edu in education:
                st.markdown(f"- **{edu.get('degree', '')}** — {edu.get('institution', '')} ({edu.get('dates', '')})")
                if edu.get("details"):
                    st.caption(f"  {edu['details']}")
        else:
            st.caption("No education recorded yet")

        # Certifications & Achievements
        cert_col, ach_col = st.columns(2)
        with cert_col:
            st.markdown("### 🏆 Certifications")
            certs = profile.get("certifications", [])
            if certs:
                for c in certs:
                    st.markdown(f"- {c}")
            else:
                st.caption("None yet")

        with ach_col:
            st.markdown("### 🌟 Achievements")
            achievements = profile.get("achievements", [])
            if achievements:
                for a in achievements:
                    st.markdown(f"- {a}")
            else:
                st.caption("None yet")

        # LinkedIn data
        if profile.get("linkedin_url"):
            st.markdown(f"### 🔗 LinkedIn: [{profile['linkedin_url']}]({profile['linkedin_url']})")

        # Last updated
        if profile.get("last_updated"):
            st.caption(f"Last updated: {profile['last_updated']}")

        # Export
        st.divider()
        export_col1, export_col2 = st.columns(2)
        with export_col1:
            st.download_button(
                label="📥 Export Profile (JSON)",
                data=__import__("json").dumps(profile, indent=2),
                file_name="cv_profile.json",
                mime="application/json",
                use_container_width=True
            )
        with export_col2:
            if st.button("🗑️ Reset Profile", use_container_width=True, type="secondary"):
                from utils.profile_store import _get_profile_path
                path = _get_profile_path()
                if path.exists():
                    path.unlink()
                st.success("Profile cleared!")
                st.rerun()
