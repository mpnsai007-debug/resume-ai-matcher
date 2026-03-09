from flask import Flask, render_template, request, send_file, redirect, session
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import PyPDF2
import docx
import os
import wikipedia
import sqlite3

from werkzeug.security import generate_password_hash, check_password_hash

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import A4

app = Flask(__name__)
app.secret_key = "super_secret_key_123"

app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024

# Create static folder if missing
if not os.path.exists("static"):
    os.makedirs("static")

# -------------------------
# DATABASE
# -------------------------
def init_db():
    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        email TEXT UNIQUE,
        password TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# -------------------------
# WIKIPEDIA ROLE MAPPING
# -------------------------
wiki_mapping = {
    "Data Scientist": "Data science",
    "Web Developer": "Web developer",
    "Software Engineer": "Software engineering"
}

def get_job_description(role, level):
    try:
        page = wiki_mapping.get(role, role)
        summary = wikipedia.summary(page, sentences=5)

        if level == "Fresher":
            extra = "Entry-level candidate expected to have strong fundamentals and academic knowledge."
        else:
            extra = "Candidate expected to have industry experience and real-world project exposure."

        return summary + " " + extra

    except:
        return "Professional technical role requiring analytical and problem solving skills."

# -------------------------
# RESUME EXTRACTION
# -------------------------
def extract_pdf(file):
    reader = PyPDF2.PdfReader(file)
    text = ""
    for p in reader.pages:
        text += p.extract_text() or ""
    return text

def extract_docx(file):
    doc = docx.Document(file)
    return "\n".join([p.text for p in doc.paragraphs])

# -------------------------
# PDF REPORT
# -------------------------
def generate_report(score, role, level, missing):
    path = "static/report.pdf"

    doc = SimpleDocTemplate(path, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Resume Analysis Report", styles['Heading1']))
    elements.append(Spacer(1,0.3*inch))

    data = [
        ["Role", role],
        ["Experience", level],
        ["Score", str(score)+"%"]
    ]

    table = Table(data)
    table.setStyle(TableStyle([
        ('GRID',(0,0),(-1,-1),1,colors.grey)
    ]))

    elements.append(table)
    elements.append(Spacer(1,0.3*inch))

    elements.append(Paragraph("Missing Skills:", styles['Heading2']))

    for m in missing:
        elements.append(Paragraph("- "+m, styles['Normal']))

    doc.build(elements)

# -------------------------
# AUTH ROUTES
# -------------------------
@app.route("/signup", methods=["POST"])
def signup():

    username = request.form["username"]
    email = request.form["email"]
    password = generate_password_hash(request.form["password"])

    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    try:
        c.execute("INSERT INTO users(username,email,password) VALUES(?,?,?)",
                  (username,email,password))
        conn.commit()
    except:
        return redirect("/")

    conn.close()

    session["user"] = username
    return redirect("/")


@app.route("/login", methods=["POST"])
def login():

    email = request.form["email"]
    password = request.form["password"]

    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    c.execute("SELECT * FROM users WHERE email=?", (email,))
    user = c.fetchone()

    conn.close()

    if user and check_password_hash(user[3], password):
        session["user"] = user[1]

    return redirect("/")


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/")

# -------------------------
# DOWNLOAD REPORT
# -------------------------
@app.route('/download')
def download():
    return send_file("static/report.pdf", as_attachment=True)

# -------------------------
# MAIN PAGE
# -------------------------
@app.route("/", methods=["GET","POST"])
def index():

    score=None
    missing=[]
    ready=False

    if request.method=="POST":

        role = request.form.get("role")
        level = request.form.get("level")
        file = request.files.get("resume")

        if not role or not level:
            return redirect("/")

        jd = get_job_description(role,level)

        if file.filename.endswith(".pdf"):
            resume = extract_pdf(file)

        elif file.filename.endswith(".docx"):
            resume = extract_docx(file)

        else:
            resume = file.read().decode("utf-8", errors="ignore")

        data=[resume,jd]

        cv = CountVectorizer(stop_words="english")
        matrix = cv.fit_transform(data)

        sim = cosine_similarity(matrix)[0][1]
        score = round(sim*100,2)

        r=set(resume.lower().split())
        j=set(jd.lower().split())

        missing=list(j-r)[:10]

        generate_report(score,role,level,missing)
        ready=True

    return render_template("index.html",
                           score=score,
                           missing_keywords=missing,
                           report_ready=ready,
                           user=session.get("user"))

# -------------------------
# RUN
# -------------------------
if __name__ == "__main__":
    port=int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0",port=port)