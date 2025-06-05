#!/usr/bin/env python3
"""
PostgreSQL Logical Replication Testing Script
Validates replication setup and performs automated tests
"""

import psycopg2
import time
import json
import sys
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional

class ReplicationTester:
    def __init__(self, primary_config: Dict, replica_config: Dict):
        self.primary_config = primary_config
        self.replica_config = replica_config
        self.primary_conn = None
        self.replica_conn = None
        
    def connect_databases(self) -> bool:
        """Establish connections to both primary and replica databases"""
        try:
            # Connect to primary
            self.primary_conn = psycopg2.connect(**self.primary_config)
            self.primary_conn.autocommit = True
            print("✓ Connected to primary database")
            
            # Connect to replica
            self.replica_conn = psycopg2.connect(**self.replica_config)
            self.replica_conn.autocommit = True
            print("✓ Connected to replica database")
            
            return True
        except Exception as e:
            print(f"✗ Database connection failed: {e}")
            return False
    
    def verify_replication_setup(self) -> bool:
        """Verify that replication is properly configured"""
        try:
            # Check primary database settings
            with self.primary_conn.cursor() as cur:
                cur.execute("SHOW wal_level;")
                wal_level = cur.fetchone()[0]
                if wal_level != 'logical':
                    print(f"✗ WAL level is {wal_level}, should be 'logical'")
                    return False
                print(f"✓ WAL level: {wal_level}")
                
                # Check replication slots
                cur.execute("SELECT COUNT(*) FROM pg_replication_slots WHERE active = true;")
                active_slots = cur.fetchone()[0]
                print(f"✓ Active replication slots: {active_slots}")
                
                # Check publication
                cur.execute("SELECT COUNT(*) FROM pg_publication WHERE pubname = 'my_publication';")
                publications = cur.fetchone()[0]
                if publications == 0:
                    print("✗ Publication 'my_publication' not found")
                    return False
                print("✓ Publication 'my_publication' exists")
            
            # Check replica database
            with self.replica_conn.cursor() as cur:
                # Check subscription
                cur.execute("SELECT COUNT(*) FROM pg_subscription WHERE subname = 'my_subscription';")
                subscriptions = cur.fetchone()[0]
                if subscriptions == 0:
                    print("✗ Subscription 'my_subscription' not found")
                    return False
                print("✓ Subscription 'my_subscription' exists")
                
                # Check subscription status
                cur.execute("""
                    SELECT subname, pid, received_lsn, latest_end_lsn 
                    FROM pg_stat_subscription 
                    WHERE subname = 'my_subscription';
                """)
                sub_stats = cur.fetchone()
                if sub_stats and sub_stats[1]:  # pid is not None
                    print(f"✓ Subscription worker running (PID: {sub_stats[1]})")
                else:
                    print("⚠ Subscription worker not running")
            
            return True
        except Exception as e:
            print(f"✗ Replication verification failed: {e}")
            return False
    
    def test_data_replication(self) -> bool:
        """Test actual data replication by inserting test records"""
        test_table = "replication_test"
        
        try:
            # Create test table on primary
            with self.primary_conn.cursor() as cur:
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {test_table} (
                        id SERIAL PRIMARY KEY,
                        test_data VARCHAR(100),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                print(f"✓ Created test table '{test_table}' on primary")
            
            # Create test table on replica (structure only)
            with self.replica_conn.cursor() as cur:
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {test_table} (
                        id SERIAL PRIMARY KEY,
                        test_data VARCHAR(100),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                print(f"✓ Created test table '{test_table}' on replica")
            
            # Insert test data on primary
            test_value = f"test_data_{int(time.time())}"
            with self.primary_conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO {test_table} (test_data) VALUES (%s) RETURNING id;",
                    (test_value,)
                )
                test_id = cur.fetchone()[0]
                print(f"✓ Inserted test record with ID {test_id} on primary")
            
            # Wait for replication
            print("⏳ Waiting for replication (10 seconds)...")
            time.sleep(10)
            
            # Verify data on replica
            with self.replica_conn.cursor() as cur:
                cur.execute(
                    f"SELECT test_data FROM {test_table} WHERE id = %s;",
                    (test_id,)
                )
                result = cur.fetchone()
                
                if result and result[0] == test_value:
                    print(f"✓ Test data replicated successfully: {test_value}")
                    return True
                else:
                    print(f"✗ Test data not found on replica")
                    return False
                    
        except Exception as e:
            print(f"✗ Data replication test failed: {e}")
            return False
        finally:
            # Cleanup test table
            try:
                with self.primary_conn.cursor() as cur:
                    cur.execute(f"DROP TABLE IF EXISTS {test_table};")
                with self.replica_conn.cursor() as cur:
                    cur.execute(f"DROP TABLE IF EXISTS {test_table};")
                print(f"✓ Cleaned up test table '{test_table}'")
            except:
                pass
    
    def measure_replication_lag(self) -> Optional[float]:
        """Measure current replication lag in seconds"""
        try:
            with self.replica_conn.cursor() as cur:
                cur.execute("""
                    SELECT EXTRACT(EPOCH FROM (now() - latest_end_time)) as lag_seconds
                    FROM pg_stat_subscription 
                    WHERE subname = 'my_subscription' AND latest_end_time IS NOT NULL;
                """)
                result = cur.fetchone()
                if result and result[0] is not None:
                    lag_seconds = float(result[0])
                    print(f"✓ Current replication lag: {lag_seconds:.2f} seconds")
                    return lag_seconds
                else:
                    print("⚠ Unable to measure replication lag")
                    return None
        except Exception as e:
            print(f"✗ Failed to measure replication lag: {e}")
            return None
    
    def get_replication_stats(self) -> Dict:
        """Get comprehensive replication statistics"""
        stats = {}
        
        try:
            # Primary statistics
            with self.primary_conn.cursor() as cur:
                # WAL statistics
                cur.execute("""
                    SELECT 
                        pg_current_wal_lsn() as current_wal_lsn,
                        pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), '0/0')) as total_wal_size;
                """)
                wal_stats = cur.fetchone()
                stats['primary'] = {
                    'current_wal_lsn': wal_stats[0],
                    'total_wal_size': wal_stats[1]
                }
                
                # Replication slot statistics
                cur.execute("""
                    SELECT 
                        slot_name,
                        active,
                        pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)) as lag_size
                    FROM pg_replication_slots;
                """)
                slots = cur.fetchall()
                stats['primary']['replication_slots'] = [
                    {'name': slot[0], 'active': slot[1], 'lag_size': slot[2]}
                    for slot in slots
                ]
            
            # Replica statistics
            with self.replica_conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        subname,
                        received_lsn,
                        latest_end_lsn,
                        latest_end_time,
                        last_msg_send_time,
                        last_msg_receipt_time
                    FROM pg_stat_subscription;
                """)
                sub_stats = cur.fetchone()
                if sub_stats:
                    stats['replica'] = {
                        'subscription_name': sub_stats[0],
                        'received_lsn': sub_stats[1],
                        'latest_end_lsn': sub_stats[2],
                        'latest_end_time': sub_stats[3].isoformat() if sub_stats[3] else None,
                        'last_msg_send_time': sub_stats[4].isoformat() if sub_stats[4] else None,
                        'last_msg_receipt_time': sub_stats[5].isoformat() if sub_stats[5] else None,
                    }
            
            return stats
        except Exception as e:
            print(f"✗ Failed to get replication stats: {e}")
            return {}
    
    def run_complete_test(self) -> bool:
        """Run complete test suite"""
        print("🚀 Starting PostgreSQL Logical Replication Test Suite")
        print("=" * 60)
        
        # Connect to databases
        if not self.connect_databases():
            return False
        
        # Verify replication setup
        print("\n📋 Verifying replication setup...")
        if not self.verify_replication_setup():
            return False
        
        # Test data replication
        print("\n🔄 Testing data replication...")
        if not self.test_data_replication():
            return False
        
        # Measure replication lag
        print("\n⏱️  Measuring replication lag...")
        self.measure_replication_lag()
        
        # Get comprehensive stats
        print("\n📊 Gathering replication statistics...")
        stats = self.get_replication_stats()
        if stats:
            print(json.dumps(stats, indent=2, default=str))
        
        print("\n✅ All tests completed successfully!")
        return True
    
    def close_connections(self):
        """Close database connections"""
        if self.primary_conn:
            self.primary_conn.close()
        if self.replica_conn:
            self.replica_conn.close()

def main():
    """Main function to run replication tests"""
    # Database configuration
    primary_config = {
        'host': os.getenv('PRIMARY_HOST', 'localhost'),
        'port': int(os.getenv('PRIMARY_PORT', '5432')),
        'database': os.getenv('DB_NAME', 'replication_demo'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', 'password'),
        'sslmode': 'require'
    }
    
    replica_config = {
        'host': os.getenv('REPLICA_HOST', 'localhost'),
        'port': int(os.getenv('REPLICA_PORT', '5432')),
        'database': os.getenv('DB_NAME', 'replication_demo'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', 'password'),
        'sslmode': 'require'
    }
    
    # Print configuration (without passwords)
    print("Configuration:")
    print(f"Primary: {primary_config['host']}:{primary_config['port']}")
    print(f"Replica: {replica_config['host']}:{replica_config['port']}")
    print(f"Database: {primary_config['database']}")
    print()
    
    # Run tests
    tester = ReplicationTester(primary_config, replica_config)
    try:
        success = tester.run_complete_test()
        sys.exit(0 if success else 1)
    finally:
        tester.close_connections()

if __name__ == "__main__":
    main()
