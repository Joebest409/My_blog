from flask import (
    Flask,
    render_template,
    request,
    redirect,
    session,
    send_from_directory,
    url_for
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

import sqlite3
import os
app = Flask(__name__)

app.secret_key = "change-this-secret-key"

app.config["UPLOAD_FOLDER"] = os.path.join(
    app.root_path,
    "uploads"
)

app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp"
}

os.makedirs(
    app.config["UPLOAD_FOLDER"],
    exist_ok=True
)

def allowed_file(filename):

    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )
app.secret_key = "change-this-secret-key"


# =========================
# DATABASE
# =========================

def get_db():
    conn = sqlite3.connect("blog.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()

    # POSTS TABLE
    conn.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            author TEXT NOT NULL,
            category TEXT DEFAULT 'General',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # USERS TABLE
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # CREATE DEFAULT ADMIN
    conn.execute("""
        INSERT OR IGNORE INTO users
        (username, email, password, is_admin)
        VALUES (?, ?, ?, ?)
    """, (
        "admin",
        "admin@example.com",
        generate_password_hash("admin123"),
        1
    ))

    # COMMENTS TABLE
    conn.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (post_id) REFERENCES posts(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # COMMENT LIKES TABLE
    conn.execute("""
        CREATE TABLE IF NOT EXISTS comment_likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            comment_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, comment_id)
        )
    """)

    conn.commit()
    conn.close()


def add_missing_columns():

    conn = get_db()

    # USERS
    try:
        conn.execute("""
            ALTER TABLE users
            ADD COLUMN is_admin INTEGER DEFAULT 0
        """)
    except sqlite3.OperationalError:
        pass

    # POSTS CATEGORY
    try:
        conn.execute("""
            ALTER TABLE posts
            ADD COLUMN category TEXT DEFAULT 'General'
        """)
    except sqlite3.OperationalError:
        pass

    # POSTS IMAGE
    try:
        conn.execute("""
            ALTER TABLE posts
            ADD COLUMN image TEXT
        """)
    except sqlite3.OperationalError:
        pass

    # POSTS FEATURED
    try:
        conn.execute("""
            ALTER TABLE posts
            ADD COLUMN featured INTEGER DEFAULT 0
        """)
    except sqlite3.OperationalError:
        pass

    # POSTS VIEWS
    try:
        conn.execute("""
            ALTER TABLE posts
            ADD COLUMN views INTEGER DEFAULT 0
        """)
    except sqlite3.OperationalError:
        pass

    # COMMENTS USERNAME
    try:
        conn.execute("""
            ALTER TABLE comments
            ADD COLUMN username TEXT DEFAULT 'Anonymous'
        """)
    except sqlite3.OperationalError:
        pass

    # COMMENTS PARENT ID
    try:
        conn.execute("""
            ALTER TABLE comments
            ADD COLUMN parent_id INTEGER DEFAULT NULL
        """)
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()


# =========================
# DATABASE MIGRATIONS
# =========================

def add_missing_columns():

    conn = get_db()

    # Add is_admin if old users table doesn't have it
    try:

        conn.execute("""
            ALTER TABLE users
            ADD COLUMN is_admin INTEGER DEFAULT 0
        """)

    except sqlite3.OperationalError:

        pass


    # Add category if old posts table doesn't have it
    try:

        conn.execute("""
            ALTER TABLE posts
            ADD COLUMN category TEXT DEFAULT 'General'
        """)

    except sqlite3.OperationalError:

        pass


    conn.commit()
    conn.close()


# =========================
# ADMIN CHECK
# =========================

def admin_required():

    if not session.get("user_id"):
        return False

    if session.get("is_admin") != 1:
        return False

    return True


# =========================
# HOME
# =========================

@app.route("/")
def home():

    page = request.args.get("page", 1, type=int)

    per_page = 5

    offset = (page - 1) * per_page

    conn = get_db()

    featured_posts = conn.execute("""
        SELECT *
        FROM posts
        WHERE featured = 1
        ORDER BY created_at DESC
        LIMIT 3
    """).fetchall()

    posts = conn.execute("""
        SELECT *
        FROM posts
        WHERE featured = 0
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    """, (
        per_page,
        offset
    )).fetchall()

    total_posts = conn.execute("""
        SELECT COUNT(*)
        FROM posts
        WHERE featured = 0
    """).fetchone()[0]

    conn.close()

    total_pages = (
        total_posts + per_page - 1
    ) // per_page

    return render_template(
        "index.html",
        featured_posts=featured_posts,
        posts=posts,
        page=page,
        total_pages=total_pages
    )

# =========================
# VIEW POST
# =========================

@app.route("/post/<int:post_id>")
def post(post_id):

    conn = get_db()

    post = conn.execute("""
        SELECT *
        FROM posts
        WHERE id = ?
    """, (post_id,)).fetchone()

    if post is None:
        conn.close()
        return "Post not found", 404

    conn.execute("""
        UPDATE posts
        SET views = views + 1
        WHERE id = ?
    """, (post_id,))

    conn.commit()

    post = conn.execute("""
        SELECT *
        FROM posts
        WHERE id = ?
    """, (post_id,)).fetchone()

    conn.close()

    return render_template(
        "post.html",
        post=post
    )
# =====================
# CREATE POST
# =====================

@app.route("/create-post", methods=["GET", "POST"])
def create_post():

    if not admin_required():
        return "Access denied. Admins only.", 403

    if request.method == "POST":

        title = request.form["title"].strip()
        content = request.form["content"].strip()
        author = request.form["author"].strip()
        category = request.form["category"].strip()

        # Get uploaded image
        file = request.files.get("image")

        image_filename = None

        if file and file.filename:

            if not allowed_file(file.filename):
                return "Invalid image type.", 400

            image_filename = secure_filename(file.filename)

            base, extension = os.path.splitext(image_filename)

            counter = 1

            while os.path.exists(
                os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    image_filename
                )
            ):

                image_filename = (
                    f"{base}_{counter}{extension}"
                )

                counter += 1

            file.save(
                os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    image_filename
                )
            )

        conn = get_db()

        conn.execute("""
            INSERT INTO posts
            (title, content, author, category, image)
            VALUES (?, ?, ?, ?, ?)
        """, (
            title,
            content,
            author,
            category,
            image_filename
        ))

        conn.commit()
        conn.close()

        return redirect("/")

    return render_template("create_post.html")

# =========================
# EDIT POST
# =========================

@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
def edit_post(post_id):

    if not admin_required():
        return "Access denied. Admins only.", 403

    conn = get_db()

    post = conn.execute("""
        SELECT *
        FROM posts
        WHERE id = ?
    """, (post_id,)).fetchone()

    if post is None:
        conn.close()
        return "Post not found", 404

    if request.method == "POST":

        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        author = request.form.get("author", "").strip()
        category = request.form.get("category", "General").strip()

        # Keep existing image
        image_filename = post["image"]

        # Get new image
        file = request.files.get("image")

        if file and file.filename:

            if not allowed_file(file.filename):
                conn.close()
                return "Invalid image type.", 400

            filename = secure_filename(file.filename)

            base, extension = os.path.splitext(filename)

            counter = 1

            while os.path.exists(
                os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    filename
                )
            ):
                filename = f"{base}_{counter}{extension}"
                counter += 1

            # Save new image
            file.save(
                os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    filename
                )
            )

            image_filename = filename

        conn.execute("""
            UPDATE posts
            SET title = ?,
                content = ?,
                author = ?,
                category = ?,
                image = ?
            WHERE id = ?
        """, (
            title,
            content,
            author,
            category,
            image_filename,
            post_id
        ))

        conn.commit()

        updated_post = conn.execute("""
            SELECT *
            FROM posts
            WHERE id = ?
        """, (post_id,)).fetchone()

        conn.close()

        return redirect(
            url_for("post", post_id=post_id)
        )

    conn.close()

    return render_template(
        "edit_post.html",
        post=post
    )


# =========================
# DELETE POST
# =========================

@app.route(
    "/delete-post/<int:post_id>",
    methods=["POST"]
)
def delete_post(post_id):

    if not admin_required():
        return "Access denied. Admins only.", 403


    conn = get_db()

    conn.execute("""
        DELETE FROM posts
        WHERE id = ?
    """, (post_id,))

    conn.commit()
    conn.close()

    return redirect("/")


# =========================
# REGISTER
# =========================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]


        password_hash = generate_password_hash(
            password
        )


        conn = get_db()


        try:

            conn.execute("""
                INSERT INTO users
                (
                    username,
                    email,
                    password,
                    is_admin
                )

                VALUES (?, ?, ?, 0)
            """, (
                username,
                email,
                password_hash
            ))


            conn.commit()


        except sqlite3.IntegrityError:

            conn.close()

            return "Username or email already exists."


        conn.close()

        return redirect("/login")


    return render_template(
        "register.html"
    )


# =========================
# LOGIN
# =========================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]


        conn = get_db()

        user = conn.execute("""
            SELECT *
            FROM users
            WHERE username = ?
        """, (username,)).fetchone()

        conn.close()


        if user is None:

            return "Invalid username or password."


        if not check_password_hash(
            user["password"],
            password
        ):

            return "Invalid username or password."


        # Create login session
        session.clear()

        session["user_id"] = user["id"]

        session["username"] = user["username"]

        session["is_admin"] = int(
            user["is_admin"]
        )


        return redirect("/")


    return render_template(
        "login.html"
    )


# =========================
# LOGOUT
# =========================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


# =========================
# ADMIN DASHBOARD
# =========================

@app.route("/admin")
def admin_dashboard():

    if not admin_required():
        return "Access denied. Admins only.", 403

    conn = get_db()

    # Get posts
    posts = conn.execute("""
        SELECT *
        FROM posts
        ORDER BY created_at DESC
    """).fetchall()

    # Get users
    users = conn.execute("""
        SELECT
            id,
            username,
            email,
            is_admin,
            created_at
        FROM users
        ORDER BY created_at DESC
    """).fetchall()

    # Statistics
    total_users = conn.execute("""
        SELECT COUNT(*)
        FROM users
    """).fetchone()[0]

    total_posts = conn.execute("""
        SELECT COUNT(*)
        FROM posts
    """).fetchone()[0]

    total_comments = conn.execute("""
        SELECT COUNT(*)
        FROM comments
    """).fetchone()[0]

    total_likes = conn.execute("""
        SELECT COUNT(*)
        FROM likes
    """).fetchone()[0]

    conn.close()

    return render_template(
        "admin_dashboard.html",
        posts=posts,
        users=users,
        total_users=total_users,
        total_posts=total_posts,
        total_comments=total_comments,
        total_likes=total_likes
    )


# =========================
# SETUP FIRST ADMIN
# =========================

@app.route(
    "/setup-admin",
    methods=["GET", "POST"]
)
def setup_admin():

    conn = get_db()


    existing_admin = conn.execute("""
        SELECT id
        FROM users
        WHERE is_admin = 1
        LIMIT 1
    """).fetchone()


    if existing_admin:

        conn.close()

        return "Admin account already exists."


    if request.method == "POST":

        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]


        password_hash = generate_password_hash(
            password
        )


        try:

            conn.execute("""
                INSERT INTO users
                (
                    username,
                    email,
                    password,
                    is_admin
                )

                VALUES (?, ?, ?, 1)
            """, (
                username,
                email,
                password_hash
            ))


            conn.commit()


        except sqlite3.IntegrityError:

            conn.close()

            return "Username or email already exists."


        conn.close()

        return redirect("/login")


    conn.close()

    return render_template(
        "setup_admin.html"
    )
    
    
# =========================
#SEARCH POST
# =========================

@app.route("/search")
def search():

    query = request.args.get("q", "").strip()

    conn = get_db()

    if query:

        posts = conn.execute("""
            SELECT *
            FROM posts
            WHERE title LIKE ?
               OR content LIKE ?
               OR author LIKE ?
            ORDER BY created_at DESC
        """, (
            f"%{query}%",
            f"%{query}%",
            f"%{query}%"
        )).fetchall()

    else:

        posts = []

    conn.close()

    return render_template(
        "search.html",
        posts=posts,
        query=query
    )
    
    
# ========================
# CATEGORY
# ========================

@app.route("/category/<category_name>")
def category(category_name):

    conn = get_db()

    posts = conn.execute("""
        SELECT *
        FROM posts
        WHERE category = ?
        ORDER BY created_at DESC
    """, (category_name,)).fetchall()

    conn.close()

    return render_template(
        "category.html",
        posts=posts,
        category=category_name
    )
    
    
# =======================
# COMMENT
# =======================

@app.route(
    "/post/<int:post_id>/comment",
    methods=["POST"]
)
def add_comment(post_id):

    if not session.get("user_id"):
        return redirect("/login")

    content = request.form["content"].strip()

    if not content:
        return redirect(f"/post/{post_id}")

    conn = get_db()

    post = conn.execute("""
        SELECT id
        FROM posts
        WHERE id = ?
    """, (post_id,)).fetchone()

    if post is None:
        conn.close()
        return "Post not found", 404

    conn.execute("""
        INSERT INTO comments
        (post_id, user_id, content)
        VALUES (?, ?, ?)
    """, (
        post_id,
        session["user_id"],
        content
    ))

    conn.commit()
    conn.close()

    return redirect(f"/post/{post_id}")
    
    
# ======================
# ADMIN COMMENT
# ======================

@app.route("/admin/comments")
def admin_comments():

    if not admin_required():
        return "Access denied. Admins only.", 403

    conn = get_db()

    comments = conn.execute("""
        SELECT
            comments.id,
            comments.content,
            comments.created_at,
            users.username,
            posts.title,
            posts.id AS post_id

        FROM comments

        JOIN users
            ON comments.user_id = users.id

        JOIN posts
            ON comments.post_id = posts.id

        ORDER BY comments.created_at DESC
    """).fetchall()

    conn.close()

    return render_template(
        "admin_comments.html",
        comments=comments
    )
    
    
# =========================
# DELETE COMMENT
# =========================

@app.route(
    "/admin/comments/delete/<int:comment_id>",
    methods=["POST"]
)
def delete_comment(comment_id):

    if not admin_required():
        return "Access denied. Admins only.", 403

    conn = get_db()

    conn.execute("""
        DELETE FROM comments
        WHERE id = ?
    """, (comment_id,))

    conn.commit()
    conn.close()

    return redirect("/admin/comments")
    
    
# ========================
# LIKE ROUTE
# ========================

@app.route("/post/<int:post_id>/like", methods=["POST"])
def like_post(post_id):

    # User must be logged in
    if not session.get("user_id"):
        return redirect("/login")

    user_id = session["user_id"]

    conn = get_db()

    # Check if this user already liked the post
    existing_like = conn.execute("""
        SELECT id
        FROM likes
        WHERE post_id = ?
        AND user_id = ?
    """, (post_id, user_id)).fetchone()

    if existing_like:

        # Remove the like
        conn.execute("""
            DELETE FROM likes
            WHERE post_id = ?
            AND user_id = ?
        """, (post_id, user_id))

    else:

        # Add the like
        conn.execute("""
            INSERT INTO likes
            (post_id, user_id)
            VALUES (?, ?)
        """, (post_id, user_id))

    conn.commit()
    conn.close()

    return redirect(f"/post/{post_id}")
    
    
# ======================
# PROFILE ROUE
# ======================

@app.route("/profile")
def profile():

    if not session.get("user_id"):
        return redirect("/login")

    conn = get_db()

    user = conn.execute("""
        SELECT
            id,
            username,
            email,
            created_at
        FROM users
        WHERE id = ?
    """, (session["user_id"],)).fetchone()

    comments = conn.execute("""
        SELECT
            comments.content,
            comments.created_at,
            posts.title,
            posts.id AS post_id
        FROM comments
        JOIN posts
            ON comments.post_id = posts.id
        WHERE comments.user_id = ?
        ORDER BY comments.created_at DESC
    """, (session["user_id"],)).fetchall()

    conn.close()

    if user is None:
        session.clear()
        return redirect("/login")

    return render_template(
        "profile.html",
        user=user,
        comments=comments
    )
    
    
# ====================
# EDIT PROFILE
# ====================

@app.route("/edit-profile", methods=["GET", "POST"])
def edit_profile():

    if not session.get("user_id"):
        return redirect("/login")

    conn = get_db()

    user = conn.execute("""
        SELECT *
        FROM users
        WHERE id = ?
    """, (session["user_id"],)).fetchone()

    if user is None:
        conn.close()
        session.clear()
        return redirect("/login")

    if request.method == "POST":

        username = request.form["username"].strip()
        email = request.form["email"].strip()
        password = request.form["password"]

        if not username or not email:
            conn.close()
            return "Username and email are required."

        try:

            if password.strip():

                password_hash = generate_password_hash(password)

                conn.execute("""
                    UPDATE users
                    SET username = ?,
                        email = ?,
                        password = ?
                    WHERE id = ?
                """, (
                    username,
                    email,
                    password_hash,
                    session["user_id"]
                ))

            else:

                conn.execute("""
                    UPDATE users
                    SET username = ?,
                        email = ?
                    WHERE id = ?
                """, (
                    username,
                    email,
                    session["user_id"]
                ))

            conn.commit()

        except sqlite3.IntegrityError:

            conn.close()

            return "Username or email already exists."

        conn.close()

        # Update the session username
        session["username"] = username

        return redirect("/profile")

    conn.close()

    return render_template(
        "edit_profile.html",
        user=user
    )
    
    
# ================
# UPLOADS
# ================

@app.route("/uploads/<filename>")
def uploaded_file(filename):

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )


# =================
# FEACTURE
# ==================

@app.route("/feature-post/<int:post_id>")
def feature_post(post_id):

    if not admin_required():
        return "Access denied. Admins only.", 403

    conn = get_db()

    conn.execute("""
        UPDATE posts
        SET featured = 1
        WHERE id = ?
    """, (post_id,))

    conn.commit()
    conn.close()

    return redirect("/admin")
    
    
#=====================
# UNFEATURE
#======================

@app.route("/unfeature-post/<int:post_id>")
def unfeature_post(post_id):

    if not admin_required():
        return "Access denied. Admins only.", 403

    conn = get_db()

    conn.execute("""
        UPDATE posts
        SET featured = 0
        WHERE id = ?
    """, (post_id,))

    conn.commit()
    conn.close()

    return redirect("/admin")


# =========================
# START APPLICATION
# =========================

# Initialize database when the application starts
init_db()
add_missing_columns()


if __name__ == "__main__":
    app.run(debug=True)
