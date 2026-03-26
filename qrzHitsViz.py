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
    """Cumulative hits over time — log scale."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['Time_UTC'], y=df['Hits'],
        mode='lines', line=dict(color=COLOR_PRIMARY, width=2),
        name='Hits',
        hovertemplate='%{x|%Y-%m-%d %H:%M UTC}<br>Hits: %{y:,}<extra></extra>',
    ))
    fig.update_layout(**make_chart_layout(
        'QRZ Profile Hits — Log Scale',
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
        f'Hits — Last {days} Days',
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
        title=dict(text='Daily Hit Gains — Contribution Calendar (UTC)', font=dict(size=16, color='#333333')),
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
        f'Anomaly Detection — Rate of Change (UTC)',
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


def build_html(figures, summary_html, callsign):
    """Combine all figures into a single self-contained HTML page."""
    chart_divs = []
    chart_js = []

    for i, (title, fig) in enumerate(figures):
        if fig is None:
            continue
        div_id = f'chart-{i}'
        chart_divs.append(f'<div class="chart-container"><div id="{div_id}"></div></div>')
        fig_json = fig.to_json()
        chart_js.append(f"""
        (function() {{
            var data = {fig_json};
            Plotly.newPlot('{div_id}', data.data, data.layout, {{responsive: true}});
        }})();
        """)

    charts_html = '\n'.join(chart_divs)
    charts_script = '\n'.join(chart_js)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{callsign} QRZ Lookup Stats</title>
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f8f9fa;
            color: #333;
            padding: 20px;
            max-width: 1200px;
            margin: 0 auto;
        }}
        h1 {{
            font-size: 1.8rem;
            font-weight: 600;
            margin-bottom: 8px;
            color: #1a1a2e;
        }}
        .subtitle {{
            color: #666;
            margin-bottom: 24px;
            font-size: 0.95rem;
        }}
        .tz-info {{
            display: inline-block;
            background: #e8f4f8;
            color: #1a6b8a;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 0.85rem;
            margin-bottom: 20px;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 12px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: white;
            border-radius: 8px;
            padding: 16px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
            text-align: center;
        }}
        .stat-value {{
            font-size: 1.4rem;
            font-weight: 700;
            color: #1a1a2e;
        }}
        .stat-label {{
            font-size: 0.8rem;
            color: #888;
            margin-top: 4px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .chart-container {{
            background: white;
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        }}
    </style>
</head>
<body>
    <h1>{callsign} QRZ Lookup Stats</h1>
    <div class="subtitle">Auto-updated hourly. All times shown in UTC.</div>
    <div class="tz-info" id="tz-info">Detecting your timezone...</div>

    {summary_html}
    {charts_html}

    <script>
    // Display viewer's timezone
    (function() {{
        try {{
            var tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
            document.getElementById('tz-info').textContent = 'Your timezone: ' + tz + ' — chart hover tooltips show UTC';
        }} catch(e) {{
            document.getElementById('tz-info').textContent = 'Charts display UTC times';
        }}
    }})();

    {charts_script}
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
        ('Hits — Log Scale', fig_raw_values_log(df)),
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
    html = build_html(figures, summary_html, callsign)

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'index.html')
    with open(output_path, 'w') as f:
        f.write(html)
    print(f"Saved: {output_path}")

    # Generate standalone embed pages and static PNGs for each chart
    for title, fig in figures:
        if fig is None:
            continue
        slug = title.lower().replace(' ', '_').replace('—', '').replace('\u2014', '')

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
