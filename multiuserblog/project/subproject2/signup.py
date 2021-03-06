import os

import re
from string import letters

import jinja2
import webapp2
import string
import re
import random

from google.appengine.ext import db

import hashlib
import hmac

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
                               autoescape = True)


USER_RE = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")
def valid_username(username):
    return username and USER_RE.match(username)

PASS_RE = re.compile(r"^.{3,20}$")
def valid_password(password):
    return password and PASS_RE.match(password)

EMAIL_RE  = re.compile(r'^[\S]+@[\S]+\.[\S]+$')
def valid_email(email):
    return not email or EMAIL_RE.match(email)


SECRET ="donot"
def hash_str(s):
    return hmac.new(SECRET, s).hexdigest()

def make_secure_val(s):
    return "%s|%s" % (s, hash_str(s))

def check_secure_val(h):
    a= h.split("|")[0]
    if (h==make_secure_val(a)):
        return a

COOKIE_RE = re.compile(r'.+=;\s*Path=/')
def valid_cookie(cookie):
    return cookie and COOKIE_RE.match(cookie)


def make_salt():
    return "".join(random.choice(string.letters) for x in xrange(5))

def make_pw_hash(name, pw, salt=None):
    if not salt:
        salt = make_salt()
    h = hashlib.sha256(name+pw+salt).hexdigest()
    return "%s,%s" % (h, salt)

def valid_pw(name, pw, h):
    salt=h.split(",")[1]
    return h == make_pw_hash(name, pw, salt)


def user_key(group = 'default'):
    return db.Key.from_path('users', group)

def render_str(template, **params):
    t = jinja_env.get_template(template)
    return t.render(params)

class Userinfo(db.Model):
    username = db.StringProperty(required = True)
    password = db.StringProperty(required = True) #not regular password but hash of the password
    email = db.EmailProperty()

    def render(self):
        self._render_text = self.email.replace('\n', '<br>')
        return render_str("post.html", p = self)

    # if you want to work on above created class instead of creating instances, we can use this method
    # @classmethod is called decorator
    @classmethod
    def by_id(cls, uid):
        return Userinfo.get_by_id(uid, parent = user_key())

    @classmethod
    def by_name(cls, username):
        u = Userinfo.all().filter('username =', username).get()
        return u

    @classmethod
    def register(cls, username, password, email =None):
        pw_hash = make_pw_hash(username, password)
        return Userinfo(parent = user_key(),
                        username = username,
                        password = pw_hash,
                        email = email)

    @classmethod
    def login(cls, username, password):
        u = cls.by_name(username)
        if u and valid_pw(username, password, u):
            return u


class Handler(webapp2.RequestHandler):
    def write(self, *a, **kw):
        self.response.write(*a,**kw)

    def render_str(self, template, **params):
        t = jinja_env.get_template(template)
        return t.render(params)

    def render(self, template, **kw):
        self.write(self.render_str(template, **kw))

    def setting_cookies(self, name, val):
        new_cookie_val = make_secure_val(val)
        self.response.headers.add_header('Set-Cookie', '%s=%s; path=/' % (name, new_cookie_val))

    def reading_cookies(self,name):
        cookie_val = self.request.cookies.get(name)
        return cookie_val and check_secure_val(cookie_val)

    def login(self, user):
        self.setting_cookies('user_id', str(user.key().id()))

    def logout(self):
        self.response.headers.add_header('Set-Cookie', 'user_id=; path=/')


class SignUp(Handler):
    def get(self):
        self.render("homepage.html")

    def post(self):
        have_error = False
        username = self.request.get('username')
        password = self.request.get('password')
        verify = self.request.get('verify')
        email = self.request.get('email')

        params = dict(username = username,
                      email = email)

        if not valid_username(username):
            params['error_username'] = "That's not a valid username."
            have_error = True

        if not valid_password(password):
            params['error_passwordord'] = "That wasn't a valid passwordord."
            have_error = True
        elif (password != verify):
            params['error_verify'] = "Your passwords didn't match."
            have_error = True

        if not valid_email(email):
            params['error_email'] = "That's not a valid email."
            have_error = True

        if have_error:
            self.render('homepage.html', **params)
        else:
            ## add cookies
            check_user_exist = Userinfo.by_name(username)
            if check_user_exist:
                self.render('homepage.html', error_username = "That user already exists")
            else:
                uinfo = Userinfo.register(username, password , email)
                uinfo.put()

                self.login(uinfo)
                self.redirect('/welcome?username=' + username)


class Front(Handler):
    def get(self):
        self.render('firstpage.html')


class LogIn(Handler):
    def get(self):
        self.render('login.html')

    def post(self):
        username = self.request.get('username')
        password = self.request.get('password')
        data = db.GqlQuery("select * from Userinfo")

        for i in data:
            pass_val=0
            u_value=0
            if i.username == username:
                h = i.password
                if valid_pw(username, password, h):
                    return self.render("welcome.html",username=username)
                else:
                    return self.render("login.html",error_password="password is wrong")
            else:
                u_value=1

        if u_value==1:
            self.render("login.html",error_username="username does not exist")


class LogOut(Handler):
    def get(self):
        self.logout()
        self.redirect('/signup')


class Welcome(Handler):
    def get(self):
        #username =
        user_id = self.reading_cookies('user_id')
        user_name = user_id and Userinfo.by_id(int(user_id))
        if user_name:
            self.render("welcome.html",username=user_id)
        else:
            self.redirect('/signup')


app = webapp2.WSGIApplication([('/signup', SignUp),
                               ('/login', LogIn),
                               ('/?', Front),
                               ('/logout', LogOut),
                               ('/welcome',Welcome)], debug=True)


## to delete all data from database
# dev_appserver.py --clear_datastore=yes /home/bittu/Documents/github/Udacity/multiuserblog/project/subproject/
