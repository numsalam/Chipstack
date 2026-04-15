"""
ChipStack - Hack Club Jackpot Project Showcase
A Flask + SQLAlchemy app for student project showcase with GitHub integration.
"""

from datetime import datetime
import os
import re
import time
import requests
from pathlib import Path
from flask import Flask, render_template, request, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Config
BASE_DIR = Path(__file__).parent
DATABASE_PATH = BASE_DIR / "instance" / "chipstack.db"
DATABASE_PATH.parent.mkdir(exist_ok=True)

app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DATABASE_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key-change-in-production")

db = SQLAlchemy(app)

# Globals for caching
github_cache = {}
CACHE_TIMEOUT = 2 * 60 * 60  # 2 hours

class Project(db.Model):
    """Project model with GitHub integration fields."""

    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    github_url = db.Column(db.String(500), nullable=True)
    demo_url = db.Column(db.String(500), nullable=True)
    hours = db.Column(db.Float, nullable=False, default=0.0)
    submitter = db.Column(db.String(100), nullable=False)
    tags = db.Column(db.String(500), nullable=True)  # comma-separated e.g. "python,flask"
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    stars = db.Column(db.Integer, default=0)
    language = db.Column(db.String(50), nullable=True)
    github_last_fetched = db.Column(db.DateTime, nullable=True)
    last_updated = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<Project {self.title}>"

def get_github_data(github_url):
    """Fetch GitHub repo stats: stars, language, last commit date. Cached 2hrs."""
    if not github_url or not github_url.startswith('https://github.com/'):
        return None

    cache_key = github_url
    if cache_key in github_cache:
        data, timestamp = github_cache[cache_key]
        if time.time() - timestamp < CACHE_TIMEOUT:
            return data

    # Extract owner/repo
    match = re.search(r'github\.com/([^/]+)/([^/]+)', github_url)
    if not match:
        return None

    owner, repo = match.groups()
    try:
        resp = requests.get(f"https://api.github.com/repos/{owner}/{repo}", timeout=10)
        resp.raise_for_status()
        js = resp.json()

        result = {
            'stars': js.get('stargazers_count', 0),
            'language': js.get('language'),
            'last_updated': datetime.fromisoformat(js.get('pushed_at', '').rstrip('Z') + '+00:00') if js.get('pushed_at') else None
        }

        github_cache[cache_key] = (result, time.time())
        return result
    except Exception as e:
        print(f"GitHub API error ({github_url}): {e}")
        return None

def safe_init_db():
    """Robust DB init for dev: drop/recreate if debug mode, seed data."""
    if app.debug:
        print("Debug mode: Dropping and recreating DB...")
        db.drop_all()
        db.create_all()
    else:
        db.create_all()

    # Seed if empty
    if not Project.query.first():
        print("Seeding sample projects...")
        seed_data = [
            Project(
                title="ChipStack Gallery",
                description="Neon Hack Club project showcase with GitHub integration.",
                github_url="https://github.com/numsalam/chipstack",
                hours=28.5,
                submitter="Numaan Aquil",
                tags="flask,python,sqlite,tailwind,neon",
            ),
            Project(
                title="Hack Club Website",
                description="Student-powered high school maker clubs platform.",
                github_url="https://github.com/hackclub/website",
                demo_url="https://hackclub.com",
                hours=125.0,
                submitter="Hack Club Core Team",
                tags="nextjs,react,tailwind,typescript",
            ),
            Project(
                title="Jackpot Fundraiser",
                description="Gamified donations for Hack Club global community.",
                github_url="https://github.com/hackclub/jackpot",
                hours=90.0,
                submitter="Zain & Team",
                tags="ruby,rails,react,postgresql",
            ),
            Project(
                title="AI Study Buddy",
                description="Chatbot for generating practice problems and study help.",
                github_url="https://github.com/hackclub/builder",
                hours=45.0,
                submitter="Hack Club Builders",
                tags="python,openai,flask",
            ),
        ]
        db.session.add_all(seed_data)
        db.session.commit()
        print("DB seeded!")

@app.route("/")
def index():
    """Home: List projects sorted by hours, fetch GitHub data."""
    projects = Project.query.order_by(Project.hours.desc()).all()

    # Update GitHub data
    for project in projects:
        if project.github_url:
            data = get_github_data(project.github_url)
            if data:
                updated = False
                if project.stars != data['stars']:
                    project.stars = data['stars']
                    updated = True
                if project.language != data['language']:
                    project.language = data['language']
                    updated = True
                if project.last_updated != data['last_updated']:
                    project.last_updated = data['last_updated']
                    project.github_last_fetched = datetime.utcnow()
                    updated = True
                if updated:
                    db.session.commit()
                    print(f"Updated GitHub data for {project.title}")

    return render_template("index.html", projects=projects)

@app.route("/submit", methods=["POST"])
def submit():
    """Submit new project with validation."""
    try:
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        submitter = request.form.get("submitter", "").strip()
        hours_str = request.form.get("hours", "0")
        github_url = request.form.get("github_url", "").strip() or None
        demo_url = request.form.get("demo_url", "").strip() or None
        tags = request.form.get("tags", "").strip() or None

        # Validation
        if not all([title, description, submitter]):
            flash("All required fields needed!", "error")
            return redirect(url_for("index"))
        if len(title) < 3 or len(description) < 10:
            flash("Title min 3 chars, desc min 10 chars.", "error")
            return redirect(url_for("index"))
        try:
            hours = float(hours_str)
            if hours <= 0:
                raise ValueError
        except ValueError:
            flash("Hours must be positive number.", "error")
            return redirect(url_for("index"))

        project = Project(
            title=title, description=description, github_url=github_url,
            demo_url=demo_url, hours=hours, submitter=submitter, tags=tags
        )
        db.session.add(project)
        db.session.commit()
        flash(f"🎉 '{title}' submitted! ({hours}h)", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Submit error: {str(e)}", "error")
    return redirect(url_for("index"))

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404

@app.errorhandler(500)
def internal_error(e):
    db.session.rollback()
    return render_template("500.html"), 500

if __name__ == "__main__":
    with app.app_context():
        safe_init_db()
    app.run(debug=True, host="0.0.0.0")

