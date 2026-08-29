import os
import time
from datetime import datetime
import sqlite3
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

DISEASES = [
    "Malaria", "Dengue", "COVID-19", "Pneumonia",
    "Typhoid", "Hypertension", "Diabetes", "Asthma", "Other"
]

DEPARTMENTS = ["General", "ICU", "AC", "Special"]

def get_db_connection():
    conn = sqlite3.connect('hospital.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            age INTEGER NOT NULL,
            gender TEXT NOT NULL,
            department TEXT NOT NULL DEFAULT 'General',
            disease TEXT NOT NULL,
            admit_date TEXT,
            discharge_date TEXT,
            bill_amount REAL DEFAULT 0.0
        )
    ''')
    
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(patients)")
    existing_columns = [column[1] for column in cursor.fetchall()]
    
    if 'department' not in existing_columns:
        conn.execute("ALTER TABLE patients ADD COLUMN department TEXT NOT NULL DEFAULT 'General'")
    if 'bill_amount' not in existing_columns:
        conn.execute("ALTER TABLE patients ADD COLUMN bill_amount REAL DEFAULT 0.0")

    conn.commit()
    conn.close()

init_db()

def generate_analytics_charts():
    """Generates dynamic chart images for the analytics dashboard."""
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM patients", conn)
    conn.close()

    os.makedirs("static", exist_ok=True)

    # Chart 1: Top Diagnoses
    plt.figure(figsize=(6, 4))
    if not df.empty:
        sns.countplot(data=df, x='disease', palette='Blues_d')
        plt.title('Top Diagnoses')
        plt.xlabel('Disease')
        plt.ylabel('Count')
        plt.xticks(rotation=30)
    else:
        plt.text(0.5, 0.5, 'No Data Available', horizontalalignment='center', verticalalignment='center', fontsize=12)
        plt.title('Top Diagnoses')
    plt.tight_layout()
    plt.savefig('static/chart_diagnoses.png')
    plt.close()

    # Chart 2: Average Cost per Department
    plt.figure(figsize=(6, 4))
    if not df.empty:
        avg_cost = df.groupby('department')['bill_amount'].mean().reset_index()
        sns.barplot(data=avg_cost, x='department', y='bill_amount', palette='viridis')
        plt.title('Avg Cost per Department')
        plt.xlabel('Department')
        plt.ylabel('Average Cost ($)')
    else:
        plt.text(0.5, 0.5, 'No Data Available', horizontalalignment='center', verticalalignment='center', fontsize=12)
        plt.title('Avg Cost per Department')
    plt.tight_layout()
    plt.savefig('static/chart_department_cost.png')
    plt.close()

def calculate_los(admit_date_str, discharge_date_str):
    try:
        admit = datetime.strptime(admit_date_str, '%Y-%m-%d')
        discharge = datetime.strptime(discharge_date_str, '%Y-%m-%d')
        return max((discharge - admit).days, 0)
    except (ValueError, TypeError):
        return 0

@app.route('/')
def index():
    generate_analytics_charts()
    conn = get_db_connection()
    raw_patients = conn.execute('SELECT * FROM patients').fetchall()
    conn.close()

    patients = []
    for row in raw_patients:
        p = dict(row)
        p['LOS'] = calculate_los(p.get('admit_date'), p.get('discharge_date'))
        patients.append(p)

    # Send current timestamp to bypass browser image caching
    timestamp = int(time.time())

    return render_template('index.html', patients=patients, diseases=DISEASES, departments=DEPARTMENTS, timestamp=timestamp)

@app.route('/add', methods=['POST'])
def add_patient():
    name = request.form.get('name')
    age = request.form.get('age')
    gender = request.form.get('gender')
    department = request.form.get('department')
    disease = request.form.get('disease')
    admit_date = request.form.get('admit_date')
    discharge_date = request.form.get('discharge_date')
    bill_amount = request.form.get('bill_amount', 0.0)

    conn = get_db_connection()
    conn.execute(
        '''INSERT INTO patients (name, age, gender, department, disease, admit_date, discharge_date, bill_amount) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (name, age, gender, department, disease, admit_date, discharge_date, bill_amount)
    )
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/edit/<int:id>', methods=['POST'])
def edit_patient(id):
    name = request.form.get('name')
    age = request.form.get('age')
    gender = request.form.get('gender')
    department = request.form.get('department')
    disease = request.form.get('disease')
    admit_date = request.form.get('admit_date')
    discharge_date = request.form.get('discharge_date')
    bill_amount = request.form.get('bill_amount', 0.0)

    conn = get_db_connection()
    conn.execute(
        '''UPDATE patients 
           SET name=?, age=?, gender=?, department=?, disease=?, admit_date=?, discharge_date=?, bill_amount=? 
           WHERE id=?''',
        (name, age, gender, department, disease, admit_date, discharge_date, bill_amount, id)
    )
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/delete/<int:id>')
def delete_patient(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM patients WHERE id = ?', (id,))
    
    # Re-sequence database IDs dynamically
    conn.execute('''
        UPDATE patients 
        SET id = (
            SELECT COUNT(*) 
            FROM patients AS p2 
            WHERE p2.id <= patients.id
        )
    ''')
    
    conn.execute('''
        UPDATE sqlite_sequence 
        SET seq = COALESCE((SELECT MAX(id) FROM patients), 0) 
        WHERE name='patients'
    ''')
    
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, port=5001)