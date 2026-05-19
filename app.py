import re
import html
from datetime import datetime
import streamlit as st
from groq import Groq

st.set_page_config(page_title="Advice Reply Coach", page_icon="✉️", layout="centered")

HELP_OPTIONS = {
    "content": [
        {"value": "address_problem", "label": "🎯 Did I address the reader's problem?"},
        {"value": "two_advice", "label": "💡 Did I give at least 2 pieces of advice?"},
        {"value": "explain_advice", "label": "🔍 Did I explain how each advice can help?"},
        {"value": "caring_tone", "label": "❤️ Did I use a caring and encouraging tone?"},
    ],
    "language": [
        {"value": "modal_verbs", "label": "💪 Did I use modal verbs (e.g. should, could, might)?"},
        {"value": "conditional_sentences", "label": "🔄 Did I use conditional sentences (e.g. If you..., you could...)?"},
        {"value": "empathy_phrases", "label": "🤗 Did I use phrases to show empathy?"},
        {"value": "linking_words", "label": "🔗 Did I use appropriate linking words?"},
        {"value": "spelling_punctuation", "label": "🔤 Are my spelling and punctuation correct?"},
    ],
    "organisation": [
        {"value": "greeting_signoff", "label": "👋 Did I include a proper greeting and sign-off?"},
        {"value": "acknowledge_problem", "label": "📨 Did I acknowledge the reader's problem in the opening?"},
        {"value": "separate_paragraphs", "label": "📄 Did I organise my advice in separate paragraphs?"},
        {"value": "encouraging_closing", "label": "🌟 Did I end with an encouraging closing?"},
    ],
}

MODE_DESCRIPTIONS = {
    "content": "💡 Help me with what I wrote about — feedback on problem response, advice, explanations, and tone.",
    "language": "🔤 Help me with my words and sentences — feedback on modal verbs, conditionals, empathy phrases, linking words, spelling, and punctuation.",
    "organisation": "📄 Help me with how I organised my email — feedback on greeting, sign-off, paragraph structure, and closing.",
}

HELP_DESC_MAP = {
    "address_problem": "whether the student clearly addressed and responded to the reader's problem or concern in their advice reply email",
    "two_advice": "whether the student gave at least 2 separate, distinct pieces of advice to help the reader with their problem",
    "explain_advice": "whether the student explained HOW each piece of advice can help the reader, not just stating the advice but showing why it would work",
    "caring_tone": "whether the student used a caring, warm, and encouraging tone throughout the email, making the reader feel supported",
    "modal_verbs": "whether the student used modal verbs appropriately (e.g. should, could, might, would) to give advice in a polite, helpful way",
    "conditional_sentences": "whether the student used conditional sentences to give advice (e.g. If you try..., you could..., If you feel..., you might...)",
    "empathy_phrases": "whether the student used phrases to show empathy and understanding (e.g. I understand how you feel, It must be hard, I know this is difficult)",
    "linking_words": "whether the student used appropriate linking words to connect ideas (e.g. firstly, moreover, in addition, furthermore, also, besides)",
    "spelling_punctuation": "whether spelling and punctuation are correct throughout the advice reply email",
    "greeting_signoff": "whether the student included a proper email greeting (e.g. Dear..., Hi...) and sign-off (e.g. Your friend, Best wishes, Take care)",
    "acknowledge_problem": "whether the student acknowledged and showed understanding of the reader's problem in the opening of the email before giving advice",
    "separate_paragraphs": "whether the student organised each piece of advice in its own separate paragraph for clarity and readability",
    "encouraging_closing": "whether the student ended the email with an encouraging closing that makes the reader feel hopeful and supported",
}

MODE_DESC_MAP = {
    "content": "CONTENT (what the student wrote about)",
    "language": "LANGUAGE (words, grammar, and sentences)",
    "organisation": "ORGANISATION (how the email is structured and organised)",
}

WRITE_FOR_ME_PATTERNS = [
    r"finish\s+(the\s+)?(writing|essay|email|reply|composition|work)\s*(for\s+me)?",
    r"write\s+(the\s+)?(rest|remaining|more|ending|body|essay|email|reply|composition)\s*(for\s+me)?",
    r"complete\s+(the\s+)?(writing|essay|email|reply|composition|work)\s*(for\s+me)?",
    r"do\s+(the\s+)?(writing|essay|email|reply|composition|work)\s*(for\s+me)?",
    r"help\s+me\s+(finish|complete|write)\s+(it|the\s+(rest|writing|essay|email|reply))",
    r"can\s+you\s+(write|finish|complete)\s+(it|the|my|this)",
    r"rewrite\s+(it|the|my|this)\s*(whole|entire|full)?",
    r"give\s+me\s+(a\s+)?(full|complete|whole|entire)\s+(writing|essay|email|reply|composition)",
    r"write\s+(it|this|everything)\s+for\s+me",
    r"just\s+(write|do|finish)\s+(it|this)\s*(for\s+me)?",
    r"write\s+for\s+me",
    r"do\s+(it|this)\s+for\s+me",
    r"make\s+(it|the\s+writing|my\s+writing|the\s+email|my\s+email)\s+(better|good|perfect)\s+for\s+me",
    r"generate\s+(a\s+)?(writing|essay|email|reply|composition)",
    r"create\s+(a\s+)?(writing|essay|email|reply|composition)\s*(for\s+me)?",
]


def init_state():
    defaults = {
        "interaction_history": [],
        "interaction_count": 0,
        "pending_more_help": False,
        "pending_fresh_start": False,
        "feedback_text": "",
        "api_ready": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def detect_write_for_me(text: str) -> bool:
    if not text:
        return False
    lower = text.lower().strip()
    return any(re.search(p, lower, re.I) for p in WRITE_FOR_ME_PATTERNS)


def word_count(text: str) -> int:
    text = (text or "").strip()
    return len([w for w in re.split(r"\s+", text) if w]) if text else 0


def build_prompt(writing, student_name, mode, help_value, custom_q):
    category_name = MODE_DESC_MAP[mode]
    help_desc = HELP_DESC_MAP.get(help_value, "") if help_value else ""
    prompt = f"You are a friendly Advice Reply Coach (age 10-11) specialising in EMAIL ADVICE REPLY writing. Student: {student_name}. Category: {category_name}.\n"
    prompt += "The student has written an advice reply email — a friendly email responding to someone who asked for help or advice about a problem.\n"
    prompt += "RULES: ONLY give feedback on " + category_name + ". NEVER write, rewrite, finish, or complete the student's email for them — not even a single paragraph. If the student asks you to write, finish, or complete their work, politely say NO in 2-3 short sentences using simple words: explain that writing it for them would not help them learn, encourage them to try on their own, and remind them you are here to give tips not to do the work. Use very simple English for weak learners. Be concise (max 150 words). More tips than praise. End with 1 encouraging sentence.\n"
    prompt += "Tips to Improve must be short, clear, and actionable — give only 1-2 simple tips using easy words. Avoid long explanations.\n"
    prompt += 'IMPORTANT: After the table, write a section called "✏️ Try This!" that gives ONE concrete before-and-after example from the student\'s own email. Pick a specific weak sentence and show how to improve it. Format: "Your sentence: [quote their sentence]. You could try: [improved version]." Keep the improved version close to their original so it feels achievable. This example MUST relate to the checklist goal.\n'
    prompt += 'Reply as a markdown table: | Checklist Goal | Did Well | Tips to Improve |\n'
    if help_value:
        prompt += f"Focus: {help_desc}.\n"
    if custom_q:
        prompt += f'Student\'s question: "{custom_q}"\n'
    prompt += f"\nAdvice Reply Email:\n---\n{writing}\n---"
    return prompt


def refusal_text():
    return (
        "I can't write or finish your email for you.\n\n"
        "Writing is your skill to grow, so you need to try first. "
        "Your ideas matter, and I can still help by giving feedback, tips, and simple improvements to your own work."
    )


def get_groq_client():
    api_key = st.secrets.get("GROQ_API_KEY", "")
    if not api_key:
        raise ValueError("Missing GROQ_API_KEY in Streamlit secrets.")
    return Groq(api_key=api_key)


def get_ai_feedback(prompt: str) -> str:
    client = get_groq_client()
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        temperature=0.3,
        messages=[
            {"role": "system", "content": "You are a helpful writing coach for primary students. Follow the user's prompt exactly and return concise markdown."},
            {"role": "user", "content": prompt},
        ],
    )
    return completion.choices[0].message.content.strip()


def escape_html(s: str) -> str:
    return html.escape(s or "")


def download_log_html():
    history = st.session_state.interaction_history
    name = st.session_state.get("student_name", "").strip() or "Student"
    cls = st.session_state.get("student_class", "").strip()
    num = st.session_state.get("student_number", "").strip()
    rows = []
    rows.append("<!DOCTYPE html><html lang='en'><head><meta charset='UTF-8'><meta name='viewport' content='width=device-width, initial-scale=1.0'>")
    rows.append(f"<title>Learning Log - {escape_html(name)}</title>")
    rows.append("""
    <style>
    body{font-family:Arial,sans-serif;max-width:900px;margin:0 auto;padding:24px;color:#0c1929;background:#f0f9ff;line-height:1.65}
    h1{text-align:center;color:#0369a1;margin-bottom:4px}
    .subtitle{text-align:center;color:#b45309;font-style:italic;font-weight:700;margin-bottom:24px}
    .info,.session{background:#fff;border:1px solid #bae6fd;border-radius:14px;padding:18px;margin-bottom:18px}
    .tag{display:inline-block;background:#e0f2fe;border-radius:999px;padding:4px 10px;margin:2px 6px 2px 0;font-size:12px}
    .sample{background:#f8fbff;border-left:4px solid #38bdf8;padding:12px 14px;border-radius:8px;white-space:pre-wrap}
    table{width:100%;border-collapse:collapse;margin:12px 0;font-size:14px}
    th{background:#0ea5e9;color:#fff;padding:10px;text-align:left}
    td{padding:10px;border-bottom:1px solid #dbeafe;vertical-align:top}
    tr:nth-child(even) td{background:#f8fbff}
    </style></head><body>
    """)
    rows.append("<h1>✉️ Advice Reply Coach</h1><div class='subtitle'>Learning Log</div>")
    rows.append("<div class='info'>")
    rows.append(f"<p><strong>Student:</strong> {escape_html(name)}</p>")
    if cls:
        rows.append(f"<p><strong>Class:</strong> {escape_html(cls)}</p>")
    if num:
        rows.append(f"<p><strong>Number:</strong> {escape_html(num)}</p>")
    rows.append(f"<p><strong>Total Feedback Sessions:</strong> {len(history)}</p></div>")
    for i, entry in enumerate(history, 1):
        rows.append("<div class='session'>")
        rows.append(f"<h3>Session {i}</h3>")
        rows.append(f"<div class='tag'>{escape_html(entry['timestamp'])}</div><div class='tag'>{escape_html(entry['mode_label'])}</div>")
        if entry.get('help_goal'):
            rows.append(f"<p><strong>Checklist Goal:</strong> {escape_html(entry['help_goal'])}</p>")
        if entry.get('custom_question'):
            rows.append(f"<p><strong>Custom Question:</strong> {escape_html(entry['custom_question'])}</p>")
        rows.append("<p><strong>My Email:</strong></p>")
        rows.append(f"<div class='sample'>{escape_html(entry['writing'])}</div>")
        rows.append("<p><strong>AI Feedback:</strong></p>")
        rows.append(f"<div>{entry['response_html']}</div>")
        rows.append("</div>")
    rows.append("</body></html>")
    return ''.join(rows).encode('utf-8')


def reset_more_help():
    st.session_state.selected_mode = ""
    st.session_state.help_value = ""
    st.session_state.custom_question = ""
    st.session_state.feedback_text = ""
    st.session_state.pending_more_help = False


def reset_fresh_start():
    st.session_state.writing_input = ""
    st.session_state.selected_mode = ""
    st.session_state.help_value = ""
    st.session_state.custom_question = ""
    st.session_state.feedback_text = ""
    st.session_state.pending_fresh_start = False


init_state()

st.markdown("""
<style>
:root {
    --primary: #0ea5e9;
    --primary-dark: #0369a1;
    --accent: #f59e0b;
    --accent2: #10b981;
    --bg-soft: #f0f9ff;
    --card: rgba(255,255,255,0.86);
    --border: #bae6fd;
    --text-soft: #475569;
}
.stApp {
    background:
        radial-gradient(circle at 15% 15%, rgba(14,165,233,0.10), transparent 28%),
        radial-gradient(circle at 85% 20%, rgba(245,158,11,0.10), transparent 24%),
        radial-gradient(circle at 50% 85%, rgba(16,185,129,0.08), transparent 28%),
        linear-gradient(180deg, #f0f9ff 0%, #f8fafc 100%);
}
.block-container {max-width: 760px; padding-top: 2rem; padding-bottom: 4rem;}
.hero, .panel {
    background: var(--card);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(186,230,253,0.9);
    border-radius: 22px;
    box-shadow: 0 12px 40px rgba(14,165,233,0.10);
}
.hero {padding: 1.8rem 1.5rem; margin-bottom: 1rem; text-align: center;}
.panel {padding: 1.2rem 1.2rem; margin-bottom: 1rem;}
.badge {
    display:inline-block; padding:0.35rem 0.8rem; border-radius:999px; font-size:0.82rem; font-weight:700;
    background: linear-gradient(135deg, rgba(14,165,233,0.13), rgba(245,158,11,0.13)); color: var(--primary-dark);
    border:1px solid rgba(14,165,233,0.18); margin-bottom:0.75rem;
}
.help-chip {
    display:inline-block; padding:0.28rem 0.65rem; border-radius:999px; font-size:0.78rem; font-weight:700;
    background:#ecfeff; color:#0f766e; border:1px solid #99f6e4;
}
.small-note {color: var(--text-soft); font-size: 0.92rem;}
.feedback-box {
    padding: 1rem 1rem; border-radius: 16px; background: rgba(255,255,255,0.72); border:1px solid #dbeafe;
}
div[data-testid='stDownloadButton'] button,
button[kind='primary'] {
    border-radius: 14px !important;
    font-weight: 800 !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class='hero'>
  <div class='badge'>✉️ Advice Reply Coach</div>
  <h1 style='margin:0 0 0.35rem 0;'>Your Smart Helper for Writing a Convincing Reply!</h1>
  <p class='small-note' style='margin:0;'>把原本 POE 的分步 bot 介面改成 Streamlit 版本，保留學生資料、逐步填寫、回饋紀錄與學習日誌下載。</p>
</div>
""", unsafe_allow_html=True)

with st.container():
    st.markdown("<div class='panel'>", unsafe_allow_html=True)
    st.subheader("👋 About You")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.text_input("First Name", key="student_name", placeholder="e.g. Sarah")
    with c2:
        st.text_input("Class", key="student_class", placeholder="e.g. 1A")
    with c3:
        st.text_input("Class Number", key="student_number", placeholder="e.g. 12")
    st.markdown("</div>", unsafe_allow_html=True)

step1_ok = all([
    st.session_state.get("student_name", "").strip(),
    st.session_state.get("student_class", "").strip(),
    st.session_state.get("student_number", "").strip(),
])

st.markdown("<div class='panel'>", unsafe_allow_html=True)
st.subheader("✍️ Your Advice Reply Email")
if not step1_ok:
    st.info("請先填好姓名、班別和學號。")

st.text_area(
    "Paste or type your advice reply email below",
    key="writing_input",
    placeholder="Paste your whole advice reply email here, or just the part you want feedback on...",
    height=220,
    disabled=not step1_ok,
)
wc = word_count(st.session_state.get("writing_input", ""))
st.caption(f"{wc} word{'s' if wc != 1 else ''}")
st.markdown("</div>", unsafe_allow_html=True)

step2_ok = len(st.session_state.get("writing_input", "").strip()) > 10

st.markdown("<div class='panel'>", unsafe_allow_html=True)
st.subheader("🎯 What Would You Like Help With?")
if not step2_ok:
    st.info("請先貼上你的 advice reply email。")

mode_options = {"content": "Content", "language": "Language", "organisation": "Organisation"}
mode = st.radio(
    "Choose a help category",
    options=list(mode_options.keys()),
    format_func=lambda x: mode_options[x],
    key="selected_mode",
    horizontal=True,
    disabled=not step2_ok,
)
if step2_ok and mode:
    st.markdown(f"<p class='small-note'>{MODE_DESCRIPTIONS[mode]}</p>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

step3_ok = step2_ok and bool(mode)
options_map = {"": "-- Pick a goal --"}
if step3_ok:
    for item in HELP_OPTIONS[mode]:
        options_map[item["value"]] = item["label"]

st.markdown("<div class='panel'>", unsafe_allow_html=True)
st.subheader("📋 Choose a Checklist Goal")
if not step3_ok:
    st.info("請先選擇一個 help category。")
help_value = st.selectbox(
    "What would you like feedback on?",
    options=list(options_map.keys()),
    format_func=lambda x: options_map[x],
    key="help_value",
    disabled=not step3_ok,
)
st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div class='panel'>", unsafe_allow_html=True)
st.subheader("💬 Ask Your Own Question")
st.text_area(
    "Got a specific question about your email?",
    key="custom_question",
    placeholder="e.g. Does my advice sound helpful? Did I show enough empathy?",
    height=90,
    disabled=not step3_ok,
)
st.markdown("</div>", unsafe_allow_html=True)

col_a, col_b = st.columns([2,1])
with col_a:
    submit = st.button("📨 Get Feedback", type="primary", use_container_width=True, disabled=not step3_ok)
with col_b:
    clear_feedback = st.button("🧹 Clear", use_container_width=True)

if clear_feedback:
    st.session_state.feedback_text = ""

if submit:
    writing = st.session_state.get("writing_input", "").strip()
    custom_q = st.session_state.get("custom_question", "").strip()
    help_value = st.session_state.get("help_value", "")
    mode = st.session_state.get("selected_mode", "")
    name = st.session_state.get("student_name", "").strip()

    if not writing or len(writing) < 10:
        st.error("Please type or paste your advice reply email first.")
    elif not mode:
        st.error("Please choose a help category.")
    elif not help_value and not custom_q:
        st.error("Please pick a checklist goal or type your own question.")
    elif detect_write_for_me(custom_q):
        st.warning(refusal_text())
        st.session_state.feedback_text = refusal_text()
    else:
        prompt = build_prompt(writing, name, mode, help_value, custom_q)
        help_label = options_map.get(help_value, "") if help_value else ""
        try:
            with st.spinner("Groq is reviewing the email..."):
                feedback = get_ai_feedback(prompt)
            st.session_state.feedback_text = feedback
            st.session_state.api_ready = True
            st.session_state.interaction_count += 1
            st.session_state.interaction_history.append({
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "mode": mode,
                "mode_label": MODE_DESC_MAP[mode],
                "help_goal": help_label,
                "custom_question": custom_q,
                "writing": writing,
                "response": feedback,
                "response_html": feedback,
            })
        except Exception as e:
            st.session_state.feedback_text = ""
            st.error(f"Groq API error: {e}")

if st.session_state.feedback_text:
    st.markdown("<div class='panel'>", unsafe_allow_html=True)
    st.subheader("✨ Your Feedback")
    st.markdown(f"<span class='help-chip'>💬 {st.session_state.interaction_count} interaction(s)</span>", unsafe_allow_html=True)
    st.markdown("<div class='feedback-box'>", unsafe_allow_html=True)
    st.markdown(st.session_state.feedback_text)
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

if st.session_state.interaction_history:
    st.markdown("<div class='panel'>", unsafe_allow_html=True)
    st.subheader("🚀 What's Next?")
    nx1, nx2 = st.columns(2)
    with nx1:
        if st.button("🎯 Try Another Checklist Goal", use_container_width=True):
            reset_more_help()
            st.rerun()
    with nx2:
        if st.button("✏️ Review a New Part of My Email", use_container_width=True):
            reset_fresh_start()
            st.rerun()

    st.download_button(
        "💾 Save Learning Log",
        data=download_log_html(),
        file_name=f"Learning_Log_{(st.session_state.get('student_name','Student') or 'Student').replace(' ', '_')}.html",
        mime="text/html",
        use_container_width=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

with st.expander("🧾 Session History"):
    if not st.session_state.interaction_history:
        st.write("No feedback sessions yet.")
    else:
        for i, item in enumerate(reversed(st.session_state.interaction_history), 1):
            st.markdown("<div class='history-card'>", unsafe_allow_html=True)
            st.markdown(f"**Session {len(st.session_state.interaction_history)-i+1}**")
            st.markdown(f"<span class='history-meta'>🕒 {item['timestamp']}</span><span class='history-meta'>🎯 {item['mode_label']}</span>", unsafe_allow_html=True)
            if item.get('help_goal'):
                st.markdown(f"<span class='history-meta'>📋 {item['help_goal']}</span>", unsafe_allow_html=True)
            if item.get('custom_question'):
                st.markdown(f"**Custom Question:** {item['custom_question']}")
            st.markdown("**Writing sample**")
            st.code(item['writing'], language=None)
            st.markdown("**Feedback**")
            st.markdown(item['response'])
            st.markdown("</div>", unsafe_allow_html=True)

st.caption("Created from your original POE bot structure, now adapted for Streamlit deployment.")
