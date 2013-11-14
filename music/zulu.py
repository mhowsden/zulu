# built-in
import time
import json
import logging
from datetime import datetime
from sqlite3 import dbapi2 as sqlite3
from urlparse import urlparse, parse_qs

# third party
from flask import Flask, render_template, request, g, flash, redirect, url_for, abort
import requests

app = Flask(__name__)

# Load default config and override config from an environment variable
app.config.update(dict(
    DATABASE='/tmp/zulu.db'
))
#app.config.from_envvar('ZULU_SETTINGS', silent=True)
app.config.from_pyfile('config.zulu')

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
    if parsed.hostname == "www.youtube.com" and 'v' in query_dict:
        video_id = query_dict['v'][0]
        embed_code = """<iframe width="560" height="315"
        data-src="//www.youtube.com/embed/%s" frameborder="0"
         allowfullscreen></iframe>"""
        return embed_code % video_id
    elif parsed.hostname.endswith('bandcamp.com') and 'embed_id' in query_dict:
        video_id = query_dict['embed_id'][0]
        track_id = query_dict['track_id'][0]
        embed_code = """<iframe style="border: 0; width: 350px; height: 470px;"
        data-src="http://bandcamp.com/EmbeddedPlayer/album=%s/size=large/bgcol=333333/linkcol=e99708/notracklist=true/t=%s/transparent=true/" seamless></iframe>"""
        return embed_code % (video_id, track_id)
    elif parsed.hostname.endswith('soundcloud.com'):
        embed_code = '<iframe width="100%%" height="166" scrolling="no" frameborder="no" data-src="%s"></iframe>'
        return embed_code % parsed.geturl()
    else:
        return ""

def derive_bandcamp_url(url):
    r = requests.get(url)
    if r.ok:
        c = r.content
        # parsing for embed code id
        block_start = c.find('tralbum_param')
        blob = c[block_start:block_start+300]
        embed_id = blob.split('value : ')[1].split(' }')[0]
        track_id = blob.split('t : ')[1].split(',\n')[0]
        return urlparse("%s?embed_id=%s&track_id=%s" % (url, embed_id, track_id))
    else:
        return None

def derive_soundcloud_url(url):
    r = requests.get("http://soundcloud.com/oembed/?format=json&url=%s" % url)
    if r.ok:
        j = r.json()
        return urlparse(j['html'].split("src=\"")[1].split('"></iframe>')[0])
    else:
        return None


def format_timestamp(sqlite_date):
    if sqlite_date:
        return datetime.fromtimestamp(int(sqlite_date))
    else:
        return ""

def get_songs(tag_name=None):
    db = get_db()
    if tag_name:
        cur = db.execute('SELECT * FROM entries WHERE ID IN (SELECT entry_id FROM tags WHERE name=(?)) ORDER BY id DESC', [tag_name])
    else:
        cur = db.execute('SELECT * FROM entries ORDER BY id DESC')
    db_entries = cur.fetchall()
    entries = []
    for e in db_entries:
        de = dict(e)
        de['embed_code'] = derive_embedcode(e['url'])
        de['created_at'] = format_timestamp(e['created_at'])
        entries.append(de)
    return entries

@app.teardown_appcontext
def close_db(error):
    """Closes the database again at the end of the request."""
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()

@app.route("/tag/<tag_name>")
def tag(tag_name):
    songs = get_songs(tag_name)
    if not songs:
        abort(404)
    return render_template("tag.html", entries=songs, tag_list=[])

@app.route("/")
def index():
    # query the database for all entries
    # get all entries descending by creation date
    db = get_db()
    try:
        cur = db.execute('SELECT * FROM entries ORDER BY id DESC')
    except sqlite3.OperationalError:
        # this should only happen the first time the db is used
        # init_db() ### this should be moved outside the app
        cur = db.execute('SELECT * FROM entries ORDER BY id DESC')
    db_entries = cur.fetchall()

    entries = []
    for e in db_entries:
        de = dict(e)
        # stripping GET params for bandcamp urls
        if urlparse(e['url']).hostname.endswith('bandcamp.com'):
            de['url'] = e['url'].split('?')[0]
        de['embed_code'] = derive_embedcode(e['url'])
        de['created_at'] = format_timestamp(e['created_at'])
        entries.append(de)
    cur = db.execute('SELECT DISTINCT name, sum(CASE WHEN name=name THEN 1 END) as ncount FROM tags GROUP BY name')
    db_tags = cur.fetchall()
    tags = {}
    for t in db_tags:
        tags[t[0]] = t[1] + 10
    return render_template("index.html", entries=entries, tags=tags,
                           tag_list=json.dumps(tags.keys()))

@app.route('/add', methods=['POST'])
def add_entry():
    # validating the url before allowing anything to be submitted
    url = urlparse(request.form['url'])
    if url.hostname:
        db = get_db()
        # check to see if the url has been posted yet
        cur = db.execute('SELECT * FROM entries WHERE url = ?', [request.form['url']])
        db_entries = cur.fetchall()
        if len(db_entries) > 0:
            return redirect(url_for('index'))
        if url.hostname == 'www.youtube.com' or url.hostname.endswith('bandcamp.com') or \
                url.hostname.endswith('soundcloud.com'):
            # validating bandcamp url
            if url.hostname.endswith('bandcamp.com'):
                url = derive_bandcamp_url(url.geturl())
                if not url:
                    return redirect(url_for('index'))
            # validating soundcloud url
            if url.hostname.endswith('soundcloud.com'):
                url = derive_soundcloud_url(url.geturl())
                if not url:
                    return redirect(url_for('index'))
            cur = db.execute(
                'INSERT INTO entries (title, url, artist, created_at) VALUES (?, ?, ?, ?)',
                [request.form['title'], url.geturl(),
                 request.form['artist'], time.time()])
            db.commit()
            entry_id = cur.lastrowid
            # adding tagging to the entry, using crappy ip based validation
            # this is for the nginx proxied case, could be spoofed
            if not request.headers.getlist("X-Real-IP"):
                ip = request.remote_addr
            else:
                ip = request.headers.getlist("X-Real-IP")[0]
            if 'ALLOWED_IPS' in app.config and ip in app.config['ALLOWED_IPS']:
                # user can add new tags
                for tag_name in request.form['tags'].split(','):
                    db.execute('INSERT INTO tags (name, entry_id) VALUES (?, ?)',
                               [tag_name, entry_id])
                    db.commit()
            else:
                # user can only add existing tags
                cur = db.execute('SELECT DISTINCT name FROM tags')
                current_tags = [t[0] for t in cur.fetchall()]
                for tag_name in request.form['tags'].split(','):
                    if tag_name in current_tags:
                        db.execute('INSERT INTO tags (name, entry_id) VALUES (?, ?)',
                                   [tag_name, entry_id])
                        db.commit()
            # update the main list of videos with the secret header
            # if it exists in the config file, this is for nginx
            if 'SECRET_HEADER' and 'SITE_URL' in app.config:
                r = requests.get(app.config['SITE_URL'],
                                 headers={app.config['SECRET_HEADER']:1})
                if r.status_code != requests.codes.ok:
                    abort(500)
            if 'HIPCHAT_ROOM_ID' and 'HIPCHAT_ROOM_TOKEN' in app.config:
                headers = {'content-type': 'application/json'}
                params = {'auth_token':app.config['HIPCHAT_ROOM_TOKEN']}
                payload = {'message':request.form['url'],'notify':True,'message_format':'text'}
                r = requests.post('https://api.hipchat.com/v2/room/%s/notification' % app.config['HIPCHAT_ROOM_ID'],
                                  params=params,data=json.dumps(payload),headers=headers)
        #flash('New entry was successfully posted')

    return redirect(url_for('index'))


if __name__ == "__main__":
    if 'LOG_FILE' in app.config:
        logging.basicConfig(filename=app.config['LOG_FILE'], level=logging.INFO)
    app.run()
