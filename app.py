from flask import Flask, request, jsonify
import mysql.connector
from flask_cors import CORS
from flask import render_template
from werkzeug.security import generate_password_hash, check_password_hash
import os
from werkzeug.utils import secure_filename


app = Flask(__name__)
CORS(app)
# for image 
UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Anmol@123",
    database="lost_found"
)

def is_admin_or_security(user_id):
    cursor = db.cursor(dictionary=True)

    cursor.execute(
        "SELECT role FROM Users WHERE user_id = %s",
        (user_id,)
    )

    user = cursor.fetchone()

    return user and user["role"] in ("admin", "security")

@app.route("/")
def home():
    return "Backend Running ✅"


# add items
@app.route("/add-item", methods=["POST"])
def add_item():
    try:
        data = request.form
        image = request.files.get("image")

        image_url = None

        if image and image.filename:
            filename = secure_filename(image.filename)
            image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            image.save(image_path)
            image_url = "/" + image_path

        cursor = db.cursor()

        sql = """
        INSERT INTO Items 
        (title, description, category, color, brand, location, event_date, report_type, status, reported_by, image_url)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        cursor.execute(sql, (
            data["title"],
            data.get("description"),
            data["category"],
            data.get("color"),
            data.get("brand"),
            data["location"],
            data["event_date"],
            data["report_type"],
            "open",
            data["reported_by"],
            image_url
        ))

        db.commit()

        return jsonify({"message": "Item added successfully with image"})

    except Exception as e:
        return jsonify({"error": str(e)})


# items
@app.route("/items", methods=["GET"])
def get_items():
    try:
        cursor = db.cursor(dictionary=True)

        cursor.execute("SELECT * FROM Items")
        items = cursor.fetchall()

        return jsonify(items)

    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/hello")
def hello():
    return "HELLO WORKING"

@app.route("/match/<keyword>", methods=["GET"])
def match_items(keyword):
    try:
        cursor = db.cursor(dictionary=True)

        status = request.args.get("status")
        report_type = request.args.get("report_type")
        category = request.args.get("category")

        like_pattern = f"%{keyword}%"

        query = """
        SELECT *,
        (
            (title LIKE %s) * 4 +
            (description LIKE %s) * 2 +
            (category LIKE %s) * 2 +
            (color LIKE %s) * 2 +
            (brand LIKE %s) * 2 +
            (location LIKE %s) * 1 +
            (report_type LIKE %s) * 1
        ) AS score
        FROM Items
        WHERE 
            (
                title LIKE %s OR 
                description LIKE %s OR 
                category LIKE %s OR 
                color LIKE %s OR 
                brand LIKE %s OR 
                location LIKE %s OR
                report_type LIKE %s
            )
        """

        values = [
            like_pattern, like_pattern, like_pattern, like_pattern,
            like_pattern, like_pattern, like_pattern,
            like_pattern, like_pattern, like_pattern, like_pattern,
            like_pattern, like_pattern, like_pattern
        ]

        if status:
            query += " AND status = %s"
            values.append(status)

        if report_type:
            query += " AND report_type = %s"
            values.append(report_type)

        if category:
            query += " AND category = %s"
            values.append(category)

        query += " ORDER BY score DESC, created_at DESC"

        cursor.execute(query, tuple(values))
        results = cursor.fetchall()

        return jsonify({
            "matches": results
        })

    except Exception as e:
        return jsonify({"error": str(e)})

    
@app.route("/ui")
def ui():
    return render_template("index.html")

# login page---
@app.route("/register", methods=["POST"])
def register():
    try:
        data = request.get_json()
        cursor = db.cursor()

        password_hash = generate_password_hash(data["password"])

        query = """
        INSERT INTO Users (name, email, password_hash, student_id, role, is_verified)
        VALUES (%s, %s, %s, %s, %s, %s)
        """

        cursor.execute(query, (
            data["name"],
            data["email"],
            password_hash,
            data.get("student_id"),
            data.get("role", "student"),
            False
        ))

        db.commit()

        return jsonify({"message": "User registered successfully. Verification pending."})

    except Exception as e:
        return jsonify({"error": str(e)})

# register-page
@app.route("/register-page")
def register_page():
    return render_template("register.html")

# check email + password


@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json()
        cursor = db.cursor(dictionary=True)

        query = "SELECT * FROM Users WHERE email = %s"
        cursor.execute(query, (data["email"],))
        user = cursor.fetchone()

        # Check user + password
        if user and check_password_hash(user["password_hash"], data["password"]):

            # Check verification
            if not user["is_verified"]:
                return jsonify({
                    "error": "Your account is not verified yet. Please contact admin/security."
                }), 403

            # Successful login
            return jsonify({
                "message": "Login successful",
                "user": {
                    "user_id": user["user_id"],
                    "name": user["name"],
                    "email": user["email"],
                    "student_id": user["student_id"],
                    "role": user["role"],
                    "is_verified": user["is_verified"]
                }
            })

        else:
            return jsonify({"error": "Invalid credentials"}), 401

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# admin-page
@app.route("/admin-page")
def admin_page():
    return render_template("admin.html")
 
#pending user
@app.route("/pending-users", methods=["GET"])
def pending_users():
    try:
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT user_id, name, email, student_id, role, is_verified, created_at
            FROM Users
            WHERE is_verified = FALSE
            ORDER BY created_at DESC
        """)

        users = cursor.fetchall()
        return jsonify(users)

    except Exception as e:
        return jsonify({"error": str(e)})

# verify user
@app.route("/verify-user/<int:user_id>", methods=["PUT"])
def verify_user(user_id):
    try:
        data = request.get_json()
        reviewed_by = data.get("reviewed_by")

        if not reviewed_by or not is_admin_or_security(reviewed_by):
            return jsonify({"error": "Only admin or security can verify users"}), 403

        cursor = db.cursor()

        cursor.execute(
            "UPDATE Users SET is_verified = TRUE WHERE user_id = %s",
            (user_id,)
        )

        cursor.execute("""
            INSERT INTO AuditLogs (user_id, action, entity_type, entity_id)
            VALUES (%s, %s, %s, %s)
        """, (reviewed_by, "Verified user", "User", user_id))

        db.commit()

        return jsonify({"message": "User verified successfully"})

    except Exception as e:
        return jsonify({"error": str(e)})

# claims
@app.route("/claim", methods=["POST"])
def claim_item():
    try:
        data = request.get_json()
        cursor = db.cursor()

        query = """
        INSERT INTO Claims (item_id, claimant_id, proof_description)
        VALUES (%s, %s, %s)
        """

        cursor.execute(query, (
            data["item_id"],
            data["claimant_id"],
            data["proof_description"]
        ))

        cursor.execute(
            "UPDATE Items SET status = 'under_review' WHERE item_id = %s",
            (data["item_id"],)
        )

        db.commit()

        return jsonify({"message": "Claim request sent for review"})

    except Exception as e:
        return jsonify({"error": str(e)})

    
# approve 
@app.route("/approve-claim/<int:claim_id>", methods=["PUT"])
def approve_claim(claim_id):
    try:
        data = request.get_json()
        reviewed_by = data.get("reviewed_by")
        if not reviewed_by or not is_admin_or_security(reviewed_by):
            return jsonify({"error": "Only admin or security can approve claims"}), 403


        cursor = db.cursor()

        cursor.execute("SELECT item_id FROM Claims WHERE claim_id = %s", (claim_id,))
        result = cursor.fetchone()

        if not result:
            return jsonify({"error": "Claim not found"})

        item_id = result[0]

        cursor.execute(
            """
            UPDATE Claims 
            SET status = 'approved', reviewed_by = %s, reviewed_at = CURRENT_TIMESTAMP
            WHERE claim_id = %s
            """,
            (reviewed_by, claim_id)
        )

        cursor.execute(
            "UPDATE Items SET status = 'claimed' WHERE item_id = %s",
            (item_id,)
        )

        cursor.execute(
            """
            INSERT INTO AuditLogs (user_id, action, entity_type, entity_id)
            VALUES (%s, %s, %s, %s)
            """,
            (reviewed_by, "Approved claim", "Claim", claim_id)
        )

        db.commit()

        return jsonify({"message": "Claim approved"})

    except Exception as e:
        return jsonify({"error": str(e)})


# reject claim
@app.route("/reject-claim/<int:claim_id>", methods=["PUT"])
def reject_claim(claim_id):
    try:
        data = request.get_json()
        reviewed_by = data.get("reviewed_by")
        if not reviewed_by or not is_admin_or_security(reviewed_by):
            return jsonify({"error": "Only admin or security can reject claims"}), 403


        cursor = db.cursor()

        cursor.execute("SELECT item_id FROM Claims WHERE claim_id = %s", (claim_id,))
        result = cursor.fetchone()

        if not result:
            return jsonify({"error": "Claim not found"})

        item_id = result[0]

        cursor.execute(
            """
            UPDATE Claims 
            SET status = 'rejected', reviewed_by = %s, reviewed_at = CURRENT_TIMESTAMP
            WHERE claim_id = %s
            """,
            (reviewed_by, claim_id)
        )

        cursor.execute(
            "UPDATE Items SET status = 'open' WHERE item_id = %s",
            (item_id,)
        )

        cursor.execute(
            """
            INSERT INTO AuditLogs (user_id, action, entity_type, entity_id)
            VALUES (%s, %s, %s, %s)
            """,
            (reviewed_by, "Rejected claim", "Claim", claim_id)
        )

        db.commit()

        return jsonify({"message": "Claim rejected"})

    except Exception as e:
        return jsonify({"error": str(e)})

    
# login page
@app.route("/login-page")
def login_page():
    return render_template("login.html")


    
# claime name
@app.route("/get-claims", methods=["GET"])
def get_claims():
    try:
        cursor = db.cursor(dictionary=True)

        query = """
        SELECT 
            c.claim_id,
            c.status,
            c.proof_description,
            c.created_at,
            i.title AS item_name,
            i.category,
            i.location,
            u.name AS claimant_name,
            u.student_id AS claimant_roll_no

        FROM Claims c
        JOIN Items i ON c.item_id = i.item_id
        JOIN Users u ON c.claimant_id = u.user_id
        ORDER BY c.created_at DESC
        """

        cursor.execute(query)
        data = cursor.fetchall()

        return jsonify(data)

    except Exception as e:
        return jsonify({"error": str(e)})

# my reports
@app.route("/my-reports/<int:user_id>", methods=["GET"])
def my_reports(user_id):
    try:
        cursor = db.cursor(dictionary=True)

        query = """
        SELECT *
        FROM Items
        WHERE reported_by = %s
        ORDER BY created_at DESC
        """

        cursor.execute(query, (user_id,))
        reports = cursor.fetchall()

        return jsonify(reports)

    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/my-claims/<int:user_id>", methods=["GET"])
def my_claims(user_id):
    try:
        cursor = db.cursor(dictionary=True)

        query = """
        SELECT 
            c.claim_id,
            c.status,
            c.proof_description,
            c.created_at,
            i.title AS item_name,
            i.category,
            i.location,
            i.report_type,
            i.status AS item_status
        FROM Claims c
        JOIN Items i ON c.item_id = i.item_id
        WHERE c.claimant_id = %s
        ORDER BY c.created_at DESC
        """

        cursor.execute(query, (user_id,))
        claims = cursor.fetchall()

        return jsonify(claims)

    except Exception as e:
        return jsonify({"error": str(e)})

# admin stats
@app.route("/admin-stats", methods=["GET"])
def admin_stats():
    try:
        cursor = db.cursor(dictionary=True)

        stats = {}

        cursor.execute("SELECT COUNT(*) AS total_users FROM Users")
        stats["total_users"] = cursor.fetchone()["total_users"]

        cursor.execute("SELECT COUNT(*) AS verified_users FROM Users WHERE is_verified = TRUE")
        stats["verified_users"] = cursor.fetchone()["verified_users"]

        cursor.execute("SELECT COUNT(*) AS pending_users FROM Users WHERE is_verified = FALSE")
        stats["pending_users"] = cursor.fetchone()["pending_users"]

        cursor.execute("SELECT COUNT(*) AS total_items FROM Items")
        stats["total_items"] = cursor.fetchone()["total_items"]

        cursor.execute("SELECT COUNT(*) AS lost_items FROM Items WHERE report_type = 'lost'")
        stats["lost_items"] = cursor.fetchone()["lost_items"]

        cursor.execute("SELECT COUNT(*) AS found_items FROM Items WHERE report_type = 'found'")
        stats["found_items"] = cursor.fetchone()["found_items"]

        cursor.execute("SELECT COUNT(*) AS pending_claims FROM Claims WHERE status = 'pending'")
        stats["pending_claims"] = cursor.fetchone()["pending_claims"]

        cursor.execute("SELECT COUNT(*) AS approved_claims FROM Claims WHERE status = 'approved'")
        stats["approved_claims"] = cursor.fetchone()["approved_claims"]

        cursor.execute("SELECT COUNT(*) AS rejected_claims FROM Claims WHERE status = 'rejected'")
        stats["rejected_claims"] = cursor.fetchone()["rejected_claims"]

        cursor.execute("SELECT COUNT(*) AS returned_items FROM Items WHERE status = 'returned'")
        stats["returned_items"] = cursor.fetchone()["returned_items"]

        return jsonify(stats)

    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/mark-returned/<int:claim_id>", methods=["PUT"])
def mark_returned(claim_id):
    try:
        data = request.get_json()
        reviewed_by = data.get("reviewed_by")

        if not reviewed_by or not is_admin_or_security(reviewed_by):
            return jsonify({"error": "Only admin or security can mark items as returned"}), 403

        cursor = db.cursor()

        cursor.execute(
            "SELECT item_id FROM Claims WHERE claim_id = %s AND status = 'approved'",
            (claim_id,)
        )

        result = cursor.fetchone()

        if not result:
            return jsonify({"error": "Approved claim not found"})

        item_id = result[0]

        cursor.execute(
            "UPDATE Items SET status = 'returned' WHERE item_id = %s",
            (item_id,)
        )

        cursor.execute("""
            INSERT INTO AuditLogs (user_id, action, entity_type, entity_id)
            VALUES (%s, %s, %s, %s)
        """, (reviewed_by, "Marked item as returned", "Claim", claim_id))

        db.commit()

        return jsonify({"message": "Item marked as returned successfully"})

    except Exception as e:
        return jsonify({"error": str(e)})


if __name__ == "__main__":
    app.run(debug=True)