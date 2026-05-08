import streamlit as st
from streamlit_geolocation import streamlit_geolocation
import google.generativeai as genai
import folium
from streamlit_folium import st_folium
import re
import time

# 1. 세션 상태 초기화 (기억 장치)
if 'disliked_foods' not in st.session_state:
    st.session_state.disliked_foods = []
if 'current_mood' not in st.session_state:
    st.session_state.current_mood = None
if 'recommendation_result' not in st.session_state:
    st.session_state.recommendation_result = None

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

st.title("📍 실시간 위치 기반 메뉴 추천 🍱")

# 2. 기분 및 위치 설정
VALID_MODEL = "models/gemini-flash-latest"
SKKU_LAT, SKKU_LON = 37.2937156, 126.974337
mood_map = {
    "🔥": "스트레스", "😔": "우울", "🧠": "집중 필요", "🥳": "판타스틱",
    "😴": "졸림", "😤": "화남", "🥗": "다이어트 중", "😭": "속상함",
    "😷": "감기 기운", "🥵": "열이 남"
}

col1, col2 = st.columns([1, 1.2])

# 2. 기분 버튼 섹션
with col1:
    st.subheader("지금 기분은 어떠신가요?")
    items = list(mood_map.items())
    for i in range(2):
        btn_cols = st.columns(5)
        for j in range(5):
            idx = i * 5 + j
            if idx < len(items):
                emoji, meaning = items[idx]
                # 버튼을 누르면 세션 상태에 저장
                if btn_cols[j].button(emoji, key=f"m_{idx}", use_container_width=True):
                    st.session_state.current_mood = meaning
                    st.session_state.recommendation_result = None # 새로운 기분일 땐 결과 초기화

# 3. 메뉴 추천 및 결과 표시 로직
# 세션에 기분이 저장되어 있다면 결과를 보여줍니다.
if st.session_state.current_mood:
    mood = st.session_state.current_mood
    
    # 아직 결과가 없다면 AI에게 물어봅니다.
    if st.session_state.recommendation_result is None:
        with st.spinner(f"'{mood}'에 딱 맞는 메뉴를 고르고 있어요..."):
            try:
                avoid_list = ", ".join(st.session_state.disliked_foods) if st.session_state.disliked_foods else "없음"
                model = genai.GenerativeModel(VALID_MODEL)
                prompt = f"좌표 [{SKKU_LAT}, {SKKU_LON}] 근처, 기분 '{mood}'에 맞는 메뉴 1개를 [음식명] 형식으로 추천해줘. 금지: [{avoid_list}] 및 유사메뉴."
                
                response = model.generate_content(prompt)
                res_text = response.text
                match = re.search(r"\[(.*?)\]", res_text)
                food_keyword = match.group(1) if match else "맛있는 음식"
                
                # 결과를 세션에 저장 (박제!)
                st.session_state.recommendation_result = {
                    "food": food_keyword,
                    "text": res_text
                }
            except Exception as e:
                st.error(f"AI 응답 오류: {e}")

    # 박제된 결과가 있다면 화면에 출력
    if st.session_state.recommendation_result:
        res = st.session_state.recommendation_result
        with col1:
            st.write("---")
            st.success(f"### 🍱 오늘의 추천: {res['food']}")
            st.write(res['text']) # AI의 상세 설명(멘트) 출력
            
            # 피드백 버튼
            f_col1, f_col2 = st.columns(2)
            with f_col1:
                if st.button("👍 좋아요", use_container_width=True):
                    st.toast(f"사용자님의 취향 저격! {res['food']} 메모 완료! ✨", icon="😍")
            
            with f_col2:
                if st.button("👎 싫어요", use_container_width=True):
                    if res['food'] not in st.session_state.disliked_foods:
                        st.session_state.disliked_foods.append(res['food'])
                    st.toast(f"'{res['food']}' 제외 완료. 다른 메뉴를 찾아볼게요!", icon="🧹")
                    st.session_state.recommendation_result = None # 결과 지우기
                    time.sleep(1)
                    st.rerun() # 새로운 추천을 위해 재실행
