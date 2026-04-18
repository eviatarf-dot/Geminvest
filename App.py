import streamlit as st
import finnhub
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- CONFIGURACIÓN DE APIS ---
API_KEY = "d7ht319r01qu8vfmhpa0d7ht319r01qu8vfmhpag"
client = finnhub.Client(api_key=API_KEY)

st.set_page_config(page_title="Gemini Financial Terminal", layout="wide", page_icon="📈")

# Estilo CSS para el punto verde parpadeante (Indicador de conexión)
st.markdown("""
    <style>
    .blink_me { animation: blinker 1.5s linear infinite; color: #00ff00; font-size: 24px; font-weight: bold; }
    @keyframes blinker { 50% { opacity: 0; } }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCIONES DE LÓGICA CORE ---

@st.cache_data(ttl=3600)
def get_market_context():
    """Analiza el estado del S&P 500 (SPY) para filtrar el riesgo macro."""
    spy = yf.download("SPY", period="100d", progress=False)
    current_spy = spy['Close'].iloc[-1]
    ema50_spy = ta.ema(spy['Close'], length=50).iloc[-1]
    return "BULLISH" if current_spy > ema50_spy else "BEARISH"

def analizar_estrategia(ticker, datos_live, hist, market_status):
    """Calcula indicadores técnicos, probabilidad y niveles operativos."""
    # Indicadores Técnicos
    c = hist['Close']
    rsi = ta.rsi(c, length=14).iloc[-1]
    atr = ta.atr(hist['High'], hist['Low'], c, length=14).iloc[-1]
    ema20 = ta.ema(c, length=20).iloc[-1]
    ema50 = ta.ema(c, length=50).iloc[-1]
    
    # Volumen Relativo (RVol)
    avg_vol = hist['Volume'].rolling(window=20).mean().iloc[-1]
    rvol = hist['Volume'].iloc[-1] / avg_vol
    
    # Cálculo de Probabilidad Gemini
    prob = 55 # Base
    if market_status == "BULLISH": prob += 15
    else: prob -= 20
    if 40 < rsi < 60: prob += 10
    if rvol > 1.3: prob += 10
    
    # Niveles Operativos (Tu fórmula 1.5x ATR)
    precio = datos_live['c']
    entrada = ema20 if precio > ema20 else precio
    sl = entrada - (1.5 * atr)
    tp1 = entrada + (2 * atr)
    tp2 = entrada + (4 * atr)
    
    return {
        "prob": max(min(prob, 95), 5), "rsi": rsi, "rvol": rvol,
        "sl": sl, "tp1": tp1, "tp2": tp2, "entrada": entrada,
        "ema20": ema20, "ema50": ema50, "atr": atr
    }

# --- INTERFAZ DE USUARIO (SIDEBAR) ---

st.sidebar.title("💎 Configuración")
ticker = st.sidebar.text_input("Ticker Acción (USA)", value="NVDA").upper()
market_status = get_market_context()

st.sidebar.markdown(f"**Mercado (SPY):** {'🟢 ALCISTA' if market_status == 'BULLISH' else '🔴 BAJISTA'}")

# Escáner Premarket
st.sidebar.divider()
if st.sidebar.button("🔍 Escáner Premarket Gaps"):
    st.toast("Escaneando Watchlist...", icon="📡")
    watchlist = ["AAPL", "TSLA", "NVDA", "AMD", "META", "MSFT", "GOOGL", "AMZN"]
    gaps = []
    for t in watchlist:
        q = client.quote(t)
        change = ((q['c'] - q['pc']) / q['pc']) * 100
        if abs(change) > 2.0:
            gaps.append({"Ticker": t, "Cambio %": f"{change:.2f}%", "Precio": q['c']})
    if gaps: st.sidebar.table(pd.DataFrame(gaps))
    else: st.sidebar.write("Sin movimientos bruscos.")

# Gestión de Capital
st.sidebar.divider()
st.sidebar.subheader("💰 Gestión de Capital")
cap_total = st.sidebar.number_input("Capital Total ($)", value=10000)
riesgo_pct = st.sidebar.slider("Riesgo por trade (%)", 0.5, 3.0, 1.0) / 100

# --- CUERPO PRINCIPAL ---

quote = client.quote(ticker)
hist = yf.download(ticker, period="120d", progress=False)

if not hist.empty and quote['c'] > 0:
    res = analizar_estrategia(ticker, quote, hist, market_status)
    
    # Indicador Live Premarket
    col_t1, col_t2 = st.columns([0.1, 0.9])
    with col_t1: st.markdown('<p class="blink_me">●</p>', unsafe_allow_html=True)
    with col_t2: st.title(f"{ticker} - ${quote['c']:.2f}")

    # Notificación de Entrada Premarket
    distancia_entrada = abs(quote['c'] - res['entrada']) / res['entrada']
    if distancia_entrada < 0.005:
        st.success(f"🎯 **AVISO PREMARKET:** El precio está en zona de entrada (${res['entrada']:.2f})")
        st.toast("¡Zona de entrada detectada!", icon="✅")

    # Alerta Earnings
    cal = client.earnings_calendar(_from=datetime.now().strftime('%Y-%m-%d'), to=(datetime.now()+timedelta(days=7)).strftime('%Y-%m-%d'), symbol=ticker)
    if cal.get('earningsCalendar'):
        st.warning(f"⚠️ RESULTADOS PRÓXIMOS: {cal['earningsCalendar'][0]['date']}")

    # Dashboard de Métricas
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Probabilidad", f"{res['prob']}%")
    c2.metric("RSI", f"{res['rsi']:.1f}")
    c3.metric("RVol", f"{res['rvol']:.2f}x")
    c4.metric("Entrada Sugerida", f"${res['entrada']:.2f}")

    # Gestión de Posición
    riesgo_usd = cap_total * riesgo_pct
    pos_size = riesgo_usd / (res['entrada'] - res['sl']) if (res['entrada'] - res['sl']) > 0 else 0
    
    st.info(f"👉 **GESTIÓN DE RIESGO:** Compra **{int(pos_size)} acciones**. Si toca el Stop (${res['sl']:.2f}), perderás ${riesgo_usd:.2f} (1% de tu cuenta).")

    # Niveles de Salida
    st.subheader("🎯 Objetivos de Salida")
    s1, s2, s3 = st.columns(3)
    s1.error(f"STOP LOSS: ${res['sl']:.2f}")
    s2.success(f"TAKE PROFIT 1: ${res['tp1']:.2f}")
    s3.success(f"TAKE PROFIT 2: ${res['tp2']:.2f}")

    # Gráfico
    fig = go.Figure(data=[go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'])])
    fig.add_hline(y=res['sl'], line_color="red", line_dash="dash", annotation_text="STOP")
    fig.add_hline(y=res['tp1'], line_color="green", line_dash="dash", annotation_text="TP1")
    fig.update_layout(template="plotly_dark", height=600, margin=dict(l=0, r=0, b=0, t=0))
    st.plotly_chart(fig, use_container_width=True)

else:
    st.error("Ticker no encontrado o sin datos.")
