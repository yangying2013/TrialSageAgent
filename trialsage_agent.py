import streamlit as st
import google.generativeai as genai
import pdfplumber
import os
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
# Configure the Gemini API key
try:
    api_key = os.getenv("API_KEY")
    if not api_key:
        st.error("API_KEY not found. Please set it in your .env file.")
        st.stop()
    genai.configure(api_key=api_key)
except Exception as e:
    st.error(f"Error configuring Gemini API: {e}")
    st.stop()

# System instruction for the AI agent
SYSTEM_INSTRUCTION = """You are an expert AI assistant for analyzing clinical trial protocols. Your task is to extract key information from the provided text and return it as a structured JSON object.

The JSON object MUST have these six keys: "officialTitle", "phase", "sponsor", "objective", "eligibility", and "endpoints".

- officialTitle: Find the official title of the study. If it's missing, use the string "Not specified".
- phase: Identify the trial phase (e.g., Phase 1, Phase 2, Not Applicable). If it's missing, use the string "Not specified".
- sponsor: Identify the primary sponsor of the trial. If it's missing, use the string "Not specified".

For the content of the "objective", "eligibility", and "endpoints" keys, use Markdown for formatting to improve readability. Use bullet points for lists (like inclusion/exclusion criteria or endpoints) and use bold formatting to highlight key terms.

- objective: Find the study's primary goal or purpose. Format with bolding for key concepts. If it's missing from the text, use the string "Not specified".
- eligibility: Find and summarize the inclusion and exclusion criteria. Use nested bullet points. For example:
  * **Inclusion Criteria:**
    * [Criteria 1]
    * [Criteria 2]
  * **Exclusion Criteria:**
    * [Criteria 1]
    * [Criteria 2]
  If it's missing from the text, use the string "Not specified".
- endpoints: Find the primary and secondary outcomes. Use bullet points for different endpoints. If it's missing from the text, use the string "Not specified".

Your output must be ONLY the valid JSON object. Do not include any other text, explanations, or markdown formatting outside of the JSON values."""

# --- Helper Functions ---

def extract_text_from_file(uploaded_file):
    """Extracts text from uploaded .txt, .md, or .pdf files."""
    if uploaded_file.name.lower().endswith('.pdf'):
        with pdfplumber.open(uploaded_file) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    else:
        return uploaded_file.getvalue().decode("utf-8")

def get_summary_from_gemini(protocol_text: str):
    """
    Calls the Gemini API to get a structured summary.
    Returns a dictionary with the summary or raises an exception on error.
    """
    required_keys = ["officialTitle", "phase", "sponsor", "objective", "eligibility", "endpoints"]
    
    try:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash", # Corrected to a stable version
            system_instruction=SYSTEM_INSTRUCTION,
        )
        
        response = model.generate_content(
            protocol_text,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
                temperature=0
            )
        )
        
        summary_data = json.loads(response.text)
        
        # Validate that all required keys are in the response
        if not all(key in summary_data for key in required_keys):
            raise ValueError("The AI response is missing one or more required keys.")
            
        return summary_data

    except Exception as e:
        st.error(f"An error occurred while generating the summary: {e}")
        return None


# --- Streamlit UI ---

st.set_page_config(page_title="TrialSage", layout="wide")

# Initialize session state
if "protocol_text" not in st.session_state:
    st.session_state.protocol_text = ""
if "summary" not in st.session_state:
    st.session_state.summary = None
if "loading" not in st.session_state:
    st.session_state.loading = False
if "error" not in st.session_state:
    st.session_state.error = None

# Create two columns
left_col, right_col = st.columns(2)

# --- Left Column (Input) ---
with left_col:
    st.title("TrialSage Protocol Summarizer")
    st.markdown("Paste your clinical trial protocol below or upload a file.")

    uploaded_file = st.file_uploader(
        "Upload Protocol File",
        type=['txt', 'md', 'pdf'],
        on_change=lambda: st.session_state.update(summary=None, error=None) # Clear old summary on new file
    )
    
    if uploaded_file:
        st.session_state.protocol_text = extract_text_from_file(uploaded_file)

    st.session_state.protocol_text = st.text_area(
        "Protocol Text",
        st.session_state.protocol_text,
        height=400,
        placeholder="Paste your protocol text here..."
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Generate Summary", type="primary", use_container_width=True):
            if not st.session_state.protocol_text.strip():
                st.session_state.error = "Please enter some protocol text or upload a file."
            else:
                st.session_state.loading = True
                st.session_state.summary = None
                st.session_state.error = None
                
    with col2:
        if st.button("Clear", use_container_width=True):
            st.session_state.protocol_text = ""
            st.session_state.summary = None
            st.session_state.error = None
            st.session_state.loading = False

# Handle summary generation
if st.session_state.loading:
    with right_col:
        with st.spinner('AI is analyzing the protocol...'):
            summary_result = get_summary_from_gemini(st.session_state.protocol_text)
            if summary_result:
                st.session_state.summary = summary_result
            else:
                # Error is handled and displayed within the get_summary_from_gemini function
                # We just need to ensure we capture that an error occurred.
                st.session_state.error = st.session_state.error or "Failed to generate summary. Check logs for details."
            st.session_state.loading = False
            st.rerun() # Rerun to update the display

# --- Right Column (Output) ---
with right_col:
    st.subheader("Analysis Results")

    if st.session_state.error:
        st.error(st.session_state.error)

    if not st.session_state.summary and not st.session_state.loading and not st.session_state.error:
        st.info("The generated summary will appear here.")
    
    if st.session_state.summary:
        summary = st.session_state.summary
        
        # Display Study Details
        st.markdown("### Study Details")
        st.markdown(f"**Official Title:** {summary.get('officialTitle', 'Not specified')}")
        st.markdown(f"**Phase:** {summary.get('phase', 'Not specified')}")
        st.markdown(f"**Sponsor:** {summary.get('sponsor', 'Not specified')}")
        st.divider()

        # Display Formatted Sections
        st.markdown("### Objective")
        st.markdown(summary.get('objective', 'Not specified'), unsafe_allow_html=True)
        st.divider()

        st.markdown("### Eligibility Criteria")
        st.markdown(summary.get('eligibility', 'Not specified'), unsafe_allow_html=True)
        st.divider()

        st.markdown("### Endpoints")
        st.markdown(summary.get('endpoints', 'Not specified'), unsafe_allow_html=True)
        
        # Plain text for copy button
        plain_text_summary = f"""
Official Title: {summary.get('officialTitle')}
Phase: {summary.get('phase')}
Sponsor: {summary.get('sponsor')}

Objective:
{summary.get('objective')}

Eligibility Criteria:
{summary.get('eligibility')}

Endpoints:
{summary.get('endpoints')}
"""
        st.code(plain_text_summary, language='text')
        st.markdown("*(The text above is formatted for easy copying.)*")