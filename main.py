from fastapi import FastAPI
from fastapi import Response
from fastapi import HTTPException
from pydantic import BaseModel
import mysql.connector
import io
import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import make_interp_spline
from fastapi.middleware.cors import CORSMiddleware



# ------------------ DATABASE CONNECTION ------------------
def get_db():
    return mysql.connector.connect(
        host="127.0.0.1",
        user="root",
        password="ajay0987",
        database="personal_finance",
        auth_plugin="mysql_native_password"
    )


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)






#Login checking
class Login(BaseModel):
    email: str
    password: str

@app.post("/login")
def login(data: Login):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT user_id, email, password
        FROM user
        WHERE email = %s
    """, (data.email,))

    user = cursor.fetchone()

    cursor.close()
    db.close()

    # ❌ Email not found
    if not user:
        raise HTTPException(status_code=401, detail="Email not found")

    # ❌ Password incorrect
    if user["password"] != data.password:
        raise HTTPException(status_code=401, detail="Incorrect password")

    # ✔ Login successful
    return {
        "message": "Login successful",
        "user_id": user["user_id"]
    }





# ----- SIGNUP MODEL -----
class Signup(BaseModel):
    first_name: str
    last_name: str
    email: str
    password: str

@app.post("/signup")
def signup(data: Signup):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Check if email already exists
    cursor.execute("SELECT user_id FROM user WHERE email = %s", (data.email,))
    exists = cursor.fetchone()

    if exists:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Insert new user
    cursor.execute("""
        INSERT INTO user (first_name, last_name, email, password)
        VALUES (%s, %s, %s, %s)
    """, (data.first_name, data.last_name, data.email, data.password))

    db.commit()

    new_user_id = cursor.lastrowid

    cursor.close()
    db.close()

    return {
        "success": True,
        "message": "Signup Successful!",
        "user_id": new_user_id
    }




# ------------------ MODELS ------------------
class Transaction(BaseModel):
    user_id: int
    type: str         # "income" or "expense"
    category: str     # Category name like Salary, Food, Rent
    amount: float
    date: str
    note: str | None = None


# ------------------ HELPER: GET CATEGORY ID OR CREATE ------------------
def get_or_create_category(cursor, table, category_name):
    query_check = f"SELECT category_id FROM {table} WHERE category_name = %s"
    cursor.execute(query_check, (category_name,))
    row = cursor.fetchone()

    if row:
        return row[0]

    query_insert = f"INSERT INTO {table} (category_name) VALUES (%s)"
    cursor.execute(query_insert, (category_name,))
    return cursor.lastrowid


# ------------------ POST: ADD TRANSACTION ------------------
@app.post("/add_transaction")
def add_transaction(data: Transaction):
    db = get_db()
    cursor = db.cursor()

    if data.type == "income":
        category_id = get_or_create_category(cursor, "income_categories", data.category)

        cursor.execute("""
            INSERT INTO incomes (user_id, category_id, amount, income_date, note)
            VALUES (%s, %s, %s, %s, %s)
        """, (data.user_id, category_id, data.amount, data.date, data.note))

    elif data.type == "expense":
        category_id = get_or_create_category(cursor, "expense_categories", data.category)

        cursor.execute("""
            INSERT INTO expenses (user_id, category_id, amount, expense_date, note)
            VALUES (%s, %s, %s, %s, %s)
        """, (data.user_id, category_id, data.amount, data.date, data.note))

    db.commit()
    cursor.close()
    db.close()

    return {"message": "Transaction saved successfully!"}


# ------------------ GET: TRANSACTION HISTORY ------------------
@app.get("/history/{user_id}")
def history(user_id: int):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Income
    cursor.execute("""
        SELECT 
            'income' AS type,
            income_categories.category_name AS category,
            incomes.amount,
            incomes.income_date AS date,
            incomes.note
        FROM incomes
        JOIN income_categories 
            ON incomes.category_id = income_categories.category_id
        WHERE incomes.user_id = %s
    """, (user_id,))
    income_data = cursor.fetchall()

    # Expense
    cursor.execute("""
        SELECT 
            'expense' AS type,
            expense_categories.category_name AS category,
            expenses.amount,
            expenses.expense_date AS date,
            expenses.note
        FROM expenses
        JOIN expense_categories 
            ON expenses.category_id = expense_categories.category_id
        WHERE expenses.user_id = %s
    """, (user_id,))
    expense_data = cursor.fetchall()

    # Combine & sort by date (newest first)
    all_tx = income_data + expense_data
    all_tx.sort(key=lambda x: x["date"], reverse=True)

    return all_tx
