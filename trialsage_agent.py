import streamlit as st
import google.generativeai as genai
import pdfplumber
import os
import json

# --- Configuration ---
# Configure the Gemini API key
try:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        st.error("GOOGLE_API_KEY environment variable not found. Please set it in your system environment.")
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

def clean_pdf_artifacts(text):
    """Remove common PDF processing artifacts"""
    import re
    
    # Remove standalone PPD artifacts (but keep legitimate PPD abbreviations)
    text = re.sub(r'\bPPD\s*\n', '', text)  # PPD on its own line
    text = re.sub(r'\bPPD\s+PPD\s*', '', text)  # Multiple PPDs
    text = re.sub(r'(\s)PPD(\s)', r'\1\2', text)  # Isolated PPD with spaces
    
    # Fix some common number/letter patterns
    text = re.sub(r'\b(\d+)\s+ot\s+(\d+)\b', r'\1 to \2', text)  # "6 ot 2" → "6 to 2"
    
    # Remove excessive whitespace
    text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)  # Multiple blank lines
    text = re.sub(r' {3,}', '  ', text)  # Multiple spaces
    
    return text

def fix_reversed_text(text):
    """Fix reversed/mirrored text that sometimes appears in PDFs"""
    import re
    
    # Common reversed words patterns
    reversed_patterns = {
        'tuohsaW': 'Washout',
        'doireP': 'Period', 
        'skeew': 'weeks',
        'gnineercS': 'Screening',
        'tisiV': 'Visit',
        'gniwollof': 'following',
        'gnineercs': 'screening',
        'tnesnoC': 'Consent',
        'demrofnI': 'Informed',
        'gnitseT': 'Testing',
        'ycnangerP': 'Pregnancy',
        'kcehC': 'Check',
        'airetirC': 'Criteria',
        'ytilibigilE': 'Eligibility',
        'tneitap': 'patient',
        'syaD': 'Days',
        'motpmys': 'symptom',
        'gnitroper': 'reporting',
        'ylhtnom': 'monthly',
        'yliaD': 'Daily',
        'lawardhtiw': 'withdrawal',
        'ylrae': 'early',
        'enirU': 'Urine',
        'ecnO': 'Once',
        'reviL': 'Liver',
        'weiveR': 'Review',
        'lacisyhP': 'Physical',
        'thgieW': 'Weight',
        'thgieH': 'Height',
        'sutats': 'status',
        'nacs': 'scan',
        'sisongaid': 'diagnosis',
        'eugolana': 'analogue',
        'nitatsotamos': 'somatostatin',
        'smotpmys': 'symptoms',
        'tnemtaert': 'treatment',
        'sesylana': 'analyses',
        'eerf': 'free',
        'lleC': 'Cell',
        'elpmas': 'sample',
        'doolb': 'blood',
        'gniliforp': 'profiling',
        'cimoneg': 'genomic',
        'eliforp': 'profile',
        'ruoh': 'hour',
        'ninargomorhC': 'Chromogranin',
        'ninikorueN': 'Neurokinin',
        'seriannoitseuQ': 'Questionnaires',
        'tcejbuS': 'Subject',
        'noitartsinimdA': 'Administration',
        'noitacidem': 'medication',
        'tnatimocnoC': 'Concomitant',
        'lacigrus': 'surgical',
        'seipareht': 'therapies',
        'serudecorp': 'procedures',
        'gurd': 'drug',
        'tnevE': 'Event',
        'esrevdA': 'Adverse',
        'noitelpmoC': 'Completion'
    }
    
    # Replace reversed patterns
    for reversed_word, correct_word in reversed_patterns.items():
        text = re.sub(r'\b' + re.escape(reversed_word) + r'\b', correct_word, text, flags=re.IGNORECASE)
    
    return text

def decode_cid_codes(text):
    """Decode common CID codes to readable text"""
    # Common CID to character mappings
    cid_mappings = {
        '(cid:3)': ' ',      # space
        '(cid:20)': '1',     # number 1
        '(cid:21)': '2',     # number 2
        '(cid:22)': '3',     # number 3
        '(cid:23)': '4',     # number 4
        '(cid:24)': '5',     # number 5
        '(cid:25)': '6',     # number 6
        '(cid:26)': '7',     # number 7
        '(cid:27)': '8',     # number 8
        '(cid:28)': '9',     # number 9
        '(cid:19)': '0',     # number 0
        '(cid:36)': 'A',     # letter A
        '(cid:37)': 'B',     # letter B
        '(cid:38)': 'C',     # letter C
        '(cid:39)': 'D',     # letter D
        '(cid:40)': 'E',     # letter E
        '(cid:41)': 'F',     # letter F
        '(cid:42)': 'G',     # letter G
        '(cid:43)': 'H',     # letter H
        '(cid:44)': 'I',     # letter I
        '(cid:45)': 'J',     # letter J
        '(cid:46)': 'K',     # letter K
        '(cid:47)': 'L',     # letter L
        '(cid:48)': 'M',     # letter M
        '(cid:49)': 'N',     # letter N
        '(cid:50)': 'O',     # letter O
        '(cid:51)': 'P',     # letter P
        '(cid:52)': 'Q',     # letter Q
        '(cid:53)': 'R',     # letter R
        '(cid:54)': 'S',     # letter S
        '(cid:55)': 'T',     # letter T
        '(cid:56)': 'U',     # letter U
        '(cid:57)': 'V',     # letter V
        '(cid:58)': 'W',     # letter W
        '(cid:59)': 'X',     # letter X
        '(cid:60)': 'Y',     # letter Y
        '(cid:61)': 'Z',     # letter Z
        '(cid:68)': 'a',     # letter a
        '(cid:69)': 'b',     # letter b
        '(cid:70)': 'c',     # letter c
        '(cid:71)': 'd',     # letter d
        '(cid:72)': 'e',     # letter e
        '(cid:73)': 'f',     # letter f
        '(cid:74)': 'g',     # letter g
        '(cid:75)': 'h',     # letter h
        '(cid:76)': 'i',     # letter i
        '(cid:77)': 'j',     # letter j
        '(cid:78)': 'k',     # letter k
        '(cid:79)': 'l',     # letter l
        '(cid:80)': 'm',     # letter m
        '(cid:81)': 'n',     # letter n
        '(cid:82)': 'o',     # letter o
        '(cid:83)': 'p',     # letter p
        '(cid:84)': 'q',     # letter q
        '(cid:85)': 'r',     # letter r
        '(cid:86)': 's',     # letter s
        '(cid:87)': 't',     # letter t
        '(cid:88)': 'u',     # letter u
        '(cid:89)': 'v',     # letter v
        '(cid:90)': 'w',     # letter w
        '(cid:91)': 'x',     # letter x
        '(cid:92)': 'y',     # letter y
        '(cid:93)': 'z',     # letter z
        '(cid:177)': '-',    # dash
        '(cid:18)': '/',     # slash
        '(cid:17)': '.',     # period/full stop
        '(cid:29)': ':',     # colon
        '(cid:15)': ',',     # comma
        '(cid:11)': '(',     # opening parenthesis
        '(cid:12)': ')',     # closing parenthesis
        '(cid:138)': '®',    # registered trademark
        '(cid:16)': '-',     # hyphen/dash
        '(cid:14)': '.',     # period (alternative)
        '(cid:13)': ' ',     # space (alternative)
        '(cid:59)': ';',     # semicolon
        '(cid:33)': '!',     # exclamation mark
        '(cid:63)': '?',     # question mark
        '(cid:182)': "'",    # apostrophe
        '(cid:147)': '±',    # plus-minus sign
        '(cid:30)': ';',     # semicolon
        '(cid:120)': '•',    # bullet point
        '(cid:8)': '%',      # percent sign
        '(cid:31)': '≤',     # less than or equal to
        '(cid:32)': ' ',     # space (common)
        '(cid:9)': '\t',     # tab
        '(cid:179)': '"',    # opening quote
        '(cid:180)': '"',    # closing quote
        '(cid:119)': 'ï',    # i with diaeresis (naïve)
        '(cid:181)': 'μ',    # micro sign
        '(cid:34)': '?',     # question mark
        '(cid:66)': '_',     # underscore
    }
    
    # Replace CID codes with actual characters
    for cid, char in cid_mappings.items():
        text = text.replace(cid, char)
    
    return text

def extract_text_from_file(uploaded_file):
    """Extracts text from uploaded .txt, .md, or .pdf files."""
    if uploaded_file.name.lower().endswith('.pdf'):
        # Try alternative PDF library first
        st.write("🔄 Trying alternative PDF extraction method...")
        try:
            import PyPDF2
            uploaded_file.seek(0)  # Reset file pointer
            pdf_reader = PyPDF2.PdfReader(uploaded_file)
            alt_text_parts = []
            
            st.write(f"PyPDF2 found {len(pdf_reader.pages)} pages")
            for i, page in enumerate(pdf_reader.pages[:5]):  # Test first 5 pages
                try:
                    page_text = page.extract_text()
                    st.write(f"PyPDF2 Page {i+1}: {len(page_text)} chars")
                    if page_text.strip():
                        alt_text_parts.append(f"\n--- Page {i+1} (PyPDF2) ---\n")
                        alt_text_parts.append(page_text)
                except Exception as e:
                    st.write(f"PyPDF2 Page {i+1} failed: {e}")
            
            if alt_text_parts:
                st.success("✅ PyPDF2 extracted text successfully!")
                return "\n".join(alt_text_parts)
            else:
                st.warning("⚠️ PyPDF2 also failed, trying pdfplumber...")
        except ImportError:
            st.write("PyPDF2 not available, using pdfplumber...")
        except Exception as e:
            st.write(f"PyPDF2 extraction failed: {e}")
        
        # Reset file pointer for pdfplumber
        uploaded_file.seek(0)
        try:
            with pdfplumber.open(uploaded_file) as pdf:
                text_parts = []
                total_pages = len(pdf.pages)
                processed_pages = 0
                
                # Debug info
                st.info(f"📄 Found {total_pages} pages in PDF. Starting extraction...")
                st.write(f"PDF object type: {type(pdf)}")
                st.write(f"Pages list length: {len(pdf.pages)}")
                
                # Add progress bar for large PDFs
                if total_pages > 10:
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                
                empty_pages = 0
                error_pages = 0
                
                # Try to access each page first to see if there are issues
                st.write("Checking page accessibility...")
                for i, page in enumerate(pdf.pages[:5]):  # Check first 5 pages
                    try:
                        page_obj = pdf.pages[i]
                        st.write(f"Page {i+1}: {type(page_obj)} - OK")
                    except Exception as e:
                        st.error(f"Page {i+1}: Error accessing - {e}")
                
                st.write("Starting page-by-page extraction...")
                
                for page_num, page in enumerate(pdf.pages, 1):
                    st.write(f"Attempting to process page {page_num}...")
                    try:
                        # Update progress for large PDFs
                        if total_pages > 10:
                            progress = page_num / total_pages
                            progress_bar.progress(progress)
                            status_text.text(f"Processing page {page_num}/{total_pages}")
                        
                        # Try multiple extraction methods
                        page_text = ""
                        
                        # Method 1: Standard extraction
                        try:
                            page_text = page.extract_text() or ""
                            st.write(f"  Method 1 (extract_text): {len(page_text)} chars")
                        except Exception as e:
                            st.write(f"  Method 1 failed: {e}")
                        
                        # Method 2: Alternative extraction if Method 1 fails or is empty
                        if not page_text:
                            try:
                                # Try extracting words and joining them
                                words = page.extract_words()
                                if words:
                                    page_text = " ".join([word['text'] for word in words])
                                    st.write(f"  Method 2 (extract_words): {len(page_text)} chars")
                            except Exception as e:
                                st.write(f"  Method 2 failed: {e}")
                        
                        # Method 3: Character-level extraction if others fail
                        if not page_text:
                            try:
                                chars = page.chars
                                if chars:
                                    page_text = "".join([char['text'] for char in chars])
                                    st.write(f"  Method 3 (chars): {len(page_text)} chars")
                            except Exception as e:
                                st.write(f"  Method 3 failed: {e}")
                        
                        # Don't pre-clean CID codes here - let our decoder handle them
                        original_text = page_text
                        
                        # Debug: Check what we got from this page
                        text_length = len(original_text)
                        stripped_length = len(original_text.strip())
                        
                        # Show debug info for first few pages
                        if page_num <= 5:
                            st.write(f"Debug Page {page_num}: Raw length={text_length}, Stripped length={stripped_length}")
                            if text_length > 0:
                                preview = original_text[:100].replace('\n', '\\n')
                                st.write(f"Preview: {preview}...")
                        
                        # Process ALL pages that have any text content (including CID codes)
                        if original_text:  # Any text at all, even just whitespace or CID codes
                            text_parts.append(f"\n--- Page {page_num} (Raw: {text_length} chars, Clean: {stripped_length} chars) ---\n")
                            text_parts.append(original_text)
                            processed_pages += 1
                        
                        # If truly no text, try table extraction
                        else:
                            tables = page.extract_tables()
                            if tables:
                                text_parts.append(f"\n--- Page {page_num} (Table Data) ---\n")
                                table_text = []
                                for table in tables:
                                    for row in table:
                                        if row:
                                            table_text.append(" ".join([cell or "" for cell in row]))
                                if table_text:
                                    text_parts.extend(table_text)
                                    processed_pages += 1
                                else:
                                    empty_pages += 1
                            else:
                                empty_pages += 1
                        
                        # Limit processing for extremely large PDFs to prevent memory issues
                        if len(text_parts) > 1000:  # Roughly 50+ pages of content
                            st.warning(f"⚠️ Large PDF detected. Processing first {processed_pages} pages to avoid memory issues.")
                            break
                            
                    except Exception as page_error:
                        error_pages += 1
                        st.warning(f"⚠️ Error processing page {page_num}: {str(page_error)}")
                        continue
                
                # Clean up progress indicators
                if total_pages > 10:
                    progress_bar.empty()
                    status_text.empty()
                
                # Final status with breakdown
                st.success(f"✅ Successfully processed {processed_pages} pages out of {total_pages}")
                if empty_pages > 0:
                    st.info(f"📄 {empty_pages} pages were empty or contained no extractable text")
                if error_pages > 0:
                    st.warning(f"⚠️ {error_pages} pages had processing errors")
                
                extracted_text = "\n".join(text_parts)
                
                # Import re for regex operations
                import re
                
                # First decode CID codes
                decoded_text = decode_cid_codes(extracted_text)
                
                # Then fix reversed text
                fixed_text = fix_reversed_text(decoded_text)
                
                # Finally clean PDF artifacts
                cleaned_text = clean_pdf_artifacts(fixed_text)
                
                # Check processing results
                original_cid_count = len(re.findall(r'\(cid:\d+\)', extracted_text))
                remaining_cid_count = len(re.findall(r'\(cid:\d+\)', cleaned_text))
                
                if original_cid_count > 0:
                    st.info(f"🔧 Processing PDF issues: {original_cid_count} CID codes → {remaining_cid_count} remaining + fixed reversed text + cleaned artifacts")
                
                if remaining_cid_count > 5:
                    st.warning(f"⚠️ Still {remaining_cid_count} unrecognized characters remain. Suggestions:\n1. Try copying and pasting text content\n2. Use text version of the document\n3. Convert to Word format and try again")
                
                return cleaned_text
        except Exception as e:
            st.error(f"PDF processing error: {e}")
            return ""
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
            model_name="gemini-2.0-flash", # Using Gemini 2.0 Flash
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
    
    # Add PDF to TXT conversion option
    if uploaded_file and uploaded_file.name.lower().endswith('.pdf'):
        if st.button("🔄 Convert PDF to TXT (for better processing)", use_container_width=True):
            extracted_text = extract_text_from_file(uploaded_file)
            
            # Check if text contains many CID codes
            import re
            cid_count = len(re.findall(r'\(cid:\d+\)', extracted_text))
            
            if cid_count > 10:
                st.error("⚠️ This PDF contains unrecognizable character encoding. Suggestions:")
                st.write("1. 📋 **Manual Copy-Paste**: Open PDF in Adobe Reader and copy text content")
                st.write("2. 🔄 **Conversion Tools**: Use Adobe Acrobat or online conversion tools")
                st.write("3. 📝 **OCR Recognition**: If it's a scanned document, text recognition is needed")
                st.write("4. 💡 **Direct Input**: Paste text content directly in the text box below")
            else:
                # Create a downloadable TXT file
                st.download_button(
                    label="⬇️ Download as TXT file",
                    data=extracted_text,
                    file_name=f"{uploaded_file.name.replace('.pdf', '')}.txt",
                    mime="text/plain"
                )
    
    if uploaded_file:
        st.session_state.protocol_text = extract_text_from_file(uploaded_file)

    st.session_state.protocol_text = st.text_area(
        "Protocol Text",
        st.session_state.protocol_text,
        height=400,
        placeholder="Paste your protocol text here..."
    )
    
    # Add text processing buttons
    text_issues = []
    if st.session_state.protocol_text:
        if "(cid:" in st.session_state.protocol_text:
            text_issues.append("CID codes")
        # Check for common reversed words
        reversed_words = ['tuohsaW', 'doireP', 'skeew', 'gnineercS', 'tneitap', 'enirU', 'ecnO']
        if any(word in st.session_state.protocol_text for word in reversed_words):
            text_issues.append("reversed text")
        # Check for PPD artifacts
        if st.session_state.protocol_text.count('PPD') > 3:
            text_issues.append("PDF artifacts")
    
    if text_issues:
        issue_text = " + ".join(text_issues)
        if st.button(f"🔧 Fix Text Issues ({issue_text})", use_container_width=True):
            # First decode CID codes
            processed_text = decode_cid_codes(st.session_state.protocol_text)
            # Then fix reversed text
            processed_text = fix_reversed_text(processed_text)
            # Finally clean artifacts
            processed_text = clean_pdf_artifacts(processed_text)
            st.session_state.protocol_text = processed_text
            st.success(f"✅ Fixed: {issue_text}")
            st.rerun()

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