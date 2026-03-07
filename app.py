import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import japanize_matplotlib
import matplotlib.ticker as ticker

# ==========================================
# ▼ ページ設定 ▼
# ==========================================
st.set_page_config(page_title="資産ライフプランシミュレーター", layout="wide")

st.title("📊 資産＆ライフプラン シミュレーター")

# ==========================================
# ▼ 教育費データ（年額・万円） ▼
# ==========================================
EDU_COSTS = {
    "all_public": { "kindergarten": 23, "elementary": 35, "junior_high": 54, "high_school": 52, "university": 120 },
    "private_uni": { "kindergarten": 23, "elementary": 35, "junior_high": 54, "high_school": 52, "university": 172 },
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
    if 18 <= age <= 23 and course_type == "medical_private": return "medical_uni"
    if 18 <= age <= 21:
        if course_type in ["all_public", "private_uni", "all_private"]: return "university"
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
# ▼ サイドバー・基本設定 ▼
# ==========================================
with st.expander("▼ 基本設定（ここをタップして変更）", expanded=True):
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        current_age = st.number_input("現在の年齢", 0, 100, 35, key="input_current_age")
        current_assets = st.number_input("現在の資産 (万円)", 0, 500000, 500)
        inflation_rate_pct = st.slider("インフレ率 (%)", 0.0, 5.0, 2.0, 0.1)

    with col_b2:
        mean_return_pct = st.slider("想定利回り (年率%)", 0.0, 20.0, 5.0, 0.1)
        risk_std_pct = st.slider("リスク (標準偏差%)", 0.0, 40.0, 15.0, 0.5)

    # --- 住宅ローン設定 ---
    st.markdown("---")
    st.markdown("##### 🏠 住宅・ローン設定")
    housing_option = st.radio(
        "住居・ローンの状況", 
        ["考慮しない (賃貸・ローンなし)", "これから購入予定", "すでに購入済み (ローン返済中)"],
        horizontal=True
    )
    
    housing_info = {"type": "none", "annual_pmt": 0, "start_age": 0, "end_age": 0, "current_rent_saved": 0}

    if housing_option == "これから購入予定":
        h_col1, h_col2, h_col3 = st.columns(3)
        with h_col1:
            h_age = st.number_input("購入年齢", current_age, 100, current_age + 5)
            h_price = st.number_input("物件価格 (万円)", 0, 50000, 4000)
        with h_col2:
            h_down = st.number_input("頭金 (万円)", 0, h_price, 500)
            h_rate = st.number_input("金利 (%)", 0.0, 10.0, 1.5, 0.1)
        with h_col3:
            h_years = st.number_input("返済期間 (年)", 1, 50, 35)
            current_rent_val = st.number_input("現在の住居費 (年額)", 0, 1000, 120)
        
        loan_principal = h_price - h_down
        if loan_principal > 0:
            r = h_rate / 100 / 12
            n = h_years * 12
            monthly_pmt = loan_principal * (r * (1+r)**n) / ((1+r)**n - 1) if r > 0 else loan_principal / n
            housing_info = {"type": "future", "annual_pmt": monthly_pmt * 12, "start_age": h_age, "end_age": h_age + h_years - 1, "current_rent_saved": current_rent_val}

    elif housing_option == "すでに購入済み (ローン返済中)":
        h_col1, h_col2 = st.columns(2)
        with h_col1:
            loan_principal = st.number_input("現在のローン残高 (万円)", 0, 50000, 3000)
            h_rate = st.number_input("金利 (%)", 0.0, 10.0, 1.5, 0.1)
        with h_col2:
            h_years_remain = st.number_input("残り返済期間 (年)", 1, 50, 25)
        
        if loan_principal > 0:
            r = h_rate / 100 / 12
            n = h_years_remain * 12
            monthly_pmt = loan_principal * (r * (1+r)**n) / ((1+r)**n - 1) if r > 0 else loan_principal / n
            housing_info = {"type": "already", "annual_pmt": monthly_pmt * 12, "start_age": current_age, "end_age": current_age + h_years_remain - 1, "current_rent_saved": 0}

    # --- 年金設定 ---
    st.markdown("---")
    st.markdown("##### 👴 年金設定")
    use_pension = st.checkbox("年金を考慮する", value=True)
    if use_pension:
        p_col1, p_col2 = st.columns(2)
        with p_col1: pension_start_age = st.number_input("年金受給開始年齢", 60, 75, 65)
        with p_col2: pension_annual = st.number_input("世帯年金の受給額 (年額・万円)", 0, 1000, 240)
    else:
        pension_start_age = 65; pension_annual = 0

# 計算用共通変数
mean_return = mean_return_pct / 100
risk_std = risk_std_pct / 100
inflation_rate = inflation_rate_pct / 100
real_mean_return = mean_return - inflation_rate

# ==========================================
# ▼ データ管理 (Session State) ▼
# ==========================================
if "phases_list" not in st.session_state:
    st.session_state.phases_list = [{"end": 45, "amount": 100}, {"end": 60, "amount": 200}, {"end": 65, "amount": 100}, {"end": 100, "amount": -100}]
if "events_list" not in st.session_state:
    st.session_state.events_list = [{"age": 60, "amount": 1500, "name": "退職金"}, {"age": 40, "amount": -300, "name": "車購入"}]
if "children_list" not in st.session_state:
    st.session_state.children_list = [{"age": 5, "course": "private_uni"}, {"age": 2, "course": "private_uni"}]

def add_phase(): st.session_state.phases_list.append({"end": st.session_state.phases_list[-1]["end"] + 5, "amount": 0})
def remove_phase(): 
    if len(st.session_state.phases_list) > 1: st.session_state.phases_list.pop()
def remove_child(index): st.session_state.children_list.pop(index)
def remove_event(index): st.session_state.events_list.pop(index)

# ==========================================
# ▼ 入力・UIエリア ▼
# ==========================================
col1, col2 = st.columns(2)
with col1:
    st.subheader("1. ライフステージ収支")
    start_age_tracker = current_age
    for i, phase in enumerate(st.session_state.phases_list):
        st.markdown(f"**🔹 第{i+1}期間 ({start_age_tracker}歳 〜 )**")
        c_p1, c_p2 = st.columns(2)
        with c_p1: phase["end"] = st.number_input(f"何歳まで？", start_age_tracker, 150, int(phase["end"]), key=f"p_end_{i}")
        with c_p2: phase["amount"] = st.number_input(f"年間の収支 (万円)", value=int(phase["amount"]), key=f"p_amt_{i}")
        start_age_tracker = phase["end"] + 1
    st.button("➕ 期間追加", on_click=add_phase)
    st.button("🗑️ 期間削除", on_click=remove_phase)

with col2:
    st.subheader("2. 子供の教育費")
    for i, child in enumerate(st.session_state.children_list):
        with st.container(border=True):
            st.markdown(f"**👶 お子様 {i+1}**")
            child["age"] = st.number_input("現在の年齢", 0, 30, int(child["age"]), key=f"c_age_{i}")
            child["course"] = st.selectbox("進学コース", options=list(EDU_COSTS.keys()), key=f"c_course_{i}")
            if st.button("🗑️ 削除", key=f"c_del_{i}"): remove_child(i); st.rerun()
    if st.button("➕ 子供追加"): st.session_state.children_list.append({"age": 0, "course": "private_uni"}); st.rerun()

# ==========================================
# ▼ シミュレーション実行 ▼
# ==========================================
st.divider()
if st.button("シミュレーションを実行する (10,000回)", type="primary"):
    end_age = st.session_state.phases_list[-1]["end"]
    years = end_age - current_age
    num_simulations = 10000
    
    # マッピング作成
    cashflow_map = {}
    temp_start = current_age
    for p in st.session_state.phases_list:
        for age in range(temp_start, int(p["end"]) + 1): cashflow_map[age] = int(p["amount"])
        temp_start = int(p["end"]) + 1

    education_cost_map = {}
    for child in st.session_state.children_list:
        for y in range(years + 1):
            parent_age = current_age + y
            stage = get_school_stage(child["age"] + y, child["course"])
            if stage:
                cost = EDU_COSTS[child["course"]][stage]
                cashflow_map[parent_age] = cashflow_map.get(parent_age, 0) - cost
                education_cost_map[parent_age] = education_cost_map.get(parent_age, 0) + cost

    for y in range(years + 1):
        age = current_age + y
        if use_pension and age >= pension_start_age: cashflow_map[age] = cashflow_map.get(age, 0) + pension_annual
        if housing_info["type"] == "already" and age > housing_info["end_age"]:
            cashflow_map[age] = cashflow_map.get(age, 0) + housing_info["annual_pmt"]
        elif housing_info["type"] == "future":
            if age >= housing_info["start_age"]:
                cashflow_map[age] = cashflow_map.get(age, 0) + housing_info["current_rent_saved"]
                if age <= housing_info["end_age"]: cashflow_map[age] = cashflow_map.get(age, 0) - housing_info["annual_pmt"]

    event_map = {int(e["age"]): int(e["amount"]) for e in st.session_state.events_list}

    # 計算実行
    deterministic_assets = [current_assets]; principal_assets = [current_assets]
    simulation_results = np.zeros((num_simulations, years + 1))
    
    for year in range(years):
        age = current_age + year
        flow = cashflow_map.get(age, 0) + event_map.get(age, 0)
        deterministic_assets.append(max(0, (deterministic_assets[-1] + flow) * (1 + real_mean_return)))
        principal_assets.append(max(0, principal_assets[-1] + flow))

    for i in range(num_simulations):
        assets = [current_assets]
        for year in range(years):
            age = current_age + year
            r = np.random.normal(real_mean_return, risk_std)
            new_val = (assets[-1] + cashflow_map.get(age, 0) + event_map.get(age, 0)) * (1 + r)
            assets.append(max(0, new_val))
        simulation_results[i, :] = assets

    # 結果表示
    median_res = np.percentile(simulation_results, 50, axis=0)
    bottom_20_res = np.percentile(simulation_results, 20, axis=0)
    top_20_res = np.percentile(simulation_results, 80, axis=0)
    ruin_prob = (np.sum(simulation_results[:, -1] == 0) / num_simulations) * 100

    c1, c2, c3 = st.columns(3)
    c1.metric(f"{end_age}歳生存率", f"{100 - ruin_prob:.1f}%")
    c2.metric("中央値", f"{int(median_res[-1]):,}万")
    c3.metric("不調時 (20%)", f"{int(bottom_20_res[-1]):,}万")

    # グラフ表示
    fig, ax = plt.subplots(figsize=(10, 5))
    age_axis = np.arange(current_age, end_age + 1)
    ax.plot(age_axis, principal_assets, color='gray', label='元本')
    ax.plot(age_axis, median_res, color='blue', label='中央値')
    ax.fill_between(age_axis, bottom_20_res, top_20_res, color='blue', alpha=0.1, label='80%範囲')
    ax.set_xlabel("年齢"); ax.set_ylabel("資産 (万円)"); ax.legend(); ax.grid(True)
    st.pyplot(fig); plt.close(fig)

    # ==========================================
    # ▼ 1年ごとの詳細データテーブル ▼
    # ==========================================
    st.divider()
    st.subheader("📅 年度別シミュレーション詳細 (1年単位)")
    yearly_data = []
    for y in range(years + 1):
        age = current_age + y
        total_cf = cashflow_map.get(age, 0) + event_map.get(age, 0)
        yearly_data.append({
            "年齢": f"{age}歳",
            "年間収支(万)": int(total_cf),
            "積立元本(万)": int(principal_assets[y]),
            "中央値(万)": int(median_res[y]),
            "不調時20%(万)": int(bottom_20_res[y])
        })
    st.dataframe(pd.DataFrame(yearly_data), use_container_width=True, hide_index=True)
