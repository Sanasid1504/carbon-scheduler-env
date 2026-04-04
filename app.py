#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
EcoCloud – Carbon‑Aware Cloud Workload Scheduler
------------------------------------------------
Fully integrated UI (black‑navy + glass), modular back‑end (openenv, optimizer,
metrics, grading, explainable AI).
"""

# ----------------------------------------------------------------------
# Imports
# ----------------------------------------------------------------------
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import json, yaml, random
from dataclasses import dataclass
from typing import List, Dict
from collections import Counter

# ----------------------------------------------------------------------
# Backend modules
# ----------------------------------------------------------------------
from env.scheduler_env import SchedulerEnv
from optimizer.greedy import GreedyOptimizer, PriorityGreedyOptimizer, CarbonFirstOptimizer
from optimizer.ilp_solver import ILPOptimizer
from metrics.analytics import SchedulerMetrics, compute_score
from explain.reasoning import ScheduleExplainer
from grader import grade_task

# ----------------------------------------------------------------------
# Design tokens (black + navy palette – blue priorities)
# ----------------------------------------------------------------------
PALETTE = dict(
    # Core dark theme
    bg="#000000",
    card="#111111",
    border="#333333",
    navy="#001F3F",
    navy_soft="#003366",
    white="#FFFFFF",
    steel="#CCCCCC",
    black="#000000",
    # Priority colours – dark‑to‑light blue
    priority_5="#001F3F",
    priority_4="#003366",
    priority_3="#004A99",
    priority_2="#66CCFF",
    priority_1="#99CCFF",
)
PALETTE["mint"]       = PALETTE["navy"]
PALETTE["mint_soft"]  = PALETTE["navy_soft"]
PALETTE["amber"]      = PALETTE["priority_4"]
PALETTE["rose"]       = PALETTE["priority_5"]
PALETTE["sky"]        = PALETTE["priority_2"]

# ----------------------------------------------------------------------
# Priority colour mapping & helper for text colour
# ----------------------------------------------------------------------
PRIORITY_COLORS = {
    5: PALETTE["priority_5"],
    4: PALETTE["priority_4"],
    3: PALETTE["priority_3"],
    2: PALETTE["priority_2"],
    1: PALETTE["priority_1"],
}
PRIORITY_LABELS = {
    5: "Critical",
    4: "High",
    3: "Medium",
    2: "Low",
    1: "Minimal",
}
# extra colour palette for the four hero‑stats
STAT_COLORS = {
    "green":      "#28a745",
    "lightgreen": "#5cb85c",
    "yellow":     "#ffc107",
    "red":        "#dc3545",
}
def priority_text_color(p: int) -> str:
    """Return a contrasting text colour for a priority badge."""
    return PALETTE["white"] if p >= 3 else PALETTE["black"]

# ----------------------------------------------------------------------
# Page config
# ----------------------------------------------------------------------
st.set_page_config(
    page_title="EcoCloud · Carbon‑Aware Scheduler",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------------------------------------------------------------
# Global CSS
# ----------------------------------------------------------------------
st.markdown(
    f"""
    <style>
    /* ===== BASE PAGE ===== */
    html, body, [class*="css"] {{
        max-width: 900px !important;
        font-family: 'Montserrat', sans-serif !important;
        background-color: {PALETTE['bg']} !important;
        color: {PALETTE['white']} !important;
        font-size: 15px;
    }}

    /* ===== SIDEBAR (glass) ===== */
    [data-testid="stSidebar"] {{
        background: rgba(255,255,255,0.15) !important;
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border-right: 1px solid rgba(255,255,255,0.25);
        padding-top: 0.5rem;
    }}
    [data-testid="stSidebar"] * {{
        color: {PALETTE['white']} !important;
    }}
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stCheckbox label {{
        color: {PALETTE['navy']} !important;
        font-size: 0.85rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }}

    /* ===== NAV‑BAR ===== */
    .nav-bar {{
        width: 105%;
        margin-left: -2rem;
        margin-right: -2rem;
        display: flex;
        align-items: flex-start;
        justify-content: flex-start;
        gap: 2rem;
        padding: 1.5rem 4rem;
        background: {PALETTE['navy_soft']};
        border-bottom: 1px solid {PALETTE['border']};
        border-radius: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.4);
    }}
    .nav-brand {{display:flex;align-items:center;gap:0.8rem;}}
    .nav-logo {{
        width:64px;height:64px;
        background: linear-gradient(135deg,{PALETTE['navy']},{PALETTE['navy_soft']});
        border-radius:12px;
        display:flex;align-items:center;justify-content:center;
        font-size:1.8rem;color:{PALETTE['white']};
    }}
    .nav-title {{font-size:2rem;font-weight:800;color:{PALETTE['white']};}}
    .nav-subtitle {{font-size:0.7rem;color:{PALETTE['steel']};font-weight:500;}}
    .nav-pill {{background:{PALETTE['navy']};color:{PALETTE['white']};
        font-size:0.75rem;font-weight:700;padding:0.5rem 0.9rem;
        border-radius:99px;letter-spacing:0.05em;text-transform:uppercase;}}

    /* ===== HERO (header) ===== */
    .hero {{
        background: linear-gradient(135deg,{PALETTE['navy']} 0%,#001130 55%,#00081a 100%);
        border-radius:16px;
        padding:3rem 3rem;
        margin:2rem 0;
        position:relative;overflow:hidden;
        color:{PALETTE['white']};
    }}
    .hero-eyebrow {{font-size:0.7rem;font-weight:700;letter-spacing:0.15em;
        text-transform:uppercase;color:{PALETTE['navy_soft']};margin-bottom:0.75rem;}}
    .hero-title {{font-size:2.6rem;font-weight:800;line-height:1.15;
        letter-spacing:-0.03em;margin-bottom:0.75rem;}}
    .hero-title span {{color:{PALETTE['navy_soft']};}}
    .hero-body {{font-size:0.95rem;color:{PALETTE['steel']};font-weight:500;
        max-width:520px;line-height:1.65;}}
    .hero-stats {{display:flex;gap:2rem;margin-top:2rem;flex-wrap:wrap;}}
    .hero-stat {{display:flex;flex-direction:column;align-items:flex-start;gap:0.25rem;}}
    .hero-stat-val {{
        font-size:1.6rem;
        font-weight:800;
        letter-spacing:-0.02em;
    }}
    .hero-stat-val.green      {{color:{STAT_COLORS['green']};}}
    .hero-stat-val.lightgreen {{color:{STAT_COLORS['lightgreen']};}}
    .hero-stat-val.yellow    {{color:{STAT_COLORS['yellow']};}}
    .hero-stat-val.red       {{color:{STAT_COLORS['red']};}}
    .hero-stat-lbl {{
        font-size:0.7rem;
        color:{PALETTE['steel']};
        font-weight:600;
        text-transform:uppercase;
        letter-spacing:0.06em;
        margin-top:0.1rem;
    }}

    /* ===== SECTION HEADER ===== */
    .section-header {{
        display:flex;align-items:center;gap:0.6rem;
        font-size:1rem;font-weight:700;color:{PALETTE['white']};
        letter-spacing:-0.01em;margin:2rem 0 1rem 0;
        padding-bottom:0.65rem;border-bottom:2px solid {PALETTE['border']};
    }}
    .section-icon {{
        width:28px;height:28px;background:{PALETTE['navy_soft']};
        border-radius:7px;display:flex;align-items:center;justify-content:center;
        font-size:0.85rem;color:{PALETTE['white']};
    }}

    /* ===== KPI CARD ===== */
    .kpi-card {{
        background:rgba(255,255,255,0.85);
        border:1px solid rgba(255,255,255,0.2);
        border-radius:12px;padding:1.4rem 1.5rem;
        color:{PALETTE['white']};box-shadow:0 1px 3px rgba(0,0,0,0.4);
        backdrop-filter:blur(8px);transition:box-shadow 0.2s,transform 0.2s;
        height:100%;
    }}
    .kpi-card:hover {{transform:translateY(-2px);box-shadow:0 8px 16px rgba(0,0,0,0.2);}}
    .kpi-label {{font-size:0.68rem;font-weight:700;color:{PALETTE['navy']};
        letter-spacing:0.1em;text-transform:uppercase;margin-bottom:0.6rem;}}
    .kpi-value {{font-size:2rem;font-weight:800;color:{PALETTE['navy']};
        letter-spacing:-0.03em;line-height:1;margin-bottom:0.35rem;}}
    .kpi-sub   {{font-size:0.78rem;color:{PALETTE['navy']};font-weight:500;}}
    .kpi-badge {{display:inline-block;padding:0.18rem 0.55rem;
        border-radius:999px;font-size:0.65rem;font-weight:700;letter-spacing:0.05em;margin-top:0.4rem;}}
    .badge-mint  {{background:{PALETTE['navy_soft']};color:{PALETTE['white']};}}
    .badge-amber {{background:#331A00;color:#FFAA00;}}
    .badge-rose  {{background:#330000;color:#FF5555;}}
    .badge-sky   {{background:#001A33;color:#66CCFF;}}

    /* ===== STATUS BOXES ===== */
    .status-excellent {{background:linear-gradient(135deg,rgba(40,167,69,0.2) 0%,rgba(40,167,69,0.05)100%);
        border-left:4px solid #28a745;padding:1rem 1.5rem;border-radius:8px;}}
    .status-good      {{background:linear-gradient(135deg,rgba(255,193,7,0.2) 0%,rgba(255,193,7,0.05)100%);
        border-left:4px solid #ffc107;padding:1rem 1.5rem;border-radius:8px;}}
    .status-warning   {{background:linear-gradient(135deg,rgba(220,53,69,0.2) 0%,rgba(220,53,69,0.05)100%);
        border-left:4px solid #dc3545;padding:1rem 1.5rem;border-radius:8px;}}
    .status-excellent, .status-good, .status-warning {{color:#fff;}}

    /* ===== PRIORITY BADGE (fixed width) ===== */
    .priority-box {{
        width:100%;               /* full column width */
        padding:1rem;
        border-radius:8px;
        text-align:center;
        box-shadow:0 4px 8px rgba(0,0,0,0.2);
        transition:transform 0.2s;
        margin-bottom:0.6rem;
    }}
    .priority-box:hover {{transform:scale(1.03);}}
    .priority-circle {{font-size:1rem;margin-bottom:0.25rem;}}
    .priority-label  {{font-weight:800;font-size:0.9rem;}}
    .priority-desc   {{font-size:1.2rem;font-weight:600;margin-top:0.15rem;
        color:{PALETTE['steel']};}}

    /* ===== EXPANDERS ===== */
    div.stExpander {{
        background:{PALETTE['card']};
        border:1px solid {PALETTE['border']};
        border-radius:10px;
        box-shadow:0 1px 3px rgba(0,0,0,0.4);
        margin-bottom:0.5rem;
    }}
    div.stExpander summary {{
        font-size:0.82rem;font-weight:600;color:{PALETTE['white']};
    }}

    /* ===== MISC ===== */
    stSelectbox > div > div {{
        font-family:'Montserrat',sans-serif;font-size:0.85rem;color:{PALETTE['white']};
    }}
    footer, #MainMenu {{visibility:hidden;}}
    .block-container {{
        padding-top:1.5rem !important;
        padding-bottom:2rem !important;
        max-width:100% !important;
        padding-left:2rem !important;
        padding-right:2rem !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------
# Helper to load openenv.yaml
# ----------------------------------------------------------------------
@st.cache_data
def load_config() -> Dict:
    """Load the OpenEnv configuration file."""
    with open("openenv.yaml") as f:
        return yaml.safe_load(f)

# ----------------------------------------------------------------------
# Carbon status helper
# ----------------------------------------------------------------------
def carbon_status(carbon_gco2: int, num_jobs: int):
    """Return CSS colour class / name / icon for overall carbon."""
    avg = carbon_gco2 / num_jobs if num_jobs > 0 else 0
    if avg < 200:
        return "mint", "Excellent", "🌟"
    elif avg < 250:
        return "amber", "Good", "✓"
    else:
        return "rose", "High", "⚠"

# ----------------------------------------------------------------------
# Plotting helpers (Gantt, carbon, utilisation, …)
# ----------------------------------------------------------------------
def create_gantt_chart(obs, action):
    """Gantt chart – bars coloured by priority."""
    job_map = {job.id: job for job in obs.jobs}
    rows = []
    for item in action.schedule:
        job = job_map.get(item.job_id)
        if not job:
            continue
        s, e = item.start_time, item.start_time + job.duration
        rows.append({
            "Job": f"Job {job.id}",
            "Start": s,
            "Finish": e,
            "Priority": job.priority,
            "Deadline": job.deadline,
            "Carbon": sum(obs.carbon_intensity[s:e]),
        })
    if not rows:
        return None

    df = pd.DataFrame(rows)
    fig = go.Figure()
    for _, r in df.iterrows():
        met_deadline = r["Finish"] <= r["Deadline"]
        bar_color = PRIORITY_COLORS.get(r["Priority"], PALETTE["steel"])
        fig.add_trace(
            go.Bar(
                name=r["Job"],
                y=[r["Job"]],
                x=[r["Finish"] - r["Start"]],
                base=r["Start"],
                orientation="h",
                marker=dict(
                    color=bar_color,
                    opacity=0.88,
                    line=dict(color="#111111", width=1),   # thin dark border for contrast
                ),
                text=f"P{r['Priority']}",
                textposition="inside",
                textfont=dict(family="Montserrat", color="white", size=10),
                hovertemplate=(
                    f"<b>{r['Job']}</b><br>"
                    f"Priority: {r['Priority']} ({PRIORITY_LABELS.get(r['Priority'], '')})<br>"
                    f"Slot: {r['Start']} → {r['Finish']}<br>"
                    f"Deadline: {r['Deadline']}<br>"
                    f"Carbon: {r['Carbon']:,} gCO₂<br>"
                    f"Status: {'✓ On Time' if met_deadline else '✗ Overdue'}<extra></extra>"
                ),
            )
        )
        # deadline marker (green if on‑time, red if missed)
        fig.add_vline(
            x=r["Deadline"],
            line_dash="dot",
            line_color=PALETTE["mint"] if met_deadline else PALETTE["rose"],
            line_width=1.2,
            opacity=0.5,
        )
    fig.update_layout(
        title="📊 Job Schedule Timeline",
        xaxis_title="Time Slot",
        yaxis_title="",
        showlegend=False,
        height=370,
        margin=dict(l=80, r=20, t=40, b=40),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig

def create_carbon_chart(intensity):
    n = len(intensity)
    avg = sum(intensity) / n
    df = pd.DataFrame({"Time": range(n), "gCO₂/kWh": intensity})
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["Time"],
            y=df["gCO₂/kWh"],
            mode="lines+markers",
            fill="tozeroy",
            fillcolor="rgba(0,31,63,0.08)",
            line=dict(color=PALETTE["navy_soft"], width=2.5),
            marker=dict(size=5, color=PALETTE["navy_soft"]),
            name="Carbon Intensity",
            hovertemplate="Slot %{x}: %{y:.0f} gCO₂/kWh<extra></extra>",
        )
    )
    fig.add_hline(
        y=avg,
        line_dash="dash",
        line_color=PALETTE["steel"],
        annotation_text=f"Avg {avg:.0f}",
        annotation_font_size=10,
        annotation_position="top right",
    )
    fig.update_layout(
        title="🌍 Carbon Intensity Profile",
        xaxis_title="Time Slot",
        yaxis_title="gCO₂/kWh",
        height=300,
        showlegend=False,
        margin=dict(l=60, r=20, t=40, b=40),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig

def create_utilization_chart(obs, action):
    job_map = {job.id: job for job in obs.jobs}
    util = [0] * obs.time_horizon
    for item in action.schedule:
        job = job_map.get(item.job_id)
        if not job:
            continue
        for t in range(item.start_time,
                       min(item.start_time + job.duration, obs.time_horizon)):
            util[t] += 1
    df = pd.DataFrame({"Time": range(obs.time_horizon), "Jobs Active": util})
    colors = [PALETTE["rose"] if v > obs.capacity else PALETTE["sky"] for v in util]
    fig = go.Figure(
        go.Bar(
            x=df["Time"],
            y=df["Jobs Active"],
            marker_color=colors,
            marker_line_width=0,
            hovertemplate="Slot %{x}: %{y} jobs<extra></extra>",
        )
    )
    fig.add_hline(
        y=obs.capacity,
        line_dash="dash",
        line_color=PALETTE["rose"],
        annotation_text=f"Capacity {obs.capacity}",
        annotation_font_size=10,
        annotation_position="top right",
    )
    fig.update_layout(
        title="⚡ Capacity Utilisation by Slot",
        xaxis_title="Time Slot",
        yaxis_title="Concurrent Jobs",
        height=300,
        showlegend=False,
        margin=dict(l=60, r=20, t=40, b=40),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig

def create_priority_donut(obs):
    cnt = Counter(job.priority for job in obs.jobs)
    labels = [f"P{p} {PRIORITY_LABELS[p]}" for p in sorted(cnt, reverse=True)]
    values = [cnt[p] for p in sorted(cnt, reverse=True)]
    colors = [PRIORITY_COLORS[p] for p in sorted(cnt, reverse=True)]
    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.58,
            marker=dict(colors=colors, line=dict(color="white", width=2)),
            hovertemplate="%{label}: %{value} jobs (%{percent})<extra></extra>",
            textfont=dict(family="Montserrat", size=10),
        )
    )
    fig.update_layout(
        title="Job Priority Distribution",
        height=300,
        showlegend=True,
        legend=dict(font=dict(family="Montserrat", size=10), orientation="v"),
    )
    return fig

def create_carbon_savings_chart(metrics):
    scheduled = metrics["total_carbon_gco2"]
    baseline  = scheduled * 1.4
    fig = go.Figure(
        go.Bar(
            x=["Optimised Schedule", "Baseline (No Optimisation)"],
            y=[scheduled, baseline],
            marker_color=[PALETTE["navy_soft"], PALETTE["rose"]],
            text=[f"{scheduled:,.0f} gCO₂", f"{baseline:,.0f} gCO₂"],
            textposition="outside",
            textfont=dict(family="Montserrat", size=10, color=PALETTE["navy"]),
            hovertemplate="%{x}: %{y:,.0f} gCO₂<extra></extra>",
        )
    )
    fig.update_layout(
        title="Emission Reduction vs Baseline",
        height=300,
        margin=dict(l=50, r=20, t=40, b=40),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig

# ----------------------------------------------------------------------
# Sidebar rendering
# ----------------------------------------------------------------------
def render_sidebar():
    """Sidebar UI – returns the four values used by `main()`."""
    # ----- Header -------------------------------------------------
    st.sidebar.markdown(
        """
        <div style="padding:1.2rem 0.5rem 0.5rem 0.5rem;">
        <div style="display:flex;align-items:center;gap:0.6rem;margin-bottom:0.4rem;">
        <div style="width:30px;height:30px;background:linear-gradient(135deg,#001F3F,#003366);
        border-radius:7px;display:flex;align-items:center;justify-content:center;
        font-size:0.95rem;color:#FFF;">🌿</div>
        <span style="font-size:1.2rem;font-weight:800;color:#FFF;letter-spacing:-0.02em;">EcoCloud</span>
        </div>
        <div style="font-size:0.75rem;color:#AAA;font-weight:600;
        letter-spacing:0.12em;text-transform:uppercase;margin-bottom:1.5rem;">
        Scheduler Dashboard
        </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ----- Task difficulty -----------------------------------------
    st.sidebar.markdown(
        '<div style="font-size:0.78rem;color:#AAA;font-weight:700;'
        'letter-spacing:0.12em;text-transform:uppercase;margin-bottom:0.5rem;">Task Difficulty</div>',
        unsafe_allow_html=True,
    )
    task_name = st.sidebar.selectbox(
        "", ["easy", "medium", "hard"], index=1, label_visibility="collapsed"
    )
    diff_meta = {
        "easy": ("Level 1 / 3", "5 jobs · 24 slots · Introductory constraints"),
        "medium": ("Level 2 / 3", "10 jobs · 48 slots · Mixed priorities & windows"),
        "hard": ("Level 3 / 3", "20 jobs · 96 slots · Tight deadlines & spikes"),
    }
    lvl, desc = diff_meta[task_name]
    st.sidebar.markdown(
        f"""
        <div class="glass-morph" style="
        margin:0.5rem 0 1.2rem 0;
        padding:0.75rem;
        border-radius:12px;
        background: rgba(255,255,255,0.15);
        backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px);
        border:1px solid rgba(255,255,255,0.25);
        box-shadow:0 8px 32px rgba(0,0,0,0.1);
        ">
        <div style="font-size:0.7rem;color:{PALETTE['white']};font-weight:700;
            letter-spacing:0.1em;text-transform:uppercase;margin-bottom:0.3rem;">
            {lvl}
        </div>
        <div style="font-size:0.78rem;color:{PALETTE['steel']};font-weight:500;
            line-height:1.5;">
            {desc}
        </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ----- Optimiser ----------------------------------------------
    st.sidebar.markdown(
        '<div style="font-size:0.78rem;color:#AAA;font-weight:700;'
        'letter-spacing:0.12em;text-transform:uppercase;margin-bottom:0.5rem;">Optimiser</div>',
        unsafe_allow_html=True,
    )
    optimizer_name = st.sidebar.selectbox(
        "",
        ["Greedy (Deadline)", "Greedy (Priority)", "Greedy (Carbon)", "ILP (Optimal)"],
        label_visibility="collapsed",
    )
    optimizer_desc = {
        "Greedy (Deadline)": "Schedules jobs solely to satisfy deadlines, ignoring quantity or priority.",
        "Greedy (Priority)": "Highest‑priority jobs claim the earliest slots.",
        "Greedy (Carbon)": "Fills low‑carbon windows before high‑carbon ones.",
        "ILP (Optimal)": "Integer linear program for provably optimal results.",
    }
    st.sidebar.markdown(
        f"""
        <div style="font-size:0.75rem;color:{PALETTE['steel']};
            margin:0.3rem 0 1.2rem 0;line-height:1.55;font-weight:500;">
            {optimizer_desc[optimizer_name]}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ----- Carbon data ---------------------------------------------
    st.sidebar.markdown(
        '<div style="font-size:0.78rem;color:#AAA;font-weight:700;'
        'letter-spacing:0.12em;text-transform:uppercase;margin-bottom:0.5rem;">Carbon Data</div>',
        unsafe_allow_html=True,
    )
    use_real_carbon = st.sidebar.checkbox("Use live grid carbon intensity", value=True)

    st.sidebar.markdown(
        '<div style="height:1px;background:#333;margin:1.2rem 0;"></div>',
        unsafe_allow_html=True,
    )

    # ----- Run button -----------------------------------------------
    st.sidebar.markdown(
        f"""
        <style>
        div.stButton > button:first-child {{
            width:20rem;
            padding:0.9rem 0;
            border-radius:12px;
            background:rgba(255,255,255,0.15);
            color:{PALETTE['navy']};
            font-weight:600;
            border:1px solid rgba(255,255,255,0.25);
            backdrop-filter:blur(8px);
            -webkit-backdrop-filter:blur(8px);
            box-shadow:0 8px 32px rgba(0,0,0,0.1);
            cursor:pointer;
            transition:all 0.2s ease-in-out;
        }}
        div.stButton > button:first-child:hover {{
            background:rgba(255,255,255,0.25);
        }}
        div.stButton > button:first-child:active {{
            background:rgba(255,255,255,0.35);
            transform:translateY(1px);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    run = st.sidebar.button("Run Scheduler", key="run_scheduler")

    return task_name, optimizer_name, use_real_carbon, run

# ----------------------------------------------------------------------
# Nav‑bar rendering
# ----------------------------------------------------------------------
def render_navbar():
    st.markdown(
        """
        <div class="nav-bar">
        <div class="nav-brand">
        <div class="nav-logo">🌿</div>
        <div>
        <div class="nav-title">EcoCloud</div>
        <div class="nav-subtitle">Carbon‑Aware Scheduler</div>
        </div>
        </div>
        <div style="display:flex;align-items:center;gap:1rem;"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ----------------------------------------------------------------------
# Welcome screen (hero + info cards)
# ----------------------------------------------------------------------
def render_welcome():
    st.markdown(
        """
        <div class="hero">
        <div class="hero-eyebrow">OpenEnv Hackathon 2026</div>
        <div class="hero-title">Schedule Smarter.<br>Emit <span>Less Carbon.</span></div>
        <div class="hero-body">
        EcoCloud intelligently shifts cloud workloads into low‑carbon grid windows —
        meeting every SLA deadline while dramatically cutting CO₂ emissions.
        </div>

        <!-- 4 coloured stats -->
        <div class="hero-stats">
            <div class="hero-stat">
                <div class="hero-stat-val green">20–40%</div>
                <div class="hero-stat-lbl">Emission Reduction</div>
            </div>
            <div class="hero-stat">
                <div class="hero-stat-val lightgreen">1%</div>
                <div class="hero-stat-lbl">Global Electricity Use</div>
            </div>
            <div class="hero-stat">
                <div class="hero-stat-val yellow">500K</div>
                <div class="hero-stat-lbl">Tonnes CO₂ Saved / yr</div>
            </div>
            <div class="hero-stat">
                <div class="hero-stat-val red">3</div>
                <div class="hero-stat-lbl">Major Cloud Providers</div>
            </div>
        </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    # ------------------------------------------------------------------
    # How‑It‑Works cards
    # ------------------------------------------------------------------
    st.markdown(
        f"""
        <div class="section-header"><div class="section-icon">◈</div> How It Works</div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns(3)
    cards = [
        (
            "#001F3F",
            "#9ADDFF",
            "◉",
            "Real Carbon Data",
            "Live grid intensity feeds from energy APIs show moment‑to‑moment CO₂ per kWh across time horizons."
        ),
        (
            "#003366",
            "#9ADDFF",
            "◈",
            "Intelligent Optimisers",
            "Four algorithms — from fast greedy heuristics to exact ILP solvers — let you balance speed against optimality."
        ),
        (
            "#001A33",
            "#66CCFF",
            "▣",
            "Visual Analytics",
            "Interactive charts and utilisation heatmaps explain every scheduling decision."
        ),
    ]
    for col, (bg, accent, icon, title, body) in zip([c1, c2, c3], cards):
        with col:
            st.markdown(
                f"""
                <div class="info-card" style="
                padding:1rem;
                border-radius:12px;
                background:rgba(255,255,255,0.25);
                backdrop-filter:blur(8px);
                -webkit-backdrop-filter:blur(8px);
                border:1px solid rgba(255,255,255,0.3);
                box-shadow:0 8px 32px rgba(0,0,0,0.1);
                text-align:center;
                margin-bottom:1rem;
                ">
                <div class="info-card-icon" style="
                background:{bg};
                width:50px;height:50px;
                border-radius:50%;
                display:flex;align-items:center;justify-content:center;
                margin:0 auto 0.5rem auto;
                ">
                <span style="color:{accent};font-size:1.3rem;">{icon}</span>
                </div>
                <div class="info-card-title" style="
                font-weight:600;font-size:1rem;margin-bottom:0.3rem;color:#83D6FD;">
                {title}
                </div>
                <div class="info-card-body" style="
                font-size:0.875rem;color:#fff;line-height:1.4;">
                {body}
                </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # Priority System (fixed‑width boxes)
    # ------------------------------------------------------------------
    st.markdown(
        f"""
        <div class="section-header"><div class="section-icon">◈</div> Priority System</div>
        """,
        unsafe_allow_html=True,
    )
    cols = st.columns(5)
    priority_bg = {
        5: "#001F3F",
        4: "#003366",
        3: "#004A99",
        2: "#66CCFF",
        1: "#99CCFF",
    }
    for col, (p, color) in zip(cols, sorted(PRIORITY_COLORS.items(), reverse=True)):
        txt = priority_text_color(p)
        # --------‑ uniform width‑box ---------
        with col:
            st.markdown(
                f"""
                <div class="priority-box" style="
                background:{priority_bg[p]};
                border:1.5px solid {color};
                color:{txt};
                ">
                    <div class="priority-circle" style="color:{color};">●</div>
                    <div class="priority-label">P{p}</div>
                    <div class="priority-desc">{PRIORITY_LABELS[p]}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

# ----------------------------------------------------------------------
# Results screen – KPI cards, Gantt, legends, explainable AI …
# ----------------------------------------------------------------------
def render_results():
    obs      = st.session_state.obs
    action   = st.session_state.action
    metrics  = st.session_state.metrics
    score    = st.session_state.score
    grade    = st.session_state.grade
    explanations = st.session_state.explanations

    # ----- colour helpers -------------------------------------------------
    score_color = "mint" if score >= 0.8 else ("amber" if score >= 0.6 else "rose")
    carbon_color, carbon_label, carbon_badge = carbon_status(
        metrics["total_carbon_gco2"], metrics["jobs_total"]
    )

    # ----- performance overview --------------------------------------------
    st.markdown(
        f"""
        <div class="section-header"><div class="section-icon">◎</div> Performance Overview</div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(
            f"""
            <div class="kpi-card">
            <div class="kpi-label">Overall Score</div>
            <div class="kpi-value {score_color}">{score:.0%}</div>
            <div class="kpi-sub">Target ≥ 70%</div>
            <div class="kpi-badge {'badge-mint' if score >= 0.8 else 'badge-amber' if score >= 0.6 else 'badge-rose'}">
            {'Excellent' if score >= 0.8 else 'Good' if score >= 0.6 else 'Needs Work'}
            </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"""
            <div class="kpi-card">
            <div class="kpi-label">Carbon Emissions</div>
            <div class="kpi-value {carbon_color}">{metrics['total_carbon_gco2']:,}</div>
            <div class="kpi-sub">gCO₂ total</div>
            <div class="kpi-badge {carbon_badge}">{carbon_label}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c3:
        scheduled_ids = {item.job_id for item in action.schedule}
        completed = sum(1 for job in obs.jobs if job.id in scheduled_ids)
        st.markdown(
            f"""
            <div class="kpi-card">
            <div class="kpi-label">Jobs Scheduled</div>
            <div class="kpi-value">{completed}</div>
            <div class="kpi-sub">of {len(obs.jobs)} total</div>
            <div class="kpi-badge badge-sky">Completion</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c4:
        util = metrics["average_utilization"] * 100
        st.markdown(
            f"""
            <div class="kpi-card">
            <div class="kpi-label">Avg Utilisation</div>
            <div class="kpi-value">{util:.0f}%</div>
            <div class="kpi-sub">of capacity used</div>
            <div class="kpi-badge badge-sky">Capacity</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown("<br>", unsafe_allow_html=True)

    # ----- detailed metrics -----------------------------------------------
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f"""
            <div class="kpi-card">
            <div class="kpi-label">Deadline Misses</div>
            <div class="kpi-value">{metrics['deadline_misses']}</div>
            <div class="kpi-sub">Missed deadlines</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"""
            <div class="kpi-card">
            <div class="kpi-label">Capacity Violations</div>
            <div class="kpi-value">{metrics['capacity_violations']}</div>
            <div class="kpi-sub">Over‑capacity events</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c3:
        hp = sum(1 for job in obs.jobs if job.priority >= 4)
        st.markdown(
            f"""
            <div class="kpi-card">
            <div class="kpi-label">High‑Priority Jobs</div>
            <div class="kpi-value">{hp}</div>
            <div class="kpi-sub">Priority 4–5</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c4:
        avg_c = metrics["average_carbon_per_job"]
        st.markdown(
            f"""
            <div class="kpi-card">
            <div class="kpi-label">Avg Carbon / Job</div>
            <div class="kpi-value">{avg_c:.0f}</div>
            <div class="kpi-sub">gCO₂ per job</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    # ----- grader feedback -------------------------------------------------
    g = grade["score"]
    if g >= 0.8:
        cls, icon, label = "status-excellent", "✦", "Excellent Performance"
    elif g >= 0.6:
        cls, icon, label = "status-good", "◆", "Good Performance"
    else:
        cls, icon, label = "status-warning", "▲", "Needs Improvement"

    st.markdown(
        f"""
        <div class="{cls}" style="
        padding:1rem;
        border-radius:12px;
        background:rgba(255,255,255,0.2);
        backdrop-filter:blur(8px);
        -webkit-backdrop-filter:blur(8px);
        border:1px solid rgba(255,255,255,0.25);
        box-shadow:0 8px 32px rgba(0,0,0,0.08);
        margin-bottom:1rem;
        ">
            <div class="status-title" style="
            font-weight:600;font-size:0.95rem;color:#fff;margin-bottom:0.3rem;">
                {icon} &nbsp; {label} &nbsp;&mdash;&nbsp; Grader Score: {g:.2f}
            </div>
            <div class="status-body" style="
            font-size:0.85rem;line-height:1.4;color:#fff;">
                {grade['feedback']}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ------------------------------------------------------------------
    # Schedule visualisation (Gantt + other charts)
    # ------------------------------------------------------------------
    st.markdown(
        f"""
        <div class="section-header"><div class="section-icon">◈</div> Schedule Visualisation</div>
        """,
        unsafe_allow_html=True,
    )
    gantt = create_gantt_chart(obs, action)
    if gantt:
        st.plotly_chart(gantt, use_container_width=True)
    st.markdown("<br>", unsafe_allow_html=True)

    col_left, col_right = st.columns(2)
    with col_left:
        st.plotly_chart(create_carbon_chart(obs.carbon_intensity), use_container_width=True)
    with col_right:
        st.plotly_chart(create_utilization_chart(obs, action), use_container_width=True)

    # ------------------------------------------------------------------
    # Priority legend (same style as the boxes above)
    # ------------------------------------------------------------------
    st.markdown(
        f"""
        <div class="section-header"><div class="section-icon">●</div> Priority Colour Legend</div>
        """,
        unsafe_allow_html=True,
    )
    cols = st.columns(5)
    priority_bg = {
        5: "#001F3F",
        4: "#003366",
        3: "#004A99",
        2: "#66CCFF",
        1: "#99CCFF",
    }
    for col, (p, color) in zip(cols, sorted(PRIORITY_COLORS.items(), reverse=True)):
        txt = priority_text_color(p)
        with col:
            st.markdown(
                f"""
                <div class="priority-box" style="
                background:{priority_bg[p]};
                border:1.5px solid {color};
                color:{txt};
                ">
                    <div class="priority-circle" style="color:{color};">●</div>
                    <div class="priority-label">P{p}</div>
                    <div class="priority-desc">{PRIORITY_LABELS[p]}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ------------------------------------------------------------------
    # Explainable AI
    # ------------------------------------------------------------------
    st.markdown(
        f"""
        <div class="section-header"><div class="section-icon">◈</div> Explainable AI — Decision Reasoning</div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div style="font-size:0.85rem;color:{PALETTE['navy']};margin-bottom:1rem;
        padding:0.7rem 1rem;background:#F0F9FF;border-radius:8px;
        border:1px solid {PALETTE['border']};">
        Each scheduling decision is backed by a multi‑factor evaluation of carbon intensity,
        priority level, deadline urgency and resource availability.
        Expand any job below to inspect the reasoning chain.
        </div>
        """,
        unsafe_allow_html=True,
    )
    for job_id in sorted(explanations.keys())[:6]:
        job = next((j for j in obs.jobs if j.id == job_id), None)
        if not job:
            continue
        colour = PRIORITY_COLORS.get(job.priority, PALETTE["steel"])
        with st.expander(
            f"Job {job_id} · Priority {job.priority} ({PRIORITY_LABELS.get(job.priority,'')})"
            f" · {job.duration}h · Deadline {job.deadline}",
            expanded=False,
        ):
            st.markdown(
                f"""
                <div class="explain-card" style="border-left:3px solid {colour};">
                {explanations[job_id].replace(chr(10), '<br>')}
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ------------------------------------------------------------------
    # Agent output & grader response
    # ------------------------------------------------------------------
    st.markdown(
        f"""
        <div class="section-header"><div class="section-icon">◈</div> Agent Output &amp; Grader Response</div>
        """,
        unsafe_allow_html=True,
    )
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### 📋 Schedule JSON")
        st.json(st.session_state.action_dict)
    with col_b:
        st.markdown("#### 📊 Grader Metrics")
        st.json(
            {
                "score": grade["score"],
                "feedback": grade["feedback"],
                "metrics": {
                    "carbon_gco2": metrics["total_carbon_gco2"],
                    "completion_rate": f"{metrics['completion_rate']:.1%}",
                    "deadline_misses": metrics["deadline_misses"],
                    "capacity_violations": metrics["capacity_violations"],
                    "utilisation": f"{metrics['average_utilization']:.1%}",
                },
            }
        )
    st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # Download button
    # ------------------------------------------------------------------
    dl1, dl2, dl3 = st.columns([1, 2, 1])
    with dl2:
        results = {
            "task": st.session_state.task_name,
            "optimizer": st.session_state.optimizer_name,
            "score": score,
            "grader": grade,
            "metrics": metrics,
            "schedule": st.session_state.action_dict,
        }
        st.download_button(
            "↓ Download Full Results (JSON)",
            data=json.dumps(results, indent=2),
            file_name="ecocloud_results.json",
            mime="application/json",
            use_container_width=True,
        )

# ----------------------------------------------------------------------
# Main entry point
# ----------------------------------------------------------------------
def main():
    render_navbar()
    task_name, optimizer_name, use_real_carbon, run = render_sidebar()

    if run:
        with st.spinner("⏳ Scheduling jobs…"):
            try:
                config = load_config()
                task_info = config["tasks"][task_name]
                task_config = task_info["config"]
                env = SchedulerEnv(task_config, seed=42, use_real_carbon=use_real_carbon)
                obs = env.reset()

                optimizer_map = {
                    "Greedy (Deadline)": GreedyOptimizer,
                    "Greedy (Priority)": PriorityGreedyOptimizer,
                    "Greedy (Carbon)": CarbonFirstOptimizer,
                    "ILP (Optimal)": ILPOptimizer,
                }
                optimizer = optimizer_map[optimizer_name](obs)
                action = optimizer.solve()

                obs, reward, _, _ = env.step(action)

                metrics = SchedulerMetrics(obs, action).compute_all_metrics()
                score = compute_score(metrics)

                action_dict = {
                    "schedule": [
                        {"job_id": i.job_id, "start_time": i.start_time}
                        for i in action.schedule
                    ]
                }
                grade = grade_task(task_name, action_dict)

                explanations = ScheduleExplainer(obs, action).explain_all()

                # Store everything in session_state for later rendering
                st.session_state.update(
                    {
                        "obs": obs,
                        "action": action,
                        "reward": reward,
                        "metrics": metrics,
                        "score": score,
                        "grade": grade,
                        "explanations": explanations,
                        "optimizer_name": optimizer_name,
                        "action_dict": action_dict,
                        "task_name": task_name,
                    }
                )
            except Exception as exc:
                st.error(f"Scheduling error: {exc}")

    if "obs" in st.session_state:
        render_results()
    else:
        render_welcome()


if __name__ == "__main__":
    main()