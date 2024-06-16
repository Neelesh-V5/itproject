import os
import re
import sqlite3
import pandas as pd
import json

from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps

app = Flask(__name__)

app.config["TEMPLATES_AUTO_RELOAD"] = True

app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/1.0/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

def create_tables():
    sql_statements = [
        """
            PRAGMA foreign_keys = ON;
        """,
        """
          CREATE TABLE IF NOT EXISTS user(
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT NOT NULL UNIQUE,
            age INTEGER NOT NULL
          );            
        """,
        """
            CREATE TABLE IF NOT EXISTS songs(
              id INTEGER PRIMARY KEY,
              title TEXT NOT NULL,
              link TEXT NOT NULL
            );
        """,
        """
            CREATE TABLE IF NOT EXISTS ratings(
              id INTEGER PRIMARY KEY,
              user_id INTEGER NOT NULL,
              song_id INTEGER NOT NULL,
              rating REAL NOT NULL,
              FOREIGN KEY (user_id) REFERENCES user(id),
              FOREIGN KEY (song_id) REFERENCES songs(id)
            );
        """
    ]

    try:
        with sqlite3.connect('harm.db') as conn:
            cursor = conn.cursor()
            for statement in sql_statements:
                cursor.execute(statement)

    except sqlite3.Error as e:
        print(e)


create_tables()
connection = sqlite3.connect("harm.db",check_same_thread=False)
cursor = connection.cursor()


def update_songs():
    df = pd.read_csv('songs.csv')
    records = df.to_dict(orient = "records")
    for record in records:
        if (cursor.execute("SELECT * FROM songs WHERE id = ?", (record['id'],)).fetchall()):
            pass
        else:
            data = ( record['title'], record['link'])
            cursor.execute('''

              INSERT INTO songs (title, link) VALUES (?,?)

            ''', data)
            connection.commit()

# update_songs()


@app.route("/")
def index():
    print("index")
    update_songs()
    return render_template("index.html", logged_in = session.get("user_id") != None)

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST": 
        user_attr = ["username", "password", "name", "email", "phone", "age"]
        for attr in user_attr:
            if not request.form.get(attr):
                return f"Must proive {attr}"
        if not request.form.get("password") == request.form.get("confirmation"):
            return "Passwords don't match"

        rows = cursor.execute("SELECT * FROM user")
        for row in rows:
            print(row)
            if row[1] == request.form.get("username"):
                return "User already exists"
        phash = generate_password_hash(request.form.get("password"), method="pbkdf2:sha256", salt_length=8)
        
        print(phash, request.form.get('username'))

        data = (request.form.get("username"),phash,request.form.get("name"),request.form.get("age"),request.form.get("email"),request.form.get("phone"))
        
        cursor.execute('''
                       INSERT INTO user(username, password, name, age, email, phone) VALUES(?, ?, ?, ?, ?, ?)
                       ''', data
        )
        connection.commit()

        return redirect("/login")

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    session.clear()
    if request.method == "POST":
        if not request.form.get("username"):
            return "Must provide username"
        elif not request.form.get("password"):
            return "Must provied password"
        
        rows = cursor.execute("SELECT * FROM user").fetchall()
        
        cont = 0
        req_id = -1
        req_row = []
        for row in rows:
            if row[1] == request.form.get('username'):
                cont = 1       
                req_id = row[0]
                req_row = row
                print(request.form.get('username'), req_id)
                break

        if cont == 0 or not check_password_hash(req_row[2], request.form.get("password")):
            return "Invalid username or password"
        
        session["user_id"] = req_id
        
        return redirect("/")
    
    else:
        return render_template("login.html")
    


@app.route("/logout")
@login_required
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/search", methods = ["GET", "POST"])
def search():
    if request.method == "GET" or request.method == "POST":
        return render_template("search.html")
    
@app.route("/query")
def query():
        q = request.args.get("q")
        songs = cursor.execute('''
                SELECT * FROM songs WHERE title LIKE ? LIMIT 25
                ''',('%'+q+'%',)).fetchall()
        obj = []
        for result in songs:
          avg = cursor.execute('''
            SELECT avg(rating) FROM ratings WHERE song_id = ?
          ''', (result[0],)).fetchone()[0]
          obj.append({'id': result[0], 'title' : result[1], 'link' : result[2], 'avg' : avg})
        
        print(obj)
        
        if q == "":
            return jsonify([])
        
        return jsonify(obj)
    
@app.route('/rate', methods=["GET","POST"])
@login_required
def rate():
    songs = cursor.execute('''
            SELECT * FROM songs;
        ''').fetchall()
    obj = []
    your_rating = ["NA",]
    for result in songs:
        
        if cursor.execute("SELECT rating FROM ratings WHERE user_id = ? AND song_id = ?",(session["user_id"],result[0])).fetchall():
            your_rating = cursor.execute("SELECT rating FROM ratings WHERE user_id = ? AND song_id = ?",(session["user_id"],result[0])).fetchall()[0]
            obj.append({'id': result[0], 'title' : result[1], 'link' : result[2], 'user_rating' : your_rating[0]})
        else:
            obj.append({'id': result[0], 'title' : result[1], 'link' : result[2], 'user_rating' : "NA"})

    if request.method == "GET":    
        return render_template("rate.html", songs=obj)
    
    if request.method == "POST":
        scores = [0 for x in range (0, len(obj)+2)]
        
        for song in obj: 
            
            scores[song['id']] = request.form.get(f"score{song['id']}")
            do = [1 for x in range(0, len(obj)+2)]
            #if already rated
            if request.form.get(f"score{song['id']}"):
                rows = cursor.execute("SELECT * FROM ratings")
                for row in rows:
                    if row[1] == session["user_id"] and row[2] == song['id']:
                        data = (scores[song['id']], session["user_id"], song['id'])
                        if int(scores[song['id']]) > 0:
                            cursor.execute('''
                            UPDATE ratings SET rating = ? WHERE user_id = ? AND song_id = ?

                            ''', data)
                            do[song['id']] = 0
                            connection.commit()
            if do[song['id']] == 1:
                score = 0
                if request.form.get(f"score{song['id']}"):
                    score = scores[song['id']]
                    data = ( session["user_id"], song['id'], score)
                    if score != 0:
                        cursor.execute('''

                 INSERT INTO ratings (user_id, song_id, rating) VALUES (?,?,?)

                 ''', data)
                        connection.commit()

        return redirect('/recommend')
    
@app.route('/recommend')
@login_required
def recommend():
    songs = cursor.execute('''
            SELECT * FROM songs;
        ''').fetchall()
    obj = []
    your_rating = list(["NA",])
    
    for result in songs:
      avg = cursor.execute('''
            SELECT avg(rating) FROM ratings WHERE song_id = ?
          ''', (result[0],)).fetchone()[0]
      
      if cursor.execute("SELECT rating FROM ratings WHERE user_id = ? AND song_id = ?",(session["user_id"],result[0])).fetchall():
        your_rating = cursor.execute("SELECT rating FROM ratings WHERE user_id = ? AND song_id = ?",(session["user_id"],result[0])).fetchall()[0]
        obj.append({'id': result[0], 'title' : result[1], 'link' : result[2], 'avg' : avg, 'user_rating' : your_rating[0]})
      else:
        obj.append({'id': result[0], 'title' : result[1], 'link' : result[2], 'avg' : avg, 'user_rating' : 'NA'})
    
    def sortRate(song):
        if song['avg'] == None:
            return 0
        return song['avg']

    obj.sort(key=sortRate, reverse=True)
    print(obj)
    

    return render_template('recommend.html', songs = obj)

        