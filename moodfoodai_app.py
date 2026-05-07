import streamlit as st
import google.generativeai as genai
import folium
from streamlit_folium import st_folium
import re
import time

# 1. 환경 설정 및 세션 메모리 초기화
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("Streamlit Cloud 설정에서 GEMINI_API_KEY를 입력해주세요.")

# [핵심] 사용자가 싫어하는 음식을 기억하는 저장소
if 'disliked_foods' not in st.session_state:
    st.session_state.disliked_foods = []

st.set_page_config(page_title="Mood Food AI", layout="wide", page_icon="🍱")

# PWA 및 스타일 설정
st.markdown("""
    <link rel="manifest" href="./manifest.json">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <style>
        .stButton>button { border-radius: 12px; height: 3em; font-size: 18px !important; }
    </style>
""", unsafe_allow_html=True)

st.title("🌍 10가지 기분별 메뉴 추천 🍱")

# 2. 기분 및 위치 설정
VALID_MODEL = "models/gemini-flash-latest"
SKKU_LAT, SKKU_LON = 37.2937156, 126.974337
mood_map = {
    "🔥": "스트레스", "😔": "우울", "🧠": "집중 필요", "🥳": "판타스틱",
    "😴": "졸림", "😤": "화남", "🥗": "다이어트 중", "😭": "속상함",
    "😷": "감기 기운", "🥵": "열이 남"
}

col1, col2 = st.columns([1, 1.2])

with col1:
    st.subheader("지금 기분은 어떠신가요?")
    items = list(mood_map.items())
    user_input = None
    for i in range(2):
        btn_cols = st.columns(5)
        for j in range(5):
            idx = i * 5 + j
            if idx < len(items):
                emoji, meaning = items[idx]
                if btn_cols[j].button(emoji, key=f"m_{idx}", use_container_width=True):
                    user_input = meaning

with col2:
    st.write("### 📍 성균관대 인근 맛집 지도")
    m = folium.Map(location=[SKKU_LAT, SKKU_LON], zoom_start=15)
    folium.Marker([SKKU_LAT, SKKU_LON], popup="내 위치", icon=folium.Icon(color='red')).add_to(m)
    st_folium(m, width=600, height=450, key="main_map")

# 3. 메뉴 추천 로직 (싫어요 반영)
if user_input:
    # 싫어하는 리스트를 텍스트로 변환
    avoid_list = ", ".join(st.session_state.disliked_foods) if st.session_state.disliked_foods else "없음"
    
    with st.spinner(f"'{user_input}'에 맞는 메뉴를 찾는 중..."):
        try:
            model = genai.GenerativeModel(VALID_MODEL)
            # [핵심] Representation Space 개념을 프롬프트에 주입하여 유사 메뉴 제외
            prompt = f"""
            좌표 [{SKKU_LAT}, {SKKU_LON}] 근처에서 기분이 '{user_input}'일 때 메뉴 1개를 [음식명] 형식으로 추천해줘.
            절대 추천 금지 리스트: [{avoid_list}]
            위 리스트에 있는 음식과 의미론적으로 유사하거나(예: 포케와 샐러드볼) 주재료가 겹치는 음식도 절대 제외해줘.
            """
            
            response = model.generate_content(prompt)
            res_text = response.text
            match = re.search(r"\[(.*?)\]", res_text)
            food_keyword = match.group(1) if match else "추천 메뉴"

            with col1:
                st.write("---")
                st.success(f"### 🍱 추천: {food_keyword}")
                st.write(res_text)
                
                # 피드백 버튼
                f_col1, f_col2 = st.columns(2)
                with f_col1:
                    if st.button("👍 좋아요"):
                        st.toast("취향을 기억하겠습니다! ✨")
                with f_col2:
                    if st.button("👎 싫어요"):
                        if food_keyword not in st.session_state.disliked_foods:
                            st.session_state.disliked_foods.append(food_keyword)
                        st.toast(f"'{food_keyword}'와 유사한 메뉴를 앞으로 제외합니다.")
                        time.sleep(1)
                        st.rerun() # 즉시 재실행하여 새로운 메뉴 추천

        except Exception as e:
            st.error(f"에러 발생: {e}")

# 싫어하는 메뉴 리스트 디버깅용 (필요 없으면 삭제 가능)
if st.session_state.disliked_foods:
    with st.expander("🚫 현재 제외된 메뉴 리스트"):
        st.write(", ".join(st.session_state.disliked_foods))
