# Setup Guide

This guide will walk you through setting up PostgreSQL logical replication on AWS RDS.

## Prerequisites

### AWS Account Requirements

- Active AWS account with billing enabled
- IAM user with appropriate permissions
- AWS CLI installed and configured

### Required AWS Permissions

Your IAM user needs the following permissions:
- `rds:*`
- `ec2:*` (for VPC and security groups)
- `iam:*` (for creating service roles)
- `cloudformation:*` (if using CloudFormation)

### Local Environment

- PostgreSQL client tools (`psql`)
- Python 3.8+ (for testing scripts)
- AWS CLI v2
- Git

## Step 1: AWS CLI Configuration

```bash
aws configure
# Enter your Access Key ID
# Enter your Secret Access Key
# Enter your default region: us-east-1
# Enter default output format: json
```

Verify configuration:
```bash
aws sts get-caller-identity
```

## Step 2: Clone Repository

```bash
git clone <repository-url>
cd aurora-postgresql-logical-replication-guide
```

## Step 3: Environment Preparation

### Install Python Dependencies

```bash
pip install -r requirements.txt
```

### Set Environment Variables

Create a `.env` file:
```bash
AWS_REGION=us-east-1
DB_INSTANCE_CLASS=db.r6g.large
DB_NAME=replication_demo
DB_USERNAME=postgres
DB_PASSWORD=your-secure-password
```

## Step 4: Infrastructure Deployment


### Using CloudFormation (Recommended)

```bash
# Deploy the main infrastructure
aws cloudformation create-stack \
  --stack-name postgresql-replication \
  --template-body file://cloudformation/infrastructure.yaml \
  --parameters file://cloudformation/parameters.json \
  --capabilities CAPABILITY_IAM \
  --region us-east-1

# Wait for completion
aws cloudformation wait stack-create-complete \
  --stack-name postgresql-replication \
  --region us-east-1
```

### Get Connection Information

```bash
# Get primary endpoint
aws cloudformation describe-stacks \
  --stack-name postgresql-replication \
  --query 'Stacks[0].Outputs[?OutputKey==`PrimaryEndpoint`].OutputValue' \
  --output text

# Get replica endpoint
aws cloudformation describe-stacks \
  --stack-name postgresql-replication \
  --query 'Stacks[0].Outputs[?OutputKey==`ReplicaEndpoint`].OutputValue' \
  --output text
```


## Step 5: Verify Deployment

### Test Database Connections

```bash
# Test primary connection
psql -h <primary-endpoint> -U postgres -d postgres

# Test replica connection
psql -h <replica-endpoint> -U postgres -d postgres
```

### Check Instance Status

```bash
aws rds describe-db-instances \
  --query 'DBInstances[?DBInstanceStatus!=`available`]'
```

## Step 6: Security Configuration

### Parameter Groups

Ensure the following parameters are set:
- `wal_level = logical`
- `max_replication_slots = 10`
- `max_wal_senders = 10`
- `shared_preload_libraries = 'pg_stat_statements'`

### Network Security

- Limit security group access to your IP
- Use SSL connections in production
- Consider using VPC endpoints for internal communication

## Cost Considerations

### Estimated Monthly Costs (us-east-1)

- 2x db.r6g.large: ~$20-25
- Storage (20GB each): ~$4-6
- Backup storage: ~$2-3
- **Total**: ~$26-34 per month

### Cost Optimization

1. **Stop instances when not in use**
2. **Use reserved instances for long-term learning**
3. **Monitor billing alerts**
4. **Clean up resources promptly**

## Next Steps

1. Continue to `docs/configuration.md`
2. Set up logical replication
3. Test the configuration
4. Explore monitoring capabilities

## Troubleshooting

If you encounter issues:
1. Check AWS CloudFormation events
2. Verify IAM permissions
3. Review VPC and security group settings
4. Consult `docs/troubleshooting.md`

---

**Important**: Keep track of your AWS resources to avoid unexpected charges!
