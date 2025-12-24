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
        # ★初期値を変更：20歳
        current_age = st.number_input("現在の年齢", 0, 100, 20, key="input_current_age")
        # ★初期値を変更：300万円
        current_assets = st.number_input("現在の資産 (万円)", 0, 500000, 300)
        inflation_rate_pct = st.slider("インフレ率 (%)", 0.0, 5.0, 2.0, 0.1)

    with col_b2:
        mean_return_pct = st.slider("想定利回り (年率%)", 0.0, 10.0, 5.0, 0.1)
        risk_std_pct = st.slider("リスク (標準偏差%)", 0.0, 30.0, 15.0, 0.5)

# 計算用数値
mean_return = mean_return_pct / 100
risk_std = risk_std_pct / 100
inflation_rate = inflation_rate_pct / 100
real_mean_return = mean_return - inflation_rate

st.divider()

# ==========================================
# データ管理用ロジック（追加・削除機能）
# ==========================================

# 1. ライフステージの初期データ（20歳向けに調整）
if "phases_list" not in st.session_state:
    st.session_state.phases_list = [
        {"end": 30, "amount": 100},   # 20代：少しずつ貯金
        {"end": 60, "amount": 400},   # 30代〜：本格的に貯金
        {"end": 65, "amount": 100},   # 再雇用期間
        {"end": 100, "amount": -300}, # 老後
    ]

# 2. イベントの初期データ（20歳向けに調整）
if "events_list" not in st.session_state:
    st.session_state.events_list = [
        {"age": 30, "amount": -500, "name": "結婚・住宅頭金"},
        {"age": 60, "amount": 2000, "name": "退職金"},
    ]

# ボタン操作のコールバック関数
def add_phase():
    # 最後の期間の終了年齢+5歳をデフォルトにする
    if st.session_state.phases_list:
        last_end = st.session_state.phases_list[-1]["end"]
    else:
        last_end = current_age
    st.session_state.phases_list.append({"end": last_end + 5, "amount": 0})

def remove_phase():
    if len(st.session_state.phases_list) > 1:
        st.session_state.phases_list.pop()

def add_event():
    st.session_state.events_list.append({"age": current_age + 5, "amount": -100, "name": "新しいイベント"})

def remove_event(index):
    st.session_state.events_list.pop(index)

# ==========================================
# メイン画面入力エリア
# ==========================================
col1, col2 = st.columns(2)

# === 左側：ライフステージ入力（期間追加式） ===
with col1:
    st.subheader("1. ライフステージ収支")
    st.info("期間を追加・削除して、人生の収支計画を立てましょう。")

    # 期間のリストを表示
    start_age_tracker = current_age
    
    for i, phase in enumerate(st.session_state.phases_list):
        st.markdown(f"**🔹 第{i+1}期間 ({start_age_tracker}歳 〜 )**")
        
        c_p1, c_p2 = st.columns([1, 1])
        with c_p1:
            # 終了年齢の入力
            new_end = st.number_input(
                f"何歳まで？ (第{i+1}期間)",
                min_value=start_age_tracker, 
                max_value=150,
                value=int(phase["end"]),
                key=f"phase_end_{i}"
            )
            st.session_state.phases_list[i]["end"] = new_end
            
        with c_p2:
            # 金額の入力
            new_amount = st.number_input(
                f"年間の収支 (万円)",
                value=int(phase["amount"]),
                key=f"phase_amount_{i}"
            )
            st.session_state.phases_list[i]["amount"] = new_amount
        
        # 次の期間の開始年齢を更新
        start_age_tracker = new_end + 1
        st.markdown("---")

    # 追加・削除ボタン
    b_col1, b_col2 = st.columns(2)
    with b_col1:
        st.button("➕ 期間を追加", on_click=add_phase, use_container_width=True)
    with b_col2:
        st.button("🗑️ 最後の期間を削除", on_click=remove_phase, use_container_width=True)


# === 右側：イベント入力（リスト追加式） ===
with col2:
    st.subheader("2. イベント・一時金")
    st.caption("イベントを好きなだけ追加できます。")

    # イベントリスト表示
    for i, event in enumerate(st.session_state.events_list):
        with st.container(border=True):
            e_col1, e_col2 = st.columns([2, 1])
            with e_col1:
                st.markdown(f"**イベント {i+1}**")
            with e_col2:
                if st.button("🗑️ 削除", key=f"del_event_{i}"):
                    remove_event(i)
                    st.rerun()
            
            e_in1, e_in2, e_in3 = st.columns([1, 1, 1.5])
            with e_in1:
                new_age = st.number_input("年齢", min_value=0, max_value=150, value=int(event["age"]), key=f"ev_age_{i}")
                st.session_state.events_list[i]["age"] = new_age
            with e_in2:
                new_amt = st.number_input("金額(万円)", value=int(event["amount"]), key=f"ev_amt_{i}")
                st.session_state.events_list[i]["amount"] = new_amt
            with e_in3:
                new_name = st.text_input("内容", value=event["name"], key=f"ev_name_{i}")
                st.session_state.events_list[i]["name"] = new_name

    st.button("➕ イベントを追加", on_click=add_event, use_container_width=True)


# --- シミュレーション実行ボタン ---
st.divider()
if st.button("シミュレーションを実行する (10,000回)", type="primary"):
    
    try:
        # 最終的な終了年齢を取得
        if st.session_state.phases_list:
            end_age = st.session_state.phases_list[-1]["end"]
        else:
            end_age = 100
            
        years = end_age - current_age
        
        # エラー回避：もし終了年齢が現在年齢以下なら警告
        if years <= 0:
            st.error(f"エラー：終了年齢({end_age}歳)は、現在の年齢({current_age}歳)より未来に設定してください。")
        else:
            num_simulations = 10000 
            
            # 収支マップ作成
            cashflow_map = {}
            temp_start = current_age
            for p in st.session_state.phases_list:
                end_val = int(p["end"])
                amount_val = int(p["amount"])
                
                if temp_start <= end_val:
                    for age in range(temp_start, end_val + 1):
                        cashflow_map[age] = amount_val
                temp_start = end_val + 1

            # イベントマップ作成
            event_map = {}
            for e in st.session_state.events_list:
                age = int(e["age"])
                amount = int(e["amount"])
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
            temp_start = current_age
            for p in st.session_state.phases_list:
                end_val = int(p["end"])
                if p["amount"] < 0:
                    ax.axvspan(temp_start, end_val, color='orange', alpha=0.1)
                temp_start = end_val + 1

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
        st.error(f"エラーが発生しました: {e}")
