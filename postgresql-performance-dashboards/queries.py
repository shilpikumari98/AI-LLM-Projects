# queries.py

sql1 = ['''SELECT pid,(now()-pg_stat_activity.query_start) AS duration,query,state FROM pg_stat_activity 
            WHERE (now() - pg_stat_activity.query_start) > interval '1 minutes'; ''']

sql2 = ['''SELECT table_schema || '.' || table_name AS TableName, 
            pg_size_pretty(pg_total_relation_size('"' || table_schema || '"."' || table_name || '"')) AS 
            TableSize FROM information_schema.tables ORDER BY 
            pg_total_relation_size('"' || table_schema || '"."' || table_name || '"') DESC;''']

sql3 = ['''SELECT TableName,pg_size_pretty(pg_table_size(TableName)) AS TableSize,pg_size_pretty(pg_indexes_size(TableName)) 
            AS IndexSize,pg_size_pretty(pg_total_relation_size(TableName)) AS TotalSize FROM 
            (SELECT ('"' || table_schema || '"."' || table_name || '"') AS TableName FROM information_schema.tables ) AS 
            Tables ORDER BY 4 DESC;''']

sql4 = ["SELECT now(), txid_current();",
        "SELECT * FROM pg_stat_database;",
        "SELECT pg_sleep(10);",
        "SELECT now(), txid_current();",
        "SELECT * FROM pg_stat_database;",
        "SELECT * from pg_stat_statements order by shared_blks_hit;",
        "SELECT * from pg_stat_statements order by shared_blks_read;",
        "SELECT * from pg_stat_statements order by rows;",
        "SELECT * from pg_stat_statements order by  ( total_plan_time + total_exec_time );",
        "SELECT relname, indexrelname, idx_scan, idx_tup_read, idx_tup_fetch FROM \
            pg_stat_all_indexes ORDER BY idx_tup_fetch DESC LIMIT 10;",
        "SELECT relname, indexrelname, idx_scan, idx_tup_read, idx_tup_fetch FROM \
            pg_stat_all_indexes ORDER BY idx_scan DESC LIMIT 10;",
        "SELECT relname, indexrelname, idx_scan, idx_tup_read, idx_tup_fetch FROM \
            pg_stat_all_indexes ORDER BY idx_tup_read DESC LIMIT 10;",
        "SELECT relid::regclass, seq_scan, seq_tup_read, idx_scan, idx_tup_fetch FROM \
            pg_stat_all_tables ORDER BY seq_scan DESC LIMIT 10;",
        "SELECT relid::regclass, seq_scan, seq_tup_read, idx_scan, idx_tup_fetch FROM \
            pg_stat_all_tables ORDER BY seq_tup_read DESC LIMIT 10;",
        "SELECT relid::regclass, seq_scan, seq_tup_read, idx_scan, idx_tup_fetch FROM \
            pg_stat_all_tables ORDER BY idx_scan DESC LIMIT 10;",
        "SELECT relid::regclass, seq_scan, seq_tup_read, idx_scan, idx_tup_fetch FROM \
            pg_stat_all_tables ORDER BY idx_tup_fetch DESC LIMIT 10;",
       "SELECT schemaname,  relname, seq_scan, idx_scan,\
                   CASE WHEN (seq_scan + idx_scan) <> 0 \
                    THEN 100.0 * idx_scan / (seq_scan + idx_scan) \
                    ELSE 0 \
                    END AS percent_of_index_usage,\
                   n_live_tup AS rows_in_table, idx_tup_fetch /* CASE WHEN seq_scan <> 0 THEN (seq_tup_read/ seq_scan) ELSE 0  END AS  avg_num_rows_each_seq_scan_read */ \
                   FROM pg_stat_user_tables \
                   ORDER BY n_live_tup DESC;"]

sql5 = ["""
    SELECT 
        n.nspname AS schemaname,
        t.relname,
        t.last_vacuum,
        t.last_autovacuum,
        t.last_analyze,
        t.last_autoanalyze
    FROM pg_stat_all_tables t
    JOIN pg_class c ON c.relname = t.relname
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
    ORDER BY n.nspname, t.relname;
    """]

# sql5 = ["SELECT relname,last_vacuum,last_autovacuum,last_analyze,last_autoanalyze from pg_stat_all_tables;"]

sql6 = ["SELECT pid, wait_event_type, wait_event FROM pg_stat_activity WHERE wait_event is NOT NULL;"]

sql7 = ["SELECT CASE WHEN pg_last_wal_receive_lsn() = pg_last_wal_replay_lsn() THEN 0 ELSE EXTRACT \
            (EPOCH FROM now() - pg_last_xact_replay_timestamp()) END AS log_delay;"]

sql8 = ["SELECT client_addr, pg_wal_lsn_diff(pg_stat_replication.sent_lsn, pg_stat_replication.replay_lsn) AS \
             byte_lag  FROM pg_stat_replication;"]

sql9 = ["SELECT c.relname, count(*) AS buffers FROM pg_buffercache b INNER JOIN pg_class c \
            ON b.relfilenode = pg_relation_filenode(c.oid) AND b.reldatabase IN \
            (0, (SELECT oid FROM pg_database  WHERE datname = current_database())) GROUP BY c.relname ORDER BY 2 DESC LIMIT 10;"]

sql10 = ["SELECT schema_name, sum(table_size)* 0.00000095 size_in_mb \
            /* commented the below stats you may use if requried */ \
            /* (sum(table_size) / database_size) * 100 as percentage_of_schema_size_in_db */ \
            FROM ( \
            SELECT pg_catalog.pg_namespace.nspname as schema_name, \
            pg_relation_size(pg_catalog.pg_class.oid) as table_size, \
            sum(pg_relation_size(pg_catalog.pg_class.oid)) over () as database_size \
            FROM pg_catalog.pg_class \
            JOIN pg_catalog.pg_namespace ON relnamespace = pg_catalog.pg_namespace.oid) t \
            GROUP BY schema_name;"]

sql11 = ["SELECT * from pg_replication_slots;"]

sql12 = ["SELECT datname, datfrozenxid, age(datfrozenxid) ,datminmxid from pg_database order by datname ;",
        "SELECT oid::regclass, relfrozenxid, age(relfrozenxid), txid_current() FROM pg_class WHERE NOT relfrozenxid = '0' \
            ORDER BY age(relfrozenxid) DESC LIMIT 10;"]

sql13 = [
        "SELECT blocked_locks.pid AS blocked_pid,\
        blocked_activity.usename AS blocked_user,\
        blocking_locks.pid AS blocking_pid,\
        blocking_activity.usename AS blocking_user,\
        blocked_activity.query AS blocked_statement,\
        blocking_activity.query AS current_statement_in_blocking_process,\
        blocked_activity.application_name AS blocked_application,\
        blocking_activity.application_name AS blocking_application \
        FROM pg_catalog.pg_locks blocked_locks \
        JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid \
        JOIN pg_catalog.pg_locks blocking_locks \
        ON blocking_locks.locktype = blocked_locks.locktype \
        AND blocking_locks.DATABASE IS NOT DISTINCT FROM blocked_locks.DATABASE \
        AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation \
        AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page \
        AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple \
        AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid \
        AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid \
        AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid \
        AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid \
        AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid \
        AND blocking_locks.pid != blocked_locks.pid JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid \
        WHERE NOT blocked_locks.GRANTED;"
        ]

sql14 = [
    "select * from pgstattuple('pg_catalog.pg_proc');"
]

sql15=[
    "SELECT \
	pg_database.datname AS database_name, \
	COUNT(pg_stat_activity.datid) AS num_sessions \
    FROM pg_database \
    LEFT JOIN \
	pg_stat_activity ON pg_database.oid = pg_stat_activity.datid \
    GROUP BY \
	pg_database.oid \
    ORDER BY \
	num_sessions DESC;"
]

sql16=[
    "SELECT \
     pid, \
     usename, \
     application_name, \
     state \
    FROM \
     pg_stat_activity \
    WHERE \
     state IN ('active', 'disabled', 'fast path', 'idle', 'idle in transaction');"
     ]

sql17=[
        "SELECT \
            pg_stat_activity.pid, \
            pg_stat_activity.usename, \
            pg_stat_activity.query, \
            pg_locks.mode \
        FROM \
            pg_stat_activity \
        JOIN \
            pg_locks ON pg_stat_activity.pid = pg_locks.pid \
        WHERE \
            pg_locks.mode IN ( \
                'RowExclusiveLock', \
                'ShareUpdateExclusiveLock', \
                'ShareRowExclusiveLock', \
                'ExclusiveLock', \
                'AccessExclusiveLock' \
  );"
  ]

sql18 = ["""
SELECT 
    query,
    calls,
    CASE 
        WHEN calls = 0 THEN 0 
        ELSE total_exec_time / NULLIF(calls, 0) 
    END AS time_per_call,
    CASE 
        WHEN total_exec_time = 0 THEN 0 
        ELSE calls / NULLIF(total_exec_time, 0) 
    END AS calls_per_second,
    CASE 
        WHEN total_exec_time = 0 THEN 0 
        ELSE rows / NULLIF(total_exec_time, 0) 
    END AS rows_per_second,
    total_exec_time,
    rows
FROM 
    pg_stat_statements 
ORDER BY 
    total_exec_time DESC 
LIMIT 30;
"""]

# sql18 = ["""
#     SELECT 
#         query,
#         calls,
#         CASE 
#             WHEN calls = 0 THEN 0 
#             ELSE total_exec_time / NULLIF(calls, 0) 
#         END AS time_per_call,
#         CASE 
#             WHEN total_exec_time = 0 THEN 0 
#             ELSE calls / NULLIF(total_exec_time, 0) 
#         END AS calls_per_second,
#         CASE 
#             WHEN total_exec_time = 0 THEN 0 
#             ELSE rows / NULLIF(total_exec_time, 0) 
#         END AS rows_per_second,
#         CASE 
#             WHEN calls = 0 THEN 0 
#             ELSE (total_exec_time / NULLIF(calls, 0)) * 1000 
#         END AS cpu_time_per_second,
#         CASE 
#             WHEN total_exec_time = 0 THEN 0 
#             ELSE (blk_read_time + blk_write_time) / NULLIF(total_exec_time, 0) 
#         END AS io_time_per_second,
#         CASE 
#             WHEN total_exec_time = 0 THEN 0 
#             ELSE (shared_blks_dirtied + local_blks_dirtied) / NULLIF(total_exec_time, 0) 
#         END AS dirtied_blocks_per_second
#     FROM 
#         pg_stat_statements 
#     ORDER BY 
#         total_exec_time DESC 
#     LIMIT 30;
# """]

sql19 = ["""
    WITH config_lines AS (
        SELECT 
            '# ' || category || ' Settings' as section,
            name || ' = ' || quote_literal(setting) || 
            CASE 
                WHEN unit IS NOT NULL THEN ' ' || unit 
                ELSE '' 
            END as setting_line
        FROM pg_settings 
        WHERE source = 'configuration file'
    )
    SELECT setting_line as "postgresql.conf"
    FROM config_lines
    ORDER BY section, setting_line;
"""]

# sql20 = ["""
#     WITH vacuum_stats AS (
#         VACUUM VERBOSE ANALYZE;
#         SELECT 
#             schemaname, 
#             relname as table_name,
#             last_vacuum,
#             last_autovacuum,
#             vacuum_count,
#             autovacuum_count
#         FROM pg_stat_all_tables 
#         WHERE schemaname NOT IN ('pg_toast', 'pg_catalog')
#         ORDER BY last_vacuum DESC NULLS LAST
#     )
#     SELECT * FROM vacuum_stats;
# """]

sql20=["SELECT \
    schemaname, \
    relname AS table_name, \
    last_vacuum, \
    last_autovacuum, \
    vacuum_count, \
    autovacuum_count \
FROM  \
    pg_stat_all_tables  \
WHERE \
    schemaname NOT IN ('pg_toast', 'pg_catalog') \
ORDER BY \
    last_vacuum DESC NULLS LAST;"
]

sql21=["""
       SELECT 
    schemaname, 
    relname AS table_name,
    last_vacuum,
    last_autovacuum,
    vacuum_count,
    autovacuum_count
FROM 
    pg_stat_all_tables 
WHERE 
    schemaname NOT IN ('pg_toast', 'pg_catalog')
    AND relname = 'orders'  -- Replace 'orders' with any table to analyze
ORDER BY \
    last_vacuum DESC NULLS LAST; """
       ]

sql23=["SELECT \
        c.relname AS table_name, \
        pg_size_pretty(count(*) * 8192) AS buffer_size, \
        count(*) AS num_buffers, \
        round(100.0 * count(*) / (SELECT setting::numeric FROM pg_settings WHERE name = 'shared_buffers'), 2) AS buffer_percentage, \
        CASE \
            WHEN count(*) > 1 THEN 'yes' \
            ELSE 'no' \
        END AS is_multiple_buffers \
        FROM \
        pg_buffercache b \
        INNER JOIN pg_class c ON b.relfilenode = c.relfilenode \
        GROUP BY \
        c.relname \
        ORDER BY \
        count(*) DESC;"
        ]

sql24="iostat -xm 1"

sql25=["SELECT \
       pid,  \
       usename, \
       application_name,\
       client_addr, \
       client_port, \
       query_start, \
       backend_start, \
       now() - query_start AS query_duration, \
       now() - backend_start AS total_duration \
       FROM pg_stat_activity \
       WHERE state = 'active';"
       ]

# sql26=[
#     "SELECT \
#     userid, \
#     dbid, \
#     queryid, \
#     calls, \
#     total_exec_time, \
#     rows, \
#     query \
#     FROM \
#     pg_stat_statements \
#     WHERE \
#     query ~* 'commit' \
#     ORDER BY \
#     calls DESC \
#     LIMIT 10; "
#     ]

sql26=[
    " SELECT \
        r.rolname AS username, \
        d.datname AS database_name,\
        s.queryid,\
        s.calls, \
        s.total_exec_time,\
        s.rows, \
        s.query \
    FROM pg_stat_statements s \
    JOIN pg_roles r ON s.userid = r.oid \
    JOIN pg_database d ON s.dbid::oid = d.oid  -- ✅ Fix: Explicit cast to OID \
    WHERE s.query ILIKE '%commit%' \
    ORDER BY s.calls DESC  \
    LIMIT 10; "
]

sql27=[
        "SELECT\
        query, \
        calls, \
        total_exec_time, \
        rows, \
        blk_read_time, \
        shared_blks_read, \
        shared_blks_hit \
        FROM \
        pg_stat_statements \
        WHERE \
        blk_read_time IS NOT NULL \
        ORDER BY \
        blk_read_time DESC \
        LIMIT 10;"
]

sql28=[
    "SELECT \
    query, \
    calls, \
    total_exec_time, \
    rows, \
    blk_write_time, \
    shared_blks_written \
    FROM \
    pg_stat_statements \
    WHERE \
    blk_write_time IS NOT NULL \
    ORDER BY\
    blk_write_time DESC \
    LIMIT 10;"
]

sql29="top -b -n 1 -p $(pgrep -d',' -o postgres)"

sql30=["top -c -p $(pgrep -o postgres)","free -h"]

sql31="iostat -d -x 1"

# sql32=["SELECT \
#         table_schema, \
#         table_name, \
#         pg_size_pretty(pg_total_relation_size(table_schema || '.' || table_name)) AS total_size \
#         FROM \
#         information_schema.tables \
#         ORDER BY \
#         total_size DESC \
#         LIMIT 10;"
#         ]

sql32=["SELECT \
    nspname AS schema_name, \
    relname AS table_name, \
    pg_size_pretty(pg_total_relation_size(pg_class.oid)) AS total_size, \
    pg_total_relation_size(pg_class.oid) AS size_bytes  -- Raw size for sortingn \
FROM \
    pg_class \
JOIN \
    pg_namespace ON pg_class.relnamespace = pg_namespace.oid \
WHERE \
    pg_total_relation_size(pg_class.oid) > 0  -- Exclude empty tables \
ORDER BY \
    size_bytes DESC \
LIMIT 10; "
]


# sql33=["SELECT \
#         table_schema, \
#         table_name, \
#         pg_size_pretty(pg_total_relation_size(table_schema || '.' || table_name)) AS total_size \
#         FROM \
#         information_schema.tables \
#         ORDER BY \
#         table_schema, \
#         table_name;"
#     ]

sql33 = [
    "SELECT table_schema, table_name, pg_total_relation_size(table_schema || '.' || table_name) AS total_size_bytes  \
    FROM information_schema.tables \
    ORDER BY total_size_bytes DESC;"
]

sql34=[
    "SELECT \
        application_name, \
        client_addr, \
        state, \
        sync_state, \
        sent_lsn,  \
        write_lsn, \
        flush_lsn, \
        replay_lsn \
        FROM \
        pg_stat_replication;",
        
    "SELECT\
        pid, \
        sender_host,  \
        status, \
        latest_end_lsn, \
        written_lsn, \
        flushed_lsn \
        FROM \
        pg_stat_wal_receiver;"
        ]

sql35=[
        "SELECT \
            pid, \
            usename, \
            application_name, \
            state, \
            state_change, \
            now() - pg_stat_activity.query_start AS duration \
            FROM \
            pg_stat_activity \
            WHERE \
            state = 'active' AND now() - pg_stat_activity.query_start > interval '5 minutes' \
            ORDER BY \
            duration DESC;"
        ] 

sql36=[
        "SELECT \
        indexrelid::regclass AS index_name, \
        pg_size_pretty(pg_total_relation_size(indexrelid)) AS index_size \
        FROM \
        pg_stat_user_indexes \
        WHERE \
        idx_scan = 0;"
        ] 

sql37=[
        " SELECT \
        wait_event, \
        wait_event_type \
        FROM \
        pg_stat_activity \
        ORDER BY \
        wait_event_type;"
    ]

sql38=[
        "SELECT \
        datname, \
        pg_size_pretty(pg_database_size(datname)) AS total_size, \
        pg_database_size(datname) AS size_in_bytes \
        FROM pg_database \
        ORDER BY size_in_bytes DESC;"
    ]

sql39=[
        "SELECT \
        current_database() AS current_database, \
        version() AS postgres_version, \
        pg_is_in_recovery() AS in_recovery, \
        pg_postmaster_start_time() AS postmaster_start_time, \
        pg_stat_reset() AS statistics_reset;"
    ]

sql40=[
        "SELECT \
        now() AS current_time, \
        pg_stat_get_db_xact_commit(pg_database_size(current_database())) \
        AS total_commits, \
        pg_stat_get_db_xact_rollback(pg_database_size(current_database())) \
        AS total_rollbacks;"
    ]

sql41=[
        "SELECT \
        datname, \
        pg_size_pretty(pg_database_size(datname)) \
        AS total_database_size \
        FROM pg_database;"
    ]

sql42=[
        "SELECT \
        MAX(CASE WHEN name = 'max_connections' THEN setting::integer END) \
        AS max_connections, \
        MAX(CASE WHEN name = 'wal_level' THEN setting END) \
        AS wal_level,\
        MAX(CASE WHEN name = 'max_wal_senders' THEN setting::integer END) \
        AS max_wal_senders, \
        MAX(CASE WHEN name = 'wal_level' THEN setting END) \
        AS current_wal_senders \
        FROM pg_settings \
        WHERE name IN ('max_connections', 'wal_level', 'max_wal_senders');"
    ]

sql43=[
    "SELECT \
    application_name, \
    state, \
    sync_state, \
    sent_lsn, \
    write_lsn, \
    flush_lsn, \
    replay_lsn \
    FROM \
    pg_stat_replication;" 
]

sql44=[
        "SELECT \
        datname, \
        pg_size_pretty(pg_database_size(datname)) AS database_size, \
        pg_database_size(datname) AS size_in_bytes \
        FROM pg_database \
        WHERE datistemplate = false \
        ORDER BY size_in_bytes DESC;" 
    ]

# 45 and 46 used for IntelliDB Diag and IntelliDB tuning#

sql47=[
    "SELECT \
    name AS guc_parameter, \
    setting AS current_value \
    FROM \
    pg_settings \
    ORDER BY \
    name;" 
]

sql48=[
    """
    SELECT
    name AS guc_parameter,
    setting AS current_value
    FROM
    pg_settings
    WHERE
    name IN 
    ('effective_cache_size', 'maintenance_work_mem', 'max_wal_size', 'shared_buffers', 'work_mem');
    """
]

sql49="""
Below is the recommendation BY IntelliDB Xpert:
-------------------------------------------------------------
 -- Set the values in the configuration file
-- Adjust the paths and filenames based on your PostgreSQL installation
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET effective_cache_size = '4653MB';
ALTER SYSTEM SET enable_seqscan = on;
ALTER SYSTEM SET fsync = on;
ALTER SYSTEM SET full_page_writes = on;
ALTER SYSTEM SET max_wal_size = '84MB';
ALTER SYSTEM SET maintenance_work_mem = '524MB';
ALTER SYSTEM SET shared_buffers = '1474MB';

-- Reload the configuration to apply changes without restarting PostgreSQL
SELECT pg_reload_conf();
Please note the following:

--The ALTER SYSTEM commands are written to the PostgreSQL configuration file. The exact 
path to this file can vary based on your PostgreSQL installation. In the example above,
it's assumed to be the default configuration file.

--The pg_reload_conf() function is used to reload the configuration file without restarting PostgreSQL. This function 
is available in PostgreSQL versions 9.4 and later.

--Ensure you have the necessary permissions to modify the PostgreSQL configuration file.

--Remember that changes to certain parameters, such as shared_buffers, may 
require a PostgreSQL restart to take effect.

--Make sure to back up your PostgreSQL configuration file before making changes, and 
thoroughly test any configuration changes in a safe environment before applying them to a production system.

--Or Make changes in postgresql.conf File , You can copy and paste the tuning recommendations 
in the conf format into the postgresql.conf file:

checkpoint_completion_target = 0.9
effective_cache_size = '4653 MB'
enable_seqscan = on
fsync = on
full_page_writes = on
max_wal_size = '84MB'
maintenance_work_mem = '524 MB'
shared_buffers = '1474 MB'

--Recomended GUCs
GUC Category   					Recommendation   
autovacuum         		        on
checkpoint_completion_target    0.9
enable_async_append             on
enable_bitmapscan               on
enable_gathermerge              on
enable_group_by_reordering      on
enable_hashagg                  on
enable_hashjoin                 on
enable_incremental_sort         on 
enable_indexonlyscan            on
enable_indexscan                on
enable_material                 on
enable_memoize                  on 
enable_mergejoin                on
enable_nestloop                 on
enable_parallel_append          on 
enable_parallel_hash            on 
enable_partition_pruning        on 
enable_partitionwise_aggregate  on
enable_partitionwise_join       on
enable_seqscan                  on
enable_sort                     on
enable_tidscan                  on
fsync static                    on
full_page_writes                on
log_checkpoints                 on
parallel_leader_participation   on
seq_page_cost                   1.0
track_activities                on
track_counts                    on
zero_damaged_pages              on
-------------------------------------------------------------
"""

sql50=["""SELECT
        wait_event_type AS event,
        count(*) AS wait_count,
        sum(COALESCE(EXTRACT(epoch FROM now() - state_change), 0)) AS total_time,
        sum(COALESCE(EXTRACT(epoch FROM now() - state_change), 0)) / count(*) AS avg_wait_time
        FROM
        pg_stat_activity
        WHERE
        wait_event_type IS NOT NULL
        GROUP BY
        wait_event_type
        ORDER BY
        total_time DESC
        LIMIT 10;"""
    ]

sql51=[
    """
    SELECT
    state,
    count(*) AS wait_count,
    sum(COALESCE(EXTRACT(epoch FROM now() - state_change), 0)) AS total_time,
    sum(COALESCE(EXTRACT(epoch FROM now() - state_change), 0)) / count(*) AS avg_wait_time
    FROM
    pg_stat_activity
    WHERE
    state IS NOT NULL
    GROUP BY
    state
    ORDER BY
    total_time DESC
    LIMIT 10;"""
]

sql52=[
    """
    SELECT * FROM pg_stat_activity 
    WHERE state LIKE 'idle in transaction%' OR state LIKE 'active'
    OR  state LIKE 'idle' OR  state LIKE 'active';
    """
]

sql53=[
    """
    SELECT
    relation::regclass,
    transactionid,
    mode,
    granted
    FROM
    pg_locks;
    """
]

sql54=[
    """
    SELECT
    COUNT(*) AS buffer_io_waits
    FROM
    pg_stat_bgwriter
    WHERE
    checkpoints_timed + checkpoints_req > 0;
    """
]

sql55=[
    """
    SELECT
    pid,
    usename,
    query,
    state,
    now() - pg_stat_activity.query_start AS duration
    FROM
    pg_stat_activity
    WHERE
    state = 'active' AND now() - pg_stat_activity.query_start > interval '5 minutes'
    ORDER BY
    duration DESC;
    """
]
sqlA = ["""
    SELECT 
        to_char(total_exec_time, '999999.99') as execution_time,
        to_char(calls, '999999') as call_count,
        to_char(rows, '999999') as row_count,
        substring(query, 1, 100) as query_text
    FROM pg_stat_statements 
    WHERE query NOT LIKE '%pg_stat_statements%'
    ORDER BY total_exec_time DESC 
    LIMIT 5;
"""]

sqlB=[
    "SELECT \
    pid, \
    usename, \
    application_name, \
    state, \
    state_change, \
    now() - pg_stat_activity.query_start AS duration \
    FROM \
    pg_stat_activity \
    WHERE \
    state = 'active' AND now() - pg_stat_activity.query_start > interval '5 minutes' \
    ORDER BY \
    duration DESC;"
    ]

sqlC=[
    "SELECT \
    table_schema, \
    table_name, \
    pg_size_pretty(pg_total_relation_size(table_schema || '.' || table_name)) AS total_size \
    FROM \
    information_schema.tables \
    ORDER BY \
    total_size DESC \
    LIMIT 10;"
]

# sqlD=[
#     "SELECT \
#     round( (pg_stat_bgwriter.buffers_checkpoint + pg_stat_bgwriter.buffers_clean) / NULLIF(pg_stat_bgwriter.buffers_alloc, 0) * 100.0, 2 ) \
#     AS buffer_cache_hit_ratio \
#     FROM pg_stat_bgwriter;"
# ]

sqlD=[
"""
SELECT
    datname,
    ROUND(100.0 * blks_hit / NULLIF(blks_hit + blks_read, 0), 2) AS buffer_cache_hit_ratio
FROM
    pg_stat_database
ORDER BY
    datname;
"""
]

# sqlE=[
#     "SELECT\
#     checkpoints_timed, \
#     checkpoints_req, \
#     checkpoint_write_time, \
#     checkpoint_sync_time \
#     FROM \
#     pg_stat_bgwriter;"
# ]

sqlE=["""
     SELECT
    num_timed AS checkpoints_timed,
    num_requested AS checkpoints_req,
    write_time AS checkpoint_write_time,
    sync_time AS checkpoint_sync_time
FROM
    pg_stat_checkpointer;
""" ]

# Lock Analysis
sqlF = ["""
    SELECT 
        pid,
        usename,
        application_name,
        state,
        to_char(query_start, 'YYYY-MM-DD HH24:MI:SS') as query_start_time,
        substring(query, 1, 100) as query_text
    FROM pg_stat_activity 
    WHERE state IN ('idle in transaction', 'active', 'idle')
    ORDER BY query_start;
"""]

# Vacuum Analysis
sqlG = ["""
    SELECT 
        schemaname,
        relname,
        to_char(last_vacuum, 'YYYY-MM-DD HH24:MI:SS') as last_vacuum_time,
        to_char(last_autovacuum, 'YYYY-MM-DD HH24:MI:SS') as last_autovacuum_time,
        to_char(vacuum_count, '999999') as vacuum_count,
        to_char(autovacuum_count, '999999') as autovacuum_count
    FROM pg_stat_all_tables 
    WHERE last_autovacuum IS NOT NULL 
    ORDER BY last_autovacuum DESC 
    LIMIT 5;
"""]

sqlH = ["""
    SELECT 
        relname as table_name,
        CAST(heap_blks_hit::float / NULLIF(heap_blks_hit + heap_blks_read, 0) * 100 AS numeric(10,2)) as hit_ratio
    FROM pg_statio_user_tables 
    WHERE heap_blks_hit + heap_blks_read > 0 
    ORDER BY hit_ratio DESC
    LIMIT 10;
"""]


# Growth Analysis
# sqlI = ["""
#     SELECT 
#         t.table_name,
#         pg_size_pretty(pg_total_relation_size(quote_ident(t.table_name)::regclass)) as total_size,
#         pg_size_pretty(pg_relation_size(quote_ident(t.table_name)::regclass)) as data_size,
#         pg_size_pretty(pg_indexes_size(quote_ident(t.table_name)::regclass)) as index_size,
#         to_char(s.n_live_tup, '999,999,999') as row_count,
#         to_char(s.last_analyze, 'YYYY-MM-DD HH24:MI:SS') as last_analyze_time
#     FROM information_schema.tables t
#     JOIN pg_stat_user_tables s ON t.table_name = s.relname
#     WHERE t.table_schema = 'public'
#     ORDER BY pg_total_relation_size(quote_ident(t.table_name)::regclass) DESC;
# """]

sqlI=[
   """
   SELECT
    table_name,
    pg_size_pretty(total_size) AS total_size,
    pg_size_pretty(data_size) AS data_size,
    pg_size_pretty(index_size) AS index_size,
    pg_size_pretty(toast_size) AS toast_size,
    pg_size_pretty(table_size) AS table_size,
    row_count,
    pg_size_pretty(size_increase) AS size_increase,
    last_analyze,
    last_autoanalyze
    FROM (
        SELECT
            table_name,
            total_size,
            data_size,
            index_size,
            toast_size,
            table_size,
            row_count,
            LAG(table_size) OVER (PARTITION BY table_name ORDER BY last_analyze) AS prev_table_size,
            table_size - LAG(table_size) OVER (PARTITION BY table_name ORDER BY last_analyze) AS size_increase,
            last_analyze,
            last_autoanalyze
        FROM (
            SELECT
                table_name,
                pg_total_relation_size(table_name::regclass) AS total_size,
                pg_relation_size(table_name::regclass) AS data_size,
                pg_indexes_size(table_name::regclass) AS index_size,
                pg_total_relation_size(table_name::regclass) - pg_relation_size(table_name::regclass) - pg_indexes_size(table_name::regclass) AS toast_size,
                pg_total_relation_size(table_name::regclass) - pg_indexes_size(table_name::regclass) AS table_size,
                pg_table_size(table_name::regclass) AS row_count,
                last_analyze,
                last_autoanalyze
            FROM
                information_schema.tables
            LEFT JOIN
                pg_stat_all_tables
                ON information_schema.tables.table_name = pg_stat_all_tables.relname
            WHERE
                table_schema = 'public' -- Adjust schema as needed
        ) AS table_stats
    ) AS size_changes
    ORDER BY
        size_increase DESC NULLS LAST;
   """
]
############END OF IntelliDB Diag Queries##############


#Following queries are for IntelliDB Tuning (option 46)#
tune_sqlA = ["""
    SELECT 
        ui.schemaname,
        ui.relname as tablename,
        ui.indexrelname as indexname,
        ui.idx_scan,
        pg_size_pretty(pg_total_relation_size(quote_ident(ui.schemaname) || '.' || quote_ident(ui.relname))) as table_size
    FROM pg_stat_user_indexes ui
    JOIN pg_class c ON ui.indexrelid = c.oid
    WHERE ui.idx_scan = 0 
    AND ui.schemaname NOT IN ('pg_catalog', 'pg_toast')
    AND c.relkind = 'i'
    AND pg_total_relation_size(quote_ident(ui.schemaname) || '.' || quote_ident(ui.relname)) > 0
    ORDER BY pg_total_relation_size(quote_ident(ui.schemaname) || '.' || quote_ident(ui.relname)) DESC;
"""]

tune_sqlA=[ """
SELECT
    schemaname,
    relname AS table_name,
    indexrelname AS index_name,
    idx_scan AS index_scans,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM
    pg_stat_all_indexes
WHERE
    idx_scan = 0  -- No scans performed using the index
    AND schemaname NOT IN ('pg_catalog', 'information_schema')  -- Exclude system schemas
ORDER BY
    pg_relation_size(indexrelid) DESC;
"""
]

tune_sqlB = ["""
    SELECT 
        schemaname,
        relname as table_name,
        indexrelname as index_name,
        idx_scan,
        idx_tup_read,
        idx_tup_fetch,
        pg_size_pretty(pg_relation_size(indexrelid)) as index_size,
        'DROP INDEX IF EXISTS ' || quote_ident(schemaname) || '.' || quote_ident(indexrelname) || ';' as drop_command
    FROM pg_stat_user_indexes
    WHERE schemaname NOT IN ('pg_catalog', 'pg_toast')
    ORDER BY idx_scan ASC, pg_relation_size(indexrelid) DESC;
"""]

tune_sqlC = ["""
    SELECT 
        schemaname, 
        relname as table_name,
        last_vacuum,
        last_analyze,
        n_live_tup as live_rows,
        n_dead_tup as dead_rows,
        pg_size_pretty(pg_total_relation_size(schemaname || '.' || relname)) as table_size
    FROM pg_stat_user_tables 
    WHERE schemaname NOT IN ('pg_catalog', 'pg_toast')
    ORDER BY n_dead_tup DESC;
"""]

tune_sqlD = ["""
    SELECT 
        blocked_locks.pid AS blocked_pid,
        blocked_activity.usename AS blocked_user,
        blocking_locks.pid AS blocking_pid,
        blocking_activity.usename AS blocking_user,
        blocked_activity.query AS blocked_query,
        blocking_activity.query AS blocking_query,
        now() - blocked_activity.query_start AS blocked_duration
    FROM pg_locks blocked_locks
    JOIN pg_stat_activity blocked_activity ON blocked_locks.pid = blocked_activity.pid
    JOIN pg_locks blocking_locks 
        ON blocked_locks.locktype = blocking_locks.locktype
        AND blocked_locks.database IS NOT DISTINCT FROM blocking_locks.database
        AND blocked_locks.relation IS NOT DISTINCT FROM blocking_locks.relation
        AND blocked_locks.page IS NOT DISTINCT FROM blocking_locks.page
        AND blocked_locks.tuple IS NOT DISTINCT FROM blocking_locks.tuple
        AND blocked_locks.virtualxid IS NOT DISTINCT FROM blocking_locks.virtualxid
        AND blocked_locks.transactionid IS NOT DISTINCT FROM blocking_locks.transactionid
        AND blocked_locks.classid IS NOT DISTINCT FROM blocking_locks.classid
        AND blocked_locks.objid IS NOT DISTINCT FROM blocking_locks.objid
        AND blocked_locks.objsubid IS NOT DISTINCT FROM blocking_locks.objsubid
        AND blocked_locks.pid != blocking_locks.pid
    JOIN pg_stat_activity blocking_activity ON blocking_locks.pid = blocking_activity.pid
    WHERE NOT blocked_locks.granted
    ORDER BY blocked_duration DESC;
"""]

# Checksum Analysis Queries
sql56 = [
    """
    SELECT 
        name,
        setting,
        unit,
        context,
        source,
        boot_val as default_value,
        pending_restart,
        category,
        short_desc
    FROM pg_settings 
    WHERE name LIKE '%checksum%'
    ORDER BY name;
    """,
    
    """
    SELECT 
        current_setting('data_checksums') as data_checksums_enabled,
        current_setting('ignore_checksum_failure') as ignore_checksum_failure,
        version() as postgresql_version
    FROM pg_settings 
    LIMIT 1;
    """
]

# Auto Explain Analysis Queries
sql57 = [
    """
    SELECT 
        name,
        setting,
        unit,
        context,
        short_desc
    FROM pg_settings
    WHERE name LIKE 'auto_explain%'
    ORDER BY name;
    """,
    
    """
    SELECT 
        queryid,
        query,
        calls,
        total_exec_time,
        mean_exec_time,
        rows,
        shared_blks_hit + shared_blks_read as total_blocks
    FROM pg_stat_statements
    ORDER BY total_exec_time DESC
    LIMIT 10;
    """
]
