from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import date
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///tasks.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = "supersecret"

db = SQLAlchemy(app)

# ======================
# LOGIN REQUIRED DECORATOR
# ======================

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated


# ======================
# MODELS
# ======================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    reward_points = db.Column(db.Integer, default=0)
    tasks = db.relationship("Task", backref="user", lazy=True)


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    completed = db.Column(db.Boolean, default=False)
    date_created = db.Column(db.Date, default=date.today)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


# ======================
# LANDING PAGE
# ======================

@app.route("/")
def landing():
    return render_template("landing.html")


# ======================
# DASHBOARD
# ======================

@app.route("/dashboard")
@login_required
def dashboard():

    tasks = Task.query.filter_by(
        user_id=session["user_id"]
    ).order_by(Task.id.desc()).all()

    user = User.query.get(session["user_id"])

    return render_template(
        "index.html",
        tasks=tasks,
        username=user.username
    )


# ======================
# SIGNUP
# ======================

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":

        username = request.form["username"]

        if User.query.filter_by(username=username).first():
            return "Username already exists"

        password = generate_password_hash(request.form["password"])

        user = User(username=username, password=password)

        db.session.add(user)
        db.session.commit()

        return redirect("/login")

    return render_template("signup.html")


# ======================
# LOGIN
# ======================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":

        user = User.query.filter_by(
            username=request.form["username"]
        ).first()

        if user and check_password_hash(user.password, request.form["password"]):

            session["user_id"] = user.id
            return redirect("/dashboard")

        return "Invalid credentials"

    return render_template("login.html")


# ======================
# LOGOUT
# ======================

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ======================
# CREATE TASK
# ======================

@app.route("/tasks", methods=["POST"])
@login_required
def create_task():

    task_text = request.form.get("task")

    if task_text:
        new_task = Task(
            content=task_text,
            user_id=session["user_id"]
        )

        db.session.add(new_task)
        db.session.commit()

    return redirect("/dashboard")


# ======================
# COMPLETE TASK
# ======================

@app.route("/tasks/<int:id>/complete")
@login_required
def complete_task(id):

    task = Task.query.filter_by(
        id=id,
        user_id=session["user_id"]
    ).first()

    if task and not task.completed:
        task.completed = True

        user = User.query.get(session["user_id"])
        user.reward_points += 1

        db.session.commit()

    return redirect("/dashboard")


# ======================
# DELETE TASK
# ======================

@app.route("/tasks/<int:id>/delete")
@login_required
def delete_task(id):

    task = Task.query.filter_by(
        id=id,
        user_id=session["user_id"]
    ).first()

    if task:
        db.session.delete(task)
        db.session.commit()

    return redirect("/dashboard")


# ======================
# CONSISTENCY FUNCTION
# ======================

def calculate_consistency(user_id):
    total = Task.query.filter_by(user_id=user_id).count()
    completed = Task.query.filter_by(
        user_id=user_id,
        completed=True
    ).count()

    if total == 0:
        return 0

    return round((completed / total) * 100, 2)


# ======================
# MY ACCOUNT
# ======================

@app.route("/account")
@login_required
def account():

    user = User.query.get(session["user_id"])

    total_tasks = Task.query.filter_by(user_id=user.id).count()
    completed_tasks = Task.query.filter_by(
        user_id=user.id,
        completed=True
    ).count()

    consistency = calculate_consistency(user.id)

    return render_template(
        "account.html",
        username=user.username,
        reward=user.reward_points,
        total=total_tasks,
        completed=completed_tasks,
        consistency=consistency
    )
    
def check_incomplete_tasks():

    users = User.query.all()

    for user in users:

        incomplete = Task.query.filter_by(
            user_id=user.id,
            completed=False
        ).count()

        if incomplete > 0:
            print(f"Reminder: {user.username} has incomplete tasks today!")
            
            
scheduler = BackgroundScheduler()
scheduler.add_job(
    func=check_incomplete_tasks,
    trigger="cron",
    hour=21,
    minute=0
)
scheduler.start()


# ======================

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)