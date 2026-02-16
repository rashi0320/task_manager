from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps


app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///tasks.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = "supersecret"  # Change in production

db = SQLAlchemy(app)


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
    tasks = db.relationship("Task", backref="user", lazy=True)


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    def __repr__(self):
        return f"<Task {self.id}>"


# ======================
# AUTH ROUTES
# ======================


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]

        # Prevent duplicate usernames
        if User.query.filter_by(username=username).first():
            return "Username already exists"

        password = generate_password_hash(request.form["password"])
        user = User(username=username, password=password)

        db.session.add(user)
        db.session.commit()

        return redirect("/login")

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(username=request.form["username"]).first()

        if user and check_password_hash(user.password, request.form["password"]):
            session["user_id"] = user.id
            return redirect("/")

        return "Invalid credentials"

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ======================
# HOME / READ TASKS
# ======================


@app.route("/")
@login_required
def get_tasks():

    if "user_id" not in session:
        return redirect("/login")

    tasks = (
        Task.query.filter_by(user_id=session["user_id"]).order_by(Task.id.desc()).all()
    )

    user = User.query.get(session["user_id"])
    return render_template("index.html", tasks=tasks, username=user.username)


# ======================
# CREATE TASK
# ======================


@app.route("/tasks", methods=["POST"])
@login_required
def create_task():

    if "user_id" not in session:
        return redirect("/login")

    task_text = request.form.get("task")

    if task_text:
        new_task = Task(content=task_text, user_id=session["user_id"])
        db.session.add(new_task)
        db.session.commit()

    return redirect(url_for("get_tasks"))


# ======================
# UPDATE TASK (AJAX)
# ======================


@app.route("/tasks/<int:id>/update", methods=["POST"])
@login_required
def update_text(id):

    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    task = Task.query.filter_by(id=id, user_id=session["user_id"]).first()

    if not task:
        return jsonify({"error": "Task not found"}), 404

    data = request.get_json()
    task.content = data["content"]
    db.session.commit()

    return jsonify({"status": "updated"})


# ======================
# DELETE SINGLE TASK
# ======================


@app.route("/tasks/<int:id>/delete")
@login_required
def delete_task(id):

    if "user_id" not in session:
        return redirect("/login")

    task = Task.query.filter_by(id=id, user_id=session["user_id"]).first()

    if task:
        db.session.delete(task)
        db.session.commit()

    return redirect(url_for("get_tasks"))


# ======================
# MULTI DELETE
# ======================


@app.route("/tasks/multi-delete", methods=["POST"])
@login_required
def multi_delete():

    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    ids = data.get("ids")

    if ids:
        Task.query.filter(Task.id.in_(ids), Task.user_id == session["user_id"]).delete(
            synchronize_session=False
        )

        db.session.commit()

    return jsonify({"status": "success"})


# ======================

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
