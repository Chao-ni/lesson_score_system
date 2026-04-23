from flask import Flask, render_template, jsonify, request
import pymysql
import json
from datetime import datetime
import os

app = Flask(__name__)

# =========================
# 你的JSON数据路径
# =========================
# JSON_PATH = r"C:\Users\Admin\Desktop\fsdownload\predict_outputs_extracted_0209\all_generated_predictions_extracted_merged_data_G.json"
# SCORING_RULES_PATH = "评分准则.json"
# TAG_OPTIONS_PATH = "概括词.json"
# APP_STATE_PATH = "session_state.json"
# CURRENT_TABLE = "scores"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

JSON_PATH = os.path.join(BASE_DIR, "all_generated_predictions_extracted_merged_data_G.json")
SCORING_RULES_PATH = os.path.join(BASE_DIR, "评分准则.json")
TAG_OPTIONS_PATH = os.path.join(BASE_DIR, "概括词.json")
APP_STATE_PATH = os.path.join(BASE_DIR, "session_state.json")

# ==========================
# 启动时读取一次JSON
# ==========================
with open(JSON_PATH, "r", encoding="utf-8") as f:
    ALL_DATA = json.load(f)
ID_DATA_MAP = {d["idx_id"]: d for d in ALL_DATA}
ALL_IDS = list(ID_DATA_MAP.keys())

with open(SCORING_RULES_PATH, "r", encoding="utf-8") as f:
    SCORING_RULES = json.load(f)

with open(TAG_OPTIONS_PATH, "r", encoding="utf-8") as f:
    TAG_OPTIONS = json.load(f)

SCORE_DIMENSIONS = SCORING_RULES["评分维度"]
# =========================
# MySQL数据库连接配置
# =========================
# def get_db():
#
#     conn = pymysql.connect(
#         host="localhost",
#         user="root",          # 你的MySQL用户名
#         password="123456",    # 改成你的MySQL密码
#         database="lesson_eval",
#         charset="utf8mb4"
#     )
#
#     return conn
# def get_db():
#     conn = pymysql.connect(
#         host=os.environ.get("centerbeam.proxy.rlwy.net"),
#         user=os.environ.get("root"),
#         password=os.environ.get("fyqcyclFddWXgBhTaAuUkLhbClCDLaYu"),
#         database=os.environ.get("railway"),
#         charset="utf8mb4"
#     )
#     return conn
CURRENT_TABLE = "scores_round2"
def get_db():
    conn = pymysql.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        charset="utf8mb4",
        autocommit=False
    )
    return conn

def load_app_state():

    if not os.path.exists(APP_STATE_PATH):
        return {}

    with open(APP_STATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_app_state(state):

    with open(APP_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def get_existing_columns(cursor, table_name):

    cursor.execute(f"SHOW COLUMNS FROM {table_name}")
    return {row[0] for row in cursor.fetchall()}


def ensure_table_schema(cursor, table_name):

    existing_columns = get_existing_columns(cursor, table_name)
    required_columns = {
        "submitted_at": "DATETIME NULL",
    }

    for index in range(1, 8):
        required_columns[f"s{index}_tags"] = "TEXT NULL"
        required_columns[f"m{index}"] = "VARCHAR(20) NULL"

    for column_name, column_type in required_columns.items():
        if column_name not in existing_columns:
            cursor.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
            )


def table_exists(cursor, table_name):

    cursor.execute("SHOW TABLES LIKE %s", (table_name,))
    return cursor.fetchone() is not None


def get_table_score_count(cursor, table_name):

    if not table_exists(cursor, table_name):
        return 0

    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    row = cursor.fetchone()
    return row[0] if row else 0


def clear_task_lock(cursor):

    try:
        cursor.execute("DELETE FROM task_lock")
    except:
        pass


def create_new_round_table(cursor):

    cursor.execute("SHOW TABLES LIKE 'scores_round%'")
    tables = cursor.fetchall()
    nums = []

    for t in tables:
        name = t[0]
        if name.startswith("scores_round"):
            nums.append(int(name.replace("scores_round", "")))

    round_num = max(nums) + 1 if nums else 1
    new_table = f"scores_round{round_num}"

    cursor.execute(f"CREATE TABLE {new_table} LIKE scores")
    ensure_table_schema(cursor, new_table)
    return new_table


def get_resume_table(cursor):

    state = load_app_state()
    saved_table = state.get("current_table")

    if saved_table and table_exists(cursor, saved_table):
        return saved_table

    if table_exists(cursor, CURRENT_TABLE):
        ensure_table_schema(cursor, CURRENT_TABLE)
        return CURRENT_TABLE

    return None


# =========================
# 获取已评分ID（防止重复评分）
# =========================
def get_scored_ids():

    conn = get_db()
    cursor = conn.cursor()

    # cursor.execute("SELECT idx_id FROM scores")
    cursor.execute(f"SELECT idx_id FROM {CURRENT_TABLE}")
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return set([r[0] for r in rows])


# =========================
# 首页
# =========================
@app.route("/")
def index():

    conn = get_db()
    cursor = conn.cursor()
    resume_table = get_resume_table(cursor)
    resume_count = get_table_score_count(cursor, resume_table) if resume_table else 0
    cursor.close()
    conn.close()

    return render_template(
        "setup.html",
        resume_table=resume_table,
        resume_count=resume_count
    )


@app.route("/score")
def score_page():

    return render_template(
        "index.html",
        score_dimensions=SCORE_DIMENSIONS,
        score_note=SCORING_RULES.get("评分说明", ""),
        tag_options=TAG_OPTIONS,
        current_table=CURRENT_TABLE
    )


@app.route("/start_session", methods=["POST"])
def start_session():

    global CURRENT_TABLE

    mode = request.form.get("mode", "")

    conn = get_db()
    cursor = conn.cursor()

    if mode == "new":
        CURRENT_TABLE = create_new_round_table(cursor)
    else:
        resume_table = get_resume_table(cursor)

        if not resume_table:
            resume_table = create_new_round_table(cursor)

        CURRENT_TABLE = resume_table
        ensure_table_schema(cursor, CURRENT_TABLE)

    clear_task_lock(cursor)
    conn.commit()

    save_app_state({
        "current_table": CURRENT_TABLE,
        "last_mode": mode or "resume",
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

    cursor.close()
    conn.close()

    return """
    <script>
    location.href='/score';
    </script>
    """


# =========================
# 返回需要评分的数据
# =========================
# @app.route("/get_data")
# def get_data():

#     with open(JSON_PATH, "r", encoding="utf-8") as f:
#         data = json.load(f)

#     scored_ids = get_scored_ids()

#     # 过滤掉已经评分的数据
#     data = [d for d in data if d["idx_id"] not in scored_ids]

#     return jsonify(data)

# @app.route("/get_one")
# def get_one():
#     data = ALL_DATA

#     # with open(JSON_PATH, "r", encoding="utf-8") as f:
#     #   data = json.load(f)

#     scored_ids = get_scored_ids()

#     # 找到第一条未评分数据
#     for d in data:
#         if d["idx_id"] not in scored_ids:
#             return jsonify(d)

#     # 如果全部评分完成
#     return jsonify(None)
@app.route("/get_one")
def get_one():

    conn = get_db()
    cursor = conn.cursor()

    scored_ids = get_scored_ids()

    for idx in ALL_IDS:

        # 已评分跳过
        if idx in scored_ids:
            continue

        try:

            # 尝试锁定任务
            cursor.execute(
                "INSERT INTO task_lock (idx_id) VALUES (%s)",
                (idx,)
            )
            conn.commit()

            data = ID_DATA_MAP[idx]

            cursor.close()
            conn.close()

            return jsonify({
                "data": data,
                "remain": len(ALL_IDS) - len(scored_ids)
            })

        except:
            # 如果插入失败，说明已经被别人领取
            continue

    cursor.close()
    conn.close()

    return jsonify(None)

# =========================
# 提交评分
# =========================
@app.route("/submit_score", methods=["POST"])
def submit_score():

    data = request.json

    conn = get_db()
    cursor = conn.cursor()
    ensure_table_schema(cursor, CURRENT_TABLE)

    sql = f"""
    INSERT IGNORE INTO {CURRENT_TABLE}
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
        data["idx_id"],
        data["s1"],
        json.dumps(data.get("s1_tags", []), ensure_ascii=False),
        data.get("m1", ""),
        data["s2"],
        json.dumps(data.get("s2_tags", []), ensure_ascii=False),
        data.get("m2", ""),
        data["s3"],
        json.dumps(data.get("s3_tags", []), ensure_ascii=False),
        data.get("m3", ""),
        data["s4"],
        json.dumps(data.get("s4_tags", []), ensure_ascii=False),
        data.get("m4", ""),
        data["s5"],
        json.dumps(data.get("s5_tags", []), ensure_ascii=False),
        data.get("m5", ""),
        data["s6"],
        json.dumps(data.get("s6_tags", []), ensure_ascii=False),
        data.get("m6", ""),
        data["s7"],
        json.dumps(data.get("s7_tags", []), ensure_ascii=False),
        data.get("m7", ""),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({"status": "success"})


# =========================
# 查看评分数据接口
# =========================
@app.route("/view_scores")
def view_scores():

    conn = get_db()
    cursor = conn.cursor()

    # cursor.execute("SELECT * FROM scores")
    cursor.execute(f"SELECT * FROM {CURRENT_TABLE}")
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify(rows)

@app.route("/reset_round", methods=["POST"])
def reset_round():

    global CURRENT_TABLE

    conn = get_db()
    cursor = conn.cursor()

    new_table = create_new_round_table(cursor)
    clear_task_lock(cursor)

    conn.commit()

    cursor.close()
    conn.close()

    CURRENT_TABLE = new_table
    save_app_state({
        "current_table": CURRENT_TABLE,
        "last_mode": "new",
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

    return jsonify({
        "status": "success",
        "table": new_table
    })
# =========================
# 启动Flask
# =========================
# if __name__ == "__main__":

    #app.run(debug=True)
    # app.run(host="0.0.0.0", port=5000, debug=True)
if __name__ == "__main__":
    app.run()