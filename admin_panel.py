# admin_panel.py

from flask import Flask, request, redirect, url_for, render_template_string

from utils.database_use import (
    init_db,
    list_users,
    update_user_flags,
    get_user_by_tg_id,
)
from utils.settings import DB_PATH  # просто чтобы было понятно, где БД
from contextlib import closing


app = Flask(__name__)


TEMPLATE = """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>FinLove Admin</title>
  <style>
    body { font-family: system-ui, -apple-system, BlinkMacSystemFont, sans-serif; margin: 20px; background:#f5f5f7; }
    h1 { font-size: 24px; }
    table { border-collapse: collapse; width: 100%; background:white; box-shadow:0 2px 6px rgba(0,0,0,0.05); }
    th, td { border: 1px solid #ddd; padding: 6px 8px; font-size: 14px; text-align: left; }
    th { background: #fafafa; }
    tr:nth-child(even) { background: #fafafa; }
    .badge { padding: 2px 6px; border-radius: 4px; font-size: 12px; }
    .badge-ok { background: #d1fae5; color: #047857; }
    .badge-bad { background: #fee2e2; color: #b91c1c; }
    .badge-admin { background:#e0f2fe;color:#0369a1; }
    .controls { margin-bottom: 16px; }
    .controls form { display:inline-block; margin-right: 12px; }
    input[type="text"] { padding:4px 6px; }
    button { padding:4px 8px; cursor:pointer; }
    .small { font-size: 12px; color:#555; }
  </style>
</head>
<body>
  <h1>FinLove Admin</h1>
  <p class="small">База: {{ db_path }}</p>

  <div class="controls">
    <form method="get" action="{{ url_for('users') }}">
      <input type="text" name="q" value="{{ q or '' }}" placeholder="Поиск по нику / имени / фамилии">
      <button type="submit">Найти</button>
    </form>

    <form method="post" action="{{ url_for('add_whitelist') }}">
      <input type="text" name="username" placeholder="Ник без @ для WL">
      <button type="submit">Добавить в whitelist</button>
    </form>
  </div>

  <table>
    <thead>
      <tr>
        <th>tg_id</th>
        <th>Username</th>
        <th>Имя</th>
        <th>Возраст</th>
        <th>Факультет</th>
        <th>Статусы</th>
        <th>Флаги</th>
        <th>Сохранить</th>
      </tr>
    </thead>
    <tbody>
    {% for u in users %}
      <tr>
        <td>{{ u.tg_id }}</td>
        <td>@{{ u.username or "" }}</td>
        <td>{{ (u.first_name or "") ~ (" " + u.last_name if u.last_name else "") }}</td>
        <td>{{ u.age or "-" }}</td>
        <td>{{ u.faculty or "-" }}</td>
        <td>
          {% if u.verified %}
            <span class="badge badge-ok">verified</span>
          {% else %}
            <span class="badge badge-bad">not verified</span>
          {% endif %}

          {% if u.is_admin %}
            <span class="badge badge-admin">admin</span>
          {% endif %}

          {% if u.is_banned %}
            <span class="badge badge-bad">banned</span>
          {% endif %}

          {% if u.is_whitelisted %}
            <span class="badge badge-ok">WL</span>
          {% endif %}
        </td>
        <td>
          <form method="post" action="{{ url_for('update_user', tg_id=u.tg_id) }}">
            <label>
              <input type="checkbox" name="is_admin" value="1" {% if u.is_admin %}checked{% endif %}>
              admin
            </label><br>
            <label>
              <input type="checkbox" name="is_banned" value="1" {% if u.is_banned %}checked{% endif %}>
              banned
            </label><br>
            <label>
              <input type="checkbox" name="is_whitelisted" value="1" {% if u.is_whitelisted %}checked{% endif %}>
              whitelist
            </label>
        </td>
        <td>
            <button type="submit">OK</button>
          </form>
        </td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
</body>
</html>
"""


@app.route("/admin/users", methods=["GET"])
def users():
    q = request.args.get("q", "").strip() or None
    users = list_users(search=q)
    return render_template_string(TEMPLATE, users=users, q=q, db_path=DB_PATH)


@app.route("/admin/users/<int:tg_id>/update", methods=["POST"])
def update_user(tg_id: int):
    is_admin = 1 if request.form.get("is_admin") == "1" else 0
    is_banned = 1 if request.form.get("is_banned") == "1" else 0
    is_whitelisted = 1 if request.form.get("is_whitelisted") == "1" else 0

    update_user_flags(
        tg_id=tg_id,
        is_admin=is_admin,
        is_banned=is_banned,
        is_whitelisted=is_whitelisted,
    )
    # после апдейта — обратно к списку, сохранив поиск если был
    q = request.args.get("q", "")
    return redirect(url_for("users", q=q))


@app.route("/admin/whitelist", methods=["POST"])
def add_whitelist():
    username = (request.form.get("username") or "").strip().lstrip("@")
    if not username:
        return redirect(url_for("users"))

    # Помечаем как whitelist ВСЕХ пользователей с таким username, которые уже есть в БД.
    # Важно: это сработает только если человек хотя бы раз нажал /start,
    # т.е. появился в таблице users.
    from utils.database_use import get_db_connection

    with get_db_connection() as conn, closing(conn.cursor()) as cur:
        cur.execute(
            "UPDATE users SET is_whitelisted = 1 WHERE lower(username) = lower(?)",
            (username,),
        )
        conn.commit()

    return redirect(url_for("users"))


if __name__ == "__main__":
    # На всякий случай инициализируем БД
    init_db()
    print("Admin panel running on http://127.0.0.1:5000/admin/users")
    app.run(debug=True)
