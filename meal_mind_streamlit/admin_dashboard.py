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
    
    conn = get_snowflake_connection()
    
    # Create tabs
    tab1, tab2, tab3, tab4 = st.tabs(["Generation Queue", "Nutrition Verifier", "Model Arena", "Automated Evals"])
    
    with tab1:
        st.header("Generation Queue & Issues")
        if st.button("🔄 Refresh Data"):
            st.rerun()
            
        stats = get_generation_stats(conn)
        
        # Metrics
        col1, col2, col3 = st.columns(3)
        
        col1.metric("Generating Today", stats["today_count"], delta_color="normal")
        col2.metric("Generating Tomorrow", stats["tomorrow_count"], delta_color="normal")
        col3.metric("Issues / Overdue", stats["overdue_count"], delta_color="inverse")
        
        # Detailed Table
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

    with tab2:
        st.header("🧪 Nutrition Data Verifier")
        st.markdown("Verify the accuracy of AI-generated nutrition data against Snowflake Cortex Search.")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            food_name = st.text_input("Food Item Name", placeholder="e.g., Peanut butter cookie")
            json_input = st.text_area("Generated JSON", height=300, placeholder='Paste the full JSON here...')
            
            verify_btn = st.button("Verify Nutrition", type="primary")
            
        with col2:
            if verify_btn and food_name and json_input:
                try:
                    import json
                    from utils.evaluation_agent import NutritionEvaluationAgent
                    from utils.db import get_snowpark_session
                    
                    # Parse JSON
                    data = json.loads(json_input)
                    
                    # Init Agent
                    session = get_snowpark_session()
                    eval_agent = NutritionEvaluationAgent(session)
                    
                    with st.spinner(f"Consulting Cortex Search for '{food_name}'..."):
                        result = eval_agent.evaluate_nutrition(food_name, data)
                        
                    # Display Result
                    if result['verdict'] == "CORRECT":
                        st.success(f"✅ VERDICT: {result['verdict']}")
                    else:
                        st.error(f"❌ VERDICT: {result['verdict']}")
                        
                    st.markdown(f"**Explanation:** {result['explanation']}")
                    
                    if result.get('ground_truth'):
                        st.subheader("Ground Truth (Cortex)")
                        st.json(result['ground_truth'])
                        
                except json.JSONDecodeError:
                    st.error("Invalid JSON format. Please check your input.")
                except Exception as e:
                    st.error(f"Error: {e}")

    with tab3:
        st.header("⚔️ Model Comparison Arena")
        st.markdown("Compare top LLMs (Meta, Anthropic, Mistral, Snowflake) on latency and groundedness.")
        
        mode = st.radio("Evaluation Mode", ["Single Prompt (Dynamic)", "Batch Evaluation (CSV)"], horizontal=True)
        
        if mode == "Single Prompt (Dynamic)":
            arena_prompt = st.text_area("Test Prompt", value="How much protein is in 100g of grilled chicken breast?", height=100)
            run_arena_btn = st.button("Run Arena", type="primary")
            
            if run_arena_btn and arena_prompt:
                from utils.model_arena import ModelArena
                from utils.db import get_snowpark_session
                
                session = get_snowpark_session()
                arena = ModelArena(session)
                
                results, context = arena.run_comparison(arena_prompt)
                
                # Display Results
                st.subheader("🏆 Leaderboard")
                
                res_df = pd.DataFrame(results)
                # Charts
                import altair as alt
                
                # Helper for Altair Charts (Duplicated for now, could be moved to utils)
                def create_colored_bar_chart(data, x_col, y_col, title, higher_is_better=True):
                    min_val = data[y_col].min()
                    max_val = data[y_col].max()
                    
                    if higher_is_better:
                        domain = [min_val, max_val]
                        range_ = ['#d32f2f', '#388e3c'] 
                    else:
                        domain = [min_val, max_val]
                        range_ = ['#388e3c', '#d32f2f'] 
                        
                    chart = alt.Chart(data).mark_bar().encode(
                        x=alt.X(x_col, axis=alt.Axis(labelAngle=0)),
                        y=alt.Y(y_col, title=title),
                        color=alt.Color(y_col, scale=alt.Scale(domain=domain, range=range_), legend=None),
                        tooltip=[x_col, y_col]
                    ).properties(title=title)
                    return chart

                col1, col2 = st.columns(2)
                with col1:
                    st.altair_chart(
                        create_colored_bar_chart(res_df, "model_name", "latency", "⏱️ Latency (s)", higher_is_better=False),
                        use_container_width=True
                    )
                    
                with col2:
                    st.altair_chart(
                        create_colored_bar_chart(res_df, "model_name", "groundedness_score", "🎯 Groundedness", higher_is_better=True),
                        use_container_width=True
                    )
                    
                # Style function for text color
                def style_text_color(df):
                    styles = pd.DataFrame('', index=df.index, columns=df.columns)
                    max_score = df['groundedness_score'].max()
                    min_score = df['groundedness_score'].min()
                    min_lat = df['latency'].min()
                    max_lat = df['latency'].max()
                    
                    for idx, row in df.iterrows():
                        if row['groundedness_score'] == max_score:
                            styles.at[idx, 'groundedness_score'] = 'color: #2e7d32; font-weight: bold'
                        elif row['groundedness_score'] == min_score:
                            styles.at[idx, 'groundedness_score'] = 'color: #c62828'
                            
                        if row['latency'] == min_lat:
                            styles.at[idx, 'latency'] = 'color: #2e7d32; font-weight: bold'
                        elif row['latency'] == max_lat:
                            styles.at[idx, 'latency'] = 'color: #c62828'
                    return styles

                st.dataframe(
                    res_df[["model_name", "latency", "groundedness_score", "explanation"]].style.apply(style_text_color, axis=None),
                    use_container_width=True
                )
                
                with st.expander("View Detailed Responses & Context"):
                    st.markdown("### Ground Truth Context")
                    st.info(context[:1000] + "...")
                    
                    for r in results:
                        st.markdown(f"#### {r['model_name']}")
                        st.write(r['response'])
                        st.divider()
                        
        elif mode == "Batch Evaluation (CSV)":
            csv_path = "meal_mind_streamlit/Meal_Mind_Combined_2025-12-06-1503.csv"
            output_path = "meal_mind_streamlit/evaluation_results.csv"
            
            try:
                df = pd.read_csv(csv_path)
                st.success(f"Loaded {len(df)} food items from CSV.")
                st.dataframe(df.head(), use_container_width=True)
                
                col1, col2 = st.columns([1, 1])
                
                run_new = False
                load_existing = False
                
                with col1:
                    if st.button("🚀 Run Batch Evaluation", type="primary"):
                        run_new = True
                        
                with col2:
                    if os.path.exists(output_path):
                        if st.button("📂 Load Previous Results"):
                            load_existing = True
                    else:
                        st.info("No previous results found.")
                
                res_df = None
                
                if run_new:
                    from utils.model_arena import ModelArena
                    from utils.db import get_snowpark_session
                    
                    session = get_snowpark_session()
                    arena = ModelArena(session)
                    
                    with st.spinner("Running batch evaluation... This may take a few minutes."):
                        results = arena.run_batch_evaluation(df)
                        
                    # Process Results
                    res_df = pd.DataFrame(results)
                    
                    # Save to CSV
                    res_df.to_csv(output_path, index=False)
                    st.success(f"Results saved to `{output_path}`")
                    
                elif load_existing:
                    res_df = pd.read_csv(output_path)
                    st.success(f"Loaded results from `{output_path}`")
                    
                # Visualization (Common for both)
                if res_df is not None:
                    import altair as alt
                    
                    # Aggregate Metrics
                    st.subheader("📊 Aggregate Performance")
                    
                    # Calculate Ratio per row first
                    res_df["token_ratio"] = res_df["output_tokens"] / res_df["input_tokens"]
                    
                    agg_metrics = res_df.groupby("model_name").agg({
                        "latency": "mean",
                        "groundedness_score": "mean",
                        "input_tokens": "mean",
                        "output_tokens": "mean",
                        "token_ratio": "mean"
                    }).reset_index()
                    
                    # Helper for Altair Charts
                    def create_colored_bar_chart(data, x_col, y_col, title, higher_is_better=True):
                        # Determine domain for color scale
                        min_val = data[y_col].min()
                        max_val = data[y_col].max()
                        
                        # For color scheme: 
                        # If higher is better (Score): Low(Red) -> High(Green)
                        # If lower is better (Latency): Low(Green) -> High(Red)
                        
                        if higher_is_better:
                            # Red to Green
                            domain = [min_val, max_val]
                            range_ = ['#d32f2f', '#388e3c'] # Red to Green
                        else:
                            # Green to Red (Low latency is green)
                            domain = [min_val, max_val]
                            range_ = ['#388e3c', '#d32f2f'] # Green to Red
                            
                        chart = alt.Chart(data).mark_bar().encode(
                            x=alt.X(x_col, axis=alt.Axis(labelAngle=0)),
                            y=alt.Y(y_col, title=title),
                            color=alt.Color(y_col, scale=alt.Scale(domain=domain, range=range_), legend=None),
                            tooltip=[x_col, y_col]
                        ).properties(
                            title=title
                        )
                        return chart

                    col1, col2 = st.columns(2)
                    with col1:
                        st.altair_chart(
                            create_colored_bar_chart(agg_metrics, "model_name", "latency", "⏱️ Avg Latency (s)", higher_is_better=False),
                            use_container_width=True
                        )
                        
                    with col2:
                        st.altair_chart(
                            create_colored_bar_chart(agg_metrics, "model_name", "groundedness_score", "🎯 Avg Groundedness", higher_is_better=True),
                            use_container_width=True
                        )
                        
                    col3, col4 = st.columns(2)
                    with col3:
                        st.bar_chart(agg_metrics.set_index("model_name")["output_tokens"])
                        
                    with col4:
                        st.bar_chart(agg_metrics.set_index("model_name")["token_ratio"])
                        
                    # Detailed Table
                    st.subheader("📝 Detailed Results")
                    
                    # Style function for text color
                    def style_text_color(df):
                        # Create a DataFrame of CSS strings
                        styles = pd.DataFrame('', index=df.index, columns=df.columns)
                        
                        # Groundedness: High=Green
                        max_score = df['groundedness_score'].max()
                        min_score = df['groundedness_score'].min()
                        
                        # Latency: Low=Green
                        min_lat = df['latency'].min()
                        max_lat = df['latency'].max()
                        
                        for idx, row in df.iterrows():
                            # Score
                            if row['groundedness_score'] == max_score:
                                styles.at[idx, 'groundedness_score'] = 'color: #2e7d32; font-weight: bold' # Green
                            elif row['groundedness_score'] == min_score:
                                styles.at[idx, 'groundedness_score'] = 'color: #c62828' # Red
                                
                            # Latency
                            if row['latency'] == min_lat:
                                styles.at[idx, 'latency'] = 'color: #2e7d32; font-weight: bold' # Green
                            elif row['latency'] == max_lat:
                                styles.at[idx, 'latency'] = 'color: #c62828' # Red
                                
                        return styles

                    st.dataframe(
                        res_df[["food_name", "model_name", "groundedness_score", "latency", "input_tokens", "output_tokens", "token_ratio", "citation_count", "explanation"]].style.apply(style_text_color, axis=None),
                        use_container_width=True
                    )
                    
            except FileNotFoundError:
                st.error(f"CSV file not found at `{csv_path}`. Please ensure it exists.")

    with tab4:
        st.header("🤖 Automated Evals (CI/CD)")
        st.markdown("Track the performance of Meal Mind agents over time using daily automated runs.")
        
        if st.button("🔄 Refresh Evals"):
            st.rerun()
            
        try:
            # Fetch Data from Snowflake
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM EVALUATION_LOGS ORDER BY EXECUTION_DATE DESC")
            rows = cursor.fetchall()
            
            if not rows:
                st.info("No evaluation logs found. The Airflow pipeline might not have run yet.")
            else:
                # Convert to DataFrame
                # Get column names
                col_names = [desc[0] for desc in cursor.description]
                eval_df = pd.DataFrame(rows, columns=col_names)
                
                # Metrics
                latest_run_id = eval_df['RUN_ID'].iloc[0]
                latest_run_df = eval_df[eval_df['RUN_ID'] == latest_run_id]
                
                avg_acc = latest_run_df['SCORE_ACCURACY'].mean()
                avg_qual = latest_run_df['SCORE_QUALITY'].mean()
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Latest Run Accuracy", f"{avg_acc:.1%}")
                col2.metric("Latest Run Quality", f"{avg_qual:.1f}/5.0")
                col3.metric("Total Test Cases", len(latest_run_df))
                
                # Trend Chart
                st.subheader("📈 Performance Trend")
                trend_df = eval_df.groupby('EXECUTION_DATE').agg({
                    'SCORE_ACCURACY': 'mean',
                    'SCORE_QUALITY': 'mean'
                }).reset_index()
                
                st.line_chart(trend_df.set_index('EXECUTION_DATE')[['SCORE_ACCURACY', 'SCORE_QUALITY']])
                
                # Detailed Table
                st.subheader("📝 Latest Run Details")
                st.dataframe(
                    latest_run_df[['INPUT', 'EXPECTED_INTENT', 'ACTUAL_INTENT', 'SCORE_ACCURACY', 'SCORE_QUALITY', 'JUDGE_REASONING']],
                    use_container_width=True,
                    hide_index=True
                )
                
        except Exception as e:
            st.warning(f"Could not fetch evaluation logs: {e}")
            st.info("Ensure the 'EVALUATION_LOGS' table exists in Snowflake.")
        finally:
            cursor.close()

if __name__ == "__main__":
    main()
