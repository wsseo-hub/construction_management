import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
import plotly.express as px
from pathlib import Path

# =========================
# 기본 설정
# =========================
st.set_page_config(
    page_title="공사비 대시보드",
    page_icon="📊",
    layout="wide"
)

# =========================
# 로그인 체크
# =========================
def check_login(username, password):
    return username == "admin" and password == "1234"

# =========================
# 로그인 페이지
# =========================
def login_page():
    st.title("🔐 로그인")

    with st.form("login_form"):
        username = st.text_input("아이디")
        password = st.text_input("비밀번호", type="password")
        submit = st.form_submit_button("로그인")

        if submit:
            if check_login(username, password):
                st.session_state["logged_in"] = True
                st.session_state["user"] = username
                st.rerun()
            else:
                st.error("아이디 또는 비밀번호가 올바르지 않습니다.")

# =========================
# 데이터 로드 (캐시)
# =========================
@st.cache_data
def load_cost_data():
    from pathlib import Path
    base_dir = Path(__file__).resolve().parent

    excel_path = base_dir / "data" / "data.xlsx"
    parquet_path = base_dir / "data" / "data.parquet"

    # 이미 변환되어 있으면 Parquet 사용
    if parquet_path.exists():
        return pd.read_parquet(parquet_path)

    # 최초 1회만 엑셀 로드
    df = pd.read_excel(excel_path)

    # Parquet로 저장
    df.to_parquet(parquet_path, index=False)

    return df

# =========================
# 하위 필터 reset 유틸
# =========================
def reset_lower_filters(changed_level: int, max_level: int = 7):
    for lvl in range(changed_level + 1, max_level + 1):
        key = f"filter_분류{lvl}"
        if key in st.session_state:
            st.session_state.pop(key)

# =========================
# 애니메이션 데이터 생성 (Ease-Out)
# =========================
def make_animated_df(df, value_col="금액", steps=8):
    frames = []
    for step in range(steps + 1):
        t = step / steps
        ratio = 1 - (1 - t) ** 3

        temp = df.copy()
        temp[value_col] = temp[value_col] * ratio
        temp["frame"] = step
        frames.append(temp)

    return pd.concat(frames, ignore_index=True)

# =========================
# 부위별 공사비 페이지
# =========================
def page_overview():
    st.header("📌 부위별 공사비")

    df = load_cost_data()

    # ---------- 공사종류 필터 ----------
    st.sidebar.subheader("🔎 필터")

    공사종류 = st.sidebar.selectbox(
        "공사종류",
        ["전체"] + sorted(df["공사종류"].dropna().unique().tolist())
    )

    filtered_df = df.copy()
    if 공사종류 != "전체":
        filtered_df = filtered_df[filtered_df["공사종류"] == 공사종류]

    # ---------- 연동 필터 (분류1~7) ----------
    for i in range(1, 8):
        col = f"분류{i}"
        key = f"filter_{col}"

        if col not in df.columns:
            continue

        options = sorted(filtered_df[col].dropna().unique().tolist())
        if not options:
            reset_lower_filters(i - 1)
            break

        if key in st.session_state and st.session_state[key] not in options:
            st.session_state.pop(key)

        val = st.sidebar.selectbox(
            col,
            ["전체"] + options,
            key=key,
            on_change=reset_lower_filters,
            kwargs={"changed_level": i}
        )

        if val != "전체":
            filtered_df = filtered_df[filtered_df[col] == val]
        else:
            reset_lower_filters(i)
            break

    # =========================
    # 📊 그래프용 집계
    # =========================
    agg_df = (
            filtered_df
            .groupby("공사종류", as_index=False)["금액"]
            .sum()
            .sort_values("금액", ascending=False)
        )

    if agg_df.empty:
        st.warning("선택 조건에 해당하는 데이터가 없습니다.")
        return

    ani_df = make_animated_df(agg_df, value_col="금액", steps=15) # 부드러움을 위해 step 약간 증가

    fig = px.bar(
        ani_df,
        x="공사종류",
        y="금액",
        animation_frame="frame",
        range_y=[0, agg_df["금액"].max() * 1.1],
        color="공사종류", # 시각적 효과 추가
        color_discrete_sequence=px.colors.qualitative.Pastel
    )

    # 애니메이션 속도 및 자동 실행 설정
    fig.update_layout(
        title="공사종류별 금액",
        xaxis_title="공사종류",
        yaxis_title="금액 (원)",
        yaxis_tickformat=",",
        height=520,
        # 핵심: 차트가 로드되자마자 재생되도록 설정
    )

    # 애니메이션 컨트롤 버튼 제거 및 자동 재생 속도 설정
    fig["layout"]["updatemenus"][0]["buttons"][0]["args"][1]["frame"]["duration"] = 50
    fig["layout"]["updatemenus"][0]["buttons"][0]["args"][1]["transition"]["duration"] = 30
    
    # 그래프를 그릴 때 'Play' 버튼이 자동으로 눌린 상태처럼 동작하게 함
    # Plotly Express의 기본 play 버튼 설정을 활용
    fig.layout.updatemenus[0].type = 'dropdown' # 버튼 대신 드롭다운으로 숨기거나 (선택사항)
    fig.layout.updatemenus[0].showactive = True

    # Streamlit에서 Plotly 차트 출력
    # config 설정을 통해 모드바를 제어할 수 있습니다.
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # =========================
    # 📋 하단 테이블 (원본 데이터 집계)
    # =========================
    st.subheader("📋 내역 상세 (필터 조건 반영)")

    table_cols = [
        "공사종류",
        "매칭_내역품명",
        "매칭_내역규격",
        "단위",
        "물량",
        "단가",
        "금액",
    ]

    # 필요한 컬럼만 사용
    table_df = filtered_df[table_cols].copy()

    # 동일 품명 + 규격 통합
    table_df = (
        table_df
        .groupby(
            ["공사종류", "매칭_내역품명", "매칭_내역규격", "단위", "단가"],
            as_index=False
        )
        .agg({
            "물량": "sum",
            "금액": "sum"
        })
    )

    # 가독성 포맷
    table_df["물량"] = table_df["물량"].round(3)
    table_df["단가"] = table_df["단가"].map(lambda x: f"{int(x):,}")
    table_df["금액"] = table_df["금액"].map(lambda x: f"{int(x):,}")

    # 컬럼 순서 보장
    table_df = table_df[table_cols]

    st.dataframe(
        table_df,
        use_container_width=True,
        hide_index=True
    )

# =========================
# 기타 페이지
# =========================
def page_cost_ratio():
    st.header("📊 공종별 공사비")

def page_similar_case():
    st.header("🔍 유사 사례 단지")

def page_settings():
    st.header("⚙️ 설계변경")

# =========================
# 대시보드 메인
# =========================
def dashboard_page():
    with st.sidebar:
        st.markdown("## 📁 메뉴")
        st.markdown(f"👤 사용자: **{st.session_state['user']}**")

        selected = option_menu(
            menu_title=None,
            options=["부위별 공사비", "공종별 공사비", "유사 사례", "설계변경"],
            icons=["house", "bar-chart", "search", "gear"],
            default_index=0,
        )

        st.divider()
        if st.button("로그아웃"):
            st.session_state.clear()
            st.rerun()

    if selected == "부위별 공사비":
        page_overview()
    elif selected == "공종별 공사비":
        page_cost_ratio()
    elif selected == "유사 사례":
        page_similar_case()
    elif selected == "설계변경":
        page_settings()

# =========================
# 실행 로직
# =========================
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if st.session_state["logged_in"]:
    dashboard_page()
else:
    login_page()
