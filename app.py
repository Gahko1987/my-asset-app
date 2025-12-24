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
            {"開始年齢": 66, "終了年齢": 100, "収支(万円)": -300},
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

    if needs_rerun:
        st.session_state.df_phases = temp_df
        st.rerun()

# === 右側（スマホでは下）：イベント入力 ===
with col2:
    st.subheader("2. イベント・一時金")
    st.caption("退職金(プラス)や大きな買い物(マイナス)")
    
    default_events = [
        {"年齢": 60, "金額(万円)": 2000, "内容": "退職金"},
        {"年齢": 30, "金額(万円)": -500, "内容": "結婚・住宅頭金など"},
    ]
    if "df_events_init" not in st.session_state:
        st.session_state.df_events_init = pd.DataFrame(default_events)

    edited_events = st.data_editor(
        st.session_state.df_events_init,
        num_rows="dynamic",
        use_container_width=True
    )

# --- シミュレーション実行ボタン ---
st.divider()
if st.button("シミュレーションを実行する (10,000回)", type="primary"):
    
    try:
        # データ整理
        phases_data = st.session_state.df_phases.copy()
        if phases_data.empty:
             end_age = 100
        else:
             valid_phases = phases_data.dropna(subset=["終了年齢"])
             if valid_phases.empty:
                 end_age = 100
             else:
                 end_age = int(valid_phases["終了年齢"].max())

        years = end_age - current_age
        
        # 10,000回シミュレーション
        num_simulations = 10000 
        
        cashflow_map = {}
        for index, row in phases_data.iterrows():
            if pd.isna(row["開始年齢"]) or pd.isna(row["終了年齢"]) or pd.isna(row["収支(万円)"]):
                continue
            start, end, amount = int(row["開始年齢"]), int(row["終了年齢"]), row["収支(万円)"]
            for age in range(start, end + 1):
                cashflow_map[age] = amount

        event_map = {}
        for index, row in edited_events.iterrows():
            if pd.isna(row["年齢"]) or pd.isna(row["金額(万円)"]):
                continue
            try:
                age = int(row["年齢"])
                amount = int(row["金額(万円)"])
                event_map[age] = event_map.get(age, 0) + amount
            except:
                continue

        # --- A. 単純計算 ---
        deterministic_assets = [current_assets]
        for year in range(years):
            age = current_age + year
            annual_flow = cashflow_map.get(age, 0)
            spot_flow = event_map.get(age, 0)
            
            prev_asset = deterministic_assets[-1]
            if prev_asset <= 0:
                new_value = 0
            else:
                total_principal = prev_asset + annual_flow + spot_flow
                new_value = total_principal * (1 + real_mean_return)
                if new_value < 0: new_value = 0
            deterministic_assets.append(new_value)

        # --- B. モンテカルロ ---
        simulation_results = np.zeros((num_simulations, years + 1))
        
        # 進捗バーを表示
        progress_bar = st.progress(0)
        
        for i in range(num_simulations):
            assets = [current_assets]
            
            # 100回ごとにバーを進める
            if i % 100 == 0:
                progress_bar.progress(i / num_simulations)
                
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
            
        progress_bar.progress(1.0) # 完了

        # 結果表示
        median_res = np.percentile(simulation_results, 50, axis=0)
        top_10_res = np.percentile(simulation_results, 90, axis=0)
        bottom_10_res = np.percentile(simulation_results, 10, axis=0)
        ruin_prob = (np.sum(simulation_results[:, -1] == 0) / num_simulations) * 100

        st.subheader(f"シミュレーション結果 ({end_age}歳まで / {num_simulations}回試行)")
        res_col1, res_col2, res_col3, res_col4 = st.columns(4)
        res_col1.metric(f"{end_age}歳生存率", f"{100 - ruin_prob:.1f}%")
        res_col2.metric("単純計算", f"{int(deterministic_assets[-1]):,}万")
        res_col3.metric("中央値", f"{int(median_res[-1]):,}万")
        res_col4.metric("不調時", f"{int(bottom_10_res[-1]):,}万")

        fig, ax = plt.subplots(figsize=(10, 6))
        age_axis = np.arange(current_age, end_age + 1)
        
        for index, row in phases_data.iterrows():
            if not pd.isna(row["収支(万円)"]) and row["収支(万円)"] < 0:
                ax.axvspan(row["開始年齢"], row["終了年齢"], color='orange', alpha=0.1)

        ax.plot(age_axis, deterministic_assets, color='orange', linewidth=3, linestyle=':', label='単純計算')
        ax.plot(age_axis, median_res, color='blue', linewidth=2, label='中央値')
        ax.plot(age_axis, top_10_res, color='green', linestyle='--', linewidth=1, label='好調')
        ax.plot(age_axis, bottom_10_res, color='red', linestyle='--', linewidth=1, label='不調')
        
        ax.set_title("資産推移", fontsize=14)
        ax.set_xlabel("年齢")
        ax.set_ylabel("資産額 (万円)")
        ax.legend()
        ax.grid(True, linestyle='--', alpha=0.7)
        ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: f'{int(x):,}'))
        
        st.pyplot(fig)

    except Exception as e:
        st.error(f"エラー: {e}")
