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
# 文部科学省「子供の学習費調査」などを参考に概算
# ==========================================
EDU_COSTS = {
    # 1. すべて国公立 (大学4年)
    "all_public": {
        "kindergarten": 23, "elementary": 35, "junior_high": 54, "high_school": 52,
        "university": 120 # 国立大
    },
    # 2. 大学だけ私立 (大学4年)
    "private_uni": {
        "kindergarten": 23, "elementary": 35, "junior_high": 54, "high_school": 52,
        "university": 172 # 私立大(文系)
    },
    # 3. すべて私立 (大学4年)
    "all_private": {
        "kindergarten": 36, "elementary": 170, "junior_high": 144, "high_school": 105,
        "university": 172 # 私立大(文系)
    },
    # 4. 専門学校 (2年)
    "vocational": {
        "kindergarten": 23, "elementary": 35, "junior_high": 54, "high_school": 52,
        "vocational_school": 130 # 専門学校(概算)
    },
    # 5. 短期大学 (2年)
    "junior_college": {
        "kindergarten": 23, "elementary": 35, "junior_high": 54, "high_school": 52,
        "junior_college": 120 # 短大(概算)
    },
    # 6. 高校卒業まで (進学なし)
    "high_school_grad": {
        "kindergarten": 23, "elementary": 35, "junior_high": 54, "high_school": 52
        # 大学費用なし
    }
}

# 学年と年齢の対応ロジック（コースによって期間を変える）
def get_school_stage(age, course_type):
    if 3 <= age <= 5: return "kindergarten"
    if 6 <= age <= 11: return "elementary"
    if 12 <= age <= 14: return "junior_high"
    if 15 <= age <= 17: return "high_school"
    
    # 18歳以降の分岐
    if 18 <= age <= 21:
        # 4年制大学へ行くコース
        if course_type in ["all_public", "private_uni", "all_private"]:
            return "university"
        
        # 2年制（専門・短大）へ行くコース (20,21歳は無し)
        if course_type == "vocational" and age <= 19:
            return "vocational_school"
        if course_type == "junior_college" and age <= 19:
            return "junior_college"
            
        # 高卒コース (18歳以降なし)
        if course_type == "high_school_grad":
            return None
            
    return None

# 表表示用の略称
STAGE_NAMES = {
    "kindergarten": "幼",
    "elementary": "小",
    "junior_high": "中",
    "high_school": "高",
    "university": "大",
    "vocational_school": "専", # 専門学校
    "junior_college": "短"    # 短大
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
        {"end": 45, "amount": 100},
        {"end": 60, "amount": 200},
        {"end": 65, "amount": 100},
        {"end": 100, "amount": -200},
    ]

# 2. イベントの初期データ
if "events_list" not in st.session_state:
    st.session_state.events_list = [
        {"age": 60, "amount": 1500, "name": "退職金"},
        {"age": 40, "amount": -300, "name": "車購入"},
    ]

# 3. 子供情報の初期データ
if "children_list" not in st.session_state:
    st.session_state.children_list = [
        {"age": 5, "course": "private_uni"}, 
        {"age": 2, "course": "private_uni"}
    ]

# コールバック関数
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

def add_child():
    st.session_state.children_list.append({"age": 0, "course": "private_uni"})

def remove_child(index):
    st.session_state.children_list.pop(index)

# ==========================================
# メイン画面入力エリア
# ==========================================
col1, col2 = st.columns(2)

# === 左側：ライフステージ入力 ===
with col1:
    st.subheader("1. ライフステージ収支")
    st.info("子供の学費を除いた、基本的な生活収支を入力してください。")

    start_age_tracker = current_age
    
    for i, phase in enumerate(st.session_state.phases_list):
        st.markdown(f"**🔹 第{i+1}期間 ({start_age_tracker}歳 〜 )**")
        
        c_p1, c_p2 = st.columns([1, 1])
        with c_p1:
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


# === 右側：イベント＆子供入力 ===
with col2:
    # --- 子供入力エリア ---
    st.subheader("2. 子供の教育費 (自動計算)")
    st.info("お子様の年齢を入れると、学費を自動で収支から引きます。")
    
    for i, child in enumerate(st.session_state.children_list):
        with st.container(border=True):
            c_head1, c_head2 = st.columns([2, 1])
            with c_head1:
                st.markdown(f"**👶 お子様 {i+1}**")
            with c_head2:
                if st.button("🗑️ 削除", key=f"del_child_{i}"):
                    remove_child(i)
                    st.rerun()

            c_in1, c_in2 = st.columns(2)
            with c_in1:
                new_age = st.number_input("現在の年齢", 0, 30, int(child["age"]), key=f"child_age_{i}")
                st.session_state.children_list[i]["age"] = new_age
            with c_in2:
                # 選択肢の定義（キー：表示名）
                course_opts = {
                    "all_public": "国公立大 (標準)",
                    "private_uni": "私立大学 (平均)",
                    "all_private": "すべて私立 (手厚い)",
                    "vocational": "専門学校 (2年)",
                    "junior_college": "短期大学 (2年)",
                    "high_school_grad": "高校卒業まで"
                }
                current_c = child["course"]
                if current_c not in course_opts: current_c = "private_uni"

                current_idx = list(course_opts.keys()).index(current_c)
                new_course = st.selectbox(
                    "進学コース",
                    options=list(course_opts.keys()),
                    format_func=lambda x: course_opts[x],
                    index=current_idx,
                    key=f"child_course_{i}"
                )
                st.session_state.children_list[i]["course"] = new_course
    
    st.button("➕ 子供を追加", on_click=add_child, use_container_width=True)
    
    st.divider()

    # --- イベント入力エリア ---
    st.subheader("3. その他のイベント・一時金")
    st.caption("住宅購入や退職金など、学費以外の大きな出費・収入。")

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
            
            # --- 収支マップ作成 ---
            cashflow_map = {}
            temp_start = current_age
            for p in st.session_state.phases_list:
                end_val = int(p["end"])
                amount_val = int(p["amount"])
                if temp_start <= end_val:
                    for age in range(temp_start, end_val + 1):
                        cashflow_map[age] = amount_val
                temp_start = end_val + 1

            # --- 教育費計算 ---
            education_cost_map = {}
            for child in st.session_state.children_list:
                c_age = child["age"]
                c_course = child["course"]
                for y in range(40): 
                    current_c_age = c_age + y
                    parent_age = current_age + y
                    if parent_age > end_age: break
                    
                    # コースを引数に渡す
                    stage = get_school_stage(current_c_age, c_course)
                    
                    if stage:
                        cost = EDU_COSTS[c_course][stage]
                        cashflow_map[parent_age] = cashflow_map.get(parent_age, 0) - cost
                        education_cost_map[parent_age] = education_cost_map.get(parent_age, 0) + cost

            # --- イベントマップ作成 ---
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

            # --- B. 積立元本 ---
            principal_assets = [current_assets]
            for year in range(years):
                age = current_age + year
                annual_flow = cashflow_map.get(age, 0)
                spot_flow = event_map.get(age, 0)
                prev_val = principal_assets[-1]
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

            # --- 結果表示 ---
            median_res = np.percentile(simulation_results, 50, axis=0)
            top_10_res = np.percentile(simulation_results, 90, axis=0)
            bottom_10_res = np.percentile(simulation_results, 10, axis=0)
            ruin_prob = (np.sum(simulation_results[:, -1] == 0) / num_simulations) * 100

            st.subheader(f"シミュレーション結果 ({end_age}歳まで)")
            
            total_edu_cost = sum(education_cost_map.values())
            if total_edu_cost > 0:
                st.info(f"🎓 **教育費の合計負担額: 約 {total_edu_cost:,} 万円** が収支から自動で差し引かれています。")

            with st.expander("🔰 数字の見方ガイド", expanded=True):
                st.markdown("""
                * **生存率**: 資産が底をつかない確率。80%以上が目安。
                * **単純計算**: 決まった利回りで増え続けた場合の金額。
                * **中央値**: 最も現実的なシミュレーション結果。
                * **不調時**: 運悪く相場が悪かった場合の結果。
                """)

            res_col1, res_col2, res_col3, res_col4 = st.columns(4)
            res_col1.metric(f"{end_age}歳生存率", f"{100 - ruin_prob:.1f}%")
            res_col2.metric("単純計算", f"{int(deterministic_assets[-1]):,}万")
            res_col3.metric("中央値", f"{int(median_res[-1]):,}万")
            res_col4.metric("不調時", f"{int(bottom_10_res[-1]):,}万")

            fig, ax = plt.subplots(figsize=(10, 6))
            age_axis = np.arange(current_age, end_age + 1)
            
            for age, cost in education_cost_map.items():
                if cost > 0:
                     ax.axvspan(age, age+1, color='cyan', alpha=0.1)
            
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
            
            # 説明書き
            st.caption("※ グラフ背景の色について：")
            st.caption("🟦 **水色の期間**: お子様の教育費がかかっている期間")
            st.caption("🟧 **オレンジの期間**: 年間の収支がマイナス（貯金を取り崩している）期間")

            st.divider()
            
            # --- 表1: 分布詳細 (10%刻み) ---
            st.subheader("📋 詳細データ: 資産額の分布 (10歳刻み)")
            st.caption("各年齢ごとの上位〜下位グループの平均資産額を表示します。")
            
            step_years = 10
            target_ages = list(range(current_age, end_age + 1, step_years))
            if target_ages[-1] != end_age: target_ages.append(end_age)
            
            percentile_ranges = [
                (90, 100, "上位 10%"),
                (80, 90, "11% - 20%"),
                (70, 80, "21% - 30%"),
                (60, 70, "31% - 40%"),
                (50, 60, "41% - 50% (中央)"),
                (40, 50, "51% - 60%"),
                (30, 40, "61% - 70%"),
                (20, 30, "71% - 80%"),
                (10, 20, "81% - 90%"),
                (0, 10, "91% - 100% (下位)")
            ]
            
            dist_data = {"ランク": [label for _, _, label in percentile_ranges]}
            ref_data = {"指標": ["単純計算", "積立元本"]}

            for target_age in target_ages:
                col_name = f"{target_age}歳"
                idx = target_age - current_age
                assets_at_age = np.sort(simulation_results[:, idx])
                
                dist_col = []
                for p_start, p_end, _ in percentile_ranges:
                    s_s = int(num_simulations * (p_start / 100))
                    s_e = int(num_simulations * (p_end / 100))
                    subset = assets_at_age[s_s:s_e]
                    avg = np.mean(subset) if len(subset) > 0 else 0
                    dist_col.append(f"{int(avg):,} 万円")
                dist_data[col_name] = dist_col

                ref_col = []
                if idx < len(deterministic_assets):
                    ref_col.append(f"{int(deterministic_assets[idx]):,} 万円")
                else:
                    ref_col.append("-")
                if idx < len(principal_assets):
                    ref_col.append(f"{int(principal_assets[idx]):,} 万円")
                else:
                    ref_col.append("-")
                ref_data[col_name] = ref_col

            st.dataframe(pd.DataFrame(dist_data), hide_index=True, use_container_width=True)
            
            st.caption("👇 比較用データ")
            st.dataframe(pd.DataFrame(ref_data), hide_index=True, use_container_width=True)

            # --- 追加: 教育費詳細テーブル（一番下へ） ---
            st.divider()
            st.subheader("🎓 教育費の内訳詳細")
            st.caption("自動で差し引かれた教育費の内訳です。（幼:幼稚園, 小:小学校, 中:中学校, 高:高校, 大:大学, 専:専門学校, 短:短大）")
            
            edu_table_data = []
            for y in range(years + 1):
                p_age = current_age + y
                yearly_total = 0
                row = {"親の年齢": f"{p_age}歳"}
                has_student = False

                for i, child in enumerate(st.session_state.children_list):
                    c_age = child["age"] + y
                    # コースを渡す
                    stage = get_school_stage(c_age, child["course"])
                    
                    if stage:
                        cost = EDU_COSTS[child["course"]][stage]
                        yearly_total += cost
                        s_name = STAGE_NAMES.get(stage, stage)
                        row[f"子供{i+1}"] = f"{c_age}歳({s_name}): {cost}万"
                        has_student = True
                    else:
                        row[f"子供{i+1}"] = "-"
                
                if has_student:
                    row["教育費合計"] = f"▲{yearly_total}万円"
                    edu_table_data.append(row)
            
            if edu_table_data:
                st.dataframe(pd.DataFrame(edu_table_data), hide_index=True, use_container_width=True)
            else:
                st.info("教育費がかかる期間はありません。")

    except Exception as e:
        st.error(f"エラー: {e}")
