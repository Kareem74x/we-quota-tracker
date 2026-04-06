import logging

import psycopg2
import psycopg2.extras
from config import DATABASE_URL, START_GB



def get_db_connection():
    logging.info("Connecting to database...")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        logging.info("Connected successfully")
        return conn
    except Exception as e:
        logging.error("Database connection failed. Please check your network and DATABASE_URL in .env")
        return None


def ensure_table_exists(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quota_log (
            id            SERIAL PRIMARY KEY,
            date_time     TIMESTAMP       NOT NULL,
            day           INT,
            usage_gbs     NUMERIC(10, 1),
            remaining_gbs NUMERIC(10, 1),
            overall_state VARCHAR(50),
            state_gbs     NUMERIC(10, 1),
            state_days    NUMERIC(10, 1),
            remaining_days INT
        )
    """)


def insert_record(now_datetime, currentDay, remainGB, overAllState, overAllStateGbs, stateDays, remainingDays):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # TODO: replace this temporary solution with a more robust method for handling the start of a new cycle
        if currentDay == 1:
            logging.info("First day of the cycle — clearing quota_log table for a fresh start.")
            cursor.execute("DELETE FROM quota_log")
            conn.commit()

        ensure_table_exists(cursor)

        # Get previous remaining GBs to calculate usage
        cursor.execute("SELECT remaining_gbs FROM quota_log ORDER BY id DESC LIMIT 1")
        last_row = cursor.fetchone()
        prev_remain = last_row["remaining_gbs"] if last_row else START_GB
        usage = round(float(prev_remain) - remainGB, 1)

        insertion_query = """
            INSERT INTO quota_log
                (date_time, day, usage_gbs, remaining_gbs, overall_state, state_gbs, state_days, remaining_days)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        insertion_values = (
            now_datetime,
            currentDay,
            usage,
            round(remainGB, 1),
            overAllState,
            round(overAllStateGbs, 1),
            round(stateDays, 1),
            remainingDays
        )

        cursor.execute(insertion_query, insertion_values)

        conn.commit()
        cursor.close()
        conn.close()
        return True, usage

    except Exception as e:
        logging.error("Failed to write quota record to database.")
        return False, 0
