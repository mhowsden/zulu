import time
from datetime import datetime
from flask import Flask, render_template, request, g, flash, redirect, url_for
from sqlite3 import dbapi2 as sqlite3
from urlparse import urlparse, parse_qs

app = Flask(__name__)

# Load default config and override config from an environment variable
app.config.update(dict(
    DATABASE='/tmp/zulu.db'
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

def derive_embedcode(url):
    parsed = urlparse(url)
    query_dict = parse_qs(parsed.query)
    if 'v' in query_dict:
        youtube_id = query_dict['v'][0]
        embed_code = """<iframe width="560" height="315" 
        data-src="//www.youtube.com/embed/%s" frameborder="0"
         allowfullscreen></iframe>"""
    else:
        embed_code = None
    return embed_code % youtube_id

def format_timestamp(sqlite_date):
    if sqlite_date:
        return datetime.fromtimestamp(int(sqlite_date))
    else:
        return ""

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
    try:
        cur = db.execute('select * from entries order by id desc')
    except sqlite3.OperationalError:
        # this should only happen the first time the db is used
        init_db()
        cur = db.execute('select * from entries order by id desc')
    db_entries = cur.fetchall()

    entries = []
    for e in db_entries:
        de = dict(e)
        de['embed_code'] = derive_embedcode(e['url'])
        de['created_at'] = format_timestamp(e['created_at'])
        entries.append(de)
    return render_template("index.html", entries=entries)

@app.route('/add', methods=['POST'])
def add_entry():
    # validating the url is from youtube before allowing anything to be submitted
    if request.form.has_key('url'):
        db = get_db()
        # check to see if the url has been posted yet
        cur = db.execute('SELECT * FROM entries WHERE url = ?', [request.form['url']])
        db_entries = cur.fetchall()
        if len(db_entries) > 0:
            return redirect(url_for('index'))
        url = urlparse(request.form['url'])
        if url.hostname == 'www.youtube.com':
            db.execute(
                'INSERT INTO entries (title, url, artist, created_at, genre) VALUES (?, ?, ?, ?, ?)',
                [request.form['title'], request.form['url'], 
                 request.form['artist'], time.time(), request.form['genre']])
            db.commit()
        #flash('New entry was successfully posted')
    return redirect(url_for('index'))


if __name__ == "__main__":
    app.run()


