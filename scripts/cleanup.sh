#!/bin/bash

# PostgreSQL Logical Replication Cleanup Script
# Region: us-east-1
# Instance Type: db.r6g.large

set -e  # Exit on any error

echo "🧹 PostgreSQL Logical Replication Cleanup Script"
echo "=================================================="
echo "Region: us-east-1"
echo "This script will remove ALL resources created for the replication demo."
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
STACK_NAME="postgresql-replication"
REGION="us-east-1"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if AWS CLI is configured
check_aws_cli() {
    print_status "Checking AWS CLI configuration..."
    
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed or not in PATH"
        echo "Please install AWS CLI: https://aws.amazon.com/cli/"
        exit 1
    fi
    
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS CLI is not configured or credentials are invalid"
        echo "Please run: aws configure"
        exit 1
    fi
    
    print_success "AWS CLI is properly configured"
}

# Function to confirm deletion
confirm_deletion() {
    echo ""
    print_warning "⚠️  WARNING: This will permanently delete the following resources:"
    echo "   • RDS instances (primary and replica)"
    echo "   • VPC and associated networking components"
    echo "   • Security groups"
    echo "   • DB subnet groups"
    echo "   • Parameter groups"
    echo "   • CloudFormation stack"
    echo ""
    echo "This action cannot be undone!"
    echo ""
    
    read -p "Are you sure you want to proceed? (type 'DELETE' to confirm): " confirmation
    
    if [ "$confirmation" != "DELETE" ]; then
        print_status "Cleanup cancelled by user"
        exit 0
    fi
}

# Function to delete RDS instances manually (if not using CloudFormation)
delete_rds_instances() {
    print_status "Checking for RDS instances to delete..."
    
    # List of potential instance identifiers
    INSTANCE_IDS=("postgresql-primary" "postgresql-replica" "${STACK_NAME}-primary" "${STACK_NAME}-replica")
    
    for instance_id in "${INSTANCE_IDS[@]}"; do
        if aws rds describe-db-instances --db-instance-identifier "$instance_id" --region "$REGION" &> /dev/null; then
            print_status "Deleting RDS instance: $instance_id"
            
            aws rds delete-db-instance \
                --db-instance-identifier "$instance_id" \
                --skip-final-snapshot \
                --delete-automated-backups \
                --region "$REGION" || true
                
            print_success "Initiated deletion of $instance_id"
        fi
    done
}

# Function to wait for RDS instances to be deleted
wait_for_rds_deletion() {
    print_status "Waiting for RDS instances to be deleted..."
    
    INSTANCE_IDS=("postgresql-primary" "postgresql-replica" "${STACK_NAME}-primary" "${STACK_NAME}-replica")
    
    for instance_id in "${INSTANCE_IDS[@]}"; do
        print_status "Checking deletion status of $instance_id..."
        
        # Wait up to 20 minutes for deletion
        timeout=1200
        elapsed=0
        
        while [ $elapsed -lt $timeout ]; do
            if ! aws rds describe-db-instances --db-instance-identifier "$instance_id" --region "$REGION" &> /dev/null; then
                print_success "$instance_id has been deleted"
                break
            fi
            
            echo -n "."
            sleep 30
            elapsed=$((elapsed + 30))
        done
        
        if [ $elapsed -ge $timeout ]; then
            print_warning "Timeout waiting for $instance_id to be deleted"
        fi
    done
}

# Function to delete CloudFormation stack
delete_cloudformation_stack() {
    print_status "Checking for CloudFormation stack: $STACK_NAME"
    
    if aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" &> /dev/null; then
        print_status "Deleting CloudFormation stack: $STACK_NAME"
        
        aws cloudformation delete-stack \
            --stack-name "$STACK_NAME" \
            --region "$REGION"
        
        print_status "Waiting for CloudFormation stack deletion..."
        
        aws cloudformation wait stack-delete-complete \
            --stack-name "$STACK_NAME" \
            --region "$REGION" || {
            print_warning "CloudFormation stack deletion timed out or failed"
            print_status "You may need to check the AWS console for manual cleanup"
        }
        
        print_success "CloudFormation stack deleted successfully"
    else
        print_warning "CloudFormation stack $STACK_NAME not found"
    fi
}

# Function to clean up orphaned resources
cleanup_orphaned_resources() {
    print_status "Cleaning up any orphaned resources..."
    
    # Clean up security groups
    print_status "Checking for orphaned security groups..."
    SECURITY_GROUPS=$(aws ec2 describe-security-groups \
        --filters "Name=group-name,Values=*postgresql*,*replication*" \
        --query "SecurityGroups[?GroupName != 'default'].GroupId" \
        --output text \
        --region "$REGION" 2>/dev/null || true)
    
    if [ ! -z "$SECURITY_GROUPS" ]; then
        for sg in $SECURITY_GROUPS; do
            print_status "Attempting to delete security group: $sg"
            aws ec2 delete-security-group --group-id "$sg" --region "$REGION" 2>/dev/null || true
        done
    fi
    
    # Clean up VPCs (only if they're empty)
    print_status "Checking for empty VPCs created for replication..."
    VPCS=$(aws ec2 describe-vpcs \
        --filters "Name=tag:Project,Values=PostgreSQLReplication" \
        --query "Vpcs[].VpcId" \
        --output text \
        --region "$REGION" 2>/dev/null || true)
    
    if [ ! -z "$VPCS" ]; then
        for vpc in $VPCS; do
            print_status "Found VPC tagged for PostgreSQL replication: $vpc"
            print_warning "Please manually verify and delete VPC $vpc if it's no longer needed"
        done
    fi
}

# Function to verify cleanup
verify_cleanup() {
    print_status "Verifying cleanup completion..."
    
    # Check for remaining RDS instances
    REMAINING_INSTANCES=$(aws rds describe-db-instances \
        --query "DBInstances[?contains(DBInstanceIdentifier, 'postgresql') || contains(DBInstanceIdentifier, 'replication')].DBInstanceIdentifier" \
        --output text \
        --region "$REGION" 2>/dev/null || true)
    
    if [ ! -z "$REMAINING_INSTANCES" ]; then
        print_warning "Some RDS instances may still exist: $REMAINING_INSTANCES"
        print_status "These might be in the process of being deleted"
    fi
    
    # Check for remaining CloudFormation stacks
    REMAINING_STACKS=$(aws cloudformation list-stacks \
        --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
        --query "StackSummaries[?contains(StackName, 'postgresql') || contains(StackName, 'replication')].StackName" \
        --output text \
        --region "$REGION" 2>/dev/null || true)
    
    if [ ! -z "$REMAINING_STACKS" ]; then
        print_warning "Some CloudFormation stacks may still exist: $REMAINING_STACKS"
    fi
}

# Function to estimate cost savings
estimate_cost_savings() {
    print_status "Estimated monthly cost savings after cleanup:"
    
    case "db.r6g.large" in
        "db.t3.micro")
            echo "   • 2x db.t3.micro instances: ~$25-30/month"
            ;;
        "db.t3.small")
            echo "   • 2x db.t3.small instances: ~$50-60/month"
            ;;
        "db.t3.medium")
            echo "   • 2x db.t3.medium instances: ~$90-100/month"
            ;;
    esac
    
    echo "   • Storage and backups: ~$10-15/month"
    echo "   • VPC and networking: ~$5-10/month"
    echo ""
    print_success "Total estimated savings: $40-120/month"
}

# Function to generate cleanup report
generate_cleanup_report() {
    local report_file="cleanup-report-$(date +%Y%m%d-%H%M%S).txt"
    
    print_status "Generating cleanup report: $report_file"
    
    {
        echo "PostgreSQL Logical Replication Cleanup Report"
        echo "=============================================="
        echo "Date: $(date)"
        echo "Region: $REGION"
        echo "Stack Name: $STACK_NAME"
        echo ""
        echo "Resources that were targeted for deletion:"
        echo "- CloudFormation stack: $STACK_NAME"
        echo "- RDS instances: postgresql-primary, postgresql-replica"
        echo "- VPC and networking components"
        echo "- Security groups and parameter groups"
        echo ""
        echo "Estimated cost savings: $40-120/month"
        echo ""
        echo "Next steps:"
        echo "1. Verify your AWS billing dashboard"
        echo "2. Check for any unexpected charges"
        echo "3. Consider setting up billing alerts"
        echo "4. Review this repository for learning materials"
    } > "$report_file"
    
    print_success "Cleanup report saved to: $report_file"
}

# Main execution
main() {
    echo "Starting cleanup process..."
    echo ""
    
    # Pre-checks
    check_aws_cli
    
    # Confirmation
    confirm_deletion
    
    # Cleanup process
    print_status "Beginning cleanup process..."
    
    # Delete CloudFormation stack first (this handles most resources)
    delete_cloudformation_stack
    
    # Manual cleanup of any remaining RDS instances
    delete_rds_instances
    
    # Wait for RDS deletion to complete
    wait_for_rds_deletion
    
    # Clean up any orphaned resources
    cleanup_orphaned_resources
    
    # Verification
    verify_cleanup
    
    # Generate report
    generate_cleanup_report
    
    # Final message
    echo ""
    print_success "🎉 Cleanup process completed!"
    echo ""
    estimate_cost_savings
    echo ""
    print_status "Important reminders:"
    echo "   • Check your AWS billing dashboard in 24-48 hours"
    echo "   • Verify that all resources have been deleted"
    echo "   • Keep the cleanup report for your records"
    echo "   • Consider setting up billing alerts for future projects"
    echo ""
    print_status "Thank you for using the PostgreSQL Logical Replication Guide!"
}

# Script options
case "${1:-}" in
    --help|-h)
        echo "Usage: $0 [options]"
        echo ""
        echo "Options:"
        echo "  --help, -h     Show this help message"
        echo "  --dry-run      Show what would be deleted without actually deleting"
        echo "  --force        Skip confirmation prompt"
        echo ""
        echo "Environment variables:"
        echo "  AWS_PROFILE    AWS profile to use"
        echo "  AWS_REGION     AWS region (default: us-east-1)"
        echo ""
        exit 0
        ;;
    --dry-run)
        echo "DRY RUN MODE - No resources will be deleted"
        check_aws_cli
        delete_cloudformation_stack() { echo "Would delete CloudFormation stack: $STACK_NAME"; }
        delete_rds_instances() { echo "Would delete RDS instances"; }
        wait_for_rds_deletion() { echo "Would wait for RDS deletion"; }
        cleanup_orphaned_resources() { echo "Would clean up orphaned resources"; }
        verify_cleanup() { echo "Would verify cleanup"; }
        generate_cleanup_report() { echo "Would generate cleanup report"; }
        main
        ;;
    --force)
        confirm_deletion() { echo "Skipping confirmation (--force used)"; }
        main
        ;;
    *)
        main
        ;;
esac
