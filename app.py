import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import japanize_matplotlib
import matplotlib.ticker as ticker
import urllib.parse  # ★追加: URLエンコード用

# ページ設定
st.set_page_config(page_title="資産ライフプランシミュレーター", layout="wide")

st.title("📊 資産＆ライフプラン シミュレーター")

# ==========================================
# ▼ 教育費データ（年額・万円） ▼
# ==========================================
EDU_COSTS = {
    "all_public": { "kindergarten": 23, "elementary": 35, "junior_high": 54, "high_school": 52, "university": 120 },
    "private_uni": { "kindergarten": 23, "elementary": 35, "junior_high": 54, "high_school": 52, "university": 172 },
    "private_from_jr": { "kindergarten": 23, "elementary": 35, "junior_high": 144, "high_school": 105, "university": 172 }, 
    "all_private": { "kindergarten": 36, "elementary": 170, "junior_high": 144, "high_school": 105, "university": 172 },
    "vocational": { "kindergarten": 23, "elementary": 35, "junior_high": 54, "high_school": 52, "vocational_school": 130 },
    "junior_college": { "kindergarten": 23, "elementary": 35, "junior_high": 54, "high_school": 52, "junior_college": 120 },
    "high_school_grad": { "kindergarten": 23, "elementary": 35, "junior_high": 54, "high_school": 52 },
    "medical_private": { "kindergarten": 36, "elementary": 170, "junior_high": 144, "high_school": 105, "medical_uni": 500 },
    "study_abroad": { "kindergarten": 36, "elementary": 170, "junior_high": 144, "high_school": 105, "overseas_uni": 700 }
}

def get_school_stage(age, course_type):
    if 3 <= age <= 5: return "kindergarten"
    if 6 <= age <= 11: return "elementary"
    if 12 <= age <= 14: return "junior_high"
    if 15 <= age <= 17: return "high_school"
    
    # 18歳以降の分岐
    if 18 <= age <= 23 and course_type == "medical_private": return "medical_uni"
    if 18 <= age <= 21:
        if course_type in ["all_public", "private_uni", "all_private", "private_from_jr"]: return "university"
        if course_type == "study_abroad": return "overseas_uni"
    if 18 <= age <= 19:
        if course_type == "vocational": return "vocational_school"
        if course_type == "junior_college": return "junior_college"
        
    return None

STAGE_NAMES = {
    "kindergarten": "幼", "elementary": "小", "junior_high": "中", 
    "high_school": "高", "university": "大", "vocational_school": "専", "junior_college": "短",
    "medical_uni": "医", "overseas_uni": "留"
}

# ==========================================
# ローン計算ロジック (変動金利・上限ストッパー対応)
# ==========================================
def calculate_loan_schedule(principal, years, initial_rate, annual_increase, max_rate):
    schedule = []
    current_principal = principal
    base_pmt = 0
    
    for y in range(years):
        if current_principal <= 0:
            break
        
        # 金利が上限(max_rate)を超えないように制御
        rate = min(initial_rate + annual_increase * y, max_rate)
        r = rate / 100 / 12
        n = (years - y) * 12
        
        if r > 0:
            monthly_pmt = current_principal * (r * (1+r)**n) / ((1+r)**n - 1)
            # 1年(12ヶ月)後の残債計算
            next_principal = current_principal * ((1+r)**n - (1+r)**12) / ((1+r)**n - 1)
        else:
            monthly_pmt = current_principal / n
            next_principal = current_principal - monthly_pmt * 12
            
        annual_pmt = monthly_pmt * 12
        if y == 0:
            base_pmt = annual_pmt
            
        schedule.append({
            "year": y,
            "rate": rate,
            "annual_pmt": annual_pmt,
            "balance": max(0, next_principal)
        })
        current_principal = max(0, next_principal)
        
    return schedule, base_pmt

# ==========================================
# ▼ 基本設定パネル ▼
# ==========================================
with st.expander("▼ 基本設定（ここをタップして変更）", expanded=True):
    col_b1, col_b2 = st.columns(2)
    
    with col_b1:
        current_age = st.number_input("現在の年齢", 0, 100, 35, key="input_current_age")
        current_assets = st.number_input("現在の資産 (万円)", 0, 500000, 500)
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

    # --- 住宅ローン設定 ---
    st.markdown("---")
    st.markdown("##### 🏠 住宅・ローン設定 (変動金利・上限対応)")
    
    housing_option = st.radio(
        "住居・ローンの状況", 
        ["考慮しない (賃貸・ローンなし)", "これから購入予定", "すでに購入済み (ローン返済中)"],
        horizontal=True
    )
    
    housing_info = {"type": "none", "base_pmt": 0, "schedule": {}, "start_age": 0, "end_age": 0, "current_rent_saved": 0}

    if housing_option == "これから購入予定":
        st.caption("※ 購入後は「現在の家賃」がかからなくなり、代わりに「ローン返済」が始まります。")
        h_col1, h_col2, h_col3 = st.columns(3)
        with h_col1:
            h_age = st.number_input("購入年齢", current_age, 100, current_age + 5)
            h_price = st.number_input("物件価格 (万円)", 0, 50000, 4000)
            current_rent_val = st.number_input("現在の家賃(年額・万)", 0, 1000, 120)
        with h_col2:
            h_down = st.number_input("頭金 (万円)", 0, h_price, 500)
            h_years = st.number_input("返済期間 (年)", 1, 50, 35)
        with h_col3:
            h_rate = st.number_input("初期金利 (%)", 0.0, 10.0, 1.5, 0.1)
            h_rate_inc = st.number_input("毎年の金利上昇幅 (%)", 0.0, 2.0, 0.0, 0.05, help="0.0なら固定金利。")
            h_rate_max = st.number_input("上限金利 (%)", 0.0, 20.0, 4.0, 0.1, help="設定した金利以上には上がりません")
        
        loan_principal = h_price - h_down
        if loan_principal > 0:
            schedule_list, base_pmt = calculate_loan_schedule(loan_principal, h_years, h_rate, h_rate_inc, h_rate_max)
            schedule_dict = {h_age + item["year"]: item for item in schedule_list}
            housing_info = {
                "type": "future", "base_pmt": base_pmt, "schedule": schedule_dict,
                "start_age": h_age, "end_age": h_age + h_years - 1, "current_rent_saved": current_rent_val
            }
            st.info(f"📅 **計画**: {h_age}歳で購入。初年度の返済は約{int(base_pmt)}万円。金利が上がると返済額が増え、収支からマイナスされます。")

    elif housing_option == "すでに購入済み (ローン返済中)":
        st.caption("※ 金利上昇で返済額が増えた分は、現在の収支からマイナスされます。")
        h_col1, h_col2, h_col3 = st.columns(3)
        with h_col1:
            loan_principal = st.number_input("現在のローン残高 (万円)", 0, 50000, 3000)
            h_years_remain = st.number_input("残り返済期間 (年)", 1, 50, 25)
        with h_col2:
            h_rate = st.number_input("現在の金利 (%)", 0.0, 10.0, 1.5, 0.1)
            h_rate_inc = st.number_input("毎年の金利上昇幅 (%)", 0.0, 2.0, 0.0, 0.05, help="0.0なら固定金利")
        with h_col3:
            h_rate_max = st.number_input("上限金利 (%)", 0.0, 20.0, 4.0, 0.1, help="設定した金利以上には上がりません")
        
        if loan_principal > 0:
            schedule_list, base_pmt = calculate_loan_schedule(loan_principal, h_years_remain, h_rate, h_rate_inc, h_rate_max)
            schedule_dict = {current_age + item["year"]: item for item in schedule_list}
            housing_info = {
                "type": "already", "base_pmt": base_pmt, "schedule": schedule_dict,
                "start_age": current_age, "end_age": current_age + h_years_remain - 1, "current_rent_saved": 0
            }
            st.info(f"📅 **計画**: 現在の年間返済額は約{int(base_pmt)}万円基準。完済後はこの額が収支にプラスされます。")

    # --- 年金設定 ---
    st.markdown("---")
    use_pension = st.checkbox("年金を考慮する", value=True)
    if use_pension:
        p_col1, p_col2 = st.columns(2)
        with p_col1: pension_start_age = st.number_input("受給開始年齢", 60, 75, 65)
        with p_col2: pension_annual = st.number_input("受給額 (年額・万円)", 0, 1000, 240)
    else:
        pension_start_age = 65; pension_annual = 0

real_mean_return = (mean_return_pct / 100) - (inflation_rate_pct / 100)
risk_std = risk_std_pct / 100

st.divider()

# ==========================================
# データ管理 (ライフステージ、イベント、子供)
# ==========================================
if "phases_list" not in st.session_state:
    st.session_state.phases_list = [{"end": 45, "amount": 100}, {"end": 60, "amount": 200}, {"end": 65, "amount": 100}, {"end": 100, "amount": -100}]
if "events_list" not in st.session_state:
    st.session_state.events_list = [{"age": 60, "amount": 1500, "name": "退職金"}, {"age": 40, "amount": -300, "name": "車購入"}]
if "children_list" not in st.session_state:
    st.session_state.children_list = [{"age": 5, "course": "private_uni"}, {"age": 2, "course": "private_uni"}]

def add_phase(): st.session_state.phases_list.append({"end": (st.session_state.phases_list[-1]["end"] if st.session_state.phases_list else current_age) + 5, "amount": 0})
def remove_phase():
    if len(st.session_state.phases_list) > 1: st.session_state.phases_list.pop()
def add_event(): st.session_state.events_list.append({"age": current_age + 5, "amount": -100, "name": "新イベント"})
def remove_event(index): st.session_state.events_list.pop(index)
def add_child(): st.session_state.children_list.append({"age": 0, "course": "private_uni"})
def remove_child(index): st.session_state.children_list.pop(index)

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. ライフステージ収支")
    st.info("💡 **現在の住居費（家賃やローン返済額）を含んだ**、年間の収支を入力してください。")
    start_age_tracker = current_age
    for i, phase in enumerate(st.session_state.phases_list):
        c_p1, c_p2 = st.columns([1, 1])
        with c_p1:
            st.session_state.phases_list[i]["end"] = st.number_input(f"終了年齢 (第{i+1}期)", start_age_tracker, 150, max(start_age_tracker, int(phase["end"])), key=f"p_end_{i}")
        with c_p2:
            st.session_state.phases_list[i]["amount"] = st.number_input(f"年間収支 (万円)", value=int(phase["amount"]), key=f"p_amt_{i}")
        start_age_tracker = st.session_state.phases_list[i]["end"] + 1
    b_col1, b_col2 = st.columns(2)
    with b_col1: st.button("➕ 期間を追加", on_click=add_phase, use_container_width=True)
    with b_col2: st.button("🗑️ 最後の期間を削除", on_click=remove_phase, use_container_width=True)

with col2:
    st.subheader("2. 子供の教育費")
    for i, child in enumerate(st.session_state.children_list):
        with st.container(border=True):
            c_in1, c_in2, c_in3 = st.columns([1.5, 2.5, 1])
            with c_in1: st.session_state.children_list[i]["age"] = st.number_input("現在年齢", 0, 30, int(child["age"]), key=f"c_age_{i}")
            with c_in2:
                opts = {"all_public": "国公立大", "private_uni": "私立大学", "private_from_jr": "中学から私立", "all_private": "すべて私立", "vocational": "専門", "junior_college": "短大", "study_abroad": "海外留学", "medical_private": "私立医学部", "high_school_grad": "高卒"}
                st.session_state.children_list[i]["course"] = st.selectbox("コース", list(opts.keys()), format_func=lambda x: opts[x], index=list(opts.keys()).index(child["course"] if child["course"] in opts else "private_uni"), key=f"c_crs_{i}")
            with c_in3:
                if st.button("削除", key=f"del_c_{i}"): remove_child(i); st.rerun()
    st.button("➕ 子供を追加", on_click=add_child, use_container_width=True)
    
    st.divider()
    st.subheader("3. イベント・一時金")
    for i, event in enumerate(st.session_state.events_list):
        e_in1, e_in2, e_in3, e_in4 = st.columns([1, 1, 1.5, 0.8])
        with e_in1: st.session_state.events_list[i]["age"] = st.number_input("年齢", 0, 150, int(event["age"]), key=f"e_age_{i}")
        with e_in2: st.session_state.events_list[i]["amount"] = st.number_input("万円", value=int(event["amount"]), key=f"e_amt_{i}")
        with e_in3: st.session_state.events_list[i]["name"] = st.text_input("内容", value=event["name"], key=f"e_name_{i}")
        with e_in4: 
            if st.button("削除", key=f"del_e_{i}"): remove_event(i); st.rerun()
    st.button("➕ イベント追加", on_click=add_event, use_container_width=True)

# ==========================================
# シミュレーション実行
# ==========================================
st.divider()
if st.button("シミュレーションを実行する (10,000回)", type="primary"):
    try:
        end_age = st.session_state.phases_list[-1]["end"] if st.session_state.phases_list else 100
        years = end_age - current_age
        
        if years > 0:
            num_simulations = 10000 
            cashflow_map = {}
            
            # 1. ライフステージ収支
            t_start = current_age
            for p in st.session_state.phases_list:
                end_val = int(p["end"])
                amount_val = int(p["amount"])
                if t_start <= end_val:
                    for age in range(t_start, end_val + 1):
                        cashflow_map[age] = amount_val
                t_start = end_val + 1

            # 2. 教育費の控除
            education_cost_map = {}
            for child in st.session_state.children_list:
                c_age = child["age"]
                c_course = child["course"]
                for y in range(40): 
                    current_c_age = c_age + y
                    parent_age = current_age + y
                    if parent_age > end_age: break
                    stage = get_school_stage(current_c_age, c_course)
                    if stage:
                        cost = EDU_COSTS[c_course][stage]
                        cashflow_map[parent_age] = cashflow_map.get(parent_age, 0) - cost
                        education_cost_map[parent_age] = education_cost_map.get(parent_age, 0) + cost

            # 3. 年金 & 住宅ローン(変動対応)
            for y in range(years + 1):
                age = current_age + y
                if use_pension and age >= pension_start_age:
                    cashflow_map[age] = cashflow_map.get(age, 0) + pension_annual
                
                # すでに購入済みの場合
                if housing_info["type"] == "already":
                    if housing_info["start_age"] <= age <= housing_info["end_age"]:
                        actual_pmt = housing_info["schedule"][age]["annual_pmt"]
                        # ベース(今の返済額)と実際の返済額の差額だけマイナスする
                        cashflow_map[age] = cashflow_map.get(age, 0) + (housing_info["base_pmt"] - actual_pmt)
                    elif age > housing_info["end_age"]:
                        # 完済後は今の返済額分がまるまるプラスに
                        cashflow_map[age] = cashflow_map.get(age, 0) + housing_info["base_pmt"]
                
                # これから購入予定の場合
                elif housing_info["type"] == "future":
                    if housing_info["start_age"] <= age <= housing_info["end_age"]:
                        actual_pmt = housing_info["schedule"][age]["annual_pmt"]
                        # 家賃が浮く分プラスし、実際の返済額を全額マイナスする
                        cashflow_map[age] = cashflow_map.get(age, 0) + housing_info["current_rent_saved"] - actual_pmt
                    elif age > housing_info["end_age"]:
                        # 完済後は家賃浮き分だけがずっとプラスに
                        cashflow_map[age] = cashflow_map.get(age, 0) + housing_info["current_rent_saved"]

            # 4. イベントマップ
            event_map = {}
            for e in st.session_state.events_list:
                event_map[int(e["age"])] = event_map.get(int(e["age"]), 0) + int(e["amount"])
            
            # --- シミュレーション計算 (高速化版) ---
            deterministic_assets = [current_assets]
            principal_assets = [current_assets]
            
            flows = np.array([cashflow_map.get(current_age + y, 0) for y in range(years)])
            spots = np.array([event_map.get(current_age + y, 0) for y in range(years)])
            total_flows = flows + spots
            
            random_returns = np.random.normal(real_mean_return, risk_std, (num_simulations, years))
            simulation_results = np.zeros((num_simulations, years + 1))
            simulation_results[:, 0] = current_assets
            
            progress_bar = st.progress(0)
            
            for year in range(years):
                # 単純計算用
                prev_d = deterministic_assets[-1]
                if prev_d <= 0: new_d = 0
                else:
                    new_d = (prev_d + total_flows[year]) * (1 + real_mean_return)
                    if new_d < 0: new_d = 0
                deterministic_assets.append(new_d)
                
                # 元本計算用
                prev_p = principal_assets[-1]
                new_p = prev_p + total_flows[year]
                if new_p < 0: new_p = 0
                principal_assets.append(new_p)

                # モンテカルロ計算用（一括処理）
                prev_assets = simulation_results[:, year]
                active_mask = prev_assets > 0
                
                new_assets = np.zeros_like(prev_assets)
                new_assets[active_mask] = (prev_assets[active_mask] + total_flows[year]) * (1 + random_returns[active_mask, year])
                new_assets[new_assets < 0] = 0
                
                simulation_results[:, year + 1] = new_assets
                
                if year % 5 == 0:
                    progress_bar.progress((year + 1) / years)
                    
            progress_bar.progress(1.0)

            # --- 結果集計 ---
            median_res = np.percentile(simulation_results, 50, axis=0)
            top_20_res = np.percentile(simulation_results, 80, axis=0)
            bottom_20_res = np.percentile(simulation_results, 20, axis=0)
            ruin_prob = (np.sum(simulation_results[:, -1] == 0) / num_simulations) * 100

            st.subheader(f"シミュレーション結果 ({end_age}歳まで)")
            
            total_edu = sum(education_cost_map.values())
            if total_edu > 0: st.info(f"🎓 **教育費**: 総額 約 {total_edu:,} 万円 を考慮済")
            if use_pension: st.success(f"👴 **年金**: {pension_start_age}歳から年額 {pension_annual:,} 万円 を加算済")
            
            if housing_info["type"] != "none":
                # ローンの総支払額を計算
                total_loan = sum([item["annual_pmt"] for item in housing_info["schedule"].values()])
                st.warning(f"🏠 **住宅ローン**: {housing_info['start_age']}歳〜{housing_info['end_age']}歳まで返済。総支払額は約 {int(total_loan):,} 万円 です。")

            with st.expander("🔰 数字の見方ガイド", expanded=True):
                st.markdown("""
                * **生存率**: 資産が底をつかない確率。80%以上が目安。
                * **好調/不調**: **上位20%** と **下位20%** のラインを表示。
                * **積立元本(グレー)**: 投資をせず、貯金だけで推移した場合の金額。
                """)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric(f"{end_age}歳生存率", f"{100 - ruin_prob:.1f}%")
            c2.metric("単純計算", f"{int(deterministic_assets[-1]):,}万")
            c3.metric("中央値", f"{int(median_res[-1]):,}万")
            c4.metric("不調時 (下位20%)", f"{int(bottom_20_res[-1]):,}万")

            # グラフ
            fig, ax = plt.subplots(figsize=(10, 6))
            age_axis = np.arange(current_age, end_age + 1)
            
            for age, cost in education_cost_map.items():
                if cost > 0: ax.axvspan(age, age+1, color='cyan', alpha=0.1)
            
            for y in range(years):
                age = current_age + y
                flow = cashflow_map.get(age, 0)
                if flow < 0: ax.axvspan(age, age+1, color='orange', alpha=0.1)
                
                if housing_info["type"] != "none":
                    if housing_info["start_age"] <= age <= housing_info["end_age"]:
                         ax.axvspan(age, age+1, ymin=0, ymax=0.05, color='purple', alpha=0.5)

            ax.plot(age_axis, principal_assets, color='gray', linewidth=2, linestyle='-', label='積立元本')
            ax.plot(age_axis, deterministic_assets, color='orange', linewidth=3, linestyle=':', label='単純計算')
            ax.plot(age_axis, median_res, color='blue', linewidth=2, label='中央値')
            ax.plot(age_axis, top_20_res, color='green', linestyle='--', linewidth=1, label='好調 (上位20%)')
            ax.plot(age_axis, bottom_20_res, color='red', linestyle='--', linewidth=1, label='不調 (下位20%)')
            
            ax.set_title("資産推移", fontsize=14)
            ax.set_xlabel("年齢")
            ax.set_ylabel("資産額 (万円)")
            ax.legend()
            ax.grid(True, linestyle='--', alpha=0.7)
            ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: f'{int(x):,}'))
            st.pyplot(fig)
            
            st.caption("※ グラフ背景の色について：")
            st.caption("🟦 **水色**: 教育費がかかる期間")
            st.caption("🟧 **オレンジ**: 収支が赤字（貯金取崩し）の期間")
            st.caption("🟩 **緑色**: 上記2つが重なっている期間（教育費負担があり、かつ赤字の期間）")
            st.caption("🟪 **紫の帯(下部)**: 住宅ローン返済期間")

            # ==========================================
            # ★ AI相談機能（ChatGPT連携）
            # ==========================================
            st.divider()
            st.subheader("🤖 AI（ChatGPT）にシミュレーション結果を相談する")
            st.info("以下のボタンを押すとChatGPTが起動し、今回の結果を元にしたアドバイスを自動でリクエストします。")
            
            prompt_text = f"""あなたは優秀なファイナンシャルプランナー（FP）です。
以下の家計シミュレーション結果をもとに、具体的な改善アドバイスを提示してください。

【基本情報】
・現在の年齢: {current_age}歳
・現在の資産: {current_assets}万円
・想定利回り: {mean_return_pct}% / インフレ率: {inflation_rate_pct}%

【シミュレーション結果 ({end_age}歳時点)】
・資産が底をつかない確率(生存率): {100 - ruin_prob:.1f}%
・想定される資産額(中央値): {int(median_res[-1]):,}万円
・最悪のケース(下位20%): {int(bottom_20_res[-1]):,}万円

【相談内容】
この結果を踏まえて、将来の家計破綻リスクを減らし、より安心できるライフプランを築くための具体的なアクションプランや見直しポイントを3つ教えてください。
"""
            # URLエンコードしてChatGPTのリンクを生成
            encoded_prompt = urllib.parse.quote(prompt_text)
            chatgpt_url = f"https://chatgpt.com/?q={encoded_prompt}"
            
            st.link_button("💬 ChatGPTを開いて相談する", chatgpt_url, type="primary")
            
            with st.expander("送信されるプロンプト（相談内容）を確認・手動コピーする"):
                st.text_area("以下の内容がChatGPTに送信されます", value=prompt_text, height=250)

            st.divider()
            
            # --- 表1: 資産額分布 (1歳ごと) ---
            st.subheader("📋 詳細データ: 資産額の分布 (1歳ごと)")
            
            step = 1 
            t_ages = list(range(current_age, end_age + 1, step))
            if t_ages[-1] != end_age: t_ages.append(end_age)
            
            ranges = [
                (90, 100, "上位 10%"), (80, 90, "11% - 20%"), (70, 80, "21% - 30%"), (60, 70, "31% - 40%"),
                (50, 60, "41% - 50% (中央)"), (40, 50, "51% - 60%"), (30, 40, "61% - 70%"), (20, 30, "71% - 80%"),
                (10, 20, "81% - 90%"), (0, 10, "91% - 100% (下位)")
            ]
            
            d_data = {"ランク": [r[2] for r in ranges]}
            r_data = {"指標": ["単純計算", "積立元本"]}

            for ta in t_ages:
                col = f"{ta}歳"
                idx = ta - current_age
                vals = np.sort(simulation_results[:, idx])
                col_vals = []
                for s, e, _ in ranges:
                    idx_s, idx_e = int(num_simulations * s / 100), int(num_simulations * e / 100)
                    subset = vals[idx_s:idx_e]
                    avg = np.mean(subset) if len(subset) > 0 else 0
                    col_vals.append(f"{int(avg):,} 万円")
                d_data[col] = col_vals
                
                c_vals = []
                c_vals.append(f"{int(deterministic_assets[idx]):,} 万円" if idx < len(deterministic_assets) else "-")
                c_vals.append(f"{int(principal_assets[idx]):,} 万円" if idx < len(principal_assets) else "-")
                r_data[col] = c_vals

            # ヘッダー固定表示
            df_dist = pd.DataFrame(d_data)
            df_dist.set_index("ランク", inplace=True)
            st.dataframe(df_dist, use_container_width=True)
            
            st.caption("👇 比較用データ")
            df_ref = pd.DataFrame(r_data)
            df_ref.set_index("指標", inplace=True)
            st.dataframe(df_ref, use_container_width=True)

            # --- 表2: 教育費内訳 ---
            st.divider()
            st.subheader("🎓 教育費の内訳詳細")
            edu_rows = []
            grand_total = 0
            c_totals = [0]*len(st.session_state.children_list)

            for y in range(years + 1):
                p_age = current_age + y
                y_tot = 0
                row = {"親の年齢": f"{p_age}歳"}
                has = False
                for i, child in enumerate(st.session_state.children_list):
                    c_age = child["age"] + y
                    stg = get_school_stage(c_age, child["course"])
                    if stg:
                        cost = EDU_COSTS[child["course"]][stg]
                        y_tot += cost
                        c_totals[i] += cost
                        grand_total += cost
                        sn = STAGE_NAMES.get(stg, stg)
                        row[f"子供{i+1}"] = f"{c_age}歳({sn}): {cost}万"
                        has = True
                    else:
                        row[f"子供{i+1}"] = "-"
                if has:
                    row["教育費合計"] = f"▲{y_tot}万円"
                    edu_rows.append(row)
            
            if edu_rows:
                total_row = {"親の年齢": "合計"}
                for i, t in enumerate(c_totals): total_row[f"子供{i+1}"] = f"{t:,}万円"
                total_row["教育費合計"] = f"{grand_total:,}万円"
                edu_rows.append(total_row)
                
                # ヘッダー固定表示
                df_edu = pd.DataFrame(edu_rows)
                df_edu.set_index("親の年齢", inplace=True)
                st.dataframe(df_edu, use_container_width=True)
            else:
                st.info("教育費がかかる期間はありません。")
                
            # --- 表3: 住宅ローン内訳 ---
            if housing_info["type"] != "none":
                st.divider()
                st.subheader("🏠 住宅ローン返済の内訳詳細 (金利変動対応)")
                loan_rows = []
                
                for y in range(years + 1):
                    p_age = current_age + y
                    if p_age <= housing_info["end_age"] + 3:
                        if housing_info["start_age"] <= p_age <= housing_info["end_age"]:
                            info = housing_info["schedule"][p_age]
                            base_pmt = housing_info["base_pmt"]
                            actual_pmt = info["annual_pmt"]
                            
                            # 金利上昇によって増えた支払額（初年度返済額からの差額）
                            increase = max(0, actual_pmt - base_pmt)
                            
                            loan_rows.append({
                                "年齢": f"{p_age}歳", 
                                "状態": "返済中", 
                                "適用金利": f"{info['rate']:.2f} %", 
                                "年間返済額": f"{int(actual_pmt):,} 万円", 
                                "増加分(収支マイナス)": f"▲ {int(increase):,} 万円" if increase > 0 else "0 万円",
                                "年末残高": f"{int(info['balance']):,} 万円"
                            })
                        elif p_age > housing_info["end_age"]:
                            loan_rows.append({
                                "年齢": f"{p_age}歳", 
                                "状態": "完済 🎉", 
                                "適用金利": "-", 
                                "年間返済額": "-", 
                                "増加分(収支マイナス)": "-", 
                                "年末残高": "-"
                            })
                        elif p_age < housing_info["start_age"]:
                            loan_rows.append({
                                "年齢": f"{p_age}歳", 
                                "状態": "購入前", 
                                "適用金利": "-", 
                                "年間返済額": "-", 
                                "増加分(収支マイナス)": "-", 
                                "年末残高": "-"
                            })
                            
                if loan_rows:
                    df_loan = pd.DataFrame(loan_rows)
                    df_loan.set_index("年齢", inplace=True)
                    st.dataframe(df_loan, use_container_width=True)

        else:
            st.error("終了年齢は現在の年齢より大きくしてください。")

    except Exception as e:
        st.error(f"エラーが発生しました: {e}")
