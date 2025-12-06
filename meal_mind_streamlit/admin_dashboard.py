import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from utils.db import get_snowflake_connection

# Page Config
st.set_page_config(
    page_title="Meal Mind Admin",
    page_icon="🛡️",
    layout="wide"
)

def get_generation_stats(conn):
    """Fetch stats for meal plan generation"""
    cursor = conn.cursor()
    
    # Today's date
    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    
    stats = {
        "today_count": 0,
        "tomorrow_count": 0,
        "overdue_count": 0,
        "details": []
    }
    
    try:
        # Get counts and details
        cursor.execute("""
            SELECT DISTINCT u.username, ps.next_plan_date, ps.status, ps.user_id
            FROM planning_schedule ps
            JOIN users u ON ps.user_id = u.user_id
            WHERE ps.status = 'ACTIVE'
            ORDER BY ps.next_plan_date
        """)
        
        rows = cursor.fetchall()
        
        for row in rows:
            username = row[0]
            next_date = row[1]
            status = row[2]
            user_id = row[3]
            
            # Categorize
            category = "Upcoming"
            if next_date < today:
                stats["overdue_count"] += 1
                category = "Overdue (Issue)"
            elif next_date == today:
                stats["today_count"] += 1
                category = "Generating Today"
            elif next_date == tomorrow:
                stats["tomorrow_count"] += 1
                category = "Generating Tomorrow"
            
            # Add to details if relevant (Today, Tomorrow, or Overdue)
            if next_date <= tomorrow:
                stats["details"].append({
                    "User": username,
                    "Next Generation": next_date,
                    "Status": category,
                    "User ID": user_id
                })
                
    except Exception as e:
        st.error(f"Error fetching stats: {e}")
    finally:
        cursor.close()
        
    return stats

def main():
    st.title("🛡️ Meal Mind Admin Dashboard")
    st.markdown("Monitor automated meal plan generation status.")
    
    conn = get_snowflake_connection()
    
    if st.button("🔄 Refresh Data"):
        st.rerun()
    
    stats = get_generation_stats(conn)
    
    # Metrics
    col1, col2, col3 = st.columns(3)
    
    col1.metric("Generating Today", stats["today_count"], delta_color="normal")
    col2.metric("Generating Tomorrow", stats["tomorrow_count"], delta_color="normal")
    col3.metric("Issues / Overdue", stats["overdue_count"], delta_color="inverse")
    
    # Detailed Table
    st.markdown("### 📋 Generation Queue & Issues")
    if stats["details"]:
        df = pd.DataFrame(stats["details"])
        
        # Color coding function
        def highlight_status(val):
            color = ''
            if 'Overdue' in val:
                color = 'background-color: #ffcdd2; color: #c62828' # Red
            elif 'Today' in val:
                color = 'background-color: #fff9c4; color: #fbc02d' # Yellow
            elif 'Tomorrow' in val:
                color = 'background-color: #c8e6c9; color: #2e7d32' # Green
            return color

        st.dataframe(
            df.style.map(highlight_status, subset=['Status']),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No pending generations for today or tomorrow, and no overdue plans.")

if __name__ == "__main__":
    main()
