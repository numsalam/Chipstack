"""
ChipStack - Hack Club Jackpot Project Showcase
Robust Flask app with GitHub API & SQLite.
"""

from datetime import datetime, timezone
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

# Globals
github_cache = {}
CACHE_TIMEOUT = 7200  # 2 hours

class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    github_url = db.Column(db.String(500), nullable=True)
    demo_url = db.Column(db.String(500), nullable=True)
    hours = db.Column(db.Float, nullable=False, default=0.0)
    submitter = db.Column(db.String(100), nullable=False)
    tags = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    stars = db.Column(db.Integer, default=0)
    language = db.Column(db.String(50), nullable=True)
    github_last_fetched = db.Column(db.DateTime, nullable=True)
    last_updated = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<Project {self.title}>"

def get_github_data(github_url):
    if not github_url or not github_url.startswith('https://github.com/'):
        return None

    cache_key = github_url
    if cache_key in github_cache:
        data, ts = github_cache[cache_key]
        if time.time() - ts < CACHE_TIMEOUT:
            return data

    match = re.search(r'github\.com/([^/]+)/([^/]+)', github_url)
    if not match:
        return None

    owner, repo = match.groups()
    try:
        r = requests.get(f"https://api.github.com/repos/{owner}/{repo}", timeout=10)
        r.raise_for_status()
        js = r.json()

        data = {
            'stars': js.get('stargazers_count', 0),
            'language': js.get('language'),
            'last_updated': datetime.fromisoformat(js['pushed_at'].rstrip('Z') + '+00:00') if 'pushed_at' in js else None
        }

        github_cache[cache_key] = (data, time.time())
        return data
    except Exception as e:
        print(f"GitHub error ({github_url}): {e}")
        return None

def safe_init_db():
    """Dev-safe DB: Always drop/recreate + seed (early dev)."""
    print("Initializing DB...")
    db.drop_all()
    db.create_all()
    print("Tables created.")

    if not Project.query.first():
        print("Seeding projects...")
        seeds = [
            Project(title="ChipStack", description="Hack Club showcase w/ GitHub API.", github_url="https://github.com/numsalam/chipstack", hours=30, submitter="Numaan", tags="flask,python,neon"),
            Project(title="HackClub Website", description="Student maker clubs site.", github_url="https://github.com/hackclub/website", demo_url="https://hackclub.com", hours=125, submitter="Team", tags="nextjs,react"),
            Project(title="Jackpot", description="Gamified Hack Club donations.", github_url="https://github.com/hackclub/jackpot", hours=90, submitter="Zain", tags="ruby,rails"),
        ]
        db.session.add_all(seeds)
        db.session.commit()
        print("Seeded 3 projects!")
    else:
        print("DB already seeded.")

@app.route("/")
def index():
    projects = Project.query.order_by(Project.hours.desc()).all()
    for p in projects:
        if p.github_url:
            data = get_github_data(p.github_url)
            if data:
                changed = False
                if p.stars != data['stars']:
                    p.stars = data['stars']
                    changed = True
                if p.language != data['language']:
                    p.language = data['language']
                    changed = True
                if p.last_updated != data['last_updated']:
                    p.last_updated = data['last_updated']
                    p.github_last_fetched = datetime.now(timezone.utc)
                    changed = True
                if changed:
                    db.session.commit()
                    print(f"Updated {p.title}")
    db.session.commit()
    return render_template("index.html", projects=projects)

@app.route("/leaderboard")
def leaderboard():
    """Leaderboard - same projects as home."""
    return index()

@app.route("/refresh", methods=["POST"])
def refresh():
    """Refresh GitHub data for all projects."""
    updated = 0
    for p in Project.query.all():
        if p.github_url:
            data = get_github_data(p.github_url)
            if data:
                changed = False
                if p.stars != data['stars']:
                    p.stars = data['stars']
                    changed = True
                if p.language != data['language']:
                    p.language = data['language']
                    changed = True
                if p.last_updated != data['last_updated']:
                    p.last_updated = data['last_updated']
                    p.github_last_fetched = datetime.now(timezone.utc)
                    changed = True
                if changed:
                    updated += 1
    db.session.commit()
    flash(f"Refreshed GitHub data for {updated} projects!", "success")
    return redirect(url_for("index"))

@app.route("/submit", methods=["POST"])
def submit():
    try:
        title = request.form["title"].strip()
        desc = request.form["description"].strip()
        submitter = request.form["submitter"].strip()
        hours = float(request.form["hours"])
        if not all([title, desc, submitter]) or hours <= 0 or len(title) < 3:
            flash("Invalid input!", "error")
            return redirect(url_for("index"))
        p = Project(title=title, description=desc, github_url=request.form.get("github_url") or None, demo_url=request.form.get("demo_url") or None, hours=hours, submitter=submitter, tags=request.form.get("tags") or None)
        db.session.add(p)
        db.session.commit()
        flash(f"Added '{title}' ({hours}h)", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error: {e}", "error")
    return redirect(url_for("index"))

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404

@app.errorhandler(500)
def server_error(e):
    db.session.rollback()
    return render_template("500.html"), 500

if __name__ == "__main__":
    with app.app_context():
        safe_init_db()
    app.run(debug=True)
