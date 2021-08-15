from flask import Flask, render_template, request, flash, redirect, url_for, session, logging
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from wtforms import Form, StringField, TextAreaField, PasswordField, validators
from passlib.hash import sha256_crypt
from datetime import datetime
import json
import math
from functools import wraps
import pymysql
pymysql.install_as_MySQLdb()

local_server = True
with open('config.json', 'r') as c:
    params = json.load(c)["params"]

app = Flask(__name__)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config.update(
    MAIL_SERVER = 'smtp.gmail.com',
    MAIL_PORT ='465',
    MAIL_USE_SSL = True,
    MAIL_USERNAME='sd774430',
    MAIL_PASSWORD='&uperuser'
)
mail = Mail(app)

if local_server:
    app.config['SQLALCHEMY_DATABASE_URI'] = params['local_uri']
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = params['prod_uri']

db = SQLAlchemy(app)


class Contact(db.Model):
    sno = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phno = db.Column(db.String(12), nullable=False)
    message = db.Column(db.String(200), nullable=False)
    date = db.Column(db.DateTime)

class Posts(db.Model):
    sno = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(20), nullable=False)
    content = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(20), nullable=False)
    date = db.Column(db.DateTime)
    img_file = db.Column(db.String(12), nullable=True)

@app.route("/")
def home():
    posts = Posts.query.filter_by().all()
    last = math.ceil(len(posts)/int(params['no_of_posts']))
    page = request.args.get('page')
    if (not str(page).isnumeric()):
        page = 1
    page = int(page)
    posts = posts[(page-1)*int(params['no_of_posts']):(page-1)*int(params['no_of_posts'])+ int(params['no_of_posts'])]
    if page==1:
        prev = "#"
        next = "/?page="+ str(page+1)
    elif page==last:
        prev = "/?page="+ str(page-1)
        next = "#"
    else:
        prev = "/?page="+ str(page-1)
        next = "/?page="+ str(page+1)
    
    return render_template('index.html', params=params, posts=posts, prev=prev, next=next)

@app.route("/post/<string:post_slug>", methods=['GET'])
def post_route(post_slug):
    post = Posts.query.filter_by(slug=post_slug).first()
    return render_template('post.html', params=params, post=post)


@app.route('/contact', methods=['GET','POST'])
def contact():
    if (request.method == "POST"):
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        msg = request.form.get('message')
        entry = Contact(name=name, email=email, phno=phone, message=msg, date=datetime.now())
        db.session.add(entry)
        db.session.commit()
        mail.send_message('New Message from ' + name, 
                            sender=email, 
                            recipients=['satyajitdebnath87@gmail.com'], 
                            body=msg + "\n" + phone)
    return render_template('contact.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Get Form Fields
        username = request.form.get('username')
        password_candidate = request.form.get('password')

        # Get user by username
        result = User.query.filter_by(username=username).first()

        if result is not None:
            # Get stored hash
            password = result.password

            # Compare Passwords
            if sha256_crypt.verify(password_candidate, password):
                # Passed
                session['logged_in'] = True
                session['username'] = username

                flash('You are now logged in', 'success')
                return redirect(url_for('dashboard'))
            else:
                error = 'Invalid login'
                return render_template('login.html', error=error)
        else:
            error = 'Username not found'
            return render_template('login.html', error=error)

    return render_template('login.html')
def is_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            flash('Unauthorized, Please login', 'danger')
            return redirect(url_for('login'))
    return wrap

# Dashboard
@app.route('/dashboard')
@is_logged_in
def dashboard():
    
    # Get articles
    #result = posts.query.all()
    # Show articles only from the user logged in 
    posts = Posts.query.filter_by(author=session['username'])

    if posts is not None:
        return render_template('dashboard.html', posts=posts)
    else:
        msg = 'No Articles Found'
        return render_template('dashboard.html', msg=msg)

# Logout
@app.route('/logout')
@is_logged_in
def logout():
    session.clear()
    flash('You are now logged out', 'success')
    return redirect(url_for('login'))

# Article Form Class
class ArticleForm(Form):
    title = StringField('Title', [validators.Length(min=1, max=200)])
    body = TextAreaField('Body', [validators.Length(min=30)])

class User(db.Model):
    name = db.Column(db.String(25), primary_key=True)
    username = db.Column(db.String(25), nullable=False)
    email = db.Column(db.String(35), nullable=False)
    password = db.Column(db.String(200), nullable=False)

class RegisterForm(Form):
    name = StringField('Name', [validators.Length(min=4, max=24)])
    username = StringField('Username', [validators.Length(min=4, max=24)])
    email = StringField('Email Address', [validators.Length(min=6, max=35)])
    password = PasswordField('New Password', [
        validators.DataRequired(),
        validators.EqualTo('confirm', message='Passwords must match')
    ])
    confirm = PasswordField('Repeat Password')

@app.route('/register', methods=['GET','POST'])
def register():
    form = RegisterForm(request.form)
    if request.method == 'POST' and form.validate():
        name= form.name.data
        username= form.username.data
        email= form.email.data
        password= sha256_crypt.hash(str(form.password.data)) 
        values = User(name=name, username=username, email=email, password=password)
        db.session.add(values)
        db.session.commit()

        flash('You are now registered, Log in Continue', 'success')
    return render_template('register.html', form=form)

@app.route("/edit/<string:sno>" , methods=['GET', 'POST'])

def edit(sno):
    if session['logged_in']==True:
        print(type(sno))
        if request.method=="POST":
            print(sno)
            box_title = request.form.get('title')
            slug = request.form.get('slug')
            content = request.form.get('content')
            img_file = request.form.get('img_file')
            date = datetime.now()
            author = session['username']
            print(box_title, slug, content,img_file, date,author)
            if sno=='0':
                print(sno)
                post = Posts(title=box_title, slug=slug, content=content, img_file=img_file, date=date, author=author)
                db.session.add(post)
                db.session.commit()
                
            else:
                print(1)
                post = Posts.query.filter_by(sno=sno).first()
                post.box_title = box_title
                post.slug = slug
                post.content = content
                post.img_file = img_file
                post.date = date
                db.session.commit()
                return redirect('/edit/'+sno)

        post = Posts.query.filter_by(sno=sno).first()
        return render_template('edit.html', post=post, sno=sno)


# Delete Article
@app.route('/delete_article/<string:id>', methods=['POST'])
@is_logged_in
def delete_article(id):

    # Execute
    article = Posts.query.filter_by(sno=id).first()

    # Commit to DB
    db.session.delete(article)
    db.session.commit()

    flash('Article Deleted', 'success')

    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.secret_key = 'secret'
    app.run(debug=True)