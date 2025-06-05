# Aurora PostgreSQL Logical Replication Troubleshooting Guide

Advanced troubleshooting for Aurora PostgreSQL logical replication - Within Region Setup.

## Aurora Cluster Connection Issues

### Cannot Connect to Aurora Cluster

**Symptoms:**
- Connection timeout to cluster endpoints
- "Connection refused" errors
- DNS resolution failures for cluster endpoints

**Aurora-Specific Solutions:**

1. **Check Aurora Cluster Status**
   ```bash
   aws rds describe-db-clusters \
     --db-cluster-identifier <cluster-id>
   ```

2. **Verify Cluster Endpoints**
   ```bash
   # Check writer endpoint
   aws rds describe-db-clusters \
     --db-cluster-identifier <cluster-id> \
     --query 'DBClusters[0].Endpoint'
   
   # Check reader endpoint
   aws rds describe-db-clusters \
     --db-cluster-identifier <cluster-id> \
     --query 'DBClusters[0].ReaderEndpoint'
   ```

3. **Aurora Instance Health Check**
   ```bash
   aws rds describe-db-instances \
     --filters Name=db-cluster-id,Values=<cluster-id>
   ```

4. **Security Group Validation**
   ```bash
   aws ec2 describe-security-groups \
     --group-ids <aurora-security-group-id> \
     --query 'SecurityGroups[0].IpPermissions'
   ```



### SSL Connection Issues

**Symptoms:**
- SSL handshake failures
- Certificate verification errors

**Solutions:**

1. **Download RDS Certificate**
   ```bash
   wget https://s3.amazonaws.com/rds-downloads/rds-ca-2019-root.pem
   ```

2. **Connect with SSL**
   ```bash
   psql "host=<endpoint> port=5432 dbname=postgres user=postgres sslmode=require sslrootcert=rds-ca-2019-root.pem"
   ```

## Replication Issues

### Logical Replication Not Working

**Symptoms:**
- Data not replicating
- Subscription status shows "disabled"

**Solutions:**

1. **Check WAL Level**
   ```sql
   SHOW wal_level;
   -- Should be 'logical'
   ```

2. **Verify Replication Slots**
   ```sql
   SELECT * FROM pg_replication_slots;
   ```

3. **Check Publication Status**
   ```sql
   SELECT * FROM pg_publication;
   SELECT * FROM pg_publication_tables;
   ```

4. **Verify Subscription**
   ```sql
   SELECT * FROM pg_subscription;
   SELECT * FROM pg_stat_subscription;
   ```

### Subscription Creation Fails

**Symptoms:**
- "could not connect to publisher" errors
- Authentication failures

**Solutions:**

1. **Check Network Connectivity**
   ```bash
   # From replica instance
   telnet <primary-endpoint> 5432
   ```

2. **Verify User Permissions**
   ```sql
   -- On primary
   GRANT REPLICATION ON DATABASE <dbname> TO <user>;
   GRANT USAGE ON SCHEMA public TO <user>;
   GRANT SELECT ON ALL TABLES IN SCHEMA public TO <user>;
   ```

3. **Check pg_hba.conf Settings**
   - RDS automatically configures this
   - Verify security groups allow connection

## Performance Issues

### High Replication Lag

**Symptoms:**
- `pg_stat_subscription` shows high lag
- Data appears slowly on replica

**Solutions:**

1. **Monitor Replication Statistics**
   ```sql
   SELECT 
     subname,
     received_lsn,
     latest_end_lsn,
     latest_end_time,
     last_msg_send_time,
     last_msg_receipt_time
   FROM pg_stat_subscription;
   ```

2. **Check Resource Utilization**
   - Monitor CPU and memory on both instances
   - Check disk I/O performance
   - Review CloudWatch metrics

3. **Tune Parameters**
   ```sql
   -- Increase worker processes
   ALTER SYSTEM SET max_logical_replication_workers = 8;
   
   -- Increase worker memory
   ALTER SYSTEM SET work_mem = '256MB';
   ```

### High CPU Usage

**Symptoms:**
- CloudWatch shows sustained high CPU
- Query performance degradation

**Solutions:**

1. **Identify Resource-Intensive Queries**
   ```sql
   SELECT 
     query,
     calls,
     total_time,
     mean_time
   FROM pg_stat_statements
   ORDER BY total_time DESC
   LIMIT 10;
   ```

2. **Consider Instance Scaling**
   - Upgrade to larger instance class
   - Use Multi-AZ for read replicas

## CloudFormation Issues


### Stack Creation Fails

**Common Causes:**
- Insufficient IAM permissions
- Resource limits exceeded
- Invalid parameter values

**Solutions:**

1. **Check CloudFormation Events**
   ```bash
   aws cloudformation describe-stack-events \
     --stack-name postgresql-replication
   ```

2. **Validate Template**
   ```bash
   aws cloudformation validate-template \
     --template-body file://cloudformation/infrastructure.yaml
   ```

3. **Review IAM Permissions**
   ```bash
   aws iam simulate-principal-policy \
     --policy-source-arn <your-user-arn> \
     --action-names cloudformation:CreateStack \
     --resource-arns '*'
   ```

### Resource Already Exists Errors

**Solutions:**

1. **Use Different Stack Name**
2. **Delete Existing Resources**
3. **Import Existing Resources**


## Monitoring and Logging

### Enable Enhanced Monitoring

```bash
aws rds modify-db-instance \
  --db-instance-identifier <instance-id> \
  --monitoring-interval 60 \
  --monitoring-role-arn <role-arn>
```

### CloudWatch Log Groups

Monitor these log groups:
- `/aws/rds/instance/<instance-id>/postgresql`
- `/aws/rds/instance/<instance-id>/upgrade`

### Key Metrics to Watch

1. **Database Connections**
2. **CPU Utilization**
3. **Free Storage Space**
4. **Read/Write IOPS**
5. **Replication Lag**

## Cost-Related Issues

### Unexpected Charges

**Common Causes:**
- Instances running longer than expected
- High IOPS usage
- Cross-AZ data transfer

**Solutions:**

1. **Set Up Billing Alerts**
   ```bash
   aws budgets create-budget \
     --account-id <account-id> \
     --budget file://budget.json
   ```

2. **Use Cost Explorer**
   - Identify cost drivers
   - Set up cost anomaly detection

3. **Clean Up Resources**
   ```bash
   ./scripts/cleanup.sh
   ```

## Emergency Procedures

### Complete Cleanup

If you need to remove everything immediately:

```bash
# Delete CloudFormation stack
aws cloudformation delete-stack \
  --stack-name postgresql-replication

# Wait for deletion
aws cloudformation wait stack-delete-complete \
  --stack-name postgresql-replication

# Verify no resources remain
aws rds describe-db-instances
aws ec2 describe-vpcs --filters Name=tag:Project,Values=PostgreSQLReplication
```

### Data Recovery

If you lose important data:

1. **Check RDS Snapshots**
   ```bash
   aws rds describe-db-snapshots \
     --db-instance-identifier <instance-id>
   ```

2. **Point-in-Time Recovery**
   ```bash
   aws rds restore-db-instance-to-point-in-time \
     --source-db-instance-identifier <source> \
     --target-db-instance-identifier <target> \
     --restore-time <timestamp>
   ```

## Getting Help

### AWS Support

- Use AWS Support Console
- Check AWS Service Health Dashboard
- Review AWS documentation

### Community Resources

- PostgreSQL mailing lists
- AWS forums
- Stack Overflow (tag: postgresql, aws-rds)

### Logs and Diagnostics

Always collect:
- CloudFormation events
- RDS logs
- Application logs
- Network traces (if applicable)

---

**Remember**: When in doubt, err on the side of caution and clean up resources to avoid charges!
