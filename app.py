import os
import time
from datetime import datetime
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from flask import Flask, render_template, request, redirect, url_for
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

DISEASES = [
    "Malaria", "Dengue", "COVID-19", "Pneumonia",
    "Typhoid", "Hypertension", "Diabetes", "Asthma", "Other"
]

DEPARTMENTS = ["General", "ICU", "AC", "Special"]

def get_db_connection():
    """Establishes connection to PostgreSQL using DATABASE_URL."""
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL:
        if DATABASE_URL.startswith("postgres://"):
            DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    else:
        raise Exception("DATABASE_URL environment variable not found on Render!")

def init_db():
    """Initializes table schema automatically on PostgreSQL startup."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS patients (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                age INT NOT NULL,
                gender VARCHAR(20) NOT NULL,
                department VARCHAR(50) NOT NULL DEFAULT 'General',
                disease VARCHAR(100) NOT NULL,
                admit_date VARCHAR(20),
                discharge_date VARCHAR(20),
                bill_amount DOUBLE PRECISION DEFAULT 0.0
            );
        ''')
        conn.commit()
        cur.close()
        conn.close()
        print("Database initialized successfully!")
    except Exception as e:
        print(f"Database Initialization Error: {e}")

init_db()

def generate_analytics_charts():
    """Generates dynamic chart images for the analytics dashboard based on PBL specs."""
    try:
        conn = get_db_connection()
        df = pd.read_sql_query("SELECT * FROM patients", conn)
        conn.close()

        os.makedirs("static", exist_ok=True)

        # PBL Requirement 1 & 2: Data Cleansing & Age Group Categorization
        if not df.empty and 'age' in df.columns:
            df['AgeGroup'] = pd.cut(df['age'], bins=[0, 18, 60, 100], labels=['Child', 'Adult', 'Senior'], right=True)

        # Chart 1: Top Diagnoses
        plt.figure(figsize=(6, 4))
        if not df.empty and 'disease' in df.columns:
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
        if not df.empty and 'department' in df.columns and 'bill_amount' in df.columns:
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

        # Chart 3 (PBL Step 2): Age Group Distribution Analysis
        plt.figure(figsize=(6, 4))
        if not df.empty and 'AgeGroup' in df.columns:
            sns.countplot(data=df, x='AgeGroup', palette='Set2')
            plt.title('Patient Age Group Distribution')
            plt.xlabel('Age Group')
            plt.ylabel('Patient Count')
        else:
            plt.text(0.5, 0.5, 'No Data Available', horizontalalignment='center', verticalalignment='center', fontsize=12)
            plt.title('Age Group Distribution')
        plt.tight_layout()
        plt.savefig('static/chart_age_group.png')
        plt.close()

    except Exception as e:
        print(f"Chart Generation Error: {e}")

def calculate_los(admit_date_str, discharge_date_str):
    if not discharge_date_str:
        return 0
    try:
        admit = datetime.strptime(admit_date_str, '%Y-%m-%d')
        discharge = datetime.strptime(discharge_date_str, '%Y-%m-%d')
        return max((discharge - admit).days, 0)
    except (ValueError, TypeError):
        return 0

def clean_age(age_val):
    """Ensures age is always a positive integer greater than 0."""
    try:
        parsed_age = int(age_val)
        return parsed_age if parsed_age > 0 else 1
    except (ValueError, TypeError):
        return 1

def clean_bill_amount(bill_val):
    """Safely converts bill amount to float, defaults to 0.0 if empty/invalid."""
    try:
        return float(bill_val) if bill_val is not None and str(bill_val).strip() != '' else 0.0
    except (ValueError, TypeError):
        return 0.0

@app.route('/')
def index():
    generate_analytics_charts()
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT * FROM patients ORDER BY id ASC;')
    raw_patients = cur.fetchall()
    cur.close()
    conn.close()

    patients = []
    for row in raw_patients:
        p = dict(row)
        p['LOS'] = calculate_los(p.get('admit_date'), p.get('discharge_date'))
        patients.append(p)

    timestamp = int(time.time())
    return render_template('index.html', patients=patients, diseases=DISEASES, departments=DEPARTMENTS, timestamp=timestamp)

@app.route('/add', methods=['POST'])
def add_patient():
    name = request.form.get('name')
    age = clean_age(request.form.get('age'))
    gender = request.form.get('gender')
    department = request.form.get('department')
    disease = request.form.get('disease')
    admit_date = request.form.get('admit_date')
    
    raw_discharge_date = request.form.get('discharge_date')
    discharge_date = raw_discharge_date if raw_discharge_date else None
    
    bill_amount = clean_bill_amount(request.form.get('bill_amount'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        '''INSERT INTO patients (name, age, gender, department, disease, admit_date, discharge_date, bill_amount) 
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
        (name, age, gender, department, disease, admit_date, discharge_date, bill_amount)
    )
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('index'))

@app.route('/edit/<int:id>', methods=['POST'])
def edit_patient(id):
    name = request.form.get('name')
    age = clean_age(request.form.get('age'))
    gender = request.form.get('gender')
    department = request.form.get('department')
    disease = request.form.get('disease')
    admit_date = request.form.get('admit_date')
    
    raw_discharge_date = request.form.get('discharge_date')
    discharge_date = raw_discharge_date if raw_discharge_date else None
    
    bill_amount = clean_bill_amount(request.form.get('bill_amount'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        '''UPDATE patients 
           SET name=%s, age=%s, gender=%s, department=%s, disease=%s, admit_date=%s, discharge_date=%s, bill_amount=%s 
           WHERE id=%s''',
        (name, age, gender, department, disease, admit_date, discharge_date, bill_amount, id)
    )
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('index'))

@app.route('/delete/<int:id>')
def delete_patient(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM patients WHERE id = %s', (id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('index'))

@app.route('/view-data')
def view_data():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM patients ORDER BY id ASC;")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return {"status": "success", "total_entries": len(rows), "data": rows}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)