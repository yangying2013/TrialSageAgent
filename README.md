# TrialSage Protocol Summarizer

A Streamlit-based AI agent for summarizing clinical trial protocols using Google Gemini.

## Features

- **Protocol Analysis**: Extract key information from clinical trial protocols
- **Structured Output**: Get organized summaries with study objectives, inclusion/exclusion criteria, and endpoints
- **File Support**: Upload PDF, TXT, or MD files containing protocol text
- **AI-Powered**: Uses Google Gemini 1.5 Flash

## Installation

1. Clone this repository:
```bash
git clone <your-repo-url>
cd trialsage
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
   - Create a `.env` file in the project root
   - Add your Google Gemini API key:
   ```
   API_KEY=your_gemini_api_key_here
   ```

## Usage

1. Run the Streamlit app:
```bash
streamlit run trialsage_agent.py
```

2. Open your browser and navigate to the provided URL (usually `http://localhost:8501`)

3. Either:
   - Upload a protocol file (PDF, TXT, or MD)
   - Paste protocol text directly into the text area

4. Click "Generate Summary" to analyze the protocol

## Output Format

The application extracts and displays:
- **Official Title**: The study's official title
- **Phase**: Trial phase (Phase 1, Phase 2, etc.)
- **Sponsor**: Primary sponsor information
- **Objective**: Study goals and purpose
- **Eligibility**: Inclusion and exclusion criteria
- **Endpoints**: Primary and secondary outcomes

## Requirements

- Python 3.7+
- Google Gemini API key
- See `requirements.txt` for Python dependencies
