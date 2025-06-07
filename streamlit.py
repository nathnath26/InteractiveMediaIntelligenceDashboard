import streamlit as st
import pandas as pd
import requests
import io
import plotly.graph_objects as go
import plotly.express as px

# Colors for charts (coquette style)
COLORS = ['#FADADD', '#ADD8E6', '#C7CEEA', '#DDA0DD', '#FFE4E1', '#E6E6FA', '#FFF0F5', '#DEB887']

# Set Streamlit page configuration
st.set_page_config(layout="wide", page_title="Interactive Media Intelligence Dashboard", page_icon="📊")

# --- Helper function to parse CSV data ---
@st.cache_data
def parse_csv_data(uploaded_file):
    """
    Parses an uploaded CSV file into a pandas DataFrame, cleans and processes data.
    - Converts 'Date' column to datetime objects.
    - Fills empty 'Engagements' with 0 and converts to integer.
    - Removes rows with invalid dates.
    """
    if uploaded_file is None:
        return pd.DataFrame()

    try:
        df = pd.read_csv(uploaded_file)

        # Define expected columns
        required_columns = ['Date', 'Engagements', 'Sentiment', 'Platform', 'Media Type', 'Location']
        
        # Check if all required columns are present
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            st.warning(f"Kolom berikut tidak ditemukan dalam file CSV: {', '.join(missing_columns)}. "
                       f"Beberapa filter dan grafik mungkin tidak berfungsi sebagaimana mestinya.")
            # We will still proceed with available columns but handle missing ones gracefully later.

        # Data cleaning: Convert 'Date' to datetime and 'Engagements' to int
        # Errors='coerce' will turn unparseable dates into NaT (Not a Time)
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df.dropna(subset=['Date'], inplace=True) # Drop rows where 'Date' is NaT (invalid date)
        else:
            st.warning("Kolom 'Date' tidak ditemukan. Tren keterlibatan tidak akan tersedia.")
            df['Date'] = pd.NaT # Set to NaT if missing to avoid errors in date filtering

        if 'Engagements' in df.columns:
            df['Engagements'] = pd.to_numeric(df['Engagements'], errors='coerce').fillna(0).astype(int)
        else:
            st.warning("Kolom 'Engagements' tidak ditemukan. Data keterlibatan mungkin tidak akurat.")
            df['Engagements'] = 0 # Default to 0 if missing

        return df
    except Exception as e:
        st.error(f"Error parsing CSV: {e}. Please ensure the file is a valid CSV and has the expected columns.")
        return pd.DataFrame()

# --- Gemini API Call Function ---
def generate_campaign_summary_llm(prompt):
    """
    Calls the Gemini API to generate a campaign summary based on the provided prompt.
    """
    api_key = "" # Canvas will provide this in runtime

    if not api_key: # Added check for empty API key
        st.error("API Key tidak ditemukan. Pastikan API Key diatur dengan benar di lingkungan Canvas.")
        return "Gagal membuat ringkasan: API Key tidak diatur."

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"

    chat_history = [{"role": "user", "parts": [{"text": prompt}]}]
    payload = {"contents": chat_history}

    try:
        response = requests.post(api_url, headers={'Content-Type': 'application/json'}, json=payload)
        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
        result = response.json()

        if result.get('candidates') and len(result['candidates']) > 0 and \
           result['candidates'][0].get('content') and result['candidates'][0]['content'].get('parts') and \
           len(result['candidates'][0]['content']['parts']) > 0:
            return result['candidates'][0]['content']['parts'][0]['text']
        else:
            st.error("Gemini API response structure unexpected.")
            return "Gagal membuat ringkasan. Silakan coba lagi."
    except requests.exceptions.RequestException as e:
        st.error(f"Error calling Gemini API: {e}. Please ensure you have internet connectivity and a valid API key.")
        return "Error membuat ringkasan: Terjadi masalah koneksi atau API."
    except Exception as e:
        st.error(f"An unexpected error occurred during summary generation: {e}")
        return "Error membuat ringkasan: Terjadi kesalahan tak terduga."


# --- Main Application Layout ---

st.markdown(
    """
    <style>
    .reportview-container .main .block-container {
        padding-top: 2rem;
        padding-right: 2rem;
        padding-left: 2rem;
        padding-bottom: 2rem;
    }
    .stSelectbox > div > div {
        border-radius: 0.75rem; /* rounded-lg */
        border-color: #FADADD; /* pink-200 */
        background-color: #FFF0F5; /* pink-50 */
        color: #4A5568; /* gray-800 */
    }
    .stDateInput > label > div {
        border-radius: 0.75rem;
        border-color: #FADADD;
        background-color: #FFF0F5;
        color: #4A5568;
    }
    .stButton > button {
        border-radius: 0.75rem;
        padding: 0.75rem 1.5rem;
        font-weight: bold;
        transition: transform 0.2s;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    /* Coquette style buttons for the app */
    .stButton > button:hover {
        transform: scale(1.05);
    }
    .stButton > button:active {
        transform: scale(0.95);
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("💖 Interactive Media Intelligence Dashboard 💖")

# --- File Upload Section ---
st.header("Unggah File CSV Anda")
uploaded_file = st.file_uploader(
    "Silakan unggah file CSV yang berisi data intelijen media Anda. "
    "Pastikan memiliki kolom untuk 'Date', 'Engagements', 'Sentiment', 'Platform', 'Media Type', dan 'Location'.",
    type="csv"
)

df_original = parse_csv_data(uploaded_file)

if df_original.empty:
    st.info("Unggah file CSV di atas untuk memulai analitik.")
    st.stop() # Stop execution if no data is loaded

st.success(f"File CSV berhasil diunggah dengan {len(df_original)} baris.")

# --- Sidebar for Filters ---
st.sidebar.header("Filter Data")

# Populate unique filter values, handling missing columns gracefully
unique_platforms = ['All'] + sorted(df_original['Platform'].dropna().unique().tolist()) if 'Platform' in df_original.columns else ['All']
unique_sentiments = ['All'] + sorted(df_original['Sentiment'].dropna().unique().tolist()) if 'Sentiment' in df_original.columns else ['All']
unique_media_types = ['All'] + sorted(df_original['Media Type'].dropna().unique().tolist()) if 'Media Type' in df_original.columns else ['All']
unique_locations = ['All'] + sorted(df_original['Location'].dropna().unique().tolist()) if 'Location' in df_original.columns else ['All']

# Filter selectboxes
platform_filter = st.sidebar.selectbox("Platform", unique_platforms)
sentiment_filter = st.sidebar.selectbox("Sentiment", unique_sentiments)
media_type_filter = st.sidebar.selectbox("Media Type", unique_media_types)
location_filter = st.sidebar.selectbox("Location", unique_locations)

# Date Range Filter
st.sidebar.markdown("---")
st.sidebar.subheader("Filter Rentang Tanggal")

# Handle min_date and max_date if 'Date' column is missing or empty
min_date = df_original['Date'].min().date() if 'Date' in df_original.columns and not df_original['Date'].empty else None
max_date = df_original['Date'].max().date() if 'Date' in df_original.columns and not df_original['Date'].empty else None

# Provide default values for date inputs if min_date/max_date are None
start_date_filter = st.sidebar.date_input(
    "Tanggal Mulai", 
    value=min_date if min_date else pd.to_datetime('2023-01-01').date(), 
    min_value=min_date, 
    max_value=max_date
)
end_date_filter = st.sidebar.date_input(
    "Tanggal Akhir", 
    value=max_date if max_date else pd.to_datetime('2023-12-31').date(), 
    min_value=min_date, 
    max_value=max_date
)


# --- Apply Filters ---
df_filtered = df_original.copy()

if platform_filter != 'All' and 'Platform' in df_filtered.columns:
    df_filtered = df_filtered[df_filtered['Platform'] == platform_filter]
if sentiment_filter != 'All' and 'Sentiment' in df_filtered.columns:
    df_filtered = df_filtered[df_filtered['Sentiment'] == sentiment_filter]
if media_type_filter != 'All' and 'Media Type' in df_filtered.columns:
    df_filtered = df_filtered[df_filtered['Media Type'] == media_type_filter]
if location_filter != 'All' and 'Location' in df_filtered.columns:
    df_filtered = df_filtered[df_filtered['Location'] == location_filter]

# Apply date filters only if 'Date' column exists
if 'Date' in df_filtered.columns:
    if start_date_filter:
        df_filtered = df_filtered[df_filtered['Date'].dt.date >= start_date_filter]
    if end_date_filter:
        df_filtered = df_filtered[df_filtered['Date'].dt.date <= end_date_filter]

if df_filtered.empty:
    st.warning("Tidak ada data yang cocok dengan kriteria filter yang dipilih.")
    st.stop()


# --- Campaign Strategy Summary (LLM Integration) ---
st.markdown("## ⚡ Ringkasan Strategi Kampanye")

if st.button("Buat Ringkasan Strategi", type="primary"):
    with st.spinner('Membuat ringkasan...'):
        # Prepare aggregated data for the LLM prompt, checking for column existence
        dominant_sentiment = 'N/A'
        if 'Sentiment' in df_filtered.columns and not df_filtered['Sentiment'].empty:
            sentiment_counts = df_filtered['Sentiment'].value_counts()
            dominant_sentiment = sentiment_counts.idxmax() if not sentiment_counts.empty else 'N/A'

        top_platform = 'N/A'
        top_platform_engagements = 0
        if 'Platform' in df_filtered.columns and 'Engagements' in df_filtered.columns:
            platform_engagements = df_filtered.groupby('Platform')['Engagements'].sum().sort_values(ascending=False)
            top_platform = platform_engagements.index[0] if not platform_engagements.empty else 'N/A'
            top_platform_engagements = platform_engagements.iloc[0] if not platform_engagements.empty else 0

        # Engagement trend
        overall_trend = 'stabil'
        start_date_llm = 'N/A'
        end_date_llm = 'N/A'

        if 'Date' in df_filtered.columns and 'Engagements' in df_filtered.columns:
            engagement_trend_data = df_filtered.groupby(df_filtered['Date'].dt.date)['Engagements'].sum().reset_index()
            engagement_trend_data.columns = ['date', 'engagements']
            engagement_trend_data = engagement_trend_data.sort_values('date')

            if len(engagement_trend_data) > 1:
                first_eng = engagement_trend_data.iloc[0]['engagements']
                last_eng = engagement_trend_data.iloc[-1]['engagements']
                if last_eng > first_eng * 1.1:
                    overall_trend = 'meningkat'
                elif last_eng < first_eng * 0.9:
                    overall_trend = 'menurun'
            
            start_date_llm = engagement_trend_data['date'].min().strftime('%Y-%m-%d') if not engagement_trend_data.empty else 'N/A'
            end_date_llm = engagement_trend_data['date'].max().strftime('%Y-%m-%d') if not engagement_trend_data.empty else 'N/A'

        dominant_media_type = 'N/A'
        if 'Media Type' in df_filtered.columns and not df_filtered['Media Type'].empty:
            media_type_counts = df_filtered['Media Type'].value_counts()
            dominant_media_type = media_type_counts.idxmax() if not media_type_counts.empty else 'N/A'

        top_location = 'N/A'
        top_location_engagements = 0
        if 'Location' in df_filtered.columns and 'Engagements' in df_filtered.columns:
            location_engagements = df_filtered.groupby('Location')['Engagements'].sum().sort_values(ascending=False)
            top_location = location_engagements.index[0] if not location_engagements.empty else 'N/A'
            top_location_engagements = location_engagements.iloc[0] if not location_engagements.empty else 0

        prompt = f"""Berdasarkan data intelijen media dan wawasan berikut, berikan ringkasan strategi kampanye yang ringkas (tindakan dan rekomendasi utama).
- Sentimen Dominan: {dominant_sentiment}.
- Platform Keterlibatan Teratas: {top_platform} dengan {top_platform_engagements} keterlibatan.
- Tren Keterlibatan Keseluruhan: {overall_trend} dari {start_date_llm} hingga {end_date_llm}.
- Jenis Media yang Paling Sering Digunakan: {dominant_media_type}.
- Lokasi Teratas untuk Keterlibatan: {top_location} dengan {top_location_engagements} keterlibatan.
Sarankan 3-5 rekomendasi yang dapat ditindaklanjuti untuk mengoptimalkan kampanye media. Fokus pada langkah-langkah yang dapat ditindaklanjuti berdasarkan poin data ini."""

        campaign_summary = generate_campaign_summary_llm(prompt)
        st.session_state.campaign_summary = campaign_summary

if 'campaign_summary' in st.session_state and st.session_state.campaign_summary:
    st.markdown(st.session_state.campaign_summary)
else:
    st.info("Klik 'Buat Ringkasan Strategi' untuk mendapatkan rekomendasi kampanye berdasarkan data yang difilter.")


# --- Dashboard Visualizations ---

col1, col2 = st.columns(2)

with col1:
    st.markdown("### 📊 Analisis Sentimen")
    if 'Sentiment' in df_filtered.columns and not df_filtered['Sentiment'].empty:
        sentiment_data = df_filtered['Sentiment'].value_counts().reset_index()
        sentiment_data.columns = ['Sentiment', 'Count']
        fig_sentiment = go.Figure(data=[go.Pie(
            labels=sentiment_data['Sentiment'],
            values=sentiment_data['Count'],
            hole=.3,
            marker_colors=COLORS,
            hoverinfo="label+percent",
            textinfo="percent",
            insidetextorientation="radial"
        )])
        fig_sentiment.update_layout(showlegend=True, height=350, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig_sentiment, use_container_width=True)
    else:
        st.warning("Kolom 'Sentiment' tidak ditemukan atau kosong. Analisis sentimen tidak tersedia.")

    st.markdown("### 📈 Tren Keterlibatan Seiring Waktu")
    if 'Date' in df_filtered.columns and 'Engagements' in df_filtered.columns and not df_filtered['Date'].empty and not df_filtered['Engagements'].empty:
        engagement_trend_data = df_filtered.groupby(df_filtered['Date'].dt.date)['Engagements'].sum().reset_index()
        engagement_trend_data.columns = ['Date', 'Engagements']
        engagement_trend_data = engagement_trend_data.sort_values('Date')
        if not engagement_trend_data.empty:
            fig_trend = px.line(engagement_trend_data, x='Date', y='Engagements',
                                labels={'Engagements': 'Total Keterlibatan', 'Date': 'Tanggal'},
                                color_discrete_sequence=["#FF6B6B"])
            fig_trend.update_layout(height=350, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.warning("Tidak ada data tren keterlibatan untuk ditampilkan.")
    else:
        st.warning("Kolom 'Date' atau 'Engagements' tidak ditemukan atau kosong. Tren keterlibatan tidak tersedia.")


with col2:
    st.markdown("### 📱 Keterlibatan per Platform")
    if 'Platform' in df_filtered.columns and 'Engagements' in df_filtered.columns and not df_filtered['Platform'].empty and not df_filtered['Engagements'].empty:
        platform_engagement_data = df_filtered.groupby('Platform')['Engagements'].sum().reset_index()
        platform_engagement_data.columns = ['Platform', 'Engagements']
        platform_engagement_data = platform_engagement_data.sort_values('Engagements', ascending=False)
        if not platform_engagement_data.empty:
            fig_platform = px.bar(platform_engagement_data, x='Engagements', y='Platform',
                                orientation='h',
                                labels={'Engagements': 'Total Keterlibatan', 'Platform': 'Platform'},
                                color='Platform',
                                color_discrete_sequence=COLORS)
            fig_platform.update_layout(height=350, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig_platform, use_container_width=True)
        else:
            st.warning("Tidak ada data keterlibatan platform untuk ditampilkan.")
    else:
        st.warning("Kolom 'Platform' atau 'Engagements' tidak ditemukan atau kosong. Keterlibatan per platform tidak tersedia.")

    st.markdown("### 📝 Kombinasi Jenis Media")
    if 'Media Type' in df_filtered.columns and not df_filtered['Media Type'].empty:
        media_type_data = df_filtered['Media Type'].value_counts().reset_index()
        media_type_data.columns = ['Media Type', 'Count']
        if not media_type_data.empty:
            fig_media_type = go.Figure(data=[go.Pie(
                labels=media_type_data['Media Type'],
                values=media_type_data['Count'],
                hole=.3,
                marker_colors=COLORS,
                hoverinfo="label+percent",
                textinfo="percent",
                insidetextorientation="radial"
            )])
            fig_media_type.update_layout(showlegend=True, height=350, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig_media_type, use_container_width=True)
        else:
            st.warning("Tidak ada data jenis media untuk ditampilkan.")
    else:
        st.warning("Kolom 'Media Type' tidak ditemukan atau kosong. Kombinasi jenis media tidak tersedia.")

st.markdown("### 📍 5 Lokasi Teratas")
if 'Location' in df_filtered.columns and 'Engagements' in df_filtered.columns and not df_filtered['Location'].empty and not df_filtered['Engagements'].empty:
    location_engagement_data = df_filtered.groupby('Location')['Engagements'].sum().reset_index()
    location_engagement_data.columns = ['Location', 'Engagements']
    location_engagement_data = location_engagement_data.sort_values('Engagements', ascending=True).tail(5) # Top 5, sorted ascending for horizontal bar chart
    if not location_engagement_data.empty:
        fig_location = px.bar(location_engagement_data, x='Engagements', y='Location',
                            orientation='h',
                            labels={'Engagements': 'Total Keterlibatan', 'Location': 'Lokasi'},
                            color='Location',
                            color_discrete_sequence=COLORS)
        fig_location.update_layout(height=400, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig_location, use_container_width=True)
    else:
        st.warning("Tidak ada data lokasi untuk ditampilkan.")
else:
    st.warning("Kolom 'Location' atau 'Engagements' tidak ditemukan atau kosong. 5 Lokasi Teratas tidak tersedia.")

st.sidebar.markdown("---")
st.sidebar.info(
    "💡 Untuk mengekspor dashboard sebagai PDF, gunakan fungsi 'Cetak' bawaan browser Anda (Ctrl+P atau Cmd+P)."
)



