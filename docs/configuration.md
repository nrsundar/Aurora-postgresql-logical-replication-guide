# Configuration Guide

Step-by-step instructions for configuring PostgreSQL logical replication.

## Overview

This guide covers the complete setup process for logical replication between two PostgreSQL instances on AWS RDS.

## Prerequisites

- Completed setup from `setup-guide.md`
- Two RDS instances running
- Database connectivity verified

## Step 1: Configure Primary Database

### Enable Logical Replication

Connect to the primary database:

```bash
psql -h <primary-endpoint> -U postgres -d postgres
```

Verify replication settings:

```sql
-- Check current WAL level
SHOW wal_level;

-- Check replication parameters
SHOW max_replication_slots;
SHOW max_wal_senders;
```

### Create Replication User

```sql
-- Create replication user
CREATE USER replicator WITH REPLICATION LOGIN PASSWORD 'your-secure-password';

-- Grant necessary permissions
GRANT CONNECT ON DATABASE replication_demo TO replicator;
GRANT USAGE ON SCHEMA public TO replicator;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO replicator;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO replicator;

-- Grant permissions for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO replicator;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON SEQUENCES TO replicator;
```

### Create Sample Data

```sql
-- Create test table
CREATE TABLE employees (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    department VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert sample data
INSERT INTO employees (name, email, department) VALUES
    ('John Doe', 'john.doe@example.com', 'Engineering'),
    ('Jane Smith', 'jane.smith@example.com', 'Marketing'),
    ('Bob Johnson', 'bob.johnson@example.com', 'Sales');
```

### Create Publication

```sql
-- Create publication for all tables
CREATE PUBLICATION my_publication FOR ALL TABLES;

-- Verify publication
SELECT * FROM pg_publication;
SELECT * FROM pg_publication_tables;
```

## Step 2: Configure Replica Database

Connect to the replica database:

```bash
psql -h <replica-endpoint> -U postgres -d replication_demo
```

### Create Schema Structure

```sql
-- Create the same table structure (without data)
CREATE TABLE employees (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    department VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Create Subscription

```sql
-- Create subscription
CREATE SUBSCRIPTION my_subscription 
CONNECTION 'host=<primary-endpoint> port=5432 dbname=replication_demo user=replicator password=your-secure-password sslmode=require'
PUBLICATION my_publication;

-- Verify subscription
SELECT * FROM pg_subscription;
SELECT * FROM pg_stat_subscription;
```

## Step 3: Verify Replication

### Check Replication Status

On the primary:

```sql
-- Check replication slots
SELECT slot_name, plugin, slot_type, database, active FROM pg_replication_slots;

-- Check WAL sender processes
SELECT * FROM pg_stat_replication;
```

On the replica:

```sql
-- Check subscription status
SELECT subname, pid, received_lsn, latest_end_lsn, latest_end_time 
FROM pg_stat_subscription;

-- Verify data replication
SELECT COUNT(*) FROM employees;
```

### Test Data Replication

Insert new data on primary:

```sql
-- On primary
INSERT INTO employees (name, email, department) 
VALUES ('Test User', 'test@example.com', 'QA');
```

Check replication on replica:

```sql
-- On replica
SELECT * FROM employees WHERE email = 'test@example.com';
```

## Step 4: Monitor Replication

### Key Metrics to Monitor

```sql
-- Replication lag
SELECT 
    subname,
    pid,
    received_lsn,
    latest_end_lsn,
    latest_end_time,
    last_msg_send_time,
    last_msg_receipt_time
FROM pg_stat_subscription;

-- Replication slot lag
SELECT 
    slot_name,
    plugin,
    database,
    active,
    pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)) as lag_size
FROM pg_replication_slots;
```

### Set Up Monitoring Alerts

Create CloudWatch alarms for:
- Replication lag
- Disk space usage
- Connection count
- CPU utilization

## Step 5: Handle Schema Changes

### Adding New Tables

On primary:

```sql
-- Create new table
CREATE TABLE departments (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    manager VARCHAR(100)
);

-- Add to publication
ALTER PUBLICATION my_publication ADD TABLE departments;
```

On replica:

```sql
-- Create same table structure
CREATE TABLE departments (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    manager VARCHAR(100)
);

-- Refresh subscription
ALTER SUBSCRIPTION my_subscription REFRESH PUBLICATION;
```

### Handling DDL Changes

Logical replication does not replicate DDL changes. You must:

1. Apply DDL changes to replica first
2. Apply DDL changes to primary
3. Refresh subscription if needed

## Troubleshooting

### Common Issues

1. **Subscription stuck in 'initialize' state**
   - Check network connectivity
   - Verify user permissions
   - Check publication exists

2. **Replication lag increasing**
   - Monitor system resources
   - Check for long-running transactions
   - Consider increasing worker processes

3. **Connection errors**
   - Verify security group settings
   - Check SSL requirements
   - Validate connection string

### Useful Commands

```sql
-- Drop and recreate subscription
DROP SUBSCRIPTION my_subscription;
CREATE SUBSCRIPTION my_subscription 
CONNECTION '...' PUBLICATION my_publication;

-- Disable/enable subscription
ALTER SUBSCRIPTION my_subscription DISABLE;
ALTER SUBSCRIPTION my_subscription ENABLE;

-- Check worker processes
SELECT * FROM pg_stat_activity WHERE application_name LIKE '%logical%';
```

## Best Practices

1. **Security**
   - Use SSL connections
   - Limit replication user permissions
   - Regular password rotation

2. **Performance**
   - Monitor replication lag
   - Tune worker processes
   - Use appropriate instance sizes

3. **Maintenance**
   - Regular monitoring setup
   - Backup strategy
   - Disaster recovery planning

---

Next: Continue to `troubleshooting.md` for common issues and solutions.
