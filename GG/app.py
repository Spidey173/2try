from flask import Flask, request, render_template, redirect, url_for, session, send_from_directory, jsonify
import os
import sqlite3
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import mutagen

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['UPLOAD_FOLDER'] = 'static/songs'
app.config['COVER_FOLDER'] = 'static/covers'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['COVER_FOLDER'], exist_ok=True)

def init_db():
    with sqlite3.connect('admin.db') as conn:
        conn.executescript('''
        CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            artist TEXT NOT NULL,
            filename TEXT NOT NULL,
            cover_filename TEXT,
            duration INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            type TEXT CHECK(type IN ('language', 'genre')) NOT NULL
        );
        CREATE TABLE IF NOT EXISTS song_categories (
            song_id INTEGER,
            category_id INTEGER,
            PRIMARY KEY (song_id, category_id),
            FOREIGN KEY(song_id) REFERENCES songs(id) ON DELETE CASCADE,
            FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS likes (
            user_id INTEGER,
            song_id INTEGER,
            PRIMARY KEY (user_id, song_id),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(song_id) REFERENCES songs(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS play_history (
            user_id INTEGER,
            song_id INTEGER,
            played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(song_id) REFERENCES songs(id) ON DELETE CASCADE
        );
        ''')

init_db()

def get_conn():
    return sqlite3.connect('admin.db')

def get_song_duration(filepath):
    try:
        audio = mutagen.File(filepath)
        return int(audio.info.length)
    except:
        file_size = os.path.getsize(filepath)
        return max(30, int(file_size / (160 * 1024) * 60))  # FIXED: missing parenthesis


@app.route('/')
def home():
    q = request.args.get('q', '').strip()
    user_id = session.get('user_id')

    # 1) grab raw id/name lists
    with get_conn() as conn:
        raw_languages = conn.execute(
            "SELECT id, name FROM categories WHERE type='language' ORDER BY name LIMIT 4"
        ).fetchall()
        raw_genres = conn.execute(
            "SELECT id, name FROM categories WHERE type='genre' ORDER BY name LIMIT 4"
        ).fetchall()

    # 2) define per-card backgrounds (colors, gradients or image URLs)
    style_map = {
        'English': 'linear-gradient(135deg, #6a5acd, #00bfff)',
        'Hindi': 'linear-gradient(45deg, #FFA726, #FB8C00)',
        'Tamil': '#7E57C2',
        'Kannada': '#29B6F6',
        'Love': 'linear-gradient(to right, #cc2b5e, #753a88)',
        'Workout': 'url(/static/images/workout-bg.jpg) center/cover',
        # …add any others you need…
    }

    # 3) build the final triples your template expects
    languages = [
        (lid, lname, style_map.get(lname, 'var(--hover-bg)'))
        for lid, lname in raw_languages
    ]
    genres = [
        (gid, gname, style_map.get(gname, 'var(--hover-bg)'))
        for gid, gname in raw_genres
    ]

    # 4) now fetch featured, recent & search exactly as before
    featured = []
    recent = []
    search_results = []
    with get_conn() as conn:
        # featured
        if user_id:
            featured = conn.execute('''
                SELECT s.id,s.title,s.artist,s.filename,s.cover_filename
                  FROM songs s
                  JOIN play_history h ON s.id=h.song_id
                 WHERE h.user_id=?
              GROUP BY s.id
              ORDER BY COUNT(*) DESC
                 LIMIT 8
            ''', (user_id,)).fetchall()
            if len(featured) < 8:
                used = ','.join(str(s[0]) for s in featured) or '0'
                extra = conn.execute(f'''
                    SELECT id,title,artist,filename,cover_filename
                      FROM songs
                     WHERE id NOT IN ({used})
                     ORDER BY RANDOM()
                     LIMIT ?
                ''', (8-len(featured),)).fetchall()
                featured.extend(extra)
        else:
            featured = conn.execute(
                "SELECT id,title,artist,filename,cover_filename FROM songs ORDER BY RANDOM() LIMIT 8"
            ).fetchall()

        # recent
        if user_id:
            recent = conn.execute('''
                SELECT s.id,s.title,s.artist,s.filename,s.cover_filename
                  FROM play_history h
                  JOIN songs s ON h.song_id=s.id
                 WHERE h.user_id=?
              GROUP BY s.id
              ORDER BY MAX(h.played_at) DESC
                 LIMIT 4
            ''', (user_id,)).fetchall()

        # search
        if q:
            search_results = conn.execute('''
                SELECT id,title,artist,filename,cover_filename
                  FROM songs
                 WHERE title LIKE ? OR artist LIKE ?
            ''', (f'%{q}%', f'%{q}%')).fetchall()

    # 5) render
    return render_template(
        'index.html',
        languages=languages,
        genres=genres,
        featured=featured,
        recent=recent,
        search_results=search_results,
        q=q
    )


@app.route('/category/<int:cat_id>')
def songs_by_category(cat_id):
    with get_conn() as conn:
        category = conn.execute(
            'SELECT name, type FROM categories WHERE id=?', (cat_id,)
        ).fetchone()

        if not category:
            return "Category not found", 404

        songs = conn.execute(
            'SELECT s.id, s.title, s.artist, s.filename, s.cover_filename FROM songs s '
            'JOIN song_categories sc ON s.id=sc.song_id '
            'WHERE sc.category_id=?', (cat_id,)
        ).fetchall()

    return render_template('songs.html',
                           songs=songs,
                           heading=category[0])


@app.route('/song-data/<int:song_id>')
def song_data(song_id):
    with get_conn() as conn:
        song = conn.execute(
            'SELECT id, title, artist, filename, cover_filename, duration FROM songs WHERE id=?',
            (song_id,)
        ).fetchone()

    if not song:
        return jsonify({'error': 'Song not found'}), 404

    if 'user_id' in session:
        with get_conn() as conn:
            conn.execute(
                'INSERT INTO play_history (user_id, song_id) VALUES (?, ?)',
                (session['user_id'], song_id)
            )

    return jsonify({
        'id': song[0],
        'title': song[1],
        'artist': song[2],
        'filename': song[3],
        'cover_url': url_for('serve_cover', filename=song[4]) if song[4] else '',
        'duration': song[5],
        'url': url_for('serve_song', filename=song[3])
    })


@app.route('/static/songs/<filename>')
def serve_song(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/static/covers/<filename>')
def serve_cover(filename):
    return send_from_directory(app.config['COVER_FOLDER'], filename)


# -- User Authentication ------------------------------------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()

        if not username or not password:
            return 'Username and password are required', 400

        pw_hash = generate_password_hash(password)
        try:
            with get_conn() as conn:
                conn.execute(
                    'INSERT INTO users (username, password) VALUES (?, ?)',
                    (username, pw_hash)
                )
            return redirect(url_for('user_login'))
        except sqlite3.IntegrityError:
            return 'Username already taken', 400
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        with get_conn() as conn:
            user = conn.execute(
                'SELECT id, password FROM users WHERE username=?',
                (username,)
            ).fetchone()

        if user and check_password_hash(user[1], password):
            session.clear()
            session['user_id'] = user[0]
            session['username'] = username
            return redirect(url_for('home'))
        return 'Invalid credentials', 401
    return render_template('login.html')


@app.route('/logout')
def user_logout():
    session.clear()
    return redirect(url_for('home'))


# -- Like/Unlike ---------------------------------------------------------------
@app.route('/like/<int:song_id>', methods=['POST'])
def like(song_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Login required'}), 401

    with get_conn() as conn:
        # Check if song exists
        song = conn.execute(
            'SELECT 1 FROM songs WHERE id=?', (song_id,)
        ).fetchone()
        if not song:
            return jsonify({'error': 'Song not found'}), 404

        exists = conn.execute(
            'SELECT 1 FROM likes WHERE user_id=? AND song_id=?',
            (user_id, song_id)
        ).fetchone()

        if exists:
            conn.execute(
                'DELETE FROM likes WHERE user_id=? AND song_id=?',
                (user_id, song_id)
            )
            liked = False
        else:
            conn.execute(
                'INSERT INTO likes (user_id, song_id) VALUES (?, ?)',
                (user_id, song_id)
            )
            liked = True

    return jsonify({'liked': liked, 'count': get_like_count(song_id)})


def get_like_count(song_id):
    with get_conn() as conn:
        return conn.execute(
            'SELECT COUNT(*) FROM likes WHERE song_id=?', (song_id,)
        ).fetchone()[0]

@app.route('/library')
def library():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('user_login'))

    with get_conn() as conn:
        # Get liked songs
        liked = conn.execute(
            'SELECT s.id, s.title, s.artist, s.filename, s.cover_filename '
            'FROM songs s '
            'JOIN likes l ON s.id=l.song_id '
            'WHERE l.user_id=?', (user_id,)
        ).fetchall()

        # Get recently played
        recent = conn.execute(
            'SELECT s.id, s.title, s.artist, s.filename, s.cover_filename '
            'FROM play_history h '
            'JOIN songs s ON h.song_id = s.id '
            'WHERE h.user_id = ? '
            'GROUP BY s.id '
            'ORDER BY MAX(h.played_at) DESC LIMIT 12', (user_id,)
        ).fetchall()

    return render_template('library.html',
                           liked=liked,
                           recent=recent)


# -- Run Application -----------------------------------------------------------
if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5001, debug=True)
