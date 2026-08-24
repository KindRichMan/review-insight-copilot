import streamlit as st
import pandas as pd
import plotly.express as px
from collections import Counter
import re
from streamlit_gsheets import GSheetsConnection

st.set_page_config(
    page_title="Review Insight Copilot",
    layout="wide"
)

st.title("📊 Review Insight Copilot")

# ============================================================
# 섹션별 시각화 설정 기본값 (session_state에 섹션마다 따로 저장)
# ============================================================
DEFAULTS = {
    "감성 분포": {"chart": "파이", "pos": "#1f77b4", "neu": "#aec7e8", "neg": "#d62728"},
    "카테고리별 리뷰 수": {"chart": "막대", "color": "#1f77b4"},
    "카테고리별 평점": {"chart": "막대", "color": "#2ca02c"},
    "TOP 키워드": {"chart": "가로 막대", "n": 20, "color": "#ff7f0e"},
    "VOC 분석": {"chart": "막대"},
    "상품별 리뷰 TOP": {"chart": "가로 막대", "n": 20, "color": "#9467bd"},
    "상품 위험도": {"chart": "가로 막대", "n": 20, "color": "#d62728"},
}

if "cfg" not in st.session_state:
    st.session_state.cfg = {k: dict(v) for k, v in DEFAULTS.items()}
cfg = st.session_state.cfg


def available_sections(cols):
    secs = ["감성 분포"]
    if "상품명" in cols:
        secs.append("카테고리별 리뷰 수")
        if "평점" in cols:
            secs.append("카테고리별 평점")
    secs += ["TOP 키워드", "VOC 분석"]
    if "상품명" in cols:
        secs += ["상품별 리뷰 TOP", "상품 위험도"]
    return secs


def sentiment(text):
    text = str(text)
    positive_words = [
        "좋", "만족", "추천", "부드럽", "흡수", "편하", "최고",
        "감사", "빠르", "재구매", "가성비", "믿고", "잘사용"
    ]
    negative_words = [
        "아쉽", "실망", "불편", "늦", "문제", "파손", "끊어",
        "찝찝", "힘들", "품절", "별로", "불만"
    ]
    pos = sum(1 for w in positive_words if w in text)
    neg = sum(1 for w in negative_words if w in text)
    if pos > neg:
        return "긍정"
    if neg > pos:
        return "부정"
    return "중립"


def category_mapping(product):
    product = str(product)
    if "하기스" in product:
        return "기저귀"
    elif "그린핑거" in product:
        return "베이비케어"
    elif "크리넥스" in product or "스카트" in product:
        return "생활용품"
    elif "좋은느낌" in product or "화이트" in product:
        return "여성용품"
    elif any(x in product for x in ["삼다수", "동원샘물", "생수", "아이시스"]):
        return "생수"
    elif any(x in product for x in ["우유", "두유", "주스", "엔요", "음료", "커피"]):
        return "음료"
    elif any(x in product for x in ["치즈", "식혜", "과자", "참치", "팝콘"]):
        return "식품"
    return "기타"


def voc_mapping(text):
    text = str(text)
    rules = {
        "배송": ["배송", "도착", "택배"],
        "가격": ["가격", "비싸", "세일", "할인"],
        "품질": ["파손", "불량", "끊어", "문제"],
        "포장": ["포장", "박스"],
        "사용성": ["불편", "힘들", "착용"],
        "재고/품절": ["품절", "재고"]
    }
    for category, words in rules.items():
        for w in words:
            if w in text:
                return category
    return "기타"


def item_bar(df, cat_col, val_col, chart, color):
    if chart == "가로 막대":
        d = df.sort_values(val_col)
        return px.bar(d, x=val_col, y=cat_col, orientation="h",
                      color_discrete_sequence=[color])
    return px.bar(df, x=cat_col, y=val_col, color_discrete_sequence=[color])


def radio_with_default(label, options, current):
    return st.sidebar.radio(
        label, options,
        index=options.index(current) if current in options else 0,
        horizontal=True
    )


# ------------------------------------------------------------
# 1) Google Sheets에서 데이터 읽기 (엑셀 업로드 대체)
#    - Secrets의 [connections.gsheets] spreadsheet 링크를 사용
#    - ttl 로 주기적으로 새로고침 (시트 수정 시 반영)
# ------------------------------------------------------------
st.sidebar.header("⚙️ 시각화 설정")

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(ttl="10m")          # 특정 탭이면: conn.read(worksheet="시트1", ttl="10m")
    df = df.dropna(how="all")          # 빈 행 제거
except Exception as e:
    st.error("구글 시트를 불러오지 못했습니다. Secrets의 spreadsheet 링크와 공유 설정(뷰어)을 확인하세요.")
    st.caption(f"상세: {e}")
    st.stop()

if "상품평" not in df.columns:
    st.error("시트에서 '상품평' 컬럼을 찾지 못했습니다. 첫 행 헤더를 확인하세요.")
    st.stop()

col_refresh = st.sidebar.button("🔄 데이터 새로고침")
if col_refresh:
    st.cache_data.clear()
    st.rerun()

data_cols = list(df.columns)

result = df.copy()
result["감성"] = result["상품평"].fillna("").astype(str).apply(sentiment)
if "상품명" in result.columns:
    result["카테고리"] = result["상품명"].fillna("").astype(str).apply(category_mapping)
result["VOC"] = result["상품평"].fillna("").astype(str).apply(voc_mapping)

# ------------------------------------------------------------
# 2) 컬럼 기반 섹션 목록 → 사이드바 선택 메뉴
# ------------------------------------------------------------
secs = available_sections(data_cols)
section = st.sidebar.selectbox("섹션 선택", secs)
st.sidebar.markdown(f"**[{section}] 설정**")

c = cfg[section]

if section == "감성 분포":
    c["chart"] = radio_with_default("차트 종류", ["파이", "도넛", "막대"], c["chart"])
    c["pos"] = st.sidebar.color_picker("긍정 색", c["pos"])
    c["neu"] = st.sidebar.color_picker("중립 색", c["neu"])
    c["neg"] = st.sidebar.color_picker("부정 색", c["neg"])
elif section in ("카테고리별 리뷰 수", "카테고리별 평점"):
    c["chart"] = radio_with_default("차트 종류", ["막대", "파이"], c["chart"])
    c["color"] = st.sidebar.color_picker("막대 색", c["color"])
elif section == "TOP 키워드":
    c["chart"] = radio_with_default("차트 종류", ["가로 막대", "세로 막대"], c["chart"])
    c["n"] = st.sidebar.slider("표시 개수", 5, 30, c["n"])
    c["color"] = st.sidebar.color_picker("막대 색", c["color"])
elif section == "VOC 분석":
    c["chart"] = radio_with_default("차트 종류", ["막대", "파이"], c["chart"])
elif section in ("상품별 리뷰 TOP", "상품 위험도"):
    c["chart"] = radio_with_default("차트 종류", ["가로 막대", "세로 막대"], c["chart"])
    c["n"] = st.sidebar.slider("표시 개수", 5, 30, c["n"])
    c["color"] = st.sidebar.color_picker("막대 색", c["color"])

st.sidebar.caption("섹션을 바꿔도 각 설정은 유지됩니다.")

has_product = "상품명" in data_cols
has_rating = "평점" in data_cols

# ------------------------------------------------------------
# 3) 필터 + 분석
# ------------------------------------------------------------
fcol1, fcol2 = st.columns(2)
with fcol1:
    if "카테고리" in result.columns:
        selected_category = st.selectbox(
            "카테고리",
            ["전체"] + sorted(result["카테고리"].unique().tolist())
        )
    else:
        selected_category = "전체"
with fcol2:
    selected_voc = st.selectbox(
        "VOC",
        ["전체"] + sorted(result["VOC"].unique().tolist())
    )

filtered_df = result.copy()
if selected_category != "전체" and "카테고리" in filtered_df.columns:
    filtered_df = filtered_df[filtered_df["카테고리"] == selected_category]
if selected_voc != "전체":
    filtered_df = filtered_df[filtered_df["VOC"] == selected_voc]

total = len(filtered_df)
positive = len(filtered_df[filtered_df["감성"] == "긍정"])
negative = len(filtered_df[filtered_df["감성"] == "부정"])
neutral = len(filtered_df[filtered_df["감성"] == "중립"])
positive_rate = round(positive / total * 100, 1) if total else 0

m1, m2, m3, m4 = st.columns(4)
m1.metric("전체 리뷰", total)
m2.metric("긍정", positive)
m3.metric("부정", negative)
m4.metric("긍정률", f"{positive_rate}%")

# ---------------- 감성 분포 ----------------
st.subheader("📈 감성 분포")
sc = cfg["감성 분포"]
sentiment_df = pd.DataFrame({
    "감성": ["긍정", "중립", "부정"],
    "건수": [positive, neutral, negative]
})
color_map = {"긍정": sc["pos"], "중립": sc["neu"], "부정": sc["neg"]}
if sc["chart"] == "막대":
    fig = px.bar(sentiment_df, x="감성", y="건수",
                 color="감성", color_discrete_map=color_map)
else:
    hole = 0.4 if sc["chart"] == "도넛" else 0
    fig = px.pie(sentiment_df, names="감성", values="건수",
                 color="감성", color_discrete_map=color_map, hole=hole)
st.plotly_chart(fig, use_container_width=True)

# ---------------- 카테고리별 리뷰 수 ----------------
if has_product:
    st.subheader("📂 카테고리별 리뷰 수")
    cc = cfg["카테고리별 리뷰 수"]
    category_count = (
        result.groupby("카테고리").size()
        .reset_index(name="리뷰수")
        .sort_values("리뷰수", ascending=False)
    )
    if cc["chart"] == "파이":
        fig = px.pie(category_count, names="카테고리", values="리뷰수")
    else:
        fig = px.bar(category_count, x="카테고리", y="리뷰수",
                     color_discrete_sequence=[cc["color"]])
    st.plotly_chart(fig, use_container_width=True)
    with st.expander("표 보기"):
        st.dataframe(category_count, use_container_width=True)

# ---------------- 카테고리별 평점 ----------------
if has_product and has_rating:
    st.subheader("⭐ 카테고리별 평점")
    rc = cfg["카테고리별 평점"]
    rating_df = result.groupby("카테고리")["평점"].mean().reset_index()
    if rc["chart"] == "파이":
        fig = px.pie(rating_df, names="카테고리", values="평점")
    else:
        fig = px.bar(rating_df, x="카테고리", y="평점",
                     color_discrete_sequence=[rc["color"]])
    st.plotly_chart(fig, use_container_width=True)
    with st.expander("표 보기"):
        st.dataframe(rating_df, use_container_width=True)

# ---------------- TOP 키워드 ----------------
st.subheader("🔥 TOP 키워드")
kc = cfg["TOP 키워드"]
text = " ".join(filtered_df["상품평"].fillna("").astype(str))
words = re.findall(r"[가-힣]{2,}", text)
stop_words = {"좋아요", "있어요", "합니다", "너무", "정말", "제품", "사용"}
words = [w for w in words if w not in stop_words]
keyword_df = pd.DataFrame(
    Counter(words).most_common(kc["n"]),
    columns=["키워드", "빈도"]
)
if not keyword_df.empty:
    fig = item_bar(keyword_df, "키워드", "빈도", kc["chart"], kc["color"])
    st.plotly_chart(fig, use_container_width=True)
with st.expander("표 보기"):
    st.dataframe(keyword_df, use_container_width=True)

# ---------------- VOC 분석 ----------------
st.subheader("🚨 VOC 분석")
vc = cfg["VOC 분석"]
voc_df = (
    filtered_df.groupby("VOC").size()
    .reset_index(name="건수")
    .sort_values("건수", ascending=False)
)
if vc["chart"] == "파이":
    voc_chart = px.pie(voc_df, names="VOC", values="건수")
else:
    voc_chart = px.bar(voc_df, x="VOC", y="건수", color="VOC")
st.plotly_chart(voc_chart, use_container_width=True)
with st.expander("표 보기"):
    st.dataframe(voc_df, use_container_width=True)

# ---------------- 상품별 리뷰 TOP ----------------
if has_product:
    pc = cfg["상품별 리뷰 TOP"]
    st.subheader(f"📦 상품별 리뷰 TOP{pc['n']}")
    product_df = (
        filtered_df.groupby("상품명").size()
        .reset_index(name="리뷰수")
        .sort_values("리뷰수", ascending=False)
        .head(pc["n"])
    )
    if not product_df.empty:
        fig = item_bar(product_df, "상품명", "리뷰수", pc["chart"], pc["color"])
        st.plotly_chart(fig, use_container_width=True)
    with st.expander("표 보기"):
        st.dataframe(product_df, use_container_width=True)

# ---------------- 상품 위험도 ----------------
if has_product:
    rk = cfg["상품 위험도"]
    st.subheader("⚠️ 상품 위험도")
    risk_df = (
        result.groupby("상품명")
        .agg(
            전체리뷰=("감성", "count"),
            부정리뷰=("감성", lambda x: (x == "부정").sum())
        )
        .reset_index()
    )
    risk_df["위험도(%)"] = (risk_df["부정리뷰"] / risk_df["전체리뷰"] * 100).round(1)
    risk_df = risk_df.sort_values("위험도(%)", ascending=False)
    risk_top = risk_df.head(rk["n"])
    if not risk_top.empty:
        fig = item_bar(risk_top, "상품명", "위험도(%)", rk["chart"], rk["color"])
        st.plotly_chart(fig, use_container_width=True)
    with st.expander("표 보기"):
        st.dataframe(risk_top, use_container_width=True)

# ---------------- 재구매 의향 ----------------
st.subheader("🔄 재구매 의향")
repurchase_keywords = ["재구매", "또 구매", "또 주문", "계속 사용", "계속 구매"]
repurchase_count = filtered_df["상품평"].astype(str).apply(
    lambda x: any(k in x for k in repurchase_keywords)
).sum()
repurchase_rate = round(
    repurchase_count / len(filtered_df) * 100, 1
) if len(filtered_df) else 0
st.metric("재구매 의향 비율", f"{repurchase_rate}%")

# ---------------- 리뷰 상세 ----------------
st.subheader("📝 리뷰 상세")
show_negative = st.checkbox("부정 리뷰만 보기")
view_cols = [x for x in ["감성", "카테고리", "VOC", "상품명", "상품평"] if x in result.columns]
view_df = filtered_df[view_cols]
if show_negative:
    view_df = view_df[view_df["감성"] == "부정"]


def color_sentiment(val):
    if val == "긍정":
        return "color:blue;font-weight:bold"
    if val == "부정":
        return "color:red;font-weight:bold"
    return ""


def highlight_row(row):
    if row["감성"] == "부정":
        return ["background-color:#ffeaea"] * len(row)
    elif row["감성"] == "긍정":
        return ["background-color:#eaf3ff"] * len(row)
    return [""] * len(row)


styled = (
    view_df.style
    .map(color_sentiment, subset=["감성"])
    .apply(highlight_row, axis=1)
)
st.dataframe(styled, use_container_width=True, height=600)

# ---------------- 경영진 인사이트 ----------------
st.subheader("💡 경영진 인사이트")
if len(voc_df) > 0:
    st.success(f"주요 VOC : {voc_df.iloc[0]['VOC']}")
if positive_rate >= 80:
    st.success("고객 만족도가 매우 높습니다.")
elif positive_rate >= 60:
    st.warning("고객 만족도가 보통 수준입니다.")
else:
    st.error("고객 만족도 개선이 필요합니다.")

# ---------------- 개선 우선순위 ----------------
st.subheader("🎯 개선 우선순위")
for rank, (idx, row) in enumerate(voc_df.head(3).iterrows(), start=1):
    st.write(f"{rank}위 {row['VOC']} ({row['건수']}건)")

# ---------------- 다운로드 ----------------
csv = filtered_df.to_csv(index=False, encoding="utf-8-sig")
st.download_button(
    "📥 결과 다운로드",
    csv,
    file_name="review_analysis.csv",
    mime="text/csv"
)
