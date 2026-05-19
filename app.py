import re
import html
from datetime import datetime
import streamlit as st
from groq import Groq

st.set_page_config(page_title="Advice Reply Coach", page_icon="✉️", layout="centered")

# ── Data ──────────────────────────────────────────────────────────────────────

HELP_OPTIONS = {
    "content": [
        {"value": "address_problem",  "label": "🎯 Did I address the reader's problem?"},
        {"value": "two_advice",        "label": "💡 Did I give at least 2 pieces of advice?"},
        {"value": "explain_advice",    "label": "🔍 Did I explain how each piece of advice can help?"},
        {"value": "caring_tone",       "label": "❤️ Did I use a caring and encouraging tone?"},
    ],
    "language": [
        {"value": "modal_verbs",           "label": "💪 Did I use modal verbs (e.g. should, could, might)?"},
        {"value": "conditional_sentences", "label": "🔄 Did I use conditional sentences (e.g. If you..., you could...)?"},
        {"value": "empathy_phrases",       "label": "🤗 Did I use phrases to show empathy?"},
        {"value": "linking_words",         "label": "🔗 Did I use appropriate linking words?"},
        {"value": "spelling_punctuation",  "label": "🔤 Are my spelling and punctuation correct?"},
    ],
    "organisation": [
        {"value": "greeting_signoff",    "label": "👋 Did I include a proper greeting and sign-off?"},
        {"value": "acknowledge_problem", "label": "📨 Did I acknowledge the reader's problem in the opening?"},
        {"value": "separate_paragraphs", "label": "📄 Did I organise my advice in separate paragraphs?"},
        {"value": "encouraging_closing", "label": "🌟 Did I end with an encouraging closing?"},
    ],
}

MODE_DESCRIPTIONS = {
    "content":      "💡 Help me with what I wrote about — feedback on problem response, advice, explanations, and tone.",
    "language":     "🔤 Help me with my words and sentences — feedback on modal verbs, conditionals, empathy phrases, linking words, spelling, and punctuation.",
    "organisation": "📄 Help me with how I organised my email — feedback on greeting, sign-off, paragraph structure, and closing.",
}

HELP_DESC_MAP = {
    "address_problem":      "whether the student clearly addressed and responded to the reader's problem or concern",
    "two_advice":           "whether the student gave at least 2 separate, distinct pieces of advice",
    "explain_advice":       "whether the student explained HOW each piece of advice can help the reader",
    "caring_tone":          "whether the student used a caring, warm, and encouraging tone throughout",
    "modal_verbs":          "whether the student used modal verbs appropriately (e.g. should, could, might, would)",
    "conditional_sentences":"whether the student used conditional sentences (e.g. If you try..., you could...)",
    "empathy_phrases":      "whether the student used phrases to show empathy (e.g. I understand how you feel)",
    "linking_words":        "whether the student used appropriate linking words (e.g. firstly, moreover, in addition)",
    "spelling_punctuation": "whether spelling and punctuation are correct throughout",
    "greeting_signoff":     "whether the student included a proper greeting and sign-off",
    "acknowledge_problem":  "whether the student acknowledged the reader's problem in the opening",
    "separate_paragraphs":  "whether each piece of advice is in its own paragraph",
    "encouraging_closing":  "whether the student ended with an encouraging closing",
}

MODE_DESC_MAP = {
    "content":      "CONTENT (what the student wrote about)",
    "language":     "LANGUAGE (words, grammar, and sentences)",
    "organisation": "ORGANISATION (how the email is structured)",
}

WRITE_FOR_ME_PATTERNS = [
    r"finish\s+(the\s+)?(writing|essay|email|reply|composition|work)\s*(for\s+me)?",
    r"write\s+(the\s+)?(rest|remaining|more|ending|body|essay|email|reply|composition)\s*(for\s+me)?",
    r"complete\s+(the\s+)?(writing|essay|email|reply|composition|work)\s*(for\s+me)?",
    r"do\s+(the\s+)?(writing|essay|email|reply|composition|work)\s*(for\s+me)?",
    r"help\s+me\s+(finish|complete|write)\s+(it|the\s+(rest|writing|essay|email|reply))",
    r"can\s+you\s+(write|finish|complete)\s+(it|the|my|this)",
    r"rewrite\s+(it|the|my|this)\s*(whole|entire|full)?",
    r"write\s+(it|this|everything)\s+for\s+me",
    r"just\s+(write|do|finish)\s+(it|this)\s*(for\s+me)?",
    r"write\s+for\s+me",
    r"do\s+(it|this)\s+for\s+me",
    r"generate\s+(a\s+)?(writing|essay|email|reply|composition)",
    r"create\s+(a\s+)?(writing|essay|email|reply|composition)\s*(for\s+me)?",
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def init_state():
    defaults = {
        "student_name": "",
        "student_class": "",
        "student_number": "",
        "writing_input": "",
        "selected_mode": "content",
        "help_value": "",
        "custom_question": "",
        "feedback_text": "",
        "interaction_history": [],
        "interaction_count": 0,
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
    prompt = (
        f"You are a friendly Advice Reply Coach for students aged 10–11, "
        f"specialising in EMAIL ADVICE REPLY writing. Student: {student_name}. "
        f"Category: {category_name}.\n"
        "The student has written an advice reply email — a friendly email responding "
        "to someone who asked for help or advice about a problem.\n"
        "RULES: ONLY give feedback on " + category_name + ". "
        "NEVER write, rewrite, finish, or complete the student's email — not even a "
        "single sentence. Use very simple English. Be concise (max 150 words). "
        "More tips than praise. End with 1 short encouraging sentence.\n"
        "Tips to Improve: short, clear, actionable — 1–2 simple tips only.\n"
        "IMPORTANT: After the table, write a section called \"✏️ Try This!\" with ONE "
        "concrete before-and-after example from the student's own writing. "
        "Format: \"Your sentence: [quote]. You could try: [improved version].\"\n"
        "Reply as a markdown table: | Checklist Goal | Did Well | Tips to Improve |\n"
    )
    if help_value:
        prompt += f"Focus: {help_desc}.\n"
    if custom_q:
        prompt += f'Student's question: "{custom_q}"\n'
    prompt += f"\nAdvice Reply Email:\n---\n{writing}\n---"
    return prompt


def get_ai_feedback(prompt: str) -> str:
    api_key = st.secrets.get("GROQ_API_KEY", "")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set in Streamlit secrets.")
    client = Groq(api_key=api_key)
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        temperature=0.3,
        messages=[
            {"role": "system", "content": (
                "You are a helpful, encouraging writing coach for primary school students. "
                "Follow the user prompt exactly and return concise markdown."
            )},
            {"role": "user", "content": prompt},
        ],
    )
    return completion.choices[0].message.content.strip()


def escape_html(s: str) -> str:
    return html.escape(s or "")


def download_log_html() -> bytes:
    history = st.session_state.interaction_history
    name = st.session_state.get("student_name", "").strip() or "Student"
    cls  = st.session_state.get("student_class", "").strip()
    num  = st.session_state.get("student_number", "").strip()
    rows = [
        "<!DOCTYPE html><html lang='en'><head><meta charset='UTF-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>",
        f"<title>Learning Log — {escape_html(name)}</title>",
        """<style>
body{font-family:Arial,sans-serif;max-width:900px;margin:0 auto;padding:24px;
     color:#0c1929;background:#f0f9ff;line-height:1.65}
h1{text-align:center;color:#0369a1;margin-bottom:4px}
.subtitle{text-align:center;color:#b45309;font-style:italic;font-weight:700;margin-bottom:24px}
.info,.session{background:#fff;border:1px solid #bae6fd;border-radius:14px;
               padding:18px;margin-bottom:18px}
.tag{display:inline-block;background:#e0f2fe;border-radius:999px;
     padding:4px 10px;margin:2px 6px 2px 0;font-size:12px}
.sample{background:#f8fbff;border-left:4px solid #38bdf8;padding:12px 14px;
        border-radius:8px;white-space:pre-wrap}
table{width:100%;border-collapse:collapse;margin:12px 0;font-size:14px}
th{background:#0ea5e9;color:#fff;padding:10px;text-align:left}
td{padding:10px;border-bottom:1px solid #dbeafe;vertical-align:top}
tr:nth-child(even) td{background:#f8fbff}
</style></head><body>""",
        "<h1>✉️ Advice Reply Coach</h1><div class='subtitle'>Learning Log</div>",
        "<div class='info'>",
        f"<p><strong>Student:</strong> {escape_html(name)}</p>",
    ]
    if cls: rows.append(f"<p><strong>Class:</strong> {escape_html(cls)}</p>")
    if num: rows.append(f"<p><strong>Number:</strong> {escape_html(num)}</p>")
    rows.append(f"<p><strong>Total Sessions:</strong> {len(history)}</p></div>")
    for i, entry in enumerate(history, 1):
        rows += [
            "<div class='session'>",
            f"<h3>Session {i}</h3>",
            f"<div class='tag'>{escape_html(entry['timestamp'])}</div>"
            f"<div class='tag'>{escape_html(entry['mode_label'])}</div>",
        ]
        if entry.get("help_goal"):
            rows.append(f"<p><strong>Checklist Goal:</strong> {escape_html(entry['help_goal'])}</p>")
        if entry.get("custom_question"):
            rows.append(f"<p><strong>Custom Question:</strong> {escape_html(entry['custom_question'])}</p>")
        rows += [
            "<p><strong>My Email:</strong></p>",
            f"<div class='sample'>{escape_html(entry['writing'])}</div>",
            "<p><strong>AI Feedback:</strong></p>",
            f"<div>{entry['response']}</div>",
            "</div>",
        ]
    rows.append("</body></html>")
    return "".join(rows).encode("utf-8")


# ── Reset helpers (called BEFORE any widget renders) ─────────────────────────

def do_reset_more_help():
    """Keep student info + writing; clear mode/goal/feedback only."""
    st.session_state["selected_mode"]  = "content"
    st.session_state["help_value"]     = ""
    st.session_state["custom_question"] = ""
    st.session_state["feedback_text"]  = ""


def do_reset_fresh_start():
    """Keep student info; clear everything else."""
    st.session_state["writing_input"]   = ""
    st.session_state["selected_mode"]   = "content"
    st.session_state["help_value"]      = ""
    st.session_state["custom_question"] = ""
    st.session_state["feedback_text"]   = ""


# ── App entry point ───────────────────────────────────────────────────────────

init_state()

# Handle deferred resets BEFORE any widget is rendered this run
if st.session_state.pop("_do_reset_more_help", False):
    do_reset_more_help()
if st.session_state.pop("_do_reset_fresh_start", False):
    do_reset_fresh_start()

# ── Global CSS ────────────────────────────────────────────────────────────────

st.markdown("""
<style>
/* ── App background ── */
.stApp {
    background: linear-gradient(160deg, #f0f9ff 0%, #f8fafc 100%);
}
.block-container {max-width: 760px; padding-top: 2rem; padding-bottom: 4rem;}

/* ── Section panels ── */
.panel {
    background: #f3f4f6;
    border: 1px solid #e2e8f0;
    border-radius: 18px;
    padding: 1.25rem 1.25rem 0.5rem;
    margin-bottom: 1rem;
    box-shadow: 0 2px 12px rgba(14,165,233,0.06);
}
.hero {
    background: #f3f4f6;
    border: 1px solid #e2e8f0;
    border-radius: 18px;
    padding: 1.8rem 1.5rem;
    margin-bottom: 1rem;
    text-align: center;
    box-shadow: 0 2px 12px rgba(14,165,233,0.06);
}

/* ── Force white background on ALL input widgets ── */
input, textarea,
div[data-baseweb="input"] input,
div[data-baseweb="textarea"] textarea,
div[data-baseweb="base-input"] input,
div[data-baseweb="base-input"] textarea,
.stTextInput > div > div > input,
.stTextArea > div > textarea,
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea,
div[class*="st-"] input,
div[class*="st-"] textarea {
    background-color: #ffffff !important;
    background: #ffffff !important;
}

/* Selectbox white background */
div[data-baseweb="select"] > div:first-child,
div[data-baseweb="popover"] div[role="option"] {
    background-color: #ffffff !important;
}

/* ── Dividers between sections ── */
hr, [data-testid="stDivider"] {
    border-color: #e5e7eb !important;
    background-color: #e5e7eb !important;
}

/* ── Feedback box ── */
.feedback-box {
    background: #ffffff;
    border: 1px solid #bae6fd;
    border-radius: 14px;
    padding: 1rem 1.1rem;
    margin-top: 0.5rem;
}

/* ── Badges / chips ── */
.badge {
    display: inline-block;
    padding: 0.35rem 0.9rem;
    border-radius: 999px;
    font-size: 0.82rem;
    font-weight: 700;
    background: linear-gradient(135deg, rgba(14,165,233,0.12), rgba(245,158,11,0.12));
    color: #0369a1;
    border: 1px solid rgba(14,165,233,0.20);
    margin-bottom: 0.75rem;
}
.help-chip {
    display: inline-block;
    padding: 0.28rem 0.65rem;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 700;
    background: #ecfeff;
    color: #0f766e;
    border: 1px solid #99f6e4;
}

/* ── History card ── */
.history-card {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 1rem 1rem 0.5rem;
    margin-bottom: 0.85rem;
}
.history-meta {
    display: inline-block;
    margin: 0 0.4rem 0.3rem 0;
    padding: 0.25rem 0.65rem;
    border-radius: 999px;
    background: #e0f2fe;
    color: #075985;
    font-size: 0.78rem;
    font-weight: 700;
}

.small-note {color: #475569; font-size: 0.92rem; margin: 0;}
</style>
""", unsafe_allow_html=True)

# ── Hero ──────────────────────────────────────────────────────────────────────

st.markdown("""
<div class='hero'>
  <div class='badge'>✉️ Advice Reply Coach</div>
  <h1 style='margin:0 0 0.35rem 0;'>Your Smart Helper for Writing a Convincing Reply!</h1>
  <p class='small-note'>Step through the form, get targeted AI feedback, and download your Learning Log.</p>
</div>
""", unsafe_allow_html=True)

# ── Step 1: Student Info ──────────────────────────────────────────────────────

st.markdown("<div class='panel'>", unsafe_allow_html=True)
st.subheader("👋 Step 1 — About You")
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

# ── Step 2: Writing Input ─────────────────────────────────────────────────────

st.markdown("<div class='panel'>", unsafe_allow_html=True)
st.subheader("✍️ Step 2 — Your Advice Reply Email")
if not step1_ok:
    st.info("Please fill in your name, class, and class number above first.")

st.text_area(
    "Paste or type your advice reply email below",
    key="writing_input",
    placeholder="Paste your whole email here, or just the part you want feedback on...",
    height=220,
    disabled=not step1_ok,
)
wc = word_count(st.session_state.get("writing_input", ""))
st.caption(f"{wc} word{'s' if wc != 1 else ''}")
st.markdown("</div>", unsafe_allow_html=True)

step2_ok = len(st.session_state.get("writing_input", "").strip()) > 10

# ── Step 3: Mode Selection ────────────────────────────────────────────────────

st.markdown("<div class='panel'>", unsafe_allow_html=True)
st.subheader("🎯 Step 3 — What Would You Like Help With?")
if not step2_ok:
    st.info("Please paste your advice reply email above first.")

mode = st.radio(
    "Choose a help category",
    options=["content", "language", "organisation"],
    format_func=lambda x: {"content": "Content", "language": "Language", "organisation": "Organisation"}[x],
    key="selected_mode",
    horizontal=True,
    disabled=not step2_ok,
)
if step2_ok and mode:
    st.markdown(f"<p class='small-note'>{MODE_DESCRIPTIONS[mode]}</p>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

step3_ok = step2_ok and bool(mode)

# ── Step 4: Checklist Goal ────────────────────────────────────────────────────

options_map = {"": "— Pick a goal —"}
if step3_ok:
    for item in HELP_OPTIONS[mode]:
        options_map[item["value"]] = item["label"]

st.markdown("<div class='panel'>", unsafe_allow_html=True)
st.subheader("📋 Step 4 — Choose a Checklist Goal")
if not step3_ok:
    st.info("Please choose a help category above first.")

st.selectbox(
    "What would you like feedback on?",
    options=list(options_map.keys()),
    format_func=lambda x: options_map[x],
    key="help_value",
    disabled=not step3_ok,
)
st.markdown("</div>", unsafe_allow_html=True)

# ── Step 5: Custom Question (optional) ───────────────────────────────────────

st.markdown("<div class='panel'>", unsafe_allow_html=True)
st.subheader("💬 Step 5 — Ask Your Own Question  *(optional)*")
st.text_area(
    "Got a specific question about your email?",
    key="custom_question",
    placeholder="e.g. Does my advice sound helpful? Did I show enough empathy?",
    height=90,
    disabled=not step3_ok,
)
st.markdown("</div>", unsafe_allow_html=True)

# ── Submit ────────────────────────────────────────────────────────────────────

col_a, col_b = st.columns([3, 1])
with col_a:
    submit = st.button("📨 Get Feedback", type="primary",
                       use_container_width=True, disabled=not step3_ok)
with col_b:
    if st.button("🧹 Clear", use_container_width=True):
        st.session_state["feedback_text"] = ""
        st.rerun()

if submit:
    writing  = st.session_state.get("writing_input", "").strip()
    custom_q = st.session_state.get("custom_question", "").strip()
    hv       = st.session_state.get("help_value", "")
    md       = st.session_state.get("selected_mode", "")
    name     = st.session_state.get("student_name", "").strip()

    if not writing or len(writing) < 10:
        st.error("Please type or paste your advice reply email first (at least a few sentences).")
    elif not hv and not custom_q:
        st.error("Please pick a checklist goal or type your own question.")
    elif detect_write_for_me(custom_q):
        st.warning(
            "I can't write or finish your email for you.\n\n"
            "Writing is YOUR skill to grow — try your best first, then I'll give you tips to make it even better!"
        )
    else:
        prompt     = build_prompt(writing, name, md, hv, custom_q)
        help_label = options_map.get(hv, "") if hv else ""
        try:
            with st.spinner("Reviewing your email..."):
                feedback = get_ai_feedback(prompt)
            st.session_state["feedback_text"] = feedback
            st.session_state["interaction_count"] += 1
            st.session_state["interaction_history"].append({
                "timestamp":       datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "mode":            md,
                "mode_label":      MODE_DESC_MAP[md],
                "help_goal":       help_label,
                "custom_question": custom_q,
                "writing":         writing,
                "response":        feedback,
            })
        except Exception as e:
            st.error(f"Groq API error: {e}")

# ── Feedback Display ──────────────────────────────────────────────────────────

if st.session_state.get("feedback_text"):
    st.markdown("<div class='panel'>", unsafe_allow_html=True)
    st.subheader("✨ Your Feedback")
    count = st.session_state["interaction_count"]
    st.markdown(
        f"<span class='help-chip'>💬 {count} interaction{'s' if count != 1 else ''}</span>",
        unsafe_allow_html=True,
    )
    st.markdown("<div class='feedback-box'>", unsafe_allow_html=True)
    st.markdown(st.session_state["feedback_text"])
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ── What's Next ───────────────────────────────────────────────────────────────

if st.session_state.get("interaction_history"):
    st.markdown("<div class='panel'>", unsafe_allow_html=True)
    st.subheader("🚀 What's Next?")
    nx1, nx2 = st.columns(2)
    with nx1:
        if st.button("🎯 Try Another Checklist Goal", use_container_width=True,
                     help="Keep the same email, choose a different goal"):
            st.session_state["_do_reset_more_help"] = True
            st.rerun()
    with nx2:
        if st.button("✏️ Review a New Part of My Email", use_container_width=True,
                     help="Clear the email box and start fresh"):
            st.session_state["_do_reset_fresh_start"] = True
            st.rerun()

    st.download_button(
        "💾 Save Learning Log",
        data=download_log_html(),
        file_name=f"Learning_Log_{(st.session_state.get('student_name') or 'Student').replace(' ','_')}.html",
        mime="text/html",
        use_container_width=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

# ── Session History expander ──────────────────────────────────────────────────

with st.expander("🧾 Session History"):
    history = st.session_state.get("interaction_history", [])
    if not history:
        st.write("No feedback sessions yet.")
    else:
        for i, item in enumerate(reversed(history), 1):
            idx = len(history) - i + 1
            st.markdown("<div class='history-card'>", unsafe_allow_html=True)
            st.markdown(f"**Session {idx}**")
            st.markdown(
                f"<span class='history-meta'>🕒 {item['timestamp']}</span>"
                f"<span class='history-meta'>🎯 {item['mode_label']}</span>",
                unsafe_allow_html=True,
            )
            if item.get("help_goal"):
                st.markdown(
                    f"<span class='history-meta'>📋 {item['help_goal']}</span>",
                    unsafe_allow_html=True,
                )
            if item.get("custom_question"):
                st.markdown(f"**Custom question:** {item['custom_question']}")
            st.markdown("**Writing sample**")
            st.code(item["writing"], language=None)
            st.markdown("**Feedback**")
            st.markdown(item["response"])
            st.markdown("</div>", unsafe_allow_html=True)

st.caption("Powered by Groq · Adapted from the original POE bot")
