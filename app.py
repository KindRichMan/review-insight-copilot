import streamlit as st
import pandas as pd
import plotly.express as px
from collections import Counter
import re

st.set_page_config(
    page_title="Review Insight Copilot",
    layout="wide"
)

st.title("📊 Review Insight Copilot")

# ============================================================
# 사이드바 : 시각화 설정 (앱 사용자가 실시간으로 변경 가능)
# ============================================================
st.sidebar.header("⚙️ 시각화 설정")

chart_type = st.sidebar.radio(
    "감성 차트 종류",
    ["파이", "도넛", "막대"],
    horizontal=True
)

st.sidebar.markdown("**감성 색상**")
pos_color = st.sidebar.color_picker("긍정", "#1f77b4")
neu_color = st.sidebar.color_picker("중립", "#aec7e8")
neg_color = st.sidebar.color_picker("부정", "#d62728")
sentiment_color_map = {
    "긍정": pos_color,
    "중립": neu_color,
    "부정": neg_color
}

voc_chart_type = st.sidebar.radio(
    "VOC 차트 종류",
    ["막대", "파이"],
    horizontal=True
)

top_keyword_n = st.sidebar.slider(
    "TOP 키워드 개수", 5, 30, 20
)
top_product_n = st.sidebar.slider(
    "상품 / 위험도 TOP N", 5, 30, 20
)

uploaded_file = st.file_uploader(
    "엑셀 파일 업로드",
    type=["xlsx"]
)


def sentiment(text):
    text = str(text)

    positive_words = [
        "좋", "만족", "추천", "부드럽",
        "흡수", "편하", "최고", "감사",
        "빠르", "재구매", "가성비",
        "믿고", "잘사용"
    ]

    negative_words = [
        "아쉽", "실망", "불편",
        "늦", "문제", "파손",
        "끊어", "찝찝",
        "힘들", "품절",
        "별로", "불만"
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


def make_sentiment_chart(sentiment_df, chart_type, color_map):
    if chart_type == "막대":
        fig = px.bar(
            sentiment_df,
            x="감성", y="건수",
            color="감성",
            color_discrete_map=color_map
        )
    else:
        hole = 0.4 if chart_type == "도넛" else 0
        fig = px.pie(
            sentiment_df,
            names="감성", values="건수",
            color="감성",
            color_discrete_map=color_map,
            hole=hole
        )
    return fig


if uploaded_file:

    df = pd.read_excel(uploaded_file, engine="openpyxl")

    review_col = "상품평"

    if review_col not in df.columns:
        st.error("상품평 컬럼을 찾지 못했습니다.")
        st.stop()

    result = df.copy()

    result["감성"] = (
        result["상품평"].fillna("").astype(str).apply(sentiment)
    )

    if "상품명" in result.columns:
        result["카테고리"] = (
            result["상품명"].fillna("").astype(str).apply(category_mapping)
        )
    else:
        result["카테고리"] = "기타"

    result["VOC"] = (
        result["상품평"].fillna("").astype(str).apply(voc_mapping)
    )

    col1, col2 = st.columns(2)

    with col1:
        selected_category = st.selectbox(
            "카테고리",
            ["전체"] + sorted(result["카테고리"].unique().tolist())
        )

    with col2:
        selected_voc = st.selectbox(
            "VOC",
            ["전체"] + sorted(result["VOC"].unique().tolist())
        )

    filtered_df = result.copy()

    if selected_category != "전체":
        filtered_df = filtered_df[filtered_df["카테고리"] == selected_category]

    if selected_voc != "전체":
        filtered_df = filtered_df[filtered_df["VOC"] == selected_voc]

    total = len(filtered_df)
    positive = len(filtered_df[filtered_df["감성"] == "긍정"])
    negative = len(filtered_df[filtered_df["감성"] == "부정"])
    neutral = len(filtered_df[filtered_df["감성"] == "중립"])

    positive_rate = round(positive / total * 100, 1) if total else 0

    a, b, c, d = st.columns(4)
    a.metric("전체 리뷰", total)
    b.metric("긍정", positive)
    c.metric("부정", negative)
    d.metric("긍정률", f"{positive_rate}%")

    # ---------------- 감성 분포 ----------------
    st.subheader("📈 감성 분포")

    sentiment_df = pd.DataFrame({
        "감성": ["긍정", "중립", "부정"],
        "건수": [positive, neutral, negative]
    })

    fig = make_sentiment_chart(sentiment_df, chart_type, sentiment_color_map)
    st.plotly_chart(fig, use_container_width=True)

    # ---------------- 카테고리별 리뷰 수 ----------------
    st.subheader("📂 카테고리별 리뷰 수")

    category_count = (
        result.groupby("카테고리")
        .size()
        .reset_index(name="리뷰수")
        .sort_values("리뷰수", ascending=False)
    )

    st.dataframe(category_count, use_container_width=True)

    # ---------------- 카테고리별 평점 ----------------
    if "평점" in result.columns:
        st.subheader("⭐ 카테고리별 평점")

        rating_df = (
            result.groupby("카테고리")["평점"].mean().reset_index()
        )

        st.dataframe(rating_df, use_container_width=True)

    # ---------------- TOP 키워드 ----------------
    st.subheader("🔥 TOP 키워드")

    text = " ".join(filtered_df["상품평"].fillna("").astype(str))
    words = re.findall(r"[가-힣]{2,}", text)

    stop_words = {
        "좋아요", "있어요", "합니다",
        "너무", "정말", "제품", "사용"
    }

    words = [w for w in words if w not in stop_words]

    keyword_df = pd.DataFrame(
        Counter(words).most_common(top_keyword_n),
        columns=["키워드", "빈도"]
    )

    st.dataframe(keyword_df, use_container_width=True)

    # ---------------- VOC 분석 ----------------
    st.subheader("🚨 VOC 분석")

    voc_df = (
        filtered_df.groupby("VOC")
        .size()
        .reset_index(name="건수")
        .sort_values("건수", ascending=False)
    )

    st.dataframe(voc_df, use_container_width=True)

    if voc_chart_type == "파이":
        voc_chart = px.pie(voc_df, names="VOC", values="건수")
    else:
        voc_chart = px.bar(voc_df, x="VOC", y="건수", color="VOC")

    st.plotly_chart(voc_chart, use_container_width=True)

    # ---------------- 상품별 리뷰 TOP ----------------
    st.subheader(f"📦 상품별 리뷰 TOP{top_product_n}")

    product_df = (
        filtered_df.groupby("상품명")
        .size()
        .reset_index(name="리뷰수")
        .sort_values("리뷰수", ascending=False)
        .head(top_product_n)
    )

    st.dataframe(product_df, use_container_width=True)

    # ---------------- 상품 위험도 ----------------
    st.subheader("⚠️ 상품 위험도")

    risk_df = (
        result.groupby("상품명")
        .agg(
            전체리뷰=("감성", "count"),
            부정리뷰=("감성", lambda x: (x == "부정").sum())
        )
        .reset_index()
    )

    risk_df["위험도(%)"] = (
        risk_df["부정리뷰"] / risk_df["전체리뷰"] * 100
    ).round(1)

    risk_df = risk_df.sort_values("위험도(%)", ascending=False)

    st.dataframe(risk_df.head(top_product_n), use_container_width=True)

    # ---------------- 재구매 의향 ----------------
    st.subheader("🔄 재구매 의향")

    repurchase_keywords = [
        "재구매", "또 구매", "또 주문",
        "계속 사용", "계속 구매"
    ]

    repurchase_count = (
        filtered_df["상품평"].astype(str).apply(
            lambda x: any(k in x for k in repurchase_keywords)
        ).sum()
    )

    repurchase_rate = round(
        repurchase_count / len(filtered_df) * 100, 1
    ) if len(filtered_df) else 0

    st.metric("재구매 의향 비율", f"{repurchase_rate}%")

    # ---------------- 리뷰 상세 ----------------
    st.subheader("📝 리뷰 상세")

    show_negative = st.checkbox("부정 리뷰만 보기")

    view_df = filtered_df[["감성", "카테고리", "VOC", "상품명", "상품평"]]

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
        top_voc = voc_df.iloc[0]["VOC"]
        st.success(f"주요 VOC : {top_voc}")

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
