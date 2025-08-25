import React, { useState, useEffect } from 'react';
import Plot from 'react-plotly.js';
import { Database, Table, BarChart, PieChart, Info, Wifi, WifiOff } from 'lucide-react'; // Icons

// Table descriptions and use cases as provided in the Python app
const tableDescriptions = {
    "pg_database": {
        "description": "This system catalog table stores essential metadata for each database instance within your PostgreSQL server. It holds critical information about the databases themselves, not the data within them.",
        "use_case": `
        <p style="font-weight: bold; color: #007bff; margin-top: 10px;">Use Cases:</p>
        <ul>
            <li><strong>Database Administration:</strong> Identify all databases, their creation details, owners, and default encodings.</li>
            <li><strong>Auditing:</strong> Track database ownership changes or review database configurations.</li>
            <li><strong>Capacity Planning:</strong> Get a quick overview of how many databases exist on your server.</li>
            <li><strong>Example Columns of Interest:</strong> <code>datname</code> (database name), <code>datdba</code> (owner OID), <code>encoding</code> (character set encoding), <code>datistemplate</code> (is it a template database).</li>
        </ul>
        `
    },
    "pg_stat_database": {
        "description": "Provides real-time statistics about database activity. This view is invaluable for performance monitoring and understanding the workload on your databases.",
        "use_case": `
        <p style="font-weight: bold; color: #007bff; margin-top: 10px;">Use Cases:</p>
        <ul>
            <li><strong>Performance Monitoring:</strong> Track the number of transactions committed/rolled back (<code>xact_commit</code>, <code>xact_rollback</code>), data blocks read (<code>blks_read</code>) and hit in cache (<code>blks_hit</code>).</li>
            <li><strong>Workload Analysis:</strong> Identify databases with high activity levels or I/O patterns.</li>
            <li><strong>Troubleshooting:</strong> Pinpoint databases that might be experiencing issues like excessive rollbacks.</li>
            <li><strong>Example Columns of Interest:</strong> <code>datname</code>, <code>xact_commit</code>, <code>xact_rollback</code>, <code>blks_read</code>, <code>blks_hit</code>, <code>numbackends</code> (number of active connections).</li>
        </ul>
        `
    },
    "pg_tablespace": {
        "description": "Contains information about all defined tablespaces. Tablespaces allow database administrators to control the physical location of database objects on disk, enabling more flexible storage management and I/O optimization.",
        "use_case": `
        <p style="font-weight: bold; color: #007bff; margin-top: 10px;">Use Cases:</p>
        <ul>
            <li><strong>Storage Management:</strong> See where different parts of your database (tables, indexes) are physically stored.</li>
            <li><strong>I/O Optimization:</strong> Verify if critical data is on faster storage (e.g., SSDs) by checking tablespace locations.</li>
            <li><strong>Migration Planning:</strong> Understand the current storage layout before moving data or upgrading hardware.</li>
            <li><strong>Example Columns of Interest:</strong> <code>spcname</code> (tablespace name), <code>spclocation</code> (physical directory path), <code>spcowner</code> (owner OID).</li>
        </ul>
        `
    },
    "pg_operator": {
        "description": "Lists all operators (e.g., `+`, `-`, `=`, `LIKE`) available in the database, including both built-in and user-defined operators. It provides details about their functionality, operand types, and return types.",
        "use_case": `
        <p style="font-weight: bold; color: #007bff; margin-top: 10px;">Use Cases:</p>
        <ul>
            <li><strong>Query Understanding:</strong> Understand the behavior and types involved in various operations within SQL queries.</li>
            <li><strong>Custom Function Development:</strong> Explore existing operators to guide the creation of new, specialized operators.</li>
            <li><strong>Debugging:</strong> Investigate unexpected behavior of custom operators.</li>
            <li><strong>Example Columns of Interest:</strong> <code>oprname</code> (operator name), <code>oprleft</code> (left operand type), <code>oprright</code> (right operand type), <code>oprresult</code> (result type).</li>
        </ul>
        `
    },
    "pg_available_extensions": {
        "description": "Provides a list of all PostgreSQL extensions that are available to be installed in a database, along with their versions and brief descriptions.",
        "use_case": `
        <p style="font-weight: bold; color: #007bff; margin-top: 10px;">Use Cases:</p>
        <ul>
            <li><strong>Feature Discovery:</strong> See what additional functionalities (e.g., PostGIS for geospatial data, <code>pg_stat_statements</code> for query analysis) can be easily added to your database.</li>
            <li><strong>Planning:</strong> Determine which extensions might be useful for new projects or performance improvements.</li>
            <li><strong>Troubleshooting:</strong> Verify if a specific extension is present and available for installation.</li>
            <li><strong>Example Columns of Interest:</strong> <code>name</code> (extension name), <code>default_version</code>, <code>installed_version</code>, <code>comment</code>.</li>
        </ul>
        `
    },
    "pg_shadow": {
        "description": "This table contains information about all database roles (users and groups), including their password hashes. It's a highly sensitive table, and direct access is usually restricted to superusers.",
        "use_case": `
        <p style="font-weight: bold; color: #007bff; margin-top: 10px;">Use Cases:</p>
        <ul>
            <li><strong>User Management:</strong> Review existing roles, their attributes (e.g., can login, can create DBs), and password settings.</li>
            <li><strong>Security Audits:</strong> Check for roles with excessive privileges or weak password policies.</li>
            <li><strong>Note:</strong> Due to its sensitive nature, direct queries on <code>pg_shadow</code> should be avoided for routine operations. Use <code>\\du</code> in <code>psql</code> or <code>SELECT rolname, rolsuper, rolcreaterole, rolcreatedb FROM pg_roles;</code> for safer inspection.</li>
            <li><strong>Example Columns of Interest:</strong> <code>rolname</code> (role name), <code>rolpassword</code> (hashed password), <code>rolsuper</code> (is superuser), <code>rolcreaterole</code> (can create roles).</li>
        </ul>
        `
    },
    "pg_stats": {
        "description": "Contains detailed statistics used by the PostgreSQL query planner to make informed decisions about how to execute queries efficiently. This includes statistics about column data distribution, null values, and common values.",
        "use_case": `
        <p style="font-weight: bold; color: #007bff; margin-top: 10px;">Use Cases:</p>
        <ul>
            <li><strong>Query Optimization:</strong> Understand why the query planner chooses a particular execution plan.</li>
            <li><strong>Data Analysis:</strong> Gain insights into the distribution and characteristics of data within columns, even without direct data access (if permissions allow).</li>
            <li><strong>Troubleshooting Slow Queries:</strong> Identify columns where statistics might be outdated or insufficient, leading to poor query plans.</li>
            <li><strong>Example Columns of Interest:</strong> <code>schemaname</code>, <code>tablename</code>, <code>attname</code> (column name), <code>null_frac</code> (fraction of null values), <code>n_distinct</code> (number of distinct values), <code>most_common_vals</code>.</li>
        </ul>
        `
    },
    "pg_timezone_names": {
        "description": "Provides a comprehensive list of all time zone names recognized by PostgreSQL, along with their standard abbreviations and UTC offsets.",
        "use_case": `
        <p style="font-weight: bold; color: #007bff; margin-top: 10px;">Use Cases:</p>
        <ul>
            <li><strong>Application Development:</strong> Ensure consistent handling of dates and times across different regions.</li>
            <li><strong>Data Import/Export:</strong> Verify time zone settings when migrating data between systems.</li>
            <li><strong>Debugging:</strong> Understand how PostgreSQL resolves time zone names for timestamps.</li>
            <li><strong>Example Columns of Interest:</strong> <code>name</code> (time zone name), <code>abbrev</code> (abbreviation), <code>utc_offset</code>, <code>is_dst</code> (is daylight saving time).</li>
        </ul>
        `
    },
    "pg_locks": {
        "description": "Shows information about all currently held locks within the database server. Locks are fundamental for concurrency control, ensuring data integrity during concurrent transactions.",
        "use_case": `
        <p style="font-weight: bold; color: #007bff; margin-top: 10px;">Use Cases:</p>
        <ul>
            <li><strong>Concurrency Debugging:</strong> Identify long-running transactions or queries that might be holding locks and blocking other operations.</li>
            <li><strong>Deadlock Detection:</strong> Analyze lock contention to diagnose potential deadlocks.</li>
            <li><strong>Performance Tuning:</strong> Understand locking patterns to optimize application design and database queries.</li>
            <li><strong>Example Columns of Interest:</strong> <code>locktype</code>, <code>relation</code>, <code>mode</code> (type of lock), <code>granted</code> (is the lock held), <code>pid</code> (process ID of the locker).</li>
        </ul>
        `
    },
    "pg_tables": {
        "description": "Provides a list of all tables (including system tables) that are visible to the current user in the database. It's a convenient view for browsing the database schema.",
        "use_case": `
        <p style="font-weight: bold; color: #007bff; margin-top: 10px;">Use Cases:</p>
        <ul>
            <li><strong>Schema Exploration:</strong> Quickly list all tables within a schema.</li>
            <li><strong>Auditing:</strong> Review table owners, tablespaces, and <code>hasindexes</code> status.</li>
            <li><strong>Scripting:</strong> Programmatically retrieve table names for automated tasks.</li>
            <li><strong>Example Columns of Interest:</strong> <code>schemaname</code>, <code>tablename</code>, <code>tableowner</code>, <code>tablespace</code>.</li>
        </ul>
        `
    },
    "pg_settings": {
        "description": "Displays all current runtime configuration parameters of the PostgreSQL server. This includes settings from <code>postgresql.conf</code>, command-line options, and environment variables.",
        "use_case": `
        <p style="font-weight: bold; color: #007bff; margin-top: 10px;">Use Cases:</p>
        <ul>
            <li><strong>Configuration Review:</strong> Check the active values of important parameters like <code>shared_buffers</code>, <code>work_mem</code>, <code>max_connections</code>, <code>log_destination</code>.</li>
            <li><strong>Performance Tuning:</strong> Verify that performance-related settings are applied as expected.</li>
            <li><strong>Security Audits:</strong> Check security-related parameters.</li>
            <li><strong>Example Columns of Interest:</strong> <code>name</code> (parameter name), <code>setting</code> (current value), <code>unit</code>, <code>short_desc</code>, <code>vartype</code> (data type of the parameter).</li>
        </ul>
        `
    },
    "pg_user_mappings": {
        "description": "Shows mappings between database users and users on foreign servers, which are used with Foreign Data Wrappers (FDW). FDWs allow PostgreSQL to query data residing on external data sources (e.g., other databases, flat files, web services) as if they were local tables.",
        "use_case": `
        <p style="font-weight: bold; color: #007bff; margin-top: 10px;">Use Cases:</p>
        <ul>
            <li><strong>Federated Data Management:</strong> Understand which local users are mapped to which remote users for accessing external data.</li>
            <li><strong>Security Configuration:</strong> Review the security context used for foreign data access.</li>
            <li><strong>Troubleshooting FDWs:</strong> Diagnose permission issues when querying foreign tables.</li>
            <li><strong>Example Columns of Interest:</strong> <code>umname</code> (user mapping name), <code>srvname</code> (foreign server name), <code>usename</code> (local user name), <code>umoptions</code> (connection options).</li>
        </ul>
        `
    },
    "pg_indexes": {
        "description": "Lists all indexes defined in the database, providing details about the index itself, the table it belongs to, and its definition.",
        "use_case": `
        <p style="font-weight: bold; color: #007bff; margin-top: 10px;">Use Cases:</p>
        <ul>
            <li><strong>Performance Optimization:</strong> Identify existing indexes, check their uniqueness or primary key status.</li>
            <li><strong>Schema Review:</strong> Understand the indexing strategy of a database.</li>
            <li><strong>Troubleshooting Slow Queries:</strong> Determine if a necessary index exists or if an index is redundant.</li>
            <li><strong>Example Columns of Interest:</strong> <code>schemaname</code>, <code>tablename</code>, <code>indexname</code>, <code>indexdef</code> (CREATE INDEX statement), <code>indisunique</code> (is unique index).</li>
        </ul>
        `
    },
    "pg_views": {
        "description": "Provides a list of all views defined in the database, along with their schema, owner, and definition. Views are virtual tables defined by a query, simplifying complex queries and providing a layer of abstraction and security.",
        "use_case": `
        <p style="font-weight: bold; color: #007bff; margin-top: 10px;">Use Cases:</p>
        <ul>
            <li><strong>Schema Exploration:</strong> Discover all views and their underlying definitions.</li>
            <li><strong>Data Abstraction:</strong> Understand how complex data is presented in a simplified manner to users or applications.</li>
            <li><strong>Security Review:</strong> Check which views are exposed and what data they reveal.</li>
            <li><strong>Example Columns of Interest:</strong> <code>schemaname</code>, <code>viewname</code>, <code>viewowner</code>, <code>definition</code> (the SQL query that defines the view).</li>
        </ul>
        `
    },
    "pg_stat_activity": {
        "description": "A crucial system view that allows you to monitor all active connections and their current activity on the PostgreSQL server, including details about executing queries and transaction states.",
        "use_case": `
        <p style="font-weight: bold; color: #007bff; margin-top: 10px;">Use Cases:</p>
        <ul>
            <li><strong>Real-time Performance Monitoring:</strong> See which queries are running, their duration, and what resources they are consuming.</li>
            <li><strong>Troubleshooting Hung Queries/Sessions:</strong> Identify sessions that are idle in transaction, blocked, or running unusually long queries.</li>
            <li><strong>Connection Management:</strong> Observe the number of active connections per user or database.</li>
            <li><strong>Example Columns of Interest:</strong> <code>pid</code> (process ID), <code>datname</code> (database name), <code>usename</code> (user name), <code>application_name</code>, <code>client_addr</code>, <code>backend_start</code> (session start time), <code>query_start</code> (query start time), <code>state</code> (e.g., 'active', 'idle', 'idle in transaction'), <code>wait_event_type</code>, <code>wait_event</code>, <code>query</code>.</li>
        </ul>
        `
    }
};

const systemCatalogTables = Object.keys(tableDescriptions);

// Helper to capitalize the first letter of a string
const capitalize = (s) => s && s[0].toUpperCase() + s.slice(1);

function App() {
    // State for database connection details
    const [dbHost, setDbHost] = useState('localhost');
    const [dbPort, setDbPort] = useState('5555');
    const [dbName, setDbName] = useState('intellidb');
    const [dbUser, setDbUser] = useState('intellidb');
    const [dbPassword, setDbPassword] = useState('');
    const [isConnected, setIsConnected] = useState(false);
    const [connectionMessage, setConnectionMessage] = useState('');

    // State for selected table and its data
    const [selectedTable, setSelectedTable] = useState('');
    const [tableData, setTableData] = useState([]);
    const [loadingData, setLoadingData] = useState(false);
    const [dataError, setDataError] = useState('');

    // State for visualization selections
    const [selectedNumCol, setSelectedNumCol] = useState('');
    const [selectedCatCol, setSelectedCatCol] = useState('');
    const [chartType, setChartType] = useState('Bar Chart');

    // Function to simulate database connection
    const handleConnect = () => {
        // In a real application, this would send credentials to a backend
        // and await a response. Here, we simulate success after a delay.
        if (dbHost && dbPort && dbName && dbUser && dbPassword) {
            setConnectionMessage('Attempting to connect...');
            setTimeout(() => {
                setIsConnected(true);
                setConnectionMessage('Successfully connected to the database (simulated)!');
                // Set a default selected table once connected
                if (systemCatalogTables.length > 0) {
                    setSelectedTable(systemCatalogTables[0]);
                }
            }, 1000); // Simulate network delay
        } else {
            setConnectionMessage('Please fill in all database connection details.');
            setIsConnected(false);
        }
    };

    // Function to generate mock data using Gemini API
    const fetchMockTableData = async (tableName) => {
        setLoadingData(true);
        setDataError('');
        setTableData([]); // Clear previous data

        let prompt = `Generate mock data for the PostgreSQL system catalog table '${tableName}' as a JSON array of objects.`;
        let responseSchema = {
            type: "ARRAY",
            items: {
                type: "OBJECT",
                properties: {} // Properties will be dynamically set based on table name
            }
        };

        // Define schema properties based on table name for better mock data
        switch (tableName) {
            case 'pg_database':
                prompt += " Include columns: datname (string), datdba (number), encoding (string), datistemplate (boolean). Provide around 5-10 realistic-looking rows.";
                responseSchema.items.properties = {
                    "datname": { "type": "STRING" },
                    "datdba": { "type": "NUMBER" },
                    "encoding": { "type": "STRING" },
                    "datistemplate": { "type": "BOOLEAN" }
                };
                break;
            case 'pg_stat_database':
                prompt += " Include columns: datname (string), xact_commit (number), xact_rollback (number), blks_read (number), blks_hit (number), numbackends (number). Provide around 5-10 realistic-looking rows.";
                responseSchema.items.properties = {
                    "datname": { "type": "STRING" },
                    "xact_commit": { "type": "NUMBER" },
                    "xact_rollback": { "type": "NUMBER" },
                    "blks_read": { "type": "NUMBER" },
                    "blks_hit": { "type": "NUMBER" },
                    "numbackends": { "type": "NUMBER" }
                };
                break;
            case 'pg_tablespace':
                prompt += " Include columns: spcname (string), spclocation (string), spcowner (number). Provide around 3-5 realistic-looking rows.";
                responseSchema.items.properties = {
                    "spcname": { "type": "STRING" },
                    "spclocation": { "type": "STRING" },
                    "spcowner": { "type": "NUMBER" }
                };
                break;
            case 'pg_operator':
                prompt += " Include columns: oprname (string), oprleft (string), oprright (string), oprresult (string). Provide around 10-15 realistic-looking rows.";
                responseSchema.items.properties = {
                    "oprname": { "type": "STRING" },
                    "oprleft": { "type": "STRING" },
                    "oprright": { "type": "STRING" },
                    "oprresult": { "type": "STRING" }
                };
                break;
            case 'pg_available_extensions':
                prompt += " Include columns: name (string), default_version (string), installed_version (string), comment (string). Provide around 5-10 realistic-looking rows.";
                responseSchema.items.properties = {
                    "name": { "type": "STRING" },
                    "default_version": { "type": "STRING" },
                    "installed_version": { "type": "STRING" },
                    "comment": { "type": "STRING" }
                };
                break;
            case 'pg_shadow':
                prompt += " Include columns: rolname (string), rolsuper (boolean), rolcreaterole (boolean), rolcreatedb (boolean). Provide around 3-5 realistic-looking rows.";
                responseSchema.items.properties = {
                    "rolname": { "type": "STRING" },
                    "rolsuper": { "type": "BOOLEAN" },
                    "rolcreaterole": { "type": "BOOLEAN" },
                    "rolcreatedb": { "type": "BOOLEAN" }
                };
                break;
            case 'pg_stats':
                prompt += " Include columns: schemaname (string), tablename (string), attname (string), null_frac (number), n_distinct (number). Provide around 5-10 realistic-looking rows.";
                responseSchema.items.properties = {
                    "schemaname": { "type": "STRING" },
                    "tablename": { "type": "STRING" },
                    "attname": { "type": "STRING" },
                    "null_frac": { "type": "NUMBER" },
                    "n_distinct": { "type": "NUMBER" }
                };
                break;
            case 'pg_timezone_names':
                prompt += " Include columns: name (string), abbrev (string), utc_offset (string), is_dst (boolean). Provide around 5-10 realistic-looking rows.";
                responseSchema.items.properties = {
                    "name": { "type": "STRING" },
                    "abbrev": { "type": "STRING" },
                    "utc_offset": { "type": "STRING" },
                    "is_dst": { "type": "BOOLEAN" }
                };
                break;
            case 'pg_locks':
                prompt += " Include columns: locktype (string), relation (string), mode (string), granted (boolean), pid (number). Provide around 5-10 realistic-looking rows.";
                responseSchema.items.properties = {
                    "locktype": { "type": "STRING" },
                    "relation": { "type": "STRING" },
                    "mode": { "type": "STRING" },
                    "granted": { "type": "BOOLEAN" },
                    "pid": { "type": "NUMBER" }
                };
                break;
            case 'pg_tables':
                prompt += " Include columns: schemaname (string), tablename (string), tableowner (string), tablespace (string). Provide around 5-10 realistic-looking rows.";
                responseSchema.items.properties = {
                    "schemaname": { "type": "STRING" },
                    "tablename": { "type": "STRING" },
                    "tableowner": { "type": "STRING" },
                    "tablespace": { "type": "STRING" }
                };
                break;
            case 'pg_settings':
                prompt += " Include columns: name (string), setting (string), unit (string), short_desc (string), vartype (string). Provide around 5-10 realistic-looking rows.";
                responseSchema.items.properties = {
                    "name": { "type": "STRING" },
                    "setting": { "type": "STRING" },
                    "unit": { "type": "STRING" },
                    "short_desc": { "type": "STRING" },
                    "vartype": { "type": "STRING" }
                };
                break;
            case 'pg_user_mappings':
                prompt += " Include columns: umname (string), srvname (string), usename (string), umoptions (string). Provide around 3-5 realistic-looking rows.";
                responseSchema.items.properties = {
                    "umname": { "type": "STRING" },
                    "srvname": { "type": "STRING" },
                    "usename": { "type": "STRING" },
                    "umoptions": { "type": "STRING" }
                };
                break;
            case 'pg_indexes':
                prompt += " Include columns: schemaname (string), tablename (string), indexname (string), indexdef (string), indisunique (boolean). Provide around 5-10 realistic-looking rows.";
                responseSchema.items.properties = {
                    "schemaname": { "type": "STRING" },
                    "tablename": { "type": "STRING" },
                    "indexname": { "type": "STRING" },
                    "indexdef": { "type": "STRING" },
                    "indisunique": { "type": "BOOLEAN" }
                };
                break;
            case 'pg_views':
                prompt += " Include columns: schemaname (string), viewname (string), viewowner (string), definition (string). Provide around 5-10 realistic-looking rows.";
                responseSchema.items.properties = {
                    "schemaname": { "type": "STRING" },
                    "viewname": { "type": "STRING" },
                    "viewowner": { "type": "STRING" },
                    "definition": { "type": "STRING" }
                };
                break;
            case 'pg_stat_activity':
                prompt += " Include columns: pid (number), datname (string), usename (string), application_name (string), client_addr (string), query_start (string), state (string), query (string). Provide around 5-10 realistic-looking rows.";
                responseSchema.items.properties = {
                    "pid": { "type": "NUMBER" },
                    "datname": { "type": "STRING" },
                    "usename": { "type": "STRING" },
                    "application_name": { "type": "STRING" },
                    "client_addr": { "type": "STRING" },
                    "query_start": { "type": "STRING" },
                    "state": { "type": "STRING" },
                    "query": { "type": "STRING" }
                };
                break;
            default:
                prompt += " Provide a generic set of columns for a system catalog table, around 5-10 rows.";
                responseSchema.items.properties = {
                    "id": { "type": "NUMBER" },
                    "name": { "type": "STRING" },
                    "value": { "type": "STRING" }
                };
                break;
        }

        const chatHistory = [{ role: "user", parts: [{ text: prompt }] }];
        const payload = {
            contents: chatHistory,
            generationConfig: {
                responseMimeType: "application/json",
                responseSchema: responseSchema
            }
        };

        const apiKey = ""; // Canvas will automatically provide this
        const apiUrl = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${apiKey}`;

        try {
            const response = await fetch(apiUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const errorBody = await response.text();
                throw new Error(`HTTP error! status: ${response.status}, body: ${errorBody}`);
            }

            const result = await response.json();

            if (result.candidates && result.candidates.length > 0 &&
                result.candidates[0].content && result.candidates[0].content.parts &&
                result.candidates[0].content.parts.length > 0) {
                const jsonString = result.candidates[0].content.parts[0].text;
                try {
                    const parsedData = JSON.parse(jsonString);
                    setTableData(parsedData);
                } catch (parseError) {
                    setDataError(`Failed to parse API response: ${parseError.message}. Raw: ${jsonString}`);
                    console.error("Parsing error:", parseError, "Raw JSON:", jsonString);
                }
            } else {
                setDataError('No data found in API response.');
            }
        } catch (error) {
            setDataError(`Failed to fetch data: ${error.message}`);
            console.error("API call error:", error);
        } finally {
            setLoadingData(false);
        }
    };

    // Effect to fetch data when selectedTable changes and connection is active
    useEffect(() => {
        if (isConnected && selectedTable) {
            fetchMockTableData(selectedTable);
        }
    }, [isConnected, selectedTable]);

    // Derived state for column types
    const columns = tableData.length > 0 ? Object.keys(tableData[0]) : [];
    const numericalCols = columns.filter(col => typeof tableData[0][col] === 'number' && col.toLowerCase() !== 'oid');
    const categoricalCols = columns.filter(col => typeof tableData[0][col] === 'string' || typeof tableData[0][col] === 'boolean');

    // Effect to update selected visualization columns when tableData or selectedTable changes
    useEffect(() => {
        if (numericalCols.length > 0) {
            setSelectedNumCol(numericalCols[0]);
        } else {
            setSelectedNumCol('');
        }
        if (categoricalCols.length > 0) {
            setSelectedCatCol(categoricalCols[0]);
        } else {
            setSelectedCatCol('');
        }
    }, [tableData]);

    // Function to render Plotly chart
    const renderChart = () => {
        if (!tableData || tableData.length === 0) {
            return <p className="text-gray-600">No data to visualize.</p>;
        }

        // Numerical Visualization Logic
        if (selectedNumCol && numericalCols.includes(selectedNumCol)) {
            const numUniqueValues = new Set(tableData.map(row => row[selectedNumCol])).size;

            // Attempt to find a suitable categorical column for grouping
            let groupingCatCol = null;
            for (const catCol of categoricalCols) {
                const uniqueCatValues = new Set(tableData.map(row => row[catCol])).size;
                if (uniqueCatValues > 1 && uniqueCatValues < 20) { // Heuristic for good grouping
                    groupingCatCol = catCol;
                    break;
                }
            }

            if (groupingCatCol) {
                // Group by categorical column and calculate mean of numerical
                const groupedData = tableData.reduce((acc, row) => {
                    const groupKey = row[groupingCatCol];
                    if (!acc[groupKey]) {
                        acc[groupKey] = { sum: 0, count: 0 };
                    }
                    if (typeof row[selectedNumCol] === 'number') {
                        acc[groupKey].sum += row[selectedNumCol];
                        acc[groupKey].count += 1;
                    }
                    return acc;
                }, {});

                const plotData = Object.keys(groupedData).map(key => ({
                    x: key,
                    y: groupedData[key].count > 0 ? groupedData[key].sum / groupedData[key].count : 0,
                    type: 'bar',
                    name: key
                }));

                return (
                    <div className="mb-8 p-4 bg-blue-50 rounded-md">
                        <h4 className="text-lg font-semibold mb-2 flex items-center"><BarChart className="mr-2" size={20} /> Bar Chart: '{capitalize(selectedNumCol)}' by '{capitalize(groupingCatCol)}'</h4>
                        <Plot
                            data={plotData}
                            layout={{
                                title: `Average ${capitalize(selectedNumCol)} by ${capitalize(groupingCatCol)}`,
                                xaxis: { title: capitalize(groupingCatCol) },
                                yaxis: { title: capitalize(selectedNumCol) },
                                showlegend: false,
                                height: 400,
                                margin: { l: 60, r: 20, b: 60, t: 60 }
                            }}
                            useResizeHandler
                            style={{ width: '100%', height: '100%' }}
                        />
                        <p className="text-sm text-blue-700 mt-2">This bar chart shows the *average* value of '{selectedNumCol}' for each '{groupingCatCol}' to facilitate comparison across categories.</p>
                    </div>
                );
            } else if (numUniqueValues < 50) { // Low/Medium cardinality numerical, no good grouping: Bar Chart of values
                const sortedData = [...tableData].sort((a, b) => a[selectedNumCol] - b[selectedNumCol]);
                return (
                    <div className="mb-8 p-4 bg-blue-50 rounded-md">
                        <h4 className="text-lg font-semibold mb-2 flex items-center"><BarChart className="mr-2" size={20} /> Bar Chart: Individual Values of '{capitalize(selectedNumCol)}'</h4>
                        <Plot
                            data={[{
                                y: sortedData.map(row => row[selectedNumCol]),
                                type: 'bar',
                                marker: {
                                    color: sortedData.map(row => row[selectedNumCol]),
                                    colorscale: 'Plasma'
                                }
                            }]}
                            layout={{
                                title: `Individual Values of ${capitalize(selectedNumCol)}`,
                                yaxis: { title: capitalize(selectedNumCol) },
                                showlegend: false,
                                height: 400,
                                margin: { l: 60, r: 20, b: 60, t: 60 }
                            }}
                            useResizeHandler
                            style={{ width: '100%', height: '100%' }}
                        />
                        <p className="text-sm text-blue-700 mt-2">This bar chart displays each individual value of the numerical column, sorted for easier interpretation.</p>
                    </div>
                );
            } else { // High cardinality numerical with no good grouping: Scatter Plot
                return (
                    <div className="mb-8 p-4 bg-blue-50 rounded-md">
                        <h4 className="text-lg font-semibold mb-2 flex items-center"><BarChart className="mr-2" size={20} /> Scatter Plot: Distribution of Individual Values for '{capitalize(selectedNumCol)}'</h4>
                        <Plot
                            data={[{
                                y: tableData.map(row => row[selectedNumCol]),
                                mode: 'markers',
                                type: 'scatter',
                                marker: {
                                    color: tableData.map(row => row[selectedNumCol]),
                                    colorscale: 'Plasma',
                                    size: 8,
                                    opacity: 0.7
                                }
                            }]}
                            layout={{
                                title: `Individual Values Distribution of ${capitalize(selectedNumCol)}`,
                                yaxis: { title: capitalize(selectedNumCol) },
                                showlegend: false,
                                height: 400,
                                margin: { l: 60, r: 20, b: 60, t: 60 }
                            }}
                            useResizeHandler
                            style={{ width: '100%', height: '100%' }}
                        />
                        <p className="text-sm text-blue-700 mt-2">A scatter plot shows the distribution of individual values for this numerical column, suitable for high cardinality data.</p>
                    </div>
                );
            }
        }

        // Categorical Visualization Logic
        if (selectedCatCol && categoricalCols.includes(selectedCatCol)) {
            const valueCounts = tableData.reduce((acc, row) => {
                const value = row[selectedCatCol];
                acc[value] = (acc[value] || 0) + 1;
                return acc;
            }, {});

            const labels = Object.keys(valueCounts);
            const values = Object.values(valueCounts);
            const catNumUniqueValues = labels.length;

            if (catNumUniqueValues > 0) {
                if (catNumUniqueValues <= 10) { // Suitable for Bar, Pie, or Donut
                    let chartConfig;
                    let chartTitle = `Proportion of ${capitalize(selectedCatCol)}`;

                    switch (chartType) {
                        case "Bar Chart":
                            chartConfig = {
                                data: [{
                                    x: labels,
                                    y: values,
                                    type: 'bar',
                                    marker: {
                                        color: labels.map((_, i) => `hsl(${i * (360 / labels.length)}, 70%, 50%)`)
                                    }
                                }],
                                layout: {
                                    title: `Value Counts of ${capitalize(selectedCatCol)}`,
                                    xaxis: { title: capitalize(selectedCatCol) },
                                    yaxis: { title: 'Count' },
                                    height: 400,
                                    margin: { l: 60, r: 20, b: 60, t: 60 }
                                }
                            };
                            break;
                        case "Pie Chart":
                            chartConfig = {
                                data: [{
                                    values: values,
                                    labels: labels,
                                    type: 'pie',
                                    marker: {
                                        colors: labels.map((_, i) => `hsl(${i * (360 / labels.length)}, 70%, 50%)`)
                                    }
                                }],
                                layout: {
                                    title: chartTitle,
                                    height: 400,
                                    margin: { l: 20, r: 20, b: 20, t: 60 }
                                }
                            };
                            break;
                        case "Donut Chart":
                            chartConfig = {
                                data: [{
                                    values: values,
                                    labels: labels,
                                    type: 'pie',
                                    hole: 0.4,
                                    marker: {
                                        colors: labels.map((_, i) => `hsl(${i * (360 / labels.length)}, 70%, 50%)`)
                                    }
                                }],
                                layout: {
                                    title: chartTitle,
                                    height: 400,
                                    margin: { l: 20, r: 20, b: 20, t: 60 }
                                }
                            };
                            break;
                        default:
                            return null;
                    }

                    return (
                        <div className="mb-8 p-4 bg-blue-50 rounded-md">
                            <h4 className="text-lg font-semibold mb-2 flex items-center">
                                {chartType === "Bar Chart" && <BarChart className="mr-2" size={20} />}
                                {(chartType === "Pie Chart" || chartType === "Donut Chart") && <PieChart className="mr-2" size={20} />}
                                {chartType}: '{capitalize(selectedCatCol)}'
                            </h4>
                            <Plot
                                data={chartConfig.data}
                                layout={chartConfig.layout}
                                useResizeHandler
                                style={{ width: '100%', height: '100%' }}
                            />
                        </div>
                    );

                } else if (catNumUniqueValues < 50) { // Only Bar Chart for medium cardinality
                    const plotData = [{
                        x: labels,
                        y: values,
                        type: 'bar',
                        marker: {
                            color: labels.map((_, i) => `hsl(${i * (360 / labels.length)}, 70%, 50%)`)
                        }
                    }];
                    return (
                        <div className="mb-8 p-4 bg-blue-50 rounded-md">
                            <h4 className="text-lg font-semibold mb-2 flex items-center"><BarChart className="mr-2" size={20} /> Bar Chart for '{capitalize(selectedCatCol)}' (Medium Unique Values)</h4>
                            <Plot
                                data={plotData}
                                layout={{
                                    title: `Value Counts of ${capitalize(selectedCatCol)}`,
                                    xaxis: { title: capitalize(selectedCatCol) },
                                    yaxis: { title: 'Count' },
                                    height: 400,
                                    margin: { l: 60, r: 20, b: 60, t: 60 }
                                }}
                                useResizeHandler
                                style={{ width: '100%', height: '100%' }}
                            />
                            <p className="text-sm text-blue-700 mt-2">Using a Bar Chart for medium cardinality categorical data.</p>
                        </div>
                    );
                } else { // Too many unique values for visualization
                    const top10 = Object.entries(valueCounts)
                        .sort(([, countA], [, countB]) => countB - countA)
                        .slice(0, 10);
                    return (
                        <div className="mb-8 p-4 bg-yellow-50 rounded-md">
                            <Info className="inline-block mr-2" size={18} />
                            <p className="text-orange-700">Column '{selectedCatCol}' has too many unique values ({catNumUniqueValues}) for a chart. Displaying top 10 value counts:</p>
                            <ul className="list-disc list-inside mt-2 text-gray-700">
                                {top10.map(([val, count]) => (
                                    <li key={val}><strong>{val}:</strong> {count}</li>
                                ))}
                            </ul>
                        </div>
                    );
                }
            } else {
                return (
                    <div className="mb-8 p-4 bg-yellow-50 rounded-md">
                        <Info className="inline-block mr-2" size={18} />
                        <p className="text-orange-700">Column '{selectedCatCol}' has no unique values to display for visualization.</p>
                    </div>
                );
            }
        }
        return <p className="text-gray-600">Please select a column to visualize.</p>;
    };


    return (
        <div className="min-h-screen bg-gray-100 font-sans text-gray-900 flex">
            {/* Sidebar */}
            <aside className="w-64 bg-white p-6 shadow-lg flex-shrink-0">
                <h2 className="text-xl font-bold mb-6 text-blue-700 flex items-center">
                    <Database className="mr-2" /> DB Dashboard
                </h2>

                <div className="mb-6">
                    <h3 className="text-lg font-semibold mb-3 text-gray-800">Database Configuration</h3>
                    <input
                        type="text"
                        placeholder="Database Host"
                        value={dbHost}
                        onChange={(e) => setDbHost(e.target.value)}
                        className="w-full p-2 mb-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <input
                        type="text"
                        placeholder="Database Port"
                        value={dbPort}
                        onChange={(e) => setDbPort(e.target.value)}
                        className="w-full p-2 mb-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <input
                        type="text"
                        placeholder="Database Name"
                        value={dbName}
                        onChange={(e) => setDbName(e.target.value)}
                        className="w-full p-2 mb-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <input
                        type="text"
                        placeholder="Database User"
                        value={dbUser}
                        onChange={(e) => setDbUser(e.target.value)}
                        className="w-full p-2 mb-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <input
                        type="password"
                        placeholder="Database Password"
                        value={dbPassword}
                        onChange={(e) => setDbPassword(e.target.value)}
                        className="w-full p-2 mb-4 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <button
                        onClick={handleConnect}
                        className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 transition duration-300 ease-in-out shadow-md flex items-center justify-center"
                    >
                        {isConnected ? <Wifi className="mr-2" size={20} /> : <WifiOff className="mr-2" size={20} />}
                        {isConnected ? 'Connected' : 'Connect'}
                    </button>
                    {connectionMessage && (
                        <p className={`mt-2 text-sm ${isConnected ? 'text-green-600' : 'text-red-600'}`}>
                            {connectionMessage}
                        </p>
                    )}
                </div>

                {isConnected && (
                    <div className="mb-6 pt-4 border-t border-gray-200">
                        <h3 className="text-lg font-semibold mb-3 text-gray-800 flex items-center">
                            <Table className="mr-2" /> Table Selection
                        </h3>
                        <select
                            value={selectedTable}
                            onChange={(e) => setSelectedTable(e.target.value)}
                            className="w-full p-2 border border-gray-300 rounded-md bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                        >
                            {systemCatalogTables.map(table => (
                                <option key={table} value={table}>{table}</option>
                            ))}
                        </select>
                    </div>
                )}
            </aside>

            {/* Main Content */}
            <main className="flex-1 p-8 overflow-y-auto">
                <h1 className="text-3xl font-extrabold mb-6 text-gray-800">PostgreSQL System Catalog Dashboard</h1>
                <p className="text-lg text-gray-600 mb-8">
                    This application allows you to explore the PostgreSQL system catalog tables.
                    Connect to your database (simulated), select a table, and visualize its contents.
                </p>

                {isConnected && selectedTable && (
                    <div className="bg-white p-6 rounded-lg shadow-md mb-8">
                        <h2 className="text-2xl font-bold mb-4 text-blue-700 flex items-center">
                            <Table className="mr-2" /> Data from `{selectedTable}`
                        </h2>

                        {tableDescriptions[selectedTable] && (
                            <div className="bg-blue-50 p-4 rounded-lg mb-6 border border-blue-200">
                                <p className="font-bold text-blue-800 mb-1">Description:</p>
                                <p className="text-gray-700">{tableDescriptions[selectedTable].description}</p>
                                <div className="text-gray-700" dangerouslySetInnerHTML={{ __html: tableDescriptions[selectedTable].use_case }} />
                            </div>
                        )}

                        {loadingData ? (
                            <p className="text-blue-600 flex items-center">
                                <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                </svg>
                                Loading data for '{selectedTable}'...
                            </p>
                        ) : dataError ? (
                            <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
                                <strong className="font-bold">Error!</strong>
                                <span className="block sm:inline"> {dataError}</span>
                            </div>
                        ) : tableData.length > 0 ? (
                            <div className="overflow-x-auto rounded-lg border border-gray-200 shadow-sm">
                                <table className="min-w-full divide-y divide-gray-200">
                                    <thead className="bg-gray-50">
                                        <tr>
                                            {columns.map(col => (
                                                <th key={col} scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                    {capitalize(col)}
                                                </th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody className="bg-white divide-y divide-gray-200">
                                        {tableData.map((row, rowIndex) => (
                                            <tr key={rowIndex}>
                                                {columns.map(col => (
                                                    <td key={`${rowIndex}-${col}`} className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                                        {typeof row[col] === 'boolean' ? (row[col] ? 'True' : 'False') : row[col]}
                                                    </td>
                                                ))}
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        ) : (
                            <div className="bg-yellow-100 border border-yellow-400 text-yellow-700 px-4 py-3 rounded relative" role="alert">
                                <Info className="inline-block mr-2" size={18} />
                                <span className="block sm:inline">No data retrieved for the selected table, or the table is empty.</span>
                            </div>
                        )}
                    </div>
                )}

                {isConnected && selectedTable && tableData.length > 0 && (
                    <div className="bg-white p-6 rounded-lg shadow-md">
                        <h2 className="text-2xl font-bold mb-4 text-blue-700">Visualizations</h2>

                        {/* Numerical Column Visualizations */}
                        {numericalCols.length > 0 && (
                            <div className="mb-8">
                                <h3 className="text-xl font-semibold mb-3 text-gray-800 flex items-center">
                                    <BarChart className="mr-2" /> Numerical Column Insights
                                </h3>
                                <select
                                    value={selectedNumCol}
                                    onChange={(e) => setSelectedNumCol(e.target.value)}
                                    className="w-full md:w-1/2 p-2 mb-4 border border-gray-300 rounded-md bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                                >
                                    {numericalCols.map(col => (
                                        <option key={`num-${col}`} value={col}>{capitalize(col)}</option>
                                    ))}
                                </select>
                                {selectedNumCol ? renderChart() : <p className="text-gray-600">Please select a numerical column to visualize.</p>}
                            </div>
                        )}
                        {numericalCols.length === 0 && (
                            <div className="mb-8 p-4 bg-yellow-50 rounded-md">
                                <Info className="inline-block mr-2" size={18} />
                                <p className="text-orange-700">No suitable numerical columns (excluding 'oid') found for visualization.</p>
                            </div>
                        )}

                        {/* Categorical Column Visualizations */}
                        {categoricalCols.length > 0 && (
                            <div className="mb-8">
                                <h3 className="text-xl font-semibold mb-3 text-gray-800 flex items-center">
                                    <PieChart className="mr-2" /> Categorical Column Value Counts and Proportions
                                </h3>
                                <select
                                    value={selectedCatCol}
                                    onChange={(e) => setSelectedCatCol(e.target.value)}
                                    className="w-full md:w-1/2 p-2 mb-4 border border-gray-300 rounded-md bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                                >
                                    {categoricalCols.map(col => (
                                        <option key={`cat-${col}`} value={col}>{capitalize(col)}</option>
                                    ))}
                                </select>

                                {selectedCatCol && new Set(tableData.map(row => row[selectedCatCol])).size <= 10 && (
                                    <div className="flex flex-wrap gap-4 mb-4">
                                        <label className="inline-flex items-center">
                                            <input
                                                type="radio"
                                                className="form-radio text-blue-600"
                                                name="chartType"
                                                value="Bar Chart"
                                                checked={chartType === "Bar Chart"}
                                                onChange={() => setChartType("Bar Chart")}
                                            />
                                            <span className="ml-2">Bar Chart</span>
                                        </label>
                                        <label className="inline-flex items-center">
                                            <input
                                                type="radio"
                                                className="form-radio text-blue-600"
                                                name="chartType"
                                                value="Pie Chart"
                                                checked={chartType === "Pie Chart"}
                                                onChange={() => setChartType("Pie Chart")}
                                            />
                                            <span className="ml-2">Pie Chart</span>
                                        </label>
                                        <label className="inline-flex items-center">
                                            <input
                                                type="radio"
                                                className="form-radio text-blue-600"
                                                name="chartType"
                                                value="Donut Chart"
                                                checked={chartType === "Donut Chart"}
                                                onChange={() => setChartType("Donut Chart")}
                                            />
                                            <span className="ml-2">Donut Chart</span>
                                        </label>
                                    </div>
                                )}
                                {selectedCatCol ? renderChart() : <p className="text-gray-600">Please select a categorical column to visualize.</p>}
                            </div>
                        )}
                        {categoricalCols.length === 0 && (
                            <div className="mb-8 p-4 bg-yellow-50 rounded-md">
                                <Info className="inline-block mr-2" size={18} />
                                <p className="text-orange-700">No suitable categorical columns found for detailed visualizations.</p>
                            </div>
                        )}
                    </div>
                )}
            </main>
        </div>
    );
}

export default App;
