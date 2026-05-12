import streamlit as st
from streamlit_geolocation import streamlit_geolocation
import google.generativeai as genai
import folium
from streamlit_folium import st_folium
import re
import time
from geopy.distance import geodesic

# 1. 환경 설정
st.set_page_config(page_title="Mood Food AI", layout="wide", page_icon="🍱")

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("Streamlit Cloud 설정에서 GEMINI_API_KEY를 입력해주세요.")

mood_colors = {
    "스트레스": "#FF4C33", # 강렬한 레드
    "우울": "#607D8B",    # 차분한 그레이블루
    "집중 필요": "#F2A2C0", # 핑크
    "판타스틱": "#FFD93B", # 밝은 노랑
    "졸림": "#9C27B0",    # 보라
    "화남": "#795548",    # 갈색
    "다이어트 중": "#4CAF50", # 그린
    "속상함": "#2196F3",   # 블루
    "감기 기운": "#BDBDBD", # 회색
    "열이 남": "#FF5722"   # 오렌지레드
}

# 2. 세션 상태 초기화
if 'bg_color' not in st.session_state:
    st.session_state.bg_color = "#0E1117" # 기본 다크모드 배경색

if 'disliked_foods' not in st.session_state:
    st.session_state.disliked_foods = []
if 'current_mood' not in st.session_state:
    st.session_state.current_mood = None
if 'recommendation_result' not in st.session_state:
    st.session_state.recommendation_result = None
if 'recent_history' not in st.session_state:
    st.session_state.recent_history = [] 

# 3. 기분 데이터 정의
mood_map = {
    "🔥": "스트레스", "😔": "우울", "🧠": "집중 필요", "🥳": "판타스틱",
    "😴": "졸림", "😤": "화남", "🥗": "다이어트 중", "😭": "속상함",
    "😷": "감기 기운", "🥵": "열이 남"
}

def set_bg_color(hex_code):
    # 배경색이 너무 진하면 글자가 안 보일 수 있으므로 
    # 투명도를 조절한 RGBA 스타일을 추천합니다 (0.1 ~ 0.2 정도)
    st.markdown(f"""
        <style>
        .stApp {{
            background-color: {hex_code}33; /* 뒤에 33을 붙여 투명도 20% 적용 */
            transition: background-color 0.5s ease; /* 부드러운 전환 효과 */
        }}
        </style>
    """, unsafe_allow_html=True)
    
set_bg_color(st.session_state.bg_color)

VALID_MODEL = "models/gemini-flash-latest"

# 스타일 설정
st.markdown("""
    <style>
        /* 버튼 내부 글자 크기 및 줄바꿈 설정 */
        .stButton>button {
            border-radius: 12px;
            height: 4.5em !important; /* 높이를 살짝 키움 */
            font-size: 14px !important;
            line-height: 1.2 !important;
            white-space: pre-line !important; /* \n(줄바꿈)을 인식하게 함 */
        }
        /* 마우스를 올렸을 때 강조 효과 */
        .stButton>button:hover {
            border: 2px solid #FFD93B !important;
            color: #FFD93B !important;
        }
    </style>
""", unsafe_allow_html=True)

st.title("📍 실시간 위치 기반 메뉴 추천 🍱")

# 4. 위치 설정 (사이드바 - 자동 & 수동 혼합)
with st.sidebar:
    st.write("### 🌍 위치 설정")
    
    # [수동 입력 추가] GPS 오차 대비
    manual_address = st.text_input("📍 현재 위치가 다른가요? 직접 입력하세요", placeholder="예: 혜화역, 성균관대 정문")
    
    st.write("---")
    st.write("🛰️ 자동 GPS 감지")
    location = streamlit_geolocation()
    
    # 위치 결정 로직: 수동 입력 우선 -> 자동 GPS -> 기본값 순서
    if manual_address:
        location_context = manual_address
        curr_lat, curr_lon = 37.2937156, 126.974337 # 좌표는 기본값 유지 (수동 입력시 텍스트 중심 추천)
        st.info(f"검색어 기반 추천: {manual_address}")
    elif location['latitude'] and location['longitude']:
        curr_lat, curr_lon = location['latitude'], location['longitude']
        location_context = f"좌표 [{curr_lat}, {curr_lon}]"
        st.success(f"현재 GPS 감지 완료")
    else:
        curr_lat, curr_lon = 37.2937156, 126.974337 # 기본값
        location_context = "성균관대 자연과학캠퍼스 근처"
        st.warning("위치를 입력하거나 GPS를 허용해주세요.")

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

                button_label = f"{emoji}\n{meaning}"
                if btn_cols[j].button(emoji, key=f"m_{idx}", use_container_width=True):
                    st.session_state.current_mood = meaning
                    st.session_state.bg_color = mood_colors.get(meaning, "#0E1117")
                    st.session_state.recommendation_result = None 
                    st.rerun()

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
        with st.spinner(f"'{mood}'에 딱 맞는 1km 이내 맛집을 찾는 중..."):
            try:
                avoid_list = list(set(st.session_state.disliked_foods + st.session_state.recent_history))
                avoid_str = ", ".join(avoid_list) if avoid_list else "없음"
                
                model = genai.GenerativeModel(VALID_MODEL)
                
                # 프롬프트에 위치 맥락(location_context) 반영
                prompt = f"""
                사용자의 위치 '{location_context}'에서 '도보 15분(1km) 이내'에 있는 실제 식당과 메뉴를 추천해줘.
                
                형식: [식당명 | 메뉴명]
                기분: {mood}에 어울리는 음식
                제외: [{avoid_str}]
                
                반드시 위치와 매우 가까운 실제 식당을 선택하고, 답변에 위치 정보와 도보 소요 시간을 포함해줘.
                """
                
                response = model.generate_content(prompt)
                res_text = response.text
                match = re.search(r"\[(.*?)\]", res_text)

                if match:
                    raw_info = match.group(1)
                    place_name, menu_name = map(str.strip, raw_info.split("|")) if "|" in raw_info else ("인근 맛집", raw_info)
                else:
                    place_name, menu_name = "인근 맛집", "맛있는 요리"

                st.session_state.recommendation_result = {
                    "place": place_name,
                    "menu": menu_name,
                    "full_text": res_text
                }
                
                full_rec = f"{place_name} - {menu_name}"
                if full_rec not in st.session_state.recent_history:
                    st.session_state.recent_history.append(full_rec)
                    if len(st.session_state.recent_history) > 5:
                        st.session_state.recent_history.pop(0)
                
            except Exception as e:
                st.error(f"AI 응답 오류: {e}")

    # 결과 화면 출력
    if st.session_state.recommendation_result:
        res = st.session_state.recommendation_result
        with col1:
            st.write("---")
            st.success(f"### 📍 {res['place']}")
            st.info(f"🍴 **추천 메뉴:** {res['menu']}")
            st.warning(f"🏃‍♂️ **검색 위치에서 1km 이내 (도보 권장)**")
            st.write(res['full_text'])
            
            search_url = f"https://map.naver.com/v5/search/{res['place']} {res['menu']}"
            st.link_button(f"🔗 {res['place']} 길찾기 & 거리 확인", search_url, use_container_width=True)
            
            st.write("")
            f_col1, f_col2 = st.columns(2)
            with f_col1:
                if st.button("👍 좋아요", use_container_width=True):
                    st.toast(f"취향 저격! {res['menu']} 메모 완료! ✨", icon="😍")
            with f_col2:
                if st.button("👎 싫어요", use_container_width=True):
                    if res['menu'] not in st.session_state.disliked_foods:
                        st.session_state.disliked_foods.append(res['menu'])
                    st.session_state.recommendation_result = None 
                    st.rerun()

# 9. 제외 리스트
if st.session_state.disliked_foods:
    with st.expander("🚫 현재 제외된 메뉴 리스트"):
        st.write(", ".join(st.session_state.disliked_foods))
