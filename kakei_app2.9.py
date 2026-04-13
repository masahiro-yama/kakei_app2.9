import streamlit as st
import pandas as pd
import altair as alt

st.set_page_config(page_title="家計シミュレーター", layout="wide")

st.title("家計シミュレーター（ver.2.3改）")

# ===== セッション初期化 =====
if "annual_invest" not in st.session_state:
    st.session_state["annual_invest"] = 100

# ===== 入力 =====
st.sidebar.header("入力（3ステップ）")

tab1, tab2, tab3 = st.sidebar.tabs(["① プロフィール", "② 現在の資産", "③ 将来の想定"])

with tab1:
    age = st.number_input("現在の年齢", 20, 100, 35)
    income = st.number_input("現在の手取年収（万円）", 0, 2000, 500, step=10)
    monthly_expense = st.number_input("現在の月の支出（万円）", 0, 200, 25, step=1)

with tab2:
    cash = st.number_input("現在の現金資産（万円）", 0, 10000, 200, step=10)
    investment = st.number_input("現在の投資資産（万円）", 0, 10000, 300, step=10)

with tab3:
    income_growth_percent = st.slider("年収成長率（%）", -5.0, 5.0, 1.0, step=0.5)
    return_rate_percent = st.slider("想定利回り（%）", 0.0, 15.0, 6.0, step=0.5)
    expense_growth_percent = st.slider("物価上昇率（%）", 0.0, 5.0, 2.0, step=0.2)
    annual_invest = st.number_input("年間希望投資額（万円）", 0, 10000, step=10, key="annual_invest")

income_growth = income_growth_percent / 100
return_rate = return_rate_percent / 100
expense_growth = expense_growth_percent / 100
cash_months = 6

# ===== 目標年齢 =====
min_age = age + 5
options = list(range(min_age, 121, 5))
default_age = 65 if 65 in options else options[0]

target_age = st.sidebar.selectbox("合計資産額を知りたい年齢", options, index=options.index(default_age))
years = target_age - age

st.write(f"👉 {target_age}歳まであと {years} 年")
st.write("")

# ===== シミュレーション =====
def simulate(return_rate, invest_amount):
    current_cash = cash
    current_investment = investment

    total_assets = []
    shortage_years = []
    withdrawal_years = []

    for year in range(years):
        current_age = age + year

        current_income = income * ((1 + income_growth) ** year)
        annual_expense = monthly_expense * 12 * ((1 + expense_growth) ** year)

        current_investment *= (1 + return_rate)

        current_cash += current_income
        current_cash -= annual_expense

        target_cash = monthly_expense * cash_months
        surplus = current_income - annual_expense

        if surplus < 0:
            if current_cash < target_cash:
                needed = target_cash - current_cash
                withdraw = min(needed, current_investment)
                current_investment -= withdraw
                current_cash += withdraw
                withdrawal_years.append(current_age)
        else:
            available_cash = current_cash - target_cash
            max_invest = max(0, min(surplus, available_cash))

            if max_invest < invest_amount:
                shortage_years.append(current_age)

            if max_invest > 0:
                invest = min(invest_amount, max_invest)
                current_cash -= invest
                current_investment += invest

        total_assets.append(current_cash + current_investment)

    return total_assets, shortage_years, withdrawal_years

# ===== シナリオ =====
low_total, _, _ = simulate(return_rate - 0.03, annual_invest)
base_total, shortage_years, withdrawal_years = simulate(return_rate, annual_invest)
high_total, _, _ = simulate(return_rate + 0.03, annual_invest)

df = pd.DataFrame({
    "弱気": low_total,
    "標準": base_total,
    "強気": high_total
})
df.index = list(range(age, target_age))

# ===== 上部カード =====
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("最終資産（標準）", f"{int(base_total[-1]):,} 万円")

with col2:
    stable_placeholder = st.empty()

with col3:
    best_placeholder = st.empty()

# ===== グラフ =====
st.subheader("資産推移（3シナリオ）")

df_plot = df.reset_index().rename(columns={"index": "年齢"})
df_plot = df_plot.melt("年齢", var_name="シナリオ", value_name="資産")

chart = alt.Chart(df_plot).mark_line().encode(
    x="年齢:Q",
    y="資産:Q",
    color=alt.Color("シナリオ:N", scale=alt.Scale(
        domain=["弱気", "標準", "強気"],
        range=["#d9534f", "#0275d8", "#5cb85c"]
    ))
).properties(height=350)

st.altair_chart(chart, use_container_width=True)

# ===== リスクアラート =====
st.subheader("リスクアラート")

initial_total = cash + investment

base_below = next((i for i, v in enumerate(base_total) if v < initial_total), None)
low_below = next((i for i, v in enumerate(low_total) if v < initial_total), None)

if base_below is not None:
    st.error(f"🔴 標準シナリオでは {age + base_below}歳から資産が減少します")

if low_below is not None:
    st.warning(f"🟡 弱気シナリオでは {age + low_below}歳から資産が減少します")

if base_below is None and low_below is None:
    st.success("🟢 資産は増加し続ける見込みです")

# ===== 投資戦略 =====
def is_stable(x):
    _, s, w = simulate(return_rate, x)
    return len(s) == 0 and len(w) == 0

stable = None
stable_value = None

for t in range(annual_invest, -1, -10):
    if is_stable(t):
        stable = t
        total, _, _ = simulate(return_rate, stable)
        stable_value = total[-1]
        break

best_invest = None
best_value = -1

for test in range(0, 1001, 10):
    total, _, _ = simulate(return_rate, test)
    if total[-1] > best_value:
        best_value = total[-1]
        best_invest = test

# ===== 上部カード更新 =====
stable_placeholder.metric(
    "安定投資額",
    f"{stable:,} 万円" if stable is not None else "該当なし",
    help="現金は月の支出の6ヶ月分を下回らず、投資資金不足も発生させない年間投資額です"
)

best_placeholder.metric(
    "最大効率投資額",
    f"{best_invest:,} 万円",
    help="投資資産の取り崩しを一部期間で許容しながら、最終資産を最大化する投資額です"
)

# ===== 差分 =====
if stable is not None:
    diff = best_value - stable_value
    if diff > 0:
        st.write(f"👉 最大効率投資を選ぶと +{int(diff):,} 万円 の差が出ます")

# ===== 未来レポート（改善版） =====
st.subheader("📊 未来レポート")

st.markdown(f"### {target_age}歳のあなたの資産")
st.markdown(f"## {int(base_total[-1]):,} 万円")
st.caption("（標準シナリオ）")

st.divider()

colA, colB, colC = st.columns(3)
colA.metric("弱気", f"{int(low_total[-1]):,} 万円")
colB.metric("標準", f"{int(base_total[-1]):,} 万円")
colC.metric("強気", f"{int(high_total[-1]):,} 万円")

st.divider()

colX, colY = st.columns(2)
colX.metric("安定投資額", f"{stable:,} 万円" if stable else "該当なし")
colY.metric("最大効率投資額", f"{best_invest:,} 万円")

st.divider()

if withdrawal_years:
    st.warning(f"⚠️ {min(withdrawal_years)}〜{max(withdrawal_years)}歳で投資資産を取り崩します")
else:
    st.success("🟢 投資資産の取り崩しはありません")

if stable is not None:
    st.info(f"🛡️ 安定投資額（{stable:,}万円）は家計が安定します")

st.write(f"📈 最大効率投資額（{best_invest:,}万円）は最終資産を最大化します")