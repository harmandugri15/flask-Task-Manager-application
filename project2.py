from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask_login import LoginManager, login_user, logout_user, UserMixin, login_required, current_user
from datetime import timedelta, datetime
from sqlalchemy import text, inspect
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Use os.path.abspath to create an absolute path to the database file
basedir = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = 'sqlite:///database.db'
app.config["SECRET_KEY"] = "DEVA"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=10)
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'uploads')
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Add the date filter to Jinja2 environment
def date_filter(value, format='%Y.%m'):
    if isinstance(value, str):
        value = datetime.strptime(value, '%Y-%m-%d')
    return value.strftime(format)

app.jinja_env.filters['date'] = date_filter

class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(100), default="user")
    profile_image = db.Column(db.String(255), default='default.jpg')  # Add this line
    pdfs = db.relationship('PDF', backref='user', lazy=True)

    def __repr__(self):
        return f"User('{self.username}', '{self.email}', '{self.role}')"

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Tasks(db.Model):
    __tablename__ = "tasks"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), nullable=False)
    task = db.Column(db.String(1000), nullable=False)
    date = db.Column(db.String(100), nullable=False)
    priority = db.Column(db.Boolean, default=False)
    completed = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"Task('{self.task}', '{self.date}', '{self.priority}', '{self.completed}')"

class PDF(db.Model):
    __tablename__ = "pdfs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    filepath = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f"PDF('{self.filename}', '{self.filepath}')"

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/signup")
def signup():
    return render_template('signup.html')

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")

        if not username or not email or not password:
            flash("Please fill in all fields")
            return redirect(url_for("signup"))

        if User.query.filter_by(email=email).first():
            flash("User already exists")
            return redirect(url_for("signup"))

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("User registered successfully. Please log in.")
        return redirect(url_for("login"))

    return redirect(url_for("signup"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            session.permanent = True
            flash("User Logged In Successfully")
            return redirect(url_for("home"))
        else:
            flash("Invalid email or password")
            return render_template("signup.html")

    return render_template("signup.html")

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.route("/payment")
@login_required
def payment():
    return render_template('payment.html')

@app.route("/dashboard")
@login_required
def dashboard():
    email = current_user.email
    task_data = Tasks.query.filter_by(email=email).all()
    user_data = User.query.filter_by(email=email).first()
    current_date = datetime.now()
    return render_template('dashboard.html', tasks=task_data, user=user_data, current_date=current_date)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("User Logged out Successfully")
    return redirect(url_for("home"))

@app.route("/add", methods=["GET", "POST"])
@login_required
def add():
    if request.method == "POST":
        email = current_user.email
        task = request.form.get("task-input")
        date = request.form.get("deadline-input")

        if not task or not date:
            flash("Please enter both task and deadline")
            return redirect(url_for("dashboard"))

        try:
            datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            flash("Invalid date format. Please use YYYY-MM-DD")
            return redirect(url_for("dashboard"))

        task_data = Tasks(email=email, task=task, date=date)
        db.session.add(task_data)
        db.session.commit()
        return redirect(url_for("dashboard"))
    return redirect(url_for("dashboard"))

@app.route("/delete/<int:id>", methods=["POST"])
@login_required
def deleteFunction(id):
    task = db.session.get(Tasks, id)
    if task:
        db.session.delete(task)
        db.session.commit()
        return jsonify({"success": True})
    else:
        return jsonify({"success": False})

@app.route("/prioritize/<int:id>", methods=["POST"])
@login_required
def prioritizeFunction(id):
    task = db.session.get(Tasks, id)
    if task:
        task.priority = not task.priority
        db.session.commit()
        return jsonify({"success": True})
    else:
        return jsonify({"success": False})

@app.route("/complete/<int:id>", methods=["POST"])
@login_required
def completeFunction(id):
    task = db.session.get(Tasks, id)
    if task:
        task.completed = not task.completed
        db.session.commit()
        return jsonify({"success": True})
    else:
        return jsonify({"success": False})

@app.route("/upload_pdf", methods=["GET", "POST"])
@login_required
def upload_pdf():
    if request.method == "POST":
        if 'pdf' not in request.files:
            flash("No file part")
            return redirect(url_for("dashboard"))

        file = request.files['pdf']
        if file.filename == '':
            flash("No selected file")
            return redirect(url_for("dashboard"))

        if file and file.filename.endswith('.pdf'):
            filename = secure_filename(file.filename)
            user_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(current_user.id))
            if not os.path.exists(user_folder):
                os.makedirs(user_folder)
            filepath = os.path.join(user_folder, filename)
            file.save(filepath)

            if len(current_user.pdfs) >= 3:
                flash("You can only upload up to 3 PDFs")
                os.remove(filepath)
                return redirect(url_for("dashboard"))

            pdf = PDF(user_id=current_user.id, filename=filename, filepath=filepath)
            db.session.add(pdf)
            db.session.commit()

            flash("PDF uploaded successfully")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid file format. Please upload a PDF file.")
            return redirect(url_for("dashboard"))

    return redirect(url_for("dashboard"))

@app.route("/delete_pdf/<int:id>", methods=["POST"])
@login_required
def delete_pdf(id):
    pdf = db.session.get(PDF, id)
    if pdf and pdf.user_id == current_user.id:
        os.remove(pdf.filepath)
        db.session.delete(pdf)
        db.session.commit()
        return jsonify({"success": True})
    else:
        return jsonify({"success": False})

@app.route("/view_pdf/<int:id>")
@login_required
def view_pdf(id):
    pdf = db.session.get(PDF, id)
    if pdf and pdf.user_id == current_user.id:
        return send_from_directory(os.path.dirname(pdf.filepath), pdf.filename)
    else:
        flash("Unauthorized access")
        return redirect(url_for("dashboard"))

@app.route("/upload_profile_image", methods=["POST"])
@login_required
def upload_profile_image():
    if 'profileImageInput' not in request.files:
        flash("No file part")
        return redirect(url_for("dashboard"))

    file = request.files['profileImageInput']
    if file.filename == '':
        flash("No selected file")
        return redirect(url_for("dashboard"))

    if file and file.filename.endswith(('.png', '.jpg', '.jpeg')):
        filename = secure_filename(file.filename)
        user_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(current_user.id))
        if not os.path.exists(user_folder):
            os.makedirs(user_folder)
        filepath = os.path.join(user_folder, filename)
        file.save(filepath)

        current_user.profile_image = filename
        db.session.commit()

        flash("Profile image uploaded successfully")
        return redirect(url_for("dashboard"))
    else:
        flash("Invalid file format. Please upload an image file.")
        return redirect(url_for("dashboard"))

@app.route("/profile_image/<filename>")
@login_required
def profile_image(filename):
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(current_user.id))
    return send_from_directory(user_folder, filename)

def role_required(role):
    def decorator(func):
        @wraps(func)
        def wrap(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role != role:
                flash("Unauthorized Access")
                return redirect(url_for("login"))
            return func(*args, **kwargs)
        return wrap
    return decorator

@app.route("/admin")
@login_required
@role_required("admin")
def admin():
    users_data = User.query.filter_by(role="user").all()
    return render_template("admin.html", users=users_data)

@app.route("/deleteUsers/<int:id>")
@login_required
@role_required("admin")
def deleteUsers(id):
    user_data = User.query.filter_by(id=id).first()
    task_data = Tasks.query.filter_by(email=user_data.email).all()
    db.session.delete(user_data)
    for i in task_data:
        db.session.delete(i)
    db.session.commit()
    return redirect(url_for("admin"))

with app.app_context():
    inspector = inspect(db.engine)
    if 'users' in inspector.get_table_names():
        columns = inspector.get_columns('users')
        if not any(column['name'] == 'profile_image' for column in columns):
            with db.engine.connect() as connection:
                connection.execute(text('ALTER TABLE users ADD COLUMN profile_image VARCHAR(255) DEFAULT "default.jpg"'))

    db.create_all()
    if not User.query.filter_by(role="admin").first():
        admin = User(username="admin", email="admin@gmail.com", role="admin")
        admin.set_password("admin")
        db.session.add(admin)
        db.session.commit()

if __name__ == "__main__":
    app.run(debug=True)
