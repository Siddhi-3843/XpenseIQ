import streamlit as st
import os
import requests
import pandas as pd

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

st.set_page_config(
    page_title="XpenseIQ",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

if "token" not in st.session_state:
    st.session_state.token = None
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "email" not in st.session_state:
    st.session_state.email = None
if "page" not in st.session_state:
    st.session_state.page = "dashboard"
if "use_type" not in st.session_state:
    st.session_state.use_type = None


def get_headers():
    return {"Authorization": f"Bearer {st.session_state.token}"}


def main():
    if not st.session_state.token:
        show_login_page()
    elif not st.session_state.use_type:
        show_onboarding_page()
    else:
        show_main_app()


# ─────────────────────────────────────────────────────────
# LOGIN PAGE
# ─────────────────────────────────────────────────────────

def show_login_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("💰 XpenseIQ")
        st.subheader("AI-powered Smart Expense Scanner")
        st.divider()

        tab1, tab2 = st.tabs(["Login", "Register"])

        with tab1:
            st.subheader("Login to your account")
            email = st.text_input("Email", key="login_email")
            password = st.text_input(
                "Password", type="password", key="login_password"
            )
            if st.button("Login", use_container_width=True):
                if email and password:
                    login(email, password)
                else:
                    st.error("Please enter email and password")

        with tab2:
            st.subheader("Create new account")
            full_name = st.text_input("Full Name", key="reg_name")
            reg_email = st.text_input("Email", key="reg_email")
            reg_password = st.text_input(
                "Password", type="password", key="reg_password"
            )
            if st.button("Register", use_container_width=True):
                if full_name and reg_email and reg_password:
                    register(full_name, reg_email, reg_password)
                else:
                    st.error("Please fill all fields")


def login(email: str, password: str):
    try:
        response = requests.post(
            f"{BACKEND_URL}/auth/login",
            data={
                "username": email,
                "password": password,
                "grant_type": "password"
            }
        )
        if response.status_code == 200:
            data = response.json()
            st.session_state.token = data["access_token"]
            st.session_state.user_id = data["user_id"]
            st.session_state.email = data["email"]
            st.success("Login successful!")
            st.rerun()
        else:
            st.error("Invalid email or password")
    except Exception as e:
        st.error(f"Cannot connect to server: {str(e)}")


def register(full_name: str, email: str, password: str):
    try:
        response = requests.post(
            f"{BACKEND_URL}/auth/register",
            params={
                "email": email,
                "password": password,
                "full_name": full_name
            }
        )
        if response.status_code == 200:
            st.success("Account created! Please login.")
        else:
            error = response.json().get("detail", "Registration failed")
            st.error(error)
    except Exception as e:
        st.error(f"Cannot connect to server: {str(e)}")


# ─────────────────────────────────────────────────────────
# ONBOARDING PAGE
# ─────────────────────────────────────────────────────────

def show_onboarding_page():
    st.markdown(
        """
        <style>
        .onboard-card {
            border: 2px solid #e0e0e0;
            border-radius: 12px;
            padding: 2rem;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s;
        }
        .onboard-card:hover {
            border-color: #4CAF50;
            background-color: #f9fff9;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    st.title("👋 Welcome to XpenseIQ")
    st.subheader(f"Hello, {st.session_state.email}!")
    st.write("Before we get started, tell us how you plan to use XpenseIQ:")
    st.divider()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("### 👤 Personal Use")
        st.write("Just me tracking my own expenses")
        st.write("✅ Upload receipts")
        st.write("✅ View expense history")
        st.write("✅ Dashboard & reports")
        st.write("✅ Fraud detection")
        if st.button("Select Personal", use_container_width=True):
            st.session_state.use_type = "personal"
            st.rerun()

    with col2:
        st.markdown("### 👥 Small Team")
        st.write("Team of up to 10 people")
        st.write("✅ All Personal features")
        st.write("✅ Expense approval workflow")
        st.write("✅ Pending verification queue")
        st.write("✅ Team expense reports")
        if st.button("Select Small Team", use_container_width=True):
            st.session_state.use_type = "small_team"
            st.rerun()

    with col3:
        st.markdown("### 🏢 Enterprise")
        st.write("Team of 10+ people")
        st.write("✅ All Small Team features")
        st.write("✅ Advanced analytics")
        st.write("✅ Policy compliance")
        st.write("✅ Multi-department support")
        if st.button("Select Enterprise", use_container_width=True):
            st.session_state.use_type = "enterprise"
            st.rerun()


# ─────────────────────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────────────────────

def show_main_app():
    with st.sidebar:
        st.title("💰 XpenseIQ")
        st.caption(f"Logged in as {st.session_state.email}")
        st.caption(f"Mode: {st.session_state.use_type.replace('_', ' ').title()}")
        st.divider()

        if st.button("📊 Dashboard", use_container_width=True):
            st.session_state.page = "dashboard"
            st.rerun()

        if st.button("📷 Scan Receipt", use_container_width=True):
            st.session_state.page = "scan"
            st.rerun()

        if st.button("📋 My Expenses", use_container_width=True):
            st.session_state.page = "expenses"
            st.rerun()

        if st.button("⚠️ Pending Verification", use_container_width=True):
            st.session_state.page = "pending"
            st.rerun()

        if st.button("❌ Rejected Expenses", use_container_width=True):
            st.session_state.page = "rejected"
            st.rerun()

        st.divider()

        if st.button("🔄 Change Mode", use_container_width=True):
            st.session_state.use_type = None
            st.rerun()

        if st.button("Logout", use_container_width=True):
            st.session_state.token = None
            st.session_state.user_id = None
            st.session_state.email = None
            st.session_state.page = "dashboard"
            st.session_state.use_type = None
            st.rerun()

    if st.session_state.page == "dashboard":
        show_dashboard()
    elif st.session_state.page == "scan":
        show_scan_page()
    elif st.session_state.page == "expenses":
        show_expenses_page()
    elif st.session_state.page == "pending":
        show_pending_page()
    elif st.session_state.page == "rejected":
        show_rejected_page()
    else:
        show_dashboard()


# ─────────────────────────────────────────────────────────
# DASHBOARD PAGE
# ─────────────────────────────────────────────────────────

def show_dashboard():
    st.title("📊 Dashboard")

    try:
        response = requests.get(
            f"{BACKEND_URL}/expenses/summary",
            headers=get_headers()
        )
        summary = response.json()
    except Exception as e:
        st.error(f"Could not load dashboard: {str(e)}")
        return

    # Show pending verification alert
    pending_count = summary.get("pending_count", 0)
    rejected_count = summary.get("rejected_count", 0)

    if pending_count > 0:
        st.warning(
            f"⚠️ You have **{pending_count}** expense(s) pending verification. "
            f"Click **Pending Verification** in the sidebar to review them."
        )

    # Metric cards — only approved expenses counted
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Total Spend (Approved)",
            value=f"₹{summary.get('total_spend', 0):,.2f}"
        )
    with col2:
        st.metric(
            label="Approved Transactions",
            value=summary.get("transaction_count", 0)
        )
    with col3:
        st.metric(
            label="Pending Verification",
            value=pending_count,
            delta="needs review" if pending_count > 0 else "all clear"
        )
    with col4:
        st.metric(
            label="Avg Transaction",
            value=f"₹{summary.get('avg_transaction', 0):,.2f}"
        )

    st.divider()

    # Charts
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("💰 Spend by Category")
        category_data = summary.get("category_breakdown", {})
        if category_data:
            df = pd.DataFrame(
                list(category_data.items()),
                columns=["Category", "Amount"]
            ).sort_values("Amount", ascending=False)
            st.bar_chart(df.set_index("Category"))
        else:
            st.info("No approved expense data yet. Scan your first receipt!")

    with col2:
        st.subheader("💳 Payment Methods")
        payment_data = summary.get("payment_method_breakdown", {})
        if payment_data:
            df = pd.DataFrame(
                list(payment_data.items()),
                columns=["Method", "Count"]
            )
            st.bar_chart(df.set_index("Method"))
        else:
            st.info("No payment data yet.")

    st.divider()

    # Recent approved expenses
    st.subheader("🧾 Recent Approved Expenses")
    try:
        response = requests.get(
            f"{BACKEND_URL}/expenses/",
            headers=get_headers()
        )
        data = response.json()
        expenses = data.get("expenses", [])[:5]

        if expenses:
            df = pd.DataFrame(expenses)
            display_cols = [
                "vendor_name", "total_amount",
                "primary_category", "transaction_date",
                "payment_method", "fraud_risk_score"
            ]
            display_cols = [c for c in display_cols if c in df.columns]
            df_display = df[display_cols].copy()
            df_display.columns = [
                "Vendor", "Amount (₹)", "Category",
                "Date", "Payment", "Fraud Risk"
            ]
            st.dataframe(df_display, use_container_width=True)
        else:
            st.info("No approved expenses yet.")
    except Exception as e:
        st.error(f"Could not load recent expenses: {str(e)}")


# ─────────────────────────────────────────────────────────
# SCAN RECEIPT PAGE
# ─────────────────────────────────────────────────────────

def show_scan_page():
    st.title("📷 Scan Receipt")
    st.write("Upload a receipt image or PDF to extract expense data automatically.")
    st.info(
        "💡 Only valid receipts with financial data will be processed. "
        "Blank, empty, or non-receipt files will be rejected automatically."
    )

    uploaded_file = st.file_uploader(
        "Choose a receipt image or PDF",
        type=["jpg", "jpeg", "png", "webp", "bmp", "tiff", "pdf"],
        help="Supported formats: JPG, PNG, WEBP, BMP, TIFF, PDF"
    )

    if uploaded_file is not None:
        if uploaded_file.type != "application/pdf":
            st.image(uploaded_file, caption="Uploaded Receipt", width=300)
        st.info(f"📄 File: {uploaded_file.name} ({uploaded_file.type})")

        if st.button("🔍 Scan Receipt", use_container_width=True):
            with st.spinner("Processing receipt through AI pipeline..."):
                try:
                    response = requests.post(
                        f"{BACKEND_URL}/expenses/scan-receipt",
                        headers=get_headers(),
                        files={"file": (
                            uploaded_file.name,
                            uploaded_file.getvalue(),
                            uploaded_file.type
                        )}
                    )

                    if response.status_code == 200:
                        result = response.json()
                        expense_status = result.get("expense_status", "approved")

                        if expense_status == "approved":
                            st.success(
                                f"✅ {result['message']} — Expense ID: {result['expense_id']}"
                            )
                        else:
                            st.warning(
                                f"⚠️ {result['message']} — Expense ID: {result['expense_id']}"
                            )
                            st.info(
                                "This expense has been moved to **Pending Verification**. "
                                "Go to the Pending Verification page to approve or reject it."
                            )

                        extracted = result.get("extracted_data", {})
                        classification = result.get("classification", {})
                        fraud = result.get("fraud_analysis", {})
                        ocr = result.get("ocr", {})

                        st.subheader("📋 Extracted Data")
                        col1, col2 = st.columns(2)

                        with col1:
                            st.write("**Vendor Name:**", extracted.get("vendor_name", "Unknown"))
                            st.write("**Transaction Date:**", extracted.get("transaction_date", "Unknown"))
                            st.write("**Total Amount:**", f"₹{extracted.get('total_amount', 0)}")
                            st.write("**Subtotal:**", f"₹{extracted.get('subtotal', 'N/A')}")
                            st.write("**Tax Amount:**", f"₹{extracted.get('tax_amount', 'N/A')}")
                            st.write("**Tax Type:**", extracted.get("tax_type", "N/A"))
                            st.write("**Payment Method:**", extracted.get("payment_method", "Unknown"))
                            st.write("**Receipt No:**", extracted.get("receipt_number", "N/A"))
                            if extracted.get("gstin"):
                                st.write("**GSTIN:**", extracted.get("gstin"))

                        with col2:
                            st.write("**Category:**", classification.get("primary_category", "Unknown"))
                            st.write("**Subcategory:**", classification.get("subcategory", "Unknown"))
                            st.write(
                                "**Classification Confidence:**",
                                f"{classification.get('classification_confidence', 0):.0%}"
                            )
                            risk = fraud.get("fraud_risk_score", 0)
                            if risk >= 0.5:
                                st.error(f"**Fraud Risk:** {risk:.2f} — HIGH RISK")
                            elif risk >= 0.3:
                                st.warning(f"**Fraud Risk:** {risk:.2f} — MEDIUM RISK")
                            else:
                                st.success(f"**Fraud Risk:** {risk:.2f} — LOW RISK")
                            st.write("**OCR Confidence:**", f"{ocr.get('confidence_score', 0):.0%}")
                            st.write("**File Type:**", ocr.get("source", "image").upper())
                            st.write("**Expense Status:**", expense_status.replace("_", " ").title())

                        fraud_flags = fraud.get("fraud_flags", [])
                        if fraud_flags:
                            st.subheader("🚨 Fraud Flags Detected")
                            for flag in fraud_flags:
                                st.write(f"• {flag}")

                        line_items = extracted.get("line_items", [])
                        if line_items:
                            st.subheader("🛒 Line Items")
                            df = pd.DataFrame(line_items)
                            st.dataframe(df, use_container_width=True)

                    else:
                        error = response.json().get("detail", "Scan failed")
                        st.error(f"❌ {error}")

                except Exception as e:
                    st.error(f"Could not connect to server: {str(e)}")


# ─────────────────────────────────────────────────────────
# MY EXPENSES PAGE
# ─────────────────────────────────────────────────────────

def show_expenses_page():
    st.title("📋 My Expenses")
    st.caption("Showing only approved expenses. Pending and rejected expenses are excluded.")

    with st.expander("🔍 Filters", expanded=False):
        col1, col2, col3 = st.columns(3)

        with col1:
            vendor_filter = st.text_input("Vendor Name")
            category_filter = st.selectbox(
                "Category",
                [
                    "", "Food & Dining", "Travel & Transport",
                    "Health & Medical", "Office & Supplies",
                    "Utilities", "Entertainment", "Shopping",
                    "Education", "Finance", "Miscellaneous"
                ]
            )

        with col2:
            start_date = st.date_input("Start Date", value=None)
            end_date = st.date_input("End Date", value=None)

        with col3:
            min_amount = st.number_input("Min Amount (₹)", min_value=0.0, value=0.0)
            max_amount = st.number_input("Max Amount (₹)", min_value=0.0, value=0.0)

    params = {}
    if vendor_filter:
        params["vendor_name"] = vendor_filter
    if category_filter:
        params["category"] = category_filter
    if start_date:
        params["start_date"] = str(start_date)
    if end_date:
        params["end_date"] = str(end_date)
    if min_amount > 0:
        params["min_amount"] = min_amount
    if max_amount > 0:
        params["max_amount"] = max_amount

    try:
        response = requests.get(
            f"{BACKEND_URL}/expenses/",
            headers=get_headers(),
            params=params
        )
        data = response.json()
        expenses = data.get("expenses", [])

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Expenses", data.get("count", 0))
        with col2:
            st.metric("Total Spend", f"₹{data.get('total_spend', 0):,.2f}")
        with col3:
            st.metric("Flagged", data.get("flagged_count", 0))

        if expenses:
            df = pd.DataFrame(expenses)
            display_cols = [
                "id", "vendor_name", "total_amount",
                "primary_category", "transaction_date",
                "payment_method", "fraud_risk_score", "status"
            ]
            display_cols = [c for c in display_cols if c in df.columns]
            df_display = df[display_cols].copy()
            df_display.columns = [
                "ID", "Vendor", "Amount (₹)", "Category",
                "Date", "Payment", "Fraud Risk", "Status"
            ]
            st.dataframe(df_display, use_container_width=True)

            csv = df.to_csv(index=False)
            st.download_button(
                label="📥 Download as CSV",
                data=csv,
                file_name="approved_expenses.csv",
                mime="text/csv"
            )
        else:
            st.info("No approved expenses found.")

    except Exception as e:
        st.error(f"Could not load expenses: {str(e)}")


# ─────────────────────────────────────────────────────────
# PENDING VERIFICATION PAGE
# ─────────────────────────────────────────────────────────

def show_pending_page():
    st.title("⚠️ Pending Verification")
    st.caption(
        "These expenses were flagged by our AI fraud detection system. "
        "Review each one and approve or reject it. "
        "Pending expenses are NOT counted in your total spend."
    )

    try:
        response = requests.get(
            f"{BACKEND_URL}/expenses/pending",
            headers=get_headers()
        )
        data = response.json()
        expenses = data.get("expenses", [])

        if not expenses:
            st.success("✅ No expenses pending verification. Everything looks clean!")
            return

        st.warning(f"⚠️ {len(expenses)} expense(s) require your review.")

        for expense in expenses:
            with st.expander(
                f"🔍 {expense.get('vendor_name', 'Unknown Vendor')} — "
                f"₹{expense.get('total_amount', 0)} — "
                f"Risk: {expense.get('fraud_risk_score', 0):.2f}",
                expanded=True
            ):
                col1, col2 = st.columns(2)

                with col1:
                    st.write("**Expense ID:**", expense.get("id"))
                    st.write("**Vendor:**", expense.get("vendor_name", "Unknown"))
                    st.write("**Amount:**", f"₹{expense.get('total_amount', 0)}")
                    st.write("**Category:**", expense.get("primary_category", "Unknown"))
                    st.write("**Date:**", expense.get("transaction_date", "Unknown"))
                    st.write("**OCR Confidence:**", f"{expense.get('confidence_score', 0):.0%}")

                with col2:
                    risk = expense.get("fraud_risk_score", 0)
                    if risk >= 0.7:
                        st.error(f"**Fraud Risk Score:** {risk:.2f} — HIGH RISK")
                    elif risk >= 0.5:
                        st.warning(f"**Fraud Risk Score:** {risk:.2f} — MEDIUM RISK")
                    else:
                        st.info(f"**Fraud Risk Score:** {risk:.2f}")

                    fraud_flags = expense.get("fraud_flags", [])
                    if fraud_flags:
                        st.write("**Fraud Flags:**")
                        for flag in fraud_flags:
                            st.write(f"• {flag}")

                col_approve, col_reject = st.columns(2)

                with col_approve:
                    if st.button(
                        f"✅ Approve",
                        key=f"approve_{expense['id']}",
                        use_container_width=True
                    ):
                        try:
                            resp = requests.put(
                                f"{BACKEND_URL}/expenses/{expense['id']}/approve",
                                headers=get_headers()
                            )
                            if resp.status_code == 200:
                                st.success(
                                    f"✅ Expense approved and added to your expense list!"
                                )
                                st.rerun()
                            else:
                                st.error("Failed to approve expense.")
                        except Exception as e:
                            st.error(f"Error: {str(e)}")

                with col_reject:
                    if st.button(
                        f"❌ Reject",
                        key=f"reject_{expense['id']}",
                        use_container_width=True,
                        type="secondary"
                    ):
                        try:
                            resp = requests.put(
                                f"{BACKEND_URL}/expenses/{expense['id']}/reject",
                                headers=get_headers()
                            )
                            if resp.status_code == 200:
                                st.success(
                                    f"❌ Expense rejected and archived."
                                )
                                st.rerun()
                            else:
                                st.error("Failed to reject expense.")
                        except Exception as e:
                            st.error(f"Error: {str(e)}")

    except Exception as e:
        st.error(f"Could not load pending expenses: {str(e)}")


# ─────────────────────────────────────────────────────────
# REJECTED EXPENSES PAGE
# ─────────────────────────────────────────────────────────

def show_rejected_page():
    st.title("❌ Rejected Expenses")
    st.caption(
        "These expenses were rejected after review. "
        "They are archived and excluded from all expense calculations."
    )

    try:
        response = requests.get(
            f"{BACKEND_URL}/expenses/",
            headers=get_headers(),
            params={"status": "rejected"}
        )
        data = response.json()
        expenses = data.get("expenses", [])

        if not expenses:
            st.info("No rejected expenses found.")
            return

        st.error(f"❌ {len(expenses)} rejected expense(s) archived.")

        df = pd.DataFrame(expenses)
        display_cols = [
            "id", "vendor_name", "total_amount",
            "primary_category", "transaction_date",
            "fraud_risk_score", "status"
        ]
        display_cols = [c for c in display_cols if c in df.columns]
        df_display = df[display_cols].copy()
        df_display.columns = [
            "ID", "Vendor", "Amount (₹)",
            "Category", "Date", "Fraud Risk", "Status"
        ]
        st.dataframe(df_display, use_container_width=True)

    except Exception as e:
        st.error(f"Could not load rejected expenses: {str(e)}")


main()