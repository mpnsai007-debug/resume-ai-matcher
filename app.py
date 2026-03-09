from flask import Flask, render_template, request, redirect, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import PyPDF2
import docx
import os

app = Flask(__name__)
app.secret_key = "secret123"

# ---------------- DATABASE ---------------- #

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


# ---------------- SIGNUP ---------------- #

@app.route("/signup", methods=["POST"])
def signup():

    username = request.form["username"]
    email = request.form["email"]
    password = generate_password_hash(request.form["password"])

    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    try:

        c.execute(
        "INSERT INTO users(username,email,password) VALUES(?,?,?)",
        (username,email,password)
        )

        conn.commit()

    except sqlite3.IntegrityError:

        conn.close()
        return "User already exists. Please login."

    conn.close()

    session["user"] = username

    return redirect("/")


# ---------------- LOGIN ---------------- #

@app.route("/login", methods=["POST"])
def login():

    email = request.form["email"]
    password = request.form["password"]

    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    c.execute("SELECT * FROM users WHERE email=?", (email,))
    user = c.fetchone()

    conn.close()

    if user is None:
        return "User not registered. Please signup."

    if not check_password_hash(user[3], password):
        return "Incorrect password."

    session["user"] = user[1]

    return redirect("/")


# ---------------- LOGOUT ---------------- #

@app.route("/logout")
def logout():

    session.pop("user", None)

    return redirect("/")


# ---------------- RESUME TEXT EXTRACTION ---------------- #

def extract_pdf(file):

    reader = PyPDF2.PdfReader(file)

    text = ""

    for page in reader.pages:
        text += page.extract_text()

    return text


def extract_docx(file):

    doc = docx.Document(file)

    text = ""

    for para in doc.paragraphs:
        text += para.text

    return text


# ---------------- MAIN PAGE ---------------- #

@app.route("/", methods=["GET","POST"])
def index():

    score = None

    if request.method == "POST":

        role = request.form["role"]
        level = request.form["level"]
        resume = request.files["resume"]

        # Example job descriptions
        jobs = {
        "Software Engineer":"python java algorithms data structures software development",
        "Data Scientist":"python machine learning statistics data analysis pandas numpy",
        "Web Developer":"html css javascript react web development frontend backend"
        }

        jd = jobs.get(role,"")

        if resume.filename.endswith(".pdf"):
            resume_text = extract_pdf(resume)

        elif resume.filename.endswith(".docx"):
            resume_text = extract_docx(resume)

        else:
            resume_text = resume.read().decode("utf-8")

        cv = CountVectorizer()

        matrix = cv.fit_transform([resume_text, jd])

        similarity = cosine_similarity(matrix)[0][1]

        score = round(similarity * 100,2)

    return render_template(
    "index.html",
    score=score,
    user=session.get("user")
    )


# ---------------- RUN ---------------- #

if __name__ == "__main__":

    port = int(os.environ.get("PORT",5000))

    app.run(host="0.0.0.0",port=port)