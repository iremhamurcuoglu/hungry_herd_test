import streamlit as st

st.set_page_config(
    page_title="🐴 Feed the Herd 🥕",
    page_icon="🐴",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Hide Streamlit UI elements for fullscreen game experience
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .block-container {
        padding: 0 !important;
        max-width: 100% !important;
    }
    iframe {
        border: none !important;
    }
    .game-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        min-height: 95vh;
        background: #1a1a2e;
    }
    .game-title {
        color: #ffd700;
        font-family: Arial, sans-serif;
        font-size: 24px;
        margin-bottom: 10px;
        text-align: center;
    }
    .game-info {
        color: #888;
        font-family: Arial, sans-serif;
        font-size: 13px;
        margin-bottom: 15px;
        text-align: center;
    }
    .stApp {
        background: #1a1a2e;
    }
</style>
""", unsafe_allow_html=True)

GAME_URL = "https://iremhamurcuoglu.github.io/hungry_herd_irem/"

st.markdown("""
<div class="game-container">
    <div class="game-title">🐴 Feed the Herd 🥕</div>
    <div class="game-info">Oyun yükleniyorsa lütfen bekleyin. Tıklayarak veya klavye ile oynayabilirsiniz.</div>
</div>
""", unsafe_allow_html=True)

st.components.v1.iframe(GAME_URL, width=1024, height=768, scrolling=False)
