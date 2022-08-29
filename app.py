import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
import datetime
from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/", methods=["GET"])
@login_required
def index():
    total_stock = 0
    """Show portfolio of stocks"""
    portfolio = db.execute(
        "SELECT * FROM portfolio WHERE portfolio.id=?", session["user_id"])
    users = db.execute(
        "SELECT * FROM USERS WHERE users.id=?", session["user_id"])
    for p in portfolio:
        total_stock += p["total"]
        new_info = lookup(p["symbol"])
        db.execute("UPDATE portfolio SET price=?,total=price*shares WHERE symbol=? and id=?",
                   new_info["price"], new_info["symbol"], session["user_id"])

    portfolio = db.execute(
        "SELECT * FROM portfolio WHERE portfolio.id=?", session["user_id"])
    for p in portfolio:
        print(p)
    return render_template("index.html", portfolio=portfolio, users=users, total_stock=total_stock)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        if shares.isnumeric():
            shares = int(shares)
        else:
            return apology("Only integers")
        if not lookup(symbol) and shares:
            return apology("Invalid symbol")
        elif not shares and not symbol:
            return apology("Missing shares and symbol")
        elif lookup(symbol) and not shares:
            return apology("Missing shares")
        elif not lookup(symbol) and not shares:
            return apology("Invalid symbol and missing shares")
        elif not lookup(symbol) or shares == 0:
            return apology("Type only integer shares")
        else:
            info = lookup(symbol)
            rows = db.execute(
                "SELECT * FROM portfolio WHERE id=? and symbol=?", session["user_id"], symbol)
            user = db.execute(
                "SELECT * FROM users WHERE id=?", session["user_id"])[0]

            for row in rows:
                print((user["cash"]-(info["price"]*int(shares))))
                print(row["id"], session["user_id"])
                if row["symbol"] == info["symbol"] and row["id"] == session["user_id"] and (user["cash"]-(info["price"]*int(shares))) >= 0:
                    time = f"{datetime.datetime.now().year}-{datetime.datetime.now().month}-{datetime.datetime.now().day} {datetime.datetime.now().hour}:{datetime.datetime.now().minute}:{datetime.datetime.now().second}"
                    db.execute("UPDATE portfolio SET shares=shares+?,total=total+(?),datetime=? WHERE symbol=? and id=?",
                               shares, info["price"]*int(shares), time, info["symbol"], session["user_id"])
                    db.execute("INSERT INTO history (id,symbol,shares,price,transacted) VALUES (?,?,?,?,?)",
                               session["user_id"], info["symbol"], shares, info["price"], time)
                    return redirect("/")
                else:
                    return apology("Not enough cash")
            if (float(user["cash"])-float(info["price"]*int(shares))) >= 0:
                time = f"{datetime.datetime.now().year}-{datetime.datetime.now().month}-{datetime.datetime.now().day} {datetime.datetime.now().hour}:{datetime.datetime.now().minute}:{datetime.datetime.now().second}"
                db.execute("INSERT INTO portfolio (id,symbol,shares,price,total,name,datetime) VALUES(?,?,?,?,?,?,?)",
                           session["user_id"], info["symbol"], shares, info["price"], info["price"]*int(shares), info["name"], time)
                db.execute("UPDATE users SET cash=cash-(?) WHERE id=?",
                           info["price"]*int(shares), session["user_id"])
                db.execute("INSERT INTO history (id,symbol,shares,price,transacted) VALUES (?,?,?,?,?)",
                           session["user_id"], info["symbol"], shares, info["price"], time)
                return redirect("/")
            else:
                return apology("Not enough cash")
    else:
        return render_template("buy.html")


@app.route("/history", methods=["GET"])
@login_required
def history():
    if request.method == "GET":
        history = db.execute(
            "SELECT * FROM history WHERE id=?", session["user_id"])
        return render_template("history.html", history=history)
    """Show history of transactions"""


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?",
                          request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        quote = request.form.get("symbol")
        if not lookup(quote):
            return apology("Symbol not found")
        else:
            info = lookup(quote)
            info["price"] = usd(info["price"])
            return render_template("quoted.html", info=info)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        password_corr = request.form.get("confirmation")
        print(password, password_corr)
        if not username or not password or not password_corr:
            print('here')
            return apology("Fill the form again")

        elif password != password_corr:
            return apology("Passwords are not the same")
        elif db.execute("SELECT username FROM users WHERE username = ?", username):
            return apology("There is a user with the same username")

        db.execute("INSERT INTO users (username,hash) VALUES (?,?)",
                   username, generate_password_hash(password))
        rows = db.execute("SELECT * FROM users WHERE username=?", username)
        session["user_id"] = rows[0]["id"]
        return redirect("/")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    symbol = request.form.get("symbol")
    shares = request.form.get("shares")
    print(symbol, shares)
    portfolio = db.execute(
        "SELECT * FROM portfolio WHERE portfolio.id=? AND portfolio.symbol=?", session["user_id"], symbol)

    all_p = db.execute("SELECT * FROM portfolio WHERE portfolio.id=?",
                       session["user_id"])
    if request.method == "POST":
        for p in portfolio:
            print((not shares or shares), "lol")
            if symbol == None and (not shares or shares):
                print('here')
                return apology("Choose stock to sell")
            elif symbol == "Symbol" and (not shares or shares):
                return apology("Choose stock to sell")
            elif symbol == p["symbol"] and not shares:
                return apology("Choose shares to sell")
            elif symbol != p["symbol"] and (not shares or shares):
                return apology("You don't have this stock")
            elif symbol == p["symbol"] and int(p["shares"])-int(shares) > 0:
                print("HERE HERE  HERE")
                time = f"{datetime.datetime.now().year}-{datetime.datetime.now().month}-{datetime.datetime.now().day} {datetime.datetime.now().hour}:{datetime.datetime.now().minute}:{datetime.datetime.now().second}"
                db.execute("UPDATE portfolio SET shares=?,total=price*?,datetime=? WHERE symbol=? and id=?",
                           int(p["shares"])-int(shares), int(p["shares"])-int(shares), time, symbol, session["user_id"])
                db.execute("UPDATE users SET cash=cash+? WHERE id=?",
                           float(p["price"])*int(shares), session["user_id"])
                db.execute("INSERT INTO history (id,symbol,shares,price,transacted) VALUES (?,?,?,?,?)",
                           session["user_id"], p["symbol"], int(shares)*(-1), p["price"], time)
            elif symbol == p["symbol"] and int(p["shares"])-int(shares) < 0:
                return apology("You don't have enough shares")
            elif symbol == p["symbol"] and int(p["shares"])-int(shares) == 0:
                time = f"{datetime.datetime.now().year}-{datetime.datetime.now().month}-{datetime.datetime.now().day} {datetime.datetime.now().hour}:{datetime.datetime.now().minute}:{datetime.datetime.now().second}"
                db.execute(
                    "DELETE FROM portfolio WHERE symbol=? and id=?", symbol, session["user_id"])
                db.execute("UPDATE users SET cash=cash+? WHERE id=?",
                           p["total"], session["user_id"])
                print(int(shares)*(-1))
                db.execute("INSERT INTO history (id,symbol,shares,price,transacted) VALUES (?,?,?,?,?)",
                           session["user_id"], p["symbol"], int(shares)*(-1), p["price"], time)

        return redirect("/")
    else:
        return render_template("sell.html", all_p=all_p)
    """Sell shares of stock"""
