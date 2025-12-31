#!/usr/bin/env python3
"""
Database schema migration script for added fields.
Run this before deploying to add new columns to existing tables.
"""

import sqlite3
import os

def migrate_database():
    """Add new columns to existing tables"""

    db_path = os.path.join(os.path.dirname(__file__), 'leads.db')

    if not os.path.exists(db_path):
        print("Database doesn't exist yet, will be created on first run")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if new columns already exist
        cursor.execute("PRAGMA table_info(leads)")
        columns = [row[1] for row in cursor.fetchall()]

        # Add new columns to leads table
        new_columns = [
            ('business_size_indicator', "TEXT"),
            ('online_presence_score', "INTEGER DEFAULT 0"),
            ('competitor_count', "INTEGER DEFAULT 0"),
            ('market_demand_score', "INTEGER DEFAULT 50"),
            ('location_advantage', "REAL DEFAULT 1.0"),
            ('industry_growth_rate', "REAL DEFAULT 0.0"),
            ('gdpr_consent', "BOOLEAN DEFAULT 1"),
            ('marketing_opt_out', "BOOLEAN DEFAULT 0"),
            ('opt_out_reason', "TEXT"),
            ('opt_out_date', "DATETIME")
        ]

        for col_name, col_def in new_columns:
            if col_name not in columns:
                print(f"Adding column {col_name} to leads table")
                cursor.execute(f"ALTER TABLE leads ADD COLUMN {col_name} {col_def}")

        # Add new columns to analytics table
        cursor.execute("PRAGMA table_info(analytics)")
        analytics_columns = [row[1] for row in cursor.fetchall()]

        analytics_new_columns = [
            ('contacted_to_responded_rate', "REAL DEFAULT 0"),
            ('responded_to_closed_rate', "REAL DEFAULT 0"),
            ('overall_conversion_rate', "REAL DEFAULT 0"),
            ('best_template_id', "INTEGER"),
            ('best_template_response_rate', "REAL DEFAULT 0"),
            ('avg_lead_score', "REAL DEFAULT 0"),
            ('hot_leads_count', "INTEGER DEFAULT 0"),
            ('warm_leads_count', "INTEGER DEFAULT 0"),
            ('cold_leads_count', "INTEGER DEFAULT 0"),
            ('opt_outs_count', "INTEGER DEFAULT 0"),
            ('gdpr_complaints', "INTEGER DEFAULT 0"),
            ('ab_test_winner_variant', "TEXT"),
            ('ab_test_improvement_rate', "REAL DEFAULT 0")
        ]

        for col_name, col_def in analytics_new_columns:
            if col_name not in analytics_columns:
                print(f"Adding column {col_name} to analytics table")
                cursor.execute(f"ALTER TABLE analytics ADD COLUMN {col_name} {col_def}")

        conn.commit()
        print("Schema migration completed successfully!")

    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_database()
