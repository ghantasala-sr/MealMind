import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from datetime import datetime

# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="NutriGen Analytics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# CUSTOM CSS STYLING
# ============================================================

st.markdown("""
    <style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        text-align: center;
        padding: 1rem 0;
    }

    .subheader-accent {
        font-size: 1.5rem;
        color: #2c3e50;
        font-weight: 600;
        border-bottom: 3px solid #667eea;
        padding-bottom: 0.5rem;
    }
    </style>
""", unsafe_allow_html=True)

# ============================================================
# DATA LOADING - WITH ERROR HANDLING
# ============================================================

@st.cache_data
def load_data():
    """Load all CSV files with comprehensive error handling"""
    try:
        df_results = pd.read_csv('nutrigen_multimodel_results.csv')
        df_summary = pd.read_csv('nutrigen_multimodel_summary.csv')
        df_profiles = pd.read_csv('nutrigen_test_profiles.csv')
        df_comparison = pd.read_csv('nutrigen_paper_comparison.csv')
        return df_results, df_summary, df_profiles, df_comparison
    except FileNotFoundError as e:
        st.error(f"Missing CSV file: {str(e)}")
        st.info("Ensure all CSV files are in the same directory as this script")
        st.stop()

# Load all data
df_results, df_summary, df_profiles, df_comparison = load_data()

# ============================================================
# TITLE & INTRO
# ============================================================

st.markdown('<div class="main-header">🍽️ NutriGen Analytics Dashboard</div>', unsafe_allow_html=True)

st.markdown("""
---
**Performance Analysis**: 5 Models × 5 Profiles = 25 Evaluations
- Accuracy Metrics (MAE %)
- Processing Speed Benchmarks
- Success Rate Analysis
- Research Paper Comparison
""")

# ============================================================
# SIDEBAR FILTERS
# ============================================================

st.sidebar.markdown("## 🔍 Filters")
st.sidebar.markdown("---")

all_models = sorted(df_results['Model'].unique().tolist())
selected_models = st.sidebar.multiselect(
    "Select Models:",
    options=all_models,
    default=all_models
)

all_profiles = sorted(df_results['Profile'].unique().tolist())
selected_profiles = st.sidebar.multiselect(
    "Select Profiles:",
    options=all_profiles,
    default=all_profiles
)

show_failures = st.sidebar.checkbox("Include Failed Tests", value=True)

# Filter data
filtered_results = df_results[
    (df_results['Model'].isin(selected_models)) &
    (df_results['Profile'].isin(selected_profiles))
]

if not show_failures:
    filtered_results = filtered_results[filtered_results['Success'] == True]

# ============================================================
# KEY METRICS - WITH PROPER TYPE HANDLING
# ============================================================

st.markdown('<div class="subheader-accent">📈 Key Performance Indicators</div>', unsafe_allow_html=True)

# CRITICAL: Safely calculate metrics with type conversion
total_tests = len(filtered_results)
successful_tests = int(filtered_results['Success'].sum()) if len(filtered_results) > 0 else 0
success_rate = (successful_tests / total_tests * 100) if total_tests > 0 else 0.0

# Safe calculations for averages
avg_error = float(filtered_results['Error_Percent'].mean()) if len(filtered_results) > 0 else 0.0
avg_time = float(filtered_results['Processing_Time'].mean()) if len(filtered_results) > 0 else 0.0

# Best model metrics
best_idx = df_summary['MAE_Percent'].idxmin()
best_model = str(df_summary.loc[best_idx, 'Model'])
best_mae = float(df_summary.loc[best_idx, 'MAE_Percent'])

# Display metrics with proper type casting
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(
        label="Total Tests",
        value=total_tests,
        delta=f"{successful_tests} successful"
    )

with col2:
    st.metric(
        label="Success Rate",
        value=f"{success_rate:.1f}%",
        delta=None
    )

with col3:
    st.metric(
        label="Avg Error",
        value=f"{avg_error:.2f}%",
        delta=None
    )

with col4:
    st.metric(
        label="Best Model",
        value=best_model.split('-')[0].upper(),
        delta=f"{best_mae:.2f}% error"
    )

with col5:
    st.metric(
        label="Avg Speed",
        value=f"{avg_time:.1f}s",
        delta=None
    )

# ============================================================
# TABS
# ============================================================

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🎯 Comparison",
    "📊 Errors",
    "⚡ Speed",
    "🔍 Profiles",
    "📋 Paper",
    "📥 Data"
])

# ============================================================
# TAB 1: MODEL COMPARISON
# ============================================================

with tab1:
    st.markdown("### Model Performance Overview")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Accuracy by Model")
        fig_mae = px.bar(
            df_summary,
            x='Model',
            y='MAE_Percent',
            color='MAE_Percent',
            color_continuous_scale='RdYlGn_r',
            title='Mean Absolute Error %',
            text='MAE_Percent'
        )
        fig_mae.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
        fig_mae.update_layout(showlegend=False, height=400)
        st.plotly_chart(fig_mae, use_container_width=True)

    with col2:
        st.markdown("#### Success Distribution")
        success_data = []
        for model in selected_models:
            model_tests = df_results[df_results['Model'] == model]
            success_data.append({
                'Model': model,
                'Success': int(model_tests['Success'].sum()),
                'Failed': int(len(model_tests) - model_tests['Success'].sum())
            })

        df_success = pd.DataFrame(success_data)
        fig_success = px.bar(
            df_success,
            x='Model',
            y=['Success', 'Failed'],
            barmode='stack',
            color_discrete_map={'Success': '#2ecc71', 'Failed': '#e74c3c'},
            title='Test Results'
        )
        fig_success.update_layout(height=400)
        st.plotly_chart(fig_success, use_container_width=True)

    st.markdown("#### Model Statistics Table")
    summary_copy = df_summary.copy()
    summary_copy['MAE_Percent'] = summary_copy['MAE_Percent'].apply(lambda x: f"{x:.2f}%")
    summary_copy['MAE_kcal'] = summary_copy['MAE_kcal'].apply(lambda x: f"{x:.2f}")
    summary_copy['Avg_Time_s'] = summary_copy['Avg_Time_s'].apply(lambda x: f"{x:.2f}s")
    st.dataframe(summary_copy, use_container_width=True, hide_index=True)

# ============================================================
# TAB 2: ERROR ANALYSIS
# ============================================================

with tab2:
    st.markdown("### Detailed Error Analysis")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Error % Distribution")
        fig_error_box = px.box(
            filtered_results,
            x='Model',
            y='Error_Percent',
            color='Model',
            title='Error Percentage'
        )
        fig_error_box.update_layout(showlegend=False, height=400)
        st.plotly_chart(fig_error_box, use_container_width=True)

    with col2:
        st.markdown("#### Calorie Error Distribution")
        fig_error_kcal = px.box(
            filtered_results,
            x='Model',
            y='Error_kcal',
            color='Model',
            title='Calorie Error (kcal)'
        )
        fig_error_kcal.update_layout(showlegend=False, height=400)
        st.plotly_chart(fig_error_kcal, use_container_width=True)

    st.markdown("#### Target vs Actual Calories")
    fig_scatter = px.scatter(
        filtered_results,
        x='Target_Calories',
        y='Actual_Calories',
        color='Model',
        size='Error_Percent',
        hover_data=['Profile', 'Error_Percent'],
        title='Target vs Actual'
    )

    if len(filtered_results) > 0:
        min_cal = min(filtered_results['Target_Calories'].min(), filtered_results['Actual_Calories'].min())
        max_cal = max(filtered_results['Target_Calories'].max(), filtered_results['Actual_Calories'].max())
        fig_scatter.add_trace(
            go.Scatter(
                x=[min_cal, max_cal],
                y=[min_cal, max_cal],
                mode='lines',
                name='Perfect',
                line=dict(dash='dash', color='gray')
            )
        )

    fig_scatter.update_layout(height=500)
    st.plotly_chart(fig_scatter, use_container_width=True)

# ============================================================
# TAB 3: SPEED ANALYSIS
# ============================================================

with tab3:
    st.markdown("### Processing Speed Analysis")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Avg Processing Time")
        fig_time = px.bar(
            df_summary,
            x='Model',
            y='Avg_Time_s',
            color='Avg_Time_s',
            color_continuous_scale='Viridis',
            title='Average Time (seconds)',
            text='Avg_Time_s'
        )
        fig_time.update_traces(texttemplate='%{text:.2f}s', textposition='outside')
        fig_time.update_layout(showlegend=False, height=400)
        st.plotly_chart(fig_time, use_container_width=True)

    with col2:
        st.markdown("#### Time Distribution")
        fig_time_box = px.box(
            filtered_results,
            x='Model',
            y='Processing_Time',
            color='Model',
            title='Processing Time Distribution'
        )
        fig_time_box.update_layout(showlegend=False, height=400)
        st.plotly_chart(fig_time_box, use_container_width=True)

    st.markdown("#### Speed vs Accuracy Trade-off")
    fig_tradeoff = px.scatter(
        df_summary,
        x='Avg_Time_s',
        y='MAE_Percent',
        size='MAE_kcal',
        color='Model',
        title='Speed vs Accuracy',
        labels={
            'Avg_Time_s': 'Time (seconds)',
            'MAE_Percent': 'MAE (%)'
        }
    )
    fig_tradeoff.update_layout(height=500)
    st.plotly_chart(fig_tradeoff, use_container_width=True)

# ============================================================
# TAB 4: PROFILE INSIGHTS
# ============================================================

with tab4:
    st.markdown("### Performance by Profile")

    selected_profile = st.selectbox(
        "Select Profile:",
        options=sorted(df_results['Profile'].unique())
    )

    profile_data = df_results[df_results['Profile'] == selected_profile]

    if len(profile_data) > 0:
        col1, col2 = st.columns(2)

        with col1:
            target_cal = int(profile_data['Target_Calories'].iloc[0])
            st.metric(
                label="Target Calories",
                value=f"{target_cal} kcal",
                delta=None
            )

        with col2:
            st.metric(
                label="Profile #",
                value=f"{selected_profile}",
                delta=f"{len(profile_data)} models tested"
            )

        col1, col2 = st.columns(2)

        with col1:
            fig_prof_error = px.bar(
                profile_data,
                x='Model',
                y='Error_Percent',
                color='Error_Percent',
                color_continuous_scale='RdYlGn_r',
                title=f'Error % - Profile {selected_profile}',
                text='Error_Percent'
            )
            fig_prof_error.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
            fig_prof_error.update_layout(showlegend=False, height=400)
            st.plotly_chart(fig_prof_error, use_container_width=True)

        with col2:
            fig_prof_cal = px.bar(
                profile_data,
                x='Model',
                y='Actual_Calories',
                color='Model',
                title=f'Actual Calories - Profile {selected_profile}',
                text='Actual_Calories'
            )
            target = profile_data['Target_Calories'].iloc[0]
            fig_prof_cal.add_hline(y=target, line_dash="dash", line_color="red")
            fig_prof_cal.update_layout(showlegend=False, height=400)
            st.plotly_chart(fig_prof_cal, use_container_width=True)

        st.dataframe(profile_data, use_container_width=True, hide_index=True)

# ============================================================
# TAB 5: PAPER COMPARISON
# ============================================================

with tab5:
    st.markdown("### Paper Comparison")

    st.info("Compare our results with published research")

    comp_clean = df_comparison.dropna(subset=['Paper_MAE_Percent'])

    if len(comp_clean) > 0:
        col1, col2 = st.columns(2)

        with col1:
            fig_comp = px.bar(
                comp_clean,
                x='Model',
                y=['Our_MAE_Percent', 'Paper_MAE_Percent'],
                barmode='group',
                title='MAE Comparison'
            )
            fig_comp.update_layout(height=400)
            st.plotly_chart(fig_comp, use_container_width=True)

        with col2:
            comp_diff = df_comparison.dropna(subset=['Difference'])
            if len(comp_diff) > 0:
                fig_diff = px.bar(
                    comp_diff,
                    x='Model',
                    y='Difference',
                    color='Difference',
                    color_continuous_scale='Reds',
                    title='Error Difference',
                    text='Difference'
                )
                fig_diff.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
                fig_diff.update_layout(showlegend=False, height=400)
                st.plotly_chart(fig_diff, use_container_width=True)

        st.dataframe(df_comparison, use_container_width=True, hide_index=True)

# ============================================================
# TAB 6: DATA EXPLORER
# ============================================================

with tab6:
    st.markdown("### Data Explorer")

    data_view = st.radio(
        "Select Data:",
        ["Detailed Results", "Summary", "Profiles", "Comparison"],
        horizontal=True
    )

    if data_view == "Detailed Results":
        st.dataframe(filtered_results, use_container_width=True, hide_index=True)
        csv = filtered_results.to_csv(index=False)
        st.download_button("📥 Download CSV", csv, "results.csv", "text/csv")

    elif data_view == "Summary":
        st.dataframe(df_summary, use_container_width=True, hide_index=True)
        csv = df_summary.to_csv(index=False)
        st.download_button("📥 Download CSV", csv, "summary.csv", "text/csv")

    elif data_view == "Profiles":
        st.dataframe(df_profiles, use_container_width=True, hide_index=True)
        csv = df_profiles.to_csv(index=False)
        st.download_button("📥 Download CSV", csv, "profiles.csv", "text/csv")

    else:
        st.dataframe(df_comparison, use_container_width=True, hide_index=True)
        csv = df_comparison.to_csv(index=False)
        st.download_button("📥 Download CSV", csv, "comparison.csv", "text/csv")

# ============================================================
# FOOTER
# ============================================================

st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("**NutriGen Analysis**\n- 5 Models\n- 5 Profiles\n- 25 Tests")

with col2:
    st.markdown(f"**Generated**\n- {datetime.now().strftime('%B %d, %Y')}\n- {datetime.now().strftime('%H:%M:%S')} UTC")

with col3:
    st.markdown("**Built With**\n- Streamlit\n- Plotly\n- Pandas\n- Python")