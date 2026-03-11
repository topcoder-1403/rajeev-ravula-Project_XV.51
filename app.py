import os
import uuid
import datetime
import mimetypes

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from pymongo import MongoClient
from bson import ObjectId
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

# ---------------- CONFIG ---------------- #

app.config['MAX_CONTENT_LENGTH'] = 2048 * 1024 * 1024

UPLOAD_FOLDER = "local_uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ADMIN_KEY = "superadmin123"

# ---------------- DATABASE ---------------- #

MONGODB_URI = "mongodb+srv://tanishqravula:umaraghu1116@cluster0.7zkonq1.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

client = MongoClient(MONGODB_URI)

db = client["time_capsule_db"]
capsules_col = db["capsules"]

print("✅ MongoDB Connected")

# ---------------- HELPERS ---------------- #

def is_admin():
    key = request.headers.get("x-admin-key")
    return key == ADMIN_KEY


def get_media_type(mime_type, filename):

    if not mime_type:
        mime_type, _ = mimetypes.guess_type(filename)

    if mime_type:

        if mime_type.startswith("video/"):
            return "video"

        if mime_type.startswith("image/"):
            return "image"

        if mime_type.startswith("audio/"):
            return "audio"

        if mime_type.startswith("text/"):
            return "text"

    return "other"

# ---------------- ROUTES ---------------- #

# GET CAPSULES
@app.route("/api/capsules", methods=["GET"])
def get_capsules():

    try:

        capsules = list(
            capsules_col.find().sort("createdAt", -1)
        )

        for c in capsules:
            c["_id"] = str(c["_id"])

        return jsonify(capsules)

    except Exception as e:

        return jsonify({"error": str(e)}), 500


# CREATE CAPSULE
@app.route("/api/capsules", methods=["POST"])
def create_capsule():

    try:

        data = request.form
        files = request.files.getlist("files")

        media = []

        for file in files:

            if file.filename == "":
                continue

            original_filename = secure_filename(file.filename)

            unique_filename = f"{uuid.uuid4().hex}_{original_filename}"

            file_path = os.path.join(UPLOAD_FOLDER, unique_filename)

            file.save(file_path)

            media_type = get_media_type(
                file.content_type,
                file.filename
            )

            media.append({

                "id": uuid.uuid4().hex,

                "type": media_type,

                "url": f"/api/files/{unique_filename}",

                "localFilename": unique_filename,

                "originalName": original_filename,

                "mimeType": file.content_type
            })

        youtube_url = data.get("youtubeUrl")

        if youtube_url:

            media.append({

                "id": uuid.uuid4().hex,

                "type": "youtube",

                "url": youtube_url
            })

        new_capsule = {

            "title": data.get("title", "Time Capsule Entry"),

            "description": data.get(
                "description",
                "A new time capsule entry"
            ),

            "date": data.get("date"),

            "media": media,

            "createdAt": datetime.datetime.utcnow(),

            "createdBy": data.get("createdBy", "admin")
        }

        result = capsules_col.insert_one(new_capsule)

        return jsonify({
            "message": "Capsule created",
            "id": str(result.inserted_id)
        }), 201

    except Exception as e:

        return jsonify({"error": str(e)}), 500


# SERVE FILE
@app.route("/api/files/<filename>")
def serve_file(filename):

    try:

        return send_from_directory(
            UPLOAD_FOLDER,
            filename,
            as_attachment=False
        )

    except Exception:

        return jsonify({"error": "File not found"}), 404


# DELETE ENTIRE CAPSULE (ADMIN)
@app.route("/api/capsules/<capsule_id>", methods=["DELETE"])
def delete_capsule(capsule_id):

    if not is_admin():
        return jsonify({"error": "Admin access required"}), 403

    try:

        oid = ObjectId(capsule_id)

        capsule = capsules_col.find_one({"_id": oid})

        if not capsule:
            return jsonify({"error": "Capsule not found"}), 404

        for item in capsule.get("media", []):

            if "localFilename" in item:

                file_path = os.path.join(
                    UPLOAD_FOLDER,
                    item["localFilename"]
                )

                if os.path.exists(file_path):
                    os.remove(file_path)

        capsules_col.delete_one({"_id": oid})

        return jsonify({"message": "Capsule deleted successfully"})

    except Exception as e:

        return jsonify({"error": str(e)}), 500


# DELETE SINGLE FILE FROM CAPSULE
@app.route("/api/capsules/<capsule_id>/file/<file_id>", methods=["DELETE"])
def delete_file(capsule_id, file_id):

    if not is_admin():
        return jsonify({"error": "Admin access required"}), 403

    try:

        oid = ObjectId(capsule_id)

        capsule = capsules_col.find_one({"_id": oid})

        if not capsule:
            return jsonify({"error": "Capsule not found"}), 404

        updated_media = []

        for item in capsule.get("media", []):

            if item.get("id") == file_id:

                if "localFilename" in item:

                    file_path = os.path.join(
                        UPLOAD_FOLDER,
                        item["localFilename"]
                    )

                    if os.path.exists(file_path):
                        os.remove(file_path)

            else:
                updated_media.append(item)

        capsules_col.update_one(

            {"_id": oid},

            {"$set": {"media": updated_media}}
        )

        return jsonify({"message": "File deleted successfully"})

    except Exception as e:

        return jsonify({"error": str(e)}), 500


# ---------------- RUN ---------------- #

if __name__ == "__main__":

    print("🚀 Server running on http://localhost:5000")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )