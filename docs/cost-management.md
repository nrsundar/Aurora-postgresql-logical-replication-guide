# Cost Management Guide

Understanding and managing AWS costs for PostgreSQL logical replication.

## Cost Breakdown

### RDS Instance Costs

**db.r6g.large Instances:**
- 2x db.r6g.large: $12-15/month
- Storage (20GB each): ~$4-6/month
- Backup storage: ~$2-3/month

**Total Estimated Monthly Cost: $30-36**

### Additional Costs

- **Data Transfer**: $0.09/GB for cross-AZ transfer
- **CloudWatch**: $0.30/metric/month for custom metrics
- **VPC Endpoints**: $0.01/hour per endpoint (if used)

## Cost Optimization Strategies

### 1. Instance Management

```bash
# Stop instances when not in use
aws rds stop-db-instance --db-instance-identifier postgresql-primary
aws rds stop-db-instance --db-instance-identifier postgresql-replica

# Start instances when needed
aws rds start-db-instance --db-instance-identifier postgresql-primary
aws rds start-db-instance --db-instance-identifier postgresql-replica
```

### 2. Automated Scheduling

Create Lambda function for automatic start/stop:

```python
import boto3
import json

def lambda_handler(event, context):
    rds = boto3.client('rds')
    action = event.get('action', 'stop')
    instances = ['postgresql-primary', 'postgresql-replica']
    
    for instance in instances:
        if action == 'stop':
            rds.stop_db_instance(DBInstanceIdentifier=instance)
        elif action == 'start':
            rds.start_db_instance(DBInstanceIdentifier=instance)
    
    return {
        'statusCode': 200,
        'body': json.dumps(f'Successfully {action}ped instances')
    }
```

### 3. Monitoring Setup

```bash
# Create billing alarm
aws cloudwatch put-metric-alarm \
  --alarm-name "PostgreSQL-Replication-Cost" \
  --alarm-description "Monitor PostgreSQL replication costs" \
  --metric-name EstimatedCharges \
  --namespace AWS/Billing \
  --statistic Maximum \
  --period 86400 \
  --threshold 50 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=Currency,Value=USD \
  --alarm-actions arn:aws:sns:us-east-1:123456789012:billing-alerts
```

## Daily Cost Tracking

### Using AWS CLI

```bash
# Get daily costs
aws ce get-cost-and-usage \
  --time-period Start=2024-01-01,End=2024-01-02 \
  --granularity DAILY \
  --metrics BlendedCost \
  --group-by Type=DIMENSION,Key=SERVICE

# Get RDS specific costs
aws ce get-cost-and-usage \
  --time-period Start=2024-01-01,End=2024-01-02 \
  --granularity DAILY \
  --metrics BlendedCost \
  --filter file://rds-filter.json
```

RDS filter file (`rds-filter.json`):

```json
{
  "Dimensions": {
    "Key": "SERVICE",
    "Values": ["Amazon Relational Database Service"]
  }
}
```

## Cost Alerts and Budgets

### Create Budget

```json
{
  "BudgetName": "PostgreSQL-Replication-Budget",
  "BudgetLimit": {
    "Amount": "50",
    "Unit": "USD"
  },
  "TimeUnit": "MONTHLY",
  "BudgetType": "COST",
  "CostFilters": {
    "Service": ["Amazon Relational Database Service"]
  }
}
```

### Budget Notifications

```json
{
  "Notification": {
    "NotificationType": "ACTUAL",
    "ComparisonOperator": "GREATER_THAN",
    "Threshold": 80,
    "ThresholdType": "PERCENTAGE"
  },
  "Subscribers": [
    {
      "SubscriptionType": "EMAIL",
      "Address": "your-email@example.com"
    }
  ]
}
```

## Resource Cleanup

### Automated Cleanup Script

```bash
#!/bin/bash

echo "Starting PostgreSQL replication cleanup..."

# Delete RDS instances
echo "Deleting RDS instances..."
aws rds delete-db-instance \
  --db-instance-identifier postgresql-primary \
  --skip-final-snapshot \
  --delete-automated-backups

aws rds delete-db-instance \
  --db-instance-identifier postgresql-replica \
  --skip-final-snapshot \
  --delete-automated-backups

# Wait for deletion
echo "Waiting for instances to be deleted..."
aws rds wait db-instance-deleted --db-instance-identifier postgresql-primary
aws rds wait db-instance-deleted --db-instance-identifier postgresql-replica

# Delete CloudFormation stack
echo "Deleting CloudFormation stack..."
aws cloudformation delete-stack --stack-name postgresql-replication

# Wait for stack deletion
aws cloudformation wait stack-delete-complete --stack-name postgresql-replication

echo "Cleanup completed!"
```

### Manual Cleanup Checklist

- [ ] Stop/Delete RDS instances
- [ ] Delete CloudFormation stacks
- [ ] Remove VPC and associated resources
- [ ] Delete CloudWatch alarms
- [ ] Remove IAM roles and policies
- [ ] Clear S3 buckets (if any)
- [ ] Cancel reserved instances (if applicable)

## Cost-Saving Tips

### 1. Development Environment

- Use `db.t3.micro` for learning
- Stop instances overnight
- Delete when not actively learning

### 2. Production Considerations

- Use Reserved Instances for 24/7 workloads
- Consider Aurora for high availability needs
- Implement proper backup retention policies

### 3. Network Costs

- Keep primary and replica in same AZ when possible
- Use VPC endpoints to avoid internet charges
- Monitor cross-region transfer if using multi-region setup

## Free Tier Usage

AWS Free Tier includes:
- 750 hours of `db.t2.micro` or `db.t3.micro`
- 20GB of storage
- 20GB of backup storage

**Note**: This covers only ONE instance in free tier.

## Cost Monitoring Dashboard

Create custom CloudWatch dashboard:

```json
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", "postgresql-primary"],
          ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", "postgresql-replica"]
        ],
        "period": 300,
        "stat": "Average",
        "region": "us-east-1",
        "title": "RDS CPU Utilization"
      }
    },
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/Billing", "EstimatedCharges", "Currency", "USD"]
        ],
        "period": 86400,
        "stat": "Maximum",
        "region": "us-east-1",
        "title": "Estimated Charges"
      }
    }
  ]
}
```

## Emergency Cost Controls

### Immediate Actions

1. **Stop all instances**:
   ```bash
   aws rds stop-db-instance --db-instance-identifier postgresql-primary
   aws rds stop-db-instance --db-instance-identifier postgresql-replica
   ```

2. **Delete stacks**:
   ```bash
   aws cloudformation delete-stack --stack-name postgresql-replication
   ```

3. **Set spending limits** (if available in your account type)

### Contact AWS Support

If unexpected charges occur:
- Open support case immediately
- Provide detailed timeline of actions
- Request cost analysis
- Ask about potential credits for learning purposes

---

**Remember**: Always monitor your AWS billing dashboard and set up alerts!

---

This completes the cost management guide. Always prioritize cost monitoring when learning with cloud resources.
