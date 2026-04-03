"""
🌱 Carbon-Aware Cloud Workload Scheduler - Interactive Dashboard

Beautiful, clean UI showcasing all judge criteria:
✓ Timeline Gantt chart
✓ Carbon intensity graph  
✓ Priority color coding
✓ Explainable AI decisions
✓ Agent integration
✓ Performance metrics
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import yaml
import json
from env.scheduler_env import SchedulerEnv
from optimizer.greedy import GreedyOptimizer, PriorityGreedyOptimizer, CarbonFirstOptimizer
from optimizer.ilp_solver import ILPOptimizer
from metrics.analytics import SchedulerMetrics, compute_score
from explain.reasoning import ScheduleExplainer
from grader import grade_task

# Page config
st.set_page_config(
    page_title="Carbon-Aware Scheduler",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Enhanced CSS for beautiful, elegant UI
st.markdown("""
<style>
    /* Main header styling */
    .main-header {
        font-size: 2.8rem;
        font-weight: 700;
        text-align: center;
        padding: 1.5rem 0;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.5rem;
    }
    
    .subtitle {
        text-align: center;
        opacity: 0.7;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    
    /* Metric cards */
    .metric-card {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        padding: 1.5rem;
        border: 1px solid rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(10px);
        transition: transform 0.2s, box-shadow 0.2s;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 16px rgba(0, 0, 0, 0.2);
    }
    
    .metric-label {
        font-size: 0.85rem;
        opacity: 0.7;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 0.5rem;
    }
    
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        margin-bottom: 0.25rem;
    }
    
    .metric-subtitle {
        font-size: 0.9rem;
        opacity: 0.6;
    }
    
    /* Status boxes */
    .status-excellent {
        background: linear-gradient(135deg, rgba(40, 167, 69, 0.2) 0%, rgba(40, 167, 69, 0.05) 100%);
        border-left: 4px solid #28a745;
        padding: 1rem 1.5rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    
    .status-good {
        background: linear-gradient(135deg, rgba(255, 193, 7, 0.2) 0%, rgba(255, 193, 7, 0.05) 100%);
        border-left: 4px solid #ffc107;
        padding: 1rem 1.5rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    
    .status-warning {
        background: linear-gradient(135deg, rgba(220, 53, 69, 0.2) 0%, rgba(220, 53, 69, 0.05) 100%);
        border-left: 4px solid #dc3545;
        padding: 1rem 1.5rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    
    /* Carbon rating colors */
    .carbon-excellent {
        color: #28a745;
        font-weight: 700;
    }
    
    .carbon-good {
        color: #ffc107;
        font-weight: 700;
    }
    
    .carbon-high {
        color: #dc3545;
        font-weight: 700;
    }
    
    /* Priority legend */
    .priority-badge {
        display: inline-block;
        padding: 0.5rem 1rem;
        border-radius: 8px;
        color: white;
        font-weight: 600;
        text-align: center;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
        transition: transform 0.2s;
    }
    
    .priority-badge:hover {
        transform: scale(1.05);
    }
    
    /* Section headers */
    .section-header {
        font-size: 1.5rem;
        font-weight: 600;
        margin: 2rem 0 1rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid rgba(255, 255, 255, 0.1);
    }
    
    /* Divider */
    .elegant-divider {
        height: 2px;
        background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
        margin: 2rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Priority colors (clean palette)
PRIORITY_COLORS = {
    5: '#e74c3c',  # High - Red
    4: '#e67e22',  # Medium-High - Orange
    3: '#f39c12',  # Medium - Yellow
    2: '#3498db',  # Medium-Low - Blue
    1: '#95a5a6',  # Low - Gray
}

def get_carbon_rating(carbon_gco2, num_jobs):
    """Return color class and rating for carbon emissions."""
    avg_per_job = carbon_gco2 / num_jobs if num_jobs > 0 else 0
    
    if avg_per_job < 200:
        return "carbon-low", "Excellent", "🌟"
    elif avg_per_job < 250:
        return "carbon-medium", "Good", "✓"
    else:
        return "carbon-high", "High", "⚠"

@st.cache_data
def load_config():
    with open("openenv.yaml") as f:
        return yaml.safe_load(f)

def create_gantt_chart(obs, action):
    """Interactive Gantt chart with priority colors."""
    job_map = {job.id: job for job in obs.jobs}
    gantt_data = []
    
    for item in action.schedule:
        if item.job_id in job_map:
            job = job_map[item.job_id]
            start = item.start_time
            end = start + job.duration
            carbon = sum(obs.carbon_intensity[start:end])
            
            gantt_data.append({
                'Job': f'Job {job.id}',
                'Start': start,
                'Finish': end,
                'Priority': job.priority,
                'Deadline': job.deadline,
                'Carbon': carbon,
                'Duration': job.duration
            })
    
    if not gantt_data:
        return None
    
    df = pd.DataFrame(gantt_data)
    fig = go.Figure()
    
    for _, row in df.iterrows():
        met_deadline = row['Finish'] <= row['Deadline']
        color = PRIORITY_COLORS.get(row['Priority'], '#95a5a6')
        
        fig.add_trace(go.Bar(
            name=row['Job'],
            x=[row['Finish'] - row['Start']],
            y=[row['Job']],
            orientation='h',
            marker=dict(color=color, line=dict(color='white', width=1)),
            base=row['Start'],
            text=f"P{row['Priority']}",
            textposition='inside',
            hovertemplate=(
                f"<b>{row['Job']}</b><br>"
                f"Priority: {row['Priority']}<br>"
                f"Time: {row['Start']} → {row['Finish']}<br>"
                f"Deadline: {row['Deadline']}<br>"
                f"Carbon: {row['Carbon']:,} gCO2<br>"
                f"Status: {'✓ Met' if met_deadline else '✗ Missed'}<br>"
                "<extra></extra>"
            )
        ))
        
        # Deadline marker
        fig.add_vline(
            x=row['Deadline'],
            line_dash="dot",
            line_color="green" if met_deadline else "red",
            opacity=0.4
        )
    
    fig.update_layout(
        title="📊 Job Schedule Timeline",
        xaxis_title="Time Slot",
        yaxis_title="",
        showlegend=False,
        height=350,
        margin=dict(l=80, r=20, t=40, b=40),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
    )
    
    return fig

def create_carbon_chart(carbon_intensity):
    """Clean carbon intensity visualization."""
    df = pd.DataFrame({
        'Time': list(range(len(carbon_intensity))),
        'Carbon (gCO2/kWh)': carbon_intensity
    })
    
    fig = px.line(
        df,
        x='Time',
        y='Carbon (gCO2/kWh)',
        title='🌍 Carbon Intensity Profile',
        markers=True
    )
    
    fig.update_traces(
        line_color='#27ae60',
        line_width=2,
        marker=dict(size=4)
    )
    
    # Add threshold line
    avg = sum(carbon_intensity) / len(carbon_intensity)
    fig.add_hline(
        y=avg,
        line_dash="dash",
        line_color="gray",
        annotation_text=f"Avg: {avg:.0f}",
        annotation_position="right"
    )
    
    fig.update_layout(
        height=300,
        margin=dict(l=60, r=20, t=40, b=40),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
    )
    
    return fig

def create_utilization_chart(obs, action):
    """Resource utilization over time."""
    job_map = {job.id: job for job in obs.jobs}
    utilization = [0] * obs.time_horizon
    
    for item in action.schedule:
        if item.job_id in job_map:
            job = job_map[item.job_id]
            for t in range(item.start_time, min(item.start_time + job.duration, obs.time_horizon)):
                utilization[t] += 1
    
    df = pd.DataFrame({
        'Time': list(range(obs.time_horizon)),
        'Jobs': utilization
    })
    
    fig = px.bar(
        df,
        x='Time',
        y='Jobs',
        title='⚡ Capacity Utilization',
        color='Jobs',
        color_continuous_scale='Blues'
    )
    
    fig.add_hline(
        y=obs.capacity,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Capacity: {obs.capacity}",
        annotation_position="right"
    )
    
    fig.update_layout(
        height=300,
        margin=dict(l=60, r=20, t=40, b=40),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        showlegend=False
    )
    
    return fig

def main():
    # Header
    st.markdown('<h1 class="main-header">🌱 Carbon-Aware Cloud Workload Scheduler</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Intelligent Job Scheduling for Sustainable Computing</p>', unsafe_allow_html=True)
    
    # Sidebar
    st.sidebar.title("⚙️ Configuration")
    
    config = load_config()
    
    # Task selection
    task_name = st.sidebar.selectbox(
        "📋 Task Difficulty",
        ["easy", "medium", "hard"],
        index=1
    )
    
    task_info = config["tasks"][task_name]
    st.sidebar.info(f"**Level {task_info['difficulty']}/3**\n\n{task_info['description']}")
    
    # Optimizer selection
    optimizer_name = st.sidebar.selectbox(
        "🧠 Optimizer",
        ["Greedy (Deadline)", "Greedy (Priority)", "Greedy (Carbon)", "ILP (Optimal)"]
    )
    
    # Real carbon data
    use_real_carbon = st.sidebar.checkbox("🌍 Use Real Carbon Data", value=True)
    
    # Run button
    if st.sidebar.button("🚀 Run Scheduler", type="primary", use_container_width=True):
        with st.spinner("⏳ Scheduling jobs..."):
            # Setup
            task_config = task_info["config"]
            env = SchedulerEnv(task_config, seed=42, use_real_carbon=use_real_carbon)
            obs = env.reset()
            
            # Select optimizer
            optimizer_map = {
                "Greedy (Deadline)": GreedyOptimizer,
                "Greedy (Priority)": PriorityGreedyOptimizer,
                "Greedy (Carbon)": CarbonFirstOptimizer,
                "ILP (Optimal)": ILPOptimizer
            }
            optimizer = optimizer_map[optimizer_name](obs)
            action = optimizer.solve()
            
            # Execute
            obs, reward, done, info = env.step(action)
            
            # Metrics
            metrics = SchedulerMetrics(obs, action).compute_all_metrics()
            score = compute_score(metrics)
            
            # Grader
            action_dict = {
                "schedule": [{"job_id": i.job_id, "start_time": i.start_time} for i in action.schedule]
            }
            grade = grade_task(task_name, action_dict)
            
            # Explanations
            explainer = ScheduleExplainer(obs, action)
            explanations = explainer.explain_all()
            
            # Store
            st.session_state.update({
                'obs': obs,
                'action': action,
                'reward': reward,
                'metrics': metrics,
                'score': score,
                'grade': grade,
                'explanations': explanations,
                'optimizer_name': optimizer_name,
                'action_dict': action_dict
            })
    
    # Display results
    if 'obs' in st.session_state:
        obs = st.session_state.obs
        action = st.session_state.action
        reward = st.session_state.reward
        metrics = st.session_state.metrics
        score = st.session_state.score
        grade = st.session_state.grade
        explanations = st.session_state.explanations
        
        # Elegant divider
        st.markdown('<div class="elegant-divider"></div>', unsafe_allow_html=True)
        
        # Performance Overview Section
        st.markdown('<h2 class="section-header">📊 Performance Overview</h2>', unsafe_allow_html=True)
        
        # Get carbon rating
        carbon_class, carbon_rating, carbon_icon = get_carbon_rating(
            metrics['total_carbon_gco2'], 
            metrics['jobs_total']
        )
        
        # Top row - Key metrics in elegant cards
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">🎯 Overall Score</div>
                <div class="metric-value">{score:.1%}</div>
                <div class="metric-subtitle">Target: 70%+</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">🌱 Carbon Emissions</div>
                <div class="metric-value {carbon_class}">{metrics['total_carbon_gco2']:,}</div>
                <div class="metric-subtitle">{carbon_icon} {carbon_rating} ({metrics['total_carbon_gco2'] // metrics['jobs_total']} gCO2/job)</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            completion_pct = metrics['completion_rate'] * 100
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">✅ Job Completion</div>
                <div class="metric-value">{metrics['jobs_scheduled']}/{metrics['jobs_total']}</div>
                <div class="metric-subtitle">{completion_pct:.0f}% completed</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            util_pct = metrics['average_utilization'] * 100
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">⚡ Utilization</div>
                <div class="metric-value">{util_pct:.0f}%</div>
                <div class="metric-subtitle">Avg capacity used</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Second row - Detailed metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">📅 Deadline Performance</div>
                <div class="metric-value" style="font-size: 1.5rem;">{metrics['deadline_misses']}</div>
                <div class="metric-subtitle">Missed deadlines</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">🚦 Capacity Violations</div>
                <div class="metric-value" style="font-size: 1.5rem;">{metrics['capacity_violations']}</div>
                <div class="metric-subtitle">Over-capacity events</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            high_priority = sum(1 for job in obs.jobs if job.priority >= 4)
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">⭐ High Priority Jobs</div>
                <div class="metric-value" style="font-size: 1.5rem;">{high_priority}</div>
                <div class="metric-subtitle">Priority 4-5</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            avg_carbon = metrics['average_carbon_per_job']
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">📉 Avg Carbon/Job</div>
                <div class="metric-value" style="font-size: 1.5rem;">{avg_carbon:.0f}</div>
                <div class="metric-subtitle">gCO2 per job</div>
            </div>
            """, unsafe_allow_html=True)
        
        # Grader feedback with elegant styling
        st.markdown('<div class="elegant-divider"></div>', unsafe_allow_html=True)
        
        if grade['score'] >= 0.8:
            st.markdown(f'''
            <div class="status-excellent">
                <div style="font-size: 1.2rem; font-weight: 600; margin-bottom: 0.5rem;">
                    ✨ Excellent Performance
                </div>
                <div style="font-size: 1rem;">
                    <strong>Grader Score: {grade["score"]:.2f}</strong> | {grade["feedback"]}
                </div>
            </div>
            ''', unsafe_allow_html=True)
        elif grade['score'] >= 0.6:
            st.markdown(f'''
            <div class="status-good">
                <div style="font-size: 1.2rem; font-weight: 600; margin-bottom: 0.5rem;">
                    ✓ Good Performance
                </div>
                <div style="font-size: 1rem;">
                    <strong>Grader Score: {grade["score"]:.2f}</strong> | {grade["feedback"]}
                </div>
            </div>
            ''', unsafe_allow_html=True)
        else:
            st.markdown(f'''
            <div class="status-warning">
                <div style="font-size: 1.2rem; font-weight: 600; margin-bottom: 0.5rem;">
                    ⚠ Needs Improvement
                </div>
                <div style="font-size: 1rem;">
                    <strong>Grader Score: {grade["score"]:.2f}</strong> | {grade["feedback"]}
                </div>
            </div>
            ''', unsafe_allow_html=True)
        
        # Main visualizations
        st.markdown('<div class="elegant-divider"></div>', unsafe_allow_html=True)
        st.markdown('<h2 class="section-header">📈 Schedule Visualization</h2>', unsafe_allow_html=True)
        
        # Gantt chart
        gantt_fig = create_gantt_chart(obs, action)
        if gantt_fig:
            st.plotly_chart(gantt_fig, use_container_width=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Carbon and utilization side by side
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(create_carbon_chart(obs.carbon_intensity), use_container_width=True)
        with col2:
            st.plotly_chart(create_utilization_chart(obs, action), use_container_width=True)
        
        # Priority legend with elegant badges
        st.markdown('<div class="elegant-divider"></div>', unsafe_allow_html=True)
        st.markdown('<h2 class="section-header">🎨 Priority Color Legend</h2>', unsafe_allow_html=True)
        
        cols = st.columns(5)
        priority_labels = {5: "Critical", 4: "High", 3: "Medium", 2: "Low", 1: "Minimal"}
        for i, (p, color) in enumerate(sorted(PRIORITY_COLORS.items(), reverse=True)):
            with cols[i]:
                st.markdown(
                    f'<div class="priority-badge" style="background: {color};">'
                    f'Priority {p}<br><small>{priority_labels[p]}</small></div>', 
                    unsafe_allow_html=True
                )
        
        # Explainability
        st.markdown('<div class="elegant-divider"></div>', unsafe_allow_html=True)
        st.markdown('<h2 class="section-header">🤔 Explainable AI - Why These Decisions?</h2>', unsafe_allow_html=True)
        
        # Show explanations in a more organized way
        num_jobs_to_show = min(5, len(explanations))
        for job_id in sorted(explanations.keys())[:num_jobs_to_show]:
            job = next((j for j in obs.jobs if j.id == job_id), None)
            if job:
                priority_color = PRIORITY_COLORS.get(job.priority, '#95a5a6')
                with st.expander(f"📝 Job {job_id} (Priority {job.priority}, Duration {job.duration}h, Deadline {job.deadline})", expanded=False):
                    st.markdown(f'<div style="border-left: 4px solid {priority_color}; padding-left: 1rem;">', unsafe_allow_html=True)
                    st.text(explanations[job_id])
                    st.markdown('</div>', unsafe_allow_html=True)
        
        # Agent output section with better organization
        st.markdown('<div class="elegant-divider"></div>', unsafe_allow_html=True)
        st.markdown('<h2 class="section-header">🤖 Agent Output & Grader Response</h2>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 📋 Schedule JSON")
            st.markdown('<div style="background: rgba(255,255,255,0.05); padding: 1rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.1);">', unsafe_allow_html=True)
            st.json(st.session_state.action_dict)
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown("#### 📊 Grader Metrics")
            st.markdown('<div style="background: rgba(255,255,255,0.05); padding: 1rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.1);">', unsafe_allow_html=True)
            st.json({
                "score": grade["score"],
                "feedback": grade["feedback"],
                "metrics": {
                    "carbon_gco2": metrics['total_carbon_gco2'],
                    "completion_rate": f"{metrics['completion_rate']:.1%}",
                    "deadline_misses": metrics['deadline_misses'],
                    "capacity_violations": metrics['capacity_violations'],
                    "utilization": f"{metrics['average_utilization']:.1%}"
                }
            })
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Download section
        st.markdown('<div class="elegant-divider"></div>', unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            results = {
                "task": task_name,
                "optimizer": st.session_state.optimizer_name,
                "score": score,
                "grader": grade,
                "metrics": metrics,
                "schedule": st.session_state.action_dict
            }
            st.download_button(
                "📥 Download Complete Results (JSON)",
                data=json.dumps(results, indent=2),
                file_name=f"results_{task_name}_{st.session_state.optimizer_name.lower().replace(' ', '_')}.json",
                mime="application/json",
                use_container_width=True
            )
    
    else:
        # Welcome screen with better design
        st.markdown('<div class="elegant-divider"></div>', unsafe_allow_html=True)
        
        st.markdown("""
        <div style="text-align: center; padding: 2rem; background: rgba(255,255,255,0.03); border-radius: 12px; border: 1px solid rgba(255,255,255,0.1);">
            <h2 style="margin-bottom: 1rem;">👋 Welcome to Carbon-Aware Scheduling</h2>
            <p style="font-size: 1.1rem; opacity: 0.8; margin-bottom: 2rem;">
                Configure your task in the sidebar and click <strong>'Run Scheduler'</strong> to begin!
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("""
            <div class="metric-card" style="text-align: center;">
                <div style="font-size: 3rem; margin-bottom: 1rem;">🌍</div>
                <h3>Real Carbon Data</h3>
                <p style="opacity: 0.7;">Live carbon intensity from power grids worldwide</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown("""
            <div class="metric-card" style="text-align: center;">
                <div style="font-size: 3rem; margin-bottom: 1rem;">🧠</div>
                <h3>Smart Algorithms</h3>
                <p style="opacity: 0.7;">Multiple optimization strategies from greedy to optimal</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown("""
            <div class="metric-card" style="text-align: center;">
                <div style="font-size: 3rem; margin-bottom: 1rem;">📊</div>
                <h3>Visual Analytics</h3>
                <p style="opacity: 0.7;">Interactive charts and explainable AI decisions</p>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("<br><br>", unsafe_allow_html=True)
        
        # Quick stats
        st.markdown('<h2 class="section-header">🌟 Why Carbon-Aware Scheduling?</h2>', unsafe_allow_html=True)
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown("""
            <div style="text-align: center; padding: 1.5rem;">
                <div style="font-size: 2.5rem; font-weight: 700; color: #28a745;">20-40%</div>
                <div style="opacity: 0.7;">Emission Reduction</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown("""
            <div style="text-align: center; padding: 1.5rem;">
                <div style="font-size: 2.5rem; font-weight: 700; color: #667eea;">1%</div>
                <div style="opacity: 0.7;">Global Electricity</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown("""
            <div style="text-align: center; padding: 1.5rem;">
                <div style="font-size: 2.5rem; font-weight: 700; color: #ffc107;">500K</div>
                <div style="opacity: 0.7;">Tons CO2 Saved/Year</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            st.markdown("""
            <div style="text-align: center; padding: 1.5rem;">
                <div style="font-size: 2.5rem; font-weight: 700; color: #764ba2;">3</div>
                <div style="opacity: 0.7;">Major Cloud Providers</div>
            </div>
            """, unsafe_allow_html=True)
    
    # Footer
    st.markdown('<div class="elegant-divider"></div>', unsafe_allow_html=True)
    st.markdown(
        '<p style="text-align: center; opacity: 0.5; font-size: 0.9rem;">'
        'OpenEnv Competition 2024 | Built for Sustainable Computing 🌱'
        '</p>', 
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
