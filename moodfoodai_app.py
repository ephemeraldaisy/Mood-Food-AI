import streamlit as st
from streamlit_geolocation import streamlit_geolocation
import google.generativeai as genai
import folium
from streamlit_folium import st_folium
import re
import time

# 1. 환경 설정
st.set_page_config(page_title="Mood Food AI", layout="wide", page_icon="🍱")

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("Streamlit Cloud 설정에서 GEMINI_API_KEY를 입력해주세요.")

# 2. 세션 상태 초기화 (기억 장치)
if 'disliked_foods' not in st.session_state:
    st.session_state.disliked_foods = []
if 'current_mood' not in st.session_state:
    st.session_state.current_mood = None
if 'recommendation_result' not in st.session_state:
    st.session_state.recommendation_result = None

# 3. [에러 해결!] 기분 데이터 정의를 위로 올렸습니다.
mood_map = {
    "🔥": "스트레스", "😔": "우울", "🧠": "집중 필요", "🥳": "판타스틱",
    "😴": "졸림", "😤": "화남", "🥗": "다이어트 중", "😭": "속상함",
    "😷": "감기 기운", "🥵": "열이 남"
}

VALID_MODEL = "models/gemini-flash-latest"

# PWA 및 스타일 설정
st.markdown("""
    <link rel="manifest" href="./manifest.json">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <style>
        .stButton>button { border-radius: 12px; height: 3em; font-size: 18px !important; }
    </style>
""", unsafe_allow_html=True)

st.title("📍 실시간 위치 기반 메뉴 추천 🍱")

# 4. 실시간 위치 가져오기
with st.sidebar:
    st.write("### 🌍 위치 설정")
    location = streamlit_geolocation()
    
    if location['latitude'] and location['longitude']:
        curr_lat, curr_lon = location['latitude'], location['longitude']
        st.success(f"현재 위치 감지: {curr_lat:.4f}, {curr_lon:.4f}")
    else:
        curr_lat, curr_lon = 37.2937156, 126.974337 # 기본값 (성균관대)
        st.warning("위치 권한을 허용해주세요. 기본값(성균관대)으로 설정됩니다.")

# 5. 레이아웃 정의
col1, col2 = st.columns([1, 1.2])

# 6. 기분 버튼 섹션 (col1)
with col1:
    st.subheader("지금 기분은 어떠신가요?")
    items = list(mood_map.items())
    for i in range(2):
        btn_cols = st.columns(5)
        for j in range(5):
            idx = i * 5 + j
            if idx < len(items):
                emoji, meaning = items[idx]
                if btn_cols[j].button(emoji, key=f"m_{idx}", use_container_width=True):
                    st.session_state.current_mood = meaning
                    st.session_state.recommendation_result = None # 새로운 기분일 땐 결과 초기화

# 7. 지도 표시 섹션 (col2)
with col2:
    st.write("### 📍 내 주변 맛집 지도")
    m = folium.Map(location=[curr_lat, curr_lon], zoom_start=15)
    folium.Marker([curr_lat, curr_lon], popup="현재 위치", icon=folium.Icon(color='red')).add_to(m)
    st_folium(m, width=600, height=450, key="dynamic_map")

# 8. 메뉴 추천 및 결과 표시 로직
if st.session_state.current_mood:
    mood = st.session_state.current_mood
    
    if st.session_state.recommendation_result is None:
        with st.spinner(f"'{mood}'에 딱 맞는 메뉴를 고르고 있어요..."):
            try:
                avoid_list = ", ".join(st.session_state.disliked_foods) if st.session_state.disliked_foods else "없음"
                model = genai.GenerativeModel(VALID_MODEL)
                prompt = f"""
                사용자의 실시간 좌표 [{curr_lat}, {curr_lon}] 인근에서 기분이 '{mood}'일 때 추천 메뉴 1개를 [음식명] 형식으로 답변해줘.
                근처에 실제로 있을 법한 식당 메뉴를 고려해줘.
                제외 리스트: [{avoid_list}]
                """
                
                response = model.generate_content(prompt)
                res_text = response.text
                match = re.search(r"\[(.*?)\]", res_text)
                food_keyword = match.group(1) if match else "맛있는 음식"
                
                st.session_state.recommendation_result = {
                    "food": food_keyword,
                    "text": res_text
                }
            except Exception as e:
                st.error(f"AI 응답 오류: {e}")

    if st.session_state.recommendation_result:
        res = st.session_state.recommendation_result
        with col1:
            st.write("---")
            st.success(f"### 🍱 오늘의 추천: {res['food']}")
            st.write(res['text']) 
            
            f_col1, f_col2 = st.columns(2)
            with f_col1:
                if st.button("👍 좋아요", use_container_width=True):
                    st.toast(f"사용자님의 취향 저격! {res['food']} 메모 완료! ✨", icon="😍")
            
            with f_col2:
                if st.button("👎 싫어요", use_container_width=True):
                    if res['food'] not in st.session_state.disliked_foods:
                        st.session_state.disliked_foods.append(res['food'])
                    st.toast(f"'{res['food']}' 제외 완료. 다른 메뉴를 찾아볼게요!", icon="🧹")
                    st.session_state.recommendation_result = None 
                    time.sleep(1)
                    st.rerun()

# 9. 제외 리스트 확인 (하단)
if st.session_state.disliked_foods:
    with st.expander("🚫 현재 제외된 메뉴 리스트"):
        st.write(", ".join(st.session_state.disliked_foods))
