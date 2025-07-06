import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime, timedelta
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

# Database setup
def get_connection():
    """MySQL database connection creation"""
    try:
        conn = mysql.connector.connect(
            user=os.getenv('SQL_USER'),
            password=os.getenv('SQL_PASSWORD'),
            host=os.getenv('SQL_HOST'),
            database=os.getenv('SQL_DATABASE_NEWBIZ'),
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci'
        )
        return conn
    except Error as e:
        st.error(f"Database connection failed: {str(e)}")
        return None

st.title("🌐 JV Process Management Portal")

st.session_state.authenticated = False

admin_pw = os.getenv('ADMIN_PASSWORD')
if not admin_pw:
    st.error('Environment variable (ADMIN_PASSWORD) is not set. Please check your .env file.')
    st.stop()

if not st.session_state.authenticated:
    password = st.text_input("Enter admin password", type="password")
    if password == admin_pw:
        st.session_state.authenticated = True
        st.rerun()
    else:
        if password:  # Show error only if password is entered
            st.error("Admin privileges required.")
        st.stop()
        
# Sample data creation
def create_sample_data(conn):
    """Sample data creation"""
    cursor = conn.cursor()
    
    try:
        # Disable foreign key checks
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        
        # Drop existing tables
        cursor.execute("DROP TABLE IF EXISTS sales")
        cursor.execute("DROP TABLE IF EXISTS production")
        cursor.execute("DROP TABLE IF EXISTS bill_of_materials")
        cursor.execute("DROP TABLE IF EXISTS order_details")
        cursor.execute("DROP TABLE IF EXISTS orders")
        cursor.execute("DROP TABLE IF EXISTS products")
        cursor.execute("DROP TABLE IF EXISTS parts")
        conn.commit()
        
        # 1. Parts table
        cursor.execute('''
            CREATE TABLE parts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                part_code VARCHAR(50) UNIQUE NOT NULL,
                part_name VARCHAR(100) NOT NULL,
                part_category VARCHAR(50),
                supplier VARCHAR(100) NOT NULL,
                unit_price DECIMAL(10, 2) NOT NULL,
                lead_time INT NOT NULL,
                stock INT DEFAULT 0,
                min_stock INT DEFAULT 0,
                specifications TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        ''')

        # 2. Products table
        cursor.execute('''
            CREATE TABLE products (
                id INT AUTO_INCREMENT PRIMARY KEY,
                product_code VARCHAR(50) UNIQUE NOT NULL,
                product_name VARCHAR(100) NOT NULL,
                product_type VARCHAR(50) NOT NULL,
                size VARCHAR(50) NOT NULL,
                brand VARCHAR(100) NOT NULL,
                selling_price DECIMAL(10, 2) NOT NULL,
                production_cost DECIMAL(10, 2) NOT NULL,
                stock INT DEFAULT 0,
                specifications TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        ''')

        # 3. Orders table
        cursor.execute('''
            CREATE TABLE orders (
                id INT AUTO_INCREMENT PRIMARY KEY,
                order_number VARCHAR(50) UNIQUE NOT NULL,
                order_date DATE NOT NULL,
                expected_arrival DATE NOT NULL,
                status VARCHAR(20) NOT NULL,
                total_amount DECIMAL(10, 2) NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        ''')

        # 4. Order details table
        cursor.execute('''
            CREATE TABLE order_details (
                id INT AUTO_INCREMENT PRIMARY KEY,
                order_id INT NOT NULL,
                part_id INT NOT NULL,
                quantity INT NOT NULL,
                unit_price DECIMAL(10, 2) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders(id),
                FOREIGN KEY (part_id) REFERENCES parts(id)
            )
        ''')

        # 5. Bill of Materials (BOM) table
        cursor.execute('''
            CREATE TABLE bill_of_materials (
                id INT AUTO_INCREMENT PRIMARY KEY,
                product_id INT NOT NULL,
                part_id INT NOT NULL,
                quantity_required INT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id),
                FOREIGN KEY (part_id) REFERENCES parts(id)
            )
        ''')

        # 6. Production table
        cursor.execute('''
            CREATE TABLE production (
                id INT AUTO_INCREMENT PRIMARY KEY,
                batch_number VARCHAR(50) UNIQUE NOT NULL,
                product_id INT NOT NULL,
                quantity INT NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE,
                status VARCHAR(20) NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        ''')

        # 7. Sales table
        cursor.execute('''
            CREATE TABLE sales (
                id INT AUTO_INCREMENT PRIMARY KEY,
                invoice_number VARCHAR(50) UNIQUE NOT NULL,
                sale_date DATE NOT NULL,
                customer VARCHAR(100) NOT NULL,
                product_id INT NOT NULL,
                quantity INT NOT NULL,
                unit_price DECIMAL(10, 2) NOT NULL,
                total_amount DECIMAL(10, 2) NOT NULL,
                payment_method VARCHAR(50) NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        ''')
        conn.commit()

        # Insert sample data
        # 1. Parts data
        parts = [
            ('PT001', 'Aluminum Frame', 'Frame', 'YUER', 50000, 7, 100, 20),
            ('PT002', 'Reinforced Glass', 'Glass', 'YUER', 30000, 5, 80, 15),
            ('PT003', 'Motor', 'Motor', 'YUER', 20000, 10, 50, 10),
            ('PT004', 'Control Board', 'Electronic', 'YUER', 15000, 7, 60, 12),
            ('PT005', 'Silicone Seal', 'Sealing', 'YUER', 5000, 3, 200, 40)
        ]
        
        cursor.executemany('''
            INSERT INTO parts (part_code, part_name, part_category, supplier, unit_price, lead_time, stock, min_stock)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', parts)
            
        # 2. Products data
        products = [
            ('PR001', 'V6 Engine', 'Fixed', 'Large', 'YUER', 5000000, 3000000, 10),
            ('PR002', 'V8 Engine', 'Fixed', 'Large', 'YUER', 8000000, 4800000, 5),
            ('PR003', 'I4 Engine', 'Fixed', 'Medium', 'YUER', 3000000, 1800000, 15),
            ('PR004', 'Diesel Engine', 'Fixed', 'Large', 'YUER', 6000000, 3600000, 8),
            ('PR005', 'Hybrid Engine', 'Automatic', 'Medium', 'YUER', 7000000, 4200000, 12)
        ]
        
        cursor.executemany('''
            INSERT INTO products (product_code, product_name, product_type, size, brand, selling_price, production_cost, stock)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', products)

        conn.commit()
        
        # Re-enable foreign key checks
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()
        
        return True
        
    except mysql.connector.Error as err:
        st.error(f"Error occurred during sample data creation: {err}")
        return False
    finally:
        cursor.close()

# App layout and features
def main():
    st.set_page_config(
        page_title="YUER-Korea Joint Venture Management System",
        page_icon="🏭",
        layout="wide"
    )
    
    # Database initialization
    conn = get_connection()
    if conn:
        # Table creation check
        if not create_sample_data(conn):
            st.error("Failed to create tables. Please create tables from the database management page.")
            return
            
        # Sidebar menu
        st.sidebar.title("YUER-AqaraLife Joint Venture")
        menu = st.sidebar.selectbox(
            "Select Menu",
            ["Dashboard", "Parts Management", "Parts Orders", "Production Management", "Products Management", "Sales Management", "Sales Analysis", "Inventory Management", "Settings"]
        )
        
        # Render page by menu
        if menu == "Dashboard":
            display_dashboard(conn)
        elif menu == "Parts Management":
            display_parts_management(conn)
        elif menu == "Parts Orders":
            display_orders_management(conn)
        elif menu == "Production Management":
            display_production_management(conn)
        elif menu == "Products Management":
            display_products_management(conn)
        elif menu == "Sales Management":
            display_sales_management(conn)
        elif menu == "Sales Analysis":
            display_sales_analysis(conn)
        elif menu == "Inventory Management":
            display_inventory_management(conn)
        elif menu == "Settings":
            display_settings(conn)
        
        # Close database connection
        conn.close()

# Dashboard page
def display_dashboard(conn):
    st.title("Joint Venture Dashboard")
    
    # Display main KPIs at the top
    col1, col2, col3, col4 = st.columns(4)
    
    # Total parts import amount
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(total_amount) FROM orders WHERE status != 'Cancelled'")
    total_import = cursor.fetchone()[0]
    if total_import is None:
        total_import = 0
    
    # Total production quantity
    cursor.execute("SELECT SUM(quantity) FROM production WHERE status = 'Completed'")
    total_production = cursor.fetchone()[0]
    if total_production is None:
        total_production = 0
    
    # Total sales amount
    cursor.execute("SELECT SUM(total_amount) FROM sales")
    total_sales = cursor.fetchone()[0]
    if total_sales is None:
        total_sales = 0
    
    # Number of low stock parts
    cursor.execute("SELECT COUNT(*) FROM parts WHERE stock < min_stock")
    low_stock_items = cursor.fetchone()[0]
    
    with col1:
        st.metric(label="Total Parts Import Amount", value=f"₩{total_import:,.0f}")
    
    with col2:
        st.metric(label="Total Production Quantity", value=f"{total_production:,} units")
    
    with col3:
        st.metric(label="Total Sales Amount", value=f"₩{total_sales:,.0f}")
    
    with col4:
        st.metric(label="Low Stock Items", value=f"{low_stock_items} items")
    
    st.markdown("---")
    
    # Second row: charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Monthly Parts Import & Product Sales Trend")
        
        # Monthly order data
        cursor.execute("""
        SELECT DATE_FORMAT(order_date, '%Y-%m') as month, SUM(total_amount) as total
        FROM orders
        WHERE status != 'Cancelled'
        GROUP BY month
        ORDER BY month
        """)
        order_data = cursor.fetchall()
        
        # Monthly sales data
        cursor.execute("""
        SELECT DATE_FORMAT(sale_date, '%Y-%m') as month, SUM(total_amount) as total
        FROM sales
        GROUP BY month
        ORDER BY month
        """)
        sales_data = cursor.fetchall()
        
        # Convert data to DataFrame
        order_df = pd.DataFrame(order_data, columns=['month', 'total'])
        order_df['type'] = 'Parts Import'
        
        sales_df = pd.DataFrame(sales_data, columns=['month', 'total'])
        sales_df['type'] = 'Product Sales'
        
        # Combine data
        combined_df = pd.concat([order_df, sales_df])
        
        if not combined_df.empty:
            fig = px.line(combined_df, x='month', y='total', color='type',
                        title='Monthly Parts Import & Product Sales Trend',
                        labels={'month': 'Month', 'total': 'Amount (₩)', 'type': 'Type'})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Not enough data available.")
    
    with col2:
        st.subheader("Sales Distribution by Product")
        
        # Sales data by product
        cursor.execute("""
        SELECT p.product_name, SUM(s.quantity) as total_quantity
        FROM sales s
        JOIN products p ON s.product_id = p.id
        GROUP BY p.product_name
        ORDER BY total_quantity DESC
        """)
        product_sales = cursor.fetchall()
        
        if product_sales:
            product_sales_df = pd.DataFrame(product_sales, columns=['product_name', 'total_quantity'])
            fig = px.pie(product_sales_df, values='total_quantity', names='product_name',
                        title='Sales Distribution by Product')
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No sales data available.")
    
    # Third row: parts inventory and production status
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Parts Inventory Status")
        
        # Parts inventory data
        cursor.execute("""
        SELECT part_name, stock, min_stock
        FROM parts
        ORDER BY (stock * 1.0 / min_stock) ASC
        """)
        part_stocks = cursor.fetchall()
        
        if part_stocks:
            part_stocks_df = pd.DataFrame(part_stocks, columns=['part_name', 'stock', 'min_stock'])
            
            # Horizontal bar chart
            fig = go.Figure()
            
            fig.add_trace(go.Bar(
                y=part_stocks_df['part_name'],
                x=part_stocks_df['stock'],
                orientation='h',
                name='Current Stock',
                marker_color='#1f77b4'
            ))
            
            fig.add_trace(go.Bar(
                y=part_stocks_df['part_name'],
                x=part_stocks_df['min_stock'],
                orientation='h',
                name='Minimum Stock',
                marker_color='rgba(255, 0, 0, 0.5)',
                opacity=0.5
            ))
            
            fig.update_layout(
                title='Parts Inventory Status',
                xaxis_title='Quantity',
                yaxis_title='Part Name',
                barmode='overlay'
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No parts data available.")
    
    with col2:
        st.subheader("Production Status")
        
        # Production data by status
        cursor.execute("""
        SELECT status, COUNT(*) as count
        FROM production
        GROUP BY status
        """)
        production_status = cursor.fetchall()
        
        if production_status:
            production_status_df = pd.DataFrame(production_status, columns=['status', 'count'])
            
            colors = {
                'Planned': '#FFA15A',
                'In Progress': '#636EFA',
                'Completed': '#00CC96',
                'Delayed': '#EF553B'
            }
            
            fig = px.bar(production_status_df, x='status', y='count',
                        title='Number of Batches by Production Status',
                        labels={'status': 'Status', 'count': 'Batch Count'},
                        color='status',
                        color_discrete_map=colors)
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Recent production batches
            st.subheader("Recent Production Batches")
            
            cursor.execute("""
            SELECT p.batch_number, pr.product_name, p.quantity, p.status, p.start_date, p.end_date
            FROM production p
            JOIN products pr ON p.product_id = pr.id
            ORDER BY p.start_date DESC
            LIMIT 5
            """)
            recent_production = cursor.fetchall()
            
            if recent_production:
                recent_production_df = pd.DataFrame(recent_production, 
                                                   columns=['Batch Number', 'Product Name', 'Quantity', 'Status', 'Start Date', 'End Date'])
                st.dataframe(recent_production_df, use_container_width=True)
            else:
                st.info("No production data available.")
        else:
            st.info("No production data available.")

# Parts Management Page
def display_parts_management(conn):
    st.title("Parts Management")
    
    tab1, tab2 = st.tabs(["Parts List", "Add/Edit Part"])
    
    with tab1:
        st.subheader("Parts List")
        
        # Fetch parts data
        cursor = conn.cursor()
        cursor.execute("""
        SELECT id, part_code, part_name, supplier, unit_price, lead_time, stock, min_stock
        FROM parts
        ORDER BY part_code
        """)
        parts_data = cursor.fetchall()
        
        if parts_data:
            parts_df = pd.DataFrame(parts_data, 
                                  columns=['ID', 'Part Code', 'Part Name', 'Supplier', 'Unit Price (₩)', 'Lead Time (days)', 'Current Stock', 'Minimum Stock'])
            
            # Stock status
            parts_df['Stock Status'] = parts_df.apply(
                lambda row: 'Low' if row['Current Stock'] < row['Minimum Stock'] else 'Normal', 
                axis=1
            )
            
            st.dataframe(parts_df, use_container_width=True)
            
            st.subheader("Stock Status by Part")
            
            chart_data = parts_df[['Part Name', 'Current Stock', 'Minimum Stock']]
            
            fig = go.Figure()
            
            fig.add_trace(go.Bar(
                x=chart_data['Part Name'],
                y=chart_data['Current Stock'],
                name='Current Stock',
                marker_color='#1f77b4'
            ))
            
            fig.add_trace(go.Scatter(
                x=chart_data['Part Name'],
                y=chart_data['Minimum Stock'],
                name='Minimum Stock',
                mode='lines+markers',
                marker_color='red'
            ))
            
            fig.update_layout(
                title='Stock Status by Part',
                xaxis_title='Part Name',
                yaxis_title='Quantity'
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No parts registered.")
    
    with tab2:
        st.subheader("Add/Edit Part")
        
        # Add part form
        with st.form("part_form"):
            st.write("Register New Part")
            part_code = st.text_input("Part Code")
            part_name = st.text_input("Part Name")
            supplier = st.text_input("Supplier", value="YUER")
            unit_price = st.number_input("Unit Price (₩)", min_value=0.0, step=0.1)
            lead_time = st.number_input("Lead Time (days)", min_value=1, step=1)
            stock = st.number_input("Current Stock", min_value=0, step=1)
            min_stock = st.number_input("Minimum Stock", min_value=0, step=1)
            
            submitted = st.form_submit_button("Add Part")
            
            if submitted:
                if not part_code or not part_name:
                    st.error("Part code and name are required.")
                else:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO parts (part_code, part_name, supplier, unit_price, lead_time, stock, min_stock) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                        (part_code, part_name, supplier, unit_price, lead_time, stock, min_stock)
                    )
                    conn.commit()
                    st.success(f"Part '{part_name}' added successfully!")
        
        st.markdown("---")
        st.write("Edit Part Information")
        
        # Fetch part list
        cursor = conn.cursor()
        cursor.execute("SELECT id, part_code, part_name FROM parts ORDER BY part_code")
        parts = cursor.fetchall()
        
        if parts:
            part_options = {f"{p[1]} - {p[2]}": p[0] for p in parts}
            selected_part = st.selectbox("Select Part to Edit", list(part_options.keys()))
            
            part_id = part_options[selected_part]
            
            # Fetch selected part info
            cursor.execute(
                "SELECT part_code, part_name, supplier, unit_price, lead_time, stock, min_stock FROM parts WHERE id = %s",
                (part_id,)
            )
            part_data = cursor.fetchone()
            
            if part_data:
                with st.form("edit_part_form"):
                    st.write(f"Edit '{part_data[1]}' Information")
                    
                    edit_part_code = st.text_input("Part Code", value=part_data[0])
                    edit_part_name = st.text_input("Part Name", value=part_data[1])
                    edit_supplier = st.text_input("Supplier", value=part_data[2])
                    edit_unit_price = st.number_input("Unit Price (₩)", min_value=0.0, step=0.1, value=float(part_data[3]))
                    edit_lead_time = st.number_input("Lead Time (days)", min_value=1, step=1, value=int(part_data[4]))
                    edit_stock = st.number_input("Current Stock", min_value=0, step=1, value=int(part_data[5]))
                    edit_min_stock = st.number_input("Minimum Stock", min_value=0, step=1, value=int(part_data[6]))
                    
                    update_submitted = st.form_submit_button("Update Information")
                    
                    if update_submitted:
                        cursor.execute(
                            "UPDATE parts SET part_code = %s, part_name = %s, supplier = %s, unit_price = %s, lead_time = %s, stock = %s, min_stock = %s WHERE id = %s",
                            (edit_part_code, edit_part_name, edit_supplier, edit_unit_price, edit_lead_time, edit_stock, edit_min_stock, part_id)
                        )
                        conn.commit()
                        st.success(f"Part '{edit_part_name}' updated successfully!")
        else:
            st.info("No parts registered.")

# Parts Orders Management Page
def display_orders_management(conn):
    st.title("Parts Orders Management")
    
    tab1, tab2, tab3 = st.tabs(["Order List", "Create New Order", "Order Status Management"])
    
    with tab1:
        st.subheader("Order List")
        
        # Fetch order data
        cursor = conn.cursor()
        cursor.execute("""
        SELECT o.id, o.order_number, o.order_date, o.expected_arrival, o.status, o.total_amount,
               COUNT(od.id) as item_count, SUM(od.quantity) as total_quantity
        FROM orders o
        LEFT JOIN order_details od ON o.id = od.order_id
        GROUP BY o.id
        ORDER BY o.order_date DESC
        """)
        orders_data = cursor.fetchall()
        
        if orders_data:
            orders_df = pd.DataFrame(orders_data, 
                                   columns=['ID', 'Order Number', 'Order Date', 'Expected Arrival', 'Status', 'Total Amount (₩)', 'Item Count', 'Total Quantity'])
            
            # Date formatting
            orders_df['Order Date'] = pd.to_datetime(orders_df['Order Date']).dt.strftime('%Y-%m-%d')
            orders_df['Expected Arrival'] = pd.to_datetime(orders_df['Expected Arrival']).dt.strftime('%Y-%m-%d')
            
            # Status color highlight
            def highlight_status(val):
                if val == 'Delivered':
                    return 'background-color: #d4f7d4'
                elif val == 'Shipped':
                    return 'background-color: #d4e5f7'
                elif val == 'Pending':
                    return 'background-color: #f7f7d4'
                elif val == 'Cancelled':
                    return 'background-color: #f7d4d4'
                return ''
            
            st.dataframe(orders_df.style.applymap(highlight_status, subset=['Status']), use_container_width=True)
            
            st.subheader("Order Details")
            selected_order = st.selectbox("Select Order", orders_df['Order Number'].tolist())
            
            if selected_order:
                order_id = int(orders_df.loc[orders_df['Order Number'] == selected_order, 'ID'].iloc[0])
                
                cursor.execute("""
                SELECT od.id, p.part_code, p.part_name, p.part_category, od.quantity, od.unit_price, (od.quantity * od.unit_price) as subtotal
                FROM order_details od
                JOIN parts p ON od.part_id = p.id
                WHERE od.order_id = %s
                """, (order_id,))
                order_details = cursor.fetchall()
                
                if order_details:
                    details_df = pd.DataFrame(order_details, 
                                            columns=['ID', 'Part Code', 'Part Name', 'Category', 'Quantity', 'Unit Price (₩)', 'Subtotal (₩)'])
                    st.dataframe(details_df, use_container_width=True)
                    
                    total_amount = float(details_df['Subtotal (₩)'].sum())
                    st.metric("Order Total Amount", f"₩{total_amount:,.0f}")
                else:
                    st.info("No details for this order.")
        else:
            st.info("No orders registered.")
    
    with tab2:
        st.subheader("Create New Order")
        
        today = datetime.now().date()
        
        with st.form("new_order_form"):
            order_number = st.text_input("Order Number", value=f"ORD-{today.strftime('%Y%m%d')}-{np.random.randint(1000, 9999)}")
            order_date = st.date_input("Order Date", value=today)
            expected_arrival = st.date_input("Expected Arrival", value=today + timedelta(days=14))
            
            # Parts selection
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, part_code, part_name, part_category, unit_price 
                FROM parts 
                ORDER BY part_category, part_code
            """)
            available_parts = cursor.fetchall()
            
            if available_parts:
                part_options = {f"{p[1]} - {p[2]} ({p[3]}) (₩{p[4]:,.0f})": p[0] for p in available_parts}
                selected_parts = st.multiselect("Select Parts to Order", list(part_options.keys()))
                
                quantities = {}
                total_amount = 0
                
                if selected_parts:
                    st.write("Enter order quantity for each part:")
                    
                    for part in selected_parts:
                        part_id = int(part_options[part])
                        part_name = part.split(' - ')[1].split(' (')[0]
                        
                        cursor.execute("SELECT unit_price FROM parts WHERE id = %s", (part_id,))
                        unit_price = float(cursor.fetchone()[0])
                        
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.write(part)
                        with col2:
                            quantity = int(st.number_input(f"{part_name} Quantity", min_value=1, value=10, key=f"qty_{part_id}"))
                            quantities[part_id] = quantity
                            total_amount += quantity * unit_price
                
                st.metric("Order Total Amount", f"₩{float(total_amount):,.0f}")
                
                submitted = st.form_submit_button("Create Order")
                
                if submitted:
                    if not selected_parts:
                        st.error("Select at least one part.")
                    else:
                        cursor.execute(
                            "INSERT INTO orders (order_number, order_date, expected_arrival, status, total_amount) VALUES (%s, %s, %s, %s, %s)",
                            (order_number, order_date, expected_arrival, "Pending", float(total_amount))
                        )
                        conn.commit()
                        
                        cursor.execute("SELECT LAST_INSERT_ID()")
                        order_id = int(cursor.fetchone()[0])
                        
                        for part_id, quantity in quantities.items():
                            cursor.execute("SELECT unit_price FROM parts WHERE id = %s", (int(part_id),))
                            unit_price = float(cursor.fetchone()[0])
                            
                            cursor.execute(
                                "INSERT INTO order_details (order_id, part_id, quantity, unit_price) VALUES (%s, %s, %s, %s)",
                                (order_id, part_id, quantity, unit_price)
                            )
                        
                        conn.commit()
                        st.success(f"Order '{order_number}' created successfully!")
            else:
                st.error("No parts registered. Please register parts first.")
    
    with tab3:
        st.subheader("Order Status Management")
        
        cursor = conn.cursor()
        cursor.execute("""
        SELECT id, order_number, order_date, expected_arrival, status, total_amount
        FROM orders
        WHERE status IN ('Pending', 'Shipped')
        ORDER BY order_date
        """)
        active_orders = cursor.fetchall()
        
        if active_orders:
            active_orders_df = pd.DataFrame(active_orders, 
                                         columns=['ID', 'Order Number', 'Order Date', 'Expected Arrival', 'Current Status', 'Total Amount (₩)'])
            
            active_orders_df['Order Date'] = pd.to_datetime(active_orders_df['Order Date']).dt.strftime('%Y-%m-%d')
            active_orders_df['Expected Arrival'] = pd.to_datetime(active_orders_df['Expected Arrival']).dt.strftime('%Y-%m-%d')
            
            st.dataframe(active_orders_df, use_container_width=True)
            
            st.write("Update Order Status")
            
            col1, col2 = st.columns(2)
            
            with col1:
                order_to_update = st.selectbox("Select Order to Update", active_orders_df['Order Number'].tolist())
            
            with col2:
                new_status = st.selectbox("New Status", ["Pending", "Shipped", "Delivered", "Cancelled"])
            
            if st.button("Update Status"):
                order_id = int(active_orders_df.loc[active_orders_df['Order Number'] == order_to_update, 'ID'].iloc[0])
                
                cursor.execute(
                    "UPDATE orders SET status = %s WHERE id = %s",
                    (new_status, order_id)
                )
                conn.commit()
                
                if new_status == "Delivered":
                    cursor.execute("""
                    SELECT part_id, quantity
                    FROM order_details
                    WHERE order_id = %s
                    """, (order_id,))
                    order_details = cursor.fetchall()
                    
                    for part_id, quantity in order_details:
                        cursor.execute(
                            "UPDATE parts SET stock = stock + %s WHERE id = %s",
                            (int(quantity), int(part_id))
                        )
                    
                    conn.commit()
                    st.success(f"Order '{order_to_update}' status updated to '{new_status}'. Parts stock updated.")
                else:
                    st.success(f"Order '{order_to_update}' status updated to '{new_status}'.")
        else:
            st.info("No pending or shipped orders.")

# Production Management Page
def display_production_management(conn):
    """Production management dashboard"""
    st.header("Production Management")
    
    # Production status query
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT 
            p.batch_number,
            pr.product_name,
            p.quantity,
            p.start_date,
            p.end_date,
            p.status
        FROM production p
        JOIN products pr ON p.product_id = pr.id
        ORDER BY p.start_date DESC
    """)
    productions = cursor.fetchall()
    
    # Production status display
    if productions:
        df = pd.DataFrame(productions)
        
        # Status-based color
        def highlight_status(val):
            color = 'lightgray'
            if val == 'Completed':
                color = 'lightgreen'
            elif val == 'In Progress':
                color = 'lightblue'
            elif val == 'Delayed':
                color = 'lightcoral'
            return f'background-color: {color}'
        
        st.dataframe(
            df.style.applymap(highlight_status, subset=['status']),
            use_container_width=True
        )
        
        # Low stock parts check
        shortage = False  # Initialize shortage variable
        for production in productions:
            if production['status'] == 'Delayed':
                shortage = True
                break
        
        if shortage:
            st.warning("⚠️ Some production is delayed. Please check parts stock.")
            
            # Low stock parts list query
            cursor.execute("""
                SELECT 
                    pa.part_name,
                    pa.stock,
                    pa.min_stock
                FROM parts pa
                WHERE pa.stock < pa.min_stock
            """)
            shortage_parts = cursor.fetchall()
            
            if shortage_parts:
                st.subheader("Low Stock Parts List")
                shortage_df = pd.DataFrame(shortage_parts)
                st.dataframe(shortage_df, use_container_width=True)
    
    else:
        st.info("No production data available.")
    
    cursor.close()

# Sales Management Page
def display_sales_management(conn):
    """Sales management page"""
    st.title("Sales Management")
    
    tab1, tab2 = st.tabs(["Sales Record", "New Sale Registration"])
    
    with tab1:
        st.subheader("Sales Record")
        
        # Sales data query
        cursor = conn.cursor()
        cursor.execute("""
        SELECT s.id, s.invoice_number, s.sale_date, s.customer, p.product_name, s.quantity, s.unit_price, s.total_amount
        FROM sales s
        JOIN products p ON s.product_id = p.id
        ORDER BY s.sale_date DESC
        """)
        sales_data = cursor.fetchall()
        
        if sales_data:
            sales_df = pd.DataFrame(sales_data, 
                                 columns=['ID', 'Invoice Number', 'Sale Date', 'Customer', 'Product Name', 'Quantity', 'Unit Price (₩)', 'Total Amount (₩)'])
            
            # Date formatting
            sales_df['Sale Date'] = pd.to_datetime(sales_df['Sale Date']).dt.strftime('%Y-%m-%d')
            
            # Dataframe display
            st.dataframe(sales_df, use_container_width=True)
        else:
            st.info("No sales record registered.")
    
    with tab2:
        st.subheader("New Sale Registration")
        
        with st.form("new_sale_form"):
            today = datetime.now().date()
            invoice_number = st.text_input("Invoice Number", value=f"INV-{today.strftime('%Y%m%d')}-{np.random.randint(1000, 9999)}")
            sale_date = st.date_input("Sale Date", value=today)
            customer = st.text_input("Customer Name")
            
            # Product selection
            cursor = conn.cursor()
            cursor.execute("SELECT id, product_code, product_name, selling_price, stock FROM products ORDER BY product_name")
            products = cursor.fetchall()
            
            if products:
                product_options = {f"{p[1]} - {p[2]} (₩{p[3]:,.0f}) (Stock: {p[4]} units)": p[0] for p in products}
                selected_product = st.selectbox("Product Selection", list(product_options.keys()))
                
                if selected_product:
                    product_id = product_options[selected_product]
                    
                    # Selected product stock check
                    cursor.execute("SELECT stock FROM products WHERE id = %s", (product_id,))
                    current_stock = cursor.fetchone()[0]
                    
                    quantity = st.number_input("Quantity", min_value=1, max_value=current_stock, value=1)
                    
                    # Selected product unit price query
                    cursor.execute("SELECT selling_price FROM products WHERE id = %s", (product_id,))
                    unit_price = float(cursor.fetchone()[0])
                    total_amount = quantity * unit_price
                    
                    st.metric("Total Sales Amount", f"₩{total_amount:,.0f}")
                    
                    payment_method = st.selectbox("Payment Method", ["Cash", "Card", "Bank Transfer", "Other"])
                    notes = st.text_area("Notes")
                    
                    submitted = st.form_submit_button("Register Sale")
                    
                    if submitted:
                        if not customer:
                            st.error("Customer name is required.")
                        else:
                            try:
                                # Transaction start
                                conn.start_transaction()
                                
                                # Sales record addition
                                cursor.execute("""
                                    INSERT INTO sales (
                                        invoice_number, sale_date, customer, product_id, quantity,
                                        unit_price, total_amount, payment_method, notes
                                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """, (invoice_number, sale_date, customer, product_id, quantity,
                                      unit_price, total_amount, payment_method, notes))
                                
                                # Product stock update
                                cursor.execute("""
                                    UPDATE products SET stock = stock - %s WHERE id = %s
                                """, (quantity, product_id))
                                
                                # Transaction commit
                                conn.commit()
                                st.success("Sale registered successfully.")
                                st.rerun()
                                
                            except mysql.connector.Error as err:
                                # Error handling rollback
                                conn.rollback()
                                st.error(f"Sale registration error: {err}")
                            finally:
                                cursor.close()
            else:
                st.error("No registered products. Please register products first.")

# Sales Analysis Page
def display_sales_analysis(conn):
    st.title("Sales Analysis")
    
    # Sales data query
    cursor = conn.cursor()
    cursor.execute("""
    SELECT s.id, s.invoice_number, s.sale_date, s.customer, p.product_name, s.quantity, s.unit_price, s.total_amount
    FROM sales s
    JOIN products p ON s.product_id = p.id
    ORDER BY s.sale_date DESC
    """)
    sales_data = cursor.fetchall()
    
    if sales_data:
        sales_df = pd.DataFrame(sales_data, 
                             columns=['ID', 'Invoice Number', 'Sale Date', 'Customer', 'Product Name', 'Quantity', 'Unit Price (₩)', 'Total Amount (₩)'])
        
        # Date formatting
        sales_df['Sale Date'] = pd.to_datetime(sales_df['Sale Date']).dt.strftime('%Y-%m-%d')
        
        # Period selection filter
        st.subheader("Period Selection")
        col1, col2 = st.columns(2)
        
        with col1:
            # Minimum/Maximum date calculation
            min_date = pd.to_datetime(sales_df['Sale Date']).min()
            max_date = pd.to_datetime(sales_df['Sale Date']).max()
            
            start_date = st.date_input("Start Date", min_date, min_value=min_date, max_value=max_date)
        
        with col2:
            end_date = st.date_input("End Date", max_date, min_value=min_date, max_value=max_date)
        
        # Filtered data
        filtered_df = sales_df[
            (pd.to_datetime(sales_df['Sale Date']) >= pd.to_datetime(start_date)) & 
            (pd.to_datetime(sales_df['Sale Date']) <= pd.to_datetime(end_date))
        ]
        
        # Time aggregation unit selection
        time_unit = st.selectbox("Time Unit", ["Daily", "Weekly", "Monthly"])
        
        # Aggregated data generation
        time_df = pd.to_datetime(filtered_df['Sale Date'])
        
        if time_unit == "Daily":
            filtered_df['Aggregation Period'] = time_df.dt.strftime('%Y-%m-%d')
        elif time_unit == "Weekly":
            filtered_df['Aggregation Period'] = time_df.dt.strftime('%Y-W%U')
        else:  # Monthly
            filtered_df['Aggregation Period'] = time_df.dt.strftime('%Y-%m')
        
        # Aggregated data
        agg_data = filtered_df.groupby('Aggregation Period').agg({
            'Total Amount (₩)': 'sum',
            'ID': 'count'
        }).reset_index()
        agg_data.columns = ['Period', 'Total Sales Amount (₩)', 'Sales Count']
        
        # KPI metrics
        st.subheader("Sales Summary")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            total_sales = filtered_df['Total Amount (₩)'].sum()
            st.metric("Total Sales Amount", f"₩{total_sales:,.0f}")
        
        with col2:
            total_orders = len(filtered_df)
            st.metric("Total Sales Count", f"{total_orders}")
        
        with col3:
            if total_orders > 0:
                avg_order_value = total_sales / total_orders
                st.metric("Average Sales Amount", f"₩{avg_order_value:,.0f}")
            else:
                st.metric("Average Sales Amount", "₩0")
        
        # Sales trend chart
        st.subheader(f"{time_unit} Sales Trend")
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=agg_data['Period'],
            y=agg_data['Total Sales Amount (₩)'],
            name='Total Sales Amount',
            marker_color='#1f77b4'
        ))
        
        fig.add_trace(go.Scatter(
            x=agg_data['Period'],
            y=agg_data['Sales Count'],
            name='Sales Count',
            mode='lines+markers',
            marker_color='red',
            yaxis='y2'
        ))
        
        fig.update_layout(
            title=f"{time_unit} Sales Trend",
            xaxis_title='Period',
            yaxis_title='Sales Amount (₩)',
            yaxis2=dict(
                title='Sales Count',
                overlaying='y',
                side='right'
            )
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Product-based sales analysis
        st.subheader("Product-based Sales Analysis")
        
        # Product aggregation
        product_agg = filtered_df.groupby('Product Name').agg({
            'Total Amount (₩)': 'sum',
            'Quantity': 'sum',
            'ID': 'count'
        }).reset_index()
        product_agg.columns = ['Product Name', 'Total Sales Amount (₩)', 'Total Sales Quantity', 'Sales Count']
        
        # Product share calculation
        product_agg['Sales Share (%)'] = (product_agg['Total Sales Amount (₩)'] / product_agg['Total Sales Amount (₩)'].sum() * 100).round(1)
        product_agg['Quantity Share (%)'] = (product_agg['Total Sales Quantity'] / product_agg['Total Sales Quantity'].sum() * 100).round(1)
        
        # Sorting
        product_agg = product_agg.sort_values('Total Sales Amount (₩)', ascending=False).reset_index(drop=True)
        
        # Table display
        st.dataframe(product_agg, use_container_width=True)
        
        # Product sales pie chart
        col1, col2 = st.columns(2)
        
        with col1:
            fig = px.pie(product_agg, values='Total Sales Amount (₩)', names='Product Name',
                      title='Product Sales Amount Share',
                      hover_data=['Sales Share (%)'],
                      labels={'Total Sales Amount (₩)': 'Sales Amount'})
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            fig = px.pie(product_agg, values='Total Sales Quantity', names='Product Name',
                      title='Product Sales Quantity Share',
                      hover_data=['Quantity Share (%)'],
                      labels={'Total Sales Quantity': 'Sales Quantity'})
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
        
        # Customer-based sales analysis
        st.subheader("Customer-based Sales Analysis")
        
        # Customer aggregation
        customer_agg = filtered_df.groupby('Customer').agg({
            'Total Amount (₩)': 'sum',
            'ID': 'count'
        }).reset_index()
        customer_agg.columns = ['Customer', 'Total Sales Amount (₩)', 'Sales Count']
        
        # Customer share calculation
        customer_agg['Sales Share (%)'] = (customer_agg['Total Sales Amount (₩)'] / customer_agg['Total Sales Amount (₩)'].sum() * 100).round(1)
        
        # Sorting
        customer_agg = customer_agg.sort_values('Total Sales Amount (₩)', ascending=False).reset_index(drop=True)
        
        # Table display
        st.dataframe(customer_agg, use_container_width=True)
        
        # Top customer bar chart
        top_n = min(len(customer_agg), 10)  # Display up to 10 only
        
        fig = px.bar(customer_agg.head(top_n), 
                   x='Customer', y='Total Sales Amount (₩)',
                   title=f'Top {top_n} Customers Sales',
                   color='Total Sales Amount (₩)',
                   labels={'Customer': 'Customer Name', 'Total Sales Amount (₩)': 'Total Sales Amount (₩)'})
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Sales data table
        st.subheader("Sales Detailed Data")
        st.dataframe(filtered_df, use_container_width=True)
    else:
        st.info("No sales data available.")

# Inventory Management Page
def display_inventory_management(conn):
    st.title("Inventory Management")
    
    tab1, tab2 = st.tabs(["Parts Inventory", "Products Inventory"])
    
    with tab1:
        st.subheader("Parts Inventory Status")
        
        # Parts inventory data query
        cursor = conn.cursor()
        cursor.execute("""
        SELECT id, part_code, part_name, supplier, stock, min_stock, unit_price, (stock * unit_price) as stock_value
        FROM parts
        ORDER BY (stock * 1.0 / min_stock) ASC
        """)
        parts_stock_data = cursor.fetchall()
        
        if parts_stock_data:
            parts_stock_df = pd.DataFrame(parts_stock_data, 
                                        columns=['ID', 'Part Code', 'Part Name', 'Supplier', 'Current Stock', 'Minimum Stock', 'Unit Price (₩)', 'Stock Value (₩)'])
            
            # Stock status calculation
            parts_stock_df['Stock Status'] = parts_stock_df.apply(
                lambda row: 'Low' if row['Current Stock'] < row['Minimum Stock'] else 'Normal', 
                axis=1
            )
            
            # Status-based color
            def highlight_status(val):
                if val == 'Normal':
                    return 'background-color: #d4f7d4'
                elif val == 'Low':
                    return 'background-color: #f7d4d4'
                return ''
            
            # Styled dataframe display
            st.dataframe(parts_stock_df.style.applymap(highlight_status, subset=['Stock Status']), use_container_width=True)
            
            # Stock value calculation
            total_stock_value = parts_stock_df['Stock Value (₩)'].sum()
            st.metric("Total Parts Stock Value", f"₩{total_stock_value:,.0f}")
            
            # Parts inventory chart
            st.subheader("Parts Inventory Level")
            
            # Low stock parts filter
            low_stock_parts = parts_stock_df[parts_stock_df['Stock Status'] == 'Low']
            
            fig = go.Figure()
            
            fig.add_trace(go.Bar(
                x=parts_stock_df['Part Name'],
                y=parts_stock_df['Current Stock'],
                name='Current Stock',
                marker_color='#1f77b4'
            ))
            
            fig.add_trace(go.Scatter(
                x=parts_stock_df['Part Name'],
                y=parts_stock_df['Minimum Stock'],
                name='Minimum Stock',
                mode='lines+markers',
                marker_color='red'
            ))
            
            fig.update_layout(
                title='Parts Inventory Level',
                xaxis_title='Part Name',
                yaxis_title='Quantity'
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Low stock parts display
            if not low_stock_parts.empty:
                st.subheader("Low Stock Parts")
                st.dataframe(low_stock_parts[['Part Code', 'Part Name', 'Current Stock', 'Minimum Stock', 'Stock Status']], use_container_width=True)
                
                # Order recommendation for low stock parts
                st.warning(f"{len(low_stock_parts)} parts stock is low. Please review orders.")
                
                if st.button("Go to Order Page"):
                    st.session_state.menu = "Parts Order"
                    st.experimental_rerun()
            else:
                st.success("All parts stock is sufficient.")
        else:
            st.info("No parts registered.")
    
    with tab2:
        st.subheader("Products Inventory Status")
        
        # Products inventory data query
        cursor = conn.cursor()
        cursor.execute("""
        SELECT id, product_code, product_name, brand, stock, selling_price, (stock * selling_price) as stock_value
        FROM products
        ORDER BY stock ASC
        """)
        products_stock_data = cursor.fetchall()
        
        if products_stock_data:
            products_stock_df = pd.DataFrame(products_stock_data, 
                                          columns=['ID', 'Product Code', 'Product Name', 'Brand', 'Current Stock', 'Selling Price (₩)', 'Stock Value (₩)'])
            
            # Stock value calculation
            total_product_value = products_stock_df['Stock Value (₩)'].sum()
            
            # Table display
            st.dataframe(products_stock_df, use_container_width=True)
            
            # Total stock value display
            st.metric("Total Products Stock Value", f"₩{total_product_value:,.0f}")
            
            # Products inventory chart
            st.subheader("Products Inventory Level")
            
            fig = px.bar(products_stock_df, 
                       x='Product Name', y='Current Stock',
                       title='Products Inventory Level',
                       color='Current Stock',
                       labels={'Product Name': 'Product Name', 'Current Stock': 'Stock Quantity'})
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Products stock value pie chart
            st.subheader("Products Stock Value Share")
            
            fig = px.pie(products_stock_df, values='Stock Value (₩)', names='Product Name',
                       title='Products Stock Value Share',
                       hover_data=['Current Stock'],
                       labels={'Stock Value (₩)': 'Stock Value'})
            fig.update_traces(textposition='inside', textinfo='percent+label')
            
            st.plotly_chart(fig, use_container_width=True)
            
            # No stock products filter
            no_stock_products = products_stock_df[products_stock_df['Current Stock'] == 0]
            
            if not no_stock_products.empty:
                st.subheader("No Stock Products")
                st.dataframe(no_stock_products[['Product Code', 'Product Name', 'Current Stock']], use_container_width=True)
                
                st.warning(f"{len(no_stock_products)} products stock is empty. Please review production plan.")
                
                if st.button("Go to Production Page"):
                    st.session_state.menu = "Production Management"
                    st.experimental_rerun()
        else:
            st.info("No products registered.")

# Settings Page
def display_settings(conn):
    st.title("System Settings")
    
    st.subheader("Company Information")
    
    with st.form("company_info_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            company_name = st.text_input("Company Name", value="YUER-Korea Skylights")
            jv_name = st.text_input("Joint Venture Name", value="YUER Korea Skylights")
            foundation_date = st.date_input("Foundation Date", value=datetime.now().date())
        
        with col2:
            company_address = st.text_input("Company Address", value="123 Teheran-ro, Gangnam-gu, Seoul")
            company_phone = st.text_input("Company Phone", value="02-1234-5678")
            company_email = st.text_input("Company Email", value="info@yuer-korea.com")
        
        submitted = st.form_submit_button("Save")
        
        if submitted:
            st.success("Company information saved successfully.")
    
    st.markdown("---")
    
    st.subheader("Database Management")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Initialize Sample Data", help="Delete current data and create sample data again."):
            # Delete all table data
            cursor = conn.cursor()
            tables = ['sales', 'production', 'bill_of_materials', 'products', 'order_details', 'orders', 'parts']
            
            for table in tables:
                cursor.execute(f"DELETE FROM {table}")
            
            conn.commit()
            
            # Create sample data
            create_sample_data(conn)
            
            st.success("Sample data initialized successfully.")
    
    with col2:
        if st.button("Delete All Data", help="Delete all data from the system. This operation cannot be undone."):
            # Confirmation dialog
            if st.checkbox("Are you sure you want to delete all data? This operation cannot be undone."):
                # Delete all table data
                cursor = conn.cursor()
                tables = ['sales', 'production', 'bill_of_materials', 'products', 'order_details', 'orders', 'parts']
                
                for table in tables:
                    cursor.execute(f"DELETE FROM {table}")
                
                conn.commit()
                
                st.success("All data deleted successfully.")
    
    st.markdown("---")
    
    st.subheader("System Information")
    
    # Simple system information display
    col1, col2 = st.columns(2)
    
    with col1:
        st.info("""**System Information**
- Application: YUER-Korea Joint Venture Management System
- Version: 1.0.0
- Developer: Claude AI
- Technology: Python, Streamlit, MySQL""")
    
    with col2:
        # Current DB statistics
        cursor = conn.cursor()
        
        # Table record count query
        cursor.execute("SELECT COUNT(*) FROM parts")
        parts_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM products")
        products_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM orders")
        orders_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM production")
        production_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM sales")
        sales_count = cursor.fetchone()[0]
        
        st.info("**Database Statistics**\n"
               f"- Parts: {parts_count} units\n"
               f"- Products: {products_count} units\n"
               f"- Orders: {orders_count} units\n"
               f"- Production Plans: {production_count} units\n"
               f"- Sales Records: {sales_count} units"
        )

def display_products_management(conn):
    """Products management page"""
    st.title("Products Management")
    
    tab1, tab2 = st.tabs(["Products List", "Products Add/Edit"])
    
    with tab1:
        st.subheader("Products List")
        
        # Products data query
        cursor = conn.cursor()
        cursor.execute("""
        SELECT id, product_code, product_name, product_type, size, brand, 
               selling_price, production_cost, stock
        FROM products
        ORDER BY product_code
        """)
        products_data = cursor.fetchall()
        
        if products_data:
            products_df = pd.DataFrame(products_data, 
                                    columns=['ID', 'Product Code', 'Product Name', 'Product Type', 'Size', 'Brand', 
                                            'Selling Price (₩)', 'Production Cost (₩)', 'Stock'])
            
            # Dataframe display
            st.dataframe(products_df, use_container_width=True)
            
            # Products stock chart
            st.subheader("Products Stock Status")
            
            fig = go.Figure()
            
            fig.add_trace(go.Bar(
                x=products_df['Product Name'],
                y=products_df['Stock'],
                name='Current Stock',
                marker_color='#1f77b4'
            ))
            
            fig.update_layout(
                title='Products Stock Level',
                xaxis_title='Product Name',
                yaxis_title='Stock Quantity'
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Products profitability analysis
            st.subheader("Products Profitability Analysis")
            
            # Margin calculation
            products_df['Margin (₩)'] = products_df['Selling Price (₩)'] - products_df['Production Cost (₩)']
            products_df['Margin %'] = (products_df['Margin (₩)'] / products_df['Selling Price (₩)'] * 100).round(1)
            
            # Profitability chart
            fig = px.bar(products_df, 
                       x='Product Name', y='Margin (₩)',
                       title='Products Margin',
                       color='Margin %',
                       labels={'Product Name': 'Product Name', 'Margin (₩)': 'Margin (₩)'})
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Detailed profitability table
            st.dataframe(products_df[['Product Name', 'Selling Price (₩)', 'Production Cost (₩)', 'Margin (₩)', 'Margin %']], 
                        use_container_width=True)
        else:
            st.info("No products registered.")
    
    with tab2:
        st.subheader("Products Add/Edit")
        
        # Products add form
        with st.form("product_form"):
            st.write("New Product Registration")
            product_code = st.text_input("Product Code")
            product_name = st.text_input("Product Name")
            product_type = st.selectbox("Product Type", ["Fixed", "Fixed", "Automatic"])
            size = st.text_input("Size")
            brand = st.text_input("Brand", value="YUER")
            selling_price = st.number_input("Selling Price (₩)", min_value=0.0, step=0.1)
            production_cost = st.number_input("Production Cost (₩)", min_value=0.0, step=0.1)
            stock = st.number_input("Initial Stock", min_value=0, step=1)
            
            submitted = st.form_submit_button("Product Add")
            
            if submitted:
                if not product_code or not product_name:
                    st.error("Product code and name are required.")
                else:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO products (product_code, product_name, product_type, size, brand, selling_price, production_cost, stock) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (product_code, product_name, product_type, size, brand, selling_price, production_cost, stock)
                    )
                    conn.commit()
                    st.success(f"Product '{product_name}' added successfully!")
        
        # Products edit section
        st.markdown("---")
        st.write("Product Information Edit")
        
        # Products list query
        cursor = conn.cursor()
        cursor.execute("SELECT id, product_code, product_name FROM products ORDER BY product_code")
        products = cursor.fetchall()
        
        if products:
            product_options = {f"{p[1]} - {p[2]}": p[0] for p in products}
            selected_product = st.selectbox("Select Product to Edit", list(product_options.keys()))
            
            product_id = product_options[selected_product]
            
            # Fetch selected product info
            cursor.execute(
                "SELECT product_code, product_name, product_type, size, brand, selling_price, production_cost, stock FROM products WHERE id = %s",
                (product_id,)
            )
            product_data = cursor.fetchone()
            
            if product_data:
                with st.form("edit_product_form"):
                    st.write(f"Edit '{product_data[1]}' Information")
                    
                    edit_product_code = st.text_input("Product Code", value=product_data[0])
                    edit_product_name = st.text_input("Product Name", value=product_data[1])
                    edit_product_type = st.selectbox("Product Type", ["Fixed", "Fixed", "Automatic"], 
                                                  index=["Fixed", "Fixed", "Automatic"].index(product_data[2]))
                    edit_size = st.text_input("Size", value=product_data[3])
                    edit_brand = st.text_input("Brand", value=product_data[4])
                    edit_selling_price = st.number_input("Selling Price (₩)", min_value=0.0, step=0.1, value=float(product_data[5]))
                    edit_production_cost = st.number_input("Production Cost (₩)", min_value=0.0, step=0.1, value=float(product_data[6]))
                    edit_stock = st.number_input("Stock", min_value=0, step=1, value=int(product_data[7]))
                    
                    update_submitted = st.form_submit_button("Information Update")
                    
                    if update_submitted:
                        cursor.execute(
                            "UPDATE products SET product_code = %s, product_name = %s, product_type = %s, size = %s, brand = %s, selling_price = %s, production_cost = %s, stock = %s WHERE id = %s",
                            (edit_product_code, edit_product_name, edit_product_type, edit_size, edit_brand, 
                             edit_selling_price, edit_production_cost, edit_stock, product_id)
                        )
                        conn.commit()
                        st.success(f"Product '{edit_product_name}' information updated successfully!")
        else:
            st.info("No products registered. Please register products first.")

if __name__ == "__main__":
    main() 