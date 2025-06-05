-- PostgreSQL Logical Replication Setup Scripts
-- Region: us-east-1
-- Instance Type: db.r6g.large

-- =============================================
-- PRIMARY DATABASE CONFIGURATION
-- =============================================

-- Step 1: Verify replication parameters
-- These should already be set via parameter group
SHOW wal_level;          -- Should be 'logical'
SHOW max_replication_slots;  -- Should be >= 10
SHOW max_wal_senders;        -- Should be >= 10

-- Step 2: Create replication user
CREATE USER replicator WITH REPLICATION LOGIN PASSWORD 'ReplicationPass123!';

-- Step 3: Grant necessary permissions
GRANT CONNECT ON DATABASE replication_demo TO replicator;
GRANT USAGE ON SCHEMA public TO replicator;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO replicator;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO replicator;

-- Grant permissions for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO replicator;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON SEQUENCES TO replicator;

-- Step 4: Create sample schema and data
CREATE TABLE IF NOT EXISTS employees (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    department VARCHAR(50),
    salary DECIMAL(10,2),
    hire_date DATE DEFAULT CURRENT_DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS departments (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    manager VARCHAR(100),
    budget DECIMAL(12,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    department_id INTEGER REFERENCES departments(id),
    start_date DATE,
    end_date DATE,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert sample data
INSERT INTO departments (name, manager, budget) VALUES
    ('Engineering', 'Alice Johnson', 500000.00),
    ('Marketing', 'Bob Smith', 200000.00),
    ('Sales', 'Carol Williams', 300000.00),
    ('HR', 'David Brown', 150000.00)
ON CONFLICT (name) DO NOTHING;

INSERT INTO employees (name, email, department, salary, hire_date) VALUES
    ('John Doe', 'john.doe@company.com', 'Engineering', 85000.00, '2023-01-15'),
    ('Jane Smith', 'jane.smith@company.com', 'Marketing', 65000.00, '2023-02-01'),
    ('Mike Johnson', 'mike.johnson@company.com', 'Engineering', 90000.00, '2023-01-20'),
    ('Sarah Wilson', 'sarah.wilson@company.com', 'Sales', 70000.00, '2023-03-10'),
    ('Tom Davis', 'tom.davis@company.com', 'HR', 60000.00, '2023-02-15')
ON CONFLICT (email) DO NOTHING;

INSERT INTO projects (name, description, department_id, start_date, status) VALUES
    ('Database Migration', 'Migrate legacy systems to PostgreSQL', 1, '2024-01-01', 'active'),
    ('Marketing Campaign Q1', 'Digital marketing campaign for Q1', 2, '2024-01-15', 'active'),
    ('Sales Automation', 'Implement CRM automation tools', 3, '2024-02-01', 'planning')
ON CONFLICT DO NOTHING;

-- Step 5: Create publication for all tables
CREATE PUBLICATION my_publication FOR ALL TABLES;

-- Verify publication
SELECT * FROM pg_publication;
SELECT schemaname, tablename FROM pg_publication_tables WHERE pubname = 'my_publication';

-- Step 6: Check replication slots (will be created by subscription)
SELECT slot_name, plugin, slot_type, database, active, restart_lsn 
FROM pg_replication_slots;

-- =============================================
-- REPLICA DATABASE CONFIGURATION
-- =============================================

-- Run these commands on the REPLICA database

-- Step 1: Create the same schema structure (without data)
CREATE TABLE IF NOT EXISTS employees (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    department VARCHAR(50),
    salary DECIMAL(10,2),
    hire_date DATE DEFAULT CURRENT_DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS departments (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    manager VARCHAR(100),
    budget DECIMAL(12,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    department_id INTEGER REFERENCES departments(id),
    start_date DATE,
    end_date DATE,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Step 2: Create subscription
-- Replace <PRIMARY_ENDPOINT> with your actual primary RDS endpoint
CREATE SUBSCRIPTION my_subscription 
CONNECTION 'host=<PRIMARY_ENDPOINT> port=5432 dbname=replication_demo user=replicator password=ReplicationPass123! sslmode=require'
PUBLICATION my_publication;

-- Step 3: Verify subscription
SELECT subname, pid, received_lsn, latest_end_lsn, latest_end_time 
FROM pg_stat_subscription;

SELECT * FROM pg_subscription;

-- =============================================
-- MONITORING AND VERIFICATION QUERIES
-- =============================================

-- Run on PRIMARY: Check WAL sender processes
SELECT application_name, client_addr, state, sent_lsn, write_lsn, flush_lsn, replay_lsn, sync_state
FROM pg_stat_replication;

-- Run on PRIMARY: Check replication slots
SELECT slot_name, plugin, slot_type, database, active, 
       pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)) as lag_size,
       pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), confirmed_flush_lsn)) as flush_lag
FROM pg_replication_slots;

-- Run on REPLICA: Check subscription worker
SELECT subname, pid, received_lsn, latest_end_lsn, latest_end_time,
       last_msg_send_time, last_msg_receipt_time,
       CASE WHEN latest_end_time IS NOT NULL 
            THEN EXTRACT(EPOCH FROM (now() - latest_end_time))
            ELSE NULL END as lag_seconds
FROM pg_stat_subscription;

-- Run on REPLICA: Verify data replication
SELECT 'employees' as table_name, COUNT(*) as row_count FROM employees
UNION ALL
SELECT 'departments' as table_name, COUNT(*) as row_count FROM departments
UNION ALL
SELECT 'projects' as table_name, COUNT(*) as row_count FROM projects;

-- =============================================
-- TEST DATA INSERTION (Run on PRIMARY)
-- =============================================

-- Insert test data to verify replication
INSERT INTO employees (name, email, department, salary) VALUES
    ('Test User 1', 'test1@company.com', 'Engineering', 75000.00),
    ('Test User 2', 'test2@company.com', 'Marketing', 68000.00);

-- Update existing record
UPDATE employees SET salary = salary * 1.05 WHERE department = 'Engineering';

-- Delete a record
DELETE FROM employees WHERE email = 'test1@company.com';

-- =============================================
-- TROUBLESHOOTING QUERIES
-- =============================================

-- Check for replication conflicts (run on replica)
SELECT * FROM pg_stat_subscription_stats;

-- Check worker processes
SELECT pid, application_name, client_addr, state, query 
FROM pg_stat_activity 
WHERE application_name LIKE '%logical%' OR query LIKE '%logical%';

-- Check system resource usage
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- =============================================
-- CLEANUP PROCEDURES
-- =============================================

-- To remove replication (run in order):

-- 1. On REPLICA: Drop subscription
-- DROP SUBSCRIPTION IF EXISTS my_subscription;

-- 2. On PRIMARY: Drop publication
-- DROP PUBLICATION IF EXISTS my_publication;

-- 3. On PRIMARY: Drop replication user
-- DROP USER IF EXISTS replicator;

-- 4. Clean up test tables if needed
-- DROP TABLE IF EXISTS projects;
-- DROP TABLE IF EXISTS employees;
-- DROP TABLE IF EXISTS departments;

-- =============================================
-- PERFORMANCE TUNING PARAMETERS
-- =============================================

-- These parameters can be tuned based on your workload:
-- 
-- max_logical_replication_workers = 4
-- max_sync_workers_per_subscription = 2
-- logical_decoding_work_mem = 64MB
-- max_slot_wal_keep_size = 1GB
-- wal_receiver_timeout = 60s
-- wal_sender_timeout = 60s

-- Monitor these views for performance:
-- pg_stat_replication
-- pg_stat_subscription
-- pg_replication_slots
-- pg_stat_wal_receiver
