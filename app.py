import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import japanize_matplotlib
import matplotlib.ticker as ticker

# ページ設定（必ず一番上に書く）
st.set_page_config(page_title="資産ライフプランシミュレーター", layout="wide")

st.title("📊 資産＆ライフプラン シミュレーター")

# --- サイドバー：基本設定 ---
st.sidebar.header("基本設定")
# 年齢入力（変更時に再計算するためキーを設定）
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

# --- メイン画面レイアウト ---
col1, col2 = st.columns(2)

# === 左側：ライフステージ入力 ===
with col1:
    st.subheader("1. ライフステージ収支 (年額)")
    st.info("💡 「終了年齢」を変えると、次の「開始年齢」が自動でつながります。")

    # セッション状態にデータを保存（画面更新で消えないようにする）
    if "df_phases" not in st.session_state:
        st.session_state.df_phases = pd.DataFrame([
            {"開始年齢": 39, "終了年齢": 42, "収支(万円)": 900},
            {"開始年齢": 43, "終了年齢": 60, "収支(万円)": 400},
            {"開始年齢": 61, "終了年齢": 65, "収支(万円)": 100},
            {"開始年齢": 66, "終了年齢": 95, "収支(万円)": -300},
        ])

    # データ編集テーブル
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

    # --- 自動修正ロジック ---
    needs_rerun = False
    temp_df = edited_phases.copy()
    next_start_age = current_age
    
    # 上から順にチェックして、開始年齢のズレを修正
    for i in range(len(temp_df)):
        # 開始年齢を強制的に修正
        if temp_df.at[i, "開始年齢"] != next_start_age:
            temp_df.at[i, "開始年齢"] = next_start_age
            needs_rerun = True
        
        # 次の行の開始年齢を計算
        end_age_val = temp_df.at[i, "終了年齢"]
        if pd.isna(end_age_val): # 空欄ならそこで計算ストップ
            break
        next_start_age = int(end_age_val) + 1

    # 修正があった場合、データを保存して再読み込み
    if needs_rerun:
        st.session_state.df_phases = temp_df
        st.rerun()

# === 右側：イベント入力 ===
with col2:
    st.subheader("2. イベント・一時金")
    st.caption("退職金(プラス)や大きな買い物(マイナス)")
    
    default_events = [
        {"年齢": 60, "金額(万円)": 2000, "内容": "退職金"},
        {"年齢": 55, "金額(万円)": -300, "内容": "車の購入"},
    ]
    # 初期化用
    if "df_events_init" not in st.session_state:
        st.session_state.df_events_init = pd.DataFrame(default_events)

    edited_events = st.data_editor(
        st.session_state.df_events_init,
        num_rows="dynamic",
        use_container_width=True
    )

# --- シミュレーション実行ボタン ---
st.divider()
if st.button("シミュレーションを実行する", type="primary"):
    
    # エラーが起きても止まらないようにtryブロックで囲む
    try:
        # 1. ライフステージデータの整理
        phases_data = st.session_state.df_phases.copy()
        if phases_data.empty:
             end_age = 95
        else:
             # 空行を除去して最大年齢を取得
             valid_phases = phases_data.dropna(subset=["終了年齢"])
             if valid_phases.empty:
                 end_age = 95
             else:
                 end_age = int(valid_phases["終了年齢"].max())

        years = end_age - current_age
        
        # 収支マップの作成
        cashflow_map = {}
        for index, row in phases_data.iterrows():
            # 空データがあればスキップ
            if pd.isna(row["開始年齢"]) or pd.isna(row["終了年齢"]) or pd.isna(row["収支(万円)"]):
                continue
            start, end, amount = int(row["開始年齢"]), int(row["終了年齢"]), row["収支(万円)"]
            for age in range(start, end + 1):
                cashflow_map[age] = amount

        # 2. イベントデータの整理（★ここでエラーを防ぐ！）
        event_map = {}
        for index, row in edited_events.iterrows():
            # 値が空(None/NaN)なら無視して次へ
            if pd.isna(row["年齢"]) or pd.isna(row["金額(万円)"]):
                continue
            
            # 安全に整数に変換
            try:
                age = int(row["年齢"])
                amount = int(row["金額(万円)"])
                event_map[age] = event_map.get(age, 0) + amount
            except:
                continue # 変換に失敗したらスキップ

        # --- A. 単純計算（リスクなし） ---
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

        # --- B. モンテカルロシミュレーション ---
        simulation_results = np.zeros((num_simulations, years + 1))
        
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

        # 結果の集計
        median_res = np.percentile(simulation_results, 50, axis=0)
        top_10_res = np.percentile(simulation_results, 90, axis=0)
        bottom_10_res = np.percentile(simulation_results, 10, axis=0)
        ruin_prob = (np.sum(simulation_results[:, -1] == 0) / num_simulations) * 100

        # 結果表示エリア
        st.subheader(f"シミュレーション結果 ({num_simulations}回試行)")
        res_col1, res_col2, res_col3, res_col4 = st.columns(4)
        res_col1.metric("95歳時点の生存率", f"{100 - ruin_prob:.1f}%")
        res_col2.metric("単純計算 (リスクなし)", f"{int(deterministic_assets[-1]):,} 万円")
        res_col3.metric("モンテカルロ (中央値)", f"{int(median_res[-1]):,} 万円")
        res_col4.metric("モンテカルロ (不調時)", f"{int(bottom_10_res[-1]):,} 万円")

        # グラフ描画
        fig, ax = plt.subplots(figsize=(10, 6))
        age_axis = np.arange(current_age, end_age + 1)
        
        # 老後エリア（収支マイナスの期間）を色付け
        for index, row in phases_data.iterrows():
            if not pd.isna(row["収支(万円)"]) and row["収支(万円)"] < 0:
                ax.axvspan(row["開始年齢"], row["終了年齢"], color='orange', alpha=0.1)

        ax.plot(age_axis, deterministic_assets, color='orange', linewidth=3, linestyle=':', label='単純計算（リスクなし）')
        ax.plot(age_axis, median_res, color='blue', linewidth=2, label='中央値')
        ax.plot(age_axis, top_10_res, color='green', linestyle='--', linewidth=1, label='好調 (上位10%)')
        ax.plot(age_axis, bottom_10_res, color='red', linestyle='--', linewidth=1, label='不調 (下位10%)')
        
        ax.set_title("資産推移シミュレーション", fontsize=14)
        ax.set_xlabel("年齢")
        ax.set_ylabel("資産額 (万円)")
        ax.legend()
        ax.grid(True, linestyle='--', alpha=0.7)
        ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: f'{int(x):,}'))
        
        st.pyplot(fig)

    except Exception as e:
        st.error("計算中にエラーが発生しました。入力内容を確認してください。")
        st.error(f"詳細: {e}")
