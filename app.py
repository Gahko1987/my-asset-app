"""資産ライフプランシミュレーター v2
Run: streamlit run app.py
Dependencies: streamlit, numpy, pandas (existing requirements.txt can be retained).
All monetary inputs and outputs are in ten-thousand JPY, at today's purchasing power.
"""
import copy
import json
import math
import numpy as np
import pandas as pd
import streamlit as st

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

COURSE_NAMES = {
    "all_public": "国公立大 (標準)", "private_uni": "私立大学 (平均)", "private_from_jr": "中学から私立 (〜私立大)", 
    "all_private": "すべて私立 (手厚い)", "vocational": "専門学校 (2年)", "junior_college": "短期大学 (2年)", 
    "study_abroad": "海外大学留学 (4年)", "medical_private": "私立医学部 (6年)", "high_school_grad": "高校卒業まで"
}

def get_school_stage(age, course_type):
    if 3 <= age <= 5: return "kindergarten"
    if 6 <= age <= 11: return "elementary"
    if 12 <= age <= 14: return "junior_high"
    if 15 <= age <= 17: return "high_school"
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
        if current_principal <= 0: break
        rate = min(initial_rate + annual_increase * y, max_rate)
        r = rate / 100 / 12
        n = (years - y) * 12
        if r > 0:
            monthly_pmt = current_principal * (r * (1+r)**n) / ((1+r)**n - 1)
            next_principal = current_principal * ((1+r)**n - (1+r)**12) / ((1+r)**n - 1)
        else:
            monthly_pmt = current_principal / n
            next_principal = current_principal - monthly_pmt * 12
        annual_pmt = monthly_pmt * 12
        if y == 0: base_pmt = annual_pmt
        schedule.append({"year": y, "rate": rate, "annual_pmt": annual_pmt, "balance": max(0, next_principal)})
        current_principal = max(0, next_principal)
    return schedule, base_pmt


DEFAULT = {
    'version': 2, 'name': '基本プラン', 'age': 35, 'assets': 500.0, 'end': 100,
    'inflation': 2.0, 'return': 5.0, 'risk': 15.0,
    'pension_on': True, 'pension_age': 65, 'pension': 240.0,
    'housing': 'none', 'buy_age': 40, 'price': 4000.0, 'down': 500.0,
    'rent': 120.0, 'principal': 3000.0, 'loan_years': 35,
    'rate': 1.5, 'rate_inc': 0.0, 'rate_max': 4.0, 'after_payoff': False,
    'phases': [{'end': 45, 'amount': 100.0}, {'end': 60, 'amount': 200.0},
               {'end': 65, 'amount': 100.0}, {'end': 100, 'amount': -100.0}],
    'children': [{'age': 5, 'course': 'private_uni'}, {'age': 2, 'course': 'private_uni'}],
    'events': [{'age': 60, 'amount': 1500.0, 'name': '退職金'},
               {'age': 40, 'amount': -300.0, 'name': '車購入'}],
}
HOUSING = {'none': '賃貸・ローンなし', 'future': 'これから購入', 'already': 'ローン返済中'}
MODEL_NOTE = (
    '金額は現在の物価水準の万円。収支・年金・教育費は実質額が一定と仮定します。'
    '各年齢の年初に収支を反映し、その後1年分を運用します。終了年齢は到達時点で、同年齢の収支は含みません。'
    '運用収益は年ごとに独立した正規分布（名目損失は100%を上限）を仮定し、物価で調整します。'
    '税・手数料は別計算しないため、利回りには控除後の想定を入力してください。'
    '年初収支反映後に残高がマイナスになった試行を資金不足とし、その後の残高はゼロで固定します。'
    '確率はこのモデルの試行割合で、将来の安全性を保証する数値ではありません。'
    '下位20%は各年齢の20パーセンタイルで、単一の経路や最悪ケースではありません。'
    '教育費は旧版の概算設定を引き継いでいます。住宅の資産価値・売却代金・購入諸費用・維持費は自動計算しません。'
    '必要な費用は基本収支やイベントに入力してください。'
)

def validate(c):
    if not isinstance(c, dict) or c.get('version') != 2:
        raise ValueError('この改修版で保存した条件ファイル（version 2）を選んでください。旧版JSONは住宅の入力情報が不足しています。')
    if set(DEFAULT) - set(c):
        raise ValueError('入力条件の項目が不足しています。')
    c = copy.deepcopy({k: c[k] for k in DEFAULT})
    ranges = {'age': (0, 100), 'end': (1, 150), 'assets': (0, 500000),
              'inflation': (0, 5), 'return': (0, 20), 'risk': (0, 40),
              'pension_age': (60, 75), 'pension': (0, 1000), 'buy_age': (0, 150),
              'price': (0, 50000), 'down': (0, 50000), 'rent': (0, 1000),
              'principal': (0, 50000), 'loan_years': (1, 50),
              'rate': (0, 10), 'rate_inc': (0, 2), 'rate_max': (0, 20)}
    ints = {'age', 'end', 'pension_age', 'buy_age', 'loan_years'}
    for k, (lo, hi) in ranges.items():
        v = c[k]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not lo <= v <= hi:
            raise ValueError(f'{k}: {lo}〜{hi}の数値を入力してください。')
        if k in ints and v != int(v):
            raise ValueError(f'{k}: 年齢・年数は整数で入力してください。')
        c[k] = int(v) if k in ints else float(v)
    if not isinstance(c['name'], str) or not c['name'].strip() or len(c['name']) > 60:
        raise ValueError('プラン名を1〜60文字で入力してください。')
    for k in ('pension_on', 'after_payoff'):
        if not isinstance(c[k], bool):
            raise ValueError(f'{k}の形式が正しくありません。')
    if c['housing'] not in HOUSING:
        raise ValueError('住居の選択が正しくありません。')
    if c['end'] <= c['age']:
        raise ValueError('終了年齢は現在の年齢より大きくしてください。')
    if c['housing'] == 'future' and (c['buy_age'] < c['age'] or c['down'] > c['price']):
        raise ValueError('購入年齢は現在年齢以降、頭金は物件価格以下にしてください。')
    if c['housing'] != 'none' and c['rate_max'] < c['rate']:
        raise ValueError('上限金利を初期・現在金利以上にしてください。')
    for k in ('phases', 'children', 'events'):
        if not isinstance(c[k], list) or len(c[k]) > 100:
            raise ValueError(f'{k}: 行数は100件以内にしてください。')
    previous = c['age'] - 1
    for p in c['phases']:
        end, amount = p['end'], p['amount']
        if not isinstance(end, (int, float)) or not math.isfinite(end) or end != int(end) or not previous < end <= 150:
            raise ValueError('収支の終了年齢は、現在年齢から重複せず昇順に入力してください。')
        if not isinstance(amount, (int, float)) or not math.isfinite(amount) or abs(amount) > 1000000:
            raise ValueError('基本収支を有効な数値で入力してください。')
        p['end'], p['amount'] = int(end), float(amount)
        previous = end
    if not c['phases'] or previous < c['end'] - 1:
        raise ValueError('基本収支の期間を終了年齢の前年まで設定してください。')
    for child in c['children']:
        a = child['age']
        if not isinstance(a, (int, float)) or not math.isfinite(a) or a != int(a) or not 0 <= a <= 30 or child['course'] not in COURSE_NAMES:
            raise ValueError('子供の年齢（0〜30歳）と進学コースを確認してください。')
        child['age'] = int(a)
    for e in c['events']:
        a, v = e['age'], e['amount']
        if not isinstance(a, (int, float)) or not math.isfinite(a) or a != int(a) or not 0 <= a <= 150:
            raise ValueError('イベント年齢を0〜150歳の整数で入力してください。')
        if not isinstance(v, (int, float)) or not math.isfinite(v) or abs(v) > 1000000:
            raise ValueError('イベント金額を有効な数値で入力してください。')
        if not isinstance(e['name'], str) or len(e['name']) > 200:
            raise ValueError('イベント名を200文字以内で入力してください。')
        e['age'], e['amount'] = int(a), float(v)
    return c


def simulate(config, trials=10000, seed=20260905):
    c = validate(config)
    ages = np.arange(c['age'], c['end'])
    count = len(ages)
    flows = pd.DataFrame({'年齢': ages})
    flows['基本収支'] = [next(p['amount'] for p in c['phases'] if a <= p['end']) for a in ages]
    flows['年金'] = [c['pension'] if c['pension_on'] and a >= c['pension_age'] else 0 for a in ages]
    edu = pd.DataFrame({'年齢': ages})
    for i, child in enumerate(c['children']):
        edu[f'子供{i+1}'] = [EDU_COSTS[child['course']].get(get_school_stage(child['age'] + y, child['course']), 0) for y in range(count)]
    edu['教育費合計'] = edu.drop(columns='年齢').sum(axis=1)
    flows['教育費'] = -edu['教育費合計']
    flows['イベント'] = [sum(e['amount'] for e in c['events'] if e['age'] == a) for a in ages]
    flows['住宅調整'] = 0.0
    flows['頭金'] = 0.0
    loan_rows = []
    if c['housing'] != 'none':
        future = c['housing'] == 'future'
        start = c['buy_age'] if future else c['age']
        principal = (c['price'] - c['down']) * (1 + c['inflation']/100) ** (start-c['age']) if future else c['principal']
        schedule, base = calculate_loan_schedule(principal, c['loan_years'], c['rate'], c['rate_inc'], c['rate_max'])
        payments = {start + x['year']: x for x in schedule}
        finish = start + len(schedule)
        for item in schedule:
            loan_rows.append({'年齢': start + item['year'], '適用金利 (%)': item['rate'],
                              '年間返済額 (万円・名目)': item['annual_pmt'], '年末残高 (万円・名目)': item['balance']})
        for y, age in enumerate(ages):
            deflator = (1 + c['inflation'] / 100) ** y
            if age in payments:
                baseline = c['rent'] if future else base / deflator
                flows.loc[y, '住宅調整'] = baseline - payments[age]['annual_pmt'] / deflator
            elif age >= finish and c['after_payoff']:
                flows.loc[y, '住宅調整'] = c['rent'] if future else base / deflator
            if future and age == start:
                # The entered purchase budget is in today's purchasing power.
                flows.loc[y, '頭金'] = -c['down']
    flows['年間純収支'] = flows.drop(columns='年齢').sum(axis=1)
    rng = np.random.default_rng(seed)
    paths = np.zeros((trials, count + 1))
    paths[:, 0] = c['assets']
    failed = np.zeros(trials, dtype=bool)
    cumulative_failure = [0.0]
    simple, no_return = [c['assets']], [c['assets']]
    simple_failed = False
    real_factor = (1 + c['return'] / 100) / (1 + c['inflation'] / 100)
    for y, cash in enumerate(flows['年間純収支']):
        available = paths[:, y] + cash
        failed |= available < -1e-9
        # Fixed seed, same draw sequence for every scenario, one year's draws at a time.
        nominal = np.maximum(-1, rng.normal(c['return']/100, c['risk']/100, trials))
        paths[:, y+1] = np.where(failed, 0, np.maximum(available, 0) * (1+nominal) / (1+c['inflation']/100))
        cumulative_failure.append(100 * failed.mean())
        simple_failed |= simple[-1] + cash < -1e-9
        simple.append(0 if simple_failed else max(0, simple[-1] + cash) * real_factor)
        no_return.append(no_return[-1] + cash)
    percentiles = np.percentile(paths, [0, 10, 20, 30, 40, 50, 60, 70, 80, 90], axis=0)
    assets = pd.DataFrame({'年齢': np.arange(c['age'], c['end']+1),
                           '下位20%': percentiles[2], '中央値': percentiles[5],
                           '上位20%': percentiles[8], '一定利回り': simple,
                           '運用なし（不足分はマイナス）': no_return,
                           '累積資金不足率 (%)': cumulative_failure})
    distribution = pd.DataFrame(percentiles.T, columns=[f'{p}パーセンタイル' for p in [0,10,20,30,40,50,60,70,80,90]])
    distribution.insert(0, '年齢', assets['年齢'])
    return {'config': c, 'assets': assets, 'flows': flows, 'education': edu,
            'loan': pd.DataFrame(loan_rows), 'distribution': distribution,
            'success': float(100 * (1-failed.mean()))}


def dumps(c):
    return json.dumps(c, ensure_ascii=False, indent=2, allow_nan=False)


def main():
    st.set_page_config(page_title='資産ライフプラン', page_icon='📊', layout='wide')
    st.title('📊 資産ライフプラン')
    st.caption('条件を入力 → 結果を確認 → プランを比較。金額の単位は万円です。')
    if 'config_source' not in st.session_state:
        st.session_state.config_source = copy.deepcopy(DEFAULT)
        st.session_state.input_revision = 0
        st.session_state.saved_plans = {}
    if 'pending_config' in st.session_state:
        st.session_state.config_source = st.session_state.pop('pending_config')
        st.session_state.input_revision += 1
        st.session_state.pop('result', None)
    source = st.session_state.config_source
    c = copy.deepcopy(source)
    revision = st.session_state.input_revision
    def key(name): return f'input_{revision}_{name}'
    def number(name, label, lo, hi, step=None):
        kwargs = {'min_value': lo, 'max_value': hi, 'value': source[name], 'key': key(name)}
        if step is not None: kwargs['step'] = step
        c[name] = st.number_input(label, **kwargs)
    with st.expander('保存した条件を読み込む', expanded=False):
        upload = st.file_uploader('この改修版で保存したJSONファイル', type=['json'])
        if st.button('条件を読み込む', disabled=upload is None):
            try:
                if upload.size > 1000000:
                    raise ValueError('1MB以下の条件ファイルを選んでください。')
                st.session_state.pending_config = validate(json.loads(upload.getvalue().decode('utf-8-sig')))
                st.rerun()
            except (ValueError, KeyError, TypeError, UnicodeError) as exc:
                st.error(f'読み込めませんでした。{exc}')
        st.caption('旧版のJSONにはローン金利などが保存されていないため、完全な復元には対応していません。')
    c['name'] = st.text_input('プラン名', source['name'], max_chars=60, key=key('name'))
    tabs = st.tabs(['① 基本情報・運用', '② 基本収支・年金', '③ 住宅', '④ 教育費・イベント'])
    with tabs[0]:
        left, right = st.columns(2)
        with left:
            number('age', '現在の年齢', 0, 100)
            number('assets', '現在の金融資産（万円）', 0.0, 500000.0, 10.0)
            number('end', '何歳の到達時点まで計算しますか？', 1, 150)
        with right:
            number('return', '想定利回り（年率・税手数料控除後 %）', 0.0, 20.0, 0.1)
            number('risk', '運用の変動幅（年率の標準偏差 %）', 0.0, 40.0, 0.5)
            number('inflation', 'インフレ率（年率 %）', 0.0, 5.0, 0.1)
        st.caption('同じ条件では同じ結果になります。年齢別の運用乱数をそろえてプランを比較します。')
    with tabs[1]:
        st.info('基本収支＝手取り収入−生活費。現在の家賃・ローン返済を含め、ここで別入力する年金・教育費・イベントは除いてください。プラスは積立、マイナスは取り崩しです。')
        unit = '年額'
        phase_df = pd.DataFrame(source['phases'])
        phases = st.data_editor(phase_df, hide_index=True, num_rows='dynamic', use_container_width=True,
            key=key('phases_'+unit), column_config={
                'end': st.column_config.NumberColumn('この年齢まで', min_value=0, max_value=150, step=1, required=True),
                'amount': st.column_config.NumberColumn(f'{unit}収支（万円）', required=True)})
        c['phases'] = phases.to_dict('records')
        st.caption('表の最下行から期間を追加できます。行を選択して削除できます。月額で把握している収支は12倍して入力してください。')
        c['pension_on'] = st.checkbox('年金を加算する', source['pension_on'], key=key('pension_on'))
        left, right = st.columns(2)
        with left: number('pension_age', '年金の受給開始年齢', 60, 75)
        with right: number('pension', '年金の手取り年額（万円）', 0.0, 1000.0, 1.0)
    with tabs[2]:
        c['housing'] = st.radio('住居・ローンの状況', list(HOUSING), index=list(HOUSING).index(source['housing']), format_func=HOUSING.get, horizontal=True, key=key('housing'))
        left, right = st.columns(2)
        if c['housing'] == 'future':
            with left:
                number('buy_age', '購入年齢', 0, 150)
                number('price', '物件価格（現在の物価水準・万円）', 0.0, 50000.0, 100.0)
            with right:
                number('down', '頭金（現在の物価水準・万円）', 0.0, 50000.0, 100.0)
                number('rent', '基本収支に含めた現在の家賃（年額・万円）', 0.0, 1000.0, 1.0)
            st.caption('購入年に頭金を差し引きます。物件価格と頭金は購入年までインフレ率で増える仮定です。その差額を購入年の名目借入額として計算します。')
        elif c['housing'] == 'already':
            with left: number('principal', '現在のローン残高（万円）', 0.0, 50000.0, 100.0)
            st.caption('初年度返済額は基本収支に含まれている前提で、金利変動による差額だけを追加反映します。')
        if c['housing'] != 'none':
            left, right = st.columns(2)
            with left:
                number('loan_years', '返済期間／残り期間（年）', 1, 50)
                number('rate', '初期・現在の金利（%）', 0.0, 10.0, 0.1)
            with right:
                number('rate_inc', '毎年の金利上昇幅（ポイント）', 0.0, 2.0, 0.05)
                number('rate_max', '想定金利の上限（%）', 0.0, 20.0, 0.1)
            c['after_payoff'] = st.checkbox('完済後の住居費減少を収支に反映する', source['after_payoff'], key=key('after_payoff'))
            st.caption('基本収支を完済後に増やしている場合はオフにしてください。元利均等返済を年ごとに再計算します。5年ルール・125%ルールは適用しません。上限はシナリオの仮定で、契約上の保証ではありません。')
    with tabs[3]:
        st.markdown('**子供の教育費**')
        child_df = pd.DataFrame(source['children'], columns=['age','course'])
        child_df['course'] = child_df['course'].map(COURSE_NAMES)
        children = st.data_editor(child_df, hide_index=True, num_rows='dynamic', use_container_width=True, key=key('children'), column_config={
            'age': st.column_config.NumberColumn('現在の年齢', min_value=0, max_value=30, step=1, required=True),
            'course': st.column_config.SelectboxColumn('進学コース', options=list(COURSE_NAMES.values()), required=True)})
        reverse = {v:k for k,v in COURSE_NAMES.items()}
        c['children'] = [{'age': r['age'], 'course': reverse.get(r['course'], '')} for r in children.to_dict('records')]
        with st.expander('教育費の設定額（子供1人・年額万円）'):
            st.dataframe(pd.DataFrame(EDU_COSTS).rename(columns=COURSE_NAMES, index=STAGE_NAMES).fillna(0), use_container_width=True)
        st.markdown('**イベント・一時金**')
        st.caption('退職金などの収入はプラス、車の購入などの支出はマイナス。住宅の頭金は別途自動計上します。')
        events = st.data_editor(pd.DataFrame(source['events'], columns=['age','amount','name']), hide_index=True, num_rows='dynamic', use_container_width=True, key=key('events'), column_config={
            'age': st.column_config.NumberColumn('年齢', min_value=0, max_value=150, step=1, required=True),
            'amount': st.column_config.NumberColumn('金額（万円）', required=True),
            'name': st.column_config.TextColumn('内容', required=True)})
        c['events'] = events.to_dict('records')
    try:
        c = validate(c)
    except (ValueError, KeyError, TypeError) as exc:
        st.error(f'入力内容を確認してください：{exc}')
        return
    for e in c['events']:
        if not c['age'] <= e['age'] < c['end']:
            st.warning(f'「{e["name"]}」（{e["age"]}歳）は計算期間外のため反映されません。')
    if c['housing'] == 'future' and c['buy_age'] >= c['end']:
        st.warning('住宅購入年齢が計算期間外のため、購入は結果に反映されません。')
    left, right = st.columns(2)
    with left:
        run = st.button('シミュレーションを実行・更新', type='primary', use_container_width=True)
    with right:
        st.download_button('入力条件を保存（JSON）', dumps(c).encode('utf-8'), 'simulation_inputs_v2.json', 'application/json', use_container_width=True)
    if run:
        with st.spinner('10,000通りの資産推移を計算しています…'):
            st.session_state.result = simulate(c)
    result = st.session_state.get('result')
    if result is None:
        st.info('入力を確認して「シミュレーションを実行・更新」を押してください。')
        return
    if result['config'] != c:
        st.warning('条件が変更されています。「シミュレーションを実行・更新」を押すと結果が更新されます。')
        return
    render_result(result)


def render_result(r):
    c, assets, flows = r['config'], r['assets'], r['flows']
    st.divider()
    st.subheader(f'{c["name"]} ｜ {c["end"]}歳到達時点まで')
    cols = st.columns(3)
    cols[0].metric('期間中に資金不足がなかった割合', f'{r["success"]:.1f}%')
    cols[1].metric('最終資産・中央値', f'{assets["中央値"].iloc[-1]:,.0f} 万円')
    cols[2].metric('最終資産・下位20%', f'{assets["下位20%"].iloc[-1]:,.0f} 万円')
    st.caption('資産ゼロでも収入で支払いができる年は資金不足に含めません。下位20%より悪い結果もあります。')
    tabs = st.tabs(['結果・グラフ', '年間収支', '教育費・ローン', 'プラン比較', 'AI相談'])
    with tabs[0]:
        st.line_chart(assets.set_index('年齢')[['下位20%', '中央値', '上位20%', '一定利回り']], height=380)
        st.caption('横軸：年齢／縦軸：資産額（万円・現在の購買力）。グラフにカーソルを合わせると金額を確認できます。')
        cols = st.columns(3)
        for col, threshold in zip(cols, [1000, 500, 0]):
            hit = assets[assets['下位20%'] < threshold] if threshold else assets[assets['下位20%'] <= 0]
            col.metric(f'下位20%が{threshold:,}万円'+('未満' if threshold else 'になる'), f'{int(hit.iloc[0]["年齢"])}歳' if len(hit) else '該当なし')
        worst = flows.loc[flows['年間純収支'].idxmin()]
        st.write(f'年間純収支が最も少ない年：{int(worst["年齢"])}歳、{worst["年間純収支"]:,.0f}万円')
        if not r['loan'].empty:
            overlap = flows[(flows['教育費'] < 0) & flows['年齢'].isin(r['loan']['年齢'])]
            if len(overlap): st.write('教育費とローン返済が重なる年齢：'+'、'.join(str(int(a))+'歳' for a in overlap['年齢']))
        with st.expander('資産分布・運用なしの場合の詳細'):
            st.dataframe(r['distribution'].round(1), hide_index=True, use_container_width=True)
            st.dataframe(assets.round(1), hide_index=True, use_container_width=True)
        with st.expander('計算の前提と数値の読み方'):
            st.write(MODEL_NOTE)
    with tabs[1]:
        st.bar_chart(flows.set_index('年齢')[['年間純収支']])
        st.dataframe(flows.round(1), hide_index=True, use_container_width=True)
        st.caption('各年齢の収支を年初に反映した後、翌年齢の到達時点まで運用します。頭金も独立した列で確認できます。')
        st.download_button('年間収支をCSVで保存', flows.to_csv(index=False).encode('utf-8-sig'), 'cash_flow.csv', 'text/csv')
    with tabs[2]:
        st.metric('計算期間内の教育費合計', f'{r["education"]["教育費合計"].sum():,.0f} 万円')
        st.dataframe(r['education'], hide_index=True, use_container_width=True)
        if r['loan'].empty:
            st.info('ローン返済はありません。')
        else:
            st.metric('ローン全期間の返済総額（名目）', f'{r["loan"]["年間返済額 (万円・名目)"].sum():,.0f} 万円')
            st.caption('ローン表は返済全期間の名目金額。年間収支への反映は計算期間内のみで、物価調整した金額です。')
            st.dataframe(r['loan'].round(2), hide_index=True, use_container_width=True)
    with tabs[3]:
        st.write('この結果を登録してから条件を変更・再計算すると、最大3案を比較できます。同名は更新します。')
        if st.button('このプランを比較に登録'):
            saved = st.session_state.saved_plans
            if c['name'] not in saved and len(saved) >= 3:
                st.warning('最大3案です。先に不要なプランを削除してください。')
            else:
                saved[c['name']] = copy.deepcopy(r)
                st.success('比較に登録しました。')
        saved = st.session_state.saved_plans
        if saved:
            rows = []
            for name, item in saved.items():
                cfg, a = item['config'], item['assets']
                rows.append({'プラン': name, '現在年齢': cfg['age'], '終了年齢': cfg['end'],
                    '初期資産（万円）': cfg['assets'], '資金不足なし (%)': item['success'],
                    '最終中央値（万円）': a['中央値'].iloc[-1], '最終下位20%（万円）': a['下位20%'].iloc[-1]})
            comparison = pd.DataFrame(rows)
            st.dataframe(comparison.round(1), hide_index=True, use_container_width=True)
            st.line_chart(pd.concat([item['assets'].set_index('年齢')['中央値'].rename(name) for name,item in saved.items()], axis=1))
            if len({(item['config']['age'], item['config']['end']) for item in saved.values()}) > 1:
                st.warning('計算期間が異なります。最終資産と資金不足の割合は同じ期間にそろえて比較してください。')
            selection = st.selectbox('操作するプラン', list(saved))
            left, right = st.columns(2)
            with left:
                if st.button('このプランの条件を入力に戻す'):
                    st.session_state.pending_config = copy.deepcopy(saved[selection]['config'])
                    st.rerun()
            with right:
                if st.button('このプランを比較から削除'):
                    del saved[selection]
                    st.rerun()
            st.download_button('比較表をCSVで保存', comparison.to_csv(index=False).encode('utf-8-sig'), 'plan_comparison.csv', 'text/csv')
        st.caption('比較への登録はこの接続中のみ有効です。後日使うプランは入力に戻してJSONで保存してください。')
    with tabs[4]:
        prompt = f'''以下のライフプランを分析し、資金不足に注意する時期と、条件を変えて比較すべき点を説明してください。モデルの限界も考慮し、試行割合を現実の保証と解釈しないでください。
資金不足なし：{r['success']:.1f}%（10,000回）
最終資産中央値：{assets['中央値'].iloc[-1]:,.0f}万円
最終資産下位20%：{assets['下位20%'].iloc[-1]:,.0f}万円
計算前提：{MODEL_NOTE}
入力条件（住宅費は基本収支に含み、差額を住宅調整として反映）：
{dumps(c)}
年間収支CSV：
{flows.round(2).to_csv(index=False)}
年齢別資産CSV（到達時点）：
{assets.round(2).to_csv(index=False)}'''
        st.write('相談用テキストに入力条件と明細をまとめました。ダウンロードしてChatGPTに添付できます。')
        st.download_button('相談用テキストを保存', prompt.encode('utf-8'), 'life_plan_consultation.txt', 'text/plain')
        with st.expander('コピーして相談する'):
            st.code(prompt, language='text')
        st.link_button('ChatGPTを開く', 'https://chatgpt.com/')
        st.caption('ボタンを押してもデータは自動送信されません。保存したテキストを添付して相談してください。')


if __name__ == '__main__':
    main()
