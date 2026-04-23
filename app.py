from flask import Flask, render_template, jsonify, request
import pymysql
import json
import os
from datetime import datetime

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

JSON_PATH = os.path.join(BASE_DIR, "all_generated_predictions_extracted_merged_data_G.json")
SCORING_RULES_PATH = os.path.join(BASE_DIR, "评分准则.json")
TAG_OPTIONS_PATH = os.path.join(BASE_DIR, "概括词.json")


def load_json_file(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"缺少文件: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


ALL_DATA = load_json_file(JSON_PATH)
SCORING_RULES = load_json_file(SCORING_RULES_PATH)
TAG_OPTIONS = load_json_file(TAG_OPTIONS_PATH)

ID_DATA_MAP = {str(d["idx_id"]): d for d in ALL_DATA}
ALL_IDS = list(ID_DATA_MAP.keys())
SCORE_DIMENSIONS = SCORING_RULES.get("评分维度", [])


def get_db():
    return pymysql.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False
    )


@app.route("/")
def index():
    return render_template(
        "index.html",
        score_dimensions=SCORE_DIMENSIONS,
        score_note=SCORING_RULES.get("评分说明", ""),
        tag_options=TAG_OPTIONS
    )


@app.route("/get_one")
def get_one():
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT idx_id FROM scores")
            scored = {str(r["idx_id"]) for r in cursor.fetchall()}

            cursor.execute("SELECT idx_id FROM task_lock")
            locked = {str(r["idx_id"]) for r in cursor.fetchall()}

            for idx in ALL_IDS:
                if idx in scored or idx in locked:
                    continue

                try:
                    cursor.execute(
                        "INSERT INTO task_lock (idx_id) VALUES (%s)",
                        (idx,)
                    )
                    conn.commit()

                    return jsonify({
                        "data": ID_DATA_MAP[idx],
                        "remain": len(ALL_IDS) - len(scored)
                    })

                except Exception:
                    continue

            return jsonify(None)

    finally:
        conn.close()


@app.route("/submit_score", methods=["POST"])
def submit_score():
    data = request.get_json()

    if not data:
        return jsonify({"status": "error", "message": "没有收到数据"}), 400

    idx_id = str(data.get("idx_id", "")).strip()
    if not idx_id:
        return jsonify({"status": "error", "message": "缺少 idx_id"}), 400

    conn = get_db()
    try:
        with conn.cursor() as cursor:
            sql = """
            INSERT INTO scores
            (
                idx_id,
                s1, s1_tags, m1,
                s2, s2_tags, m2,
                s3, s3_tags, m3,
                s4, s4_tags, m4,
                s5, s5_tags, m5,
                s6, s6_tags, m6,
                s7, s7_tags, m7,
                submitted_at
            )
            VALUES (
                %s,%s,%s,%s,
                %s,%s,%s,
                %s,%s,%s,
                %s,%s,%s,
                %s,%s,%s,
                %s,%s,%s,
                %s,%s,%s,
                %s
            )
            """

            cursor.execute(sql, (
                idx_id,
                data.get("s1"), json.dumps(data.get("s1_tags", []), ensure_ascii=False), data.get("m1", ""),
                data.get("s2"), json.dumps(data.get("s2_tags", []), ensure_ascii=False), data.get("m2", ""),
                data.get("s3"), json.dumps(data.get("s3_tags", []), ensure_ascii=False), data.get("m3", ""),
                data.get("s4"), json.dumps(data.get("s4_tags", []), ensure_ascii=False), data.get("m4", ""),
                data.get("s5"), json.dumps(data.get("s5_tags", []), ensure_ascii=False), data.get("m5", ""),
                data.get("s6"), json.dumps(data.get("s6_tags", []), ensure_ascii=False), data.get("m6", ""),
                data.get("s7"), json.dumps(data.get("s7_tags", []), ensure_ascii=False), data.get("m7", ""),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))

            cursor.execute("DELETE FROM task_lock WHERE idx_id=%s", (idx_id,))

        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


@app.route("/view_scores")
def view_scores():
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM scores ORDER BY submitted_at DESC")
            rows = cursor.fetchall()
            return jsonify(rows)
    finally:
        conn.close()


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)