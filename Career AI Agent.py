import os
import requests
import gradio as gr
import pdfplumber
from difflib import get_close_matches
import tempfile
from gtts import gTTS
import uuid

# Load Hugging Face Token
API_TOKEN = os.environ.get("HF_TOKEN")
if not API_TOKEN:
    raise ValueError("Hugging Face API token not found.")
print("Token loaded.")

# Model Info
MODEL_NAME = "mistralai/Mistral-7B-Instruct-v0.1"
API_URL = f"https://api-inference.huggingface.co/models/{MODEL_NAME}"
headers = {"Authorization": f"Bearer {API_TOKEN}"}

# Links
TEMPLATE_LINK = "https://huggingface.co/spaces/dhru1218/AI_Assistant/blob/main/Resume.docx"
COURSE_PDF_LINK = "https://huggingface.co/spaces/dhru1218/AI_Assistant/blob/main/Machine%20Learning%20and%20Artificial%20Intelligence.pdf"
LINKEDIN_PDF_LINK = "https://huggingface.co/spaces/dhru1218/AI_Assistant/resolve/main/Optimise%20your%20LinkedIn%20Checklist%20_%20Template.pdf"
COMPANY_PDF_LINK = "https://huggingface.co/spaces/dhru1218/AI_Assistant/blob/main/MNC%20Com.Questions.zip"

# Correction logic
COMMON_WORDS = ["thank", "resume", "template", "course", "linkedin", "interview", "profile"]
def correct_spelling(text):
    words = text.lower().split()
    corrected = []
    for word in words:
        match = get_close_matches(word, COMMON_WORDS, n=1, cutoff=0.8)
        corrected.append(match[0] if match else word)
    return " ".join(corrected)

# Model call
def query_model(payload):
    response = requests.post(API_URL, headers=headers, json=payload)
    if response.status_code == 200:
        result = response.json()
        if isinstance(result, list) and 'generated_text' in result[0]:
            return result[0]['generated_text']
    return "Model failed to respond properly."

# Resume analysis
def analyze_resume(pdf_path):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        if not text.strip():
            return [{"role": "assistant", "content": "Couldn't extract text."}]
        prompt = f"<s>[INST] Analyze this resume and give improvement suggestions:\n{text[:3000]} [/INST]"
        response = query_model({"inputs": prompt})
        cleaned = response.split("[/INST]")[-1].strip() if "[/INST]" in response else response.strip()
        return [{"role": "assistant", "content": cleaned}]
    except Exception as e:
        return [{"role": "assistant", "content": f"Error analyzing resume: {e}"}]

# Job fetch mock
def fetch_jobs_from_jsearch(query):
    url = "https://jsearch.p.rapidapi.com/search"
    headers = {
        "X-RapidAPI-Key": os.environ.get("JSEARCH_API_KEY", "").strip(),
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
    }
    params = {"query": query, "page": "1", "num_pages": "1"}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        jobs = response.json().get("data", [])
        results = []
        for job in jobs[:3]:
            title = job.get("job_title")
            company = job.get("employer_name")
            link = job.get("job_apply_link")
            if title and company and link:
                results.append(f"[{title} at {company}]({link})")
        return results
    return []

def handle_job_query(message):
    if any(kw in message.lower() for kw in ["job", "internship"]):
        jobs = fetch_jobs_from_jsearch(message)
        if jobs:
            formatted = "\n".join(f"{i+1}. {job}" for i, job in enumerate(jobs))
            return "Here are some opportunities:", formatted
        return "No jobs found.", "Try changing your query."
    return None

def speak_response(text, speed=1.0):
    tts = gTTS(text, lang='en', slow=False)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        tts.save(tmp.name)
        return tmp.name

# Chat logic
def generate_response(message, history, tts_enabled, tts_speed):
    message = correct_spelling(message)

    if any(greet in message.lower() for greet in ["hello", "hi", "hey"]):
        response_text = "Hello! 👋 How can I assist you today with your career, learning, or any topic?"
    elif "thank" in message.lower():
        response_text = "You're welcome! 😊 I'm here to help with anything you need."
    elif (job_result := handle_job_query(message)):
        response_text = job_result[0] + "\n\n" + job_result[1]
    elif "template" in message:
        response_text = f"Download the resume template here: [Resume Template]({TEMPLATE_LINK})"
    elif "free course" in message:
        response_text = f"Here's your course: [Download PDF]({COURSE_PDF_LINK})"
    elif "linkedin" in message and "checklist" in message:
        response_text = f"LinkedIn Optimization Guide: [Download PDF]({LINKEDIN_PDF_LINK})"
    elif "infosys" in message and "pdf" in message:
        response_text = f"Company prep questions: [Download ZIP]({COMPANY_PDF_LINK})"
    else:
        prompt = f"<s>[INST] {message} [/INST]"
        response = query_model({"inputs": prompt})
        response_text = response.split("[/INST]")[-1].strip() if "[/INST]" in response else response.strip()

    audio_path = speak_response(response_text, speed=tts_speed) if tts_enabled else None

    return history + [{"role": "user", "content": message}, {"role": "assistant", "content": response_text}], audio_path


# UI CSS for modern style
# Responsive custom CSS
custom_css = """
.gradio-container {
    font-family: 'Segoe UI', sans-serif;
    background: #f9fbfd;
    padding: 10px;
}
.card-style {
    background: #e0f0ff;
    border-radius: 20px;
    padding: 16px;
    box-shadow: 0 6px 16px rgba(0,0,0,0.08);
    margin-bottom: 20px;
}
.small-btn {
    padding: 10px 18px !important;
    font-size: 15px !important;
}
@media only screen and (max-width: 768px) {
    .gradio-container {
        padding: 8px;
    }
    .small-btn {
        width: 100%;
    }
    .gr-row > * {
        width: 100% !important;
    }
    .gradio-chatbot {
        height: 400px !important;
    }
    .gr-textbox {
        width: 100% !important;
    }
}
"""

# Gradio UI
with gr.Blocks(css=custom_css) as demo:
    gr.Markdown("## <center>💼 Career AI Agent</center>")
    gr.Markdown("<center>Your personal assistant for jobs, resumes, and career success.</center>")

    chatbot = gr.Chatbot(label="Career Assistant", height=450, type="messages")
    state = gr.State([])

    with gr.Column(elem_classes="card-style"):
        with gr.Row():
            txt = gr.Textbox(placeholder="Ask your career question...", label="Your Message", scale=4)
            send_btn = gr.Button("Send", variant="primary", elem_classes="small-btn", scale=1)

        tts_toggle = gr.Checkbox(label="🔊 Enable Voice", value=True)
        tts_speed_slider = gr.Slider(minimum=0.5, maximum=2.0, value=1.0, step=0.1, label="Voice Speed (x)")

        audio_output = gr.Audio(label="Assistant Voice", autoplay=True, visible=True)

    with gr.Column(elem_classes="card-style"):
        resume_upload = gr.File(label="📤 Upload Resume (PDF)", file_types=[".pdf"], type="filepath")
        analyze_btn = gr.Button("Analyze Resume", elem_classes="small-btn")

    # Hook interactions
    txt.submit(generate_response, [txt, state, tts_toggle, tts_speed_slider], [chatbot, audio_output])
    send_btn.click(generate_response, [txt, state, tts_toggle, tts_speed_slider], [chatbot, audio_output])
    analyze_btn.click(analyze_resume, inputs=resume_upload, outputs=chatbot)

print("Launching app...")
demo.launch()
