import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import japanize_matplotlib
import matplotlib.ticker as ticker

# ページ設定
st.set_page_config(page_title="資産ライフプランシミュレーター", layout="wide")

st.title("📊 資産＆ライフプラン シミュレーター")

# ==========================================
# ▼ 基本設定パネル ▼
# ==========================================
with st.expander("▼ 基本設定（ここをタップして変更）", expanded=True):
    col_b1, col_b2 = st.columns(2)
    
    with col_b1:
        # 年齢：初期値 20歳
        current_age = st.number_input("現在の年齢", 18, 80, 20, key="input_current_age")
        # 資産：初期値 500万円
        current_assets = st.number_input("現在の資産 (万円)", 0, 50000, 500)
        inflation_rate_pct = st.slider("インフレ率 (%)", 0.0, 5.0, 2.0, 0.1)

    with col_b2:
        mean_return_pct = st.slider("想定利回り (年率%)", 0.0, 10.0, 5.0, 0.1)
        risk_std_pct = st.slider("リスク (標準偏差%)", 0.0, 30.0, 15.0, 0.5)

# %を小数に変換
mean_return = mean_return_pct / 100
risk_std = risk_std_pct / 100
inflation_rate = inflation_rate_pct / 100
real_mean_return = mean_return - inflation_rate

# ==========================================
# メイン画面レイアウト
# ==========================================
st.divider()
col1, col2 = st.columns(2)

# === 左側（スマホでは上）：ライフステージ入力 ===
with col1:
    st.subheader("1. ライフステージ収支 (年額)")
    st.info("💡 「終了年齢」を変えると期間が自動でつながります。")

    # 初期データを「100歳まで」に設定
    if "df_phases" not in st.session_state:
        st.session_state.df_phases = pd.DataFrame([
            {"開始年齢": 20, "終了年齢": 30, "収支(万円)": 100},
            {"開始年齢": 31, "終了年齢": 60, "収支(万円)": 400},
            {"開始年齢": 61, "終了年齢": 65, "収支(万円)": 100},
            {"開始年齢": 66, "終了年齢": 100, "収支(万円)": -300}, # ここを100歳に変更
        ])

    edited_phases = st.data_editor(
        st.session_state.df_phases,
        num_rows="dynamic",
        key="phases_editor",
        column_config={
            "開始年齢": st.column_config.NumberColumn(disabled=True, format="%d歳"),
            "終了年齢": st.column_config.NumberColumn(min_value=0, max_value=120, format="%d歳"),
            "収支(万円)": st.column_config.NumberColumn(format="%d万円")
        },
        use_container_width=True
    )

    # 自動修正ロジック
    needs_rerun = False
    temp_df = edited_phases.copy()
    next_start_age = current_age
    
    for i in range(len(temp_df)):
        if temp_df.at[i, "開始年齢"] != next_start_age:
            temp_df.at[i, "開始年齢"] = next_start_age
            needs_rerun = True
        
        end_age_val = temp_df.at[i, "終了年齢"]
        if pd.isna(end_age_val):
            break
        next_start_age = int(end_age_val) + 1

    if needs
