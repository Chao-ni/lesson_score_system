from flask import Flask, render_template, jsonify, request
import pymysql
import json

app = Flask(__name__)

# =========================
# 你的JSON数据路径
# =========================
JSON_PATH = r"C:\Users\Admin\Desktop\fsdownload\predict_outputs_extracted_0209\all_generated_predictions_extracted_merged_data.json"


# =========================
# MySQL数据库连接配置
# =========================
def get_db():

    conn = pymysql.connect(
        host="localhost",
        user="root",          # 你的MySQL用户名
        password="123456",    # 改成你的MySQL密码
        database="lesson_eval",
        charset="utf8mb4"
    )

    return conn


# =========================
# 获取已评分ID（防止重复评分）
# =========================
def get_scored_ids():

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT idx_id FROM scores")

    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return set([r[0] for r in rows])


# =========================
# 首页
# =========================
@app.route("/")
def index():

    return render_template("index.html")


# =========================
# 返回需要评分的数据
# =========================
@app.route("/get_data")
def get_data():

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    scored_ids = get_scored_ids()

    # 过滤掉已经评分的数据
    data = [d for d in data if d["idx_id"] not in scored_ids]

    return jsonify(data)


# =========================
# 提交评分
# =========================
@app.route("/submit_score", methods=["POST"])
def submit_score():

    data = request.json

    conn = get_db()
    cursor = conn.cursor()

    sql = """
    INSERT INTO scores
    (idx_id, s1, s2, s3, s4, s5, s6, s7)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """

    cursor.execute(sql, (
        data["idx_id"],
        data["s1"],
        data["s2"],
        data["s3"],
        data["s4"],
        data["s5"],
        data["s6"],
        data["s7"]
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

    cursor.execute("SELECT * FROM scores")

    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify(rows)


# =========================
# 启动Flask
# =========================
if __name__ == "__main__":

    app.run(debug=True)