import streamlit as st
import psycopg2
import pandas as pd
import plotly.express as px

# --- Database Connection ---
@st.cache_resource(ttl=300) # Cache for 5 minutes (300 seconds)
def get_db_connection(db_host, db_name, db_user, db_password, db_port):
    """
    Establishes and returns a valid PostgreSQL database connection.
    Includes a health check (SELECT 1) to ensure the connection is active.
    If the connection fails or becomes stale, it clears the cache and forces a rerun.
    """
    conn = None
    try:
        conn = psycopg2.connect(
            host=db_host,
            database=db_name,
            user=db_user,
            password=db_password,
            port=db_port
        )
        # Test the connection immediately after establishing it or retrieving from cache
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        st.success("Successfully connected to the database!")
        return conn
    except psycopg2.OperationalError as e:
        # Catch connection-specific errors (e.g., refused, timeout, invalid credentials)
        st.error(f"Error connecting to the database: {e}. Please check your database server status, host, port, and credentials.")
        st.warning("Clearing connection cache and attempting to rerun...")
        st.cache_resource.clear() # Clear cache to force a new connection attempt
        st.stop() # Stop execution, Streamlit will rerun
    except Exception as e:
        # Catch any other unexpected errors during connection establishment
        st.error(f"An unexpected error occurred during database connection: {e}")
        st.warning("Clearing connection cache and attempting to rerun...")
        st.cache_resource.clear()
        st.stop() # Stop execution


# --- Data Fetching ---
def fetch_data_from_table(conn, table_name):
    """
    Fetches all data from the specified table.
    Includes robust error handling for connection issues during data fetching.
    """
    df = pd.DataFrame() # Initialize an empty DataFrame
    if conn is None:
        st.error("Database connection is not established. Please connect first.")
        return df

    try:
        # Attempt to read data using the provided connection
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        return df
    except psycopg2.InterfaceError as e:
        # This error indicates the connection object is no longer usable (e.g., server closed it)
        st.error(f"Error fetching data: The database connection became invalid or was closed ({e}).")
        st.warning("Clearing connection cache and attempting to re-establish connection on next run...")
        st.cache_resource.clear() # Clear cache to force a new connection on next rerun
        st.stop() # Stop execution, Streamlit will rerun
    except Exception as e:
        # Catch any other errors during data fetching (e.g., table not found, permission denied)
        st.error(f"Error fetching data from table '{table_name}': {e}")
        # No st.stop() here unless it's a critical, persistent error, to allow other parts of the app to function
    return df

# --- Descriptions and Use Cases for Tables ---
# Expanded descriptions with more detail and relevant use cases.
table_descriptions = {
    "pg_database": {
        "description": "This system catalog table stores essential metadata for each database instance within your PostgreSQL server. It holds critical information about the databases themselves, not the data within them.",
        "use_case": """
        **Use Cases:**
        * **Database Administration:** Identify all databases, their creation details, owners, and default encodings.
        * **Auditing:** Track database ownership changes or review database configurations.
        * **Capacity Planning:** Get a quick overview of how many databases exist on your server.
        * **Example Columns of Interest:** `datname` (database name), `datdba` (owner OID), `encoding` (character set encoding), `datistemplate` (is it a template database).
        """
    },
    "pg_stat_database": {
        "description": "Provides real-time statistics about database activity. This view is invaluable for performance monitoring and understanding the workload on your databases.",
        "use_case": """
        **Use Cases:**
        * **Performance Monitoring:** Track the number of transactions committed/rolled back (`xact_commit`, `xact_rollback`), data blocks read (`blks_read`) and hit in cache (`blks_hit`).
        * **Workload Analysis:** Identify databases with high activity levels or I/O patterns.
        * **Troubleshooting:** Pinpoint databases that might be experiencing issues like excessive rollbacks.
        * **Example Columns of Interest:** `datname`, `xact_commit`, `xact_rollback`, `blks_read`, `blks_hit`, `numbackends` (number of active connections).
        """
    },
    "pg_tablespace": {
        "description": "Contains information about all defined tablespaces. Tablespaces allow database administrators to control the physical location of database objects on disk, enabling more flexible storage management and I/O optimization.",
        "use_case": """
        **Use Cases:**
        * **Storage Management:** See where different parts of your database (tables, indexes) are physically stored.
        * **I/O Optimization:** Verify if critical data is on faster storage (e.g., SSDs) by checking tablespace locations.
        * **Migration Planning:** Understand the current storage layout before moving data or upgrading hardware.
        * **Example Columns of Interest:** `spcname` (tablespace name), `spclocation` (physical directory path), `spcowner` (owner OID).
        """
    },
    "pg_operator": {
        "description": "Lists all operators (e.g., `+`, `-`, `=`, `LIKE`) available in the database, including both built-in and user-defined operators. It provides details about their functionality, operand types, and return types.",
        "use_case": """
        **Use Cases:**
        * **Query Understanding:** Understand the behavior and types involved in various operations within SQL queries.
        * **Custom Function Development:** Explore existing operators to guide the creation of new, specialized operators.
        * **Debugging:** Investigate unexpected behavior of custom operators.
        * **Example Columns of Interest:** `oprname` (operator name), `oprleft` (left operand type), `oprright` (right operand type), `oprresult` (result type).
        """
    },
    "pg_available_extensions": {
        "description": "Provides a list of all PostgreSQL extensions that are available to be installed in a database, along with their versions and brief descriptions.",
        "use_case": """
        **Use Cases:**
        * **Feature Discovery:** See what additional functionalities (e.g., PostGIS for geospatial data, `pg_stat_statements` for query analysis) can be easily added to your database.
        * **Planning:** Determine which extensions might be useful for new projects or performance improvements.
        * **Troubleshooting:** Verify if a specific extension is present and available for installation.
        * **Example Columns of Interest:** `name` (extension name), `default_version`, `installed_version`, `comment`.
        """
    },
    "pg_shadow": {
        "description": "This table contains information about all database roles (users and groups), including their password hashes. It's a highly sensitive table, and direct access is usually restricted to superusers.",
        "use_case": """
        **Use Cases:**
        * **User Management:** Review existing roles, their attributes (e.g., can login, can create DBs), and password settings.
        * **Security Audits:** Check for roles with excessive privileges or weak password policies.
        * **Note:** Due to its sensitive nature, direct queries on `pg_shadow` should be avoided for routine operations. Use `\\du` in `psql` or `SELECT rolname, rolsuper, rolcreaterole, rolcreatedb FROM pg_roles;` for safer inspection.
        * **Example Columns of Interest:** `rolname` (role name), `rolpassword` (hashed password), `rolsuper` (is superuser), `rolcreaterole` (can create roles).
        """
    },
    "pg_stats": {
        "description": "Contains detailed statistics used by the PostgreSQL query planner to make informed decisions about how to execute queries efficiently. This includes statistics about column data distribution, null values, and common values.",
        "use_case": """
        **Use Cases:**
        * **Query Optimization:** Understand why the query planner chooses a particular execution plan.
        * **Data Analysis:** Gain insights into the distribution and characteristics of data within columns, even without direct data access (if permissions allow).
        * **Troubleshooting Slow Queries:** Identify columns where statistics might be outdated or insufficient, leading to poor query plans.
        * **Example Columns of Interest:** `schemaname`, `tablename`, `attname` (column name), `null_frac` (fraction of null values), `n_distinct` (number of distinct values), `most_common_vals`.
        """
    },
    "pg_timezone_names": {
        "description": "Provides a comprehensive list of all time zone names recognized by PostgreSQL, along with their standard abbreviations and UTC offsets.",
        "use_case": """
        **Use Cases:**
        * **Application Development:** Ensure consistent handling of dates and times across different regions.
        * **Data Import/Export:** Verify time zone settings when migrating data between systems.
        * **Debugging:** Understand how PostgreSQL resolves time zone names for timestamps.
        * **Example Columns of Interest:** `name` (time zone name), `abbrev` (abbreviation), `utc_offset`, `is_dst` (is daylight saving time).
        """
    },
    "pg_locks": {
        "description": "Shows information about all currently held locks within the database server. Locks are fundamental for concurrency control, ensuring data integrity during concurrent transactions.",
        "use_case": """
        **Use Cases:**
        * **Concurrency Debugging:** Identify long-running transactions or queries that might be holding locks and blocking other operations.
        * **Deadlock Detection:** Analyze lock contention to diagnose potential deadlocks.
        * **Performance Tuning:** Understand locking patterns to optimize application design and database queries.
        * **Example Columns of Interest:** `locktype`, `relation`, `mode` (type of lock), `granted` (is the lock held), `pid` (process ID of the locker).
        """
    },
    "pg_tables": {
        "description": "Provides a list of all tables (including system tables) that are visible to the current user in the database. It's a convenient view for browsing the database schema.",
        "use_case": """
        **Use Cases:**
        * **Schema Exploration:** Quickly list all tables within a schema.
        * **Auditing:** Review table owners, tablespaces, and `hasindexes` status.
        * **Scripting:** Programmatically retrieve table names for automated tasks.
        * **Example Columns of Interest:** `schemaname`, `tablename`, `tableowner`, `tablespace`.
        """
    },
    "pg_settings": {
        "description": "Displays all current runtime configuration parameters of the PostgreSQL server. This includes settings from `postgresql.conf`, command-line options, and environment variables.",
        "use_case": """
        **Use Cases:**
        * **Configuration Review:** Check the active values of important parameters like `shared_buffers`, `work_mem`, `max_connections`, `log_destination`.
        * **Performance Tuning:** Verify that performance-related settings are applied as expected.
        * **Security Audits:** Check security-related parameters.
        * **Example Columns of Interest:** `name` (parameter name), `setting` (current value), `unit`, `short_desc`, `vartype` (data type of the parameter).
        """
    },
    "pg_user_mappings": {
        "description": "Shows mappings between database users and users on foreign servers, which are used with Foreign Data Wrappers (FDW). FDWs allow PostgreSQL to query data residing on external data sources (e.g., other databases, flat files, web services) as if they were local tables.",
        "use_case": """
        **Use Cases:**
        * **Federated Data Management:** Understand which local users are mapped to which remote users for accessing external data.
        * **Security Configuration:** Review the security context used for foreign data access.
        * **Troubleshooting FDWs:** Diagnose permission issues when querying foreign tables.
        * **Example Columns of Interest:** `umname` (user mapping name), `srvname` (foreign server name), `usename` (local user name), `umoptions` (connection options).
        """
    },
    "pg_indexes": {
        "description": "Lists all indexes defined in the database, providing details about the index itself, the table it belongs to, and its definition.",
        "use_case": """
        **Use Cases:**
        * **Performance Optimization:** Identify existing indexes, check their uniqueness or primary key status.
        * **Schema Review:** Understand the indexing strategy of a database.
        * **Troubleshooting Slow Queries:** Determine if a necessary index exists or if an index is redundant.
        * **Example Columns of Interest:** `schemaname`, `tablename`, `indexname`, `indexdef` (CREATE INDEX statement), `indisunique` (is unique index).
        """
    },
    "pg_views": {
        "description": "Provides a list of all views defined in the database, along with their schema, owner, and definition. Views are virtual tables defined by a query, simplifying complex queries and providing a layer of abstraction and security.",
        "use_case": """
        **Use Cases:**
        * **Schema Exploration:** Discover all views and their underlying definitions.
        * **Data Abstraction:** Understand how complex data is presented in a simplified manner to users or applications.
        * **Security Review:** Check which views are exposed and what data they reveal.
        * **Example Columns of Interest:** `schemaname`, `viewname`, `viewowner`, `definition` (the SQL query that defines the view).
        """
    },
    "pg_stat_activity": {
        "description": "A crucial system view that allows you to monitor all active connections and their current activity on the PostgreSQL server, including details about executing queries and transaction states.",
        "use_case": """
        **Use Cases:**
        * **Real-time Performance Monitoring:** See which queries are running, their duration, and what resources they are consuming.
        * **Troubleshooting Hung Queries/Sessions:** Identify sessions that are idle in transaction, blocked, or running unusually long queries.
        * **Connection Management:** Observe the number of active connections per user or database.
        * **Example Columns of Interest:** `pid` (process ID), `datname` (database name), `usename` (user name), `application_name`, `client_addr`, `backend_start` (session start time), `query_start` (query start time), `state` (e.g., 'active', 'idle', 'idle in transaction'), `wait_event_type`, `wait_event`, `query`.
        """
    }
}

# --- Streamlit App Layout ---
def main():
    st.set_page_config(layout="wide", page_title="PostgreSQL System Catalog Dashboard")

    st.title("PostgreSQL System Catalog Dashboard")
    st.markdown(
        """
        This application allows you to explore the PostgreSQL system catalog tables. 
        Connect to your database, select a table, and visualize its contents.
        """
    )

    # --- Database Configuration in Sidebar ---
    st.sidebar.header("Database Configuration")
    db_host = st.sidebar.text_input("Database Host", value="localhost", key="db_host_input")
    db_port = st.sidebar.text_input("Database Port", value="5555", key="db_port_input")
    db_name = st.sidebar.text_input("Database Name", value="intellidb", key="db_name_input")
    db_user = st.sidebar.text_input("Database User", value="intellidb", key="db_user_input")
    db_password = st.sidebar.text_input("Database Password", type="password", key="db_password_input")

    # Initialize connection in session state if not present
    if 'db_conn' not in st.session_state:
        st.session_state.db_conn = None

    # Login Button
    if st.sidebar.button("Connect"):
        if all([db_host, db_port, db_name, db_user, db_password]):
            # Attempt to get connection and store in session state
            st.session_state.db_conn = get_db_connection(db_host, db_name, db_user, db_password, db_port)
        else:
            st.sidebar.error("Please fill in all database connection details.")

    # Only proceed if a valid connection exists in session state
    if st.session_state.db_conn:
        st.sidebar.write("---")
        st.sidebar.header("Table Selection")
        system_catalog_tables = list(table_descriptions.keys())
        selected_table = st.sidebar.selectbox(
            "Select a system catalog table to view:",
            system_catalog_tables,
            key="table_select"
        )

        st.subheader(f"Data from `{selected_table}`")

        # Display description and use case for the selected table using st.markdown for proper rendering
        if selected_table in table_descriptions:
            st.markdown(f"""
            <div style="background-color: #e0f2f7; padding: 15px; border-radius: 10px; margin-bottom: 20px;">
                <p style="font-weight: bold; color: #007bff;">Description:</p>
                <p>{table_descriptions[selected_table]['description']}</p>
                <p style="font-weight: bold; color: #007bff; margin-top: 10px;">Use Cases:</p>
                {table_descriptions[selected_table]['use_case']}
            </div>
            """, unsafe_allow_html=True) # Using unsafe_allow_html to embed basic styling for the info box
        else:
            st.warning("No detailed description or use case found for this table.")

        df = fetch_data_from_table(st.session_state.db_conn, selected_table)

        if not df.empty:
            st.dataframe(df, use_container_width=True)

            st.write("---")
            st.subheader("Visualizations")

            # Filter out 'oid' from numerical columns for visualization
            all_numerical_cols = df.select_dtypes(include=['number']).columns
            numerical_cols = [col for col in all_numerical_cols if col.lower() != 'oid']

            categorical_cols = df.select_dtypes(include=['object', 'bool']).columns

            # --- Numerical Column Visualizations ---
            if numerical_cols: # Check if numerical_cols is not empty after filtering
                st.write("#### Numerical Column Insights")
                selected_num_col = st.selectbox("Select a numerical column to visualize:", numerical_cols, key="viz_num_col")

                if selected_num_col:
                    num_unique_values = df[selected_num_col].nunique()

                    # Attempt to find a suitable categorical column for grouping
                    grouping_cat_col = None
                    # Iterate through categorical columns to find a good candidate for grouping
                    # A good candidate has more than 1 unique value and not too many (e.g., < 20 for bar chart X-axis)
                    for cat_col in categorical_cols:
                        if df[cat_col].nunique() > 1 and df[cat_col].nunique() < 20:
                            grouping_cat_col = cat_col
                            break

                    if grouping_cat_col:
                        st.write(f"**Bar Chart: '{selected_num_col}' by '{grouping_cat_col}'**")
                        # Check if each category typically has a single numerical value (e.g., datname and encoding)
                        # This is a heuristic: if all values in the numerical column within each group are the same.
                        # This might be too strict. A simpler approach is to always aggregate if grouping.
                        # Given user wants "value, not count", let's assume they want the direct values if possible,
                        # or an average if multiple entries per category are natural.
                        
                        # Let's aggregate by default for grouped numerical data for clarity, using mean.
                        grouped_data = df.groupby(grouping_cat_col)[selected_num_col].mean().reset_index()
                        fig_num = px.bar(grouped_data, x=grouping_cat_col, y=selected_num_col,
                                         title=f'Average {selected_num_col} by {grouping_cat_col}',
                                         color=grouping_cat_col,
                                         color_discrete_sequence=px.colors.qualitative.Plotly)
                        st.plotly_chart(fig_num, use_container_width=True)
                        st.info(f"This bar chart shows the *average* value of '{selected_num_col}' for each '{grouping_cat_col}' to facilitate comparison across categories.")

                    elif num_unique_values < 50: # Low/Medium cardinality numerical, no good grouping: Bar Chart of values
                        st.write(f"**Bar Chart: Individual Values of '{selected_num_col}'**")
                        # Sort for better readability
                        df_sorted = df.sort_values(by=selected_num_col).reset_index(drop=True)
                        fig_num = px.bar(df_sorted, y=selected_num_col,
                                        title=f'Individual Values of {selected_num_col}',
                                        color=selected_num_col, # Color by value for visual distinction
                                        color_continuous_scale=px.colors.sequential.Plasma) # Use a vibrant sequential scale
                        st.plotly_chart(fig_num, use_container_width=True)
                        st.info("This bar chart displays each individual value of the numerical column, sorted for easier interpretation.")
                    else: # High cardinality numerical with no good grouping: Scatter Plot of individual values
                        st.write(f"**Scatter Plot: Distribution of Individual Values for '{selected_num_col}'**")
                        # A scatter plot is better when many distinct values, shows distribution of values directly
                        fig_scatter = px.scatter(df, y=selected_num_col,
                                                 title=f'Individual Values Distribution of {selected_num_col}',
                                                 color=selected_num_col, # Color by value
                                                 color_continuous_scale=px.colors.sequential.Plasma)
                        st.plotly_chart(fig_scatter, use_container_width=True)
                        st.info("A scatter plot shows the distribution of individual values for this numerical column, suitable for high cardinality data.")

            else:
                st.info("No suitable numerical columns (excluding 'oid') found for visualization.")


            # --- Categorical Column Visualizations ---
            if not categorical_cols.empty:
                st.write("#### Categorical Column Value Counts and Proportions")
                selected_cat_col = st.selectbox("Select a categorical column to visualize:", categorical_cols, key="viz_cat_col")

                if selected_cat_col:
                    cat_num_unique_values = df[selected_cat_col].nunique()

                    if cat_num_unique_values > 0: # Ensure there are unique values
                        if cat_num_unique_values <= 10: # Suitable for Bar, Pie, or Donut
                            chart_type = st.radio(
                                "Choose chart type:",
                                ("Bar Chart", "Pie Chart", "Donut Chart"),
                                key=f"cat_chart_type_{selected_cat_col}"
                            )

                            if chart_type == "Bar Chart":
                                value_counts_cat = df[selected_cat_col].value_counts().reset_index()
                                value_counts_cat.columns = [selected_cat_col, 'count']
                                fig_cat = px.bar(value_counts_cat, x=selected_cat_col, y='count',
                                                 title=f'Value Counts of {selected_cat_col}', color=selected_cat_col,
                                                 color_discrete_sequence=px.colors.qualitative.Plotly)
                                st.plotly_chart(fig_cat, use_container_width=True)
                            elif chart_type == "Pie Chart":
                                fig_pie = px.pie(df, names=selected_cat_col, title=f'Proportion of {selected_cat_col}',
                                                 color_discrete_sequence=px.colors.qualitative.Plotly)
                                st.plotly_chart(fig_pie, use_container_width=True)
                            elif chart_type == "Donut Chart":
                                fig_donut = px.pie(df, names=selected_cat_col, title=f'Proportion of {selected_cat_col}', hole=0.4,
                                                   color_discrete_sequence=px.colors.qualitative.Plotly)
                                st.plotly_chart(fig_donut, use_container_width=True)
                        elif cat_num_unique_values < 50: # Only Bar Chart (too many for pie/donut)
                            st.write(f"**Bar Chart for '{selected_cat_col}' (Medium Unique Values)**")
                            value_counts_cat = df[selected_cat_col].value_counts().reset_index()
                            value_counts_cat.columns = [selected_cat_col, 'count']
                            fig_cat = px.bar(value_counts_cat, x=selected_cat_col, y='count',
                                             title=f'Value Counts of {selected_cat_col}', color=selected_cat_col,
                                             color_discrete_sequence=px.colors.qualitative.Plotly)
                            st.plotly_chart(fig_cat, use_container_width=True)
                            st.info("Using a Bar Chart for medium cardinality categorical data.")
                        else: # Too many unique values for visualization
                            st.info(f"Column '{selected_cat_col}' has too many unique values ({cat_num_unique_values}) for a chart. Displaying top 10 value counts:")
                            st.write(df[selected_cat_col].value_counts().head(10))
                    else:
                        st.info(f"Column '{selected_cat_col}' has no unique values to display for visualization.")
            else:
                st.info("No suitable categorical columns found for detailed visualizations.")
        else:
            st.warning("No data retrieved for the selected table, or the table is empty.")


if __name__ == "__main__":
    main()
