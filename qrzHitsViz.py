import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import os
import json
from datetime import timedelta

# Consistent palette
COLOR_PRIMARY = '#3b82f6'
COLOR_SECONDARY = '#10b981'
COLOR_SPIKE = '#ef4444'
COLOR_QUIET = '#6366f1'
CMAP_HEAT = 'YlGnBu'


def load_and_process_data(filepath):
    """Load CSV and process datetime columns (all UTC)."""
    df = pd.read_csv(filepath)
    df['Time_UTC'] = pd.to_datetime(df['Time'], utc=True)
    df = df.sort_values('Time_UTC')

    df['Value_Change'] = df['Hits'].diff()
    df['Time_Delta'] = df['Time_UTC'].diff().dt.total_seconds() / 3600
    df['Rate_Per_Hour'] = df['Value_Change'] / df['Time_Delta']

    df['Hour_UTC'] = df['Time_UTC'].dt.hour
    df['Day_of_Week_UTC'] = df['Time_UTC'].dt.day_name()
    df['Date_UTC'] = df['Time_UTC'].dt.date

    return df


def make_chart_layout(title, xaxis_title='', yaxis_title=''):
    """Shared layout defaults for all charts."""
    return dict(
        title=dict(text=title, font=dict(size=16, color='#333333')),
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(family='sans-serif', color='#333333'),
        xaxis=dict(
            title=xaxis_title,
            gridcolor='#eeeeee',
            linecolor='#cccccc',
        ),
        yaxis=dict(
            title=yaxis_title,
            gridcolor='#eeeeee',
            linecolor='#cccccc',
        ),
        margin=dict(l=60, r=30, t=50, b=60),
    )


def fig_raw_values(df):
    """Cumulative hits over time."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['Time_UTC'], y=df['Hits'],
        mode='lines', line=dict(color=COLOR_PRIMARY, width=2),
        fill='tozeroy', fillcolor='rgba(59,130,246,0.08)',
        name='Hits',
        hovertemplate='%{x|%Y-%m-%d %H:%M UTC}<br>Hits: %{y:,}<extra></extra>',
    ))
    fig.update_layout(**make_chart_layout(
        'QRZ Profile Hits Over Time',
        xaxis_title='Date/Time (UTC)',
        yaxis_title='Hits',
    ))
    y_min = df['Hits'].min()
    y_pad = (df['Hits'].max() - y_min) * 0.05
    fig.update_yaxes(range=[y_min - y_pad, df['Hits'].max() + y_pad])
    fig.update_yaxes(separatethousands=True)
    return fig


def fig_raw_values_log(df):
    """Cumulative hits over time, log scale."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['Time_UTC'], y=df['Hits'],
        mode='lines', line=dict(color=COLOR_PRIMARY, width=2),
        name='Hits',
        hovertemplate='%{x|%Y-%m-%d %H:%M UTC}<br>Hits: %{y:,}<extra></extra>',
    ))
    fig.update_layout(**make_chart_layout(
        'QRZ Profile Hits (Log Scale)',
        xaxis_title='Date/Time (UTC)',
        yaxis_title='Hits (Log Scale)',
    ))
    fig.update_yaxes(type='log')
    return fig


def fig_recent_raw_values(df, days=30):
    """Last N days of hits."""
    cutoff = df['Time_UTC'].max() - pd.Timedelta(days=days)
    df_recent = df[df['Time_UTC'] >= cutoff]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_recent['Time_UTC'], y=df_recent['Hits'],
        mode='lines', line=dict(color=COLOR_PRIMARY, width=2),
        fill='tozeroy', fillcolor='rgba(59,130,246,0.08)',
        name='Hits',
        hovertemplate='%{x|%Y-%m-%d %H:%M UTC}<br>Hits: %{y:,}<extra></extra>',
    ))
    fig.update_layout(**make_chart_layout(
        f'Hits, Last {days} Days',
        xaxis_title='Date/Time (UTC)',
        yaxis_title='Hits',
    ))
    y_min = df_recent['Hits'].min()
    y_pad = (df_recent['Hits'].max() - y_min) * 0.05
    fig.update_yaxes(range=[y_min - y_pad, df_recent['Hits'].max() + y_pad])
    fig.update_yaxes(separatethousands=True)
    return fig


def fig_hourly_rate(df):
    """Average hit rate by hour of day (UTC)."""
    df_rate = df.dropna(subset=['Rate_Per_Hour'])
    if df_rate.empty:
        return None

    hourly_avg = df_rate.groupby('Hour_UTC')['Rate_Per_Hour'].mean().reindex(range(24), fill_value=0)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=hourly_avg.index, y=hourly_avg.values,
        marker_color=COLOR_PRIMARY,
        hovertemplate='Hour %{x}:00 UTC<br>Avg rate: %{y:.2f}/hr<extra></extra>',
    ))
    fig.update_layout(**make_chart_layout(
        'Average Hourly Rate of Change (UTC)',
        xaxis_title='Hour of Day (UTC)',
        yaxis_title='Mean Rate (hits/hour)',
    ))
    fig.update_xaxes(dtick=1)
    return fig


def fig_activity_heatmap(df):
    """Activity heatmap: hour of day vs date."""
    if len(df['Date_UTC'].unique()) <= 7:
        return None

    pivot = df.pivot_table(
        values='Value_Change', index='Hour_UTC', columns='Date_UTC', aggfunc='sum'
    )
    if pivot.empty:
        return None

    # Thin out date labels
    dates = [str(d) for d in pivot.columns]
    step = max(1, len(dates) // 15)
    tickvals = list(range(0, len(dates), step))
    ticktext = [dates[i] for i in tickvals]

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=list(range(len(dates))),
        y=pivot.index,
        colorscale=CMAP_HEAT,
        colorbar=dict(title='Value Change'),
        hovertemplate='Date: %{customdata}<br>Hour: %{y}:00 UTC<br>Change: %{z:.1f}<extra></extra>',
        customdata=[[dates[c] for c in range(len(dates))] for _ in pivot.index],
    ))
    fig.update_layout(**make_chart_layout(
        'Daily Activity Heatmap (UTC)',
        xaxis_title='Date',
        yaxis_title='Hour of Day (UTC)',
    ))
    fig.update_xaxes(tickvals=tickvals, ticktext=ticktext, tickangle=45)
    fig.update_yaxes(dtick=1)
    return fig


def fig_dow_heatmap(df):
    """Day-of-week x hour heatmap."""
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    df_rate = df.dropna(subset=['Rate_Per_Hour'])
    if df_rate.empty:
        return None

    df_dow = df_rate.groupby(['Day_of_Week_UTC', 'Hour_UTC'])['Rate_Per_Hour'].mean().reset_index()
    pivot = df_dow.pivot(index='Day_of_Week_UTC', columns='Hour_UTC', values='Rate_Per_Hour')
    pivot = pivot.reindex([d for d in day_order if d in pivot.index])
    pivot = pivot.reindex(columns=range(24), fill_value=0)

    if pivot.empty:
        return None

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=[f'{h:02d}:00' for h in range(24)],
        y=pivot.index.tolist(),
        colorscale=CMAP_HEAT,
        colorbar=dict(title='Avg Rate/Hr'),
        hovertemplate='%{y} %{x} UTC<br>Avg rate: %{z:.2f}/hr<extra></extra>',
    ))
    fig.update_layout(**make_chart_layout(
        'Average Activity by Day of Week (UTC)',
        xaxis_title='Hour of Day (UTC)',
        yaxis_title='Day of Week',
    ))
    return fig


def fig_contribution_calendar(df):
    """GitHub-style contribution calendar of daily hit gains."""
    daily = df.groupby('Date_UTC')['Hits'].agg(['first', 'last'])
    daily['gain'] = daily['last'] - daily['first']
    daily = daily['gain']

    if daily.empty:
        return None

    start_date = daily.index.min()
    end_date = daily.index.max()
    all_dates = pd.date_range(start_date, end_date, freq='D').date
    daily = daily.reindex(all_dates, fill_value=0)

    # Build week/day grid (Sun=0 convention)
    dates_list = list(daily.index)
    values_list = list(daily.values)
    weeks = []
    days = []
    texts = []
    colors = []

    for i, (date, val) in enumerate(zip(dates_list, values_list)):
        ts = pd.Timestamp(date)
        dow_sun = (ts.dayofweek + 1) % 7  # Sun=0
        week = (i + ((pd.Timestamp(dates_list[0]).dayofweek + 1) % 7)) // 7
        weeks.append(week)
        days.append(dow_sun)
        texts.append(f'{date}: +{val:.0f} hits')
        colors.append(max(val, 0))

    vmax = max(daily.quantile(0.95), 1)

    fig = go.Figure(data=go.Heatmap(
        x=weeks, y=days, z=colors,
        colorscale='Greens',
        zmin=0, zmax=vmax,
        text=texts, hoverinfo='text',
        showscale=True,
        colorbar=dict(title='Daily Gain'),
        xgap=2, ygap=2,
    ))

    # Month labels
    month_labels_x = []
    month_labels_text = []
    seen_months = set()
    for i, date in enumerate(dates_list):
        ts = pd.Timestamp(date)
        key = (ts.year, ts.month)
        if key not in seen_months and ts.day <= 7:
            seen_months.add(key)
            week = (i + ((pd.Timestamp(dates_list[0]).dayofweek + 1) % 7)) // 7
            month_labels_x.append(week)
            month_labels_text.append(ts.strftime('%b'))

    fig.update_layout(
        title=dict(text='Daily Hit Gains: Contribution Calendar (UTC)', font=dict(size=16, color='#333333')),
        plot_bgcolor='white',
        paper_bgcolor='white',
        yaxis=dict(
            tickvals=[0, 1, 2, 3, 4, 5, 6],
            ticktext=['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'],
            autorange='reversed',
        ),
        xaxis=dict(
            tickvals=month_labels_x,
            ticktext=month_labels_text,
            side='top',
        ),
        margin=dict(l=60, r=30, t=80, b=20),
        height=250,
    )
    return fig


def fig_polar_clock(df):
    """Polar/clock chart of hourly hit rate."""
    df_rate = df.dropna(subset=['Rate_Per_Hour'])
    if df_rate.empty:
        return None

    hourly_avg = df_rate.groupby('Hour_UTC')['Rate_Per_Hour'].mean().reindex(range(24), fill_value=0)

    # Close the loop
    theta = [f'{h:02d}:00' for h in range(24)] + ['00:00']
    r = list(hourly_avg.values) + [hourly_avg.values[0]]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=r, theta=theta,
        fill='toself',
        fillcolor='rgba(59,130,246,0.15)',
        line=dict(color=COLOR_PRIMARY, width=2),
        name='Avg Rate/Hr',
        hovertemplate='%{theta} UTC<br>Avg rate: %{r:.2f}/hr<extra></extra>',
    ))
    fig.update_layout(
        title=dict(text='Hourly Activity Profile (UTC)', font=dict(size=16, color='#333333')),
        polar=dict(
            radialaxis=dict(visible=True, gridcolor='#eeeeee'),
            angularaxis=dict(direction='clockwise', rotation=90),
        ),
        paper_bgcolor='white',
        margin=dict(l=60, r=60, t=60, b=40),
        height=500,
    )
    return fig


def fig_anomaly_detection(df, sigma=2):
    """Detect and highlight spikes and quiet periods."""
    df_rate = df.dropna(subset=['Rate_Per_Hour']).copy()
    if df_rate.empty:
        return None

    mean_rate = df_rate['Rate_Per_Hour'].mean()
    std_rate = df_rate['Rate_Per_Hour'].std()
    upper_thresh = mean_rate + sigma * std_rate
    lower_thresh = max(mean_rate - sigma * std_rate, 0)

    df_rate['is_spike'] = df_rate['Rate_Per_Hour'] > upper_thresh
    df_rate['is_quiet'] = df_rate['Rate_Per_Hour'] <= lower_thresh

    spikes = df_rate[df_rate['is_spike']]
    quiets = df_rate[df_rate['is_quiet']]
    normal = df_rate[~df_rate['is_spike'] & ~df_rate['is_quiet']]

    fig = make_subplots(rows=2, cols=1, subplot_titles=[
        f'Anomaly Detection: Rate of Change (UTC)',
        'Daily Gains with Spike Days Highlighted',
    ], vertical_spacing=0.12)

    # Top: rate over time
    fig.add_trace(go.Scatter(
        x=df_rate['Time_UTC'], y=df_rate['Rate_Per_Hour'],
        mode='lines', line=dict(color='#999999', width=1),
        opacity=0.6, name='Rate', showlegend=False,
        hovertemplate='%{x|%Y-%m-%d %H:%M UTC}<br>Rate: %{y:.2f}/hr<extra></extra>',
    ), row=1, col=1)

    if not spikes.empty:
        fig.add_trace(go.Scatter(
            x=spikes['Time_UTC'], y=spikes['Rate_Per_Hour'],
            mode='markers', marker=dict(color=COLOR_SPIKE, size=6),
            name=f'Spike (>{sigma}\u03c3)',
            hovertemplate='%{x|%Y-%m-%d %H:%M UTC}<br>Rate: %{y:.2f}/hr<extra></extra>',
        ), row=1, col=1)

    if not quiets.empty:
        fig.add_trace(go.Scatter(
            x=quiets['Time_UTC'], y=quiets['Rate_Per_Hour'],
            mode='markers', marker=dict(color=COLOR_QUIET, size=5, symbol='triangle-down'),
            name=f'Quiet (\u2264{sigma}\u03c3 below)',
            hovertemplate='%{x|%Y-%m-%d %H:%M UTC}<br>Rate: %{y:.2f}/hr<extra></extra>',
        ), row=1, col=1)

    # Threshold lines
    fig.add_hline(y=mean_rate, line_dash='dash', line_color=COLOR_PRIMARY,
                  annotation_text=f'Mean ({mean_rate:.1f}/hr)', row=1, col=1)
    fig.add_hline(y=upper_thresh, line_dash='dot', line_color=COLOR_SPIKE,
                  annotation_text=f'+{sigma}\u03c3', row=1, col=1)
    if lower_thresh > 0:
        fig.add_hline(y=lower_thresh, line_dash='dot', line_color=COLOR_QUIET,
                      annotation_text=f'-{sigma}\u03c3', row=1, col=1)

    # Bottom: daily gains
    daily = df.groupby('Date_UTC')['Hits'].agg(['first', 'last'])
    daily['gain'] = daily['last'] - daily['first']
    daily_mean = daily['gain'].mean()
    daily_std = daily['gain'].std()
    daily_upper = daily_mean + sigma * daily_std

    bar_colors = [COLOR_SPIKE if g > daily_upper else COLOR_PRIMARY for g in daily['gain']]
    fig.add_trace(go.Bar(
        x=[str(d) for d in daily.index],
        y=daily['gain'],
        marker_color=bar_colors,
        name='Daily Gain',
        showlegend=False,
        hovertemplate='%{x}<br>Gain: %{y:.0f} hits<extra></extra>',
    ), row=2, col=1)

    fig.add_hline(y=daily_mean, line_dash='dash', line_color='#333333',
                  annotation_text=f'Mean ({daily_mean:.1f}/day)', row=2, col=1)
    fig.add_hline(y=daily_upper, line_dash='dot', line_color=COLOR_SPIKE,
                  annotation_text=f'+{sigma}\u03c3', row=2, col=1)

    fig.update_layout(
        plot_bgcolor='white', paper_bgcolor='white',
        font=dict(family='sans-serif', color='#333333'),
        height=700,
        margin=dict(l=60, r=30, t=50, b=60),
    )

    # Thin out x-axis labels on bottom chart
    n_days = len(daily)
    step = max(1, n_days // 15)
    tickvals = list(range(0, n_days, step))
    ticktext = [str(daily.index[i]) for i in tickvals]
    fig.update_xaxes(tickvals=tickvals, ticktext=ticktext, tickangle=45, row=2, col=1)

    return fig


def fig_milestone_forecast(df):
    """Project when future milestones will be reached."""
    df_clean = df.dropna(subset=['Hits']).copy()
    if df_clean.empty:
        return None

    current_hits = df_clean['Hits'].iloc[-1]
    current_time = df_clean['Time_UTC'].iloc[-1]
    start_time = df_clean['Time_UTC'].iloc[0]

    x_numeric = (df_clean['Time_UTC'] - start_time).dt.total_seconds().values
    y = df_clean['Hits'].values
    coeffs = np.polyfit(x_numeric, y, 1)
    slope_per_sec = coeffs[0]
    intercept = coeffs[1]

    # Recent 30-day trend
    cutoff_30 = current_time - pd.Timedelta(days=30)
    df_recent = df_clean[df_clean['Time_UTC'] >= cutoff_30]
    if len(df_recent) > 10:
        x_recent = (df_recent['Time_UTC'] - start_time).dt.total_seconds().values
        y_recent = df_recent['Hits'].values
        coeffs_recent = np.polyfit(x_recent, y_recent, 1)
        slope_recent = coeffs_recent[0]
    else:
        coeffs_recent = coeffs
        slope_recent = slope_per_sec

    # Future projection (2x current span)
    total_span_sec = x_numeric[-1]
    future_span = total_span_sec * 2
    future_x = np.linspace(0, total_span_sec + future_span, 500)
    future_times = [start_time + pd.Timedelta(seconds=float(s)) for s in future_x]

    y_linear = slope_per_sec * future_x + intercept
    y_recent_trend = slope_recent * future_x + coeffs_recent[1]

    # Milestones
    step = 500
    next_milestone = int(np.ceil(current_hits / step) * step)
    milestones = [next_milestone + i * step for i in range(5)]
    milestones = [m for m in milestones if m > current_hits][:5]

    fig = go.Figure()

    # Actual data
    fig.add_trace(go.Scatter(
        x=df_clean['Time_UTC'], y=df_clean['Hits'],
        mode='lines', line=dict(color=COLOR_PRIMARY, width=2),
        name='Actual',
        hovertemplate='%{x|%Y-%m-%d %H:%M UTC}<br>Hits: %{y:,}<extra></extra>',
    ))

    # Trend lines
    fig.add_trace(go.Scatter(
        x=future_times, y=y_linear,
        mode='lines', line=dict(color=COLOR_PRIMARY, width=1.5, dash='dash'),
        opacity=0.5,
        name=f'Overall trend ({slope_per_sec * 86400:.1f}/day)',
    ))
    fig.add_trace(go.Scatter(
        x=future_times, y=y_recent_trend,
        mode='lines', line=dict(color=COLOR_SECONDARY, width=1.5, dash='dash'),
        opacity=0.5,
        name=f'Recent 30-day trend ({slope_recent * 86400:.1f}/day)',
    ))

    # Milestone lines
    for milestone in milestones:
        fig.add_hline(y=milestone, line_dash='dot', line_color='#999999', opacity=0.5,
                      annotation_text=f'{milestone:,}')

    fig.update_layout(**make_chart_layout(
        'Milestone Forecast',
        xaxis_title='Date (UTC)',
        yaxis_title='Hits',
    ))
    fig.update_yaxes(separatethousands=True)
    return fig


def generate_summary_html(df):
    """Generate an HTML summary stats card."""
    total_records = len(df)
    date_min = df['Time_UTC'].min().strftime('%Y-%m-%d')
    date_max = df['Time_UTC'].max().strftime('%Y-%m-%d')
    duration = df['Time_UTC'].max() - df['Time_UTC'].min()
    days = duration.days

    start_val = df['Hits'].iloc[0]
    end_val = df['Hits'].iloc[-1]
    total_increase = end_val - start_val

    df_rate = df.dropna(subset=['Rate_Per_Hour'])
    mean_rate = df_rate['Rate_Per_Hour'].mean() if not df_rate.empty else 0
    median_rate = df_rate['Rate_Per_Hour'].median() if not df_rate.empty else 0

    return f"""
    <div class="summary-grid">
        <div class="stat-card">
            <div class="stat-value">{end_val:,}</div>
            <div class="stat-label">Current Hits</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">+{total_increase:,}</div>
            <div class="stat-label">Total Increase</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{mean_rate:.2f}</div>
            <div class="stat-label">Avg Hits/Hour</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{total_records:,}</div>
            <div class="stat-label">Data Points</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{days}</div>
            <div class="stat-label">Days Tracked</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{date_min} &mdash; {date_max}</div>
            <div class="stat-label">Date Range (UTC)</div>
        </div>
    </div>
    """


def _serialize_raw_data(df):
    """Serialize raw timestamps and hits as a JSON array of [unix_ms, hits]."""
    clean = df.dropna(subset=['Time_UTC', 'Hits'])
    # Use Python's datetime.timestamp() to avoid pandas dtype-unit ambiguity
    # (datetime64 can be [s], [ms], [us], or [ns] depending on pandas version).
    points = [
        [int(t.timestamp() * 1000), int(h)]
        for t, h in zip(clean['Time_UTC'], clean['Hits'])
    ]
    return json.dumps(points)


# Chart IDs (must match the JS CHART_DEFS below).
_CHART_IDS = [
    'chart-raw', 'chart-raw-log', 'chart-recent', 'chart-hourly-rate',
    'chart-activity-heatmap', 'chart-dow-heatmap', 'chart-contribution',
    'chart-polar', 'chart-anomaly', 'chart-milestone',
]


_CHART_JS = r"""
(function() {
  const RAW = __RAW_DATA__;
  let useLocal = false;

  const dayNames = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
  const monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

  function pad2(n) { return String(n).padStart(2, '0'); }
  function getHour(d) { return useLocal ? d.getHours() : d.getUTCHours(); }
  function getDow(d)  { return useLocal ? d.getDay()   : d.getUTCDay(); }
  function getDayName(d) { return dayNames[getDow(d)]; }
  function getYear(d) { return useLocal ? d.getFullYear() : d.getUTCFullYear(); }
  function getMon(d)  { return useLocal ? d.getMonth()    : d.getUTCMonth(); }
  function getDay(d)  { return useLocal ? d.getDate()     : d.getUTCDate(); }
  function getMin(d)  { return useLocal ? d.getMinutes()  : d.getUTCMinutes(); }
  function getSec(d)  { return useLocal ? d.getSeconds()  : d.getUTCSeconds(); }
  function dateKey(d) { return getYear(d) + '-' + pad2(getMon(d)+1) + '-' + pad2(getDay(d)); }
  function plotlyDateStr(d) {
    return getYear(d) + '-' + pad2(getMon(d)+1) + '-' + pad2(getDay(d)) + ' ' +
           pad2(getHour(d)) + ':' + pad2(getMin(d)) + ':' + pad2(getSec(d));
  }
  function tzLabel() { return useLocal ? 'Local' : 'UTC'; }

  const C = {
    primary:   '#3b82f6',
    secondary: '#10b981',
    spike:     '#ef4444',
    quiet:     '#6366f1',
    heat:      'YlGnBu'
  };

  const PLOTLY_THEMES = {
    light: {
      bg: 'white', paper: 'white',
      text: '#333333', muted: '#666666',
      grid: '#eeeeee', line: '#cccccc',
      neutralLine: '#999999'
    },
    dark: {
      bg: '#1a1a2e', paper: '#1a1a2e',
      text: '#e8e8e8', muted: '#a8a8b8',
      grid: '#2e2e44', line: '#404058',
      neutralLine: '#888899'
    }
  };
  let currentTheme = 'dark';
  function T() { return PLOTLY_THEMES[currentTheme]; }

  function baseLayout(title, xtitle, ytitle) {
    const t = T();
    return {
      title: { text: title, font: { size: 16, color: t.text }, x: 0.5, xanchor: 'center' },
      plot_bgcolor: t.bg, paper_bgcolor: t.paper,
      font: { family: 'sans-serif', color: t.text },
      xaxis: { title: { text: xtitle, standoff: 15 }, gridcolor: t.grid, linecolor: t.line, automargin: true, ticks: '', showline: false, zeroline: false },
      yaxis: { title: { text: ytitle, standoff: 15 }, gridcolor: t.grid, linecolor: t.line, automargin: true, ticks: '', showline: false, zeroline: false },
      margin: { l: 70, r: 30, t: 60, b: 70 },
      height: 450
    };
  }

  function preprocess() {
    const n = RAW.length;
    const dates = new Array(n);
    const hits = new Array(n);
    const valueChange = new Array(n);
    const rates = new Array(n);
    for (let i = 0; i < n; i++) {
      dates[i] = new Date(RAW[i][0]);
      hits[i] = RAW[i][1];
      if (i === 0) { valueChange[i] = null; rates[i] = null; }
      else {
        const dh = hits[i] - hits[i - 1];
        const dt = (RAW[i][0] - RAW[i - 1][0]) / 3600000;
        valueChange[i] = dh;
        rates[i] = dt > 0 ? dh / dt : null;
      }
    }
    return { dates, hits, valueChange, rates, n };
  }

  function mean(arr) {
    let s = 0, c = 0;
    for (const v of arr) if (v != null && !isNaN(v)) { s += v; c++; }
    return c ? s / c : 0;
  }
  function std(arr) {
    const m = mean(arr);
    let s = 0, c = 0;
    for (const v of arr) if (v != null && !isNaN(v)) { s += (v - m) * (v - m); c++; }
    return c ? Math.sqrt(s / c) : 0;
  }
  function quantile(arr, q) {
    const sorted = arr.filter(v => v != null && !isNaN(v)).slice().sort((a, b) => a - b);
    if (!sorted.length) return 0;
    const pos = (sorted.length - 1) * q;
    const base = Math.floor(pos);
    const rest = pos - base;
    const next = sorted[base + 1] != null ? sorted[base + 1] : sorted[base];
    return sorted[base] + rest * (next - sorted[base]);
  }

  function chartRaw(d) {
    const x = d.dates.map(plotlyDateStr);
    const yMin = Math.min.apply(null, d.hits);
    const yMax = Math.max.apply(null, d.hits);
    const pad = (yMax - yMin) * 0.05;
    const layout = baseLayout('QRZ Profile Hits Over Time', 'Date/Time (' + tzLabel() + ')', 'Hits');
    layout.yaxis.range = [yMin - pad, yMax + pad];
    layout.yaxis.separatethousands = true;
    return {
      data: [{
        x: x, y: d.hits, mode: 'lines',
        line: { color: C.primary, width: 2 },
        fill: 'tozeroy', fillcolor: 'rgba(59,130,246,0.08)',
        name: 'Hits',
        hovertemplate: '%{x|%Y-%m-%d %H:%M} ' + tzLabel() + '<br>Hits: %{y:,}<extra></extra>'
      }],
      layout: layout
    };
  }

  function chartRawLog(d) {
    const x = d.dates.map(plotlyDateStr);
    const layout = baseLayout('QRZ Profile Hits (Log Scale)', 'Date/Time (' + tzLabel() + ')', 'Hits (Log Scale)');
    layout.yaxis.type = 'log';
    return {
      data: [{
        x: x, y: d.hits, mode: 'lines',
        line: { color: C.primary, width: 2 },
        name: 'Hits',
        hovertemplate: '%{x|%Y-%m-%d %H:%M} ' + tzLabel() + '<br>Hits: %{y:,}<extra></extra>'
      }],
      layout: layout
    };
  }

  function chartRecent(d) {
    const days = 30;
    const cutoff = d.dates[d.n - 1].getTime() - days * 86400000;
    const xs = [], ys = [];
    for (let i = 0; i < d.n; i++) {
      if (d.dates[i].getTime() >= cutoff) {
        xs.push(plotlyDateStr(d.dates[i]));
        ys.push(d.hits[i]);
      }
    }
    if (!ys.length) return null;
    const yMin = Math.min.apply(null, ys);
    const yMax = Math.max.apply(null, ys);
    const pad = (yMax - yMin) * 0.05;
    const layout = baseLayout('Hits, Last ' + days + ' Days', 'Date/Time (' + tzLabel() + ')', 'Hits');
    layout.yaxis.range = [yMin - pad, yMax + pad];
    layout.yaxis.separatethousands = true;
    return {
      data: [{
        x: xs, y: ys, mode: 'lines',
        line: { color: C.primary, width: 2 },
        fill: 'tozeroy', fillcolor: 'rgba(59,130,246,0.08)',
        name: 'Hits',
        hovertemplate: '%{x|%Y-%m-%d %H:%M} ' + tzLabel() + '<br>Hits: %{y:,}<extra></extra>'
      }],
      layout: layout
    };
  }

  function chartHourlyRate(d) {
    const sums = new Array(24).fill(0);
    const counts = new Array(24).fill(0);
    for (let i = 1; i < d.n; i++) {
      if (d.rates[i] != null && !isNaN(d.rates[i])) {
        const h = getHour(d.dates[i]);
        sums[h] += d.rates[i];
        counts[h]++;
      }
    }
    const avgs = sums.map(function (s, i) { return counts[i] ? s / counts[i] : 0; });
    const layout = baseLayout(
      'Average Hourly Rate of Change (' + tzLabel() + ')',
      'Hour of Day (' + tzLabel() + ')',
      'Mean Rate (hits/hour)'
    );
    layout.xaxis.dtick = 1;
    return {
      data: [{
        x: Array.from({ length: 24 }, function (_, i) { return i; }),
        y: avgs,
        type: 'bar',
        marker: { color: C.primary },
        hovertemplate: 'Hour %{x}:00 ' + tzLabel() + '<br>Avg rate: %{y:.2f}/hr<extra></extra>'
      }],
      layout: layout
    };
  }

  function chartActivityHeatmap(d) {
    const dateSet = new Set();
    for (let i = 0; i < d.n; i++) dateSet.add(dateKey(d.dates[i]));
    if (dateSet.size <= 7) return null;
    const dates = Array.from(dateSet).sort();
    const dateIdx = new Map(dates.map(function (k, i) { return [k, i]; }));
    const z = Array.from({ length: 24 }, function () { return new Array(dates.length).fill(null); });
    for (let i = 1; i < d.n; i++) {
      if (d.valueChange[i] != null) {
        const h = getHour(d.dates[i]);
        const ci = dateIdx.get(dateKey(d.dates[i]));
        if (z[h][ci] == null) z[h][ci] = 0;
        z[h][ci] += d.valueChange[i];
      }
    }
    const step = Math.max(1, Math.floor(dates.length / 15));
    const tickvals = [], ticktext = [];
    for (let i = 0; i < dates.length; i += step) { tickvals.push(i); ticktext.push(dates[i]); }
    const customdata = Array.from({ length: 24 }, function () { return dates.slice(); });
    const layout = baseLayout('Daily Activity Heatmap (' + tzLabel() + ')', 'Date', 'Hour of Day (' + tzLabel() + ')');
    layout.xaxis.tickvals = tickvals;
    layout.xaxis.ticktext = ticktext;
    layout.xaxis.tickangle = 45;
    layout.yaxis.dtick = 1;
    return {
      data: [{
        type: 'heatmap',
        z: z,
        x: Array.from({ length: dates.length }, function (_, i) { return i; }),
        y: Array.from({ length: 24 }, function (_, i) { return i; }),
        colorscale: C.heat, reversescale: true,
        colorbar: { title: { text: 'Value Change' } },
        customdata: customdata,
        hovertemplate: 'Date: %{customdata}<br>Hour: %{y}:00 ' + tzLabel() + '<br>Change: %{z:.1f}<extra></extra>'
      }],
      layout: layout
    };
  }

  function chartDowHeatmap(d) {
    const dayOrder = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
    const sums = {}, counts = {};
    for (const day of dayOrder) {
      sums[day] = new Array(24).fill(0);
      counts[day] = new Array(24).fill(0);
    }
    for (let i = 1; i < d.n; i++) {
      if (d.rates[i] != null && !isNaN(d.rates[i])) {
        const dn = getDayName(d.dates[i]);
        const h = getHour(d.dates[i]);
        sums[dn][h] += d.rates[i];
        counts[dn][h]++;
      }
    }
    const z = dayOrder.map(function (day) {
      return sums[day].map(function (s, i) { return counts[day][i] ? s / counts[day][i] : 0; });
    });
    const layout = baseLayout(
      'Average Activity by Day of Week (' + tzLabel() + ')',
      'Hour of Day (' + tzLabel() + ')',
      'Day of Week'
    );
    return {
      data: [{
        type: 'heatmap',
        z: z,
        x: Array.from({ length: 24 }, function (_, i) { return pad2(i) + ':00'; }),
        y: dayOrder,
        colorscale: C.heat, reversescale: true,
        colorbar: { title: { text: 'Avg Rate/Hr' } },
        hovertemplate: '%{y} %{x} ' + tzLabel() + '<br>Avg rate: %{z:.2f}/hr<extra></extra>'
      }],
      layout: layout
    };
  }

  function chartContributionCalendar(d) {
    const dateMap = new Map();
    for (let i = 0; i < d.n; i++) {
      const k = dateKey(d.dates[i]);
      if (!dateMap.has(k)) dateMap.set(k, { first: d.hits[i], last: d.hits[i] });
      else dateMap.get(k).last = d.hits[i];
    }
    const sortedKeys = Array.from(dateMap.keys()).sort();
    if (!sortedKeys.length) return null;

    function parseKey(k) {
      const p = k.split('-').map(Number);
      return { y: p[0], m: p[1] - 1, d: p[2] };
    }
    function dowFromKey(k) {
      const p = parseKey(k);
      return new Date(Date.UTC(p.y, p.m, p.d)).getUTCDay();
    }
    function nextKey(k) {
      const p = parseKey(k);
      const t = new Date(Date.UTC(p.y, p.m, p.d) + 86400000);
      return t.getUTCFullYear() + '-' + pad2(t.getUTCMonth() + 1) + '-' + pad2(t.getUTCDate());
    }

    const allDates = [];
    const allGains = [];
    let cur = sortedKeys[0];
    const last = sortedKeys[sortedKeys.length - 1];
    while (true) {
      allDates.push(cur);
      const v = dateMap.get(cur);
      allGains.push(v ? v.last - v.first : 0);
      if (cur === last) break;
      cur = nextKey(cur);
    }

    const firstDow = dowFromKey(allDates[0]);
    const weeks = [], days = [], texts = [], colors = [];
    for (let i = 0; i < allDates.length; i++) {
      const dow = dowFromKey(allDates[i]);
      const week = Math.floor((i + firstDow) / 7);
      weeks.push(week);
      days.push(dow);
      texts.push(allDates[i] + ': +' + allGains[i].toFixed(0) + ' hits');
      colors.push(Math.max(allGains[i], 0));
    }
    const vmax = Math.max(quantile(allGains, 0.95), 1);

    const monthLabelsX = [], monthLabelsText = [];
    const seen = new Set();
    for (let i = 0; i < allDates.length; i++) {
      const p = parseKey(allDates[i]);
      const key = p.y + '-' + p.m;
      if (!seen.has(key) && p.d <= 7) {
        seen.add(key);
        monthLabelsX.push(Math.floor((i + firstDow) / 7));
        monthLabelsText.push(monthNames[p.m]);
      }
    }

    return {
      data: [{
        type: 'heatmap',
        x: weeks, y: days, z: colors,
        colorscale: 'Greens', reversescale: true,
        zmin: 0, zmax: vmax,
        text: texts, hoverinfo: 'text',
        showscale: true,
        colorbar: { title: { text: 'Daily Gain' } },
        xgap: 2, ygap: 2
      }],
      layout: {
        title: { text: 'Daily Hit Gains: Contribution Calendar (' + tzLabel() + ')', font: { size: 16, color: T().text }, x: 0.5, xanchor: 'center' },
        plot_bgcolor: T().bg, paper_bgcolor: T().paper,
        font: { family: 'sans-serif', color: T().text },
        yaxis: {
          tickvals: [0, 1, 2, 3, 4, 5, 6],
          ticktext: ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'],
          autorange: 'reversed',
          automargin: true,
          ticks: '', showline: false, zeroline: false, showgrid: false
        },
        xaxis: {
          tickvals: monthLabelsX,
          ticktext: monthLabelsText,
          side: 'top',
          automargin: true,
          ticks: '', showline: false, zeroline: false, showgrid: false
        },
        margin: { l: 60, r: 30, t: 80, b: 30 },
        height: 280
      }
    };
  }

  function chartPolarClock(d) {
    const sums = new Array(24).fill(0);
    const counts = new Array(24).fill(0);
    for (let i = 1; i < d.n; i++) {
      if (d.rates[i] != null && !isNaN(d.rates[i])) {
        const h = getHour(d.dates[i]);
        sums[h] += d.rates[i];
        counts[h]++;
      }
    }
    const avgs = sums.map(function (s, i) { return counts[i] ? s / counts[i] : 0; });
    const theta = Array.from({ length: 24 }, function (_, i) { return pad2(i) + ':00'; }).concat(['00:00']);
    const r = avgs.concat([avgs[0]]);
    return {
      data: [{
        type: 'scatterpolar',
        r: r, theta: theta,
        fill: 'toself',
        fillcolor: 'rgba(59,130,246,0.15)',
        line: { color: C.primary, width: 2 },
        name: 'Avg Rate/Hr',
        hovertemplate: '%{theta} ' + tzLabel() + '<br>Avg rate: %{r:.2f}/hr<extra></extra>'
      }],
      layout: {
        title: { text: 'Hourly Activity Profile (' + tzLabel() + ')', font: { size: 16, color: T().text }, x: 0.5, xanchor: 'center' },
        font: { family: 'sans-serif', color: T().text },
        polar: {
          bgcolor: T().bg,
          radialaxis: { visible: true, gridcolor: T().grid, linecolor: T().line, color: T().text },
          angularaxis: { direction: 'clockwise', rotation: 90, gridcolor: T().grid, linecolor: T().line, color: T().text }
        },
        paper_bgcolor: T().paper,
        margin: { l: 60, r: 60, t: 60, b: 40 },
        height: 500
      }
    };
  }

  function chartAnomaly(d) {
    const sigma = 2;
    const validIdx = [];
    const validRates = [];
    for (let i = 1; i < d.n; i++) {
      if (d.rates[i] != null && !isNaN(d.rates[i])) {
        validIdx.push(i);
        validRates.push(d.rates[i]);
      }
    }
    if (!validRates.length) return null;
    const mr = mean(validRates);
    const sr = std(validRates);
    const upper = mr + sigma * sr;
    const lower = Math.max(mr - sigma * sr, 0);

    const lineX = [], lineY = [], spikeX = [], spikeY = [], quietX = [], quietY = [];
    for (const i of validIdx) {
      const xs = plotlyDateStr(d.dates[i]);
      lineX.push(xs); lineY.push(d.rates[i]);
      if (d.rates[i] > upper)      { spikeX.push(xs); spikeY.push(d.rates[i]); }
      else if (d.rates[i] <= lower) { quietX.push(xs); quietY.push(d.rates[i]); }
    }

    const dateMap = new Map();
    for (let i = 0; i < d.n; i++) {
      const k = dateKey(d.dates[i]);
      if (!dateMap.has(k)) dateMap.set(k, { first: d.hits[i], last: d.hits[i] });
      else dateMap.get(k).last = d.hits[i];
    }
    const sortedDates = Array.from(dateMap.keys()).sort();
    const gains = sortedDates.map(function (k) { const v = dateMap.get(k); return v.last - v.first; });
    const dailyMean = mean(gains);
    const dailyStd = std(gains);
    const dailyUpper = dailyMean + sigma * dailyStd;
    const barColors = gains.map(function (g) { return g > dailyUpper ? C.spike : C.primary; });

    const traces = [{
      x: lineX, y: lineY, mode: 'lines',
      line: { color: T().neutralLine, width: 1 }, opacity: 0.6,
      name: 'Rate', showlegend: false,
      hovertemplate: '%{x|%Y-%m-%d %H:%M} ' + tzLabel() + '<br>Rate: %{y:.2f}/hr<extra></extra>',
      xaxis: 'x', yaxis: 'y'
    }];
    if (spikeX.length) traces.push({
      x: spikeX, y: spikeY, mode: 'markers',
      marker: { color: C.spike, size: 6 },
      name: 'Spike (>' + sigma + 'σ)',
      hovertemplate: '%{x|%Y-%m-%d %H:%M} ' + tzLabel() + '<br>Rate: %{y:.2f}/hr<extra></extra>',
      xaxis: 'x', yaxis: 'y'
    });
    if (quietX.length) traces.push({
      x: quietX, y: quietY, mode: 'markers',
      marker: { color: C.quiet, size: 5, symbol: 'triangle-down' },
      name: 'Quiet (≤' + sigma + 'σ below)',
      hovertemplate: '%{x|%Y-%m-%d %H:%M} ' + tzLabel() + '<br>Rate: %{y:.2f}/hr<extra></extra>',
      xaxis: 'x', yaxis: 'y'
    });
    traces.push({
      x: sortedDates, y: gains, type: 'bar',
      marker: { color: barColors },
      name: 'Daily Gain', showlegend: false,
      hovertemplate: '%{x}<br>Gain: %{y:.0f} hits<extra></extra>',
      xaxis: 'x2', yaxis: 'y2'
    });

    const nDays = sortedDates.length;
    const stepD = Math.max(1, Math.floor(nDays / 15));
    const tickvalsD = [], ticktextD = [];
    for (let i = 0; i < nDays; i += stepD) { tickvalsD.push(sortedDates[i]); ticktextD.push(sortedDates[i]); }

    const annotations = [
      { text: 'Anomaly Detection: Rate of Change (' + tzLabel() + ')',
        showarrow: false, x: 0.5, y: 1.0, xref: 'paper', yref: 'paper',
        xanchor: 'center', yanchor: 'bottom', font: { size: 14 } },
      { text: 'Daily Gains with Spike Days Highlighted',
        showarrow: false, x: 0.5, y: 0.45, xref: 'paper', yref: 'paper',
        xanchor: 'center', yanchor: 'bottom', font: { size: 14 } },
      // Top subplot line labels (outside plot, to the right)
      { text: 'Mean (' + mr.toFixed(1) + '/hr)', showarrow: false,
        xref: 'x domain', yref: 'y', x: 1.01, y: mr,
        xanchor: 'left', yanchor: 'middle',
        font: { size: 10, color: C.primary } },
      { text: '+' + sigma + 'σ (' + upper.toFixed(1) + ')', showarrow: false,
        xref: 'x domain', yref: 'y', x: 1.01, y: upper,
        xanchor: 'left', yanchor: 'middle',
        font: { size: 10, color: C.spike } }
    ];
    if (lower > 0) {
      annotations.push({
        text: '-' + sigma + 'σ (' + lower.toFixed(1) + ')', showarrow: false,
        xref: 'x domain', yref: 'y', x: 1.01, y: lower,
        xanchor: 'left', yanchor: 'middle',
        font: { size: 10, color: C.quiet }
      });
    }
    // Bottom subplot line labels
    annotations.push(
      { text: 'Mean (' + dailyMean.toFixed(1) + '/day)', showarrow: false,
        xref: 'x2 domain', yref: 'y2', x: 1.01, y: dailyMean,
        xanchor: 'left', yanchor: 'middle',
        font: { size: 10, color: T().text } },
      { text: '+' + sigma + 'σ (' + dailyUpper.toFixed(1) + ')', showarrow: false,
        xref: 'x2 domain', yref: 'y2', x: 1.01, y: dailyUpper,
        xanchor: 'left', yanchor: 'middle',
        font: { size: 10, color: C.spike } }
    );

    return {
      data: traces,
      layout: {
        plot_bgcolor: T().bg, paper_bgcolor: T().paper,
        font: { family: 'sans-serif', color: T().text },
        height: 700,
        margin: { l: 70, r: 140, t: 60, b: 80 },
        showlegend: true,
        legend: { x: 1.01, y: 1, xanchor: 'left', yanchor: 'top', font: { color: T().text } },
        annotations: annotations,
        xaxis:  { gridcolor: T().grid, linecolor: T().line, domain: [0, 1], anchor: 'y', automargin: true, ticks: '', showline: false, zeroline: false },
        yaxis:  { gridcolor: T().grid, linecolor: T().line, domain: [0.55, 0.95], anchor: 'x', title: { text: 'Rate (hits/hr)', standoff: 15 }, automargin: true, ticks: '', showline: false, zeroline: false },
        xaxis2: { gridcolor: T().grid, linecolor: T().line, domain: [0, 1], anchor: 'y2',
                  tickvals: tickvalsD, ticktext: ticktextD, tickangle: 45, type: 'category', automargin: true, ticks: '', showline: false, zeroline: false },
        yaxis2: { gridcolor: T().grid, linecolor: T().line, domain: [0, 0.4], anchor: 'x2', title: { text: 'Daily Gain', standoff: 15 }, automargin: true, ticks: '', showline: false, zeroline: false },
        shapes: [
          { type: 'line', xref: 'x domain',  yref: 'y',  x0: 0, x1: 1, y0: mr,         y1: mr,         line: { color: C.primary, dash: 'dash' } },
          { type: 'line', xref: 'x domain',  yref: 'y',  x0: 0, x1: 1, y0: upper,      y1: upper,      line: { color: C.spike,   dash: 'dot' } },
          (lower > 0 ? { type: 'line', xref: 'x domain', yref: 'y', x0: 0, x1: 1, y0: lower, y1: lower, line: { color: C.quiet, dash: 'dot' } } : null),
          { type: 'line', xref: 'x2 domain', yref: 'y2', x0: 0, x1: 1, y0: dailyMean,  y1: dailyMean,  line: { color: T().text, dash: 'dash' } },
          { type: 'line', xref: 'x2 domain', yref: 'y2', x0: 0, x1: 1, y0: dailyUpper, y1: dailyUpper, line: { color: C.spike,   dash: 'dot' } }
        ].filter(Boolean)
      }
    };
  }

  function chartMilestone(d) {
    const cleanIdx = [];
    for (let i = 0; i < d.n; i++) if (d.hits[i] != null && !isNaN(d.hits[i])) cleanIdx.push(i);
    if (!cleanIdx.length) return null;
    const startMs = d.dates[cleanIdx[0]].getTime();
    const lastMs = d.dates[cleanIdx[cleanIdx.length - 1]].getTime();
    const currentHits = d.hits[cleanIdx[cleanIdx.length - 1]];

    function linreg(idxs) {
      let sx = 0, sy = 0, sxx = 0, sxy = 0, n = 0;
      for (const i of idxs) {
        const x = (d.dates[i].getTime() - startMs) / 1000;
        const y = d.hits[i];
        sx += x; sy += y; sxx += x * x; sxy += x * y; n++;
      }
      const denom = n * sxx - sx * sx;
      if (denom === 0) return [0, sy / n];
      const slope = (n * sxy - sx * sy) / denom;
      const intercept = (sy - slope * sx) / n;
      return [slope, intercept];
    }

    const overall = linreg(cleanIdx);
    const slope = overall[0], intercept = overall[1];

    const cutoff30 = lastMs - 30 * 86400000;
    const recentIdx = cleanIdx.filter(function (i) { return d.dates[i].getTime() >= cutoff30; });
    let slopeR, interceptR;
    if (recentIdx.length > 10) {
      const r = linreg(recentIdx);
      slopeR = r[0]; interceptR = r[1];
    } else { slopeR = slope; interceptR = intercept; }

    const totalSpan = (lastMs - startMs) / 1000;
    const futureSpan = totalSpan * 2;
    const futureTimes = [], yLinear = [], yRecent = [];
    for (let i = 0; i < 500; i++) {
      const x = (totalSpan + futureSpan) * i / 499;
      futureTimes.push(plotlyDateStr(new Date(startMs + x * 1000)));
      yLinear.push(slope * x + intercept);
      yRecent.push(slopeR * x + interceptR);
    }

    const stepM = 500;
    const next = Math.ceil(currentHits / stepM) * stepM;
    const milestones = [];
    for (let i = 0; i < 5; i++) {
      const m = next + i * stepM;
      if (m > currentHits) milestones.push(m);
    }

    const traces = [
      {
        x: cleanIdx.map(function (i) { return plotlyDateStr(d.dates[i]); }),
        y: cleanIdx.map(function (i) { return d.hits[i]; }),
        mode: 'lines', line: { color: C.primary, width: 2 }, name: 'Actual',
        hovertemplate: '%{x|%Y-%m-%d %H:%M} ' + tzLabel() + '<br>Hits: %{y:,}<extra></extra>'
      },
      {
        x: futureTimes, y: yLinear, mode: 'lines',
        line: { color: C.primary, width: 1.5, dash: 'dash' }, opacity: 0.5,
        name: 'Overall trend (' + (slope * 86400).toFixed(1) + '/day)'
      },
      {
        x: futureTimes, y: yRecent, mode: 'lines',
        line: { color: C.secondary, width: 1.5, dash: 'dash' }, opacity: 0.5,
        name: 'Recent 30-day trend (' + (slopeR * 86400).toFixed(1) + '/day)'
      }
    ];

    const layout = baseLayout('Milestone Forecast', 'Date (' + tzLabel() + ')', 'Hits');
    layout.yaxis.separatethousands = true;
    layout.shapes = milestones.map(function (m) {
      return {
        type: 'line', xref: 'x domain', yref: 'y',
        x0: 0, x1: 1, y0: m, y1: m,
        line: { color: T().neutralLine, dash: 'dot' }, opacity: 0.5
      };
    });
    layout.annotations = milestones.map(function (m) {
      return {
        x: 1, y: m, xref: 'x domain', yref: 'y',
        xanchor: 'right', yanchor: 'bottom',
        text: m.toLocaleString(), showarrow: false, font: { color: T().muted }
      };
    });
    return { data: traces, layout: layout };
  }

  const CHART_DEFS = [
    { id: 'chart-raw',                fn: chartRaw },
    { id: 'chart-raw-log',            fn: chartRawLog },
    { id: 'chart-recent',             fn: chartRecent },
    { id: 'chart-hourly-rate',        fn: chartHourlyRate },
    { id: 'chart-activity-heatmap',   fn: chartActivityHeatmap },
    { id: 'chart-dow-heatmap',        fn: chartDowHeatmap },
    { id: 'chart-contribution',       fn: chartContributionCalendar },
    { id: 'chart-polar',              fn: chartPolarClock },
    { id: 'chart-anomaly',            fn: chartAnomaly },
    { id: 'chart-milestone',          fn: chartMilestone }
  ];

  function rebuildAll() {
    const d = preprocess();
    for (const def of CHART_DEFS) {
      const el = document.getElementById(def.id);
      if (!el) continue;
      const fig = def.fn(d);
      const wrapper = el.parentElement;
      if (!fig) {
        if (wrapper) wrapper.style.display = 'none';
        continue;
      }
      if (wrapper) wrapper.style.display = '';
      Plotly.react(def.id, fig.data, fig.layout, { responsive: true });
    }
  }

  function updateToggleUI() {
    const btn = document.getElementById('tz-toggle');
    btn.textContent = useLocal ? 'Showing: Local Time (click for UTC)' : 'Showing: UTC (click for Local)';
    let tz = '';
    try { tz = Intl.DateTimeFormat().resolvedOptions().timeZone; } catch (e) {}
    const info = document.getElementById('tz-info');
    if (useLocal) info.textContent = tz ? ('Local timezone: ' + tz) : 'Local browser time';
    else info.textContent = tz ? ('UTC times shown, your timezone: ' + tz) : 'UTC times shown';
  }

  function detectInitialTheme() {
    try {
      const saved = localStorage.getItem('qrz-theme');
      if (saved === 'light' || saved === 'dark') return saved;
    } catch (e) {}
    if (window.matchMedia) {
      if (window.matchMedia('(prefers-color-scheme: light)').matches) return 'light';
      if (window.matchMedia('(prefers-color-scheme: dark)').matches) return 'dark';
    }
    return 'dark';
  }

  function applyTheme(theme) {
    currentTheme = theme;
    document.documentElement.setAttribute('data-theme', theme);
    const btn = document.getElementById('theme-toggle');
    if (btn) btn.textContent = theme === 'dark' ? 'Theme: Dark' : 'Theme: Light';
  }

  function init() {
    applyTheme(detectInitialTheme());

    document.getElementById('tz-toggle').addEventListener('click', function () {
      useLocal = !useLocal;
      updateToggleUI();
      rebuildAll();
    });

    document.getElementById('theme-toggle').addEventListener('click', function () {
      const next = currentTheme === 'dark' ? 'light' : 'dark';
      applyTheme(next);
      try { localStorage.setItem('qrz-theme', next); } catch (e) {}
      rebuildAll();
    });

    updateToggleUI();
    rebuildAll();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
"""


def build_html(summary_html, callsign, df):
    """Combine all charts into a single self-contained HTML page with a UTC/Local toggle."""
    raw_data_js = _serialize_raw_data(df)
    chart_js = _CHART_JS.replace('__RAW_DATA__', raw_data_js)

    chart_divs = '\n    '.join(
        f'<div class="chart-container"><div id="{cid}"></div></div>'
        for cid in _CHART_IDS
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{callsign} QRZ Lookup Stats</title>
    <script>
    // Set theme before paint to prevent flash-of-wrong-theme.
    (function() {{
        try {{
            var saved = localStorage.getItem('qrz-theme');
            if (saved === 'light' || saved === 'dark') {{
                document.documentElement.setAttribute('data-theme', saved);
                return;
            }}
        }} catch(e) {{}}
        var mm = window.matchMedia;
        if (mm && mm('(prefers-color-scheme: light)').matches) {{
            document.documentElement.setAttribute('data-theme', 'light');
        }} else {{
            document.documentElement.setAttribute('data-theme', 'dark');
        }}
    }})();
    </script>
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
    <style>
        :root {{
            --bg: #f8f9fa;
            --card-bg: #ffffff;
            --text: #333333;
            --heading: #1a1a2e;
            --muted: #666666;
            --muted2: #888888;
            --body-text: #444444;
            --shadow: 0 1px 3px rgba(0,0,0,0.08);
            --info-bg: #e8f4f8;
            --info-color: #1a6b8a;
            --btn-bg: #1a1a2e;
            --btn-bg-hover: #2a2a4e;
            --btn-color: #ffffff;
        }}
        html[data-theme="dark"] {{
            --bg: #0f0f1e;
            --card-bg: #1a1a2e;
            --text: #e8e8e8;
            --heading: #ffffff;
            --muted: #a8a8b8;
            --muted2: #8a8a9a;
            --body-text: #d0d0dc;
            --shadow: 0 1px 3px rgba(0,0,0,0.35);
            --info-bg: #243446;
            --info-color: #8acce0;
            --btn-bg: #3a3a5e;
            --btn-bg-hover: #4a4a6e;
            --btn-color: #f0f0ff;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        html, body {{ background: var(--bg); }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            color: var(--text);
            padding: 20px;
            max-width: 1200px;
            margin: 0 auto;
            transition: background-color 0.15s ease, color 0.15s ease;
        }}
        h1 {{
            font-size: 1.8rem;
            font-weight: 600;
            margin-bottom: 8px;
            color: var(--heading);
        }}
        .subtitle {{
            color: var(--muted);
            margin-bottom: 16px;
            font-size: 0.95rem;
        }}
        .tz-controls {{
            display: flex;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
            margin-bottom: 20px;
        }}
        .tz-toggle, .theme-toggle {{
            background: var(--btn-bg);
            color: var(--btn-color);
            border: none;
            padding: 8px 14px;
            border-radius: 6px;
            font-size: 0.9rem;
            font-weight: 500;
            cursor: pointer;
            font-family: inherit;
        }}
        .tz-toggle:hover, .theme-toggle:hover {{ background: var(--btn-bg-hover); }}
        .tz-info {{
            display: inline-block;
            background: var(--info-bg);
            color: var(--info-color);
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 0.85rem;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 12px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: var(--card-bg);
            border-radius: 8px;
            padding: 16px;
            box-shadow: var(--shadow);
            text-align: center;
        }}
        .stat-value {{
            font-size: 1.4rem;
            font-weight: 700;
            color: var(--heading);
        }}
        .stat-label {{
            font-size: 0.8rem;
            color: var(--muted2);
            margin-top: 4px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .chart-container {{
            background: var(--card-bg);
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 20px;
            box-shadow: var(--shadow);
        }}
        .explainer {{
            background: var(--card-bg);
            border-radius: 8px;
            padding: 20px 24px;
            margin-bottom: 20px;
            box-shadow: var(--shadow);
            font-size: 0.9rem;
            line-height: 1.55;
            color: var(--body-text);
        }}
        .explainer h2 {{
            font-size: 1rem;
            font-weight: 600;
            color: var(--heading);
            margin-bottom: 8px;
        }}
        .explainer p {{ margin-bottom: 8px; }}
        .explainer p:last-child {{ margin-bottom: 0; }}
    </style>
</head>
<body>
    <h1>{callsign} QRZ Lookup Stats</h1>
    <div class="subtitle">Auto-updated hourly.</div>
    <div class="tz-controls">
        <button id="tz-toggle" class="tz-toggle" type="button">Showing: UTC (click for Local)</button>
        <button id="theme-toggle" class="theme-toggle" type="button">Theme: Dark</button>
        <span class="tz-info" id="tz-info">UTC times shown</span>
    </div>

    {summary_html}
    {chart_divs}

    <div class="explainer">
        <h2>A note on DST and the Local time view</h2>
        <p>Toggling to Local time does more than rotate the hour-of-day charts. Each data point is re-binned into the wall-clock hour it actually occurred at, which means samples cross Daylight Saving Time boundaries differently depending on when they were recorded.</p>
        <p>For example, a sample at 11:00&nbsp;UTC in August (EDT, UTC&minus;4) lands in local hour 7, while the same 11:00&nbsp;UTC in December (EST, UTC&minus;5) lands in local hour 6. So the UTC and Local hourly charts are not simple rotations of each other. The sample mix inside each bin changes. This is the intended behavior: it answers the question "what does my activity look like at 7&nbsp;AM <em>my time</em>," consistently across DST transitions.</p>
    </div>

    <script>
{chart_js}
    </script>
</body>
</html>"""


def build_embed_html(fig, title):
    """Build a minimal HTML page for a single chart, suitable for iframe embedding."""
    fig_json = fig.to_json()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ background: transparent; }}
        #chart {{ width: 100%; }}
    </style>
</head>
<body>
    <div id="chart"></div>
    <script>
    (function() {{
        var data = {fig_json};
        data.layout.paper_bgcolor = 'rgba(0,0,0,0)';
        data.layout.plot_bgcolor = 'rgba(0,0,0,0)';
        data.layout.margin = {{l: 40, r: 10, t: 40, b: 10}};
        Plotly.newPlot('chart', data.data, data.layout, {{responsive: true, displayModeBar: false}});
    }})();
    </script>
</body>
</html>"""


def main(csv_filepath, output_dir):
    """Main: load data, generate all charts, write HTML."""
    print("Loading and processing data...")
    df = load_and_process_data(csv_filepath)

    # Derive callsign from CSV filename
    csv_basename = os.path.basename(csv_filepath)
    callsign = csv_basename.replace('_QRZ_stats.csv', '')

    print("Generating summary...")
    summary_html = generate_summary_html(df)

    print("Creating interactive charts...")
    figures = [
        ('Hits Over Time', fig_raw_values(df)),
        ('Hits (Log Scale)', fig_raw_values_log(df)),
        ('Recent Hits', fig_recent_raw_values(df)),
        ('Hourly Rate', fig_hourly_rate(df)),
        ('Activity Heatmap', fig_activity_heatmap(df)),
        ('Day of Week Heatmap', fig_dow_heatmap(df)),
        ('Contribution Calendar', fig_contribution_calendar(df)),
        ('Polar Clock', fig_polar_clock(df)),
        ('Anomaly Detection', fig_anomaly_detection(df)),
        ('Milestone Forecast', fig_milestone_forecast(df)),
    ]

    print("Building HTML page...")
    html = build_html(summary_html, callsign, df)

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'index.html')
    with open(output_path, 'w') as f:
        f.write(html)
    print(f"Saved: {output_path}")

    # Generate standalone embed pages and static PNGs for each chart
    for title, fig in figures:
        if fig is None:
            continue
        slug = title.lower().replace(' ', '_').replace('\u2014', '')

        embed_path = os.path.join(output_dir, f'embed_{slug}.html')
        with open(embed_path, 'w') as f:
            f.write(build_embed_html(fig, title))

        png_path = os.path.join(output_dir, f'{slug}.png')
        fig.write_image(png_path, width=1400, height=600, scale=2)

    print(f"Saved embed pages and PNGs to {output_dir}/")


if __name__ == "__main__":
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

    csv_filename = f"{os.environ.get('QRZ_CALLSIGN', 'N0CALL')}_QRZ_stats.csv"
    csv_file_path = os.path.join(SCRIPT_DIR, csv_filename)

    # Output to _site/ for GitHub Pages deployment
    site_dir = os.path.join(SCRIPT_DIR, '_site')

    try:
        main(csv_file_path, site_dir)
        print(f"\nVisualization complete! Open _site/index.html in your browser.")
    except FileNotFoundError:
        print(f"Error: Could not find file '{csv_file_path}'")
        print("Please ensure the CSV file is in the specified directory.")
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
