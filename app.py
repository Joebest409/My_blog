import os
import sqlite3
import uuid

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from werkzeug.utils import secure_filename


# =========================================================
# FLASK APP
# =========================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "dev-secret-key-change-in-production"
)

DATABASE = "blog.db"


# =========================================================
# MEDIA SETTINGS
# =========================================================

MEDIA_FOLDER = "static/media"

ALLOWED_MEDIA_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "gif",
    "webp",
    "mp3",
    "wav",
    "ogg",
    "m4a",
    "mp4",
    "webm",
    "mov"
}

os.makedirs(MEDIA_FOLDER, exist_ok=True)


# =========================================================
# PROFILE PICTURE SETTINGS
# =========================================================

PROFILE_FOLDER = "static/profile_pictures"

ALLOWED_PROFILE_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "gif",
    "webp"
}

os.makedirs(PROFILE_FOLDER, exist_ok=True)


# =========================================================
# CATEGORIES
# =========================================================

CATEGORIES = [
    "Technology",
    "Education",
    "Business",
    "News",
    "Music",
    "Health",
    "General"
]


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db():

    conn = sqlite3.connect(DATABASE)

    conn.row_factory = sqlite3.Row

    return conn


# =========================================================
# PROFILE PICTURE CHECK
# =========================================================

def allowed_profile_picture(filename):

    if not filename:
        return False

    if "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()

    return extension in ALLOWED_PROFILE_EXTENSIONS


# =========================================================
# MEDIA CHECK
# =========================================================

def allowed_media(filename):

    if not filename:
        return False

    if "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()

    return extension in ALLOWED_MEDIA_EXTENSIONS


# =========================================================
# GET MEDIA TYPE
# =========================================================

def get_media_type(filename):

    if not filename or "." not in filename:
        return "other"

    extension = filename.rsplit(".", 1)[1].lower()

    if extension in {
        "jpg",
        "jpeg",
        "png",
        "gif",
        "webp"
    }:
        return "image"

    if extension in {
        "mp3",
        "wav",
        "ogg",
        "m4a"
    }:
        return "audio"

    if extension in {
        "mp4",
        "webm",
        "mov"
    }:
        return "video"

    return "other"


# =========================================================
# DELETE MEDIA FILES FOR A POST
# =========================================================

def delete_post_media_files(conn, post_id):

    media_files = conn.execute("""
        SELECT filename
        FROM media
        WHERE post_id = ?
    """, (
        post_id,
    )).fetchall()

    for media in media_files:

        file_path = os.path.join(
            MEDIA_FOLDER,
            media["filename"]
        )

        if os.path.exists(file_path):

            try:
                os.remove(file_path)

            except OSError:
                pass

    conn.execute("""
        DELETE FROM media
        WHERE post_id = ?
    """, (
        post_id,
    ))


# =========================================================
# NOTIFICATION COUNT
# =========================================================

def get_notification_count():

    if "user_id" not in session:
        return 0

    conn = get_db()

    count = conn.execute("""
        SELECT COUNT(*)
        FROM notifications
        WHERE user_id = ?
        AND is_read = 0
    """, (
        session["user_id"],
    )).fetchone()[0]

    conn.close()

    return count


# =========================================================
# INITIALIZE DATABASE
# =========================================================

def init_db():

    conn = get_db()


    # =====================================================
    # USERS TABLE
    # =====================================================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            username TEXT NOT NULL UNIQUE,

            email TEXT NOT NULL UNIQUE,

            password TEXT NOT NULL,

            created_at TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP

        )
    """)


    # =====================================================
    # PROFILE PICTURE MIGRATION
    # =====================================================

    user_columns = conn.execute(
        "PRAGMA table_info(users)"
    ).fetchall()

    user_column_names = [
        column["name"]
        for column in user_columns
    ]

    if "profile_picture" not in user_column_names:

        conn.execute("""
            ALTER TABLE users
            ADD COLUMN profile_picture TEXT
        """)


    # =====================================================
    # POSTS TABLE
    # =====================================================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS posts (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            title TEXT NOT NULL,

            content TEXT NOT NULL,

            author TEXT NOT NULL,

            category TEXT DEFAULT 'General',

            created_at TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP,

            likes INTEGER DEFAULT 0,

            views INTEGER DEFAULT 0

        )
    """)


    # =====================================================
    # POSTS MIGRATION
    # =====================================================

    columns = conn.execute(
        "PRAGMA table_info(posts)"
    ).fetchall()

    column_names = [
        column["name"]
        for column in columns
    ]

    if "category" not in column_names:

        conn.execute("""
            ALTER TABLE posts
            ADD COLUMN category TEXT DEFAULT 'General'
        """)

    if "likes" not in column_names:

        conn.execute("""
            ALTER TABLE posts
            ADD COLUMN likes INTEGER DEFAULT 0
        """)

    if "views" not in column_names:

        conn.execute("""
            ALTER TABLE posts
            ADD COLUMN views INTEGER DEFAULT 0
        """)


    # =====================================================
    # COMMENTS TABLE
    # =====================================================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS comments (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            post_id INTEGER NOT NULL,

            user_id INTEGER NOT NULL,

            content TEXT NOT NULL,

            parent_id INTEGER,

            created_at TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (post_id)
                REFERENCES posts(id),

            FOREIGN KEY (user_id)
                REFERENCES users(id)

        )
    """)


    # =====================================================
    # COMMENTS MIGRATION
    # =====================================================

    comment_columns = conn.execute(
        "PRAGMA table_info(comments)"
    ).fetchall()

    comment_column_names = [
        column["name"]
        for column in comment_columns
    ]

    if "parent_id" not in comment_column_names:

        conn.execute("""
            ALTER TABLE comments
            ADD COLUMN parent_id INTEGER
        """)


    # =====================================================
    # COMMENT LIKES
    # =====================================================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS comment_likes (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            comment_id INTEGER NOT NULL,

            user_id INTEGER NOT NULL,

            UNIQUE(comment_id, user_id),

            FOREIGN KEY (comment_id)
                REFERENCES comments(id),

            FOREIGN KEY (user_id)
                REFERENCES users(id)

        )
    """)


    # =====================================================
    # POST LIKES
    # =====================================================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS post_likes (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            post_id INTEGER NOT NULL,

            user_id INTEGER NOT NULL,

            UNIQUE(post_id, user_id),

            FOREIGN KEY (post_id)
                REFERENCES posts(id),

            FOREIGN KEY (user_id)
                REFERENCES users(id)

        )
    """)


    # =====================================================
    # ADMINS
    # =====================================================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS admins (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            username TEXT NOT NULL UNIQUE,

            password TEXT NOT NULL,

            created_at TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP

        )
    """)


    # =====================================================
    # NOTIFICATIONS
    # =====================================================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS notifications (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id INTEGER NOT NULL,

            message TEXT NOT NULL,

            post_id INTEGER,

            is_read INTEGER DEFAULT 0,

            created_at TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (user_id)
                REFERENCES users(id)

        )
    """)


    # =====================================================
    # MEDIA TABLE
    # =====================================================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS media (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            post_id INTEGER NOT NULL,

            filename TEXT NOT NULL,

            original_name TEXT,

            media_type TEXT NOT NULL,

            created_at TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (post_id)
                REFERENCES posts(id)

        )
    """)


    conn.commit()

    conn.close()


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    page = request.args.get(
        "page",
        1,
        type=int
    )

    if page < 1:
        page = 1

    per_page = 8

    offset = (page - 1) * per_page

    conn = get_db()

    total_posts = conn.execute("""
        SELECT COUNT(*)
        FROM posts
    """).fetchone()[0]

    total_pages = (
        (total_posts + per_page - 1)
        // per_page
    )

    posts = conn.execute("""
        SELECT *
        FROM posts
        ORDER BY created_at DESC
        LIMIT ?
        OFFSET ?
    """, (
        per_page,
        offset
    )).fetchall()

    popular_posts = conn.execute("""
        SELECT *
        FROM posts
        ORDER BY COALESCE(views, 0) DESC
        LIMIT 5
    """).fetchall()

    conn.close()

    return render_template(
        "index.html",
        posts=posts,
        popular_posts=popular_posts,
        page=page,
        total_pages=total_pages,
        categories=CATEGORIES
    )


# =========================================================
# REGISTER
# =========================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        username = request.form[
            "username"
        ].strip()

        email = request.form[
            "email"
        ].strip()

        password = request.form[
            "password"
        ]

        if not username or not email or not password:

            return "All fields are required."

        hashed_password = generate_password_hash(
            password
        )

        conn = get_db()

        try:

            conn.execute("""
                INSERT INTO users
                (
                    username,
                    email,
                    password
                )
                VALUES (?, ?, ?)
            """, (
                username,
                email,
                hashed_password
            ))

            conn.commit()

        except sqlite3.IntegrityError:

            conn.close()

            return "Username or email already exists."

        conn.close()

        return redirect(
            url_for("login")
        )

    return render_template(
        "register.html"
    )


# =========================================================
# LOGIN
# =========================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        username = request.form[
            "username"
        ].strip()

        password = request.form[
            "password"
        ]

        conn = get_db()

        user = conn.execute("""
            SELECT *
            FROM users
            WHERE username = ?
        """, (
            username,
        )).fetchone()

        conn.close()

        if user and check_password_hash(
            user["password"],
            password
        ):

            session["user_id"] = user["id"]

            session["username"] = user["username"]

            return redirect(
                url_for("home")
            )

        return "Invalid username or password."

    return render_template(
        "login.html"
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("home")
    )


# =========================================================
# CREATE POST - ADMIN ONLY
# =========================================================

@app.route(
    "/create",
    methods=["GET", "POST"]
)
def create_post():

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )

    if request.method == "POST":

        title = request.form[
            "title"
        ].strip()

        content = request.form[
            "content"
        ].strip()

        category = request.form.get(
            "category",
            "General"
        ).strip()

        if not title or not content:

            return "Title and content are required."

        if category not in CATEGORIES:

            category = "General"

        author = session[
            "admin_username"
        ]

        conn = get_db()

        conn.execute("""
            INSERT INTO posts
            (
                title,
                content,
                author,
                category
            )
            VALUES (?, ?, ?, ?)
        """, (
            title,
            content,
            author,
            category
        ))

        conn.commit()

        conn.close()

        return redirect(
            url_for("admin_dashboard")
        )

    return render_template(
        "create_post.html",
        categories=CATEGORIES
    )


# =========================================================
# VIEW POST
# =========================================================

@app.route("/post/<int:post_id>")
def post(post_id):

    conn = get_db()

    existing_post = conn.execute("""
        SELECT id
        FROM posts
        WHERE id = ?
    """, (
        post_id,
    )).fetchone()

    if existing_post is None:

        conn.close()

        return "Post not found", 404


    # Increase views

    conn.execute("""
        UPDATE posts
        SET views = COALESCE(views, 0) + 1
        WHERE id = ?
    """, (
        post_id,
    ))

    conn.commit()


    # Get post

    post = conn.execute("""
        SELECT *
        FROM posts
        WHERE id = ?
    """, (
        post_id,
    )).fetchone()


    # Get media

    media = conn.execute("""
        SELECT *
        FROM media
        WHERE post_id = ?
        ORDER BY created_at ASC
    """, (
        post_id,
    )).fetchall()


    # Get comments

    comments = conn.execute("""
        SELECT
            comments.*,
            users.username,
            users.profile_picture,

            (
                SELECT COUNT(*)
                FROM comment_likes
                WHERE comment_likes.comment_id =
                    comments.id
            ) AS comment_likes

        FROM comments

        JOIN users
        ON comments.user_id = users.id

        WHERE comments.post_id = ?

        ORDER BY comments.created_at ASC

    """, (
        post_id,
    )).fetchall()


    # Get related posts

    related_posts = conn.execute("""
        SELECT *
        FROM posts
        WHERE category = ?
        AND id != ?
        ORDER BY created_at DESC
        LIMIT 5
    """, (
        post["category"],
        post_id
    )).fetchall()

    conn.close()

    return render_template(
        "post.html",
        post=post,
        comments=comments,
        related_posts=related_posts,
        media=media
    )


# =========================================================
# UPLOAD MEDIA - ADMIN ONLY
# =========================================================

@app.route(
    "/admin/post/<int:post_id>/media",
    methods=["POST"]
)
def upload_media(post_id):

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )

    file = request.files.get("media")

    if not file or not file.filename:

        return "Please select a media file."


    if not allowed_media(file.filename):

        return "Unsupported media type."


    conn = get_db()


    # Check post

    post = conn.execute("""
        SELECT id
        FROM posts
        WHERE id = ?
    """, (
        post_id,
    )).fetchone()

    if post is None:

        conn.close()

        return "Post not found", 404


    # Secure original filename

    original_name = secure_filename(
        file.filename
    )

    if not original_name:

        conn.close()

        return "Invalid filename."


    extension = original_name.rsplit(
        ".",
        1
    )[1].lower()


    # Generate unique filename

    filename = (
        str(uuid.uuid4())
        + "."
        + extension
    )


    file_path = os.path.join(
        MEDIA_FOLDER,
        filename
    )


    # Save file

    file.save(file_path)


    # Determine type

    media_type = get_media_type(
        original_name
    )


    if media_type == "other":

        if os.path.exists(file_path):

            try:
                os.remove(file_path)

            except OSError:
                pass

        conn.close()

        return "Unsupported media type."


    # Save database record

    conn.execute("""
        INSERT INTO media
        (
            post_id,
            filename,
            original_name,
            media_type
        )
        VALUES (?, ?, ?, ?)
    """, (
        post_id,
        filename,
        original_name,
        media_type
    ))


    conn.commit()

    conn.close()


    return redirect(
        url_for(
            "post",
            post_id=post_id
        )
    )


# =========================================================
# DELETE MEDIA - ADMIN ONLY
# =========================================================

@app.route(
    "/admin/media/delete/<int:media_id>",
    methods=["POST"]
)
def delete_media(media_id):

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )

    conn = get_db()


    media = conn.execute("""
        SELECT *
        FROM media
        WHERE id = ?
    """, (
        media_id,
    )).fetchone()


    if media is None:

        conn.close()

        return "Media not found", 404


    post_id = media["post_id"]


    # Delete physical file

    file_path = os.path.join(
        MEDIA_FOLDER,
        media["filename"]
    )


    if os.path.exists(file_path):

        try:
            os.remove(file_path)

        except OSError:
            pass


    # Delete database record

    conn.execute("""
        DELETE FROM media
        WHERE id = ?
    """, (
        media_id,
    ))


    conn.commit()

    conn.close()


    return redirect(
        url_for(
            "post",
            post_id=post_id
        )
    )


# =========================================================
# LIKE / UNLIKE POST
# =========================================================

@app.route(
    "/post/<int:post_id>/like",
    methods=["POST"]
)
def like_post(post_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    conn = get_db()

    post = conn.execute("""
        SELECT id
        FROM posts
        WHERE id = ?
    """, (
        post_id,
    )).fetchone()

    if post is None:

        conn.close()

        return "Post not found", 404


    existing_like = conn.execute("""
        SELECT id
        FROM post_likes
        WHERE post_id = ?
        AND user_id = ?
    """, (
        post_id,
        session["user_id"]
    )).fetchone()


    if existing_like:

        conn.execute("""
            DELETE FROM post_likes
            WHERE post_id = ?
            AND user_id = ?
        """, (
            post_id,
            session["user_id"]
        ))

        conn.execute("""
            UPDATE posts
            SET likes =
                CASE
                    WHEN COALESCE(likes, 0) > 0
                    THEN likes - 1
                    ELSE 0
                END
            WHERE id = ?
        """, (
            post_id,
        ))


    else:

        conn.execute("""
            INSERT INTO post_likes
            (
                post_id,
                user_id
            )
            VALUES (?, ?)
        """, (
            post_id,
            session["user_id"]
        ))

        conn.execute("""
            UPDATE posts
            SET likes = COALESCE(likes, 0) + 1
            WHERE id = ?
        """, (
            post_id,
        ))


    conn.commit()

    conn.close()

    return redirect(
        url_for(
            "post",
            post_id=post_id
        )
    )


# =========================================================
# ADD COMMENT / REPLY
# =========================================================

@app.route(
    "/post/<int:post_id>/comment",
    methods=["POST"]
)
def add_comment(post_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    content = request.form.get(
        "content",
        ""
    ).strip()

    if not content:

        return redirect(
            url_for(
                "post",
                post_id=post_id
            )
        )

    parent_id = request.form.get(
        "parent_id",
        type=int
    )

    conn = get_db()


    post = conn.execute("""
        SELECT id
        FROM posts
        WHERE id = ?
    """, (
        post_id,
    )).fetchone()


    if post is None:

        conn.close()

        return "Post not found", 404


    parent_comment = None


    if parent_id:

        parent_comment = conn.execute("""
            SELECT
                id,
                user_id
            FROM comments
            WHERE id = ?
            AND post_id = ?
        """, (
            parent_id,
            post_id
        )).fetchone()


        if parent_comment is None:

            conn.close()

            return "Invalid parent comment", 400


    conn.execute("""
        INSERT INTO comments
        (
            post_id,
            user_id,
            content,
            parent_id
        )
        VALUES (?, ?, ?, ?)
    """, (
        post_id,
        session["user_id"],
        content,
        parent_id
    ))


    # Notification for reply

    if parent_comment:

        parent_user_id = parent_comment["user_id"]

        if parent_user_id != session["user_id"]:

            username = session["username"]

            message = (
                f"{username} replied to your comment."
            )

            conn.execute("""
                INSERT INTO notifications
                (
                    user_id,
                    message,
                    post_id
                )
                VALUES (?, ?, ?)
            """, (
                parent_user_id,
                message,
                post_id
            ))


    conn.commit()

    conn.close()

    return redirect(
        url_for(
            "post",
            post_id=post_id
        )
    )


# =========================================================
# LIKE / UNLIKE COMMENT
# =========================================================

@app.route(
    "/comment/<int:comment_id>/like",
    methods=["POST"]
)
def like_comment(comment_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    conn = get_db()


    comment = conn.execute("""
        SELECT
            id,
            post_id
        FROM comments
        WHERE id = ?
    """, (
        comment_id,
    )).fetchone()


    if comment is None:

        conn.close()

        return "Comment not found", 404


    existing_like = conn.execute("""
        SELECT id
        FROM comment_likes
        WHERE comment_id = ?
        AND user_id = ?
    """, (
        comment_id,
        session["user_id"]
    )).fetchone()


    if existing_like:

        conn.execute("""
            DELETE FROM comment_likes
            WHERE comment_id = ?
            AND user_id = ?
        """, (
            comment_id,
            session["user_id"]
        ))


    else:

        conn.execute("""
            INSERT INTO comment_likes
            (
                comment_id,
                user_id
            )
            VALUES (?, ?)
        """, (
            comment_id,
            session["user_id"]
        ))


    conn.commit()

    conn.close()

    return redirect(
        url_for(
            "post",
            post_id=comment["post_id"]
        )
    )


# =========================================================
# DELETE OWN COMMENT
# =========================================================

@app.route(
    "/comment/<int:comment_id>/delete",
    methods=["POST"]
)
def delete_own_comment(comment_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    conn = get_db()


    comment = conn.execute("""
        SELECT
            id,
            post_id,
            user_id
        FROM comments
        WHERE id = ?
    """, (
        comment_id,
    )).fetchone()


    if comment is None:

        conn.close()

        return "Comment not found", 404


    if comment["user_id"] != session["user_id"]:

        conn.close()

        return (
            "You are not allowed to delete this comment.",
            403
        )


    post_id = comment["post_id"]


    conn.execute("""
        UPDATE comments
        SET parent_id = NULL
        WHERE parent_id = ?
    """, (
        comment_id,
    ))


    conn.execute("""
        DELETE FROM comment_likes
        WHERE comment_id = ?
    """, (
        comment_id,
    ))


    conn.execute("""
        DELETE FROM comments
        WHERE id = ?
        AND user_id = ?
    """, (
        comment_id,
        session["user_id"]
    ))


    conn.commit()

    conn.close()


    return redirect(
        url_for(
            "post",
            post_id=post_id
        )
    )


# =========================================================
# EDIT POST
# =========================================================

@app.route(
    "/edit/<int:post_id>",
    methods=["GET", "POST"]
)
def edit_post(post_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    conn = get_db()


    post = conn.execute("""
        SELECT *
        FROM posts
        WHERE id = ?
    """, (
        post_id,
    )).fetchone()


    if post is None:

        conn.close()

        return "Post not found", 404


    if post["author"] != session["username"]:

        conn.close()

        return (
            "You are not allowed to edit this post.",
            403
        )


    if request.method == "POST":

        title = request.form[
            "title"
        ].strip()

        content = request.form[
            "content"
        ].strip()

        category = request.form.get(
            "category",
            "General"
        ).strip()


        if not title or not content:

            conn.close()

            return "Title and content are required."


        if category not in CATEGORIES:

            category = "General"


        conn.execute("""
            UPDATE posts
            SET
                title = ?,
                content = ?,
                category = ?
            WHERE id = ?
        """, (
            title,
            content,
            category,
            post_id
        ))


        conn.commit()

        conn.close()


        return redirect(
            url_for(
                "post",
                post_id=post_id
            )
        )


    conn.close()


    return render_template(
        "edit_post.html",
        post=post,
        categories=CATEGORIES
    )


# =========================================================
# DELETE POST
# =========================================================

@app.route(
    "/delete/<int:post_id>",
    methods=["POST"]
)
def delete_post(post_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    conn = get_db()


    post = conn.execute("""
        SELECT *
        FROM posts
        WHERE id = ?
    """, (
        post_id,
    )).fetchone()


    if post is None:

        conn.close()

        return "Post not found", 404


    if post["author"] != session["username"]:

        conn.close()

        return (
            "You are not allowed to delete this post.",
            403
        )


    # Delete media files

    delete_post_media_files(
        conn,
        post_id
    )


    # Delete comment likes

    conn.execute("""
        DELETE FROM comment_likes
        WHERE comment_id IN (
            SELECT id
            FROM comments
            WHERE post_id = ?
        )
    """, (
        post_id,
    ))


    # Delete comments

    conn.execute("""
        DELETE FROM comments
        WHERE post_id = ?
    """, (
        post_id,
    ))


    # Delete post likes

    conn.execute("""
        DELETE FROM post_likes
        WHERE post_id = ?
    """, (
        post_id,
    ))


    # Delete notifications

    conn.execute("""
        DELETE FROM notifications
        WHERE post_id = ?
    """, (
        post_id,
    ))


    # Delete post

    conn.execute("""
        DELETE FROM posts
        WHERE id = ?
    """, (
        post_id,
    ))


    conn.commit()

    conn.close()


    return redirect(
        url_for("home")
    )


# =========================================================
# PROFILE
# =========================================================

@app.route("/profile/<username>")
def profile(username):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    page = request.args.get(
        "page",
        1,
        type=int
    )

    if page < 1:
        page = 1

    per_page = 5

    offset = (page - 1) * per_page

    conn = get_db()


    user = conn.execute("""
        SELECT *
        FROM users
        WHERE username = ?
    """, (
        username,
    )).fetchone()


    if user is None:

        conn.close()

        return "User not found", 404


    total_posts = conn.execute("""
        SELECT COUNT(*)
        FROM posts
        WHERE author = ?
    """, (
        username,
    )).fetchone()[0]


    total_pages = (
        (total_posts + per_page - 1)
        // per_page
    )


    posts = conn.execute("""
        SELECT *
        FROM posts
        WHERE author = ?
        ORDER BY created_at DESC
        LIMIT ?
        OFFSET ?
    """, (
        username,
        per_page,
        offset
    )).fetchall()


    total_likes = conn.execute("""
        SELECT COALESCE(
            SUM(likes),
            0
        )
        FROM posts
        WHERE author = ?
    """, (
        username,
    )).fetchone()[0]


    total_views = conn.execute("""
        SELECT COALESCE(
            SUM(views),
            0
        )
        FROM posts
        WHERE author = ?
    """, (
        username,
    )).fetchone()[0]


    conn.close()


    return render_template(
        "profile.html",
        user=user,
        posts=posts,
        total_posts=total_posts,
        total_likes=total_likes,
        total_views=total_views,
        page=page,
        total_pages=total_pages
    )


# =========================================================
# EDIT PROFILE
# =========================================================

@app.route(
    "/profile/<username>/edit",
    methods=["GET", "POST"]
)
def edit_profile(username):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    if username != session.get("username"):

        return "Unauthorized", 403


    conn = get_db()


    user = conn.execute("""
        SELECT *
        FROM users
        WHERE id = ?
    """, (
        session["user_id"],
    )).fetchone()


    if user is None:

        conn.close()

        return "User not found", 404


    if request.method == "POST":

        new_username = request.form[
            "username"
        ].strip()

        new_email = request.form[
            "email"
        ].strip()


        if not new_username or not new_email:

            conn.close()

            return (
                "Username and email are required."
            )


        existing_username = conn.execute("""
            SELECT id
            FROM users
            WHERE username = ?
            AND id != ?
        """, (
            new_username,
            session["user_id"]
        )).fetchone()


        if existing_username:

            conn.close()

            return "Username already exists."


        existing_email = conn.execute("""
            SELECT id
            FROM users
            WHERE email = ?
            AND id != ?
        """, (
            new_email,
            session["user_id"]
        )).fetchone()


        if existing_email:

            conn.close()

            return "Email already exists."


        conn.execute("""
            UPDATE users
            SET
                username = ?,
                email = ?
            WHERE id = ?
        """, (
            new_username,
            new_email,
            session["user_id"]
        ))


        conn.commit()

        conn.close()


        session["username"] = new_username


        return redirect(
            url_for(
                "profile",
                username=new_username
            )
        )


    conn.close()


    return render_template(
        "edit_profile.html",
        user=user
    )


# =========================================================
# UPLOAD / CHANGE PROFILE PICTURE
# =========================================================

@app.route(
    "/profile/<username>/picture",
    methods=["POST"]
)
def upload_profile_picture(username):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    if username != session.get("username"):

        return "Unauthorized", 403


    file = request.files.get(
        "profile_picture"
    )


    if not file or not file.filename:

        return "Please select a profile picture."


    if not allowed_profile_picture(
        file.filename
    ):

        return (
            "Invalid image type. "
            "Use JPG, JPEG, PNG, GIF or WEBP."
        )


    extension = file.filename.rsplit(
        ".",
        1
    )[1].lower()


    filename = (
        str(uuid.uuid4())
        + "."
        + extension
    )


    safe_filename = secure_filename(
        filename
    )


    file_path = os.path.join(
        PROFILE_FOLDER,
        safe_filename
    )


    conn = get_db()


    user = conn.execute("""
        SELECT profile_picture
        FROM users
        WHERE id = ?
    """, (
        session["user_id"],
    )).fetchone()


    if user is None:

        conn.close()

        return "User not found", 404


    old_picture = user["profile_picture"]


    if old_picture:

        old_path = os.path.join(
            PROFILE_FOLDER,
            old_picture
        )


        if os.path.exists(old_path):

            try:
                os.remove(old_path)

            except OSError:
                pass


    file.save(file_path)


    conn.execute("""
        UPDATE users
        SET profile_picture = ?
        WHERE id = ?
    """, (
        safe_filename,
        session["user_id"]
    ))


    conn.commit()

    conn.close()


    return redirect(
        url_for(
            "profile",
            username=username
        )
    )


# =========================================================
# USER CHANGE PASSWORD
# =========================================================

@app.route(
    "/profile/<username>/change-password",
    methods=["GET", "POST"]
)
def change_user_password(username):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    if username != session.get("username"):

        return "Unauthorized", 403


    if request.method == "POST":

        current_password = request.form[
            "current_password"
        ]

        new_password = request.form[
            "new_password"
        ]

        confirm_password = request.form[
            "confirm_password"
        ]


        if (
            not current_password
            or not new_password
            or not confirm_password
        ):

            return (
                "All password fields are required."
            )


        if new_password != confirm_password:

            return "New passwords do not match."


        if len(new_password) < 8:

            return (
                "New password must be at least 8 characters."
            )


        conn = get_db()


        user = conn.execute("""
            SELECT *
            FROM users
            WHERE id = ?
        """, (
            session["user_id"],
        )).fetchone()


        if user is None:

            conn.close()

            session.clear()

            return redirect(
                url_for("login")
            )


        if not check_password_hash(
            user["password"],
            current_password
        ):

            conn.close()

            return (
                "Current password is incorrect."
            )


        hashed_password = generate_password_hash(
            new_password
        )


        conn.execute("""
            UPDATE users
            SET password = ?
            WHERE id = ?
        """, (
            hashed_password,
            session["user_id"]
        ))


        conn.commit()

        conn.close()


        return redirect(
            url_for(
                "profile",
                username=session["username"]
            )
        )


    return render_template(
        "change_user_password.html",
        username=username
    )


# =========================================================
# SEARCH
# =========================================================

@app.route("/search")
def search():

    search_query = request.args.get(
        "q",
        ""
    ).strip()

    category = request.args.get(
        "category",
        ""
    ).strip()

    page = request.args.get(
        "page",
        1,
        type=int
    )

    if page < 1:
        page = 1

    per_page = 8

    offset = (page - 1) * per_page

    conn = get_db()


    conditions = []

    params = []


    if search_query:

        conditions.append("""
            (
                title LIKE ?
                OR content LIKE ?
                OR author LIKE ?
            )
        """)

        search_value = f"%{search_query}%"

        params.extend([
            search_value,
            search_value,
            search_value
        ])


    if category:

        conditions.append(
            "category = ?"
        )

        params.append(category)


    where_clause = ""


    if conditions:

        where_clause = (
            "WHERE "
            + " AND ".join(conditions)
        )


    total_posts = conn.execute(
        f"""
        SELECT COUNT(*)
        FROM posts
        {where_clause}
        """,
        params
    ).fetchone()[0]


    total_pages = (
        (total_posts + per_page - 1)
        // per_page
    )


    posts = conn.execute(
        f"""
        SELECT *
        FROM posts
        {where_clause}
        ORDER BY created_at DESC
        LIMIT ?
        OFFSET ?
        """,
        params + [
            per_page,
            offset
        ]
    ).fetchall()


    conn.close()


    return render_template(
        "search.html",
        posts=posts,
        search_query=search_query,
        category=category,
        categories=CATEGORIES,
        page=page,
        total_pages=total_pages,
        total_posts=total_posts
    )


# =========================================================
# CATEGORY
# =========================================================

@app.route(
    "/category/<category_name>"
)
def category(category_name):

    if category_name not in CATEGORIES:

        return "Category not found", 404


    conn = get_db()


    posts = conn.execute("""
        SELECT *
        FROM posts
        WHERE category = ?
        ORDER BY created_at DESC
    """, (
        category_name,
    )).fetchall()


    conn.close()


    return render_template(
        "category.html",
        posts=posts,
        category=category_name
    )


# =========================================================
# ADMIN LOGIN
# =========================================================

@app.route(
    "/admin/login",
    methods=["GET", "POST"]
)
def admin_login():

    if request.method == "POST":

        username = request.form[
            "username"
        ].strip()

        password = request.form[
            "password"
        ]


        conn = get_db()


        admin = conn.execute("""
            SELECT *
            FROM admins
            WHERE username = ?
        """, (
            username,
        )).fetchone()


        conn.close()


        if admin and check_password_hash(
            admin["password"],
            password
        ):

            session["admin_id"] = admin["id"]

            session["admin_username"] = (
                admin["username"]
            )


            return redirect(
                url_for("admin_dashboard")
            )


        return (
            "Invalid admin username or password."
        )


    return render_template(
        "admin_login.html"
    )


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin/dashboard")
def admin_dashboard():

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )


    page = request.args.get(
        "page",
        1,
        type=int
    )


    if page < 1:
        page = 1


    per_page = 5

    offset = (page - 1) * per_page


    search = request.args.get(
        "search",
        ""
    ).strip()


    category = request.args.get(
        "category",
        ""
    ).strip()


    conn = get_db()


    total_users = conn.execute("""
        SELECT COUNT(*)
        FROM users
    """).fetchone()[0]


    total_comments = conn.execute("""
        SELECT COUNT(*)
        FROM comments
    """).fetchone()[0]


    total_likes = conn.execute("""
        SELECT COALESCE(SUM(likes), 0)
        FROM posts
    """).fetchone()[0]


    total_views = conn.execute("""
        SELECT COALESCE(SUM(views), 0)
        FROM posts
    """).fetchone()[0]


    conditions = []

    params = []


    if search:

        conditions.append("""
            (
                title LIKE ?
                OR content LIKE ?
                OR author LIKE ?
            )
        """)


        search_value = f"%{search}%"


        params.extend([
            search_value,
            search_value,
            search_value
        ])


    if category:

        conditions.append(
            "category = ?"
        )

        params.append(category)


    where_clause = ""


    if conditions:

        where_clause = (
            "WHERE "
            + " AND ".join(conditions)
        )


    total_posts = conn.execute(
        f"""
        SELECT COUNT(*)
        FROM posts
        {where_clause}
        """,
        params
    ).fetchone()[0]


    total_pages = (
        (total_posts + per_page - 1)
        // per_page
    )


    posts = conn.execute(
        f"""
        SELECT *
        FROM posts
        {where_clause}
        ORDER BY created_at DESC
        LIMIT ?
        OFFSET ?
        """,
        params + [
            per_page,
            offset
        ]
    ).fetchall()


    most_viewed_posts = conn.execute("""
        SELECT *
        FROM posts
        ORDER BY COALESCE(views, 0) DESC
        LIMIT 5
    """).fetchall()


    conn.close()


    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        total_posts=total_posts,
        total_comments=total_comments,
        total_likes=total_likes,
        total_views=total_views,
        posts=posts,
        most_viewed_posts=most_viewed_posts,
        categories=CATEGORIES,
        search=search,
        selected_category=category,
        page=page,
        total_pages=total_pages
    )


# =========================================================
# ADMIN LOGOUT
# =========================================================

@app.route("/admin/logout")
def admin_logout():

    session.pop(
        "admin_id",
        None
    )

    session.pop(
        "admin_username",
        None
    )


    return redirect(
        url_for("admin_login")
    )


# =========================================================
# ADMIN EDIT POST
# =========================================================

@app.route(
    "/admin/edit/<int:post_id>",
    methods=["GET", "POST"]
)
def admin_edit_post(post_id):

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )


    conn = get_db()


    post = conn.execute("""
        SELECT *
        FROM posts
        WHERE id = ?
    """, (
        post_id,
    )).fetchone()


    if post is None:

        conn.close()

        return "Post not found", 404


    if request.method == "POST":

        title = request.form[
            "title"
        ].strip()

        content = request.form[
            "content"
        ].strip()

        category = request.form.get(
            "category",
            "General"
        ).strip()


        if not title or not content:

            conn.close()

            return (
                "Title and content are required."
            )


        if category not in CATEGORIES:

            category = "General"


        conn.execute("""
            UPDATE posts
            SET
                title = ?,
                content = ?,
                category = ?
            WHERE id = ?
        """, (
            title,
            content,
            category,
            post_id
        ))


        conn.commit()

        conn.close()


        return redirect(
            url_for("admin_dashboard")
        )


    conn.close()


    return render_template(
        "admin_edit_post.html",
        post=post,
        categories=CATEGORIES
    )


# =========================================================
# ADMIN DELETE POST
# =========================================================

@app.route(
    "/admin/delete/<int:post_id>",
    methods=["POST"]
)
def admin_delete_post(post_id):

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )


    conn = get_db()


    post = conn.execute("""
        SELECT id
        FROM posts
        WHERE id = ?
    """, (
        post_id,
    )).fetchone()


    if post is None:

        conn.close()

        return "Post not found", 404


    # Delete media

    delete_post_media_files(
        conn,
        post_id
    )


    # Delete comment likes

    conn.execute("""
        DELETE FROM comment_likes
        WHERE comment_id IN (
            SELECT id
            FROM comments
            WHERE post_id = ?
        )
    """, (
        post_id,
    ))


    # Delete comments

    conn.execute("""
        DELETE FROM comments
        WHERE post_id = ?
    """, (
        post_id,
    ))


    # Delete post likes

    conn.execute("""
        DELETE FROM post_likes
        WHERE post_id = ?
    """, (
        post_id,
    ))


    # Delete notifications

    conn.execute("""
        DELETE FROM notifications
        WHERE post_id = ?
    """, (
        post_id,
    ))


    # Delete post

    conn.execute("""
        DELETE FROM posts
        WHERE id = ?
    """, (
        post_id,
    ))


    conn.commit()

    conn.close()


    return redirect(
        url_for("admin_dashboard")
    )


# =========================================================
# ADMIN USERS
# =========================================================

@app.route("/admin/users")
def admin_users():

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )


    page = request.args.get(
        "page",
        1,
        type=int
    )


    if page < 1:
        page = 1


    per_page = 10

    offset = (page - 1) * per_page


    conn = get_db()


    total_users = conn.execute("""
        SELECT COUNT(*)
        FROM users
    """).fetchone()[0]


    total_pages = (
        (total_users + per_page - 1)
        // per_page
    )


    users = conn.execute("""
        SELECT
            id,
            username,
            email,
            profile_picture,
            created_at
        FROM users
        ORDER BY created_at DESC
        LIMIT ?
        OFFSET ?
    """, (
        per_page,
        offset
    )).fetchall()


    conn.close()


    return render_template(
        "admin_users.html",
        users=users,
        page=page,
        total_pages=total_pages
    )


# =========================================================
# ADMIN DELETE USER
# =========================================================

@app.route(
    "/admin/users/delete/<int:user_id>",
    methods=["POST"]
)
def admin_delete_user(user_id):

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )


    conn = get_db()


    user = conn.execute("""
        SELECT *
        FROM users
        WHERE id = ?
    """, (
        user_id,
    )).fetchone()


    if user is None:

        conn.close()

        return "User not found", 404


    conn.execute("""
        UPDATE comments
        SET parent_id = NULL
        WHERE parent_id IN (
            SELECT id
            FROM comments
            WHERE user_id = ?
        )
    """, (
        user_id,
    ))


    conn.execute("""
        DELETE FROM comment_likes
        WHERE user_id = ?
        OR comment_id IN (
            SELECT id
            FROM comments
            WHERE user_id = ?
        )
    """, (
        user_id,
        user_id
    ))


    conn.execute("""
        DELETE FROM post_likes
        WHERE user_id = ?
    """, (
        user_id,
    ))


    conn.execute("""
        DELETE FROM notifications
        WHERE user_id = ?
    """, (
        user_id,
    ))


    conn.execute("""
        DELETE FROM comments
        WHERE user_id = ?
    """, (
        user_id,
    ))


    profile_picture = user["profile_picture"]


    if profile_picture:

        picture_path = os.path.join(
            PROFILE_FOLDER,
            profile_picture
        )


        if os.path.exists(picture_path):

            try:
                os.remove(picture_path)

            except OSError:
                pass


    conn.execute("""
        DELETE FROM users
        WHERE id = ?
    """, (
        user_id,
    ))


    conn.commit()

    conn.close()


    return redirect(
        url_for("admin_users")
    )


# =========================================================
# ADMIN COMMENT MANAGEMENT
# =========================================================

@app.route("/admin/comments")
def admin_comments():

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )


    page = request.args.get(
        "page",
        1,
        type=int
    )


    if page < 1:
        page = 1


    per_page = 10

    offset = (page - 1) * per_page


    conn = get_db()


    total_comments = conn.execute("""
        SELECT COUNT(*)
        FROM comments
    """).fetchone()[0]


    total_pages = (
        (total_comments + per_page - 1)
        // per_page
    )


    comments = conn.execute("""
        SELECT
            comments.id,
            comments.content,
            comments.created_at,
            comments.parent_id,
            users.username,
            posts.id AS post_id,
            posts.title AS post_title

        FROM comments

        JOIN users
        ON comments.user_id = users.id

        JOIN posts
        ON comments.post_id = posts.id

        ORDER BY comments.created_at DESC

        LIMIT ?
        OFFSET ?

    """, (
        per_page,
        offset
    )).fetchall()


    conn.close()


    return render_template(
        "admin_comments.html",
        comments=comments,
        page=page,
        total_pages=total_pages
    )


# =========================================================
# ADMIN DELETE COMMENT
# =========================================================

@app.route(
    "/admin/comments/delete/<int:comment_id>",
    methods=["POST"]
)
def admin_delete_comment(comment_id):

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )


    conn = get_db()


    comment = conn.execute("""
        SELECT id
        FROM comments
        WHERE id = ?
    """, (
        comment_id,
    )).fetchone()


    if comment is None:

        conn.close()

        return "Comment not found", 404


    conn.execute("""
        UPDATE comments
        SET parent_id = NULL
        WHERE parent_id = ?
    """, (
        comment_id,
    ))


    conn.execute("""
        DELETE FROM comment_likes
        WHERE comment_id = ?
    """, (
        comment_id,
    ))


    conn.execute("""
        DELETE FROM comments
        WHERE id = ?
    """, (
        comment_id,
    ))


    conn.commit()

    conn.close()


    return redirect(
        url_for("admin_comments")
    )


# =========================================================
# CREATE FIRST ADMIN
# =========================================================

def create_admin():

    conn = get_db()


    admin = conn.execute("""
        SELECT id
        FROM admins
        WHERE username = ?
    """, (
        "admin",
    )).fetchone()


    if admin is None:

        password = "Admin@12345"

        hashed_password = generate_password_hash(
            password
        )


        conn.execute("""
            INSERT INTO admins
            (
                username,
                password
            )
            VALUES (?, ?)
        """, (
            "admin",
            hashed_password
        ))


        conn.commit()


        print(
            "================================="
        )

        print(
            "ADMIN ACCOUNT CREATED"
        )

        print(
            "Username: admin"
        )

        print(
            "Password: Admin@12345"
        )

        print(
            "================================="
        )


    conn.close()


# =========================================================
# ADMIN CHANGE PASSWORD
# =========================================================

@app.route(
    "/admin/change-password",
    methods=["GET", "POST"]
)
def admin_change_password():

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )


    if request.method == "POST":

        current_password = request.form[
            "current_password"
        ]

        new_password = request.form[
            "new_password"
        ]

        confirm_password = request.form[
            "confirm_password"
        ]


        if (
            not current_password
            or not new_password
            or not confirm_password
        ):

            return (
                "All password fields are required."
            )


        if new_password != confirm_password:

            return "New passwords do not match."


        if len(new_password) < 8:

            return (
                "New password must be at least 8 characters."
            )


        conn = get_db()


        admin = conn.execute("""
            SELECT *
            FROM admins
            WHERE id = ?
        """, (
            session["admin_id"],
        )).fetchone()


        if admin is None:

            conn.close()


            session.pop(
                "admin_id",
                None
            )


            session.pop(
                "admin_username",
                None
            )


            return redirect(
                url_for("admin_login")
            )


        if not check_password_hash(
            admin["password"],
            current_password
        ):

            conn.close()

            return (
                "Current password is incorrect."
            )


        hashed_password = generate_password_hash(
            new_password
        )


        conn.execute("""
            UPDATE admins
            SET password = ?
            WHERE id = ?
        """, (
            hashed_password,
            session["admin_id"]
        ))


        conn.commit()

        conn.close()


        return redirect(
            url_for("admin_dashboard")
        )


    return render_template(
        "admin_change_password.html"
    )


# =========================================================
# NOTIFICATIONS
# =========================================================

@app.route("/notifications")
def notifications():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    conn = get_db()


    notification_list = conn.execute("""
        SELECT *
        FROM notifications
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (
        session["user_id"],
    )).fetchall()


    conn.close()


    return render_template(
        "notifications.html",
        notifications=notification_list
    )


# =========================================================
# MARK NOTIFICATION AS READ
# =========================================================

@app.route(
    "/notifications/read/<int:notification_id>",
    methods=["POST"]
)
def mark_notification_read(notification_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    conn = get_db()


    notification = conn.execute("""
        SELECT
            id,
            post_id
        FROM notifications
        WHERE id = ?
        AND user_id = ?
    """, (
        notification_id,
        session["user_id"]
    )).fetchone()


    if notification is None:

        conn.close()

        return "Notification not found", 404


    conn.execute("""
        UPDATE notifications
        SET is_read = 1
        WHERE id = ?
        AND user_id = ?
    """, (
        notification_id,
        session["user_id"]
    ))


    conn.commit()

    conn.close()


    if notification["post_id"]:

        return redirect(
            url_for(
                "post",
                post_id=notification["post_id"]
            )
        )


    return redirect(
        url_for("notifications")
    )


# =========================================================
# NOTIFICATION CONTEXT PROCESSOR
# =========================================================

@app.context_processor
def inject_notifications():

    return {
        "notification_count":
            get_notification_count()
    }


# =========================================================
# USER DASHBOARD
# =========================================================

@app.route("/dashboard")
def user_dashboard():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    user_id = session["user_id"]

    conn = get_db()


    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (user_id,)
    ).fetchone()


    if not user:

        conn.close()

        session.clear()

        return redirect(
            url_for("login")
        )


    # =====================================================
    # USER POST COUNT
    # =====================================================

    total_posts = conn.execute(
        """
        SELECT COUNT(*)
        FROM posts
        WHERE author = ?
        """,
        (user["username"],)
    ).fetchone()[0]


    # =====================================================
    # TOTAL LIKES
    # =====================================================

    total_likes = conn.execute(
        """
        SELECT COALESCE(SUM(likes), 0)
        FROM posts
        WHERE author = ?
        """,
        (user["username"],)
    ).fetchone()[0]


    # =====================================================
    # TOTAL VIEWS
    # =====================================================

    total_views = conn.execute(
        """
        SELECT COALESCE(SUM(views), 0)
        FROM posts
        WHERE author = ?
        """,
        (user["username"],)
    ).fetchone()[0]


    # =====================================================
    # TOTAL COMMENTS
    # =====================================================

    total_comments = conn.execute(
        """
        SELECT COUNT(*)
        FROM comments
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()[0]


    # =====================================================
    # RECENT POSTS
    # =====================================================

    posts = conn.execute(
        """
        SELECT *
        FROM posts
        WHERE author = ?
        ORDER BY created_at DESC
        LIMIT 5
        """,
        (user["username"],)
    ).fetchall()


    # =====================================================
    # RECENT NOTIFICATIONS
    # =====================================================

    notifications = conn.execute(
        """
        SELECT *
        FROM notifications
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 5
        """,
        (user_id,)
    ).fetchall()


    # =====================================================
    # RECENT COMMENTS
    # =====================================================

    recent_comments = conn.execute(
        """
        SELECT
            comments.*,
            posts.title AS post_title

        FROM comments

        JOIN posts
        ON comments.post_id = posts.id

        WHERE comments.user_id = ?

        ORDER BY comments.created_at DESC

        LIMIT 5
        """,
        (user_id,)
    ).fetchall()


    conn.close()


    return render_template(
        "user_dashboard.html",

        user=user,

        total_posts=total_posts,

        total_likes=total_likes,

        total_views=total_views,

        total_comments=total_comments,

        posts=posts,

        notifications=notifications,

        recent_comments=recent_comments
    )


# =========================================================
# START APPLICATION
# =========================================================

if __name__ == "__main__":

    init_db()

    create_admin()

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )