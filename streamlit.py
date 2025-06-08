import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import json
from io import StringIO

# Kunci API untuk Gemini (ganti dengan kunci API Anda yang sebenarnya)
# Dalam aplikasi nyata, ini harus ditangani dengan aman, mis. rahasia Streamlit
API_KEY = "AIzaSyC0VUu6xTFIwH3aP2R7tbhyu4O8m1ICxn4"

# Konfigurasi halaman
st.set_page_config(
    page_title="Dashboard Intelijen Media Interaktif",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Fungsi Pembantu ---

# Fungsi untuk mengurai data CSV
@st.cache_data
def parse_csv(data):
    # Gunakan StringIO untuk memperlakukan string sebagai file
    df = pd.read_csv(StringIO(data))
    return df

# Pembersihan dan Transformasi Data
@st.cache_data
def clean_and_process_data(df, drop_nan=True):
    initial_row_count = df.shape[0]

    # Konversi kolom 'Date' ke datetime, paksa kesalahan menjadi NaT (Not a Time)
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        # Filter baris di mana Date adalah NaT
        df = df.dropna(subset=['Date'])
    else:
        st.warning("Kolom 'Date' tidak ditemukan. Beberapa fitur mungkin tidak berfungsi dengan baik.")

    # Konversi 'Engagements' ke numerik, paksa kesalahan menjadi NaN
    if 'Engagements' in df.columns:
        df['Engagements'] = pd.to_numeric(df['Engagements'], errors='coerce').fillna(0).astype(int)
    else:
        st.warning("Kolom 'Engagements' tidak ditemukan. Metrik keterlibatan tidak akan tersedia.")
        df['Engagements'] = 0 # Tambahkan default jika tidak ada

    # Hapus baris dengan nilai NaN apa pun jika drop_nan benar
    if drop_nan:
        df_cleaned = df.dropna()
    else:
        df_cleaned = df

    rows_removed = initial_row_count - df_cleaned.shape[0]
    return df_cleaned, rows_removed

# Fungsi untuk mengonversi tebal seperti Markdown (**teks**) menjadi kuat HTML (<strong>teks</strong>)
def format_markdown_bold(text):
    # Menggunakan regex untuk menemukan **teks** dan menggantinya dengan <strong>teks</strong>
    return text.replace('**', '<strong>', 1).replace('**', '</strong>', 1)

# --- Integrasi LLM untuk Ringkasan Kampanye ---
def generate_summary(filtered_data, persona):
    if filtered_data.empty:
        return "Tidak ada data yang difilter untuk membuat ringkasan."

    # Siapkan data agregat untuk prompt LLM
    sentiment_counts = filtered_data['Sentiment'].value_counts().to_dict() if 'Sentiment' in filtered_data.columns else {}
    dominant_sentiment = max(sentiment_counts, key=sentiment_counts.get) if sentiment_counts else 'N/A'

    platform_engagements = filtered_data.groupby('Platform')['Engagements'].sum().sort_values(ascending=False).to_dict() if 'Platform' in filtered_data.columns and 'Engagements' in filtered_data.columns else {}
    top_platform = next(iter(platform_engagements)) if platform_engagements else 'N/A'
    top_platform_engagements = platform_engagements.get(top_platform, 0)

    overall_trend = 'stabil'
    if 'Date' in filtered_data.columns and 'Engagements' in filtered_data.columns:
        engagement_trend_data = filtered_data.groupby(filtered_data['Date'].dt.date)['Engagements'].sum().sort_index()
        if len(engagement_trend_data) > 1:
            first_engagement = engagement_trend_data.iloc[0]
            last_engagement = engagement_trend_data.iloc[-1]
            if last_engagement > first_engagement * 1.1:
                overall_trend = 'meningkat'
            elif last_engagement < first_engagement * 0.9:
                overall_trend = 'menurun'
        start_date_llm = engagement_trend_data.index.min().strftime('%Y-%m-%d') if not engagement_trend_data.empty else 'N/A'
        end_date_llm = engagement_trend_data.index.max().strftime('%Y-%m-%d') if not engagement_trend_data.empty else 'N/A'
    else:
        start_date_llm = 'N/A'
        end_date_llm = 'N/A'


    media_type_counts = filtered_data['Media Type'].value_counts().to_dict() if 'Media Type' in filtered_data.columns else {}
    dominant_media_type = max(media_type_counts, key=media_type_counts.get) if media_type_counts else 'N/A'

    location_engagements = filtered_data.groupby('Location')['Engagements'].sum().sort_values(ascending=False).to_dict() if 'Location' in filtered_data.columns and 'Engagements' in filtered_data.columns else {}
    top_location = next(iter(location_engagements)) if location_engagements else 'N/A'
    top_location_engagements = location_engagements.get(top_location, 0)

    persona_prefix = ""
    if persona == "consultant":
        persona_prefix = "Sebagai seorang konsultan ahli yang menyajikan laporan kepada klien penting, berikan ringkasan ini. Fokus pada rekomendasi strategis dan wawasan yang dapat ditindaklanjuti, dengan bahasa yang formal, berorientasi pada hasil, dan profesional.\n\n"
    else:  # professional (default)
        persona_prefix = "Sebagai seorang profesional internal, berikan ringkasan ini. Fokus pada tindakan langsung, wawasan operasional, dan bahasa yang ringkas.\n\n"

    prompt = persona_prefix + f"""Berdasarkan data intelijen media dan wawasan berikut, berikan ringkasan strategi kampanye yang ringkas (tindakan dan rekomendasi utama).
- Sentimen Dominan: {dominant_sentiment}.
- Platform Keterlibatan Teratas: {top_platform} dengan {top_platform_engagements} keterlibatan.
- Tren Keterlibatan Keseluruhan: {overall_trend} dari {start_date_llm} hingga {end_date_llm}.
- Jenis Media yang Paling Sering Digunakan: {dominant_media_type}.
- Lokasi Teratas untuk Keterlibatan: {top_location} dengan {top_location_engagements} keterlibatan.
Sarankan 3-5 rekomendasi yang dapat ditindaklanjuti untuk mengoptimalkan kampanye media. Fokus pada langkah-langkah yang dapat ditindaklanjuti berdasarkan poin data ini."""

    headers = {'Content-Type': 'application/json'}
    payload = {'contents': [{'role': 'user', 'parts': [{'text': prompt}]}]}
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}"

    try:
        response = requests.post(api_url, headers=headers, data=json.dumps(payload))
        response.raise_for_status() # Menimbulkan pengecualian untuk kesalahan HTTP
        result = response.json()
        if result and 'candidates' in result and len(result['candidates']) > 0 and \
           'content' in result['candidates'][0] and 'parts' in result['candidates'][0]['content'] and \
           len(result['candidates'][0]['content']['parts']) > 0:
            text = result['candidates'][0]['content']['parts'][0]['text']
            return text
        else:
            return 'Gagal membuat ringkasan. Struktur respons Gemini API tidak terduga.'
    except requests.exceptions.RequestException as e:
        st.error(f"Error memanggil Gemini API: {e}")
        return f'Error membuat ringkasan: {e}'
    except json.JSONDecodeError as e:
        st.error(f"Error mengurai respons JSON dari Gemini API: {e}")
        return f'Error mengurai respons Gemini API: {e}'

# --- Tata Letak Dasbor ---

st.title("Dashboard Intelijen Media Interaktif")

# Bagian Unggah File
uploaded_file = st.file_uploader("Unggah File CSV Anda", type=["csv"],
                                 help="Pastikan memiliki kolom untuk 'Date', 'Engagements', 'Sentiment', 'Platform', 'Media Type', dan 'Location'.")

if uploaded_file is not None:
    # Baca CSV
    csv_text = uploaded_file.getvalue().decode("utf-8")
    original_df = parse_csv(csv_text)

    # Opsi Pembersihan Data
    st.sidebar.header("Pembersihan Data")
    drop_nan = st.sidebar.checkbox("Hapus baris dengan nilai yang hilang (NaN)", value=True)
    
    cleaned_df, rows_removed = clean_and_process_data(original_df.copy(), drop_nan)

    if cleaned_df.empty:
        st.error("File CSV kosong atau tidak valid setelah pembersihan. Silakan unggah file lain.")
    else:
        st.success(f"File CSV berhasil diunggah dengan {cleaned_df.shape[0]} baris. ({rows_removed} baris dihapus selama pembersihan awal).")
        st.sidebar.write(f"File saat ini: {uploaded_file.name}")

        # --- Bagian Filter (Sidebar) ---
        st.sidebar.header("Filter Data")

        # Dapatkan nilai unik untuk filter
        platforms = ['All'] + sorted(cleaned_df['Platform'].unique().tolist()) if 'Platform' in cleaned_df.columns else ['All']
        sentiments = ['All'] + sorted(cleaned_df['Sentiment'].unique().tolist()) if 'Sentiment' in cleaned_df.columns else ['All']
        media_types = ['All'] + sorted(cleaned_df['Media Type'].unique().tolist()) if 'Media Type' in cleaned_df.columns else ['All']
        locations = ['All'] + sorted(cleaned_df['Location'].unique().tolist()) if 'Location' in cleaned_df.columns else ['All']

        selected_platform = st.sidebar.selectbox("Platform", platforms)
        selected_sentiment = st.sidebar.selectbox("Sentiment", sentiments)
        selected_media_type = st.sidebar.selectbox("Jenis Media", media_types)
        selected_location = st.sidebar.selectbox("Lokasi", locations)

        # Filter Rentang Tanggal
        min_date = cleaned_df['Date'].min() if 'Date' in cleaned_df.columns and not cleaned_df['Date'].empty else None
        max_date = cleaned_df['Date'].max() if 'Date' in cleaned_df.columns and not cleaned_df['Date'].empty else None
        
        # Ensure min_date and max_date are actual date objects for st.date_input
        if min_date and pd.isna(min_date): min_date = None
        if max_date and pd.isna(max_date): max_date = None

        col_start_date, col_end_date = st.sidebar.columns(2)
        with col_start_date:
            start_date = st.date_input("Tanggal Mulai", value=min_date, min_value=min_date, max_value=max_date) if min_date else None
        with col_end_date:
            end_date = st.date_input("Tanggal Akhir", value=max_date, min_value=min_date, max_value=max_date) if max_date else None

        # Terapkan filter
        filtered_df = cleaned_df.copy()
        if selected_platform != 'All':
            filtered_df = filtered_df[filtered_df['Platform'] == selected_platform]
        if selected_sentiment != 'All':
            filtered_df = filtered_df[filtered_df['Sentiment'] == selected_sentiment]
        if selected_media_type != 'All':
            filtered_df = filtered_df[filtered_df['Media Type'] == selected_media_type]
        if selected_location != 'All':
            filtered_df = filtered_df[filtered_df['Location'] == selected_location]

        if 'Date' in filtered_df.columns and start_date and end_date:
            filtered_df = filtered_df[(filtered_df['Date'] >= pd.to_datetime(start_date)) & (filtered_df['Date'] <= pd.to_datetime(end_date))]

        # --- Konten Dasbor ---

        st.subheader("Ringkasan Strategi Kampanye")
        summary_persona = st.selectbox("Pilih Perspektif Ringkasan:", ["professional", "consultant"],
                                       format_func=lambda x: "Sebagai Profesional" if x == "professional" else "Sebagai Konsultan")

        if st.button("Buat Ringkasan Strategi"):
            with st.spinner("Membuat ringkasan..."):
                summary_text = generate_summary(filtered_df, summary_persona)
                # Gunakan st.markdown dengan unsafe_allow_html=True untuk merender tag kuat HTML
                st.markdown(format_markdown_bold(summary_text), unsafe_allow_html=True)
        else:
            st.write("Klik 'Buat Ringkasan Strategi' untuk mendapatkan rekomendasi kampanye berdasarkan data yang difilter.")

        st.markdown("---") # Pemisah

        st.subheader("Analisis Data")

        # Grafik 1: Perincian Sentimen
        st.markdown("### Analisis Sentimen")
        if 'Sentiment' in filtered_df.columns and not filtered_df.empty:
            sentiment_counts = filtered_df['Sentiment'].value_counts().reset_index()
            sentiment_counts.columns = ['Sentiment', 'Count']
            fig_sentiment = px.pie(sentiment_counts, values='Count', names='Sentiment',
                                   title='Distribusi Sentimen', hole=0.3,
                                   color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_sentiment, use_container_width=True)
            
            # Wawasan
            insights = []
            if not sentiment_counts.empty:
                dominant_sentiment = sentiment_counts.loc[sentiment_counts['Count'].idxmax()]
                insights.append(f"Sentimen dominan adalah **{dominant_sentiment['Sentiment']}** dengan **{dominant_sentiment['Count']}** entri, menunjukkan persepsi yang umumnya {dominant_sentiment['Sentiment'].lower()}.")
                if len(sentiment_counts) > 1:
                    least_sentiment = sentiment_counts.counts = sentiment_counts.loc[sentiment_counts['Count'].idxmin()]
                    insights.append(f"**{least_sentiment['Sentiment']}** mewakili bagian terkecil dengan **{least_sentiment['Count']}** entri.")
            st.markdown("#### Wawasan Utama:")
            for insight in insights:
                st.markdown(f"- {format_markdown_bold(insight)}", unsafe_allow_html=True)
            if not insights:
                st.markdown("- Tidak ada data sentimen untuk ditampilkan.")
        else:
            st.markdown("Tidak ada data sentimen untuk ditampilkan.")
            st.markdown("#### Wawasan Utama:")
            st.markdown("- Tidak ada data sentimen untuk ditampilkan.")
        st.markdown("---")

        # Grafik 2: Tren Keterlibatan Seiring Waktu
        st.markdown("### Tren Keterlibatan Seiring Waktu")
        if 'Date' in filtered_df.columns and 'Engagements' in filtered_df.columns and not filtered_df.empty:
            # Memastikan kolom 'Date' adalah datetime dan mengurutkannya
            df_for_trend = filtered_df.set_index('Date').resample('D')['Engagements'].sum().reset_index()
            df_for_trend.columns = ['Date', 'Total Engagements']
            df_for_trend = df_for_trend.sort_values('Date') # Pastikan data diurutkan berdasarkan tanggal

            fig_trend = px.line(df_for_trend, x='Date', y='Total Engagements',
                                title='Tren Keterlibatan Harian',
                                line_shape='spline', markers=True)
            st.plotly_chart(fig_trend, use_container_width=True)
            
            # Wawasan
            insights = []
            if not df_for_trend.empty:
                peak_engagement = df_for_trend.loc[df_for_trend['Total Engagements'].idxmax()]
                insights.append(f"Keterlibatan mencapai puncaknya sekitar **{peak_engagement['Date'].strftime('%Y-%m-%d')}** dengan **{peak_engagement['Total Engagements']}** keterlibatan.")
                
                if len(df_for_trend) > 1:
                    first_val = df_for_trend['Total Engagements'].iloc[0]
                    last_val = df_for_trend['Total Engagements'].iloc[-1]
                    overall_trend = 'stabil'
                    if last_val > first_val * 1.1: overall_trend = 'meningkat'
                    elif last_val < first_val * 0.9: overall_trend = 'menurun'
                    insights.append(f"Tren keseluruhan menunjukkan keterlibatan yang **{overall_trend}** selama periode yang dipilih.")
            st.markdown("#### Wawasan Utama:")
            for insight in insights:
                st.markdown(f"- {format_markdown_bold(insight)}", unsafe_allow_html=True)
            if not insights:
                st.markdown("- Tidak ada data tren keterlibatan untuk ditampilkan.")
        else:
            st.markdown("Tidak ada data tren keterlibatan untuk ditampilkan.")
            st.markdown("#### Wawasan Utama:")
            st.markdown("- Tidak ada data tren keterlibatan untuk ditampilkan.")
        st.markdown("---")


        # Grafik 3: Keterlibatan per Platform
        st.markdown("### Keterlibatan per Platform")
        if 'Platform' in filtered_df.columns and 'Engagements' in filtered_df.columns and not filtered_df.empty:
            platform_engagements = filtered_df.groupby('Platform')['Engagements'].sum().reset_index()
            platform_engagements.columns = ['Platform', 'Total Engagements']
            platform_engagements = platform_engagements.sort_values('Total Engagements', ascending=True) # Untuk grafik batang horizontal
            fig_platform = px.bar(platform_engagements, x='Total Engagements', y='Platform',
                                  title='Total Keterlibatan per Platform', orientation='h',
                                  color_discrete_sequence=px.colors.qualitative.Set2)
            st.plotly_chart(fig_platform, use_container_width=True)

            # Wawasan
            insights = []
            if not platform_engagements.empty:
                top_platform = platform_engagements.loc[platform_engagements['Total Engagements'].idxmax()]
                insights.append(f"**{top_platform['Platform']}** secara konsisten mendorong keterlibatan tertinggi dengan total **{top_platform['Total Engagements']}**.")
                if len(platform_engagements) > 1:
                    lowest_platform = platform_engagements.loc[platform_engagements['Total Engagements'].idxmin()]
                    insights.append(f"Platform seperti **{lowest_platform['Platform']}** menunjukkan keterlibatan yang lebih rendah.")
            st.markdown("#### Wawasan Utama:")
            for insight in insights:
                st.markdown(f"- {format_markdown_bold(insight)}", unsafe_allow_html=True)
            if not insights:
                st.markdown("- Tidak ada data keterlibatan platform untuk ditampilkan.")
        else:
            st.markdown("Tidak ada data keterlibatan platform untuk ditampilkan.")
            st.markdown("#### Wawasan Utama:")
            st.markdown("- Tidak ada data keterlibatan platform untuk ditampilkan.")
        st.markdown("---")

        # Grafik 4: Kombinasi Jenis Media
        st.markdown("### Kombinasi Jenis Media")
        if 'Media Type' in filtered_df.columns and not filtered_df.empty:
            media_type_counts = filtered_df['Media Type'].value_counts().reset_index()
            media_type_counts.columns = ['Media Type', 'Count']
            fig_media_type = px.pie(media_type_counts, values='Count', names='Media Type',
                                    title='Distribusi Jenis Media', hole=0.3,
                                    color_discrete_sequence=px.colors.qualitative.Set3)
            st.plotly_chart(fig_media_type, use_container_width=True)

            # Wawasan
            insights = []
            if not media_type_counts.empty:
                dominant_media_type = media_type_counts.loc[media_type_counts['Count'].idxmax()]
                insights.append(f"**{dominant_media_type['Media Type']}** adalah jenis media yang paling sering digunakan dengan **{dominant_media_type['Count']}** entri.")
                if len(media_type_counts) > 1:
                    least_common_media = media_type_counts.loc[media_type_counts['Count'].idxmin()]
                    insights.append(f"**{least_common_media['Media Type']}** kurang umum, mungkin menjadi area untuk eksplorasi.")
            st.markdown("#### Wawasan Utama:")
            for insight in insights:
                st.markdown(f"- {format_markdown_bold(insight)}", unsafe_allow_html=True)
            if not insights:
                st.markdown("- Tidak ada data jenis media untuk ditampilkan.")
        else:
            st.markdown("Tidak ada data jenis media untuk ditampilkan.")
            st.markdown("#### Wawasan Utama:")
            st.markdown("- Tidak ada data jenis media untuk ditampilkan.")
        st.markdown("---")


        # Grafik 5: 5 Lokasi Teratas
        st.markdown("### 5 Lokasi Teratas")
        if 'Location' in filtered_df.columns and 'Engagements' in filtered_df.columns and not filtered_df.empty:
            location_engagements = filtered_df.groupby('Location')['Engagements'].sum().nlargest(5).reset_index()
            location_engagements.columns = ['Location', 'Total Engagements']
            location_engagements = location_engagements.sort_values('Total Engagements', ascending=True) # Untuk grafik batang horizontal
            fig_location = px.bar(location_engagements, x='Total Engagements', y='Location',
                                  title='5 Lokasi Teratas berdasarkan Keterlibatan', orientation='h',
                                  color_discrete_sequence=px.colors.qualitative.D3)
            st.plotly_chart(fig_location, use_container_width=True)
            
            # Wawasan
            insights = []
            if not location_engagements.empty:
                top_location = location_engagements.loc[location_engagements['Total Engagements'].idxmax()]
                insights.append(f"**{top_location['Location']}** adalah area geografis utama untuk keterlibatan dengan total **{top_location['Total Engagements']}** keterlibatan.")
            st.markdown("#### Wawasan Utama:")
            for insight in insights:
                st.markdown(f"- {format_markdown_bold(insight)}", unsafe_allow_html=True)
            if not insights:
                st.markdown("- Tidak ada data lokasi untuk ditampilkan.")
        else:
            st.markdown("Tidak ada data lokasi untuk ditampilkan.")
            st.markdown("#### Wawasan Utama:")
            st.markdown("- Tidak ada data lokasi untuk ditampilkan.")
        st.markdown("---")

        st.markdown("""
            ---
            **Ekspor ke PDF:** Untuk mengekspor seluruh dashboard ke PDF, silakan gunakan fungsi "Cetak" atau "Simpan sebagai PDF" dari browser Anda (Ctrl+P atau Cmd+P).
            """)

else:
    st.info("Silakan unggah file CSV untuk memulai.")

