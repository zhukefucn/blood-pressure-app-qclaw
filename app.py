import os
import psycopg2
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')


def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('PGHOST', 'localhost'),
        database=os.environ.get('PGDATABASE', 'blood_pressure'),
        user=os.environ.get('PGUSER', 'postgres'),
        password=os.environ.get('PGPASSWORD', '')
    )


def init_db():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS blood_pressure (
                id SERIAL PRIMARY KEY,
                measure_date DATE NOT NULL,
                measure_time TIME NOT NULL,
                systolic INT NOT NULL,
                diastolic INT NOT NULL,
                pulse INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        cur.close()
        conn.close()
        print("[init_db] Table ready.")
    except Exception as e:
        print(f"[init_db] Warning: {e}")


# ── 模块加载时执行 DB 初始化（gunicorn / __main__ 均兼容） ──
init_db()


HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>血压记录</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; }
        h1 { text-align: center; color: #333; margin-bottom: 20px; }
        .card { background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; color: #666; }
        input, select { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 16px; }
        button { background: #4CAF50; color: white; padding: 12px 24px; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; width: 100%; }
        button:hover { background: #45a049; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f8f8f8; }
        .btn-delete { background: #f44336; padding: 6px 12px; font-size: 14px; width: auto; }
        .stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; }
        .stat-item { background: #f8f8f8; padding: 15px; border-radius: 4px; text-align: center; }
        .stat-value { font-size: 24px; font-weight: bold; color: #333; }
        .stat-label { color: #666; margin-top: 5px; }
        .flash { background: #4CAF50; color: white; padding: 10px; border-radius: 4px; margin-bottom: 20px; }
        .flash-error { background: #f44336; color: white; padding: 10px; border-radius: 4px; margin-bottom: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🩺 血压记录</h1>

        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="{{ 'flash-error' if category == 'error' else 'flash' }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <div class="card">
            <h2>录入血压</h2>
            <form method="POST" action="/add">
                <div class="form-group">
                    <label>日期</label>
                    <input type="date" name="measure_date" value="{{ today }}" required>
                </div>
                <div class="form-group">
                    <label>时间</label>
                    <select name="measure_time" required>
                        <option value="06:00">早上 (6:00)</option>
                        <option value="14:00">中午 (14:00)</option>
                        <option value="21:00">晚上 (21:00)</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>收缩压 (高压 mmHg)</label>
                    <input type="number" name="systolic" min="60" max="250" required placeholder="如: 120">
                </div>
                <div class="form-group">
                    <label>舒张压 (低压 mmHg)</label>
                    <input type="number" name="diastolic" min="40" max="150" required placeholder="如: 80">
                </div>
                <div class="form-group">
                    <label>脉搏 (次/分)</label>
                    <input type="number" name="pulse" min="40" max="200" placeholder="如: 72">
                </div>
                <button type="submit">保存记录</button>
            </form>
        </div>

        {% if stats %}
        <div class="card">
            <h2>统计分析 (最近30天)</h2>
            <div class="stats">
                <div class="stat-item">
                    <div class="stat-value">{{ "%.0f"|format(stats.avg_systolic) }}</div>
                    <div class="stat-label">平均收缩压</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{{ "%.0f"|format(stats.avg_diastolic) }}</div>
                    <div class="stat-label">平均舒张压</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{{ "%.0f"|format(stats.avg_pulse) }}</div>
                    <div class="stat-label">平均脉搏</div>
                </div>
            </div>
        </div>
        {% endif %}

        <div class="card">
            <h2>历史记录</h2>
            {% if records %}
            <table>
                <thead>
                    <tr>
                        <th>日期</th>
                        <th>时间</th>
                        <th>收缩压</th>
                        <th>舒张压</th>
                        <th>脉搏</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody>
                    {% for record in records %}
                    <tr>
                        <td>{{ record.measure_date }}</td>
                        <td>{{ record.measure_time }}</td>
                        <td>{{ record.systolic }}</td>
                        <td>{{ record.diastolic }}</td>
                        <td>{{ record.pulse or '-' }}</td>
                        <td>
                            <form method="POST" action="/delete/{{ record.id }}" style="display:inline;">
                                <button type="submit" class="btn-delete" onclick="return confirm('确定删除?')">删除</button>
                            </form>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <p style="color:#999;text-align:center;padding:20px;">暂无记录，请录入第一条血压数据。</p>
            {% endif %}
        </div>
    </div>
</body>
</html>
'''


@app.route('/health')
def health():
    """Render 健康检查端点"""
    return {'status': 'ok'}, 200


@app.route('/')
def index():
    today = datetime.now().strftime('%Y-%m-%d')

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            'SELECT id, measure_date, measure_time, systolic, diastolic, pulse '
            'FROM blood_pressure ORDER BY measure_date DESC, measure_time DESC LIMIT 100'
        )
        records_raw = cur.fetchall()

        cur.execute('''
            SELECT AVG(systolic), AVG(diastolic), AVG(pulse)
            FROM blood_pressure
            WHERE measure_date >= CURRENT_DATE - INTERVAL '30 days'
        ''')
        result = cur.fetchone()
        cur.close()
        conn.close()
    except Exception as e:
        flash(f'数据库连接失败: {e}', 'error')
        return render_template_string(HTML_TEMPLATE, records=[], stats=None, today=today)

    stats = None
    if result and result[0]:
        stats = type('obj', (object,), {
            'avg_systolic': float(result[0] or 0),
            'avg_diastolic': float(result[1] or 0),
            'avg_pulse': float(result[2] or 0)
        })

    formatted_records = []
    for r in records_raw:
        formatted_records.append({
            'id': r[0],
            'measure_date': r[1].strftime('%Y-%m-%d') if hasattr(r[1], 'strftime') else str(r[1]),
            'measure_time': str(r[2])[:5] if r[2] else '',
            'systolic': r[3],
            'diastolic': r[4],
            'pulse': r[5]
        })

    return render_template_string(HTML_TEMPLATE, records=formatted_records, stats=stats, today=today)


@app.route('/add', methods=['POST'])
def add():
    try:
        measure_date = request.form['measure_date']
        measure_time = request.form['measure_time']
        systolic = int(request.form['systolic'])
        diastolic = int(request.form['diastolic'])
        pulse_val = request.form.get('pulse', '').strip()
        pulse = int(pulse_val) if pulse_val else None

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO blood_pressure (measure_date, measure_time, systolic, diastolic, pulse) '
            'VALUES (%s, %s, %s, %s, %s)',
            (measure_date, measure_time, systolic, diastolic, pulse)
        )
        conn.commit()
        cur.close()
        conn.close()
        flash('记录保存成功!')
    except Exception as e:
        flash(f'保存失败: {e}', 'error')

    return redirect(url_for('index'))


@app.route('/delete/<int:record_id>', methods=['POST'])
def delete(record_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('DELETE FROM blood_pressure WHERE id = %s', (record_id,))
        conn.commit()
        cur.close()
        conn.close()
        flash('记录已删除')
    except Exception as e:
        flash(f'删除失败: {e}', 'error')

    return redirect(url_for('index'))


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
