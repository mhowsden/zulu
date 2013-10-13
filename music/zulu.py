from flask import Flask, render_template, request, g, flash, redirect, url_for
from sqlite3 import dbapi2 as sqlite3
from urlparse import urlparse

app = Flask(__name__)

# Load default config and override config from an environment variable
app.config.update(dict(
    DATABASE='/tmp/zulu.db',
    DEBUG=True
))
app.config.from_envvar('ZULU_SETTINGS', silent=True)

def connect_db():
    """Connects to the specific database."""
    rv = sqlite3.connect(app.config['DATABASE'])
    rv.row_factory = sqlite3.Row
    return rv

def init_db():
    """Creates the database tables."""
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()

def get_db():
    """Opens a new database connection if there is none yet for the
    current application context.
    """
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db()
    return g.sqlite_db

@app.teardown_appcontext
def close_db(error):
    """Closes the database again at the end of the request."""
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()

@app.route("/")
def index():
    # query the database for all entries
    # get all entries descending by creation date
    db = get_db()
    cur = db.execute('select title, url from entries order by id desc')
    entries = cur.fetchall()
    return render_template("index.html", entries=entries)

@app.route('/add', methods=['POST'])
def add_entry():
    # validating the url is from youtube before allowing anything to be submitted
    if request.form.has_key('url'):
        url = urlparse(request.form['url'])
        if url.hostname == 'www.youtube.com':
            db = get_db()
            db.execute('insert into entries (title, url, artist) values (?, ?, ?)',
                       [request.form['title'], request.form['url'], request.form['artist']])
            db.commit()
        #flash('New entry was successfully posted')
    return redirect(url_for('index'))


if __name__ == "__main__":
    app.run()


