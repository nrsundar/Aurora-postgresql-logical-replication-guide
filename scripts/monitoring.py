#!/usr/bin/env python3
"""
PostgreSQL Logical Replication Monitoring Script
Continuously monitors replication health and performance
"""

import psycopg2
import time
import json
import sys
import os
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional

class ReplicationMonitor:
    def __init__(self, primary_config: Dict, replica_config: Dict):
        self.primary_config = primary_config
        self.replica_config = replica_config
        self.primary_conn = None
        self.replica_conn = None
        self.alerts = []
        
    def connect_databases(self) -> bool:
        """Establish connections to both databases"""
        try:
            self.primary_conn = psycopg2.connect(**self.primary_config)
            self.primary_conn.autocommit = True
            
            self.replica_conn = psycopg2.connect(**self.replica_config)
            self.replica_conn.autocommit = True
            
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False
    
    def get_replication_lag(self) -> Optional[float]:
        """Get current replication lag in seconds"""
        try:
            with self.replica_conn.cursor() as cur:
                cur.execute("""
                    SELECT EXTRACT(EPOCH FROM (now() - latest_end_time)) as lag_seconds
                    FROM pg_stat_subscription 
                    WHERE subname = 'my_subscription' AND latest_end_time IS NOT NULL;
                """)
                result = cur.fetchone()
                return float(result[0]) if result and result[0] is not None else None
        except Exception as e:
            print(f"Failed to get replication lag: {e}")
            return None
    
    def get_wal_lag_size(self) -> Optional[str]:
        """Get WAL lag size on primary"""
        try:
            with self.primary_conn.cursor() as cur:
                cur.execute("""
                    SELECT pg_size_pretty(
                        COALESCE(
                            pg_wal_lsn_diff(
                                pg_current_wal_lsn(), 
                                restart_lsn
                            ), 0
                        )
                    ) as lag_size
                    FROM pg_replication_slots 
                    WHERE slot_name LIKE '%my_subscription%' AND active = true
                    LIMIT 1;
                """)
                result = cur.fetchone()
                return result[0] if result else None
        except Exception as e:
            print(f"Failed to get WAL lag size: {e}")
            return None
    
    def get_subscription_status(self) -> Dict:
        """Get detailed subscription status"""
        try:
            with self.replica_conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        subname,
                        pid,
                        received_lsn,
                        latest_end_lsn,
                        latest_end_time,
                        last_msg_send_time,
                        last_msg_receipt_time
                    FROM pg_stat_subscription;
                """)
                result = cur.fetchone()
                
                if result:
                    return {
                        'name': result[0],
                        'worker_pid': result[1],
                        'received_lsn': result[2],
                        'latest_end_lsn': result[3],
                        'latest_end_time': result[4],
                        'last_msg_send_time': result[5],
                        'last_msg_receipt_time': result[6],
                        'worker_active': result[1] is not None
                    }
                return {}
        except Exception as e:
            print(f"Failed to get subscription status: {e}")
            return {}
    
    def get_replication_slot_status(self) -> List[Dict]:
        """Get replication slot status from primary"""
        try:
            with self.primary_conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        slot_name,
                        plugin,
                        slot_type,
                        database,
                        active,
                        pg_size_pretty(
                            COALESCE(
                                pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn), 
                                0
                            )
                        ) as lag_size,
                        restart_lsn,
                        confirmed_flush_lsn
                    FROM pg_replication_slots;
                """)
                results = cur.fetchall()
                
                slots = []
                for row in results:
                    slots.append({
                        'name': row[0],
                        'plugin': row[1],
                        'type': row[2],
                        'database': row[3],
                        'active': row[4],
                        'lag_size': row[5],
                        'restart_lsn': row[6],
                        'confirmed_flush_lsn': row[7]
                    })
                return slots
        except Exception as e:
            print(f"Failed to get replication slot status: {e}")
            return []
    
    def get_database_sizes(self) -> Dict:
        """Get database sizes for both primary and replica"""
        sizes = {}
        
        try:
            # Primary database size
            with self.primary_conn.cursor() as cur:
                cur.execute("""
                    SELECT pg_size_pretty(pg_database_size(current_database()));
                """)
                sizes['primary'] = cur.fetchone()[0]
            
            # Replica database size
            with self.replica_conn.cursor() as cur:
                cur.execute("""
                    SELECT pg_size_pretty(pg_database_size(current_database()));
                """)
                sizes['replica'] = cur.fetchone()[0]
                
        except Exception as e:
            print(f"Failed to get database sizes: {e}")
        
        return sizes
    
    def check_connection_counts(self) -> Dict:
        """Check connection counts on both databases"""
        connections = {}
        
        try:
            # Primary connections
            with self.primary_conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) as total_connections,
                           COUNT(*) FILTER (WHERE state = 'active') as active_connections
                    FROM pg_stat_activity;
                """)
                result = cur.fetchone()
                connections['primary'] = {
                    'total': result[0],
                    'active': result[1]
                }
            
            # Replica connections
            with self.replica_conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) as total_connections,
                           COUNT(*) FILTER (WHERE state = 'active') as active_connections
                    FROM pg_stat_activity;
                """)
                result = cur.fetchone()
                connections['replica'] = {
                    'total': result[0],
                    'active': result[1]
                }
                
        except Exception as e:
            print(f"Failed to get connection counts: {e}")
        
        return connections
    
    def check_alerts(self, metrics: Dict) -> List[Dict]:
        """Check for alert conditions"""
        alerts = []
        
        # Check replication lag
        if 'replication_lag_seconds' in metrics and metrics['replication_lag_seconds']:
            if metrics['replication_lag_seconds'] > 60:  # 1 minute
                alerts.append({
                    'level': 'WARNING',
                    'message': f"High replication lag: {metrics['replication_lag_seconds']:.2f} seconds"
                })
            elif metrics['replication_lag_seconds'] > 300:  # 5 minutes
                alerts.append({
                    'level': 'CRITICAL',
                    'message': f"Critical replication lag: {metrics['replication_lag_seconds']:.2f} seconds"
                })
        
        # Check subscription worker
        if 'subscription' in metrics and not metrics['subscription'].get('worker_active', False):
            alerts.append({
                'level': 'CRITICAL',
                'message': "Subscription worker is not running"
            })
        
        # Check replication slots
        if 'replication_slots' in metrics:
            for slot in metrics['replication_slots']:
                if not slot['active']:
                    alerts.append({
                        'level': 'WARNING',
                        'message': f"Replication slot '{slot['name']}' is not active"
                    })
        
        return alerts
    
    def collect_metrics(self) -> Dict:
        """Collect all monitoring metrics"""
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'replication_lag_seconds': self.get_replication_lag(),
            'wal_lag_size': self.get_wal_lag_size(),
            'subscription': self.get_subscription_status(),
            'replication_slots': self.get_replication_slot_status(),
            'database_sizes': self.get_database_sizes(),
            'connections': self.check_connection_counts()
        }
        
        # Check for alerts
        metrics['alerts'] = self.check_alerts(metrics)
        
        return metrics
    
    def print_metrics(self, metrics: Dict):
        """Print metrics in a readable format"""
        print(f"\n{'='*80}")
        print(f"PostgreSQL Replication Monitor - {metrics['timestamp']}")
        print(f"{'='*80}")
        
        # Replication Status
        print("\n🔄 REPLICATION STATUS:")
        if metrics['replication_lag_seconds'] is not None:
            print(f"   Lag Time: {metrics['replication_lag_seconds']:.2f} seconds")
        else:
            print("   Lag Time: Unable to determine")
        
        if metrics['wal_lag_size']:
            print(f"   WAL Lag Size: {metrics['wal_lag_size']}")
        
        # Subscription Status
        print("\n📡 SUBSCRIPTION STATUS:")
        sub = metrics['subscription']
        if sub:
            print(f"   Name: {sub.get('name', 'N/A')}")
            print(f"   Worker PID: {sub.get('worker_pid', 'Not running')}")
            print(f"   Worker Active: {'Yes' if sub.get('worker_active') else 'No'}")
            if sub.get('latest_end_time'):
                print(f"   Last Message: {sub['latest_end_time']}")
        else:
            print("   No subscription found")
        
        # Replication Slots
        print("\n🔌 REPLICATION SLOTS:")
        slots = metrics['replication_slots']
        if slots:
            for slot in slots:
                status = "Active" if slot['active'] else "Inactive"
                print(f"   {slot['name']}: {status} (Lag: {slot['lag_size']})")
        else:
            print("   No replication slots found")
        
        # Database Sizes
        print("\n💾 DATABASE SIZES:")
        sizes = metrics['database_sizes']
        if sizes:
            print(f"   Primary: {sizes.get('primary', 'N/A')}")
            print(f"   Replica: {sizes.get('replica', 'N/A')}")
        
        # Connection Counts
        print("\n🔗 CONNECTIONS:")
        conn = metrics['connections']
        if conn:
            if 'primary' in conn:
                print(f"   Primary: {conn['primary']['active']}/{conn['primary']['total']} active")
            if 'replica' in conn:
                print(f"   Replica: {conn['replica']['active']}/{conn['replica']['total']} active")
        
        # Alerts
        alerts = metrics['alerts']
        if alerts:
            print("\n⚠️  ALERTS:")
            for alert in alerts:
                icon = "🚨" if alert['level'] == 'CRITICAL' else "⚠️"
                print(f"   {icon} {alert['level']}: {alert['message']}")
        else:
            print("\n✅ NO ALERTS")
    
    def monitor_continuous(self, interval: int = 30, output_file: Optional[str] = None):
        """Run continuous monitoring"""
        print(f"Starting continuous monitoring (interval: {interval}s)")
        if output_file:
            print(f"Logging to: {output_file}")
        
        try:
            while True:
                metrics = self.collect_metrics()
                
                # Print to console
                self.print_metrics(metrics)
                
                # Write to file if specified
                if output_file:
                    with open(output_file, 'a') as f:
                        f.write(json.dumps(metrics, default=str) + '\n')
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n\nMonitoring stopped by user")
        except Exception as e:
            print(f"\n\nMonitoring error: {e}")
    
    def close_connections(self):
        """Close database connections"""
        if self.primary_conn:
            self.primary_conn.close()
        if self.replica_conn:
            self.replica_conn.close()

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='PostgreSQL Replication Monitor')
    parser.add_argument('--interval', type=int, default=30, help='Monitoring interval in seconds (default: 30)')
    parser.add_argument('--output', type=str, help='Output file for JSON logs')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    
    args = parser.parse_args()
    
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
    
    monitor = ReplicationMonitor(primary_config, replica_config)
    
    try:
        if not monitor.connect_databases():
            sys.exit(1)
        
        if args.once:
            # Run once and exit
            metrics = monitor.collect_metrics()
            monitor.print_metrics(metrics)
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(metrics, f, indent=2, default=str)
        else:
            # Continuous monitoring
            monitor.monitor_continuous(args.interval, args.output)
            
    finally:
        monitor.close_connections()

if __name__ == "__main__":
    main()
