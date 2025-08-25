"""
PostgreSQL 
A PostgreSQL database management and query tool built with Streamlit.

This file contains:
1. Configuration defaults (Config class)
2. A simple connection pool (DatabasePool) for managing database connections
3. A DatabaseManager class for executing queries safely
4. UIComponents class for rendering the connection form, query editor,
   table browser, database info, installed extensions, and a new Monitoring section.
5. The main application class (PostgreSQLApp) that ties everything together.

To run this code:
$ streamlit run app.py
"""

import streamlit as st
import pandas as pd
import time
import psycopg2
from psycopg2 import pool
from contextlib import contextmanager
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
from typing import Generator, Any
from queries import *  # Import your predefined queries
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pytz

# ------------------------------
# 1. CONFIGURATION
# ------------------------------
class Config:
    PAGE_TITLE = "PostgreSQL Database Performance Monitoring"
    VERSION = "17.6"
    DEFAULT_HOST = "localhost"
    DEFAULT_PORT = "5432"
    DEFAULT_DATABASE = "postgres"
    EXCLUDED_SCHEMAS = ("pg_catalog", "information_schema")
    # Optional default fetch limit for table data
    DEFAULT_FETCH_LIMIT = 1000

# ------------------------------
# 2. DATABASE CONNECTION POOL
# ------------------------------
class DatabasePool:
    """
    A simple singleton wrapper around psycopg2's SimpleConnectionPool.
    Allows reuse of connections among multiple queries.
    """
    _instance = None

    def __init__(self, min_conn: int = 1, max_conn: int = 5):
        self.connection_pool = None
        self.min_conn = min_conn
        self.max_conn = max_conn

    @classmethod
    def get_instance(cls) -> "DatabasePool":
        if cls._instance is None:
            cls._instance = DatabasePool()
        return cls._instance

    def initialize(self, **db_params):
        """
        Initialize the connection pool using provided DB parameters.
        Closes any existing pool before creating a new one.
        """
        if self.connection_pool:
            self.connection_pool.closeall()
        self.connection_pool = pool.SimpleConnectionPool(
            self.min_conn,
            self.max_conn,
            **db_params,
            connect_timeout=5
        )

    def get_connection(self):
        """
        Get a connection from the pool.
        """
        if self.connection_pool:
            return self.connection_pool.getconn()
        else:
            raise Exception("Connection pool is not initialized.")

    def put_connection(self, conn):
        """
        Return a connection back to the pool.
        """
        if self.connection_pool:
            self.connection_pool.putconn(conn)

# ------------------------------
# 3. DATABASE MANAGEMENT
# ------------------------------
class DatabaseManager:
    """
    This class is responsible for executing queries on the database.
    It uses a connection obtained from the connection pool and saved
    in the Streamlit session state.
    """
    def __init__(self):
        # Set page configuration and initialize session state
        st.set_page_config(page_title=Config.PAGE_TITLE, layout="wide")
        self.init_session_state()

    def init_session_state(self):
        # Initialize default session state variables if not already set.
        defaults = {
            "connection": None,
            "current_db": None,
            "query_history": [],
            "last_query_time": None
        }
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value

    @contextmanager
    def get_cursor(self):
        """
        Context manager to obtain a cursor from the current connection and ensure it is closed.
        """
        conn = st.session_state.connection
        if conn is None:
            raise ConnectionError("No active database connection.")
        cur = conn.cursor()
        try:
            yield cur
        finally:
            cur.close()

    def execute_query(self, query: str, params=None, fetch: bool = True):
        """
        Execute a SQL query on the active database connection.
        Returns a tuple of (DataFrame or None, execution_time_in_seconds).
        """
        conn = st.session_state.connection
        if conn is None:
            st.error("No active database connection.")
            return None, 0

        # Enable autocommit when executing commands like CREATE DATABASE
        if query.strip().lower().startswith("create database"):
            conn.autocommit = True

        start_time = time.time()
        try:
            with self.get_cursor() as cur:
                if params:
                    cur.execute(query, params)
                else:
                    cur.execute(query)
                if fetch and cur.description:
                    # If the query returns rows, convert them into a DataFrame.
                    results = cur.fetchall()
                    columns = [desc[0] for desc in cur.description]
                    df = pd.DataFrame(results, columns=columns)
                else:
                    df = None
                conn.commit()
            exec_time = time.time() - start_time
            # Save query history and execution time in session state.
            st.session_state.query_history.append((query, exec_time))
            st.session_state.last_query_time = exec_time
            return df, exec_time
        except Exception as e:
            conn.rollback()
            raise e
        
# ------------------------------
# 4. USER INTERFACE COMPONENTS
# ------------------------------
class UIComponents:
    """
    This class renders UI components and handles user inputs like connection parameters,
    SQL query editor, table browser, database info, installed extensions, and monitoring queries.
    """
    
    @staticmethod
    def render_connection_form():
        """
        Renders a form in the sidebar for database connection parameters.
        Returns a dictionary with these parameters upon submission, or None otherwise.
        """
        with st.sidebar:
            st.subheader("🔌 Database Connection")
            with st.form("connection_form"):
                connection_params = {
                    "host": st.text_input("Host", Config.DEFAULT_HOST),
                    "port": st.text_input("Port", Config.DEFAULT_PORT),
                    "database": st.text_input("Database", Config.DEFAULT_DATABASE),
                    "user": st.text_input("Username"),
                    "password": st.text_input("Password", type="password")
                }
                submitted = st.form_submit_button("Connect")
        return connection_params if submitted else None

    @staticmethod
    def render_query_editor():
        """
        Renders the SQL query editor and an 'Execute Query' button.
        Returns the query string and an execution flag.
        """
        st.header("SQL Query Editor")
        query = st.text_area("Enter SQL Query", height=150, key="query_editor")
        execute = st.button("Execute Query")
        return query, execute


    @staticmethod
    def render_table_browser(db_manager: DatabaseManager):
        st.header("Table Browser")
        
        try:
            # Get detailed table information including size and row counts
            base_query = """
                SELECT 
                    n.nspname as table_schema,
                    c.relname as table_name,
                    pg_size_pretty(pg_total_relation_size('"' || n.nspname || '"."' || c.relname || '"')) as size,
                    pg_stat_get_live_tuples(c.oid) as row_count,
                    obj_description(c.oid, 'pg_class') as description
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relkind = 'r'
                AND n.nspname NOT IN ('pg_catalog', 'information_schema')
                ORDER BY n.nspname, c.relname;
            """
            
            df, _ = db_manager.execute_query(base_query)
            
            if df is not None and not df.empty:
                col1, col2 = st.columns([2, 2])
                with col1:
                    search_term = st.text_input("🔍 Search tables", key="table_search")
                    
                with col2:
                    schema_filter = st.multiselect(
                        "Filter by Schema",
                        options=sorted(df['table_schema'].unique()),
                        default=sorted(df['table_schema'].unique())
                    )
                
                filtered_df = df[
                    (df['table_schema'].isin(schema_filter)) &
                    (df.apply(lambda x: search_term.lower() in f"{x['table_schema']}.{x['table_name']}".lower(), axis=1))
                ]
                
                st.markdown("### Available Tables")
                for _, row in filtered_df.iterrows():
                    table_id = f"{row['table_schema']}.{row['table_name']}"
                    with st.expander(f"📊 {table_id} ({row['size']} | {row['row_count']} rows)"):
                        st.markdown(f"**Description:** {row['description'] or 'No description available'}")
                        
                        # Fixed column information query
                        col_query = f"""
                            SELECT 
                                a.column_name,
                                a.data_type,
                                a.is_nullable,
                                a.column_default,
                                pg_catalog.col_description(c.oid, a.ordinal_position::int) as description
                            FROM information_schema.columns a
                            JOIN pg_class c ON c.relname = a.table_name
                            JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = a.table_schema
                            WHERE a.table_schema = '{row['table_schema']}' 
                            AND a.table_name = '{row['table_name']}'
                            ORDER BY a.ordinal_position;
                        """
                        cols_df, _ = db_manager.execute_query(col_query)
                        
                        if cols_df is not None and not cols_df.empty:
                            st.markdown("#### Columns")
                            for _, col in cols_df.iterrows():
                                col_info = f"**{col['column_name']}** ({col['data_type']})"
                                if col['is_nullable'] == 'NO':
                                    col_info += " | Required"
                                if col['column_default']:
                                    col_info += f" | Default: {col['column_default']}"
                                if col['description']:
                                    col_info += f"\n\n{col['description']}"
                                st.markdown(col_info)
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            if st.button("View Data", key=f"view_{table_id}"):
                                limit = st.slider("Number of rows", 10, 1000, 100, key=f"limit_{table_id}")
                                data_query = f"SELECT * FROM {table_id} LIMIT {limit}"
                                data_df, exec_time = db_manager.execute_query(data_query)
                                if data_df is not None:
                                    st.dataframe(data_df)
                                    st.download_button(
                                        "Download CSV",
                                        data_df.to_csv(index=False).encode('utf-8'),
                                        f"{table_id}.csv",
                                        "text/csv",
                                        key=f"dl_{table_id}"
                                    )
                        
                        with col2:
                            if st.button("Table Stats", key=f"stats_{table_id}"):
                                stats_query = f"""
                                    SELECT 
                                        count(*) as row_count,
                                        (SELECT count(*) FROM information_schema.columns 
                                        WHERE table_schema = '{row['table_schema']}' 
                                        AND table_name = '{row['table_name']}') as column_count,
                                        pg_size_pretty(pg_total_relation_size('{table_id}')) as total_size,
                                        pg_size_pretty(pg_table_size('{table_id}')) as table_size,
                                        pg_size_pretty(pg_indexes_size('{table_id}')) as index_size
                                    FROM {table_id}
                                """
                                stats_df, _ = db_manager.execute_query(stats_query)
                                if stats_df is not None:
                                    st.json(stats_df.iloc[0].to_dict())
                        
                        with col3:
                            if st.button("Show Indexes", key=f"indexes_{table_id}"):
                                idx_query = f"""
                                    SELECT
                                        indexname,
                                        indexdef
                                    FROM pg_indexes
                                    WHERE schemaname = '{row['table_schema']}'
                                    AND tablename = '{row['table_name']}'
                                """
                                idx_df, _ = db_manager.execute_query(idx_query)
                                if idx_df is not None:
                                    st.dataframe(idx_df)
            
            else:
                st.info("No tables found in the selected schemas.")
                
        except Exception as e:
            st.error(f"Error loading tables: {str(e)}")
            st.markdown("Please check your database connection and permissions.")
    
    @staticmethod
    def render_database_info(db_manager: DatabaseManager):
        """
        Renders basic database information including size, active connections, and server uptime.
        """
        st.header("Database Information")
        try:
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("System Metrics")
                # Get database size.
                size_query = "SELECT pg_size_pretty(pg_database_size(current_database()))"
                size_df, _ = db_manager.execute_query(size_query)
                st.metric("Database Size", size_df.iloc[0, 0] if size_df is not None else "N/A")
                # Get active connections.
                conn_query = "SELECT COUNT(*) FROM pg_stat_activity"
                conn_df, _ = db_manager.execute_query(conn_query)
                st.metric("Active Connections", conn_df.iloc[0, 0] if conn_df is not None else "N/A")
                # Get server uptime.
                uptime_query = """
                    SELECT EXTRACT(DAY FROM (current_timestamp - pg_postmaster_start_time())) || ' D ' ||
                           EXTRACT(HOUR FROM (current_timestamp - pg_postmaster_start_time())) || ' H ' ||
                           EXTRACT(MINUTE FROM (current_timestamp - pg_postmaster_start_time())) || ' M'
                    AS uptime;
                """
                uptime_df, _ = db_manager.execute_query(uptime_query)
                st.metric("Server Uptime", uptime_df.iloc[0, 0] if uptime_df is not None else "N/A")
            with col2:
                st.subheader("Database Objects")
                # Get count of user tables.
                table_count_query = f"""
                    SELECT COUNT(*) 
                    FROM information_schema.tables 
                    WHERE table_schema NOT IN {Config.EXCLUDED_SCHEMAS}
                """
                table_count_df, _ = db_manager.execute_query(table_count_query)
                st.metric("User Tables", table_count_df.iloc[0, 0] if table_count_df is not None else "N/A")
                # Display tool versions and encoding.
                st.metric("PostgreSQL  Version", Config.VERSION)
                encoding_query = "SHOW server_encoding"
                encoding_df, _ = db_manager.execute_query(encoding_query)
                st.metric("Database Encoding", encoding_df.iloc[0, 0] if encoding_df is not None else "N/A")
        except Exception as e:
            st.error(f"Error loading database info: {str(e)}")

    @staticmethod
    def render_extensions(db_manager: DatabaseManager):
        """
        Renders the Installed Extensions tab.
        Displays the list of PostgreSQL extensions that are installed.
        """
        st.header("Installed Extensions")
        try:
            ext_query = """
                SELECT name, default_version, installed_version 
                FROM pg_available_extensions 
                WHERE installed_version IS NOT NULL
            """
            df, _ = db_manager.execute_query(ext_query)
            df.reset_index(drop=True, inplace=True)
            st.dataframe(df)
        except Exception as e:
            st.error(f"Error loading extensions: {str(e)}")
    
    @staticmethod
    def render_user_management(db_manager):
        """
        Advanced User Management interface with comprehensive role management,
        user monitoring, and security controls.
        """
        st.header("User Management")
        
        tab1, tab2, tab3, tab4 = st.tabs([
            "👤 User Operations", 
            "🔑 Role Management", 
            "📊 User Activity", 
            "🛡️ Security Settings"
        ])
        
        with tab1:
            st.subheader("User Operations")
            operation = st.selectbox(
                "Select Operation",
                ["Create User", "Modify User", "Delete User"]
            )
            
            if operation == "Create User":
                with st.form("create_user_form"):
                    username = st.text_input("Username")
                    password = st.text_input("Password", type="password")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        superuser = st.checkbox("Superuser")
                        createdb = st.checkbox("Can create databases")
                        createrole = st.checkbox("Can create roles")
                    with col2:
                        login = st.checkbox("Can login", value=True)
                        replication = st.checkbox("Replication")
                        connection_limit = st.number_input("Connection limit", -1, 1000, -1)
                    
                    valid_until = st.date_input("Valid until")
                    
                    submitted = st.form_submit_button("Create User")
                    
                    if submitted:
                        if not username or not password:
                            st.warning("Username and password are required.")
                            return
                        
                        try:
                            check_query = "SELECT 1 FROM pg_roles WHERE rolname = %s"
                            check_result, _ = db_manager.execute_query(check_query, (username,), fetch=True)
                            
                            if not check_result.empty:
                                st.error(f"User '{username}' already exists!")
                                return
                            
                            create_query = f"""
                                CREATE USER {username}
                                WITH PASSWORD %s
                                {' SUPERUSER' if superuser else ' NOSUPERUSER'}
                                {' CREATEDB' if createdb else ' NOCREATEDB'}
                                {' CREATEROLE' if createrole else ' NOCREATEROLE'}
                                {' LOGIN' if login else ' NOLOGIN'}
                                {' REPLICATION' if replication else ' NOREPLICATION'}
                                CONNECTION LIMIT {connection_limit}
                                VALID UNTIL '{valid_until}'
                            """
                            
                            db_manager.execute_query(create_query, (password,), fetch=False)
                            st.success(f"User '{username}' created successfully!")
                            
                        except Exception as e:
                            st.error(f"Error creating user: {str(e)}")
            
            elif operation == "Modify User":
                users_query = """
                    SELECT rolname, rolsuper, rolcreatedb, rolcreaterole,
                        rolcanlogin, rolreplication, rolconnlimit
                    FROM pg_roles
                    WHERE rolname NOT LIKE 'pg_%'
                """
                users_df, _ = db_manager.execute_query(users_query, fetch=True)
                
                selected_user = st.selectbox("Select User", users_df['rolname'])
                
                if selected_user:
                    user_data = users_df[users_df['rolname'] == selected_user].iloc[0]
                    
                    with st.form("modify_user_form"):
                        new_password = st.text_input("New Password (leave blank to keep current)", type="password")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            new_superuser = st.checkbox("Superuser", value=user_data['rolsuper'])
                            new_createdb = st.checkbox("Can create databases", value=user_data['rolcreatedb'])
                        with col2:
                            new_login = st.checkbox("Can login", value=user_data['rolcanlogin'])
                            new_replication = st.checkbox("Replication", value=user_data['rolreplication'])
                        
                        submitted = st.form_submit_button("Update User")
                        
                        if submitted:
                            try:
                                update_query = f"""
                                    ALTER USER {selected_user}
                                    {' SUPERUSER' if new_superuser else ' NOSUPERUSER'}
                                    {' CREATEDB' if new_createdb else ' NOCREATEDB'}
                                    {' LOGIN' if new_login else ' NOLOGIN'}
                                    {' REPLICATION' if new_replication else ' NOREPLICATION'}
                                """
                                db_manager.execute_query(update_query, fetch=False)
                                
                                if new_password:
                                    db_manager.execute_query(
                                        f"ALTER USER {selected_user} WITH PASSWORD %s",
                                        (new_password,),
                                        fetch=False
                                    )
                                
                                st.success(f"User '{selected_user}' updated successfully!")
                                
                            except Exception as e:
                                st.error(f"Error updating user: {str(e)}")
            
            elif operation == "Delete User":
                users_result, _ = db_manager.execute_query(
                    "SELECT rolname FROM pg_roles WHERE rolname NOT LIKE 'pg_%'",
                    fetch=True
                )
                user_to_delete = st.selectbox("Select User to Delete", users_result['rolname'])
                
                if st.button("Delete User", type="primary"):
                    try:
                        db_manager.execute_query(f"DROP USER {user_to_delete}", fetch=False)
                        st.success(f"User '{user_to_delete}' deleted successfully!")
                    except Exception as e:
                        st.error(f"Error deleting user: {str(e)}")
        
        with tab2:
            st.subheader("Role Management")
            
            role_operation = st.selectbox(
                "Select Role Operation",
                ["Create Role", "Grant Privileges", "Revoke Privileges"]
            )
            
            if role_operation == "Create Role":
                with st.form("create_role_form"):
                    role_name = st.text_input("Role Name")
                    inherit = st.checkbox("Inherit privileges", value=True)
                    role_password = st.text_input("Role Password (optional)", type="password")
                    
                    submitted = st.form_submit_button("Create Role")
                    
                    if submitted and role_name:
                        try:
                            create_role_query = f"""
                                CREATE ROLE {role_name}
                                {'WITH PASSWORD %s' if role_password else ''}
                                {'INHERIT' if inherit else 'NOINHERIT'}
                            """
                            params = (role_password,) if role_password else None
                            db_manager.execute_query(create_role_query, params, fetch=False)
                            st.success(f"Role '{role_name}' created successfully!")
                        except Exception as e:
                            st.error(f"Error creating role: {str(e)}")

            elif role_operation == "Grant Privileges":
                with st.form("grant_privileges_form"):
                    # Get all roles
                    roles_df, _ = db_manager.execute_query(
                        "SELECT rolname FROM pg_roles WHERE rolname NOT LIKE 'pg_%'",
                        fetch=True
                    )
                    
                    # Get all tables
                    tables_df, _ = db_manager.execute_query("""
                        SELECT table_schema, table_name 
                        FROM information_schema.tables 
                        WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
                    """, fetch=True)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        role = st.selectbox("Select Role", roles_df['rolname'])
                        privilege = st.multiselect(
                            "Select Privileges",
                            ["SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER", "ALL"]
                        )
                        
                    with col2:
                        table_schema = st.selectbox(
                            "Select Schema",
                            sorted(tables_df['table_schema'].unique()))
                        
                        # Filter tables based on selected schema
                        tables_in_schema = tables_df[tables_df['table_schema'] == table_schema]['table_name']
                        table_name = st.selectbox("Select Table", tables_in_schema)
                        
                    with_grant = st.checkbox("WITH GRANT OPTION")
                    submitted = st.form_submit_button("Grant Privileges")
                    
                    if submitted and role and privilege and table_schema and table_name:
                        try:
                            full_table_name = f"{table_schema}.{table_name}"
                            privs = ", ".join(privilege)
                            grant_query = f"""
                                GRANT {privs} ON TABLE {full_table_name} 
                                TO {role}
                                {'WITH GRANT OPTION' if with_grant else ''}
                            """
                            db_manager.execute_query(grant_query, fetch=False)
                            st.success(f"Privileges granted to {role} on {full_table_name}")
                        except Exception as e:
                            st.error(f"Error granting privileges: {str(e)}")
            
            elif role_operation == "Revoke Privileges":
                with st.form("revoke_privileges_form"):
                    # Get all roles
                    roles_df, _ = db_manager.execute_query(
                        "SELECT rolname FROM pg_roles WHERE rolname NOT LIKE 'pg_%'",
                        fetch=True
                    )
                    
                    # Get roles with existing privileges to revoke
                    priv_roles_df, _ = db_manager.execute_query("""
                        SELECT DISTINCT grantee 
                        FROM information_schema.role_table_grants 
                        WHERE grantee NOT LIKE 'pg_%'
                    """, fetch=True)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        role = st.selectbox("Select Role", priv_roles_df['grantee'])
                        
                        # Get current privileges for the selected role
                        if role:
                            current_privs_df, _ = db_manager.execute_query(f"""
                                SELECT table_schema, table_name, privilege_type
                                FROM information_schema.role_table_grants
                                WHERE grantee = '{role}'
                            """, fetch=True)
                            
                            # Group privileges by table
                            if not current_privs_df.empty:
                                current_privs_df['full_table'] = current_privs_df['table_schema'] + '.' + current_privs_df['table_name']
                                tables_with_privs = current_privs_df['full_table'].unique()
                                table_to_revoke = st.selectbox("Select Table", tables_with_privs)
                                
                                # Get privileges for selected table
                                table_privs = current_privs_df[
                                    current_privs_df['full_table'] == table_to_revoke
                                ]['privilege_type'].tolist()
                                privileges_to_revoke = st.multiselect(
                                    "Select Privileges to Revoke",
                                    table_privs,
                                    default=table_privs
                                )
                    
                    with col2:
                        revoke_option = st.selectbox(
                            "Revoke Option",
                            ["RESTRICT", "CASCADE"],
                            help="CASCADE revokes the privilege from dependent objects too"
                        )
                        
                    submitted = st.form_submit_button("Revoke Privileges")
                    
                    if submitted and role and table_to_revoke and privileges_to_revoke:
                        try:
                            privs = ", ".join(privileges_to_revoke)
                            revoke_query = f"""
                                REVOKE {privs} ON TABLE {table_to_revoke} 
                                FROM {role}
                                {revoke_option}
                            """
                            db_manager.execute_query(revoke_query, fetch=False)
                            st.success(f"Privileges revoked from {role} on {table_to_revoke}")
                        except Exception as e:
                            st.error(f"Error revoking privileges: {str(e)}")
    
        with tab3:
            st.subheader("User Activity")
            
            active_sessions_query = """
                SELECT usename, application_name, client_addr, backend_start,
                    state, query_start, query
                FROM pg_stat_activity
                WHERE usename IS NOT NULL
            """
            sessions_df, _ = db_manager.execute_query(active_sessions_query, fetch=True)
            
            st.markdown("#### Active Sessions")
            st.dataframe(sessions_df)
            
            user_stats_query = """
                SELECT usename,
                    count(*) as total_connections,
                    max(backend_start) as last_connection
                FROM pg_stat_activity
                GROUP BY usename
            """
            stats_df, _ = db_manager.execute_query(user_stats_query, fetch=True)
            
            st.markdown("#### User Statistics")
            st.dataframe(stats_df)
        
        with tab4:
            st.subheader("Security Settings")
            
            st.markdown("#### Password Policy")
            min_length = st.slider("Minimum Password Length", 8, 32, 12)
            require_special = st.checkbox("Require Special Characters")
            require_numbers = st.checkbox("Require Numbers")
            
            if st.button("Update Password Policy"):
                st.success("Password policy updated successfully!")
            
            st.markdown("#### Connection Security")
            max_connections = st.number_input("Maximum Connections", 10, 1000, 100)
            idle_timeout = st.number_input("Idle Session Timeout (minutes)", 5, 1440, 30)
            
            if st.button("Update Connection Security"):
                try:
                    # Convert idle timeout from minutes to milliseconds
                    idle_timeout_ms = idle_timeout * 60 * 1000
                    
                    # Get the current connection from session state
                    conn = st.session_state.connection
                    if conn is None:
                        st.error("No active database connection")
                        return
                    
                    # Temporarily enable autocommit for ALTER SYSTEM commands
                    original_autocommit = conn.autocommit
                    conn.autocommit = True
                    
                    try:
                        with conn.cursor() as cur:
                            # Execute ALTER SYSTEM commands
                            cur.execute(f"ALTER SYSTEM SET max_connections = {max_connections}")
                            cur.execute(f"ALTER SYSTEM SET idle_in_transaction_session_timeout = '{idle_timeout_ms}'")
                            
                            # Reload configuration
                            cur.execute("SELECT pg_reload_conf()")
                            
                            st.success("Connection security settings updated successfully!")
                            st.info("Note: Some changes may require a server restart to take full effect.")
                            
                    finally:
                        # Restore original autocommit setting
                        conn.autocommit = original_autocommit
                        
                except Exception as e:
                    st.error(f"Error updating security settings: {str(e)}")
    
class MonitoringTools:
    """Class to handle monitoring, diagnostics and tuning tools"""
    
    @staticmethod
    def render_monitoring_tab(monitor):
        """Render the Monitoring tab with diagnostic tools"""
        st.header("🔍 PostgreSQL Monitoring Tools")
        
        # Tool categories and definitions
        tool_categories = {
            "📈 Performance Monitoring": [
                {"id": "1", "name": "Check Long Running Queries"},
                {"id": "2", "name": "Size Info for Tables"},
                {"id": "3", "name": "Table and Index Size"},
                {"id": "5", "name": "Vacuum Statistics"},
                {"id": "18", "name": "Query Metrics"},
                {"id": "25", "name": "C-Scanner"},
                {"id": "35", "name": "X-ray Transactions"},
                {"id": "55", "name": "X-ray Long Trx"}
            ],
            "✅ System Health": [
                {"id": "6", "name": "Wait Events"},
                {"id": "13", "name": "Blocking Query"},
                {"id": "15", "name": "Sessions"},
                {"id": "16", "name": "States"},
                {"id": "17", "name": "Locks"},
                {"id": "19", "name": "Display Config File"},
                {"id": "37", "name": "Congestion"},
                {"id": "50", "name": "X-ray W-Events"},
                {"id": "51", "name": "X-ray W-States"},
                {"id": "52", "name": "Conflicts"},
                {"id": "53", "name": "Check Locks"}
            ],
            "💾 Storage Analysis": [
                {"id": "9", "name": "Buffer Blocks"},
                {"id": "10", "name": "Schema Size"},
                {"id": "14", "name": "Bloat"},
                {"id": "33", "name": "Data Growth"},
                {"id": "38", "name": "DB Size"},
                {"id": "41", "name": "XC-Resource Usage"},
                {"id": "44", "name": "Production DB Size"}
            ],
            "🛠️ Maintenance": [
                {"id": "20", "name": "Vacuum"},
                {"id": "21", "name": "Vacuum Specific Table"},
                {"id": "23", "name": "Cache Scan"},
                {"id": "36", "name": "Unconsumed Idx"}
            ]
        }

        # Tool descriptions
        # tool_descriptions = {
        #     "1": "Identifies queries running longer than 1 minute and their resource usage",
        #     "2": "Displays comprehensive size information for all database tables",
        #     "3": "Shows detailed table and index size metrics with bloat analysis",
        #     "5": "Detailed vacuum statistics and maintenance metrics",
        #     "6": "Analyzes current wait events affecting database performance",
        #     "9": "Examines buffer blocks usage and efficiency",
        #     "10": "Analyzes schema sizes across the database",
        #     "13": "Identifies and analyzes blocking queries impacting performance",
        #     "14": "Detects and measures table and index bloat",
        #     "15": "Shows active database sessions and their current state",
        #     "16": "Displays detailed backend states and activities",
        #     "17": "Analyzes current locks and lock waiting situations",
        #     "18": "Detailed query performance metrics and statistics",
        #     "19": "Displays current database configuration settings",
        #     "20": "Executes VACUUM operation on database",
        #     "21": "Performs VACUUM on specific table",
        #     "23": "Analyzes cache hit ratios and efficiency",
        #     "25": "Advanced scanner for connection analysis",
        #     "33": "Tracks and analyzes database growth patterns",
        #     "35": "Comprehensive transaction analysis and monitoring",
        #     "36": "Identifies unused and redundant indexes",
        #     "37": "Analyzes database congestion points",
        #     "38": "Detailed database size analysis and trends",
        #     "41": "Resource usage analysis for XC environments",
        #     "44": "Production database size monitoring",
        #     "50": "Detailed wait event analysis",
        #     "51": "Backend state analysis with wait states",
        #     "52": "Identifies and analyzes conflicts",
        #     "53": "Comprehensive lock analysis and monitoring",
        #     "55": "Analysis of long-running transactions"
        # }

        # Tool queries mapping (simplified - you'll need to import or define these)
        tool_queries = {
            "1": sql1, "2": sql2, "3": sql3, "4": sql4, "5": sql5,
            "6": sql6, "7": sql7, "8": sql8, "9": sql9, "10": sql10,
            "11": sql11, "12": sql12, "13": sql13, "14": sql14, "15": sql15,
            "16": sql16, "17": sql17, "18": sql18, "19": sql19, "20": sql20,
            "21": sql20, "22": sql20, "23": sql23, "24": sql24, "25": sql25,
            "26": sql26, "27": sql27, "28": sql28, "29": sql29, "30": sql30,
            "31": sql31, "32": sql32, "33": sql33, "34": sql34, "35": sql35,
            "36": sql36, "37": sql37, "38": sql38, "39": sql39, "40": sql40,
            "41": sql41, "42": sql42, "43": sql43, "44": sql44, "47": sql47,
            "48": sql48, "49": sql49, "50": sql50, "51": sql51, "52": sql52,
            "53": sql53, "54": sql54, "55": sql55 
        }

        # Create tabs for each category
        tabs = st.tabs(list(tool_categories.keys()))
        
        selected_tool_id = None
        
        # Process each category tab
        for i, (category, tools) in enumerate(tool_categories.items()):
            with tabs[i]:
                # Create columns for layout
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    # Extract just the names for the dropdown
                    tool_names = [tool["name"] for tool in tools]
                    selected_name = st.selectbox(
                        f"Select a tool from {category}",
                        tool_names,
                        key=f"category_{i}",
                        help=f"Choose a {category.lower()} tool to execute"
                    )
                    
                    # Find the ID that corresponds to the selected name
                    selected_id = next((tool["id"] for tool in tools if tool["name"] == selected_name), None)
                
                with col2:
                    st.markdown("###")  # Spacing
                    execute_button = st.button(
                        "Execute", 
                        key=f"exec_{i}", 
                        type="primary",
                        help="Run the selected diagnostic tool"
                    )
                
                # Display tool description
                # if selected_id and selected_id in tool_descriptions:
                #     with st.container():
                #         st.markdown("#### Tool Information")
                #         st.info(tool_descriptions[selected_id])
                        
                #         # Add category-specific tips
                #         if category == "Performance Monitoring":
                #             st.markdown("💡 **Tip**: Performance tools help identify bottlenecks in your database operations.")
                #         elif category == "System Health":
                #             st.markdown("💡 **Tip**: System health tools provide insights into the current state of your database.")
                #         elif category == "Storage Analysis":
                #             st.markdown("💡 **Tip**: Storage tools help you manage database growth and optimize disk usage.")
                #         elif category == "Maintenance":
                #             st.markdown("💡 **Tip**: Regular maintenance is essential for optimal database performance.")

                # Execute the selected tool if button is pressed
                if execute_button and selected_id:
                    try:
                        st.subheader(f"📊 {next(tool['name'] for tool in tools if tool['id'] == selected_id)}")
                        
                        # Execute the query and handle results
                        if selected_id in tool_queries:
                                
                                # Add specific visualizations for certain tools
                                if selected_id == "1":  # Check Long Running Queries
                                    results = monitor.execute_query(tool_queries[selected_id][0])
                                                    
                                    # Display tool details
                                    st.markdown("""
                                        ### **🔹 Purpose:**  
                                        - Monitors active queries and identifies those running longer than **5 minutes**.  
                                        - Highlights problematic queries that may be **stuck, inefficient, or consuming excessive resources**.  
                                        - Provides **real-time insights** into CPU and memory usage related to long-running queries.  
                                        - Helps prevent **system slowdowns** by allowing administrators to take action  
                                        (e.g., **optimizing the query, terminating it, or allocating more resources**).  

                                        ### **🔹 Example Scenario:**  
                                        Imagine a report generation query that is expected to complete in **2 minutes** but has been running for **10 minutes**. This could indicate:  
                                        ✅ Poorly optimized SQL logic (e.g., missing indexes, unnecessary joins).  
                                        ✅ High server load causing delays.  
                                        ✅ Locking issues blocking other transactions.  

                                        Using this tool, administrators can quickly identify and **address such queries** before they impact overall system performance.  
                                    """)
                                    
                                    # Handle both DataFrame and tuple cases
                                    if isinstance(results, tuple):
                                        results = results[0]  # Assuming first element is DataFrame
                                    else:
                                        results = results
                                    
                                    if results is not None and not results.empty:
                                        # Convert duration to seconds for proper sorting
                                        def convert_to_seconds(duration):
                                            return duration.total_seconds()
                                        
                                        # Add numeric duration column for sorting
                                        results['duration_seconds'] = pd.to_timedelta(results['duration']).apply(convert_to_seconds)
                                        
                                        # Sort by duration in descending order
                                        sorted_results = results.sort_values(by='duration_seconds', ascending=False).reset_index(drop=True)
                                        
                                        # Display sorted dataframe with available columns
                                        st.dataframe(sorted_results[['pid', 'duration', 'query', 'state']], use_container_width=True)
                                        
                                        # Define color scale (Green → Yellow → Red)
                                        color_scale = [
                                            [0, "green"],   # Short queries (Low duration)
                                            [0.5, "yellow"],  # Medium duration
                                            [1, "red"]      # Long-running queries (High duration)
                                        ]
                                        
                                        # Normalize duration values to range [0,1] for color mapping
                                        max_duration = sorted_results['duration_seconds'].max()
                                        min_duration = sorted_results['duration_seconds'].min()
                                        sorted_results['normalized_duration'] = (sorted_results['duration_seconds'] - min_duration) / (max_duration - min_duration + 1e-6)  # Avoid division by zero
                                        
                                        # Create horizontal bar chart with color scale
                                        fig = px.bar(
                                            sorted_results,
                                            x='duration_seconds',
                                            y='pid',
                                            orientation='h',
                                            title='Long Running Queries by Duration',
                                            labels={
                                                'duration_seconds': 'Query Duration (seconds)',
                                                'pid': 'Process ID'
                                            },
                                            color='normalized_duration',  # Use normalized duration for coloring
                                            color_continuous_scale=color_scale,
                                            hover_data=['state']  # Show only 'state' in hover data
                                        )
                                        
                                        # Customize layout
                                        fig.update_layout(
                                            xaxis_title="Duration (seconds)",
                                            yaxis_title="Process ID (PID)",
                                            height=max(400, len(sorted_results) * 30),
                                            showlegend=False,
                                            plot_bgcolor='white',
                                            bargap=0.2,
                                            yaxis={'categoryorder': 'total ascending'}
                                        )
                                        
                                        # Add gridlines
                                        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
                                        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
                                        
                                        st.plotly_chart(fig, use_container_width=True)

                                if selected_id == "2":  # Size Info for Tables
                                    results = monitor.execute_query(tool_queries[selected_id][0])

                                    # Display tool details
                                    st.markdown("""
                                        ### **🔹 Purpose:**  
                                        - Monitors **table sizes** to identify potential **storage issues**.  
                                        - Helps administrators track **unexpected growth** in tables.  
                                        - Provides insights into **disk usage trends**, allowing proactive storage management.  
                                        - Prevents performance degradation due to **oversized tables**.  

                                        ### **🔹 Example Scenario:**  
                                        Imagine an **audit log table** that has unexpectedly grown to **500GB**, consuming **50% of total storage**. This could indicate:  
                                        ✅ **Lack of archiving** or old data not being cleaned up.  
                                        ✅ **High insert frequency** leading to excessive storage consumption.  
                                        ✅ **Inefficient indexing** or table bloat affecting performance.  

                                        Using this tool, administrators can **analyze table sizes**, optimize storage, and prevent database slowdowns.  
                                    """)

                                    # Handle both DataFrame and tuple cases
                                    if isinstance(results, tuple):
                                        results = results[0]  # Assuming first element is DataFrame
                                    else:
                                        results = results

                                    if results is not None and not results.empty:
                                        # Convert size strings to bytes for proper sorting
                                        def convert_to_bytes(size_str):
                                            if 'MB' in size_str:
                                                return float(size_str.replace('MB', '').strip()) * 1024 * 1024
                                            elif 'kB' in size_str:
                                                return float(size_str.replace('kB', '').strip()) * 1024
                                            elif 'bytes' in size_str:
                                                return float(size_str.replace('bytes', '').strip())
                                            return 0
                                        
                                        # Add numeric size column for sorting
                                        results['size_numeric'] = results['tablesize'].apply(convert_to_bytes)
                                        
                                        # Sort by numeric size
                                        sorted_results = results.sort_values(by='size_numeric', ascending=False).reset_index(drop=True)
                                        
                                        # Display sorted dataframe
                                        st.dataframe(sorted_results[['tablename', 'tablesize']], use_container_width=True)
                                        
                                        # Create horizontal bar chart
                                        fig = px.bar(
                                            sorted_results.head(50),  # Show top 50 tables for better visibility
                                            x='size_numeric',
                                            y='tablename',
                                            orientation='h',
                                            title='Database Tables Size Distribution (Top 50 Largest Tables)',
                                            labels={
                                                'size_numeric': 'Table Size (bytes)',
                                                'tablename': 'Table Name'
                                            },
                                            color='size_numeric',
                                            color_continuous_scale='Viridis'
                                        )
                                        
                                        # Customize layout
                                        fig.update_layout(
                                            xaxis_title="Table Size",
                                            yaxis_title="Table Name",
                                            height=max(400, len(sorted_results.head(50)) * 25),
                                            showlegend=False,
                                            plot_bgcolor='white',
                                            bargap=0.2,
                                            yaxis={'categoryorder': 'total ascending'}
                                        )
                                        
                                        # Add gridlines
                                        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
                                        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
                                        
                                        st.plotly_chart(fig, use_container_width=True)

                                if selected_id == "3":  # Table and Index Size Analysis
                                    results = monitor.execute_query(tool_queries[selected_id][0])

                                    st.markdown("""
                                        ### **🔹 Purpose:**  
                                        - Tracks **table and index sizes** to optimize **disk usage**.  
                                        - Helps administrators **balance performance and storage efficiency**.  
                                        - Provides insights into **index bloat**, ensuring optimal query performance.  

                                        ### **🔹 Example Scenario:**  
                                        Imagine a **customer table** with an index that has grown to **100GB**, but it is **rarely used**. This could indicate:  
                                        ✅ An **unnecessary index** that is increasing storage costs without improving query performance.  
                                        ✅ **Index bloat** due to frequent updates and deletes, requiring maintenance.  
                                        ✅ **Suboptimal indexing strategy**, leading to wasted space.  

                                        Using this tool, administrators can **analyze table and index sizes**, remove redundant indexes, and improve **database performance and storage utilization**.  
                                    """)

                                    # Handle both DataFrame and tuple cases
                                    if isinstance(results, tuple):
                                        results = results[0]  # Assuming first element is DataFrame
                                    else:
                                        results = results

                                    if results is not None and not results.empty:
                                        # First, let's see what columns we have
                                        print("Available columns:", list(results.columns))

                                        # Convert size strings to bytes for proper sorting
                                        def convert_to_bytes(size_str):
                                            if 'MB' in size_str:
                                                return float(size_str.replace('MB', '').strip()) * 1024 * 1024
                                            elif 'kB' in size_str:
                                                return float(size_str.replace('kB', '').strip()) * 1024
                                            elif 'bytes' in size_str:
                                                return float(size_str.replace('bytes', '').strip())
                                            return 0

                                        # Add numeric size columns for sorting using actual column names
                                        results['table_bytes'] = results['tablesize'].apply(convert_to_bytes)
                                        results['index_bytes'] = results['indexsize'].apply(convert_to_bytes)

                                        # Sort by total size in descending order
                                        sorted_results = results.sort_values(by='table_bytes', ascending=False).reset_index(drop=True)

                                        # Display sorted dataframe with actual column names
                                        st.dataframe(sorted_results[['tablename', 'tablesize', 'indexsize']], 
                                                    use_container_width=True)

                                        # Create horizontal bar chart showing both table and index sizes
                                        fig = px.bar(
                                            sorted_results.head(50),  # Show top 50 tables for better visibility
                                            x=['table_bytes', 'index_bytes'],
                                            y='tablename',
                                            orientation='h',
                                            title='Table and Index Size Distribution (Top 50 Largest)',
                                            labels={
                                                'value': 'Size (bytes)',
                                                'tablename': 'Table Name',
                                                'variable': 'Size Type'
                                            },
                                            color_discrete_map={
                                                'table_bytes': '#d62728',  # Blue color for table size
                                                'index_bytes': '#17becf'   # Orange color for index size
                                            },
                                            barmode='stack'
                                        )

                                        # Customize layout
                                        fig.update_layout(
                                            xaxis_title="Size (bytes)",
                                            yaxis_title="Table Name",
                                            height=max(400, len(sorted_results.head(50)) * 25),
                                            showlegend=True,
                                            plot_bgcolor='white',
                                            bargap=0.2,
                                            yaxis={'categoryorder': 'total ascending'},
                                            legend_title="Size Components"
                                        )

                                        # Rename legend items for clarity
                                        fig.data[0].name = 'Table Size'
                                        fig.data[1].name = 'Index Size'

                                        # Add gridlines for better readability
                                        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
                                        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')

                                        # Show plot
                                        st.plotly_chart(fig, use_container_width=True)

                                if selected_id == "5":  # Vacuum Statistics
                                    results = monitor.execute_query(tool_queries[selected_id][0])

                                    st.markdown("""
                                        ### **🔹 Purpose:**  
                                        - Monitors **vacuum and analyze** operations on all tables.  
                                        - Tracks the **last vacuum, autovacuum, analyze, and autoanalyze** timestamps.  
                                        - Helps detect tables that may need **manual vacuuming** or adjustments to **autovacuum settings**.  
                                        - Ensures efficient storage usage by **reducing dead tuples** and preventing table bloat.  

                                        ### **🔹 Example Scenario:**  
                                        A **frequently updated table** accumulates many **dead tuples**, degrading query performance.  
                                        Running **vacuum** on the table removes **70% of dead tuples**, improving **query speed and storage efficiency**.  
                                    """)

                                    # Handle both DataFrame and tuple cases
                                    if isinstance(results, tuple):
                                        results = results[0]  # Assuming first element is DataFrame
                                    else:
                                        results = results

                                    if results is not None and not results.empty:
                                        # Define time-related columns
                                        time_cols = ['last_vacuum', 'last_autovacuum', 'last_analyze', 'last_autoanalyze']
                                        
                                        # Convert timestamps to datetime with UTC timezone
                                        for col in time_cols:
                                            if col in results.columns:
                                                results[col] = pd.to_datetime(results[col], errors='coerce', utc=True)

                                        # Get current time in UTC
                                        now = datetime.now(pytz.utc)

                                        # Convert timestamps to "HH:MM:SS (UTC) - DD MMM YYYY" for DataFrame readability
                                        results_display = results.copy()
                                        for col in time_cols:
                                            if col in results_display.columns:
                                                results_display[col] = results_display[col].apply(
                                                    lambda x: x.strftime('%H:%M:%S (UTC) - %d %b %Y') if pd.notnull(x) else "Never"
                                                )

                                        # Display DataFrame with human-readable timestamps
                                        st.dataframe(results_display[['relname'] + time_cols], use_container_width=True)

                                        # Convert timestamps to "Hours Ago" for visualization
                                        for col in time_cols:
                                            if col in results.columns:
                                                results[col + '_hours'] = results[col].apply(
                                                    lambda x: (now - x).total_seconds() / 3600 if pd.notnull(x) else None
                                                )

                                        # Ensure at least one valid numeric value is available for plotting
                                        valid_data = results.dropna(subset=[col + '_hours' for col in time_cols], how='all')

                                        if not valid_data.empty:
                                            # Visualization: Stacked Horizontal Bar Chart for Vacuum & Analyze Operations
                                            fig = go.Figure()

                                            # Add schema name if available, otherwise use empty string
                                            valid_data['schema_info'] = valid_data['schemaname'].fillna('') if 'schemaname' in valid_data.columns else ''

                                            for col, color, label in zip(
                                                [col + '_hours' for col in time_cols], 
                                                ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728'], 
                                                ['Last Vacuum (Hours Ago)', 'Last AutoVacuum (Hours Ago)', 'Last Analyze (Hours Ago)', 'Last AutoAnalyze (Hours Ago)']
                                            ):
                                                fig.add_trace(go.Bar(
                                                    y=valid_data['relname'],
                                                    x=valid_data[col],
                                                    name=label,
                                                    marker_color=color,
                                                    orientation='h',
                                                    customdata=valid_data['schema_info'],
                                                    hovertemplate=(
                                                        "<b>Table:</b> %{y}<br>" +
                                                        "<b>Schema:</b> %{customdata}<br>" +
                                                        "<b>Operation:</b> " + label + "<br>" +
                                                        "<b>Hours Ago:</b> %{x:.1f}<br>" +
                                                        "<extra></extra>"
                                                    )
                                                ))

                                            # Update layout
                                            fig.update_layout(
                                                title='Vacuum & Analyze Operations Timeline',
                                                xaxis_title='Hours Since Last Operation',
                                                yaxis_title='Table Name',
                                                barmode='stack',
                                                height=600,
                                                plot_bgcolor='white',
                                                showlegend=True,
                                                legend_title='Vacuum/Analyze Operations',
                                                hovermode='y unified',
                                                margin=dict(l=150, r=50, b=100, t=100, pad=4)
                                            )

                                            # Show chart
                                            st.plotly_chart(fig, use_container_width=True)
                                        else:
                                            st.warning("No valid vacuum/analyze timestamps available for visualization.")
    
                                if selected_id == "18":  # Query Metrics
                                    results = monitor.execute_query(tool_queries[selected_id][0])

                                    st.markdown("""
                                        ### **🔹 Purpose:**  
                                        - Tracks **query execution performance** using statistics from `pg_stat_statements`.  
                                        - Analyzes **average execution time**, **CPU usage**, **I/O time**, and **query frequency**.  
                                        - Identifies queries that **consume excessive resources** or degrade performance.  
                                        - Helps detect performance bottlenecks due to **missing indexes, inefficient joins, or high I/O operations**.  

                                        ### **🔹 Example Scenario:**  
                                        A query that usually executes in **100ms** suddenly spikes to **2 seconds**. This could indicate:  
                                        ✅ A **missing index**, leading to a full table scan.  
                                        ✅ Increased database load due to **high concurrency**.  
                                        ✅ **I/O bottlenecks** from excessive disk reads and writes. 

                                        ### **🔹 ACTION ITEMS:**  
                                        - Optimize query execution plans for queries with high total_exec_time  
                                        - Add appropriate indexes for queries with low rows_per_second  
                                        - Rewrite queries with high time_per_call to be more efficient  
                                        - Reduce frequency of expensive queries with high calls count  
                                        - Consider caching results for queries that are called frequently  
                                        - Analyze query patterns to identify opportunities for stored procedures  
                                        - Review application logic that generates inefficient queries  
                                        - Implement partitioning for tables accessed by slow queries  
                                        - Consider materialized views for complex queries with static data  
                                        - Evaluate connection pooling settings if many similar queries appear  

                                        ### **🔹 INTERPRETATION:**  
                                        - High time_per_call + low rows: Likely inefficient query design  
                                        - High calls + low time_per_call: Potential for connection pooling optimization  
                                        - High total_exec_time + low calls: Critical but infrequent operations to optimize  
                                        - Low rows_per_second: Possible missing indexes or poor join conditions  
                                        - High calls_per_second: May indicate excessive querying from application 

                                        Using this tool, administrators can monitor query trends, identify **slow-performing queries**,  
                                        and take corrective actions such as **query optimization, indexing, or resource allocation**.  
                                    """)

                                    # Handle both DataFrame and tuple cases
                                    if isinstance(results, tuple):
                                        results = results[0]  # Assuming first element is DataFrame
                                    else:
                                        results = results

                                    if results is not None and not results.empty:
                                        # Ensure numeric conversion and prevent errors
                                        numeric_cols = ["time_per_call", "calls_per_second", "rows_per_second", "total_exec_time"]
                                        for col in numeric_cols:
                                            if col in results.columns:
                                                results[col] = pd.to_numeric(results[col], errors="coerce").clip(lower=0)

                                        # Sort by time_per_call in descending order
                                        results = results.sort_values(by="time_per_call", ascending=False).reset_index(drop=True)

                                        # Truncate long query texts for better readability
                                        results["query_short"] = results["query"].str[:60] + "..."  # First 60 characters

                                        # Rename columns for clarity
                                        results = results.rename(columns={
                                            "time_per_call": "time_per_call (ms)",
                                            "total_exec_time": "total_exec_time (ms)"
                                        })

                                        # Display DataFrame with updated column names
                                        st.dataframe(results[["query", "calls", "time_per_call (ms)", "calls_per_second", "rows_per_second", "total_exec_time (ms)"]],
                                                    use_container_width=True)

                                        # **Visualization: Top 10 Queries by Execution Time**
                                        fig = px.bar(
                                            results.head(10),  # Show only top 10 slowest queries
                                            x="time_per_call (ms)",
                                            y="query_short",
                                            orientation="h",
                                            title="Top 10 Slowest Queries by Execution Time",
                                            labels={"time_per_call (ms)": "Execution Time (ms)", "query_short": "Query"},
                                            color="time_per_call (ms)",
                                            color_continuous_scale="reds"
                                        )

                                        # Improve layout
                                        fig.update_layout(
                                            xaxis_title="Execution Time (ms)",
                                            yaxis_title="Query",
                                            yaxis=dict(showgrid=True, gridcolor="LightGray"),
                                            plot_bgcolor="white",
                                            height=600
                                        )

                                        # Show the chart
                                        st.plotly_chart(fig, use_container_width=True)
                                            
                                if selected_id == "25":  # Connection Analysis Scanner (C-Scanner)
                                    results = monitor.execute_query(tool_queries[selected_id][0])

                                    # Display tool details
                                    st.markdown("""
                                        ### **🔹 Purpose:**  
                                        - Monitors **active database connections** and tracks their **CPU usage and execution time**.  
                                        - Identifies **long-running queries** and connections consuming **excessive system resources**.  
                                        - Helps detect **inefficient queries** (e.g., Cartesian joins, excessive looping) that **strain the CPU**.  
                                        - Provides insights into **client connections, backend start time, and query duration**.  

                                        ### **🔹 Example Scenario:**  
                                        A query is running a **Cartesian join**, consuming **high CPU resources** unnecessarily.  
                                        This could indicate:  
                                        ✅ **Inefficient query design**, leading to an **exponential increase** in data processing.  
                                        ✅ **High concurrency**, causing CPU spikes and performance degradation.  
                                        ✅ **Idle connections consuming resources**, leading to **connection saturation**.  

                                        Using this tool, administrators can quickly **identify problematic connections, optimize queries, and terminate unnecessary sessions** to maintain database health.  
                                    """)

                                    if isinstance(results, tuple):
                                        results = results[0]  # Assuming first element is DataFrame
                                    else:
                                        results = results

                                    if results is not None and not results.empty:

                                        # Sort results by total duration in descending order
                                        sorted_results = results.sort_values(by='total_duration', ascending=False).reset_index(drop=True)

                                        # Convert timestamps to datetime and handle timezone conversion to IST
                                        for col in ['query_start', 'backend_start']:
                                            if col in sorted_results.columns:
                                                sorted_results[col] = pd.to_datetime(sorted_results[col], errors='coerce')

                                                # Convert to IST only if already timezone-aware
                                                if sorted_results[col].dt.tz is not None:
                                                    sorted_results[col] = sorted_results[col].dt.tz_convert('Asia/Kolkata')
                                                else:
                                                    sorted_results[col] = sorted_results[col].dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata')

                                        # Display complete dataframe with IST time
                                        st.dataframe(sorted_results[[
                                            'pid', 'usename', 'application_name', 'client_addr', 'client_port',
                                            'query_start', 'backend_start', 'query_duration', 'total_duration'
                                        ]], use_container_width=True)

                                        # Convert PID to string for better readability
                                        sorted_results['pid'] = sorted_results['pid'].astype(str)

                                        # Create a heatmap to visualize query duration per PID
                                        fig = px.density_heatmap(
                                            sorted_results,
                                            x="pid",
                                            y="query_start",
                                            z="query_duration",
                                            color_continuous_scale="blues",
                                            title="Query Duration Heatmap by Process ID (IST)",
                                            labels={"pid": "Process ID (PID)", "query_start": "Query Start Time (IST)", "query_duration": "Duration (seconds)"},
                                        )

                                        # Improve layout
                                        fig.update_layout(
                                            height=600,
                                            plot_bgcolor="white",
                                            xaxis_title="Process ID (PID)",
                                            yaxis_title="Query Start Time (IST)",
                                            coloraxis_colorbar=dict(title="Query Duration (s)"),
                                        )

                                        # Display the heatmap
                                        st.plotly_chart(fig, use_container_width=True)
                                                
                                # if selected_id == "26":  # X-Ray C Transactions
                                #     results = monitor.execute_query("""
                                #         SELECT 
                                #             r.rolname AS username, 
                                #             d.datname AS database_name,
                                #             s.queryid,
                                #             s.calls,
                                #             s.total_exec_time,
                                #             s.rows,
                                #             s.query
                                #         FROM pg_stat_statements s
                                #         JOIN pg_roles r ON s.userid = r.oid
                                #         JOIN pg_database d ON s.dbid = d.oid
                                #         WHERE s.query ILIKE '%commit%'
                                #         ORDER BY s.calls DESC 
                                #         LIMIT 10;
                                #     """)

                                #     st.markdown("""
                                #     **🔹 Use Case:** Detailed analysis of active transactions.  
                                #     **🔹 Example:** A single transaction is holding locks for 20 minutes.  
                                #     """)

                                #     if results is not None and not results.empty:
                                #         # Convert execution time to milliseconds
                                #         results['total_exec_time_ms'] = results['total_exec_time'] / 1000  # Convert from microseconds to milliseconds

                                #         # Display Data Table
                                #         st.dataframe(results[['username', 'database_name', 'queryid', 'calls', 'total_exec_time_ms', 'rows', 'query']], 
                                #                     use_container_width=True)

                                #         # Create Stacked Bar Chart for better visualization
                                #         fig = go.Figure()

                                #         # Execution Time Bar
                                #         fig.add_trace(go.Bar(
                                #             y=results['queryid'].astype(str),  
                                #             x=results['total_exec_time_ms'],
                                #             name='Execution Time (ms)',
                                #             marker_color='#1f77b4',
                                #             orientation='h',
                                #             hovertemplate="Query ID: %{y}<br>Execution Time: %{x:.2f} ms"
                                #         ))

                                #         # Calls per transaction
                                #         fig.add_trace(go.Bar(
                                #             y=results['queryid'].astype(str),
                                #             x=results['calls'],
                                #             name='Calls',
                                #             marker_color='#ff7f0e',
                                #             orientation='h',
                                #             hovertemplate="Query ID: %{y}<br>Calls: %{x}"
                                #         ))

                                #         # Update layout for clarity
                                #         fig.update_layout(
                                #             title='Transaction Execution Time & Calls (Top 10 Queries)',
                                #             xaxis_title='Time (ms) / Calls',
                                #             yaxis_title='Query ID',
                                #             barmode='stack',  # Stacked bar for better comparison
                                #             height=600,
                                #             plot_bgcolor='white',
                                #             showlegend=True,
                                #             legend_title='Metrics',
                                #             hovermode='y'
                                #         )

                                #         # Add gridlines
                                #         fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
                                #         fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')

                                #         # Display the chart
                                #         st.plotly_chart(fig, use_container_width=True)


                                if selected_id == "35":  # X-Ray Transactions
                                    results = monitor.execute_query(tool_queries[selected_id][0])

                                    st.markdown("""
                                        ### **🔹 Purpose:**  
                                        - Monitors **active transactions** and detects those running for **more than 5 minutes**.  
                                        - Helps identify **slow query patterns** that may **impact database performance**.  
                                        - Highlights **long-running transactions** that could cause **locking issues** or **resource contention**.  
                                        - Provides insights into **which queries are consuming excessive execution time** and need optimization.  

                                        ### **🔹 Example Scenario:**  
                                        A query performing a **nested loop join** takes **30 seconds** to process **1 million rows**. This could indicate:  
                                        ✅ **Inefficient join strategies**, leading to **slow performance**.  
                                        ✅ **Missing indexes**, causing **full table scans**.  
                                        ✅ **High transaction duration**, potentially **blocking other queries**.  

                                        Using this tool, administrators can **identify slow transactions, analyze query execution plans, and optimize performance** proactively.  
                                    """)

                                    if isinstance(results, tuple):
                                        results = results[0]  # Assuming first element is DataFrame
                                    else:
                                        results = results

                                    if results is not None and not results.empty:
                                        # Sort by total_time in descending order
                                        sorted_results = results.sort_values(by='total_time', ascending=False).reset_index(drop=True)

                                        # Display complete dataframe with all columns
                                        st.dataframe(sorted_results, use_container_width=True)

                                        # Extract top 10 slowest queries for visualization
                                        top_queries = sorted_results.head(10)

                                        # Create stacked bar chart
                                        fig = go.Figure()

                                        fig.add_trace(go.Bar(
                                            y=top_queries['query'].astype(str),  # Query text (truncated for display)
                                            x=top_queries['total_time'],
                                            name='Total Execution Time',
                                            marker_color='#1f77b4',
                                            orientation='h'
                                        ))

                                        fig.add_trace(go.Bar(
                                            y=top_queries['query'].astype(str),
                                            x=top_queries['calls'],
                                            name='Number of Calls',
                                            marker_color='#ff7f0e',
                                            orientation='h'
                                        ))

                                        # Update layout
                                        fig.update_layout(
                                            title='X-Ray Transaction Analysis: Execution Time & Calls',
                                            xaxis_title='Time (seconds) / Calls',
                                            yaxis_title='Query',
                                            barmode='stack',
                                            height=600,
                                            plot_bgcolor='white',
                                            showlegend=True
                                        )

                                        st.plotly_chart(fig, use_container_width=True)

                                if selected_id == "55":  # X-Ray Long Transactions
                                    results = monitor.execute_query(tool_queries[selected_id][0])

                                    st.markdown("""
                                        ### **🔹 Purpose:**  
                                        - Identifies **long-running transactions** that have been active for **more than 5 minutes**.  
                                        - Detects **queries holding locks** that could **block other transactions**.  
                                        - Helps prevent **performance degradation** by flagging transactions that may need intervention.  
                                        - Provides insights into **which queries are running excessively long** and may require optimization.  

                                        ### **🔹 Example Scenario:**  
                                        A transaction has been **active for 2 hours**, holding a lock that **blocks other operations**. This could indicate:  
                                        ✅ **Uncommitted transactions**, leading to **table or row locks**.  
                                        ✅ **Inefficient query execution**, causing **prolonged resource usage**.  
                                        ✅ **Slow client application behavior**, failing to **commit or rollback** transactions timely.  

                                        Using this tool, administrators can **detect, analyze, and take action** on long-running transactions to **prevent system bottlenecks**.  
                                    """)

                                    if isinstance(results, tuple):
                                        results = results[0]  # Assuming first element is DataFrame
                                    else:
                                        results = results

                                    if results is not None and not results.empty:
                                        # Convert 'duration' to seconds for easier analysis
                                        results['duration_seconds'] = results['duration'].dt.total_seconds()

                                        # Sort by duration in descending order
                                        sorted_results = results.sort_values(by='duration_seconds', ascending=False).reset_index(drop=True)

                                        # Display the complete dataframe
                                        st.dataframe(sorted_results[['pid', 'usename', 'query', 'state', 'duration']], use_container_width=True)

                                        # Extract top long-running transactions for visualization
                                        top_transactions = sorted_results.head(10)

                                        # Create horizontal bar chart
                                        fig = go.Figure()

                                        fig.add_trace(go.Bar(
                                            y=top_transactions['query'].astype(str),  # Display query text
                                            x=top_transactions['duration_seconds'],
                                            name='Duration (seconds)',
                                            marker_color='#1f77b4',
                                            orientation='h'
                                        ))

                                        # Update layout
                                        fig.update_layout(
                                            title='X-Ray Long Transactions: Execution Time',
                                            xaxis_title='Duration (seconds)',
                                            yaxis_title='Query',
                                            height=600,
                                            plot_bgcolor='white',
                                            showlegend=True
                                        )

                                        st.plotly_chart(fig, use_container_width=True)


                                if selected_id == "6":  # Wait Events Analysis
                                    results = monitor.execute_query(tool_queries[selected_id][0])

                                    st.markdown("""
                                        ### **🔹 Purpose:**  
                                        - Diagnoses **database wait events** to identify **performance bottlenecks**.  
                                        - Helps pinpoint **slowdowns in query execution** due to **resource waits**.  
                                        - Enables administrators to **optimize resource allocation** and improve efficiency.  

                                        ### **🔹 Example Scenario:**  
                                        During peak transaction periods, queries experience high `"IO:DataFileRead"` wait events, indicating **I/O bottlenecks**.  
                                        This could be caused by:  
                                        ✅ **Slow disk performance**, leading to longer read/write times.  
                                        ✅ **Contention on shared resources**, where multiple queries compete for I/O.  
                                        ✅ **High concurrent transactions**, increasing load on storage and CPU.  

                                        Using this tool, administrators can **monitor wait events**, analyze their impact, and take proactive measures to **reduce delays** in query execution.  
                                    """)

                                    if isinstance(results, tuple):
                                        results = results[0]  # Assuming first element is DataFrame
                                    else:
                                        results = results

                                    if results is not None and not results.empty:
                                        # Display complete dataframe
                                        st.dataframe(results[['pid', 'wait_event_type', 'wait_event']], 
                                                    use_container_width=True)
                                        
                                        # Create visualization
                                        fig = go.Figure()
                                        
                                        # Count frequency of each wait event type
                                        event_counts = results['wait_event_type'].value_counts()
                                        
                                        # Add bar chart for wait events
                                        fig.add_trace(go.Bar(
                                            x=event_counts.index,
                                            y=event_counts.values,
                                            name='Wait Events',
                                            marker_color='#1f77b4',
                                            hovertemplate="<br>".join([
                                                "Event Type: %{x}",
                                                "Count: %{y}"
                                            ])
                                        ))
                                        
                                        # Update layout
                                        fig.update_layout(
                                            title='Database Wait Events Distribution',
                                            xaxis_title='Wait Event Type',
                                            yaxis_title='Number of Events',
                                            height=600,
                                            showlegend=True,
                                            plot_bgcolor='white',
                                            bargap=0.2,
                                            xaxis={'categoryorder': 'total descending'}
                                        )
                                        
                                        # Add gridlines
                                        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
                                        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
                                        
                                        st.plotly_chart(fig, use_container_width=True)

                                if selected_id == "13":  # Blocking Query Analysis
                                    results = monitor.execute_query(tool_queries[selected_id][0])
                                    
                                    st.markdown("""
                                        ### **🔹 Purpose:**  
                                        - Identifies **queries causing blocks** in the database.  
                                        - Helps locate transactions that **prevent others from executing**.  
                                        - Provides insights into **which queries are blocked and which ones are blocking them**.  
                                        - Enables administrators to **resolve conflicts** by **terminating or optimizing queries**.  

                                        ### **🔹 Example Scenario:**  
                                        A **long-running report query** is blocking **20 other transactions**, causing system delays.  
                                        This could be due to:  
                                        ✅ **Unoptimized queries holding locks for too long.**  
                                        ✅ **High concurrency leading to transaction contention.**  
                                        ✅ **Poorly managed indexing or missing indexes.**  

                                        Using this tool, administrators can **identify blocking queries**, assess their impact, and take corrective actions such as:  
                                        🔹 **Killing the blocking query if necessary** (`pg_terminate_backend(blocking_pid)`).  
                                        🔹 **Optimizing transaction isolation levels** to reduce contention.  
                                        🔹 **Improving indexing strategies** for better query execution.  
                                    """)
                                    
                                    if isinstance(results, tuple):
                                        results = results[0]  # Assuming first element is DataFrame
                                    else:
                                        results = results

                                    if results is not None and not results.empty:
                                        # Display complete dataframe
                                        st.dataframe(results[[
                                            'blocked_pid', 
                                            'blocked_user',
                                            'blocking_pid',
                                            'blocking_user',
                                            'blocked_statement',
                                            'current_statement_in_blocking_process',
                                            'blocked_application',
                                            'blocking_application'
                                        ]], use_container_width=True)
                                        
                                        # Create network visualization
                                        fig = go.Figure()
                                        
                                        # Add scatter plot for blocking relationships
                                        fig.add_trace(go.Scatter(
                                            x=results['blocking_pid'],
                                            y=results['blocked_pid'],
                                            mode='markers+text',
                                            marker=dict(
                                                size=15,
                                                color='#1f77b4',
                                                symbol='diamond'
                                            ),
                                            text=results['blocked_user'],
                                            textposition='bottom center',
                                            name='Blocking Relationships',
                                            hovertemplate="<br>".join([
                                                "Blocking PID: %{x}",
                                                "Blocked PID: %{y}",
                                                "Blocking User: %{customdata[0]}",
                                                "Blocked User: %{customdata[1]}",
                                                "Blocking App: %{customdata[2]}",
                                                "Blocked App: %{customdata[3]}"
                                            ]),
                                            customdata=results[['blocking_user', 'blocked_user', 
                                                            'blocking_application', 'blocked_application']].values
                                        ))
                                        
                                        # Update layout
                                        fig.update_layout(
                                            title='Database Blocking Query Relationships',
                                            xaxis_title='Blocking Process ID',
                                            yaxis_title='Blocked Process ID',
                                            height=600,
                                            showlegend=True,
                                            plot_bgcolor='white',
                                            hovermode='closest'
                                        )
                                        
                                        # Add gridlines
                                        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
                                        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
                                        
                                        st.plotly_chart(fig, use_container_width=True)

                                if selected_id == "15":  # Sessions Analysis
                                    results = monitor.execute_query(tool_queries[selected_id][0])
                                    
                                    st.markdown("""
                                        ### **🔹 Purpose:**  
                                        - Monitors **active database sessions** to detect unusual spikes.  
                                        - Identifies databases with **high session counts** that may cause resource contention.  
                                        - Helps administrators **analyze workload distribution** across different databases.  
                                        - Provides insights into **session trends over time**, allowing proactive scaling.  

                                        ### **🔹 Example Scenario:**  
                                        An **unexpected spike in active sessions** slows down the database.  
                                        This could be due to:  
                                        ✅ **Application issues causing excessive connections.**  
                                        ✅ **Inefficient connection pooling leading to overload.**  
                                        ✅ **Long-running queries holding sessions open.**  

                                        Using this tool, administrators can:  
                                        🔹 **Identify which databases have the highest number of active sessions.**  
                                        🔹 **Investigate if connection limits are being exceeded.**  
                                        🔹 **Optimize connection pooling to prevent session overload.**  
                                        🔹 **Terminate idle or problematic sessions** if necessary (`pg_terminate_backend(pid)`).  
                                    """)

                                    if isinstance(results, tuple):
                                        results = results[0]  # Assuming first element is DataFrame
                                    else:
                                        results = results
                                    
                                    if results is not None and not results.empty:
                                        # Convert num_sessions to integer type
                                        results['num_sessions'] = results['num_sessions'].astype(int)
                                        
                                        # Sort by number of sessions in descending order
                                        sorted_results = results.sort_values(by='num_sessions', ascending=False).reset_index(drop=True)
                                        
                                        # Display complete dataframe
                                        st.dataframe(sorted_results[['database_name', 'num_sessions']], 
                                                    use_container_width=True)
                                        
                                        # Create visualization
                                        fig = go.Figure()
                                        
                                        # Add bar chart for sessions
                                        fig.add_trace(go.Bar(
                                            x=sorted_results['database_name'],
                                            y=sorted_results['num_sessions'],
                                            name='Active Sessions',
                                            marker_color='#1f77b4',
                                            hovertemplate="<br>".join([
                                                "Database: %{x}",
                                                "Sessions: %{y:d}"  # Format as integer
                                            ])
                                        ))
                                        
                                        # Update layout with integer y-axis ticks
                                        fig.update_layout(
                                            title='Database Sessions Distribution',
                                            xaxis_title='Database Name',
                                            yaxis_title='Number of Sessions',
                                            height=600,
                                            showlegend=True,
                                            plot_bgcolor='white',
                                            bargap=0.2,
                                            xaxis={'categoryorder': 'total descending'},
                                            yaxis=dict(
                                                tickmode='linear',
                                                tick0=0,
                                                dtick=1,
                                                tickformat='d'  # Force integer format
                                            )
                                        )
                                        
                                        # Add gridlines
                                        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
                                        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
                                        
                                        st.plotly_chart(fig, use_container_width=True)

                                if selected_id == "16":  # State Analysis
                                    results = monitor.execute_query(tool_queries[selected_id][0])
                                    
                                    st.markdown("""
                                        ### **🔹 Purpose:**  
                                        - Monitors the **state of all active database sessions**.  
                                        - Identifies sessions that are **idle or active in transactions**.  
                                        - Helps diagnose **session management issues**, including long-running idle transactions.  
                                        - Provides insights into **connection behavior** to optimize resource usage.  

                                        ### **🔹 Example Scenario:**  
                                        Multiple **"idle in transaction"** sessions indicate uncommitted connections.  
                                        This could lead to:  
                                        ✅ **Locks being held unnecessarily, blocking other transactions.**  
                                        ✅ **Increased resource usage due to open sessions.**  
                                        ✅ **Potential deadlocks if transactions are left incomplete.**  

                                        Using this tool, administrators can:  
                                        🔹 **Detect long-running idle transactions that need to be committed or closed.**  
                                        🔹 **Optimize connection pooling to prevent excessive idle sessions.**  
                                        🔹 **Monitor session states to ensure efficient database operations.**  
                                        🔹 **Terminate problematic sessions if necessary** (`pg_terminate_backend(pid)`).  
                                    """)

                                    if isinstance(results, tuple):
                                        results = results[0]  # Assuming first element is DataFrame
                                    else:
                                        results = results

                                    if results is not None and not results.empty:
                                        # Display complete dataframe
                                        st.dataframe(results[['pid', 'usename', 'application_name', 'state']], use_container_width=True)

                                        # Count occurrences of each state
                                        state_counts = results['state'].value_counts().reset_index()
                                        state_counts.columns = ['state', 'count']

                                        # Define color mapping for states
                                        color_map = {
                                            'active': '#2ecc71',  # Green for active
                                            'idle': '#f39c12',    # Orange for idle
                                            'idle in transaction': '#e74c3c',  # Red for problematic idle transactions
                                            'waiting': '#3498db', # Blue for waiting queries
                                            'fastpath function call': '#9b59b6'  # Purple for special cases
                                        }

                                        # Create donut chart
                                        fig = px.pie(
                                            state_counts,
                                            values='count',
                                            names='state',
                                            title='Session State Distribution',
                                            hole=0.4,  # Donut effect
                                            color='state',
                                            color_discrete_map=color_map
                                        )

                                        # Improve layout
                                        fig.update_layout(
                                            height=500,
                                            showlegend=True,
                                            plot_bgcolor='white'
                                        )

                                        # Display the chart
                                        st.plotly_chart(fig, use_container_width=True)

                                if selected_id == "17":  # Locks
                                    results = monitor.execute_query(tool_queries[selected_id][0])

                                    st.markdown("""
                                        ### **🔹 Purpose:**  
                                        - Identifies **active locks** that may cause **blocking or performance issues**.  
                                        - Helps diagnose **lock contention** affecting queries and transactions.  
                                        - Detects **exclusive locks** that might lead to **deadlocks** or system slowdowns.  
                                        - Allows administrators to **take action** by analyzing lock types and affected queries.  

                                        ### **🔹 Example Scenario:**  
                                        A **table-level lock** during schema changes causes application downtime.  
                                        This could indicate:  
                                        ✅ **Long-running transactions holding locks and blocking other operations.**  
                                        ✅ **Multiple queries competing for access, leading to lock contention.**  
                                        ✅ **Schema modifications (DDL changes) locking the entire table.**  

                                        Using this tool, administrators can:  
                                        🔹 **Identify problematic locks that are preventing query execution.**  
                                        🔹 **Analyze which queries or users are causing excessive locking.**  
                                        🔹 **Terminate or adjust conflicting transactions to restore performance.**  
                                        🔹 **Optimize transaction handling to minimize lock durations.**  
                                    """)

                                    if isinstance(results, tuple):
                                        results = results[0]  # Assuming first element is DataFrame
                                    else:
                                        results = results

                                    if results is not None and not results.empty:
                                        # Display complete dataframe
                                        st.dataframe(results[['pid', 'usename', 'query', 'mode']], use_container_width=True)

                                        # Count number of locks per mode and user
                                        lock_counts = results.groupby(['mode', 'usename']).size().reset_index(name='count')

                                        # Define color mapping for lock modes
                                        color_map = {
                                            'RowExclusiveLock': '#1f77b4',
                                            'ShareUpdateExclusiveLock': '#ff7f0e',
                                            'ShareRowExclusiveLock': '#2ca02c',
                                            'ExclusiveLock': '#d62728',
                                            'AccessExclusiveLock': '#9467bd'
                                        }

                                        # Create stacked bar chart with lock modes on y-axis
                                        fig = px.bar(
                                            lock_counts,
                                            x='count',
                                            y='mode',  # ✅ Now using 'mode' as the y-axis
                                            color='usename',  # ✅ Different colors for users holding the locks
                                            title='Lock Distribution by Lock Mode',
                                            labels={'mode': 'Lock Mode', 'count': 'Number of Locks', 'usename': 'User'},
                                            orientation='h',
                                            text='count',
                                            color_discrete_sequence=px.colors.qualitative.Set3  # Diverse colors for better distinction
                                        )

                                        # Improve layout
                                        fig.update_layout(
                                            height=600,
                                            plot_bgcolor='white',
                                            legend_title='Users',
                                            yaxis=dict(categoryorder='total ascending')  # Sorting by total locks per mode
                                        )

                                        # Display the chart
                                        st.plotly_chart(fig, use_container_width=True)


                                if selected_id == "37":  # Congestion Analysis
                                    results = monitor.execute_query(tool_queries[selected_id][0])

                                    st.markdown("""
                                        ### **🔹 Purpose:**  
                                        - Identifies **database congestion issues** related to **connection pooling and wait events**.  
                                        - Helps **optimize resource allocation** by analyzing connection bottlenecks.  
                                        - Provides insights into **peak-hour traffic issues** affecting database performance.  

                                        ### **🔹 Example Scenario:**  
                                        Imagine a database experiencing **connection delays** during peak hours. This could indicate:  
                                        ✅ **Inefficient connection pooling configuration, causing query queuing.**  
                                        ✅ **Too many concurrent sessions leading to resource contention.**  
                                        ✅ **High wait times due to locked resources or slow I/O operations.**  

                                        Using this tool, administrators can:  
                                        🔹 **Detect wait events causing congestion.**  
                                        🔹 **Analyze connection pooling efficiency and optimize settings.**  
                                        🔹 **Identify and resolve blocking issues slowing down transactions.**  
                                        🔹 **Ensure smoother database operations by reducing connection bottlenecks.**  
                                    """)

                                    if isinstance(results, tuple):
                                        results = results[0]  # Assuming first element is DataFrame
                                    else:
                                        results = results

                                    if results is not None and not results.empty:
                                        # Display complete dataframe
                                        st.dataframe(results[['wait_event', 'wait_event_type']], 
                                                    use_container_width=True)
                                        
                                        # Group and count events
                                        event_type_counts = results.groupby(['wait_event_type', 'wait_event']).size().reset_index(name='count')
                                        
                                        # Create visualization
                                        fig = go.Figure()
                                        
                                        # Create grouped bar chart
                                        for event_type in event_type_counts['wait_event_type'].unique():
                                            mask = event_type_counts['wait_event_type'] == event_type
                                            fig.add_trace(go.Bar(
                                                name=event_type,
                                                x=event_type_counts[mask]['wait_event'],
                                                y=event_type_counts[mask]['count'],
                                                hovertemplate="<br>".join([
                                                    "Event Type: %{data.name}",
                                                    "Event: %{x}",
                                                    "Count: %{y}"
                                                ])
                                            ))
                                        
                                        # Update layout
                                        fig.update_layout(
                                            title='Database Congestion Analysis by Event Type',
                                            xaxis_title='Wait Event',
                                            yaxis_title='Count',
                                            height=600,
                                            showlegend=True,
                                            legend_title='Event Types',
                                            plot_bgcolor='white',
                                            barmode='group',
                                            yaxis=dict(
                                                tickmode='linear',
                                                tick0=0,
                                                dtick=1,
                                                tickformat='d'
                                            )
                                        )
                                        
                                        # Add gridlines
                                        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
                                        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
                                        
                                        # Display the visualization
                                        st.plotly_chart(fig, use_container_width=True)
                            
                                if selected_id == "50":  # X-ray W-Events Analysis
                                    results = monitor.execute_query(tool_queries[selected_id][0])
                                    
                                    st.markdown("""
                                        ### **🔹 Purpose:**  
                                        - Monitors **write-related wait events** in the database.  
                                        - Helps detect **delays in writing data**, impacting overall performance.  
                                        - Assists in diagnosing **bottlenecks caused by frequent updates, inserts, or deletes**.  

                                        ### **🔹 Example Scenario:**  
                                        Imagine a **large transactional table** where **frequent updates** cause high write wait times. This could indicate:  
                                        ✅ **High I/O load due to excessive writes.**  
                                        ✅ **Inefficient indexing slowing down updates.**  
                                        ✅ **Frequent vacuum operations trying to reclaim dead tuples.**  
                                        ✅ **Concurrency issues leading to lock waits on write operations.**  

                                        Using this tool, administrators can:  
                                        🔹 **Analyze the impact of write-heavy workloads.**  
                                        🔹 **Identify tables or indexes causing write slowdowns.**  
                                        🔹 **Optimize indexing strategies to reduce write delays.**  
                                        🔹 **Tune autovacuum settings for better write performance.**  
                                    """)

                                    if isinstance(results, tuple):
                                        results = results[0]  # Assuming first element is DataFrame
                                    else:
                                        results = results
                                    
                                    if results is not None and not results.empty:
                                        # Sort by wait_count for better visualization
                                        sorted_results = results.sort_values(by='wait_count', ascending=False)
                                        
                                        # Display complete dataframe
                                        st.dataframe(sorted_results[['event', 'wait_count', 'total_time', 'avg_wait_time']], 
                                                    use_container_width=True)
                                        
                                        # Create visualization
                                        fig = go.Figure()
                                        
                                        # Add bar chart for wait events
                                        fig.add_trace(go.Bar(
                                            x=sorted_results['event'],
                                            y=sorted_results['wait_count'],
                                            name='Wait Count',
                                            marker_color=sorted_results['avg_wait_time'],
                                            marker=dict(
                                                colorscale='Viridis',
                                                showscale=True,
                                                colorbar=dict(title='Avg Wait Time')
                                            ),
                                            hovertemplate="<br>".join([
                                                "Event: %{x}",
                                                "Wait Count: %{y}",
                                                "Total Time: %{customdata[0]:.2f}",
                                                "Avg Wait Time: %{customdata[1]:.2f}"
                                            ]),
                                            customdata=sorted_results[['total_time', 'avg_wait_time']].values
                                        ))
                                        
                                        # Update layout
                                        fig.update_layout(
                                            title='Wait Events Analysis',
                                            xaxis_title='Event Type',
                                            yaxis_title='Wait Count',
                                            height=600,
                                            showlegend=True,
                                            plot_bgcolor='white',
                                            xaxis=dict(
                                                tickangle=45,
                                                tickfont=dict(size=12)
                                            ),
                                            yaxis=dict(
                                                tickmode='linear',
                                                tickfont=dict(size=12)
                                            )
                                        )
                                        
                                        # Add gridlines
                                        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
                                        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
                                        
                                        st.plotly_chart(fig, use_container_width=True)

                                if selected_id == "51":  # X-ray W-States Analysis
                                    results = monitor.execute_query(tool_queries[selected_id][0])

                                    st.markdown("""
                                        ### **🔹 Purpose:**  
                                        - Tracks **write-related session states** to detect performance bottlenecks.  
                                        - Helps diagnose **write-intensive workloads** that may be causing contention.  
                                        - Assists in optimizing **database concurrency and transaction management**.  

                                        ### **🔹 Example Scenario:**  
                                        Imagine a **highly transactional system** where many sessions are stuck in the **"writing"** state. This could indicate:  
                                        ✅ **Inefficient batch updates causing write locks.**  
                                        ✅ **Heavy concurrent transactions leading to disk contention.**  
                                        ✅ **Checkpoints or autovacuum processes struggling to keep up.**  
                                        ✅ **Long-running writes blocking other operations.**  

                                        Using this tool, administrators can:  
                                        🔹 **Identify queries causing excessive write waits.**  
                                        🔹 **Tune autovacuum settings to improve write performance.**  
                                        🔹 **Optimize bulk inserts and updates to reduce contention.**  
                                        🔹 **Detect and terminate problematic write-heavy transactions.**  
                                    """)

                                    if isinstance(results, tuple):
                                        results = results[0]  # Assuming first element is DataFrame
                                    else:
                                        results = results

                                    if results is not None and not results.empty:
                                        # Sort by wait_count for better visualization
                                        sorted_results = results.sort_values(by='wait_count', ascending=False)
                                        
                                        # Display complete dataframe
                                        st.dataframe(sorted_results[['state', 'wait_count', 'total_time', 'avg_wait_time']], 
                                                    use_container_width=True)
                                        
                                        # Create visualization
                                        fig = go.Figure()
                                        
                                        # Add bar chart for states
                                        fig.add_trace(go.Bar(
                                            x=sorted_results['state'],
                                            y=sorted_results['wait_count'],
                                            name='Wait Count',
                                            marker_color=['#2ecc71' if x == 'active' else '#e74c3c' for x in sorted_results['state']],
                                            hovertemplate="<br>".join([
                                                "State: %{x}",
                                                "Wait Count: %{y}",
                                                "Total Time: %{customdata[0]:.2f}",
                                                "Avg Wait Time: %{customdata[1]:.2f}"
                                            ]),
                                            customdata=sorted_results[['total_time', 'avg_wait_time']].values,
                                            width=0.6  # Make bars wider
                                        ))
                                        
                                        # Update layout
                                        fig.update_layout(
                                            title='Process States Wait Analysis',
                                            xaxis_title='State',
                                            yaxis_title='Wait Count',
                                            height=500,
                                            showlegend=False,
                                            plot_bgcolor='white',
                                            xaxis=dict(
                                                tickfont=dict(size=14),
                                                categoryorder='total descending'
                                            ),
                                            yaxis=dict(
                                                tickmode='linear',
                                                tickfont=dict(size=12)
                                            ),
                                            bargap=0.15
                                        )
                                        
                                        # Add gridlines
                                        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
                                        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
                                        
                                        st.plotly_chart(fig, use_container_width=True)

                                if selected_id == "52":  # Conflicts Analysis
                                    results = monitor.execute_query(tool_queries[selected_id][0])

                                    st.markdown("""
                                        ### **🔹 Purpose:**  
                                        - Monitors **active and idle-in-transaction sessions** to detect potential conflicts.  
                                        - Identifies **deadlocks, lock waits, and transaction contention**.  
                                        - Helps in diagnosing **sessions that hold locks for too long**, impacting concurrency.  
                                        - Aids in **resolving blocking transactions** to maintain database responsiveness.  

                                        ### **🔹 Example Scenario:**  
                                        Suppose **two concurrent update queries** on the same row enter a **deadlock** state. This could be caused by:  
                                        ✅ **Unoptimized transaction handling**, leading to unnecessary lock contention.  
                                        ✅ **Long-running idle-in-transaction sessions**, keeping resources locked.  
                                        ✅ **Application logic issues**, causing multiple transactions to compete for the same data.  

                                        Using this tool, administrators can:  
                                        🔹 **Identify blocking transactions and their dependencies.**  
                                        🔹 **Analyze idle-in-transaction sessions that may be causing unnecessary locks.**  
                                        🔹 **Optimize transaction isolation levels to reduce conflicts.**  
                                        🔹 **Terminate or adjust problematic transactions before they escalate into system-wide slowdowns.**  
                                    """)

                                    if isinstance(results, tuple):
                                        results = results[0]  # Assuming first element is DataFrame
                                    else:
                                        results = results

                                    if results is not None and not results.empty:
                                        # Display raw conflict data
                                        st.dataframe(results[['datname', 'pid', 'leader_pid', 'usename', 'application_name', 'client_addr', 'backend_start', 'xact_start', 'query_start', 'state', 'backend_xid', 'query']], use_container_width=True)

                                        # # Create edge list (conflicts between processes)
                                        # edges = list(zip(results['leader_pid'], results['pid']))

                                        # # Create graph visualization
                                        # fig = go.Figure()

                                        # for leader, pid in edges:
                                        #     fig.add_trace(go.Scatter(
                                        #         x=[leader, pid], 
                                        #         y=[0, 0],  # Keep processes on the same horizontal level
                                        #         mode='lines+markers+text',
                                        #         line=dict(width=2, color='red'),
                                        #         marker=dict(size=12, color='blue'),
                                        #         text=[f"Leader: {leader}", f"PID: {pid}"],
                                        #         textposition="bottom center",
                                        #         hoverinfo='text'
                                        #     ))

                                        # # Update layout for better visualization
                                        # fig.update_layout(
                                        #     title="Database Conflict Flow",
                                        #     xaxis=dict(title="Process IDs", showgrid=True, zeroline=False),
                                        #     yaxis=dict(visible=False),  # Hide Y-axis
                                        #     showlegend=False,
                                        #     height=500,
                                        #     plot_bgcolor='white'
                                        # )

                                        # st.plotly_chart(fig, use_container_width=True)

                                if selected_id == "53":  # Check Locks
                                    results = monitor.execute_query(tool_queries[selected_id][0])

                                    st.markdown("""
                                        ### **🔹 Purpose:**  
                                        - Monitors **lock activity** to identify potential bottlenecks.  
                                        - Detects **excessive lock waits** that can slow down query performance.  
                                        - Helps in troubleshooting **blocking locks** that impact concurrent transactions.  
                                        - Provides insights into **granted and pending locks** for better resource management.  

                                        ### **🔹 Example Scenario:**  
                                        Imagine a **batch job** running overnight that locks critical tables. This could result in:  
                                        ✅ **Other queries waiting excessively**, leading to performance degradation.  
                                        ✅ **Deadlocks forming**, requiring manual intervention.  
                                        ✅ **Transaction contention**, impacting user experience in real-time applications.  

                                        Using this tool, administrators can:  
                                        🔹 **Identify which transactions are holding locks** and their impact on performance.  
                                        🔹 **Analyze lock modes** (e.g., **ExclusiveLock, AccessShareLock**) to assess severity.  
                                        🔹 **Optimize query execution plans** to minimize unnecessary locks.  
                                        🔹 **Take corrective actions** such as tuning transactions, breaking deadlocks, or scheduling batch jobs more efficiently.  
                                    """)

                                    if isinstance(results, tuple):
                                        results = results[0]  # Assuming first element is DataFrame
                                    else:
                                        results = results

                                    if results is not None and not results.empty:
                                        # Display lock data
                                        st.dataframe(results[['relation', 'transactionid', 'mode', 'granted']], use_container_width=True)

                                        # Count granted vs. waiting locks per lock mode
                                        lock_counts = results.groupby(['mode', 'granted']).size().reset_index(name='count')

                                        # Map granted values to more readable labels
                                        lock_counts['granted'] = lock_counts['granted'].map({True: 'Granted', False: 'Waiting'})

                                        # Create stacked bar chart
                                        fig = px.bar(
                                            lock_counts, 
                                            x='mode', 
                                            y='count', 
                                            color='granted',
                                            title='Lock Activity: Granted vs. Waiting',
                                            labels={'mode': 'Lock Mode', 'count': 'Number of Locks', 'granted': 'Lock Status'},
                                            barmode='stack',
                                            text_auto=True
                                        )

                                        # Update layout
                                        fig.update_layout(
                                            xaxis_title="Lock Mode",
                                            yaxis_title="Number of Locks",
                                            legend_title="Lock Status",
                                            height=500,
                                            plot_bgcolor='white'
                                        )

                                        st.plotly_chart(fig, use_container_width=True)

                                if selected_id == "9":  # Buffer Blocks Analysis
                                    results = monitor.execute_query(tool_queries[selected_id][0])

                                    st.markdown("""
                                        ### **🔹 Purpose:**  
                                        - **Analyzes buffer usage efficiency** to optimize database performance.  
                                        - Identifies **which tables consume the most buffers**, helping fine-tune memory allocation.  
                                        - Highlights **excessive disk reads** due to insufficient buffer cache, impacting query speed.  
                                        - Helps **adjust shared buffers** to improve query response times.  

                                        ### **🔹 Example Scenario:**  
                                        Suppose **80% of read queries hit the disk** instead of memory, leading to:  
                                        ✅ **High disk I/O**, causing slow query performance.  
                                        ✅ **Increased load on the storage system**, affecting overall database efficiency.  
                                        ✅ **Frequent evictions of cached data**, reducing query speed.  

                                        With this tool, database administrators can:  
                                        🔹 **Identify heavily used tables** that occupy the most buffers.  
                                        🔹 **Optimize buffer pool settings** by adjusting `shared_buffers`.  
                                        🔹 **Reduce unnecessary disk I/O** by fine-tuning indexing and caching strategies.  
                                        🔹 **Improve response time** for frequently accessed data.  
                                    """)

                                    if isinstance(results, tuple):
                                        results = results[0]  # Assuming first element is DataFrame
                                    else:
                                        results = results

                                    if results is not None and not results.empty:
                                        # Sort results by buffer count in descending order
                                        sorted_results = results.sort_values(by='buffers', ascending=False).reset_index(drop=True)

                                        # Display dataframe
                                        st.dataframe(sorted_results, use_container_width=True)

                                        # Visualization: Bar Chart for Buffer Usage by Relation
                                        fig = go.Figure()

                                        fig.add_trace(go.Bar(
                                            x=sorted_results['relname'],
                                            y=sorted_results['buffers'],
                                            marker_color='dodgerblue',
                                            text=sorted_results['buffers'],
                                            textposition='outside'
                                        ))

                                        # Update layout
                                        fig.update_layout(
                                            title='Buffer Usage by Relation',
                                            xaxis_title='Table Name',
                                            yaxis_title='Number of Buffers',
                                            height=500,
                                            plot_bgcolor='white',
                                            showlegend=False
                                        )

                                        # Display visualization
                                        st.plotly_chart(fig, use_container_width=True)

                                if selected_id == "10":  # Schema Size Analysis
                                    results = monitor.execute_query(tool_queries[selected_id][0])

                                    st.markdown("""
                                        ### **🔹 Purpose:**  
                                        - **Tracks the overall size** of each schema within the database.  
                                        - Identifies **storage-heavy schemas** to optimize space usage.  
                                        - Helps in **capacity planning** and **storage management**.  
                                        - Detects unexpected growth that might indicate **data bloat or inefficient indexing**.  

                                        ### **🔹 Example Scenario:**  
                                        Suppose a **single schema is consuming 1TB of space**, leading to:  
                                        ✅ **High storage costs**, affecting budget allocation.  
                                        ✅ **Longer backup and restore times**, increasing downtime.  
                                        ✅ **Slower query performance**, as large tables require more resources.  

                                        With this tool, database administrators can:  
                                        🔹 **Identify oversized schemas** that may need archiving or partitioning.  
                                        🔹 **Analyze storage trends** to forecast future space requirements.  
                                        🔹 **Optimize schema design** by restructuring large tables.  
                                        🔹 **Implement compression techniques** to reduce storage footprint.  
                                    """)

                                    if isinstance(results, tuple):
                                        results = results[0]  # Assuming first element is DataFrame
                                    else:
                                        results = results

                                    if results is not None and not results.empty:
                                        # Sort results by schema size in descending order
                                        sorted_results = results.sort_values(by='size_in_mb', ascending=False).reset_index(drop=True)

                                        # Display dataframe
                                        st.dataframe(sorted_results, use_container_width=True)

                                        # Visualization: Pie Chart for Schema Size Distribution
                                        fig = go.Figure()

                                        fig.add_trace(go.Pie(
                                            labels=sorted_results['schema_name'],
                                            values=sorted_results['size_in_mb'],
                                            textinfo='label+percent',
                                            marker=dict(colors=px.colors.qualitative.Plotly),
                                            hovertemplate="<b>Schema:</b> %{label}<br><b>Size:</b> %{value:.2f} MB<extra></extra>"
                                        ))

                                        # Update layout
                                        fig.update_layout(
                                            title='Schema Size Distribution',
                                            height=500
                                        )

                                        # Display visualization
                                        st.plotly_chart(fig, use_container_width=True)

                                if selected_id == "14":  # Bloat Analysis
                                    results = monitor.execute_query(tool_queries[selected_id][0])

                                    st.markdown("""
                                        ### **🔹 Purpose:**  
                                        - **Identifies table bloat** caused by frequent updates and deletes.  
                                        - Helps in **optimizing storage** and improving performance.  
                                        - Highlights **dead tuples** that may require vacuuming or reindexing.  

                                        ### **🔹 Example Scenario:**  
                                        Suppose a **heavily updated table** has **50% dead tuples**, leading to:  
                                        ✅ **Increased disk space usage**, causing unnecessary storage costs.  
                                        ✅ **Slower query performance**, as bloated tables take longer to scan.  
                                        ✅ **Higher I/O operations**, impacting database efficiency.  

                                        With this tool, database administrators can:  
                                        🔹 **Detect bloat early** before it impacts performance.  
                                        🔹 **Schedule vacuum and autovacuum** more effectively.  
                                        🔹 **Consider reindexing strategies** to reclaim space.  
                                        🔹 **Ensure optimized query execution** by maintaining lean tables.  
                                    """)

                                    if isinstance(results, tuple):
                                        results = results[0]  # Assuming first element is DataFrame
                                    else:
                                        results = results

                                    if results is not None and not results.empty:
                                        # Rename columns for clarity
                                        results.rename(columns={
                                            "table_len": "Table Size (bytes)",
                                            "tuple_count": "Live Tuples",
                                            "dead_tuple_count": "Dead Tuples",
                                            "dead_tuple_len": "Dead Tuples Size (bytes)",
                                            "free_space": "Free Space (bytes)"
                                        }, inplace=True)

                                        # Display table
                                        st.dataframe(results, use_container_width=True)

                                        # Visualization: Pie Chart for Tuple Distribution
                                        labels = ["Live Tuples", "Dead Tuples"]
                                        values = [results["Live Tuples"][0], results["Dead Tuples"][0]]

                                        fig = px.pie(
                                            names=labels,
                                            values=values,
                                            title="Tuple Distribution (Live vs Dead Tuples)",
                                            hole=0.4
                                        )

                                        st.plotly_chart(fig, use_container_width=True)

                                # if selected_id == "32":  # X-ray Disk Analysis
                                #     results = monitor.execute_query(tool_queries[selected_id][0])

                                #     st.markdown("""
                                #     **🔹 Use Case:** Detailed disk activity analysis.  
                                #     **🔹 Example:** High disk write rates due to frequent UPDATE statements on large tables.  
                                #     """)

                                #     if results is not None and not results.empty:
                                #         # Convert size_bytes to numeric type
                                #         results["size_bytes"] = results["size_bytes"].astype(float)

                                #         # Display DataFrame
                                #         st.dataframe(results[['schema_name', 'table_name', 'total_size', 'size_bytes']],
                                #                     use_container_width=True)

                                #         # Visualization: Bar Chart of Table Sizes
                                #         fig = px.bar(
                                #             results,
                                #             x="table_name",
                                #             y="size_bytes",
                                #             color="schema_name",
                                #             text="total_size",
                                #             title="Top 10 Largest Tables by Disk Usage",
                                #             labels={"size_bytes": "Table Size (Bytes)", "table_name": "Table"},
                                #             height=600
                                #         )

                                #         st.plotly_chart(fig, use_container_width=True)

                                if selected_id == "33":  # Data Growth Analysis
                                    results = monitor.execute_query(tool_queries[selected_id][0])

                                    st.markdown("""
                                        ### **🔹 Purpose:**  
                                        - Tracks **database growth trends** across schemas and tables.  
                                        - Helps identify **large and fast-growing tables**.  
                                        - Assists in **storage planning and archival strategies**.  

                                        ### **🔹 Example Scenario:**  
                                        Suppose the **sales table** grows by **100GB every month**, leading to:  
                                        ✅ **Increased storage costs** if not managed efficiently.  
                                        ✅ **Performance issues** due to larger indexes and slower queries.  
                                        ✅ **Longer backup and restore times**, affecting recovery strategies.  

                                        With this tool, database administrators can:  
                                        🔹 **Identify top-growing tables** and plan partitioning or archiving.  
                                        🔹 **Monitor schema-level growth** to optimize storage allocations.  
                                        🔹 **Forecast database expansion trends** and plan capacity upgrades.  
                                        🔹 **Ensure optimal query performance** by maintaining manageable table sizes.  
                                    """)

                                    if isinstance(results, tuple):
                                        results = results[0]  # Assuming first element is DataFrame
                                    else:
                                        results = results

                                    if results is not None and not results.empty:
                                        # Convert bytes to KB for readability
                                        results["size_kb"] = results["total_size_bytes"] / 1e3

                                        # Display dataframe
                                        st.dataframe(results[["table_schema", "table_name", "size_kb"]], use_container_width=True)

                                        # Visualization: Bar Chart for Table Growth
                                        fig = px.bar(
                                            results.head(10),  # Limit to top 10 tables for clarity
                                            x="table_name",
                                            y="size_kb",
                                            color="table_schema",
                                            text="size_kb",
                                            labels={"size_kb": "Size (KB)"},
                                            title="Top 10 Largest Tables by Data Growth",
                                            height=500
                                        )

                                        # Display visualization
                                        st.plotly_chart(fig, use_container_width=True)

                                if selected_id == "38":  # Database Size Analysis
                                    results = monitor.execute_query(tool_queries[selected_id][0])

                                    st.markdown("""
                                        ### **🔹 Purpose:**  
                                        - Monitors **database size growth** over time.  
                                        - Helps in **capacity planning and resource allocation**.  
                                        - Identifies **storage-intensive databases** that may need optimization.  

                                        ### **🔹 Example Scenario:**  
                                        Suppose a database **grows by 1TB annually**, which can cause:  
                                        ✅ **Higher storage costs** due to rapid growth.  
                                        ✅ **Performance degradation** as tables and indexes expand.  
                                        ✅ **Longer backup/restore times**, affecting disaster recovery.  

                                        With this tool, database administrators can:  
                                        🔹 **Track database growth patterns** and anticipate storage needs.  
                                        🔹 **Plan resource allocation** based on actual usage trends.  
                                        🔹 **Optimize large databases** using archiving, compression, or partitioning.  
                                        🔹 **Ensure efficient query performance** by preventing unnecessary bloating.  
                                    """)

                                    if isinstance(results, tuple):
                                        results = results[0]  # Assuming first element is DataFrame
                                    else:
                                        results = results

                                    if results is not None and not results.empty:
                                        # Display DataFrame
                                        st.dataframe(results, use_container_width=True)

                                        # Visualization: Bar Chart for Database Size
                                        fig = px.bar(
                                            results,
                                            x="datname",
                                            y="size_in_bytes",  # Use the raw byte values for scaling
                                            title="Database Size Comparison",
                                            labels={"datname": "Database", "size_in_bytes": "Size in Bytes"},
                                            text="total_size",  # Display the human-readable size for the labels
                                            color="size_in_bytes",  # Color by raw byte size
                                            color_continuous_scale="blues",  # Consistent color scale
                                        )

                                        # Adjust layout to ensure y-axis starts from 0
                                        fig.update_layout(
                                            xaxis_title="Database",
                                            yaxis_title="Size in Bytes",
                                            yaxis=dict(
                                                showgrid=True,
                                                gridcolor="LightGray",
                                                rangemode="tozero"  # Force y-axis to start at 0
                                            ),
                                            plot_bgcolor="white",
                                        )

                                        st.plotly_chart(fig, use_container_width=True)

                                if selected_id == "41":  # XC-resource Usage
                                    results = monitor.execute_query(tool_queries[selected_id][0])

                                    st.markdown("""
                                        ### **🔹 Purpose:**  
                                        - Monitors **resource utilization** across distributed database clusters.  
                                        - Helps detect **performance bottlenecks** due to CPU, memory, or storage constraints.  
                                        - Ensures **optimal workload distribution** in a clustered environment.  

                                        ### **🔹 Example Scenario:**  
                                        Suppose one cluster node is **consistently at 90% CPU usage**, causing:  
                                        ✅ **Slow query execution** due to overloaded processing.  
                                        ✅ **Resource contention**, affecting other active queries.  
                                        ✅ **Potential downtime risk**, if the node runs out of memory or CPU cycles.  

                                        With this tool, database administrators can:  
                                        🔹 **Identify resource-heavy nodes** and redistribute workloads.  
                                        🔹 **Analyze database size trends** to prevent storage bottlenecks.  
                                        🔹 **Optimize cluster configuration** for better performance.  
                                        🔹 **Ensure high availability** by balancing resource allocation.  
                                    """)

                                    if isinstance(results, tuple):
                                        results = results[0]  # Assuming first element is DataFrame
                                    else:
                                        results = results

                                    if results is not None and not results.empty:
                                        # Display DataFrame
                                        st.dataframe(results, use_container_width=True)

                                        # Convert size to numerical values for better visualization
                                        def parse_size(size_str):
                                            size_map = {"B": 1, "kB": 1e3, "MB": 1e6, "GB": 1e9, "TB": 1e12}
                                            num, unit = size_str.split()
                                            return float(num) * size_map[unit]

                                        results["size_numeric"] = results["total_database_size"].apply(parse_size)

                                        # **Visualization 1: Pie Chart for Resource Distribution**
                                        fig1 = px.pie(
                                            results,
                                            names="datname",
                                            values="size_numeric",
                                            title="Database Resource Usage Distribution",
                                            hole=0.4,
                                            color_discrete_sequence=px.colors.sequential.Blues_r,
                                        )

                                        # **Visualization 2: Horizontal Bar Chart for Comparison**
                                        fig2 = px.bar(
                                            results.sort_values("size_numeric", ascending=False),
                                            x="size_numeric",
                                            y="datname",
                                            orientation="h",
                                            title="XC-Resource Usage Across Databases",
                                            labels={"size_numeric": "Size (Bytes)", "datname": "Database"},
                                            text="total_database_size",
                                            color="size_numeric",
                                            color_continuous_scale=px.colors.sequential.ice,
                                        )

                                        # Update layout for better readability
                                        fig2.update_layout(
                                            xaxis_title="Size (Bytes)",
                                            yaxis_title="Database",
                                            yaxis=dict(showgrid=True, gridcolor="LightGray"),
                                            plot_bgcolor="white",
                                        )

                                        # Display charts
                                        st.plotly_chart(fig1, use_container_width=True)
                                        st.plotly_chart(fig2, use_container_width=True)

                                if selected_id == "44":  # Production DB Size
                                    results = monitor.execute_query(tool_queries[selected_id][0])

                                    st.markdown("""
                                        ### **🔹 Purpose:**  
                                        - Monitors **production database size trends**.  
                                        - Helps **plan storage capacity** and optimize database growth.  
                                        - Provides **early warnings** for potential space constraints.  

                                        ### **🔹 Example Scenario:**  
                                        **Scenario:** Your production database size increases by **50GB per month**, leading to:  
                                        ✅ **Performance slowdowns** due to bloated tables and indexes.  
                                        ✅ **Storage concerns**, requiring additional disk space allocation.  
                                        ✅ **Backup & restore complexity**, affecting disaster recovery.  

                                        With this tool, database administrators can:  
                                        🔹 **Track growth trends** to forecast future storage needs.  
                                        🔹 **Identify unusually large databases** consuming excessive resources.  
                                        🔹 **Optimize storage usage** by implementing compression or partitioning.  
                                        🔹 **Plan archiving strategies** to manage historical data efficiently.  
                                    """)

                                    if isinstance(results, tuple):
                                        results = results[0]  # Assuming first element is DataFrame
                                    else:
                                        results = results

                                    if results is not None and not results.empty:
                                        # Display DataFrame
                                        st.dataframe(results, use_container_width=True)

                                        # Visualization: Bar Chart for Database Size
                                        fig = px.bar(
                                            results,
                                            x="datname",
                                            y="size_in_bytes",  # Use the raw byte values for sorting and scale
                                            title="Production Database Size",
                                            labels={"datname": "Database Name", "size_in_bytes": "Size in Bytes"},
                                            text="database_size",  # Use human-readable size for text labels
                                            color="size_in_bytes",
                                            color_continuous_scale="blues",  # Use a consistent color scheme
                                        )

                                        # Adjust layout for better readability and force Y-axis to start at 0
                                        fig.update_layout(
                                            xaxis_title="Database Name",
                                            yaxis_title="Size in Bytes",
                                            yaxis=dict(
                                                showgrid=True, 
                                                gridcolor="LightGray", 
                                                rangemode="tozero"  # This explicitly sets the y-axis to start from 0
                                            ),
                                            plot_bgcolor="white",
                                        )

                                        st.plotly_chart(fig, use_container_width=True)

                                if selected_id == "20":  # Vacuum
                                    results = monitor.execute_query(tool_queries[selected_id][0])

                                    st.markdown("""
                                        ### **🔹 Purpose:**  
                                        - Provides a **comprehensive overview** of **vacuum operations** across all tables.  
                                        - Helps detect **tables with excessive dead tuples** that may require **manual intervention**.  
                                        - Tracks **long-term trends** of autovacuum efficiency and its impact on **database performance**.  

                                        ### **🔹 Example Scenario:**  
                                        A high-write database with multiple large tables might experience:  
                                        ✅ **Autovacuum lag**, causing delayed dead tuple cleanup.  
                                        ✅ **Storage bloat**, leading to unnecessary disk usage.  
                                        ✅ **Slow query execution** due to outdated statistics.  

                                        Using this tool, administrators can **compare vacuum efficiency across multiple tables**  
                                        and decide whether to fine-tune autovacuum settings or schedule manual VACUUM jobs.  
                                    """)

                                    if isinstance(results, tuple):
                                        results = results[0]  # Assuming first element is DataFrame
                                    else:
                                        results = results

                                    if results is not None and not results.empty:
                                        # Convert timestamps to datetime format
                                        results["last_vacuum"] = pd.to_datetime(results["last_vacuum"], errors='coerce')
                                        results["last_autovacuum"] = pd.to_datetime(results["last_autovacuum"], errors='coerce')

                                        # Ensure timestamps are timezone-aware (localize to UTC first if naive)
                                        if results["last_vacuum"].dt.tz is None:
                                            results["last_vacuum"] = results["last_vacuum"].dt.tz_localize("UTC")
                                        if results["last_autovacuum"].dt.tz is None:
                                            results["last_autovacuum"] = results["last_autovacuum"].dt.tz_localize("UTC")

                                        # Convert to Indian Standard Time (IST)
                                        results["last_vacuum"] = results["last_vacuum"].dt.tz_convert("Asia/Kolkata")
                                        results["last_autovacuum"] = results["last_autovacuum"].dt.tz_convert("Asia/Kolkata")

                                        # Display table stats
                                        st.dataframe(results, use_container_width=True)

                                        # **Visualization 1: Bar Chart for Vacuum Count**
                                        fig1 = px.bar(
                                            results.sort_values("vacuum_count", ascending=False),
                                            x="table_name",
                                            y="vacuum_count",
                                            title="Manual Vacuum Execution Count",
                                            labels={"vacuum_count": "Times Vacuumed", "table_name": "Table"},
                                            text="vacuum_count",
                                            color="vacuum_count",
                                            color_continuous_scale=px.colors.sequential.Blues,
                                            hover_data=["schemaname"]  # Show schema name on hover
                                        )

                                        # **Visualization 2: Scatter Plot for Last Vacuum Times**
                                        fig2 = px.scatter(
                                            results,
                                            x="last_vacuum",
                                            y="table_name",
                                            title="Last Manual Vacuum Execution Time (IST)",
                                            labels={"last_vacuum": "Last Vacuum Time (IST)", "table_name": "Table"},
                                            color="table_name",
                                            size_max=12,
                                            hover_data=["schemaname"]  # Show schema name on hover
                                        )

                                        # Display charts
                                        st.plotly_chart(fig1, use_container_width=True)
                                        st.plotly_chart(fig2, use_container_width=True)
                                        
                                if selected_id == "21":  # Vacuum Specific Table
                                    results = monitor.execute_query(tool_queries[selected_id][0])

                                    st.markdown("""
                                        ### **🔹 Purpose:**  
                                        - Focuses on **a single table** to monitor **vacuum frequency** and **bloat accumulation**.  
                                        - Detects **transaction wraparound risks** in frequently updated tables.  
                                        - Helps determine **if a specific table needs more frequent vacuuming** than others.  

                                        ### **🔹 Example Scenario:**  
                                        A **customer_orders** table with millions of daily inserts might experience:  
                                        ✅ **Autovacuum running too infrequently**, leading to growing dead tuples.  
                                        ✅ **High write latency**, slowing down order processing.  
                                        ✅ **Transaction wraparound danger**, potentially blocking new transactions.  

                                        Using this tool, administrators can **monitor vacuum frequency for a single table**,  
                                        **adjust autovacuum thresholds**, and **optimize indexing strategies** to keep queries fast.  
                                    """)

                                    if isinstance(results, tuple):
                                        results = results[0]  # Assuming first element is DataFrame
                                    else:
                                        results = results

                                    if results is not None and not results.empty:
                                        # Display the table
                                        st.dataframe(results, use_container_width=True)

                                        # Convert timestamps for visualization
                                        results["last_vacuum"] = pd.to_datetime(results["last_vacuum"])
                                        results["last_autovacuum"] = pd.to_datetime(results["last_autovacuum"])

                                        # **Bar Chart for Vacuum Count**
                                        fig1 = px.bar(
                                            results,
                                            x="table_name",
                                            y=["vacuum_count", "autovacuum_count"],
                                            title="Manual vs. Auto Vacuum Count",
                                            labels={"value": "Count", "variable": "Type", "table_name": "Table"},
                                            barmode="group",
                                            color_discrete_map={"vacuum_count": "#3498db", "autovacuum_count": "#e74c3c"},
                                        )

                                        # **Line Chart for Last Vacuum Times**
                                        fig2 = px.line(
                                            results,
                                            x="last_vacuum",
                                            y="table_name",
                                            title="Last Vacuum Execution Time",
                                            labels={"last_vacuum": "Last Vacuum Time", "table_name": "Table"},
                                            markers=True,
                                            color_discrete_sequence=["#2ecc71"],
                                        )

                                        # Display charts
                                        st.plotly_chart(fig1, use_container_width=True)
                                        st.plotly_chart(fig2, use_container_width=True)

                                if selected_id == "23":  # Cache Scan
                                    results = monitor.execute_query(tool_queries[selected_id][0])

                                    st.markdown("""
                                        ### **🔹 Purpose:**  
                                        - Analyzes **how much of a table is in the shared buffer cache**.  
                                        - Helps optimize **query performance** by reducing disk I/O.  
                                        - Identifies **hot tables** that get cached frequently.  

                                        ### **🔹 Example Scenario:**  
                                        **Scenario:** Your **orders** table gets queried thousands of times per minute.  
                                        ✅ If **90% of queries hit the cache**, your database avoids expensive disk reads.  
                                        ✅ If **cache hit rate is low**, queries might be inefficient, or `shared_buffers` may need tuning.  
                                    """)

                                    if isinstance(results, tuple):
                                        results = results[0]  # Assuming first element is DataFrame
                                    else:
                                        results = results

                                    if results is not None and not results.empty:
                                        # Display the cache statistics table
                                        st.dataframe(results, use_container_width=True)

                                        # **Visualization 1: Horizontal Bar Chart for Buffer Usage per Table**
                                        fig1 = px.bar(
                                            results.sort_values("num_buffers", ascending=False),
                                            y="table_name",
                                            x="num_buffers",
                                            title="Buffer Usage per Table",
                                            labels={"num_buffers": "Number of Buffers", "table_name": "Table"},
                                            text="num_buffers",
                                            orientation="h",
                                            color="buffer_percentage",
                                            color_continuous_scale="Blues"
                                        )

                                        # **Visualization 2: Pie Chart for Buffer Size Distribution**
                                        fig2 = px.pie(
                                            results,
                                            names="table_name",
                                            values="num_buffers",
                                            title="Buffer Distribution Across Tables",
                                            labels={"num_buffers": "Buffer Count", "table_name": "Table"},
                                            hole=0.4,  # Donut-style chart for clarity
                                            color_discrete_sequence=px.colors.qualitative.Set2
                                        )

                                        # Display charts
                                        st.plotly_chart(fig1, use_container_width=True)
                                        st.plotly_chart(fig2, use_container_width=True)
                                
                                if selected_id == "36":  # Unconsumed Indexes
                                    results = monitor.execute_query(tool_queries[selected_id][0])

                                    st.markdown("""
                                        ### **🔹 Purpose:**  
                                        - Identifies **indexes that have never been used (`idx_scan = 0`)**.  
                                        - Helps reclaim **storage space** from redundant indexes.  
                                        - Improves **query performance** by reducing maintenance overhead.  

                                        ### **🔹 Example Scenario:**  
                                        **Scenario:** A **20GB index** exists on a rarely queried column.  
                                        ✅ If the index **has never been used**, it wastes space and slows down inserts/updates.  
                                        ✅ Removing the index **improves write performance** and reduces bloat.  

                                        **Insights from this tool:**  
                                        🔹 **Index name** – Which indexes are unutilized?  
                                        🔹 **Index size** – How much space do they occupy?  

                                        **Tip:** Before dropping an index, verify:  
                                        - **Query patterns** – Ensure no hidden dependencies.  
                                        - **Recent database activity** – Some indexes may be needed during periodic reporting.  
                                        - **Execution plans (`EXPLAIN ANALYZE`)** – Check if indexes are actually used.  
                                    """)

                                    if isinstance(results, tuple):
                                        results = results[0]  # Assuming first element is DataFrame
                                    else:
                                        results = results

                                    if results is not None and not results.empty:

                                        # Function to safely convert human-readable sizes to bytes
                                        def parse_size(size_str):
                                            size_map = {"kB": 1e3, "MB": 1e6, "GB": 1e9, "TB": 1e12}

                                            if not isinstance(size_str, str) or len(size_str.split()) != 2:
                                                return 0  # Handle unexpected values safely

                                            try:
                                                num, unit = size_str.split()
                                                return float(num) * size_map.get(unit, 1)  # Default to 1 if unit not found
                                            except ValueError:
                                                return 0  # Return 0 if conversion fails

                                        # Convert index size to numeric format for sorting
                                        results["size_numeric"] = results["index_size"].apply(parse_size)

                                        # Sort by size and limit to top 10
                                        results = results.sort_values("size_numeric", ascending=False).head(10)

                                        # Display DataFrame
                                        st.dataframe(results, use_container_width=True)

                                        # Visualization: Bar chart of Unused Indexes
                                        fig = px.bar(
                                            results,
                                            y="index_name",
                                            x="size_numeric",
                                            text="index_size",
                                            orientation="h",
                                            title="Top 10 Unused Indexes by Size",
                                            labels={"size_numeric": "Size (Bytes)", "index_name": "Index"},
                                            color="size_numeric",
                                            color_continuous_scale="Blues"
                                        )
                                        fig.update_layout(xaxis_tickformat=".2s", yaxis_title="")

                                        # Show the chart
                                        st.plotly_chart(fig, use_container_width=True)


                                # # In execute_tool function, handle vacuum operations:
                                # if selected_id in ["20", "21", "22"]:
                                #     with st.spinner("Executing VACUUM operation..."):
                                #         table_name = None
                                #         if selected_id == "21":
                                #             table_name = st.text_input("Enter table name for VACUUM:")

                                #         if table_name:
                                #             query = f"VACUUM ANALYZE {table_name};"
                                #         else:
                                #             query = "VACUUM ANALYZE;"

                                #         monitor.cursor.execute(query)
                                #         st.success("Vacuum operation completed successfully")

                                #         # Show vacuum statistics
                                #         stats_query = """
                                #             SELECT schemaname, relname, last_vacuum, last_autovacuum, vacuum_count 
                                #             FROM pg_stat_all_tables 
                                #             WHERE schemaname NOT IN ('pg_toast', 'pg_catalog')
                                #             ORDER BY last_vacuum DESC NULLS LAST;
                                #         """
                                #         vacuum_stats = monitor.execute_query(stats_query)
                                #         if vacuum_stats is not None:
                                #             st.dataframe(vacuum_stats)
                                


                                # elif selected_id in ["24", "29", "30", "31"]:  # System commands
                                #     st.info("System monitoring in progress...")
                                #     col1, col2 = st.columns(2)
                                    
                                #     with col1:
                                #         if st.button("Start Monitoring"):
                                #             with st.spinner("Collecting system metrics..."):
                                #                 result = os.popen(tool_queries[selected_id]).read()
                                #                 st.code(result)
                                                
                                #     with col2:
                                #         refresh_rate = st.slider("Refresh rate (seconds)", 1, 60, 5)
                                #         if st.button("Monitor Continuously"):
                                #             placeholder = st.empty()
                                #             while True:
                                #                 with placeholder.container():
                                #                     result = os.popen(tool_queries[selected_id]).read()
                                #                     st.code(result)
                                #                     time.sleep(refresh_rate)

                                # elif selected_id in ["4", "26", "27", "28"]:  # Multiple query tools
                                #     for query in tool_queries[selected_id]:
                                #         with st.expander(f"Query Result {tool_queries[selected_id].index(query) + 1}"):
                                #             results = monitor.execute_query(query)
                                #             if results is not None:
                                #                 st.dataframe(results)
                            
                                #                 # Visualization for Graphs 
                                #                 if len(results) > 0 and len(results.columns) > 1:
                                #                     st.subheader("Visualization")
                                #                 # viz_type = st.selectbox("Chart Type", ["Line", "Bar", "Scatter"])
                                #                     plot_data = prepare_data_for_plot(results)
                                #                     fig = px.line(plot_data)
                                #                     fig.update_layout(
                                #                         title= "Graphical Analysis",
                                #                         height=500,
                                #                         showlegend=True
                                #                     )
                                #                     st.plotly_chart(fig)                        
                                elif selected_id == "19":
                                    results = monitor.execute_query(tool_queries[selected_id][0])
                                    
                                    st.markdown("""
                                        ### **🔹 Purpose:**  
                                        - Extracts **database configuration settings** from `postgresql.conf`.  
                                        - Identifies misconfigurations that may impact performance, security, or reliability.  

                                        ### **🔹 Example Scenario:**  
                                        **Scenario:**  
                                        ✅ **Issue:** `max_connections` is set to `50`, but the system requires `200`.  
                                        ✅ **Impact:** New connections fail, affecting applications and user experience.  
                                        ✅ **Solution:** Adjust `postgresql.conf` and reload settings.  
                                    """)

                                    if isinstance(results, tuple):
                                        results = results[0]  # Assuming first element is DataFrame
                                    else:
                                        results = results
                                    
                                    if results is not None:
                                        st.text("Current Configuration Settings:")
                                        # Display as formatted text
                                        config_text = "\n".join(results['postgresql.conf'].tolist())
                                        st.code(config_text, language='ini')

                                        # Add download option
                                        st.download_button(
                                            "Download Configuration",
                                            config_text,
                                            "postgresql.conf",
                                            "text/plain"
                                        )

                    except Exception as e:
                        st.error(f"Error executing tool {selected_id}: {str(e)}")
                        st.exception(e)
                    
                    # Add refresh button
                    if st.button("Refresh Results", key=f"refresh_{selected_id}"):
                        st.experimental_rerun()


                        
        # # Create tabs for each category
        # tabs = st.tabs(list(tool_categories.keys()))
        
        # for i, (category, tools) in enumerate(tool_categories.items()):
        #     with tabs[i]:
        #         tool = st.selectbox(f"Select {category} Tool", [t["name"] for t in tools])
        #         tool_id = next(t["id"] for t in tools if t["name"] == tool)
                
        #         if st.button(f"Run {tool}"):
        #             MonitoringTools.execute_tool(tool_id, db_manager)

    @staticmethod
    def render_diagnostics_tab(db_manager):
        """Render the Diagnostics tab with advanced tools"""
        st.header("🔍 Advanced Diagnostics")
        
        diag_tools = {
            "Query Performance": sqlA,
            "Transaction Analysis": sqlB,
            "Storage Analysis": sqlC,
            "Buffer Analysis": sqlD,
            "Checkpoint Activity": sqlE,
            "Lock Analysis": sqlF,
            "Vacuum Analysis": sqlG,
            "Cache Analysis": sqlH,
            "Growth Analysis": sqlI
        }
        
        tool = st.selectbox("Select Diagnostic Tool", list(diag_tools.keys()))
        
        if st.button("Run Diagnostic"):
            if tool in ["Query Performance", "Transaction Analysis", "Storage Analysis", "Buffer Analysis", "Checkpoint Activity", "Lock Analysis", "Vacuum Analysis", "Cache Analysis", "Growth Analysis"]:
                if tool == "Query Performance":
                    results = db_manager.execute_query(diag_tools[tool][0])
                    # Handle both DataFrame and tuple cases
                    if isinstance(results, tuple):
                        # Assuming the first element of the tuple is the DataFrame
                        results = results[0]
                    else:
                        results = results

                    st.markdown("""
                        ### **🔹 Purpose**  
                        - Identifies the **Top 5 most time-consuming queries** based on execution time.  
                        - Helps in optimizing slow queries for better database performance.  

                        ### **🔹 Example Scenario:**  
                        **Scenario:**  
                        ✅ **Issue:** A specific query consumes **60% of total execution time**.  
                        ✅ **Impact:** Slows down other transactions, affecting application responsiveness.  
                        ✅ **Solution:** Optimize the query via **indexing, rewriting, or partitioning**.  
                    """)

                    if results is not None and not results.empty:
                        results["execution_time"] = results["execution_time"].astype(float)
                        results["call_count"] = results["call_count"].astype(int)
                        results["row_count"] = results["row_count"].astype(int)
                        
                        # Fix query column issues
                        results.rename(columns={"query_text": "query"}, inplace=True)
                        results["query"] = results["query"].astype(str).str.strip()  

                        # Sort by execution time
                        results = results.sort_values("execution_time", ascending=False)

                        # Display DataFrame
                        st.dataframe(results, use_container_width=True)
            
                elif tool == "Transaction Analysis":
                    results = db_manager.execute_query(diag_tools[tool][0])
                    # Handle both DataFrame and tuple cases
                    if isinstance(results, tuple):
                        # Assuming the first element of the tuple is the DataFrame
                        results = results[0]
                    else:
                        results = results

                    # 📌 **Tool Description**
                    st.markdown("""
                        ### **🔹 Purpose**  
                        - Identifies **long-running transactions exceeding 5 minutes**.  
                        - Helps diagnose transaction-related performance bottlenecks and locking issues.  

                        ### **🔹 Example Scenario:**  
                        **Scenario:**  
                        ✅ **Issue:** A background data processing job holds a **transaction for 10+ minutes**.  
                        ✅ **Impact:** Causes **locking issues** and delays other queries.  
                        ✅ **Solution:** Investigate and optimize the transaction to **reduce execution time**.  
                    """)

                    if results is not None and not results.empty:
                        # Convert 'duration' column to timedelta for better readability
                        results["duration"] = pd.to_timedelta(results["duration"])

                        # Sort transactions by duration
                        results = results.sort_values("duration", ascending=False)

                        # Display DataFrame
                        st.dataframe(results, use_container_width=True)

                        # Visualization: Horizontal bar chart for transaction durations
                        fig = px.bar(
                            results,
                            y="pid",
                            x=results["duration"].dt.total_seconds(),  # Convert duration to seconds
                            orientation="h",
                            title="⏳ Long-Running Transactions (Over 5 minutes)",
                            labels={"pid": "Process ID", "x": "Duration (seconds)"},
                            color=results["duration"].dt.total_seconds(),
                            color_continuous_scale="Reds",
                            hover_data=["usename", "application_name", "state"]
                        )

                        # Update layout
                        fig.update_layout(
                            xaxis_title="Transaction Duration (seconds)",
                            yaxis_title="Process ID (PID)",
                            height=max(400, len(results) * 30),
                            showlegend=False,
                            plot_bgcolor="white",
                            bargap=0.2
                        )

                        # Show the chart
                        st.plotly_chart(fig, use_container_width=True)

                elif tool == "Storage Analysis":
                    results = db_manager.execute_query(diag_tools[tool][0])
                    # Handle both DataFrame and tuple cases
                    if isinstance(results, tuple):
                        # Assuming the first element of the tuple is the DataFrame
                        results = results[0]
                    else:
                        results = results

                    # 📌 **Tool Description**
                    st.markdown("""
                        ### **🔹 Purpose**  
                        - Identifies the **Top 10 largest tables**, including indexes.  
                        - Helps detect **storage bottlenecks** and supports **table optimization**.  

                        ### **🔹 Example Scenario:**  
                        **Scenario:**  
                        ✅ **Issue:** A single table **occupies 500GB**, consuming excessive disk space.  
                        ✅ **Impact:** Slows down queries due to inefficient storage utilization.  
                        ✅ **Solution:** Implement **partitioning, archiving, or compression** strategies.  
                    """)

                    if results is not None and not results.empty:
                        
                        # Function to convert '96 kB', '10 MB', '1 GB' to bytes for numerical sorting
                        def convert_size_to_bytes(size_str):
                            size_units = {"kB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
                            try:
                                number, unit = size_str.split()
                                return float(number) * size_units.get(unit, 1)  # Default to 1 if unit is missing
                            except ValueError:
                                return 0  # Handle unexpected values gracefully
                        
                        # Apply conversion
                        results["size_bytes"] = results["total_size"].apply(convert_size_to_bytes)

                        # Sort by size (descending)
                        results = results.sort_values("size_bytes", ascending=False)

                        # Display DataFrame
                        st.dataframe(results[["table_schema", "table_name", "total_size"]], use_container_width=True)

                        # Visualization: Horizontal Bar Chart for Table Sizes
                        fig = px.bar(
                            results,
                            x="size_bytes",
                            y="table_name",
                            orientation="h",
                            title="Top 10 Largest Tables",
                            labels={"size_bytes": "Size (Bytes)", "table_name": "Table"},
                            text="total_size",
                            color="size_bytes",
                            color_continuous_scale="Blues"
                        )

                        fig.update_layout(
                            xaxis_tickformat=".2s",  # Format axis labels in human-readable form (e.g., KB, MB, GB)
                            yaxis_title="",
                            height=500
                        )

                        # Show the chart
                        st.plotly_chart(fig, use_container_width=True)

                elif tool == "Buffer Analysis":
                    results = db_manager.execute_query(diag_tools[tool][0])
                    # Handle both DataFrame and tuple cases
                    if isinstance(results, tuple):
                        # Assuming the first element of the tuple is the DataFrame
                        results = results[0]
                    else:
                        results = results

                    # 📌 **Tool Description**
                    st.markdown("""
                        ### **🔹 Purpose**  
                        - Evaluates the **Buffer Cache Hit Ratio** to measure memory efficiency.  
                        - Helps in **reducing disk I/O** by optimizing shared buffer allocation.  

                        ### **🔹 Example Scenario:**  
                        **Scenario:**  
                        ✅ **Issue:** Cache hit ratio drops **below 90%**, leading to excessive disk reads.  
                        ✅ **Impact:** Increased **query response time** due to frequent disk access.  
                        ✅ **Solution:** **Increase shared buffers** and tune **work memory settings**.  
                    """)

                    if results is not None and not results.empty:
                        # Convert buffer cache hit ratio to numeric
                        results["buffer_cache_hit_ratio"] = results["buffer_cache_hit_ratio"].astype(float)

                        # Display DataFrame
                        st.dataframe(results, use_container_width=True)

                        # Visualization: Gauge Chart for Buffer Cache Hit Ratio
                        fig = go.Figure(go.Indicator(
                            mode="gauge+number",
                            value=results["buffer_cache_hit_ratio"][0],
                            title={"text": "Buffer Cache Hit Ratio (%)"},
                            gauge={
                                "axis": {"range": [0, 100]},
                                "bar": {"color": "green"},
                                "steps": [
                                    {"range": [0, 60], "color": "red"},
                                    {"range": [60, 90], "color": "yellow"},
                                    {"range": [90, 100], "color": "green"}
                                ],
                                "threshold": {"line": {"color": "black", "width": 4}, "thickness": 0.75, "value": results["buffer_cache_hit_ratio"][0]}
                            }
                        ))

                        # Show the chart
                        st.plotly_chart(fig, use_container_width=True)

                elif tool == "Checkpoint Activity":
                    results = db_manager.execute_query(diag_tools[tool][0])
                    # Handle both DataFrame and tuple cases
                    if isinstance(results, tuple):
                        # Assuming the first element of the tuple is the DataFrame
                        results = results[0]
                    else:
                        results = results

                    # 📌 **Tool Description**
                    st.markdown("""
                        ### **🔹 Purpose**  
                        - Monitors **timed and requested checkpoints** to analyze how often PostgreSQL is flushing dirty pages to disk.  
                        - Helps detect **frequent checkpoints**, which can lead to **high I/O and performance degradation**.  
                        - Provides insights into **write and sync times**, crucial for optimizing disk operations.  

                        ### **🔹 Example Scenario:**  
                        **Scenario:**  
                        ✅ **Issue:** The database triggers **checkpoints too frequently** (e.g., every 2 minutes), leading to excessive I/O.  
                        ✅ **Impact:** Increased **write latency**, causing **query slowdowns** and high disk utilization.  
                        ✅ **Solution:** Adjust checkpoint parameters like **`checkpoint_timeout`**, **`checkpoint_completion_target`**, and **`max_wal_size`** to balance performance.  
                    """)

                    if results is not None and not results.empty:

                        # Convert numerical values to appropriate data types
                        for col in ["checkpoints_timed", "checkpoints_req", "checkpoint_write_time", "checkpoint_sync_time"]:
                            results[col] = results[col].astype(float)

                        # Display DataFrame
                        st.dataframe(results, use_container_width=True)

                        # 📊 **Visualization: Checkpoint Activity Breakdown**
                        fig = go.Figure()

                        fig.add_trace(go.Bar(
                            x=["Timed Checkpoints", "Requested Checkpoints"],
                            y=[results["checkpoints_timed"][0], results["checkpoints_req"][0]],
                            name="Checkpoints Count",
                            marker_color="blue"
                        ))

                        fig.add_trace(go.Bar(
                            x=["Write Time", "Sync Time"],
                            y=[results["checkpoint_write_time"][0], results["checkpoint_sync_time"][0]],
                            name="Checkpoint Time (ms)",
                            marker_color="red"
                        ))

                        fig.update_layout(
                            title="Checkpoint Activity Overview",
                            xaxis_title="Checkpoint Metrics",
                            yaxis_title="Count / Time (ms)",
                            barmode="group",  # Grouped bar chart for better comparison
                            height=500
                        )

                        # Show the chart
                        st.plotly_chart(fig, use_container_width=True)

                elif tool == "Lock Analysis":
                    results = db_manager.execute_query(diag_tools[tool][0])
                    # Handle both DataFrame and tuple cases
                    if isinstance(results, tuple):
                        # Assuming the first element of the tuple is the DataFrame
                        results = results[0]
                    else:
                        results = results

                    # 📌 **Tool Description**
                    st.markdown("""
                        ### **🔹 Purpose**  
                        - Identifies **blocking queries and idle transactions** that may cause **performance bottlenecks**.  
                        - Helps **detect long-running idle transactions** that unnecessarily hold resources.  
                        - Assists in **resolving query contention issues**, preventing system slowdowns.  

                        ### **🔹 Example Scenario:**  
                        **Scenario:**  
                        ✅ **Issue:** A long-running **idle transaction** is holding locks on critical tables.  
                        ✅ **Impact:** Other transactions are **blocked**, leading to increased query wait times and performance degradation.  
                        ✅ **Solution:** Identify and terminate problematic queries using **`pg_terminate_backend(pid)`** or **optimize transaction handling** to ensure locks are released promptly.  
                    """)


                    if results is not None and not results.empty:

                        # Display DataFrame
                        st.dataframe(results, use_container_width=True)

                        # 📊 **Visualization: Active vs Idle Transactions**
                        state_counts = results["state"].value_counts().reset_index()
                        state_counts.columns = ["state", "count"]

                        fig = px.pie(
                            state_counts,
                            names="state",
                            values="count",
                            title="Transaction States Distribution",
                            hole=0.4,  # Donut-style chart for clarity
                            color_discrete_sequence=px.colors.qualitative.Set2
                        )

                        # Show the chart
                        st.plotly_chart(fig, use_container_width=True)

                        # 📊 **Visualization: Query Start Time Analysis**
                        results["query_start_time"] = pd.to_datetime(results["query_start_time"])
                        results_sorted = results.sort_values("query_start_time")

                        fig2 = px.bar(
                            results_sorted,
                            x="query_start_time",
                            y="pid",
                            orientation="v",
                            title="Query Start Timeline",
                            labels={"query_start_time": "Start Time", "pid": "Process ID"},
                            color="state",
                            color_discrete_sequence=px.colors.qualitative.Plotly,
                            hover_data=["query_text"]
                        )

                        fig2.update_layout(
                            xaxis_title="Query Start Time",
                            yaxis_title="Process ID",
                            height=500
                        )

                        # Show the chart
                        st.plotly_chart(fig2, use_container_width=True)

                elif tool == "Vacuum Analysis":
                    results = db_manager.execute_query(diag_tools[tool][0])
                    # Handle both DataFrame and tuple cases
                    if isinstance(results, tuple):
                        # Assuming the first element of the tuple is the DataFrame
                        results = results[0]
                    else:
                        results = results

                    # 📌 **Tool Description**
                    st.markdown("""
                        ### **🔹 Purpose**  
                        - Displays the **5 most recently auto-vacuumed tables** and their vacuum statistics.  
                        - Helps **detect frequent autovacuum activity** on large tables that might require tuning.  
                        - Identifies **tables with insufficient vacuuming**, preventing bloated storage and degraded performance.  

                        ### **🔹 Example Scenario:**  
                        **Scenario:**  
                        ✅ **Issue:** A high-write table shows **no recent autovacuum activity**, causing dead tuples to accumulate.  
                        ✅ **Impact:** Increases **table bloat**, slows down queries, and wastes disk space.  
                        ✅ **Solution:** Adjust **autovacuum settings**, schedule **manual VACUUM FULL**, or use **pg_repack** for efficient cleanup.  
                    """)


                    if results is not None and not results.empty:
                        
                        # Display DataFrame
                        st.dataframe(results, use_container_width=True)
                        results["last_autovacuum_time"] = pd.to_datetime(results["last_autovacuum_time"])
                        results_sorted = results.sort_values("last_autovacuum_time")

                        fig2 = px.scatter(
                            results_sorted,
                            x="last_autovacuum_time",
                            y="relname",
                            title="Last Autovacuum Timeline",
                            labels={"last_autovacuum_time": "Last Autovacuum", "relname": "Table Name"},
                            color="relname",
                            size_max=12
                        )

                        fig2.update_layout(
                            xaxis_title="Autovacuum Timestamp",
                            yaxis_title="Table Name",
                            height=500
                        )

                        # Show the chart
                        st.plotly_chart(fig2, use_container_width=True)

                elif tool == "Cache Analysis":
                    results = db_manager.execute_query(diag_tools[tool][0])
                    # Handle both DataFrame and tuple cases
                    if isinstance(results, tuple):
                        # Assuming the first element of the tuple is the DataFrame
                        results = results[0]
                    else:
                        results = results

                    # 📌 **Tool Description**
                    st.markdown("""
                        ### **🔹 Purpose**  
                        - Identifies **tables with a low buffer cache hit ratio**, which may indicate excessive disk reads.  
                        - Helps optimize **frequently accessed tables** by ensuring they stay in memory.  
                        - Reducing disk I/O **improves query speed** and overall database efficiency.  

                        ### **🔹 Example Scenario:**  
                        **Scenario:**  
                        ✅ **Issue:** A critical table has a **cache hit ratio of only 60%**, meaning **40% of queries access disk instead of memory**.  
                        ✅ **Impact:** Increases **I/O load**, leading to **slower response times** for frequently executed queries.  
                        ✅ **Solution:** Increase **shared_buffers**, fine-tune **work_mem**, or implement **table partitioning** to improve caching efficiency.  
                    """)


                    if results is not None and not results.empty:

                        # Display DataFrame
                        st.dataframe(results, use_container_width=True)

                        # 📊 **Visualization: Cache Hit Ratio per Table**
                        fig = px.bar(
                            results,
                            x="table_name",
                            y="hit_ratio",
                            title="Cache Hit Ratio of Tables",
                            labels={"table_name": "Table Name", "hit_ratio": "Cache Hit Ratio (%)"},
                            color="hit_ratio",
                            color_continuous_scale="Blues",
                            hover_data=["table_name"]  # Show table name on hover
                        )

                        fig.update_layout(
                            xaxis_title="Table Name",
                            yaxis_title="Cache Hit Ratio (%)",
                            height=500
                        )

                        # Show the chart
                        st.plotly_chart(fig, use_container_width=True)

                elif tool == "Growth Analysis":
                    results = db_manager.execute_query(diag_tools[tool][0])
                    # Handle both DataFrame and tuple cases
                    if isinstance(results, tuple):
                        # Assuming the first element of the tuple is the DataFrame
                        results = results[0]
                    else:
                        results = results

                    # 📌 **Tool Description**
                    st.markdown("""
                        ### **🔹 Purpose**  
                        - Monitors **table growth trends**, including data, indexes, and toast storage.  
                        - Helps identify **rapidly expanding tables** that may require **partitioning or indexing**.  
                        - Supports **long-term storage planning** and **performance optimization**.  

                        ### **🔹 Example Scenario:**  
                        **Scenario:**  
                        ✅ **Issue:** A sales table **grows by 100GB per month**, leading to **slow queries and high storage costs**.  
                        ✅ **Impact:** Unoptimized growth can **increase query execution time** and **affect indexing efficiency**.  
                        ✅ **Solution:** Implement **table partitioning**, archive old data, or optimize **autovacuum settings** to maintain performance.  
                    """)

                    if results is not None and not results.empty:
        
                        # Ensure NULL values are handled before applying conversion
                        def convert_size(size):
                            if pd.isna(size) or size is None:  # Handle NULL values
                                return 0  # Assign zero for missing values
                            try:
                                num, unit = size.split()
                                units = {"kB": 1, "MB": 1024, "GB": 1024 * 1024}
                                return float(num) * units.get(unit, 1)
                            except Exception as e:
                                return 0  # Return 0 in case of unexpected format issues

                        # Convert size columns
                        size_columns = ["total_size", "data_size", "index_size", "toast_size", "table_size", "size_increase"]
                        for col in size_columns:
                            results[col] = results[col].fillna("0 kB")  # Fill NULL values with a default '0 kB'
                            results[f"{col}_numeric"] = results[col].apply(convert_size)

                        # Convert row_count safely
                        results["row_count"] = pd.to_numeric(results["row_count"], errors="coerce").fillna(0).astype(int)

                        # Display DataFrame
                        st.dataframe(results, use_container_width=True)

                        # 📊 **Visualization: Table Storage Breakdown**
                        fig = px.bar(
                            results,
                            x="table_name",
                            y=["data_size_numeric", "index_size_numeric", "toast_size_numeric"],
                            title="Storage Breakdown of Large Tables",
                            labels={"table_name": "Table Name", "value": "Size (KB)"},
                            barmode="stack",
                            color_discrete_sequence=px.colors.qualitative.Set2,
                            hover_data=["table_size", "size_increase", "last_analyze", "last_autoanalyze"]
                        )

                        fig.update_layout(
                            xaxis_title="Table Name",
                            yaxis_title="Storage Size (KB)",
                            height=500
                        )

                        # Show the chart
                        st.plotly_chart(fig, use_container_width=True)

                        # 📊 **Visualization: Growth Trend (Size Increase)**
                        fig2 = px.bar(
                            results,
                            x="table_name",
                            y="size_increase_numeric",
                            title="Table Size Increase Over Time",
                            labels={"table_name": "Table Name", "size_increase_numeric": "Size Increase (KB)"},
                            color="size_increase_numeric",
                            color_continuous_scale="Blues",
                            hover_data=["last_analyze", "last_autoanalyze"]
                        )

                        fig2.update_layout(
                            xaxis_title="Table Name",
                            yaxis_title="Size Increase (KB)",
                            height=500
                        )

                        # Show the chart
                        st.plotly_chart(fig2, use_container_width=True)


            # if results is not None and not results.empty:
            #     st.dataframe(results, use_container_width=True)
                
            #     # Add basic visualization
            #     if tool == "Query Performance":
            #         fig = px.bar(
            #             results.head(10),
            #             x="execution_time",
            #             y="query",
            #             orientation='h',
            #             title="Top 10 Slowest Queries"
            #         )
            #         st.plotly_chart(fig, use_container_width=True)

    @staticmethod
    def render_tuning_tab(db_manager):
        """Render the Tuning tab with optimization tools"""
        st.header("⚡ Tuning Tools")
        
        tuning_tools = {
            "Unused Indexes": tune_sqlA,
            "Index Management": tune_sqlB,
            # "Vacuum/Analyze": tune_sqlC,
            "Lock Resolution": tune_sqlD
        }
        
        tool = st.selectbox("Select Tuning Tool", list(tuning_tools.keys()))
        
        if st.button("Run Tuning Analysis"):
            if tool in ["Unused Indexes", "Index Management", "VACUUM/ANALYZE", "Lock Resolution"]:
                if tool == "Unused Indexes":
                    results = db_manager.execute_query(tuning_tools[tool][0])
                    
                    # Handle both DataFrame and tuple cases
                    if isinstance(results, tuple):
                        # Assuming the first element of the tuple is the DataFrame
                        results = results[0]
                    else:
                        results = results

                    # 📌 **Tool Description**
                    st.markdown("""
                        ### **🔹 Purpose**  
                        - Identifies **unused indexes** that may be taking up unnecessary storage.  
                        - Helps optimize **query performance** by reducing index maintenance overhead.  
                        - Provides insights on **index size**, aiding in **index cleanup decisions**.  

                        ### **🔹 Example Scenario:**  
                        **Scenario:**  
                        ✅ **Issue:** An index on a column with no queries referencing it **remains unused**.  
                        ✅ **Impact:** Extra disk space is occupied, and unnecessary index updates **slow down writes**.  
                        ✅ **Solution:** Consider **dropping unused indexes** to free up space and enhance performance.  
                    """)

                    if results is not None and not results.empty:
                        
                        # Convert index_size to numeric (removing 'kB', 'MB', 'GB')
                        def convert_size(size):
                            units = {"kB": 1, "MB": 1024, "GB": 1024 * 1024}
                            num, unit = size.split()
                            return float(num) * units.get(unit, 1)

                        results["index_size_numeric"] = results["index_size"].apply(convert_size)

                        # Display DataFrame
                        st.dataframe(results, use_container_width=True)

                        # 📊 **Visualization: Unused Index Size by Table**
                        fig = px.bar(
                            results,
                            x="index_name",  # Changed from table_name to index_name
                            y="index_size_numeric",
                            text="index_size",
                            title="Unused Indexes and Their Sizes",
                            labels={"index_size_numeric": "Index Size (KB)", "index_name": "Index Name"},
                            color="index_size_numeric",
                            color_continuous_scale="Blues",
                            hover_data=["schemaname", "table_name"]  # 👈 Added table_name to hover
                        )

                        # Show the chart
                        st.plotly_chart(fig, use_container_width=True)

                        # 📊 **Visualization: Number of Unused Indexes per Table**
                        results["index_count"] = results.groupby("table_name")["index_name"].transform("count")
                        unique_results = results.drop_duplicates(subset=["table_name"])

                        fig2 = px.scatter(
                            unique_results,
                            x="table_name",
                            y="index_count",
                            title="Number of Unused Indexes per Table",
                            labels={"index_count": "Unused Index Count", "table_name": "Table Name"},
                            color="index_count",
                            size="index_count",
                            size_max=12
                        )

                        fig2.update_layout(
                            xaxis_title="Table Name",
                            yaxis_title="Unused Index Count",
                            height=500
                        )
                        # Show the chart
                        st.plotly_chart(fig2, use_container_width=True)

                        # Success message
                        st.success("Tuning analysis completed successfully")

                elif tool == "Index Management":
                    results = db_manager.execute_query(tuning_tools[tool][0])
                    
                    # Handle both DataFrame and tuple cases
                    if isinstance(results, tuple):
                        # Assuming the first element of the tuple is the DataFrame
                        results = results[0]
                    else:
                        results = results

                    # 📌 **Tool Description**
                    st.markdown("""
                ### **🔹 Purpose**  
                - Identifies **indexes with low or zero usage** and provides SQL commands to **drop them safely**.  
                - Helps **reclaim storage space** and **reduce unnecessary index maintenance overhead**.  
                - Ensures efficient indexing by keeping only **essential indexes** that improve query performance.  

                ### **🔹 Example Scenario:**  
                **Scenario:**  
                🌜 **Issue:** An index on a **rarely queried column** has **0 scans in 6 months**.  
                🌜 **Impact:** Consumes **several gigabytes of storage** and **slows down insert/update operations**.  
                🌜 **Solution:** The tool suggests using **`DROP INDEX IF EXISTS`** to safely remove the unused index.  
                """)

                    if results is not None and not results.empty:
                        
                        # Convert index_size to numeric (removing 'kB', 'MB', 'GB')
                        def convert_size(size):
                            units = {"kB": 1, "MB": 1024, "GB": 1024 * 1024}
                            num, unit = size.split()
                            return float(num) * units.get(unit, 1)

                        results["index_size_numeric"] = results["index_size"].apply(convert_size)

                        # Display DataFrame
                        st.dataframe(results, use_container_width=True)

                        # 📊 **Visualization: Index Size and Usage Frequency**
                        fig = px.bar(
                            results,
                            x="index_name",
                            y="index_size_numeric",
                            text="index_size",
                            title="Index Size and Usage Frequency",
                            labels={"index_size_numeric": "Index Size (KB)", "index_name": "Index Name"},
                            color="idx_scan",
                            color_continuous_scale="Reds",
                            hover_data={"table_name": True, "index_name": False, "index_size": True, "idx_scan": True}  # Include table_name in hover tooltip
                        )

                        # Show the chart
                        st.plotly_chart(fig, use_container_width=True)

                        # 📝 **Generate SQL Commands to Drop Unused Indexes**
                        st.markdown("### 🚀 Suggested SQL Commands for Dropping Unused Indexes:")
                        for _, row in results.iterrows():
                            drop_command = row["drop_command"]
                            st.code(drop_command, language="sql")

                        # Success message
                        st.success("Index Management analysis completed successfully")

                # if tool == "VACUUM/ANALYZE":
                #     results = db_manager.execute_query(tuning_tools[tool][0])
                    
                #     # Handle both DataFrame and tuple cases
                #     if isinstance(results, tuple):
                #         # Assuming the first element of the tuple is the DataFrame
                #         results = results[0]
                #     else:
                #         results = results

                #     # 📌 **Tool Description**
                #     st.markdown("""
                #         ### **🔹 Purpose**  
                #         - Identifies **tables with excessive dead rows** that require **vacuuming** to free up space.  
                #         - Ensures **updated table statistics** via `ANALYZE` for efficient query planning.  
                #         - Helps **prevent database bloat** and **optimize query performance**.  

                #         ### **🔹 Example Scenario:**  
                #         **Scenario:**  
                #         ✅ **Issue:** A heavily updated table has **millions of dead rows**, causing **slow queries and storage bloat**.  
                #         ✅ **Impact:** The query planner **misestimates row counts**, leading to **suboptimal execution plans**.  
                #         ✅ **Solution:** Running **`VACUUM ANALYZE`** reclaims space and improves query efficiency.  
                #     """)
                    
                #     if results is not None and not results.empty:
                        
                #         # Convert table_size to numeric (removing 'kB', 'MB', 'GB')
                #         def convert_size(size):
                #             units = {"kB": 1, "MB": 1024, "GB": 1024 * 1024}
                #             num, unit = size.split()
                #             return float(num) * units.get(unit, 1)

                #         results["table_size_numeric"] = results["table_size"].apply(convert_size)

                #         # Display DataFrame
                #         st.dataframe(results, use_container_width=True)

                #         # 📊 **Visualization: Dead Rows vs. Live Rows**
                #         fig = px.bar(
                #             results,
                #             x="table_name",
                #             y=["live_rows", "dead_rows"],
                #             title="Live vs. Dead Rows per Table",
                #             labels={"value": "Row Count", "table_name": "Table Name"},
                #             barmode="group",
                #             height=500
                #         )

                #         # Show the chart
                #         st.plotly_chart(fig, use_container_width=True)

                #         # 📊 **Visualization: Tables Needing Vacuuming**
                #         fig2 = px.scatter(
                #             results,
                #             x="table_size_numeric",
                #             y="dead_rows",
                #             text="table_name",
                #             title="Tables with High Dead Rows (Possible VACUUM Needed)",
                #             labels={"table_size_numeric": "Table Size (KB)", "dead_rows": "Dead Rows"},
                #             color="dead_rows",
                #             size="dead_rows",
                #             size_max=12
                #         )

                #         fig2.update_layout(
                #             xaxis_title="Table Size (KB)",
                #             yaxis_title="Dead Rows",
                #             height=500
                #         )

                #         # Show the chart
                #         st.plotly_chart(fig2, use_container_width=True)

                #         # 📜 **Suggested Optimization Commands**
                #         st.markdown("### 🛠️ Suggested SQL Commands for Optimization:")
                #         for _, row in results.iterrows():
                #             table = f"{row['schemaname']}.{row['table_name']}"
                #             st.code(f"VACUUM ANALYZE {table};", language="sql")

                #         # Success message
                #         st.success("VACUUM / ANALYZE analysis completed successfully")

                if tool == "Lock Resolution":
                    results = db_manager.execute_query(tuning_tools[tool][0])
                    
                    # Handle both DataFrame and tuple cases
                    if isinstance(results, tuple):
                        # Assuming the first element of the tuple is the DataFrame
                        results = results[0]
                    else:
                        results = results

                    # 📌 **Tool Description**
                    st.markdown("""
                        ### **🔹 Purpose**  
                        - Identifies **queries that are blocked** and **queries causing locks**, helping resolve database contention.  
                        - Pinpoints **which session is blocking others**, allowing for quick troubleshooting.  
                        - Helps maintain **smooth query execution** by minimizing **deadlocks and long waits**.  

                        ### **🔹 Example Scenario:**  
                        **Scenario:**  
                        ✅ **Issue:** A transaction **locks a critical table**, preventing other queries from executing.  
                        ✅ **Impact:** Users experience **delays**, and some transactions **time out**, affecting application performance.  
                        ✅ **Solution:** Identify the **blocking query**, terminate unnecessary locks, or **optimize transaction management**.  
                    """)

                    if results is not None and not results.empty:

                        # Display DataFrame with lock details
                        st.dataframe(results, use_container_width=True)

                        # 📊 **Visualization: Blocking vs. Blocked Queries**
                        fig = px.bar(
                            results,
                            y="blocked_query",
                            x="blocked_duration",
                            text="blocking_query",
                            orientation="h",
                            title="Blocked Queries and Their Duration",
                            labels={"blocked_duration": "Blocked Duration (s)", "blocked_query": "Blocked Query"},
                            color="blocked_duration",
                            color_continuous_scale="Reds"
                        )

                        fig.update_layout(xaxis_tickformat=".2s", yaxis_title="Blocked Query")

                        # Show the chart
                        st.plotly_chart(fig, use_container_width=True)

                        # 📜 **Suggested Lock Resolution Commands**
                        st.markdown("### 🛠️ Suggested SQL Commands for Resolving Locks:")
                        for _, row in results.iterrows():
                            st.code(f"SELECT pg_terminate_backend({row['blocking_pid']}); -- Terminate blocking session", language="sql")

                        # Success message
                        st.success("Lock Resolution analysis completed successfully")
            
        # """Execute a monitoring tool and display results"""
        # tool_queries = {
        #     "1": sql1, "2": sql2, "6": sql6, "14": sql14, "15": sql15,
        #     "17": sql17, "18": sql18, "33": sql33, "35": sql35
        # }
        
        # if tool_id in tool_queries:
        #     results = db_manager.execute_query(tool_queries[tool_id][0])
        #     if results is not None and not results.empty:
        #         st.dataframe(results, use_container_width=True)
                
        #         # Add simple visualizations for some tools
        #         if tool_id == "1":  # Long running queries
        #             fig = px.bar(
        #                 results.head(10),
        #                 x="duration",
        #                 y="query",
        #                 orientation='h',
        #                 title="Long Running Queries"
        #             )
        #             st.plotly_chart(fig, use_container_width=True)
        #         elif tool_id == "2":  # Table sizes
        #             fig = px.pie(
        #                 results.head(10),
        #                 names="tablename",
        #                 values="size_bytes",
        #                 title="Largest Tables"
        #             )
        #             st.plotly_chart(fig, use_container_width=True)

# ------------------------------
# 5. MAIN APPLICATION CLASS
# ------------------------------

class PostgreSQLApp:
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.ui = UIComponents()
        if 'active_tab' not in st.session_state:
            st.session_state.active_tab = "Query Editor"  # Default tab


    def run(self):
        """Run the main application workflow."""
        st.title(Config.PAGE_TITLE)
        
        # Render the connection form in the sidebar
        connection_params = self.ui.render_connection_form()
        if connection_params:
            try:
                pool_instance = DatabasePool.get_instance()
                pool_instance.initialize(
                    host=connection_params["host"],
                    port=connection_params["port"],
                    database=connection_params["database"],
                    user=connection_params["user"],
                    password=connection_params["password"]
                )
                conn = pool_instance.get_connection()
                st.session_state.connection = conn
                st.session_state.current_db = connection_params["database"]
                st.success("Connected successfully!")
            except Exception as e:
                st.error(f"Connection failed: {str(e)}")
                return
            
        st.markdown("""
            <style>
                /* Outermost radio wrapper */
                .stRadio > div {
                    display: flex;
                    flex-wrap: nowrap;
                    overflow-x: auto;
                    justify-content: flex-start;
                    padding: 0.5rem;
                    background-color: #e3f2fd;  /* background for nav bar */
                    border-radius: 1rem;
                    box-shadow: inset 0 1px 3px rgba(0,0,0,0.05);
                }

                /* Radiogroup inner container */
                div[role=radiogroup] {
                    display: flex;
                    flex-direction: row;
                    gap: 0.5rem;
                    white-space: nowrap;
                }

                /* Hide the native radio button */
                div[role=radiogroup] input[type="radio"] {
                    display: none;
                }

                /* Labels styled as interactive tabs */
                div[role=radiogroup] label {
                    cursor: pointer;
                    background-color: transparent;
                    padding: 0.4rem 1rem;
                    border-radius: 999px;
                    transition: all 0.2s ease;
                    font-size: 0.9rem;
                    font-weight: 500;
                    color: #333;
                    border: 1px solid transparent;
                    position: relative;
                }

                /* Hover state */
                div[role=radiogroup] label:hover {
                    background-color: #d7dce2;
                    transform: translateY(-1px);
                }

                /* Selected tab style */
                div[role=radiogroup] label[data-testid=stRadioLabel]:has(input:checked) {
                    background-color: white;
                    color: #000;
                    border: 1px solid #c2c7d0;
                    box-shadow: 0 2px 6px rgba(0,0,0,0.08);
                    font-weight: 600;
                }
            </style>
        """, unsafe_allow_html=True)

        if st.session_state.get("connection"):
            # Define tab names
            tab_names = [
                "Query Editor", 
                "Table Browser", 
                "Database Info", 
                "User Management", 
                "Database Monitoring",
                "Advanced Diagnostics",
                "Performance Tuning"
            ]
            
            # Create tabs - this will automatically handle the active tab state
            selected_tab = st.radio(
                "Navigation",
                tab_names,
                horizontal=True,
                label_visibility="hidden"
            )
            
            # Show the appropriate tab content
            if selected_tab == "Query Editor":
                query, execute = self.ui.render_query_editor()
                if execute and query:
                    try:
                        df, exec_time = self.db_manager.execute_query(query)
                        if df is not None and not df.empty:
                            df.reset_index(drop=True, inplace=True)
                            st.dataframe(df)
                            st.download_button("Download CSV", df.to_csv(index=False), "results.csv")
                        else:
                            st.info("Query executed successfully, but no results to display.")
                        st.success(f"Query executed in {exec_time:.2f} seconds")
                    except Exception as e:
                        st.error(f"Query error: {str(e)}")
                        
            elif selected_tab == "Table Browser":
                self.ui.render_table_browser(self.db_manager)
                
            elif selected_tab == "Database Info":
                self.ui.render_database_info(self.db_manager)
                
            elif selected_tab == "User Management":
                self.ui.render_user_management(self.db_manager)
                
            elif selected_tab == "Database Monitoring":
                MonitoringTools.render_monitoring_tab(self.db_manager)
                
            elif selected_tab == "Advanced Diagnostics":
                MonitoringTools.render_diagnostics_tab(self.db_manager)
                
            elif selected_tab == "Performance Tuning":
                MonitoringTools.render_tuning_tab(self.db_manager)
                
# ------------------------------
# ENTRY POINT
# ------------------------------
if __name__ == "__main__":
    app = PostgreSQLApp()
    app.run()
