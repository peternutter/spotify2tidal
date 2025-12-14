"""
Custom CSS for the application.
Modern dark theme with proper alignment and visual polish.
"""

CUSTOM_CSS = """
<style>
    /* Import Inter font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /*
      Simple, stable theme:
      - Keep Streamlit layout/controls intact
      - Only add a nicer background + consistent typography + simple cards/buttons
    */

    :root {
        --accent: #1DB954;
        --accent-hover: #1ed760;
        --accent-2: #00FFFF;
        --bg-0: #0b0f14;
        --bg-1: #0f1620;
        --card: rgba(22, 27, 34, 0.78);
        --card-hover: rgba(30, 37, 46, 0.88);
        --border: rgba(48, 54, 61, 0.8);
        --text: #e6edf3;
        --text-2: #8b949e;
        --text-3: #6e7681;
        --shadow: 0 8px 22px rgba(0, 0, 0, 0.22);
    }

    html, body {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        background: var(--bg-0);
        color: var(--text);
    }

    /* App background (safe selectors) */
    [data-testid="stAppViewContainer"], .stApp {
        background:
            radial-gradient(
                1000px 600px at 12% -10%,
                rgba(29, 185, 84, 0.16) 0%,
                rgba(29, 185, 84, 0) 55%
            ),
            radial-gradient(
                800px 520px at 105% 0%,
                rgba(0, 255, 255, 0.10) 0%,
                rgba(0, 255, 255, 0) 55%
            ),
            linear-gradient(180deg, var(--bg-0) 0%, var(--bg-1) 55%, var(--bg-0) 100%);
    }

    /* IMPORTANT: only style the MAIN container, not the sidebar */
    [data-testid="stAppViewContainer"] .main .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 900px;
    }

    /* Page title styling - centered */
    .main-title {
        text-align: center;
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, var(--accent) 0%, var(--accent-2) 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.5rem;
    }

    .main-subtitle {
        text-align: center;
        color: var(--text-2);
        font-size: 1.1rem;
        font-weight: 400;
        margin-bottom: 2.5rem;
    }

    /* Card styling (simple "soft cards") */
    .status-card, .success-card, .warning-card, .error-card, .get-started-card {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        backdrop-filter: blur(10px);
        box-shadow: var(--shadow);
        transition: all 0.2s ease;
    }

    .status-card:hover, .success-card:hover, .warning-card:hover {
        background: var(--card-hover);
        border-color: rgba(48, 54, 61, 1);
    }

    /* Get Started card - special centered styling */
    .get-started-card {
        text-align: center;
        padding: 3rem 2rem;
        background: linear-gradient(
            145deg,
            rgba(22, 27, 34, 0.92) 0%,
            rgba(11, 15, 20, 0.96) 100%
        );
        border: 1px solid var(--border);
    }

    .get-started-card h3 {
        color: var(--text);
        font-size: 1.4rem;
        font-weight: 600;
        margin-bottom: 0.75rem;
    }

    .get-started-card p {
        color: var(--text-2);
        font-size: 1rem;
        margin: 0;
    }

    /* Success card with green accent */
    .success-card {
        border-left: 3px solid var(--accent);
        background: linear-gradient(
            90deg, rgba(29, 185, 84, 0.10) 0%, var(--card) 100%
        );
    }

    /* Warning card with amber accent */
    .warning-card {
        border-left: 3px solid #F59E0B;
        background: linear-gradient(
            90deg, rgba(245, 158, 11, 0.10) 0%, var(--card) 100%
        );
    }

    /* Error card with red accent */
    .error-card {
        border-left: 3px solid #EF4444;
        background: linear-gradient(
            90deg, rgba(239, 68, 68, 0.10) 0%, var(--card) 100%
        );
    }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #161b22 0%, #0d1117 100%);
        border-right: 1px solid var(--border);
    }

    [data-testid="stSidebar"] .block-container {
        padding-top: 1.25rem;
    }

    /* Sidebar headers */
    [data-testid="stSidebar"] h2 {
        color: var(--text);
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 1rem;
    }

    [data-testid="stSidebar"] h3 {
        color: var(--text);
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.75rem;
    }

    /* Connection cards in sidebar */
    .connection-card {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 0.875rem 1rem;
        margin-bottom: 0.5rem;
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }

    .connection-card.connected {
        border-color: var(--accent);
        background: linear-gradient(
            90deg, rgba(29, 185, 84, 0.14) 0%, var(--card) 100%
        );
    }

    /* Status dots */
    .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
        margin-right: 0.5rem;
    }

    .status-dot.status-connected {
        background: var(--accent);
        box-shadow: 0 0 8px rgba(29, 185, 84, 0.65);
    }

    .status-dot.status-disconnected {
        background: var(--text-3);
    }

    /* Buttons (keep sizing/layout default; only change visuals) */
    .stButton button,
    div[data-testid="stButton"] button {
        background: linear-gradient(
            135deg,
            rgba(29, 185, 84, 0.95) 0%,
            rgba(21, 128, 61, 0.95) 100%
        );
        color: white;
        border: 0;
        border-radius: 10px;
        font-weight: 600;
        padding: 0.6rem 1rem;
        transition: transform 0.15s ease, box-shadow 0.15s ease, filter 0.15s ease;
    }

    .stButton button:hover,
    div[data-testid="stButton"] button:hover {
        transform: translateY(-1px);
        box-shadow: 0 10px 22px rgba(29, 185, 84, 0.20);
        filter: brightness(1.03);
    }

    .stButton button:active,
    div[data-testid="stButton"] button:active {
        transform: translateY(0px);
        box-shadow: none;
    }

    /* Link button styling */
    .stLinkButton a,
    div[data-testid="stLinkButton"] a {
        background: linear-gradient(
            135deg,
            rgba(29, 185, 84, 0.95) 0%,
            rgba(21, 128, 61, 0.95) 100%
        ) !important;
        color: white !important;
        border: 0 !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        transition: transform 0.15s ease, box-shadow 0.15s ease,
            filter 0.15s ease !important;
    }

    .stLinkButton a:hover,
    div[data-testid="stLinkButton"] a:hover {
        transform: translateY(-1px);
        box-shadow: 0 10px 22px rgba(29, 185, 84, 0.20);
        filter: brightness(1.03);
    }

    /* Divider styling */
    hr {
        border-color: var(--border);
        margin: 1.5rem 0;
    }

    /* Activity Log */
    .activity-log {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 1rem;
        max-height: 250px;
        overflow-y: auto;
        font-family: 'SF Mono', 'Fira Code', 'Monaco', monospace;
        font-size: 0.8rem;
    }

    .log-entry {
        padding: 0.375rem 0;
        border-bottom: 1px solid var(--border);
        display: flex;
        align-items: baseline;
    }

    .log-entry:last-child {
        border-bottom: none;
    }

    .log-time {
        color: var(--text-3);
        font-weight: 500;
        margin-right: 0.75rem;
        min-width: 60px;
        font-size: 0.75rem;
    }

    .log-message {
        flex-grow: 1;
        color: var(--text-2);
    }

    .log-success { color: var(--accent); }
    .log-error { color: #EF4444; }
    .log-warning { color: #F59E0B; }
    .log-info { color: var(--text-2); }
    .log-progress { color: var(--accent-2); }

    /* Expander styling */
    .streamlit-expanderHeader {
        background: var(--bg-card);
        border-radius: 8px;
        font-weight: 500;
    }

    /* Caption/footer text */
    .stCaption {
        color: var(--text-3) !important;
    }

    /* Metric styling */
    [data-testid="stMetricValue"] {
        color: var(--text);
    }

    [data-testid="stMetricLabel"] {
        color: var(--text-2);
    }

    /* Sync button wrapper - center alignment */
    .sync-btn {
        display: flex;
        justify-content: center;
        margin: 2rem 0;
    }

    .sync-btn .stButton {
        width: auto;
        min-width: 200px;
    }

    .sync-btn .stButton button,
    .sync-btn div[data-testid="stButton"] button {
        font-size: 1.1rem;
        padding: 0.875rem 2rem;
        background: linear-gradient(
            135deg, rgba(29, 185, 84, 1) 0%, rgba(5, 150, 105, 1) 100%
        );
    }

    /* Info/warning/error boxes */
    .stAlert {
        border-radius: 8px;
        border: 1px solid var(--border);
    }

    /* Download button */
    .stDownloadButton > button {
        background: var(--card);
        border: 1px solid var(--border);
        color: var(--text);
    }

    .stDownloadButton > button:hover {
        background: var(--card-hover);
        border-color: var(--accent);
    }

    /* Progress Metrics Display */
    .progress-metrics {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 1rem 1.25rem;
        margin: 1rem 0;
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
        gap: 0.75rem;
    }

    .progress-metric {
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
    }

    .metric-label {
        color: var(--text-3);
        font-size: 0.75rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.03em;
    }

    .metric-value {
        color: var(--text);
        font-size: 0.95rem;
        font-weight: 600;
        font-family: 'SF Mono', 'Fira Code', 'Monaco', monospace;
    }

    /* Completion Stats */
    .completion-stats {
        background: linear-gradient(
            145deg,
            rgba(29, 185, 84, 0.08) 0%,
            var(--card) 100%
        );
        border: 1px solid var(--accent);
        border-radius: 12px;
        padding: 1.25rem 1.5rem;
        margin: 1rem 0;
        display: flex;
        justify-content: space-around;
        flex-wrap: wrap;
        gap: 1rem;
    }

    .stat-item {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 0.25rem;
        min-width: 80px;
    }

    .stat-icon {
        font-size: 1.5rem;
        margin-bottom: 0.25rem;
    }

    .stat-label {
        color: var(--text-2);
        font-size: 0.75rem;
        font-weight: 500;
        text-transform: uppercase;
    }

    .stat-value {
        color: var(--text);
        font-size: 1.1rem;
        font-weight: 700;
        font-family: 'SF Mono', 'Fira Code', 'Monaco', monospace;
    }

</style>
"""
