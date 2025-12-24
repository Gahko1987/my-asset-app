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
# ▼ 教育費データ（年額・万円） ▼
# ==========================================
EDU_COSTS = {
    "all_public": { "kindergarten": 23, "elementary": 35, "junior_high": 54, "high_school": 52, "university": 120 },
    "private_uni": { "kindergarten": 23, "elementary": 35, "junior_high": 54, "high_school": 52, "university": 172 },
    "all_private": { "kindergarten": 36, "elementary": 170, "junior_high": 144, "high_school": 105, "university": 172 },
    "vocational": { "kindergarten": 23, "elementary": 35, "junior_high": 54, "high_school": 52, "vocational_school": 130 },
    "junior_college": { "kindergarten": 23, "elementary": 35, "junior_high": 54, "high_school": 52, "junior_college": 120 },
    "high_school_grad": { "kindergarten": 23, "elementary": 35, "junior_high": 54, "high_school": 52 }
}

def get_school_stage(age, course_type):
    if 3 <= age <= 5: return "kindergarten"
    if 6 <= age <= 11: return "elementary"
    if 12 <= age <= 14: return "junior_high"
    if 15 <= age <= 17: return "high_school"
    if 18 <= age <= 21:
        if course_type in ["all_public", "private_uni", "all_private"]: return "university"
        if course_type == "vocational" and age <= 19: return "vocational_school"
        if course_type == "junior_college" and age <= 19: return "junior_college"
    return None

STAGE_NAMES = {
    "kindergarten": "幼", "elementary": "小", "junior_high": "中", 
    "high_school": "高", "university": "大", "vocational_school": "専", "junior_college": "短"
}

# ==========================================
# ▼ 基本設定パネル ▼
# ==========================================
with st.expander("▼ 基本設定（ここをタップして変更）", expanded=True):
    col_b1, col_b2 = st.columns(2)
    
    with col_b1:
        current_age = st.number_input("現在の年齢", 0, 100, 35, key="input_current_age")
        current_assets = st.number_input("現在の資産 (万円)", 0, 500000, 500)
        inflation_rate_pct = st.slider("インフレ率 (%)", 0.0, 5.0, 2.0, 0.1)

        st.markdown("---")
        st.markdown("##### 👴 年金設定")
        use_pension = st.checkbox("年金を考慮する", value=True)
        if use_pension:
            pension_start_age = st.number_input("年金受給開始年齢", 60, 75, 65)
            pension_annual = st.number_input("世帯年金の受給額 (年額・万円)", 0, 1000, 240)
        else:
            pension_start_age = 65; pension_annual = 0

    with col_b2:
        mean_return_pct = st.slider("想定利回り (年率%)", 0.0, 20.0, 5.0, 0.1)
        st.caption("📈 目安: オルカン 5-8%, S&P500 7-10%")
        risk_std_pct = st.slider("リスク (標準偏差%)", 0.0, 40.0, 15.0, 0.5)
        st.caption("📊 目安: オルカン 17-20%, S&P500 19-23%")

    # ★住宅ローン設定 (修正版: 3択ラジオボタン)
    st.markdown("---")
    st.markdown("##### 🏠 住宅・ローン設定")
    
    housing_option = st.radio(
        "住居・ローンの状況", 
        ["考慮しない (賃貸・ローンなし)", "これから購入予定", "すでに購入済み (ローン返済中)"],
        horizontal=True
    )
    
    housing_info = {"active": False, "annual_pmt": 0, "start_age": 0, "end_age": 0}

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
        
        loan_principal = h_price - h_down
        start_pay_age = h_age
        end_pay_age = h_age + h_years - 1
        
        # 共通計算へ
        if loan_principal > 0:
            r = h_rate / 100 / 12
            n = h_years * 12
            monthly_pmt = loan_principal * (r * (1+r)**n) / ((1+r)**n - 1) if r > 0 else loan_principal / n
            annual_pmt = monthly_pmt * 12
            housing_info = {"active": True, "annual_pmt": annual_pmt, "start_age": start_pay_age, "end_age": end_pay_age}
            st.info(f"📅 **ローン返済**: {start_pay_age}歳〜{end_pay_age}歳まで、年額 約{int(annual_pmt):,}万円")

    elif housing_option == "すでに購入済み (ローン返済中)":
        h_col1, h_col2 = st.columns(2)
        with h_col1:
            loan_principal = st.number_input("現在のローン残高 (万円)", 0, 50000, 3000)
            h_rate = st.number_input("金利 (%)", 0.0, 10.0, 1.5, 0.1)
        with h_col2:
            h_years_remain = st.number_input("残り返済期間 (年)", 1, 50, 25)
        
        start_pay_age = current_age
        end_pay_age = current_age + h_years_remain - 1
        
        # 共通計算へ
        if loan_principal > 0:
            r = h_rate / 100 / 12
            n = h_years_remain * 12
            monthly_pmt = loan_principal * (r * (1+r)**n) / ((1+r)**n - 1) if r > 0 else loan_principal / n
            annual_pmt = monthly_pmt * 12
            housing_info = {"active": True, "annual_pmt": annual_pmt, "start_age": start_pay_age, "end_age": end_pay_age}
            st.info(f"📅 **ローン返済**: {start_pay_age}歳〜{end_pay_age}歳まで、年額 約{int(annual_pmt):,}万円")

    else:
        # "考慮しない" が選ばれた場合
        st.caption("※ 住宅ローン計算は行いません（家賃などは「ライフステージ収支」に入力してください）。")


# 計算用数値
mean_return = mean_return_pct / 100
risk_std = risk_std_pct / 100
inflation_rate = inflation_rate_pct / 100
real_mean_return = mean_return - inflation_rate

st.divider()

# ==========================================
# データ管理
# ==========================================
if "phases_list" not in st.session_state:
    st.session_state.phases_list = [
        {"end": 45, "amount": 100},
        {"end": 60, "amount": 200},
        {"end": 65, "amount": 100},
        {"end": 100, "amount": -100}, 
    ]
if "events_list" not in st.session_state:
    st.session_state.events_list = [
        {"age": 60, "amount": 1500, "name": "退職金"},
        {"age": 40, "amount": -300, "name": "車購入"},
    ]
if "children_list" not in st.session_state:
    st.session_state.children_list = [
        {"age": 5, "course": "private_uni"}, 
        {"age": 2, "course": "private_uni"}
    ]

# コールバック関数
def add_phase():
    last_end = st.session_state.phases_list[-1]["end"] if st.session_state.phases_list else current_age
    st.session_state.phases_list.append({"end": last_end + 5, "amount": 0})
def remove_phase():
    if len(st.session_state.phases_list) > 1: st.session_state.phases_list.pop()
def add_event():
    st.session_state.events_list.append({"age": current_age + 5, "amount": -100, "name": "新しいイベント"})
def remove_event(index):
    st.session_state.events_list.pop(index)
def add_child():
    st.session_state.children_list.append({"age": 0, "course": "private_uni"})
def remove_child(index):
    st.session_state.children_list.pop(index)

# ==========================================
# 入力エリア
# ==========================================
col1, col2 = st.columns(2)

with col1:
    st.subheader("1. ライフステージ収支")
    st.info("住居費を除いた、ベースの生活収支を入力してください。")
    start_age_tracker = current_age
    for i, phase in enumerate(st.session_state.phases_list):
        st.markdown(f"**🔹 第{i+1}期間 ({start_age_tracker}歳 〜 )**")
        c_p1, c_p2 = st.columns([1, 1])
        with c_p1:
            min_val = start_age_tracker
            current_end_val = int(phase["end"])
            if current_end_val < min_val: current_end_val = min_val
            new_end = st.number_input(f"何歳まで？ (第{i+1}期間)", min_value=min_val, max_value=150, value=current_end_val, key=f"phase_end_{i}")
            st.session_state.phases_list[i]["end"] = new_end
        with c_p2:
            new_amount = st.number_input(f"年間の収支 (万円)", value=int(phase["amount"]), key=f"phase_amount_{i}")
            st.session_state.phases_list[i]["amount"] = new_amount
        start_age_tracker = new_end + 1
        st.markdown("---")
    b_col1, b_col2 = st.columns(2)
    with b_col1: st.button("➕ 期間を追加", on_click=add_phase, use_container_width=True)
    with b_col2: st.button("🗑️ 最後の期間を削除", on_click=remove_phase, use_container_width=True)

with col2:
    st.subheader("2. 子供の教育費 (自動計算)")
    st.info("お子様の年齢を入れると、学費を自動で収支から引きます。")
    for i, child in enumerate(st.session_state.children_list):
        with st.container(border=True):
            c_head1, c_head2 = st.columns([2, 1])
            with c_head1: st.markdown(f"**👶 お子様 {i+1}**")
            with c_head2:
                if st.button("🗑️ 削除", key=f"del_child_{i}"): remove_child(i); st.rerun()
            c_in1, c_in2 = st.columns(2)
            with c_in1:
                new_age = st.number_input("現在の年齢", 0, 30, int(child["age"]), key=f"child_age_{i}")
                st.session_state.children_list[i]["age"] = new_age
            with c_in2:
                course_opts = {"all_public": "国公立大 (標準)", "private_uni": "私立大学 (平均)", "all_private": "すべて私立 (手厚い)", "vocational": "専門学校 (2年)", "junior_college": "短期大学 (2年)", "high_school_grad": "高校卒業まで"}
                current_c = child["course"] if child["course"] in course_opts else "private_uni"
                new_course = st.selectbox("進学コース", options=list(course_opts.keys()), format_func=lambda x: course_opts[x], index=list(course_opts.keys()).index(current_c), key=f"child_course_{i}")
                st.session_state.children_list[i]["course"] = new_course
    st.button("➕ 子供を追加", on_click=add_child, use_container_width=True)
    
    st.divider()
    st.subheader("3. その他のイベント・一時金")
    for i, event in enumerate(st.session_state.events_list):
        with st.container(border=True):
            e_col1, e_col2 = st.columns([2, 1])
            with e_col1: st.markdown(f"**イベント {i+1}**")
            with e_col2:
                if st.button("🗑️ 削除", key=f"del_event_{i}"): remove_event(i); st.rerun()
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

# ==========================================
# シミュレーション実行
# ==========================================
st.divider()
if st.button("シミュレーションを実行する (10,000回)", type="primary"):
    try:
        end_age = st.session_state.phases_list[-1]["end"] if st.session_state.phases_list else 100
        years = end_age - current_age
        
        if years <= 0:
            st.error(f"エラー：終了年齢({end_age}歳)は、現在の年齢({current_age}歳)より未来に設定してください。")
        else:
            num_simulations = 10000 
            
            # 1. 基本収支マップ
            cashflow_map = {}
            temp_start = current_age
            for p in st.session_state.phases_list:
                end_val = int(p["end"])
                amount_val = int(p["amount"])
                if temp_start <= end_val:
                    for age in range(temp_start, end_val + 1):
                        cashflow_map[age] = amount_val
                temp_start = end_val + 1

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

            # 3. 年金 & 住宅ローン
            for y in range(years + 1):
                age = current_age + y
                # 年金
                if use_pension and age >= pension_start_age:
                    cashflow_map[age] = cashflow_map.get(age, 0) + pension_annual
                # 住宅ローン
                if housing_info["active"]:
                    if housing_info["start_age"] <= age <= housing_info["end_age"]:
                        cashflow_map[age] = cashflow_map.get(age, 0) - housing_info["annual_pmt"]

            # 4. イベントマップ
            event_map = {}
            for e in st.session_state.events_list:
                event_map[int(e["age"])] = event_map.get(int(e["age"]), 0) + int(e["amount"])
            
            # --- シミュレーション計算 ---
            deterministic_assets = [current_assets]
            principal_assets = [current_assets]
            simulation_results = np.zeros((num_simulations, years + 1))
            
            for year in range(years):
                age = current_age + year
                flow = cashflow_map.get(age, 0)
                spot = event_map.get(age, 0)
                
                # A: 単純計算
                prev_d = deterministic_assets[-1]
                if prev_d <= 0: new_d = 0
                else:
                    new_d = (prev_d + flow + spot) * (1 + real_mean_return)
                    if new_d < 0: new_d = 0
                deterministic_assets.append(new_d)
                
                # B: 積立元本
                prev_p = principal_assets[-1]
                new_p = prev_p + flow + spot
                if new_p < 0: new_p = 0
                principal_assets.append(new_p)

            # C: モンテカルロ
            progress_bar = st.progress(0)
            for i in range(num_simulations):
                assets = [current_assets]
                if i % 100 == 0: progress_bar.progress(i / num_simulations)
                for year in range(years):
                    age = current_age + year
                    flow = cashflow_map.get(age, 0)
                    spot = event_map.get(age, 0)
                    r = np.random.normal(real_mean_return, risk_std)
                    prev = assets[-1]
                    if prev <= 0: new_val = 0
                    else:
                        new_val = (prev + flow + spot) * (1 + r)
                        if new_val < 0: new_val = 0
                    assets.append(new_val)
                simulation_results[i, :] = assets
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
            if housing_info["active"]:
                total_loan = housing_info["annual_pmt"] * (housing_info["end_age"] - housing_info["start_age"] + 1)
                st.warning(f"🏠 **住宅ローン**: {housing_info['start_age']}歳〜{housing_info['end_age']}歳まで、総額 約{int(total_loan):,}万円 を返済")

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
            
            # 色分け
            for age, cost in education_cost_map.items():
                if cost > 0: ax.axvspan(age, age+1, color='cyan', alpha=0.1)
            
            for y in range(years):
                age = current_age + y
                flow = cashflow_map.get(age, 0)
                if flow < 0: ax.axvspan(age, age+1, color='orange', alpha=0.1)
                
                # 住宅ローン期間 (紫)
                if housing_info["active"]:
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
            
            st.caption("🟦 **水色背景**: 教育費負担期間 / 🟧 **オレンジ背景**: 赤字期間")
            st.caption("🟪 **紫の帯(下部)**: 住宅ローン返済期間")

            st.divider()
            
            # --- 表1: 資産額分布 (10歳刻み) ---
            st.subheader("📋 詳細データ: 資産額の分布 (10歳刻み)")
            step = 10
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

            st.dataframe(pd.DataFrame(d_data), hide_index=True, use_container_width=True)
            st.caption("👇 比較用データ")
            st.dataframe(pd.DataFrame(r_data), hide_index=True, use_container_width=True)

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
                st.dataframe(pd.DataFrame(edu_rows), hide_index=True, use_container_width=True)
            else:
                st.info("教育費がかかる期間はありません。")

    except Exception as e:
        st.error(f"エラー: {e}")
