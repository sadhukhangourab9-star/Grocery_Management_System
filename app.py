import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime

# --- CREDENTIALS CONFIG ---
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
# If running on Render, use secrets. If local, use JSON file.
if "gcp_service_account" in st.secrets:
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
else:
    creds = Credentials.from_service_account_file("google_creds.json", scopes=scope)

client = gspread.authorize(creds)
SHEET_NAME = "Grocery_Management_System"
sh = client.open(SHEET_NAME)

# --- UTILS ---
def get_inventory_sheet():
    month_title = f"Inventory_{datetime.now().strftime('%b_%Y')}"
    return sh.worksheet(month_title)

def get_products():
    return sh.worksheet("Product_Master").col_values(1)[1:]

# --- UI ---
st.set_page_config(page_title="Grocery Inventory", layout="wide")
st.sidebar.title("🛒 Grocery Admin")
menu = st.sidebar.radio("Navigation", ["Amazon Entry", "Receiver View", "Daily Sales", "Inventory Report"])

products = get_products()
inv_ws = get_inventory_sheet()

# --- 1. AMAZON ENTRY ---
if menu == "Amazon Entry":
    st.header("📦 Amazon Order Input")
    with st.form("entry_form"):
        col1, col2, col3 = st.columns(3)
        date = col1.date_input("Order Date")
        slot = col2.selectbox("Slot", ["10 PM", "12 PM", "8 AM", "2 PM"])
        acc = col3.text_input("Account (e.g. Amazon 16/10)")
        
        st.write("---")
        st.write("Enter Quantities:")
        # Create columns for inputs to save vertical space
        cols = st.columns(3)
        input_data = []
        for i, p in enumerate(products):
            with cols[i % 3]:
                qty = st.number_input(f"{p}", min_value=0, step=1, key=f"in_{p}")
                input_data.append(qty)
        
        if st.form_submit_button("Log Order"):
            # Format: Date, Slot, Account, Status, Products...
            row = [str(date), slot, acc, "Pending"] + input_data
            inv_ws.append_row(row)
            st.success("Order Logged in Google Sheets!")

# --- 2. RECEIVER VIEW ---
elif menu == "Receiver View":
    st.header("🚚 Incoming Deliveries")
    data = inv_ws.get_all_records()
    if data:
        df = pd.DataFrame(data)
        # Filter for Pending orders
        pending = df[df['Status'] == 'Pending']
        
        if pending.empty:
            st.success("No pending items to receive!")
        else:
            for index, row in pending.iterrows():
                # Google Sheets is 1-indexed, +1 for header, +1 for row
                sheet_row_index = index + 2 
                
                with st.expander(f"Order: {row['Account']} | Slot: {row['Slot']}"):
                    st.write("**Verify items below:**")
                    for p in products:
                        if row[p] > 0:
                            st.write(f"- {p}: **{row[p]}**")
                    
                    if st.button("Mark as Delivered", key=f"recv_{index}"):
                        # Update status column (Column D = 4)
                        inv_ws.update_cell(sheet_row_index, 4, "Delivered")
                        st.balloons()
                        st.rerun()

# --- 3. DAILY SALES ---
elif menu == "Daily Sales":
    st.header("💰 Record Sales")
    with st.form("sales_form"):
        buyer = st.selectbox("Buyer", ["Rajkumar da", "Souvik da", "Gourab", "Walk-in"])
        prod = st.selectbox("Product", products)
        sqty = st.number_input("Quantity Sold", min_value=1)
        
        if st.form_submit_button("Submit Sale"):
            sh.worksheet("Sales_Log").append_row([str(datetime.now().date()), buyer, prod, sqty])
            st.success("Sale Logged!")

# --- 4. INVENTORY REPORT ---
elif menu == "Inventory Report":
    st.header("📊 Current Stock Status")
    # Simple logic: Delivered - Sold
    inv_data = pd.DataFrame(inv_ws.get_all_records())
    sales_data = pd.DataFrame(sh.worksheet("Sales_Log").get_all_records())
    
    report = []
    for p in products:
        received = inv_data[inv_data['Status'] == 'Delivered'][p].sum()
        sold = 0
        if not sales_data.empty:
            sold = sales_data[sales_data['Product Name'] == p]['Quantity Sold'].sum()
        
        report.append({
            "Product": p,
            "Received": received,
            "Sold": sold,
            "Current Stock": received - sold
        })
    
    st.table(pd.DataFrame(report))