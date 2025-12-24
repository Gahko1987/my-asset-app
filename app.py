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
        current_age = st.number_input("現在の年齢", 0, 100, 20, key="input_current_age")
        current_assets = st.number_input("現在の資産 (万円)", 0, 500000, 300)
        inflation_rate_pct = st.slider("インフレ率 (%)", 0.0, 5.0, 2.0, 0.1)

    with col_b2:
        mean_return_pct = st.slider("想定利回り (年率%)", 0.0, 20.0, 5.0, 0.1)
        st.caption("""
        **📈 利回りの目安 (長期・円ベース)**
        - 🇯🇵 **TOPIX**: 4% 〜 6%
        - 🌏 **オルカン**: 5% 〜 8%
        - 🇺🇸 **S&P500**: 7% 〜 10%
        - 🏛 **NASDAQ**: 9% 〜 13%
        """)
        
        risk_std_pct = st.slider("リスク (標準偏差%)", 0.0, 40.0, 15.0, 0.5)
        st.caption("""
        **📊 リスクの目安 (円ベース)**
        - 🇯🇵 **TOPIX**: 15% 〜 18%
        - 🌏 **オルカン**: 17% 〜 20%
        - 🇺🇸 **S&P500**: 19% 〜 23%
        - 🏛 **NASDAQ**: 23% 〜 28%
        """)

# 計算用数値
mean_return = mean_return_pct / 100
risk_std = risk_std_pct / 100
inflation_rate = inflation_rate_pct / 100
real_mean_return = mean_return - inflation_rate

st.divider()

# ==========================================
# データ管理用ロジック
# ==========================================

# 1. ライフステージの初期データ
if "phases_list" not in st.session_state:
    st.session_state.phases_list = [
        {"end": 30, "amount": 100},
        {"end": 60, "amount": 400},
        {"end": 65, "amount": 100},
        {"end": 100, "amount": -300},
    ]

# 2. イベントの初期データ
if "events_list" not in st.session_state:
    st.session_state.events_list = [
        {"age": 60, "amount": 2000, "name": "退職金"},
        {"age": 30, "amount": -300, "name": "車購入"},
    ]

# ボタン操作のコールバック関数
def add_phase():
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

# === 左側：ライフステージ入力 ===
with col1:
    st.subheader("1. ライフステージ収支")
    st.info("期間を追加・削除して、人生の収支計画を立てましょう。")

    start_age_tracker = current_age
    
    for i, phase in enumerate(st.session_state.phases_list):
        st.markdown(f"**🔹 第{i+1}期間 ({start_age_tracker}歳 〜 )**")
        
        c_p1, c_p2 = st.columns([1, 1])
        with c_p1:
            # 年齢矛盾のエラー回避
            min_val = start_age_tracker
            current_end_val = int(phase["end"])
            
            if current_end_val < min_val:
                current_end_val = min_val
                st.session_state.phases_list[i]["end"] = current_end_val

            new_end = st.number_input(
                f"何歳まで？ (第{i+1}期間)",
                min_value=min_val,
                max_value=150,
                value=current_end_val,
                key=f"phase_end_{i}"
            )
            st.session_state.phases_list[i]["end"] = new_end
            
        with c_p2:
            new_amount = st.number_input(
                f"年間の収支 (万円)",
                value=int(phase["amount"]),
                key=f"phase_amount_{i}"
            )
            st.session_state.phases_list[i]["amount"] = new_amount
        
        start_age_tracker = new_end + 1
        st.markdown("---")

    b_col1, b_col2 = st.columns(2)
    with b_col1:
        st.button("➕ 期間を追加", on_click=add_phase, use_container_width=True)
    with b_col2:
        st.button("🗑️ 最後の期間を削除", on_click=remove_phase, use_container_width=True)


# === 右側：イベント入力 ===
with col2:
    st.subheader("2. イベント・一時金")
    st.caption("イベントを好きなだけ追加できます。")

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
                ev_val = int(event["age"])
                if ev_val < 0: ev_val = 0
                
                new_age = st.number_input("年齢", min_value=0, max_value=150, value=ev_val, key=f"ev_age_{i}")
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
        if st.session_state.phases_list:
            end_age = st.session_state.phases_list[-1]["end"]
        else:
            end_age = 100
            
        years = end_age - current_age
        
        if years <= 0:
            st.error(f"エラー：終了年齢({end_age}歳)は、現在の年齢({current_age}歳)より未来に設定してください。")
        else:
            num_simulations = 10000 
            
            cashflow_map = {}
            temp_start = current_age
            for p in st.session_state.phases_list:
                end_val = int(p["end"])
                amount_val = int(p["amount"])
                
                if temp_start <= end_val:
                    for age in range(temp_start, end_val + 1):
                        cashflow_map[age] = amount_val
                temp_start = end_val + 1

            event_map = {}
            for e in st.session_state.events_list:
                age = int(e["age"])
                amount = int(e["amount"])
                event_map[age] = event_map.get(age, 0) + amount

            # --- A. 単純計算 (リスクなし・利回りあり) ---
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

            # --- B. 積立元本 (投資なし・利回り0%) ---
            principal_assets = [current_assets]
            for year in range(years):
                age = current_age + year
                annual_flow = cashflow_map.get(age, 0)
                spot_flow = event_map.get(age, 0)
                
                prev_val = principal_assets[-1]
                # 利回りをかけず、収支を足すだけ
                new_val = prev_val + annual_flow + spot_flow
                if new_val < 0: new_val = 0
                principal_assets.append(new_val)

            # --- C. モンテカルロ ---
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

            # --- 集計 ---
            median_res = np.percentile(simulation_results, 50, axis=0)
            top_10_res = np.percentile(simulation_results, 90, axis=0)
            bottom_10_res = np.percentile(simulation_results, 10, axis=0)
            ruin_prob = (np.sum(simulation_results[:, -1] == 0) / num_simulations) * 100

            # --- 結果表示1: サマリ ---
            st.subheader(f"シミュレーション結果 ({end_age}歳まで / {num_simulations}回試行)")
            res_col1, res_col2, res_col3, res_col4 = st.columns(4)
            res_col1.metric(f"{end_age}歳生存率", f"{100 - ruin_prob:.1f}%")
            res_col2.metric("単純計算", f"{int(deterministic_assets[-1]):,}万")
            res_col3.metric("中央値", f"{int(median_res[-1]):,}万")
            res_col4.metric("不調時", f"{int(bottom_10_res[-1]):,}万")

            # --- 結果表示2: グラフ ---
            fig, ax = plt.subplots(figsize=(10, 6))
            age_axis = np.arange(current_age, end_age + 1)
            
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

            # --- 結果表示3: 分布テーブル ---
            st.divider()
            st.subheader("📋 詳細データ: 資産額の分布 (10歳刻み)")
            st.caption("各年齢ごとの上位〜下位グループの平均資産額を表示します。")

            step_years = 10
            target_ages = list(range(current_age, end_age + 1, step_years))
            if target_ages[-1] != end_age:
                target_ages.append(end_age)
            
            percentile_ranges = [
                (90, 100, "上位 10%"),
                (80, 90, "11% - 20%"),
                (70, 80, "21% - 30%"),
                (60, 70, "31% - 40%"),
                (50, 60, "41% - 50%"),
                (40, 50, "51% - 60%"),
                (30, 40, "61% - 70%"),
                (20, 30, "71% - 80%"),
                (10, 20, "81% - 90%"),
                (0, 10, "91% - 100%")
            ]
            
            # 行ラベルの作成（ランク + 単純計算 + 積立元本）
            row_labels = [label for _, _, label in percentile_ranges]
            row_labels.append("単純計算 (リスクなし)")
            row_labels.append("積立元本 (投資なし)")
            
            table_data = {"ランク": row_labels}
            
            for target_age in target_ages:
                idx = target_age - current_age
                assets_at_age = np.sort(simulation_results[:, idx])
                
                col_values = []
                
                # 1. ランクごとの値を計算
                for p_start, p_end, _ in percentile_ranges:
                    slice_start = int(num_simulations * (p_start / 100))
                    slice_end = int(num_simulations * (p_end / 100))
                    
                    subset = assets_at_age[slice_start:slice_end]
                    if len(subset) > 0:
                        avg_val = np.mean(subset)
                    else:
                        avg_val = 0
                    col_values.append(f"{int(avg_val):,} 万円")
                
                # 2. 単純計算の値を追加
                if idx < len(deterministic_assets):
                    val_simple = deterministic_assets[idx]
                    col_values.append(f"{int(val_simple):,} 万円")
                else:
                    col_values.append("-")

                # 3. 積立元本の値を追加
                if idx < len(principal_assets):
                    val_principal = principal_assets[idx]
                    col_values.append(f"{int(val_principal):,} 万円")
                else:
                    col_values.append("-")

                table_data[f"{target_age}歳"] = col_values

            df_table = pd.DataFrame(table_data)
            st.dataframe(df_table, hide_index=True, use_container_width=True)

    except Exception as e:
        st.error(f"エラーが発生しました: {e}")
