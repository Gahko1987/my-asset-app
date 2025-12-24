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
        # 年齢
        current_age = st.number_input("現在の年齢", 0, 100, 39, key="input_current_age")
        # 資産
        current_assets = st.number_input("現在の資産 (万円)", 0, 500000, 2300)
        # インフレ率
        inflation_rate_pct = st.slider("インフレ率 (%)", 0.0, 5.0, 2.0, 0.1)

    with col_b2:
        # 利回り
        mean_return_pct = st.slider("想定利回り (年率%)", 0.0, 10.0, 5.0, 0.1)
        # リスク
        risk_std_pct = st.slider("リスク (標準偏差%)", 0.0, 30.0, 15.0, 0.5)

# %を小数に変換
mean_return = mean_return_pct / 100
risk_std = risk_std_pct / 100
inflation_rate = inflation_rate_pct / 100
real_mean_return = mean_return - inflation_rate

st.divider()

# ==========================================
# 入力エリア（表をやめて、分かりやすい入力フォームに変更）
# ==========================================
col1, col2 = st.columns(2)

# === 左側：ライフステージ入力 ===
with col1:
    st.subheader("1. ライフステージ収支 (年額)")
    st.info("人生を4つの期間に分けて、貯金額（または生活費）を設定します。")

    # --- 第1期間 ---
    st.markdown("##### 🟢 第1期間 (現在 〜 )")
    c1_1, c1_2 = st.columns([1, 1])
    with c1_1:
        phase1_end = st.number_input("何歳まで？ (第1期間)", min_value=current_age, max_value=120, value=42)
    with c1_2:
        phase1_save = st.number_input("年間の収支 (万円)", value=900, key="p1_save", help="プラスは貯金、マイナスは取り崩し")

    # --- 第2期間 ---
    st.markdown(f"##### 🔵 第2期間 ({phase1_end + 1}歳 〜 )")
    c2_1, c2_2 = st.columns([1, 1])
    with c2_1:
        phase2_end = st.number_input("何歳まで？ (第2期間)", min_value=phase1_end+1, max_value=120, value=60)
    with c2_2:
        phase2_save = st.number_input("年間の収支 (万円)", value=400, key="p2_save")

    # --- 第3期間 ---
    st.markdown(f"##### 🟡 第3期間 ({phase2_end + 1}歳 〜 )")
    c3_1, c3_2 = st.columns([1, 1])
    with c3_1:
        phase3_end = st.number_input("何歳まで？ (第3期間)", min_value=phase2_end+1, max_value=120, value=65)
    with c3_2:
        phase3_save = st.number_input("年間の収支 (万円)", value=100, key="p3_save")

    # --- 第4期間 ---
    st.markdown(f"##### 🟠 第4期間 ({phase3_end + 1}歳 〜 )")
    c4_1, c4_2 = st.columns([1, 1])
    with c4_1:
        phase4_end = st.number_input("何歳まで？ (第4期間)", min_value=phase3_end+1, max_value=120, value=100)
    with c4_2:
        phase4_save = st.number_input("年間の収支 (万円)", value=-300, key="p4_save")

    # データをまとめる
    phases_list = [
        {"start": current_age, "end": phase1_end, "amount": phase1_save},
        {"start": phase1_end + 1, "end": phase2_end, "amount": phase2_save},
        {"start": phase2_end + 1, "end": phase3_end, "amount": phase3_save},
        {"start": phase3_end + 1, "end": phase4_end, "amount": phase4_save},
    ]

# === 右側：イベント入力 ===
with col2:
    st.subheader("2. イベント・一時金")
    st.caption("退職金や家の購入など、大きな出費や収入を入力")

    # --- イベント1 ---
    st.markdown("##### イベント 1")
    e1_1, e1_2, e1_3 = st.columns([1, 1, 1.5])
    with e1_1:
        ev1_age = st.number_input("年齢", min_value=0, max_value=120, value=60, key="ev1_age")
    with e1_2:
        ev1_amount = st.number_input("金額(万円)", value=2000, key="ev1_amount")
    with e1_3:
        ev1_name = st.text_input("内容", value="退職金", key="ev1_name")

    # --- イベント2 ---
    st.markdown("##### イベント 2")
    e2_1, e2_2, e2_3 = st.columns([1, 1, 1.5])
    with e2_1:
        ev2_age = st.number_input("年齢", min_value=0, max_value=120, value=55, key="ev2_age")
    with e2_2:
        ev2_amount = st.number_input("金額(万円)", value=-300, key="ev2_amount")
    with e2_3:
        ev2_name = st.text_input("内容", value="車の購入", key="ev2_name")

    # --- イベント3 ---
    st.markdown("##### イベント 3")
    e3_1, e3_2, e3_3 = st.columns([1, 1, 1.5])
    with e3_1:
        ev3_age = st.number_input("年齢", min_value=0, max_value=120, value=0, key="ev3_age")
    with e3_2:
        ev3_amount = st.number_input("金額(万円)", value=0, key="ev3_amount")
    with e3_3:
        ev3_name = st.text_input("内容", value="", key="ev3_name")

    # イベントデータをまとめる
    events_list = [
        {"age": ev1_age, "amount": ev1_amount},
        {"age": ev2_age, "amount": ev2_amount},
        {"age": ev3_age, "amount": ev3_amount},
    ]

# --- シミュレーション実行ボタン ---
st.divider()
if st.button("シミュレーションを実行する (10,000回)", type="primary"):
    
    try:
        # 計算ロジック
        end_age = phase4_end
        years = end_age - current_age
        num_simulations = 10000 
        
        # 収支マップ作成
        cashflow_map = {}
        for p in phases_list:
            start, end, amount = int(p["start"]), int(p["end"]), p["amount"]
            if start <= end:
                for age in range(start, end + 1):
                    cashflow_map[age] = amount

        # イベントマップ作成
        event_map = {}
        for e in events_list:
            age, amount = int(e["age"]), int(e["amount"])
            if amount != 0: # 金額が0のイベントは無視
                event_map[age] = event_map.get(age, 0) + amount

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
        progress_bar = st.progress(0)
        
        for i in range(num_simulations):
            assets = [current_assets]
            if i % 100 == 0: progress_bar.progress(i / num_simulations)
                
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
            
        progress_bar.progress(1.0)

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
        
        # 老後エリア（マイナス収支の期間）の色付け
        for p in phases_list:
            if p["amount"] < 0:
                ax.axvspan(p["start"], p["end"], color='orange', alpha=0.1)

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
