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
if 'recent_history' not in st.session_state:
    st.session_state.recent_history = [] #최근 5개 추천 결과 저장

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
                avoid_list = list(set(st.session_state.disliked_foods + st.session_state.recent_history))
                avoid_str = ", ".join(avoid_list) if avoid_list else "없음"
                model = genai.GenerativeModel(VALID_MODEL)
                prompt = f"""
                사용자의 실시간 좌표 [{curr_lat}, {curr_lon}] 인근에서 기분이 '{mood}'일 때 가기 좋은 '실제 식당'과 '추천 메뉴'를 하나 골라줘.
                
                반드시 아래 형식을 지켜서 답변해:
                1. 답변 시작 부분에 [식당이름 | 대표메뉴] 형식으로 핵심 정보를 적을 것. (예: [성경만두요리전문점 | 빨간전골])
                2. 그 아래에는 왜 그 식당의 그 메뉴가 현재 좌표와 기분에 어울리는지 다정하게 설명해줘.
                3. 근처에 실제로 존재하는 식당이어야 해.
                
                제외 리스트: [{avoid_str}]
                """
                
                response = model.generate_content(prompt)
                res_text = response.text
                match = re.search(r"\[(.*?)\]", res_text)
                if match:
                    raw_info = match.group(1) # "식당명 | 메뉴명" 형태
                    if "|" in raw_info:
                        place_name, menu_name = map(str.strip, raw_info.split("|"))
                    else:
                        place_name, menu_name = "인근 식당", raw_info
                    
                    # 최근 기록에는 "식당명 - 메뉴명" 형태로 저장하여 중복 방지
                    full_recommendation = f"{place_name} - {menu_name}"
                    if full_recommendation not in st.session_state.recent_history:
                        st.session_state.recent_history.append(full_recommendation)
                        if len(st.session_state.recent_history) > 5:
                            st.session_state.recent_history.pop(0)
                
                    # 결과를 세션에 저장
                    st.session_state.recommendation_result = {
                        "place": place_name,
                        "menu": menu_name,
                        "full_text": res_text
                    }
        
                food_keyword = match.group(1) if match else "맛있는 음식"

                #history 반영
                if food_keyword not in st.session_state.recent_history:
                    st.session_state.recent_history.append(food_keyword)

                #Queue of 5
                if len(st.session_state.recent_history) > 5:
                    st.session_state.recent_history.pop(0) #Delete the oldest
                
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
            # 식당명과 메뉴명을 각각 다른 스타일로 표시
            st.success(f"### 📍 {res['place']}")
            st.info(f"🍴 **추천 메뉴:** {res['menu']}")
            st.write(res['full_text'])
            
            # 피드백 버튼 아래에 추가
            search_url = f"https://map.naver.com/v5/search/{res['place']} {res['menu']}"
            st.link_button(f"🔗 {res['place']} 길찾기 (네이버 지도)", search_url)

            st.write("")

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


