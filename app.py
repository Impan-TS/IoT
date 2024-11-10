from flask import Flask, jsonify, request, render_template
from flask_socketio import SocketIO
from opcua import Client
import threading
import time
import plotly
import json
import pyodbc
from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash, make_response
from datetime import datetime, timedelta
from werkzeug.utils import redirect
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, ValidationError
import bcrypt

app = Flask(__name__)
app.secret_key = 'xyzsdfg'
socketio = SocketIO(app)

# Database configuration
DB_SERVER = 'DESKTOP-BSC7DMC\SQLEXPRESS'
DB_DATABASE = 'tse_data'
DB_USER = 'sa'
DB_PASSWORD = 'tiger'

# Connection string
connection_string = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={DB_SERVER};DATABASE={DB_DATABASE};UID={DB_USER};PWD={DB_PASSWORD}'


# # Function to create a connection
# def create_connection():
#     return pyodbc.connect(connection_string)

# Function to create a connection
def create_connection():
    while True:
        try:
            conn = pyodbc.connect(connection_string)
            return conn
        except pyodbc.Error as e:
            print(f"Error connecting to database: {e}")
            # Handle specific error cases if needed, or retry
            # Example: Handle specific error codes or types of errors
            # Check documentation for pyodbc for specific error handling

        except Exception as e:
            print(f"Unexpected error during connection: {e}")
            return None  # Handle other exceptions as needed

# Connect to the database
def connect_to_db():
    # conn_str = 'ODBC Driver 17 for SQL Server={SQL Server};SERVER=' + DESKTOP-BSC7DMCSQLEXPRESS + ';DATABASE=' + tse_data + ';UID=' + sa + ';PWD=' + tiger
    # conn_str = 'DRIVER={SQL Server};SERVER=' + DB_SERVER + ';DATABASE=' + DB_DATABASE + ';UID=' + DB_USER + ';PWD=' + DB_PASSWORD
    conn_str = 'DRIVER={SQL Server};SERVER=' + DB_SERVER + ';DATABASE=' + DB_DATABASE + ';UID=' + DB_USER + ';PWD=' + DB_PASSWORD
    return pyodbc.connect(conn_str)

# OPC UA server URL
OPC_UA_URL = "opc.tcp://DESKTOP-BSC7DMC:53530/OPCUA/SimulationServer"

# Create an OPC UA client instance
client = Client(OPC_UA_URL)

# Global variable to hold the latest values
latest_values = {}

def read_values_periodically():
    global latest_values
    while True:
        try:
            client.connect()  # Connect to the OPC UA server
            
            # Define Node IDs here
            node_ids = {
                "Counter": "ns=3;i=1008",
                "Random": "ns=3;i=1003",
                "Sawtooth": "ns=3;i=1004",
                "Sinusoid": "ns=3;i=1005",
                "Square": "ns=3;i=1006",
                "Triangle": "ns=3;i=1007"
            }
            
            for name, node_id in node_ids.items():
                node = client.get_node(node_id)
                latest_values[name] = node.get_value()  # Read the value
            
            # Emit the latest values to all connected clients
            socketio.emit('update', latest_values)
            
            socketio.emit('gauge_update', {
                "Random": latest_values.get("Random", 0),
                "Counter": latest_values.get("Counter", 0),
                "Sawtooth": latest_values.get("Sawtooth", 0)
            })
            
            client.disconnect()  # Disconnect from the server
            time.sleep(1)  # Wait for 1 second before the next read
        except Exception as e:
            print(f"Error reading values: {str(e)}")
            time.sleep(1)  # Wait before retrying in case of error
            

@app.route('/write', methods=['POST'])
def write_value():
    try:
        data = request.json
        node_id = data.get('node_id')
        value = float(data.get('value'))  # Ensure the value is treated as a float

        client.connect()  # Connect to the OPC UA server
        node = client.get_node(node_id)
        node.set_value(value)  # Write the value

        return jsonify({"status": "success", "node_id": node_id, "new_value": value})
    except Exception as e:
        return jsonify({"error": str(e)})
    finally:
        client.disconnect()  # Disconnect from the server
        
        
@app.route('/', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = create_connection()
        cursor = conn.cursor()

        # Authenticate user (user role)
        cursor.execute("""
            SELECT * FROM users 
            WHERE username COLLATE SQL_Latin1_General_CP1_CS_AS = ? 
            AND password COLLATE SQL_Latin1_General_CP1_CS_AS = ?""", 
            (username, password))
        user = cursor.fetchone()

        if user:
            session['userloggedin'] = True
            session['username'] = username
            session['role'] = 'user'  # Set the user's role in session
            return redirect(url_for('dashboard', user_type='user'))

        # Authenticate admin (admin role)
        cursor.execute("""
            SELECT * FROM admins 
            WHERE username COLLATE SQL_Latin1_General_CP1_CS_AS = ? 
            AND password COLLATE SQL_Latin1_General_CP1_CS_AS = ?""", 
            (username, password))
        admin = cursor.fetchone()

        if admin:
            session['userloggedin'] = True
            session['username'] = username
            session['role'] = 'admin'  # Set the admin's role in session
            return redirect(url_for('dashboard', user_type='admin'))

        # Flash the error message if credentials are invalid
        flash('Invalid credentials. Please try again.', 'danger')

    return render_template('User management/userlogin.html')


@app.route('/index')
def index():
    msg = {'payload': 0}
    return render_template('iot/index.html', msg=msg)  # Render the HTML template


@app.route('/tse')
def tse():
    if 'userloggedin' not in session:
        # If not logged in, redirect to the user login page
        return redirect(url_for('user_login'))
    
    else:
        response = make_response(render_template('iot/tse.html'))
        # Add cache-control header to prevent caching
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response
    
    
@app.route('/dashboard')
def dashboard():
    if 'userloggedin' not in session:
        # If not logged in, redirect to the user login page
        return redirect(url_for('user_login'))
    
    else:
        response = make_response(render_template('iot/dashboard.html'))
        # Add cache-control header to prevent caching
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response


@app.route('/spinning2')
def spinning2():
    msg = {'payload': latest_values}  # Pass the latest values to the template
    if 'userloggedin' not in session:
        # If not logged in, redirect to the user login page
        return redirect(url_for('user_login'))
    
    else:
        return render_template('iot/spinning2.html', msg=msg, active_submodule='departmentsSubmodules')
        response = make_response(render_template('iot/spinning2.html'))
        # Add cache-control header to prevent caching
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response
    
# Route to display users
@app.route('/adduser')
def adduser():
    if 'userloggedin' not in session:
        # If not logged in, redirect to the user login page
        return redirect(url_for('user_login'))
    else:
        # If logged in, proceed to display users
        connection = create_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM users")
        data = cursor.fetchall()
        cursor.close()
        connection.close()
        # Prevent caching of the /users route
        response = make_response(render_template('User management/adduser.html', users=data))
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    
@app.route('/addadmin')
def addadmin():
    if 'userloggedin' not in session:
        # If not logged in, redirect to the user login page
        return redirect(url_for('user_login'))
    else:
        connection = create_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM admins")
        data = cursor.fetchall()
        cursor.close()
        connection.close()
        # Prevent caching of the /addadmin route
        response = make_response(render_template('User management/addadmin.html', admins=data))
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    
# Route to insert a new user
@app.route('/insert', methods=['POST'])
def insert():
    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']
        try:
            connection = create_connection()
            cursor = connection.cursor()
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            connection.commit()
            flash("Data Inserted Successfully")
        except pyodbc.IntegrityError:
            flash("Username already exists. Please choose a different username.")
        finally:
            cursor.close()
            connection.close()
        return redirect(url_for('adduser'))
    
# Route to delete a user
@app.route('/delete/<string:id_data>', methods=['GET'])
def delete(id_data):
    flash("Record Has Been Deleted Successfully")
    connection = create_connection()
    cursor = connection.cursor()
    cursor.execute("DELETE FROM users WHERE id=?", (id_data,))
    connection.commit()
    cursor.close()
    connection.close()
    return redirect(url_for('adduser'))

@app.route('/update/<int:id_data>', methods=['POST'])
def update(id_data):
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Check if the new username already exists in the database
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? AND id != ?", (username, id_data))
        existing_user = cursor.fetchone()
        cursor.close()

        if existing_user:
            flash("Username already exists. Please choose a different username.", "error")
            return redirect(url_for('adduser'))

        # Perform the update operation
        cursor = conn.cursor()
        cursor.execute("""
        UPDATE users SET username=?, password=?
        WHERE id=?
        """, (username, password, id_data))
        conn.commit()
        flash("Data Updated Successfully")
        conn.close()  # Close the connection after use
        return redirect(url_for('adduser'))
    
# Route to insert a new user
@app.route('/admininsert', methods=['POST'])
def admininsert():
    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']
        try:
            connection = create_connection()
            cursor = connection.cursor()
            cursor.execute("INSERT INTO admins (username, password) VALUES (?, ?)", (username, password))
            connection.commit()
            flash("Data Inserted Successfully")
        except pyodbc.IntegrityError:
            flash("Username already exists. Please choose a different username.")
        finally:
            cursor.close()
            connection.close()
        return redirect(url_for('addadmin'))


# Route to delete a user
@app.route('/admindelete/<string:id_data>', methods=['GET'])
def admindelete(id_data):
    flash("Record Has Been Deleted Successfully")
    connection = create_connection()
    cursor = connection.cursor()
    cursor.execute("DELETE FROM admins WHERE id=?", (id_data,))
    connection.commit()
    cursor.close()
    connection.close()
    return redirect(url_for('addadmin'))


@app.route('/adminupdate/<int:id_data>', methods=['POST'])
def adminupdate(id_data):
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Check if the new username already exists in the database
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM admins WHERE username = ? AND id != ?", (username, id_data))
        existing_user = cursor.fetchone()
        cursor.close()

        if existing_user:
            flash("Username already exists. Please choose a different username.", "error")
            return redirect(url_for('addadmin'))

        # Perform the update operation
        cursor = conn.cursor()
        cursor.execute("""
        UPDATE admins SET username=?, password=?
        WHERE id=?
        """, (username, password, id_data))
        conn.commit()
        flash("Data Updated Successfully")
        conn.close()  # Close the connection after use
        return redirect(url_for('addadmin'))

@app.route('/logout')
def logout():
    # Clear user session data
    session.pop('userloggedin', None)
    session.pop('userid', None)
    session.pop('username', None)

    response = make_response(redirect(url_for('user_login')))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


if __name__ == '__main__':
    # Start the background thread to read values periodically
    thread = threading.Thread(target=read_values_periodically)
    thread.daemon = True  # Daemonize thread
    thread.start()
    app.run(host="127.0.0.1", port=7000)
    socketio.run(app, host='127.0.0.1', port=7000, debug=True)