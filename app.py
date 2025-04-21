import streamlit as st
import google.generativeai as genai
import os
import time
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

# Session state
if 'resume_generated' not in st.session_state:
    st.session_state.resume_generated = False
if 'ats_score' not in st.session_state:
    st.session_state.ats_score = None
if 'resume_suggestions' not in st.session_state:
    st.session_state.resume_suggestions = []
if 'resume_content' not in st.session_state:
    st.session_state.resume_content = ""

# Load external CSS
with open("style.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Gemini model loader
@st.cache_resource(show_spinner=False)
def get_model():
    return genai.GenerativeModel('gemini-1.5-flash')

# Retry wrapper
def safe_api_call(func, *args, **kwargs):
    max_retries = 5
    delay = 2
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait_time = delay * (2 ** attempt)
            st.warning(f"API error. Retrying in {wait_time} sec...")
            time.sleep(wait_time)
    raise Exception("API request failed.")

# Resume generator
def generate_resume(inputs, role):
    model = get_model()
    experience_details = inputs['experience']['details'].replace('. ', '.\n- ')
    prompt = f"""Generate an ATS-friendly resume tailored for a {role} role in strict Markdown format:
## Personal Information
**Name:** {inputs['name']}
**Contact:** {inputs['contact']}

## Professional Summary
{inputs['summary']}

## Work Experience
**{inputs['experience']['title']} at {inputs['experience']['company']}**
- {experience_details}

## Skills
{', '.join(inputs['skills'])}

## Education
{inputs['education']}

Use Markdown only. No tables. Keep it under 800 words.
"""
    try:
        response = safe_api_call(model.generate_content, prompt)
        return response.text.strip()
    except Exception as e:
        st.error(f"Resume generation failed: {e}")
        return None

# ATS score analyzer
def calculate_ats_score(resume_text):
    model = get_model()
    analysis_prompt = f"""
Analyze this resume and return a JSON response:
- "score" (0–100): ATS compatibility score.
- "suggestions" (array of up to 5 strings): actionable improvements.

Format: {{"score": int, "suggestions": [string, ...]}}

Resume:
{resume_text}
"""
    try:
        response = safe_api_call(model.generate_content, analysis_prompt)
        response_text = response.text.strip()
        if '```json' in response_text:
            response_text = response_text.split('```json')[1].split('```')[0].strip()
        analysis = json.loads(response_text)
        return {
            "score": max(0, min(100, int(analysis["score"]))),
            "suggestions": analysis["suggestions"][:5]
        }
    except json.JSONDecodeError as e:
        st.error(f"Failed to parse analysis: {e}")
        return None
    except Exception as e:
        st.error(f"Analysis failed: {e}")
        return None

# Streamlit app
def main():
    st.title("📄 Smart Resume Builder")
    st.markdown("**AI-Powered Resume Generator with ATS Optimization**")

    # Sidebar form
    with st.sidebar:
        with st.form("resume_form"):
            st.subheader("Personal Information")
            name = st.text_input("Full Name*").strip()
            email = st.text_input("Email*").strip()
            phone = st.text_input("Phone Number")
            linkedin = st.text_input("LinkedIn Profile")

            st.subheader("Professional Summary")
            summary = st.text_area("Summary*", height=100)

            st.subheader("Work Experience")
            job_title = st.text_input("Job Title*")
            company = st.text_input("Company Name*")
            experience = st.text_area("Experience Details*", height=100,
                                      placeholder="Separate achievements with periods.")

            st.subheader("Skills")
            skills = st.text_input("Skills (comma-separated)*")

            st.subheader("Education")
            education = st.text_input("Education Details*")

            st.subheader("Target Role")
            role = st.selectbox("Job Role*", ["Software Engineer", "Data Analyst", "Product Manager", "Other"])

            if st.form_submit_button("Generate Resume 🚀"):
                required = [name, email, summary, job_title, company, experience, skills, education]
                if not all(required):
                    st.error("Please fill all required fields (*)")
                    return

                inputs = {
                    "name": name,
                    "contact": f"{email} | {phone} | {linkedin}".strip(" |"),
                    "summary": summary,
                    "experience": {
                        "title": job_title,
                        "company": company,
                        "details": experience
                    },
                    "skills": [s.strip() for s in skills.split(",")],
                    "education": education
                }

                with st.spinner("Crafting your resume..."):
                    resume = generate_resume(inputs, role)
                    if resume:
                        st.session_state.resume_content = resume
                        analysis = calculate_ats_score(resume)
                        if analysis:
                            st.session_state.ats_score = analysis["score"]
                            st.session_state.resume_suggestions = analysis["suggestions"]
                            st.session_state.resume_generated = True
                            st.success("✅ Resume generated and analyzed!")
                        else:
                            st.error("ATS analysis failed.")

    # Main content
    if st.session_state.resume_generated:
        st.markdown("---")
        col1, col2 = st.columns([3, 2])

        with col1:
            st.subheader("Your Resume")
            st.markdown(st.session_state.resume_content)
            st.download_button(
                label="📥 Download Resume",
                data=st.session_state.resume_content,
                file_name="smart_resume.md",
                mime="text/markdown"
            )

        with col2:
            st.subheader("ATS Analysis")
            score = st.session_state.ats_score
            color = "#10b981" if score >= 75 else "#f4a261" if score >= 50 else "#e11d48"
            st.markdown(f"""
                <div style='text-align: center;'>
                    <h1 style='color: {color}; font-size: 48px;'>{score}/100</h1>
                    <p>ATS Compatibility Score</p>
                </div>
            """, unsafe_allow_html=True)

            with st.expander("Improvement Suggestions"):
                for i, suggestion in enumerate(st.session_state.resume_suggestions, 1):
                    st.markdown(f"**{i}.** {suggestion}")

if __name__ == "__main__":
    main()
