CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    PatientID TEXT UNIQUE NOT NULL,

    Age INTEGER NOT NULL,

    Gender TEXT NOT NULL,

    AdmissionDate TEXT NOT NULL,

    DischargeDate TEXT NOT NULL,

    Diagnosis TEXT NOT NULL,

    BillAmount REAL NOT NULL,

    Department TEXT NOT NULL,

    LOS REAL NOT NULL
);