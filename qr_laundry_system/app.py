from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from datetime import datetime, timedelta
import pytz

app = Flask(__name__)
app.secret_key = "supersecretkey"
DATABASE = "laundry.db"

# ---------------- DATABASE INIT ----------------
def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bookings(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        mode TEXT,
        start_time TEXT,
        end_time TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS machine(
        id INTEGER PRIMARY KEY,
        status TEXT
    )
    """)

    cursor.execute("INSERT OR IGNORE INTO machine (id, status) VALUES (1, 'Working')")

    conn.commit()
    conn.close()

init_db()

# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        try:
            cursor.execute("INSERT INTO users (username,password) VALUES (?,?)", (username, password))
            conn.commit()
            conn.close()
            return redirect(url_for("login"))
        except:
            return "Username already exists!"

    return render_template("register.html")

# ---------------- LOGIN ----------------
@app.route("/")
def home():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session["username"] = username
            return redirect(url_for("index"))
        else:
            return "Invalid Credentials!"

    return render_template("login.html")

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect(url_for("login"))

# ---------------- INDEX ----------------
@app.route("/index")
def index():
    if "username" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM bookings ORDER BY id")
    bookings = cursor.fetchall()

    cursor.execute("SELECT status FROM machine WHERE id=1")
    machine_status = cursor.fetchone()[0]

    now = datetime.now()
    cursor.execute("SELECT end_time FROM bookings ORDER BY id DESC LIMIT 1")
    last = cursor.fetchone()

    if last:
        end_time = datetime.strptime(last[0], "%Y-%m-%d %H:%M:%S")
        usage_status = "Busy" if now < end_time else "Available"
    else:
        usage_status = "Available"

    conn.close()
    return render_template("index.html", bookings=bookings,
                           machine_status=machine_status,
                           usage_status=usage_status)

# ---------------- BOOK ----------------
@app.route("/book", methods=["POST"])
def book():
    if "username" not in session:
        return redirect(url_for("login"))

    mode = request.form.get("mode")
    if not mode:
        return redirect(url_for("index"))

    durations = {"Quick Wash": 10, "Normal Wash": 30, "Heavy Wash": 45}

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("SELECT status FROM machine WHERE id=1")
    status = cursor.fetchone()[0]

    if status == "Not Working":
        conn.close()
        return "Machine is not working!"

    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)

    cursor.execute("SELECT end_time FROM bookings ORDER BY id DESC LIMIT 1")
    last = cursor.fetchone()

    if last:
        last_end = datetime.strptime(last[0], "%Y-%m-%d %H:%M:%S")
        last_end = ist.localize(last_end)
        start_time = max(now, last_end)
    else:
        start_time = now

    duration = durations.get(mode, 10)
    end_time = start_time + timedelta(minutes=duration)

    cursor.execute("""
        INSERT INTO bookings (username, mode, start_time, end_time)
        VALUES (?,?,?,?)
    """, (session["username"], mode,
          start_time.strftime("%Y-%m-%d %H:%M:%S"),
          end_time.strftime("%Y-%m-%d %H:%M:%S")))

    conn.commit()
    conn.close()

    return redirect(url_for("index"))

# ---------------- CANCEL ----------------
@app.route("/cancel/<int:id>")
def cancel(id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM bookings WHERE id=?", (id,))
    conn.commit()

    cursor.execute("SELECT id, mode FROM bookings ORDER BY id")
    bookings = cursor.fetchall()

    durations = {"Quick Wash": 10, "Normal Wash": 30, "Heavy Wash": 45}

    ist = pytz.timezone('Asia/Kolkata')
    current_time = datetime.now(ist)

    for booking in bookings:
        booking_id = booking[0]
        mode = booking[1]

        start_time = current_time
        end_time = start_time + timedelta(minutes=durations.get(mode, 10))

        cursor.execute("""
            UPDATE bookings SET start_time=?, end_time=? WHERE id=?
        """, (start_time.strftime("%Y-%m-%d %H:%M:%S"),
              end_time.strftime("%Y-%m-%d %H:%M:%S"),
              booking_id))

        current_time = end_time

    conn.commit()
    conn.close()

    return redirect(url_for("index"))

# ---------------- TOGGLE MACHINE ----------------
@app.route("/toggle_machine")
def toggle_machine():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("SELECT status FROM machine WHERE id=1")
    current = cursor.fetchone()[0]

    new_status = "Not Working" if current == "Working" else "Working"

    cursor.execute("UPDATE machine SET status=? WHERE id=1", (new_status,))
    conn.commit()
    conn.close()

    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)

  
