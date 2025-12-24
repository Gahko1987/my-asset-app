import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import japanize_matplotlib
import matplotlib.ticker as ticker

# ページ設定
st.set_page_config(page_title="資産ライフプランシミュレーター", layout="wide")
st.title("📊 資産＆ライフプラン シミュレーター")

# --- サイドバー：基本設定 ---
st.sidebar.header("基本設定")
# 年齢を変えたときに表も自動更新するため、キー(key)を指定
current_age = st.sidebar.number_input("現在の年齢", 20, 80, 39, key="input_current_age")
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

# --- メイン画面 ---

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. ライフステージ収支 (年額)")
    st.info("💡 「終了年齢」を変えると、次の「開始年齢」が自動でつながります。")

    # --- 自動計算ロジック付きテーブル ---
    
    # 1. 初回起動時にデフォルトデータを作る（session_stateに保存）
    if "df_phases" not in st.session_state:
        st.session_state.df_phases = pd.DataFrame([
            {"開始年齢": 39, "終了年齢": 42, "収支(万円)": 200},
            {"開始年齢": 43, "終了年齢": 60, "収支(万円)": 300},
            {"開始年齢": 61, "終了年齢": 65, "収支(万円)": 100},
            {"開始年齢": 66, "終了年齢": 95, "収支(万円)": -400},
        ])

    # 2. テーブルを表示（開始年齢は編集不可にする）
    edited_phases = st.data_editor(
        st.session_state.df_phases,
        num_rows="dynamic",
        key="phases_editor",
        column_config={
            "開始年齢": st.column_config.NumberColumn(disabled=True, format="%d歳"), # 編集不可
            "終了年齢": st.column_config.NumberColumn(min_value=0, max_value=120, format="%d歳"),
            "収支(万円)": st.column_config.NumberColumn(format="%d万円")
        },
        use_container_width=True
    )

    # 3. 自動修正ロジック（ここがポイント！）
    # ユーザーが「終了年齢」を変えたら、瞬時に「開始年齢」を再計算して画面を更新する
    needs_rerun = False
    temp_df = edited_phases.copy()
    
    # 現在の年齢からスタート
    next_start_age = current_age
    
    # 上から順に「開始年齢」を正しい値に書き換えていく
    for i in range(len(temp_df)):
        # もし開始年齢がズレていたら修正
        if temp_df.at[i, "開始年齢"] != next_start_age:
            temp_df.at[i, "開始年齢"] = next_start_age
            needs_rerun = True
        
        # 次の行のスタート年齢を計算（終了年齢 + 1）
        end_age_val = temp_df.at[i, "終了年齢"]
        if pd.isna(end_age_val): # 入力中は計算しない
            break
        next_start_age = int(end_age_val) + 1

    # 修正が必要な場合、データを保存して再読み込み
    if needs_rerun:
        st.session_state.df_phases = temp_df
        st.rerun()

with col2:
    st.subheader("2. イベント・一時金")
    st.caption("退職金(プラス)や大きな買い物(マイナス)")
    
    default_events = [
        {"年齢": 55, "金額(万円)": 1000, "内容": "退職金"},
        {"年齢": 43, "金額(万円)": -300, "内容": "車の購入"},
    ]
    df_events = pd.DataFrame(default_events)
    edited_events = st.data_editor(df_events, num_rows="dynamic")

# --- シミュレーション実行 ---
if st.button("シミュレーションを実行する", type="primary"):
    try:
        # 計算用データの準備
        # 自動修正済みのデータ(temp_df)を使うので、整合性は完璧です
        phases_data = st.session_state.df_phases.copy()
        
        # 最終年齢の決定
        if phases_data.empty:
             end_age = 100
        else:
             end_age = int(phases_data["終了年齢"].max())

        years = end_age - current_age
        simulation_results = np.zeros((num_simulations, years + 1))
        
        # 収支マップの作成
        cashflow_map = {}
        for index, row in phases_data.iterrows():
            if pd.isna(row["開始年齢"]) or pd.isna(row["終了年齢"]) or pd.isna(row["収支(万円)"]):
                continue
            start, end, amount = int(row["開始年齢"]), int(row["終了年齢"]), row["収支(万円)"]
            for age in range(start, end + 1):
                cashflow_map[age] = amount

        # イベントマップの作成
        event_map = {}
        for index, row in edited_events.iterrows():
            if pd.isna(row["年齢"]) or pd.isna(row["金額(万円)"]):
                continue
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

        st.divider()
        res_col1, res_col2, res_col3 = st.columns(3)
        res_col1.metric("95歳時点の生存率", f"{100 - ruin_prob:.1f}%")
        res_col2.metric("最終資産 (中央値)", f"{int(median_res[-1]):,} 万円")
        res_col3.metric("最終資産 (不調時)", f"{int(bottom_10_res[-1]):,} 万円")

        fig, ax = plt.subplots(figsize=(10, 6))
        age_axis = np.arange(current_age, end_age + 1)
        
        # 老後エリア（マイナス収支の期間）を色付け
        # 単純に「収支がマイナス設定されている期間」を塗るロジックに変更
        for index, row in phases_data.iterrows():
            if row["収支(万円)"] < 0:
                ax.axvspan(row["開始年齢"], row["終了年齢"], color='orange', alpha=0.1)

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

    except Exception as e:
        st.error(f"エラーが発生しました: {e}")
