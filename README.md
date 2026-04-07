# QRZ Lookup Tracker

Tracks the cumulative lookup count on a my QRZ page over time and generates visualizations. This can be useful, especially for voice operations, to see how well I'm getting out because people will often look you up without managing to make a contact with you. Made by Evan Boyar, NR8E.

## How it works

`qrzLookupTracker.sh` runs hourly (or as often as you'd like) via github actions. It authenticates to QRZ using a session cookie, verifies the session is valid (to avoid inflating the count with unauthenticated visits), records the current lookup count to a CSV, then regenerates all plots via `qrzHitsViz.py`.

If the session expires, a GitHub issue is raised.

## Forking
It's pretty easy to fork. 
1. You'd want a blank CSV like my NR8E_QRZ_stats.csv, but with your callsign replacing mine.
2. Log into QRZ.com and grab your xfsession cookie.
3. Enter the info indicated by the .secrets.example in your "Actions secrets and variables" for your repo, under "Repository secrets"
4. Set up a Github Actions workflow to run this every so often (see [mine here](https://github.com/EvanBoyar/qrz-tracker/blob/main/.github/workflows/qrz-tracker.yml))

## Plots generated

| File | Description |
|---|---|
| `raw_values_plot.png` | All-time lookup count, linear scale (UTC) |
| `raw_values_log_plot.png` | All-time lookup count, log scale (UTC) |
| `recent_raw_values_plot.png` | Last 30 days, linear scale (UTC + local time) |
| `hourly_rate_analysis.png` | Average lookup rate by hour of day |
| `daily_activity_heatmap.png` | Activity heatmap by date and hour |
| `day_of_week_heatmap.png` | Activity heatmap by day of week and hour |
| `contribution_calendar.png` | GitHub-style calendar of daily hit gains |
| `polar_clock.png` | 24-hour clock plot of hourly activity |
| `anomaly_detection.png` | Spike and quiet period detection |
| `milestone_forecast.png` | Projected dates for future hit milestones |

## Thanks

Special thanks to Todd, KE2AEQ for helping out with the original shell script!
