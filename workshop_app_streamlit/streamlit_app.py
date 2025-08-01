
import streamlit as st
import sqlite3
import pandas as pd
import qrcode
import io

st.set_page_config(page_title="Workshop Portal", layout="centered")

# Initialize DB
def init_db():
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS teams (
        username TEXT,
        team_size TEXT,
        name1 TEXT, reg1 TEXT, year1 TEXT, branch1 TEXT, section1 TEXT,
        name2 TEXT, reg2 TEXT, year2 TEXT, branch2 TEXT, section2 TEXT,
        name3 TEXT, reg3 TEXT, year3 TEXT, branch3 TEXT, section3 TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS transactions (
        username TEXT,
        amount INTEGER,
        txn_id TEXT
    )""")
    conn.commit()
    return conn

conn = init_db()

# Session state
if "user_logged_in" not in st.session_state:
    st.session_state.user_logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""

menu = ["Register", "Login"]
if st.session_state.user_logged_in:
    menu = ["Team Selection", "Transaction", "Logout"]
menu += ["Admin"]

choice = st.sidebar.selectbox("Navigation", menu)

# User Registration
if choice == "Register":
    st.title("User Registration")
    with st.form("register_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Register")
        if submitted:
            if username and password:
                c = conn.cursor()
                try:
                    c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
                    conn.commit()
                    st.success("Registered successfully. Please login.")
                except:
                    st.error("Username already exists.")
            else:
                st.error("All fields are required.")

# User Login
elif choice == "Login":
    st.title("User Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login_btn = st.form_submit_button("Login")
        if login_btn:
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
            if c.fetchone():
                st.session_state.user_logged_in = True
                st.session_state.username = username
                st.success("Logged in successfully!")
                st.experimental_rerun()
            else:
                st.error("Invalid credentials.")

# Team Selection
elif choice == "Team Selection":
    st.title("Team Selection")
    team_size = st.radio("Select Team Size", ["Single (₹50)", "Duo (₹80)", "Trio (₹100)"])
    size_map = {"Single (₹50)": 1, "Duo (₹80)": 2, "Trio (₹100)": 3}
    size = size_map[team_size]

    with st.form("team_form"):
        details = []
        for i in range(1, size+1):
            st.subheader(f"Member {i}")
            name = st.text_input(f"Name {i}")
            reg = st.text_input(f"Reg Number {i}")
            year = st.text_input(f"Year {i}")
            branch = st.text_input(f"Branch {i}")
            section = st.text_input(f"Section {i}")
            details.extend([name, reg, year, branch, section])
        submit_team = st.form_submit_button("Submit Team")
        if submit_team:
            c = conn.cursor()
            c.execute("DELETE FROM teams WHERE username=?", (st.session_state.username,))
            c.execute("""INSERT INTO teams VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (st.session_state.username, team_size, *details, *[""]*(15 - len(details))))
            conn.commit()
            st.success("Team saved successfully.")

# Transaction Page
elif choice == "Transaction":
    st.title("Transaction")

    team_cost = {
        "Single (₹50)": 50,
        "Duo (₹80)": 80,
        "Trio (₹100)": 100
    }

    c = conn.cursor()
    c.execute("SELECT team_size FROM teams WHERE username=?", (st.session_state.username,))
    row = c.fetchone()
    if row:
        team_size = row[0]
        price = team_cost[team_size]
        st.write(f"Team Size: {team_size}")
        st.write(f"💰 Amount to be paid: ₹{price}")

        with st.form("txn_form"):
            txn_id = st.text_input("Enter Transaction ID")
            submit_txn = st.form_submit_button("Submit")
            if submit_txn:
                c.execute("REPLACE INTO transactions VALUES (?, ?, ?)", (st.session_state.username, price, txn_id))
                conn.commit()
                st.success("Transaction recorded.")
    else:
        st.warning("Please fill team details first.")

# Logout
elif choice == "Logout":
    st.session_state.user_logged_in = False
    st.session_state.username = ""
    st.success("Logged out successfully.")
    st.experimental_rerun()

# Admin Panel
elif choice == "Admin":
    st.title("Admin Panel")
    if "admin_logged_in" not in st.session_state:
        st.session_state.admin_logged_in = False

    if not st.session_state.admin_logged_in:
        with st.form("admin_login"):
            username = st.text_input("Admin Username")
            password = st.text_input("Admin Password", type="password")
            login_btn = st.form_submit_button("Login")
            if login_btn and username == "admin" and password == "admin123":
                st.session_state.admin_logged_in = True
                st.success("Admin login successful.")
            elif login_btn:
                st.error("Invalid admin credentials.")
    else:
        st.subheader("Download Registration Details")
        reg_df = pd.read_sql_query("SELECT * FROM teams", conn)
        st.dataframe(reg_df)
        st.download_button("Download Registration CSV", reg_df.to_csv(index=False), "registrations.csv", "text/csv")

        st.subheader("Download Transaction Details")
        txn_df = pd.read_sql_query("SELECT * FROM transactions", conn)
        st.dataframe(txn_df)
        st.download_button("Download Transaction CSV", txn_df.to_csv(index=False), "transactions.csv", "text/csv")

        st.subheader("Paste Transaction ID and View QR")
        txn_id = st.text_input("Paste Transaction ID")
        if txn_id:
            img = qrcode.make(f"Transaction ID: {txn_id}")
            buf = io.BytesIO()
            img.save(buf)
            buf.seek(0)
            st.image(buf, caption="Your QR Code", width=200)
