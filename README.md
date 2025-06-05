# Aurora PostgreSQL Logical Replication Guide

A comprehensive educational guide for setting up Aurora PostgreSQL logical replication on AWS - Within Region Setup.

## 🎯 Learning Objectives

- Master Aurora PostgreSQL logical replication concepts
- Deploy Aurora clusters with within-region replication
- Configure publications and subscriptions for cluster architectures
- Monitor Aurora replication performance and lag
- Implement Aurora-specific best practices and troubleshooting
- Understand single-region networking

## 📋 Prerequisites

- AWS Account with Aurora PostgreSQL permissions
- AWS CLI configured with appropriate IAM roles
- PostgreSQL knowledge (intermediate to advanced level)
- Understanding of Aurora cluster architecture
- VPC networking fundamentals

## 🚀 Quick Start

1. **Clone this repository**
   ```bash
   git clone https://github.com/yourusername/aurora-postgresql-logical-replication-guide.git
   cd aurora-postgresql-logical-replication-guide
   ```

2. **Review the prerequisites**
   - Check `docs/setup-guide.md` for detailed setup instructions
   - Ensure your AWS account has the necessary permissions

3. **Deploy infrastructure**
   
   ```bash
   aws cloudformation create-stack \
     --stack-name postgresql-replication \
     --template-body file://cloudformation/infrastructure.yaml \
     --parameters file://cloudformation/parameters.json \
     --capabilities CAPABILITY_IAM
   ```
   

4. **Follow the step-by-step tutorial**
   - Start with `docs/configuration.md`
   - Execute SQL scripts in `scripts/`
   - Test replication using provided Python scripts

## ⚠️ Cost Warning

This guide provisions AWS resources that **incur charges**:

- **Estimated Monthly Cost**: $15-30 USD for t3.micro instances
- **Components**: 2x RDS instances, VPC, subnets, security groups
- **Important**: Always run cleanup scripts when finished learning

### Cost Management

1. **Monitor your AWS billing dashboard**
2. **Set up billing alerts**
3. **Use the provided cleanup scripts**:
   ```bash
   ./scripts/cleanup.sh
   ```

## 📚 Documentation Structure

- `docs/setup-guide.md` - Initial setup and prerequisites
- `docs/configuration.md` - Step-by-step configuration
- **🚨 `docs/troubleshooting.md` - Aurora PostgreSQL troubleshooting guide**
- `docs/cost-management.md` - Cost optimization strategies

## 🔧 Quick Help

**Need help?** Check **docs/troubleshooting.md** for solutions to:
- Aurora cluster connection issues
- Single-region networking problems
- Logical replication setup failures
- Aurora parameter configuration problems
- Performance and replication lag monitoring

## 🔧 Scripts

- `scripts/setup-replication.sql` - Database configuration scripts
- `scripts/test-replication.py` - Automated testing and validation
- `scripts/monitoring.py` - Replication monitoring tools
- `scripts/cleanup.sh` - Resource cleanup automation


## ☁️ Infrastructure

- `cloudformation/infrastructure.yaml` - Main infrastructure template
- `cloudformation/iam-roles.yaml` - IAM roles and policies
- `cloudformation/parameters.json` - Environment-specific parameters



## 📊 Architecture Diagrams

- `diagrams/architecture.svg` - Overall system architecture
- `diagrams/replication-flow.svg` - Data replication flow
- `diagrams/network-diagram.svg` - Network topology


## 🎓 Learning Path

1. **Conceptual Understanding** (30 minutes)
   - Read about logical replication concepts
   - Understand publications and subscriptions

2. **Infrastructure Setup** (45 minutes)
   - Deploy AWS resources
   - Configure networking and security

3. **Database Configuration** (60 minutes)
   - Configure primary database
   - Set up replica database
   - Create publications and subscriptions

4. **Testing and Validation** (30 minutes)
   - Run test scripts
   - Verify data replication
   - Monitor performance

5. **Cleanup** (15 minutes)
   - Remove AWS resources
   - Verify cost implications

## 🔍 Troubleshooting

Common issues and solutions are documented in `docs/troubleshooting.md`.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Educational Disclaimer

This guide is for educational purposes only. While it follows AWS best practices, always:

- Review security configurations for production use
- Implement proper backup strategies
- Follow your organization's compliance requirements
- Test thoroughly in non-production environments

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📞 Support

- Create an issue for bug reports or feature requests
- Check the troubleshooting guide first
- Join our community discussions

---

**Remember**: This creates real AWS resources with real costs. Always clean up when finished!
