import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# ページ設定
st.set_page_config(page_title="資産ライフプランシミュレーター", layout="wide")
st.title("📊 資産＆ライフプラン シミュレーター")

# --- サイドバー：基本設定 ---
st.sidebar.header("基本設定")
current_age = st.sidebar.number_input("現在の年齢", 20, 80, 39)
current_assets = st.sidebar.number_input("現在の資産 (万円)", 0, 50000, 2300)
mean_return_pct = st.sidebar.slider("想定利回り (年率%)", 0.0, 10.0, 5.0, 0.1)
risk_std_pct = st.sidebar.slider("リスク (標準偏差%)", 0.0, 30.0, 15.0, 0.5)
inflation_rate_pct = st.sidebar.slider("インフレ率 (%)", 0.0, 5.0, 2.0, 0.1)
num_simulations = 1000

# %を小数に変換
mean_return = mean_return_pct / 100
risk_std = risk_std_pct / 100
inflation_rate = inflation_rate_pct / 100
real_mean_return = mean_return - inflation_rate

# --- メイン画面：詳細設定 ---

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. ライフステージ収支 (年額)")
    st.caption("年齢ごとの積立額（プラス）や取り崩し額（マイナス）を設定")
    
    # 初期データ
    default_phases = [
        {"開始年齢": 39, "終了年齢": 42, "収支(万円)": 900},
        {"開始年齢": 43, "終了年齢": 60, "収支(万円)": 400},
        {"開始年齢": 61, "終了年齢": 65, "収支(万円)": 100},
        {"開始年齢": 66, "終了年齢": 95, "収支(万円)": -300},
    ]
    df_phases = pd.DataFrame(default_phases)
    edited_phases = st.data_editor(df_phases, num_rows="dynamic")

with col2:
    st.subheader("2. イベント・一時金")
    st.caption("退職金(プラス)や大きな買い物(マイナス)")
    
    # 初期データ
    default_events = [
        {"年齢": 60, "金額(万円)": 2000, "内容": "退職金"},
        {"年齢": 55, "金額(万円)": -300, "内容": "車の購入"},
    ]
    df_events = pd.DataFrame(default_events)
    edited_events = st.data_editor(df_events, num_rows="dynamic")

# --- シミュレーション実行 ---
if st.button("シミュレーションを実行する", type="primary"):
    
    # データの準備
    life_phases = edited_phases.values.tolist()
    spot_events = df_events.values.tolist()
    
    # 計算ロジック（前回のコードと同じロジック）
    end_age = int(edited_phases["終了年齢"].max())
    years = end_age - current_age
    simulation_results = np.zeros((num_simulations, years + 1))
    
    cashflow_map = {}
    for index, row in edited_phases.iterrows():
        start, end, amount = int(row["開始年齢"]), int(row["終了年齢"]), row["収支(万円)"]
        for age in range(start, end + 1):
            cashflow_map[age] = amount

    event_map = {}
    for index, row in edited_events.iterrows():
        age, amount = int(row["年齢"]), row["金額(万円)"]
        event_map[age] = event_map.get(age, 0) + amount

    # モンテカルロ計算
    for i in range(num_simulations):
        assets = [current_assets]
        for year in range(years):
            age = current_age + year
            annual_flow = cashflow_map.get(age, 0)
            spot_flow = event_map.get(age, 0)
            market_return = np.random.normal(real_mean_return, risk_std)
            
            prev_asset = assets[-1]
            if prev_asset <= 0:
                new_value = 0
            else:
                total_principal = prev_asset + annual_flow + spot_flow
                new_value = total_principal * (1 + market_return)
                if new_value < 0: new_value = 0
            assets.append(new_value)
        simulation_results[i, :] = assets

    # --- 結果表示 ---
    median_res = np.percentile(simulation_results, 50, axis=0)
    top_10_res = np.percentile(simulation_results, 90, axis=0)
    bottom_10_res = np.percentile(simulation_results, 10, axis=0)
    ruin_prob = (np.sum(simulation_results[:, -1] == 0) / num_simulations) * 100

    # 結果サマリ
    st.divider()
    res_col1, res_col2, res_col3 = st.columns(3)
    res_col1.metric("95歳時点の生存率", f"{100 - ruin_prob:.1f}%")
    res_col2.metric("最終資産 (中央値)", f"{int(median_res[-1]):,} 万円")
    res_col3.metric("最終資産 (不調時)", f"{int(bottom_10_res[-1]):,} 万円")

    # グラフ描画
    fig, ax = plt.subplots(figsize=(10, 6))
    age_axis = np.arange(current_age, end_age + 1)
    
    # 老後エリア
    retirement_start = 66
    if retirement_start <= end_age:
        ax.axvspan(retirement_start, end_age, color='orange', alpha=0.1, label='老後期間')

    ax.plot(age_axis, median_res, color='blue', linewidth=3, label='中央値')
    ax.plot(age_axis, top_10_res, color='green', linestyle='--', label='好調 (上位10%)')
    ax.plot(age_axis, bottom_10_res, color='red', linestyle='--', label='不調 (下位10%)')
    
    ax.set_title(f"資産推移シミュレーション ({num_simulations}回試行)", fontsize=14)
    ax.set_xlabel("年齢")
    ax.set_ylabel("資産額 (万円)")
    ax.legend()
    ax.grid(True, linestyle='--', alpha=0.7)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: f'{int(x):,}'))
    
    st.pyplot(fig)
