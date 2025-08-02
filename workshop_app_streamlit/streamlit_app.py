import streamlit as st
import sqlite3
import pandas as pd
import qrcode
import io
from PIL import Image
import re
import base64

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
        txn_id TEXT,
        screenshot BLOB
    )""")
    conn.commit()
    return conn

conn = init_db()

# Email validation function
def is_valid_email(email):
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return re.match(pattern, email) is not None


# Safe rerun function
def safe_rerun():
    try:
        st.rerun()
    except RuntimeError as e:
        if "Session state" not in str(e):
            raise

# Session state
if "user_logged_in" not in st.session_state:
    st.session_state.user_logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False
if "clear_team_form" not in st.session_state:
    st.session_state.clear_team_form = False

# Sidebar menu based on login and team registration status
menu = ["Register", "Login"]

if st.session_state.user_logged_in:
    c = conn.cursor()
    c.execute("SELECT name1, reg1, year1 FROM teams WHERE username=?", (st.session_state.username,))
    row = c.fetchone()
    has_team = row and all(row)
    if has_team:
        menu = ["Team Selection", "Transaction", "Logout"]
    else:
        menu = ["Team Selection", "Logout"]
elif st.session_state.admin_logged_in:
    menu = ["Admin", "Logout"]

choice = st.sidebar.selectbox("Navigation", menu)


# Register
if choice == "Register":
    st.title("User Registration")
    with st.form("register_form"):
        username = st.text_input("Email ID (will be your username)")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Register")
        if submitted:
            if not username or not password:
                st.error("All fields are required.")
            elif not is_valid_email(username):
                st.error("Please enter a valid email address.")
            else:
                c = conn.cursor()
                c.execute("SELECT 1 FROM users WHERE username=?", (username,))
                if c.fetchone():
                    st.error("This email is already registered. Please login.")
                else:
                    try:
                        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
                        conn.commit()
                        st.success("Registered successfully. Please login.")
                    except:
                        st.error("Error occurred while registering.")


# Login
elif choice == "Login":
    st.title("Login")
    with st.form("login_form"):
        username = st.text_input("Email ID")
        password = st.text_input("Password", type="password")
        login_btn = st.form_submit_button("Login")
        if login_btn:
            if username == "admin" and password == "admin123":
                st.session_state.admin_logged_in = True
                st.success("Admin login successful.")
                safe_rerun()
            else:
                c = conn.cursor()
                c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
                if c.fetchone():
                    st.session_state.user_logged_in = True
                    st.session_state.username = username
                    st.success("Logged in successfully!")
                    safe_rerun()
                else:
                    st.error("Invalid credentials.")


elif choice == "Team Selection":
    st.title("Team Selection")
    team_size = st.radio("Select Team Size", ["Single (₹50)", "Duo (₹80)", "Trio (₹100)"])
    size_map = {"Single (₹50)": 1, "Duo (₹80)":2, "Trio (₹100)": 3}
    size = size_map[team_size]

    if st.session_state.clear_team_form:
        for i in range(1, 4):
            for field in ["name", "reg", "year", "branch", "section"]:
                st.session_state.pop(f"{field}_{i}", None)
        st.session_state.clear_team_form = False
        safe_rerun()

    with st.form("team_form"):
        details = []
        for i in range(1, size + 1):
            # No number for single, numbered for duo/trio
            show_number = (size != 1)
            label_suffix = f" {i}" if show_number else ""

            st.subheader("Your Details" if size == 1 else f"Member {i}")
            name = st.text_input(f"Name{label_suffix}", key=f"name_{i}")
            reg = st.text_input(f"Reg Number{label_suffix}", key=f"reg_{i}")
            year = st.selectbox(f"Year{label_suffix}", options=["2", "3", "4"], key=f"year_{i}")
            branch = st.selectbox(f"Branch{label_suffix}", options=["CSD", "CSE", "CSM", "IT"], key=f"branch_{i}")
            section = st.selectbox(f"Section{label_suffix}", options=["A", "B", "C", "D"], key=f"section_{i}")
            details.extend([name, reg, year, branch, section])

        col1, col2 = st.columns(2)
        with col1:
            submit_team = st.form_submit_button("Submit Team")
        with col2:
            clear_btn = st.form_submit_button("Clear")

        if clear_btn:
            st.session_state.clear_team_form = True

        if submit_team:
            if not details[0].strip() or not details[1].strip() or not details[2].strip():
                st.error("❌ Please fill at least the first member's Name, Reg Number, and Year.")
            else:
                c = conn.cursor()
                c.execute("DELETE FROM teams WHERE username=?", (st.session_state.username,))
                placeholders = ",".join(["?"] * 17)
                c.execute(f"INSERT INTO teams VALUES ({placeholders})",
                          (st.session_state.username, team_size, *details, *[""] * (15 - len(details))))
                conn.commit()
                st.success("Team saved successfully. Redirecting to transaction page...")
                safe_rerun()


# Transaction
elif choice == "Transaction":
    st.title("Transaction")
    team_cost = {"Single (₹50)": 50, "Duo (₹80)": 80, "Trio (₹100)": 100}
    qr_map = {
        "Single (₹50)": "qr-code.png",
        "Duo (₹80)": "qr-code (1).png",
        "Trio (₹100)": "qr-code (2).png"
    }
    c = conn.cursor()
    c.execute("SELECT team_size FROM teams WHERE username=?", (st.session_state.username,))
    row = c.fetchone()

    if row:
        team_size = row[0]
        price = team_cost.get(team_size)
        qr_file = f"workshop_app_streamlit/{qr_map.get(team_size)}"
        st.write(f"Team Size: {team_size}")
        st.write(f"💰 Amount to be paid: ₹{price}")

        try:
            with open(qr_file, "rb") as f:
                st.image(f.read(), caption=f"Scan to Pay for {team_size}", width=250)
        except FileNotFoundError:
            st.error(f"QR code image not found: {qr_file}")

        with st.form("txn_form"):
            txn_id = st.text_input("Enter Transaction ID")
            valid_txn = bool(re.match(r"^T\d{22}$", txn_id)) if txn_id else False
            screenshot = st.file_uploader("Upload Payment Screenshot", type=["png", "jpg", "jpeg"])
            submit_txn = st.form_submit_button("Submit")
            if submit_txn:
                if not valid_txn:
                    st.error("❌ Invalid Transaction ID format. It should start with 'T' followed by exactly 22 digits.")
                elif not screenshot:
                    st.error("❌ Please upload the transaction screenshot.")
                else:
                    image_bytes = screenshot.read()
                    c.execute("REPLACE INTO transactions (username, amount, txn_id, screenshot) VALUES (?, ?, ?, ?)",
                              (st.session_state.username, price, txn_id, image_bytes))
                    conn.commit()
                    st.success("Transaction recorded successfully.")
    else:
        st.warning("⚠️ Please fill out team details first on the 'Team Selection' page.")

# Admin Panel


elif choice == "Admin" and st.session_state.admin_logged_in:
    st.title("Admin Panel")
    st.subheader("Download Registration Details")
    reg_df = pd.read_sql_query("SELECT * FROM teams", conn)
    st.dataframe(reg_df)
    st.download_button("Download Registration CSV", reg_df.to_csv(index=False), "registrations.csv", "text/csv")

    st.subheader("Download Transaction Details")
    txn_df = pd.read_sql_query("SELECT username, amount, txn_id FROM transactions", conn)
    st.dataframe(txn_df)
    st.download_button("Download Transaction CSV", txn_df.to_csv(index=False), "transactions.csv", "text/csv")

    st.subheader("Preview Uploaded Screenshots and Amounts")
    c = conn.cursor()
    c.execute("SELECT username, amount, txn_id, screenshot FROM transactions")
    txn_rows = c.fetchall()

    for idx, (username, amount, txn_id, screenshot_blob) in enumerate(txn_rows):
        st.markdown(f"**👤 Username:** `{username}`  \n**💸 Amount Paid:** ₹{amount}  \n**🔖 Transaction ID:** `{txn_id}`")

        if screenshot_blob:
        # Convert to base64
            b64 = base64.b64encode(screenshot_blob).decode()
            file_ext = "png"
            img_html = f'''
            <style>
            .tooltip-container {{
                position: relative;
                display: inline-block;
            }}
            .tooltip-container .tooltip-img {{
                visibility: hidden;
                width: 200px;
                background-color: transparent;
                text-align: center;
                border-radius: 6px;
                position: absolute;
                z-index: 1;
                bottom: 125%; 
                left: 50%;
                margin-left: -100px;
            }}
            .tooltip-container:hover .tooltip-img {{
                visibility: visible;
            }}
            </style>
            <div class="tooltip-container">
                <span style="font-size: 22px; cursor: pointer;">👁️</span>
                <div class="tooltip-img">
                    <img src="data:image/{file_ext};base64,{b64}" width="200"/>
                </div>
            </div>
            '''

            st.markdown(img_html, unsafe_allow_html=True)
        else:
            st.info("No screenshot uploaded.")
        st.markdown("---")


    st.subheader("💨 Danger Zone: Wipe All Data")
    with st.form("wipe_form"):
        admin_pwd = st.text_input("Enter Admin Password to Confirm", type="password")
        confirm_wipe = st.form_submit_button("Wipe All Data")
        if confirm_wipe:
            if admin_pwd == "admin234":
                c.execute("DELETE FROM users")
                c.execute("DELETE FROM teams")
                c.execute("DELETE FROM transactions")
                conn.commit()
                st.success("✅ All data wiped successfully from the database.")
                safe_rerun()
            else:
                st.error("❌ Incorrect password. Wipe operation aborted.")


# Logout
elif choice == "Logout":
    st.session_state.user_logged_in = False
    st.session_state.admin_logged_in = False
    st.session_state.username = ""
    st.success("Logged out successfully.")
    safe_rerun()
