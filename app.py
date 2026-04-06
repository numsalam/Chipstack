"""
ChipStack - Hack Club Jackpot Project Showcase
A Flask application for showcasing student projects with time invested
"""

from datetime import datetime
from pathlib import Path
import os

from flask import Flask, render_template, request, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

BASE_DIR = Path(__file__).parent
DATABASE_PATH = BASE_DIR / "instance" / "chipstack.db"
DATABASE_PATH.parent.mkdir(exist_ok=True)

app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DATABASE_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key-change-in-production")

db = SQLAlchemy(app)


class Project(db.Model):
    """Project model for ChipStack showcase"""

    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    github_url = db.Column(db.String(500), nullable=True)
    demo_url = db.Column(db.String(500), nullable=True)
    hours = db.Column(db.Float, nullable=False, default=0.0)
    submitter = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<Project {self.title}>"


def init_db():
    """Initialize database and seed with sample data if empty"""
    db.create_all()

    if Project.query.first() is not None:
        return

    sample_projects = [
        Project(
            title="AI Study Assistant",
            description="An AI-powered chatbot that helps students study by answering questions and generating practice problems.",
            github_url="https://github.com/hack-club/ai-study-assistant",
            demo_url="https://ai-study-assistant.demo",
            hours=48.5,
            submitter="Alice Chen",
        ),
        Project(
            title="Local Event Finder",
            description="A web app that uses geolocation and APIs to help users find local events, concerts, and meetups in their area.",
            github_url="https://github.com/hack-club/event-finder",
            demo_url="https://event-finder.demo",
            hours=32.0,
            submitter="Bob Martinez",
        ),
        Project(
            title="Code Collaboration Platform",
            description="Real-time collaborative code editor with syntax highlighting, version control, and live chat for remote pair programming.",
            github_url="https://github.com/hack-club/collab-code",
            demo_url="https://collab-code.demo",
            hours=56.75,
            submitter="Carol Johnson",
        ),
    ]

    db.session.add_all(sample_projects)
    db.session.commit()


@app.route("/")
def index():
    """Display all projects sorted by hours descending"""
    projects = Project.query.order_by(Project.hours.desc()).all()
    return render_template("index.html", projects=projects)


@app.route("/submit", methods=["POST"])
def submit():
    """Handle project submission from form data"""
    try:
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        submitter = request.form.get("submitter", "").strip()
        hours = request.form.get("hours", "0")

        if not all([title, description, submitter]):
            flash("Please fill in all required fields.", "error")
            return redirect(url_for("index"))

        try:
            hours_float = float(hours)
            if hours_float < 0:
                raise ValueError("Hours must be positive")
        except ValueError:
            flash("Hours must be a valid positive number.", "error")
            return redirect(url_for("index"))

        github_url = request.form.get("github_url", "").strip() or None
        demo_url = request.form.get("demo_url", "").strip() or None
        project = Project(
            title=title,
            description=description,
            github_url=github_url,
            demo_url=demo_url,
            hours=hours_float,
            submitter=submitter,
        )
        db.session.add(project)
        db.session.commit()

        flash(f"Project '{title}' submitted successfully!", "success")
        return redirect(url_for("index"))

    except Exception as e:
        db.session.rollback()
        flash(f"An error occurred while submitting your project: {str(e)}", "error")
        return redirect(url_for("index"))


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(error):
    """Handle 500 errors"""
    db.session.rollback()
    return render_template("500.html"), 500


if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True)
