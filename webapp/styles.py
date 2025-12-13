"""
CSS styles for the Spotify2Tidal web application.
Extracted for maintainability.
"""

CUSTOM_CSS = """
<style>
    /* Main background with subtle gradient */
    .stApp {
        background: linear-gradient(160deg, #0d1117 0%, #161b22 50%, #0d1117 100%);
        background-attachment: fixed;
    }

    /* Main container styling */
    .main .block-container {
        background: rgba(22, 27, 34, 0.95);
        border-radius: 16px;
        padding: 2rem;
        margin-top: 1rem;
        border: 1px solid rgba(48, 54, 61, 0.8);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    }

    /* Title gradient */
    h1 {
        background: linear-gradient(135deg, #1DB954 0%, #1ed760 50%, #00d4aa 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        font-weight: 700;
        letter-spacing: -0.5px;
    }

    /* Subheaders */
    h2, h3 {
        color: #e6edf3 !important;
        font-weight: 600;
    }

    /* Button styling */
    .stButton > button {
        width: 100%;
        border-radius: 12px;
        padding: 0.75rem 1.5rem;
        font-weight: 600;
        transition: all 0.2s ease;
        border: none;
    }

    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }

    /* Spotify brand button */
    .spotify-btn > button {
        background: linear-gradient(135deg, #1DB954 0%, #1ed760 100%) !important;
        color: white !important;
    }

    /* Tidal brand button */
    .tidal-btn > button {
        background: linear-gradient(135deg, #00FFFF 0%, #00d4aa 100%) !important;
        color: #0d1117 !important;
    }

    /* Primary sync button */
    .sync-btn > button {
        background: linear-gradient(135deg, #1DB954 0%, #00FFFF 100%) !important;
        color: white !important;
        font-size: 1.1rem !important;
        padding: 1rem 2rem !important;
        text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
    }

    /* Card-like containers */
    .status-card {
        background: rgba(48, 54, 61, 0.5);
        border: 1px solid rgba(48, 54, 61, 0.8);
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin: 0.5rem 0;
    }

    .success-card {
        background: rgba(29, 185, 84, 0.15);
        border: 1px solid rgba(29, 185, 84, 0.4);
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin: 0.5rem 0;
    }

    .warning-card {
        background: rgba(245, 158, 11, 0.15);
        border: 1px solid rgba(245, 158, 11, 0.4);
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin: 0.5rem 0;
    }

    .error-card {
        background: rgba(239, 68, 68, 0.15);
        border: 1px solid rgba(239, 68, 68, 0.4);
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin: 0.5rem 0;
    }

    /* Activity log styling */
    .activity-log {
        background: rgba(13, 17, 23, 0.8);
        border: 1px solid rgba(48, 54, 61, 0.6);
        border-radius: 8px;
        padding: 0.75rem;
        font-family: 'SF Mono', 'Fira Code', monospace;
        font-size: 0.85rem;
        max-height: 300px;
        overflow-y: auto;
    }

    .log-entry {
        padding: 0.25rem 0;
        border-bottom: 1px solid rgba(48, 54, 61, 0.3);
    }

    .log-entry:last-child {
        border-bottom: none;
    }

    .log-time {
        color: #8b949e;
        margin-right: 0.5rem;
    }

    .log-success { color: #3fb950; }
    .log-warning { color: #d29922; }
    .log-error { color: #f85149; }
    .log-info { color: #58a6ff; }
    .log-progress { color: #a371f7; }

    /* Divider styling */
    hr {
        border-color: rgba(48, 54, 61, 0.6) !important;
        margin: 1.5rem 0 !important;
    }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: rgba(22, 27, 34, 0.98);
        border-right: 1px solid rgba(48, 54, 61, 0.6);
    }

    [data-testid="stSidebar"] .block-container {
        padding-top: 1rem;
    }

    /* Metric styling */
    [data-testid="stMetric"] {
        background: rgba(48, 54, 61, 0.3);
        border-radius: 8px;
        padding: 0.75rem;
    }

    /* Connection status dots */
    .status-dot {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        margin-right: 8px;
    }
    .status-connected { background: #3fb950; box-shadow: 0 0 8px #3fb950; }
    .status-disconnected { background: #8b949e; }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
"""
