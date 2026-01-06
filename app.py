import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
from streamlit_echarts import st_echarts  # 추가됨
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
# 로그인 및 데이터 로드 로직 (기존과 동일)
# =========================
def check_login(username, password):
    return username == "admin" and password == "1234"

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

@st.cache_data
def load_cost_data():
    base_dir = Path(__file__).resolve().parent
    excel_path = base_dir / "data" / "data.xlsx"
    parquet_path = base_dir / "data" / "data.parquet"
    if parquet_path.exists():
        return pd.read_parquet(parquet_path)
    df = pd.read_excel(excel_path)
    df.to_parquet(parquet_path, index=False)
    return df

def reset_lower_filters(changed_level: int, max_level: int = 7):
    for lvl in range(changed_level + 1, max_level + 1):
        key = f"filter_분류{lvl}"
        if key in st.session_state:
            st.session_state.pop(key)

# =========================
# 부위별 공사비 페이지 (ECharts 적용)
# =========================
def page_overview():
    st.header("📌 부위별 공사비")
    df = load_cost_data()

    # ---------- 사이드바 필터 (기존 동일) ----------
    st.sidebar.subheader("🔎 필터")
    공사종류 = st.sidebar.selectbox(
        "공사종류",
        ["전체"] + sorted(df["공사종류"].dropna().unique().tolist())
    )
    filtered_df = df.copy()
    if 공사종류 != "전체":
        filtered_df = filtered_df[filtered_df["공사종류"] == 공사종류]

    for i in range(1, 8):
        col = f"분류{i}"
        key = f"filter_{col}"
        if col not in df.columns: continue
        options = sorted(filtered_df[col].dropna().unique().tolist())
        if not options:
            reset_lower_filters(i - 1); break
        if key in st.session_state and st.session_state[key] not in options:
            st.session_state.pop(key)
        val = st.sidebar.selectbox(col, ["전체"] + options, key=key,
                                   on_change=reset_lower_filters, kwargs={"changed_level": i})
        if val != "전체": filtered_df = filtered_df[filtered_df[col] == val]
        else: reset_lower_filters(i); break

    # =========================
    # 📊 ECharts용 데이터 준비
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

    # ECharts 옵션 설정
    x_data = agg_df["공사종류"].tolist()
    y_data = agg_df["금액"].tolist()

    options = {
            "title": {"text": "공사종류별 금액 (원)"},
            "tooltip": {
                "trigger": "axis",
                "axisPointer": {"type": "shadow"},
                "formatter": "{b} <br/> {c}원"
            },
            "grid": {"left": "3%", "right": "4%", "bottom": "10%", "containLabel": True},
            "xAxis": {
                "type": "category",
                "data": x_data,
                "axisLabel": {"interval": 0, "rotate": 30}
            },
            "yAxis": {
                "type": "value",
                "axisLabel": {"formatter": "{value}"}
            },
            # 애니메이션 세부 설정 (여기가 핵심입니다)
            "animationDuration": 2000,        # 처음 로드될 때 애니메이션 시간 (2초)
            "animationDurationUpdate": 1500,  # 데이터가 변경될 때(필터링) 애니메이션 시간 (1.5초)
            "animationEasing": "exponentialOut",
            "animationEasingUpdate": "exponentialOut", # 업데이트 시에도 부드러운 감속 적용
            
            "series": [
                {
                    "name": "금액",
                    "type": "bar",
                    "data": y_data,
                    "itemStyle": {
                        "color": "#5470c6",
                        "borderRadius": [5, 5, 0, 0] # 막대 상단 둥글게 (선택사항)
                    },
                    "showBackground": True,
                    "backgroundStyle": {"color": "rgba(180, 180, 180, 0.1)"}
                }
            ],
        }

        # 그래프 렌더링 시 key를 고정하면 불필요한 전체 재렌더링을 막아 애니메이션이 더 부드러워집니다.
    st_echarts(options=options, height="500px", key="main_cost_chart")

    # =========================
    # 📋 하단 테이블 (기존 동일)
    # =========================
    st.subheader("📋 내역 상세")
    table_cols = ["공사종류", "매칭_내역품명", "매칭_내역규격", "단위", "물량", "단가", "금액"]
    table_df = filtered_df[table_cols].copy()
    table_df = table_df.groupby(["공사종류", "매칭_내역품명", "매칭_내역규격", "단위", "단가"], as_index=False).agg({"물량": "sum", "금액": "sum"})
    table_df["물량"] = table_df["물량"].round(3)
    table_df["단가"] = table_df["단가"].map(lambda x: f"{int(x):,}")
    table_df["금액"] = table_df["금액"].map(lambda x: f"{int(x):,}")
    st.dataframe(table_df[table_cols], use_container_width=True, hide_index=True)

# (나머지 dashboard_page, 실행 로직 등은 기존과 동일)
def page_cost_ratio(): st.header("📊 공종별 공사비")
def page_similar_case(): st.header("🔍 유사 사례 단지")
def page_settings(): st.header("⚙️ 설계변경")

def dashboard_page():
    with st.sidebar:
        st.markdown("## 📁 메뉴")
        st.markdown(f"👤 사용자: **{st.session_state['user']}**")
        selected = option_menu(None, ["부위별 공사비", "공종별 공사비", "유사 사례", "설계변경"], 
                               icons=["house", "bar-chart", "search", "gear"], default_index=0)
        st.divider()
        if st.button("로그아웃"):
            st.session_state.clear()
            st.rerun()
    if selected == "부위별 공사비": page_overview()
    elif selected == "공종별 공사비": page_cost_ratio()
    elif selected == "유사 사례": page_similar_case()
    elif selected == "설계변경": page_settings()

if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if st.session_state["logged_in"]: dashboard_page()
else: login_page()
