import streamlit as st
from streamlit_geolocation import streamlit_geolocation
import google.generativeai as genai
import folium
from streamlit_folium import st_folium
import re
import time
from geopy.distance import geodesic
import requests 

# 1. 환경 설정, 기분별 색상 및 데이터 정의
st.set_page_config(
    page_title="내 주변 1km 기분별 맛집 추천 - Mood Food AI", 
    layout="wide", 
    page_icon="🍱"
)

GOOGLE_CLIENT_ID = st.secrets["GOOGLE_CLIENT_ID"]
GOOGLE_CLIENT_SECRET = st.secrets["GOOGLE_CLIENT_SECRET"]
# 로컬 테스트 시에는 http://localhost:8501 , 배포 시에는 해당 도메인 입력
REDIRECT_URI = "http://localhost:8501" 

# 세션 상태 초기화 (로그인 여부 확인용)
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_info" not in st.session_state:
    st.session_state.user_info = None

# --- 구글 인증 URL 생성 함수 ---
def get_login_url():
    base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "query https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/userinfo.email",
        "access_type": "offline"
    }
    # 딕셔너리를 URL 파라미터 문자열로 변환
    url_params = "&".join([f"{k}={v}" for k, v in params.items()])
    return f"{base_url}?{url_params}"

# --- 인증 코드를 토큰 및 유저 정보로 교환하는 함수 ---
def login_user(code):
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code"
    }
    token_res = requests.post(token_url, data=data).json()
    
    if "access_token" in token_res:
        access_token = token_res["access_token"]
        # 유저 프로필 가져오기
        user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}
        user_info = requests.get(user_info_url, headers=headers).json()
        return user_info
    return None

# --- 로그인 로직 체크 ---
# 구글 로그인 후 돌아올 때 URL 파라미터에 ?code=... 가 붙습니다.
query_params = st.query_params
if "code" in query_params and not st.session_state.logged_in:
    auth_code = query_params["code"]
    user_data = login_user(auth_code)
    if user_data:
        st.session_state.logged_in = True
        st.session_state.user_info = user_data
        # URL 지저분한 파라미터 비우기
        st.query_params.clear()
        st.rerun()

# --- 화면 렌더링 분기 ---
if not st.session_state.logged_in:
    # 로그인 안 되었을 때 화면
    st.center()
    st.write("# 🔐 Mood Food AI 서비스 이용 안내")
    st.write("개인 맞춤형 식당 추천 및 제외 메뉴 기억 기능을 이용하시려면 구글 로그인이 필요합니다.")
    
    # 구글 로그인 버튼 디자인
    login_url = get_login_url()
    st.link_button("🚀 구글 계정으로 로그인하기", login_url, use_container_width=True)

else:
    # 로그인 성공 시 화면 (기존 서비스 코드 전체가 이 안으로 들어옵니다)
    user = st.session_state.user_info
    
    # 사이드바 상단에 유저 프로필 표시
    with st.sidebar:
        st.write(f"### 👤 {user.get('name')}님 환영합니다!")
        if user.get("picture"):
            st.image(user.get("picture"), width=60)
        
        if st.button("로그아웃", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user_info = None
            st.rerun()
            
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("Streamlit Cloud 설정에서 GEMINI_API_KEY를 입력해주세요.")

# SEO용 키워드 메타 데이터 정의 (크롤러 수집용 구조화 데이터)
mood_data = {
    "🔥": {"meaning": "스트레스", "color": "#FF4C33", "desc": "매운 음식, 자극적인 맛집"},
    "😔": {"meaning": "우울", "color": "#607D8B", "desc": "따뜻한 국물 요리, 위로가 되는 맛"},
    "🧠": {"meaning": "집중 필요", "color": "#F2A2C0", "desc": "뇌 회전에 좋은 고단백 식단, 생선 요리"},
    "🥳": {"meaning": "판타스틱", "color": "#FFD93B", "desc": "기분 좋은 날 가기 좋은 레스토랑, 고기 맛집"},
    "😴": {"meaning": "졸림", "color": "#9C27B0", "desc": "잠을 깨워줄 상큼한 메뉴, 비타민 가득한 식사"},
    "😤": {"meaning": "화남", "color": "#795548", "desc": "스트레스 해소용 씹는 맛이 있는 요리"},
    "🥗": {"meaning": "다이어트 중", "color": "#4CAF50", "desc": "저칼로리 샐러드, 키토제닉 건강 식단"},
    "😭": {"meaning": "속상함", "color": "#2196F3", "desc": "달콤하고 편안한 소울 푸드"},
    "😷": {"meaning": "감기 기운", "color": "#BDBDBD", "desc": "면역력을 높여줄 뜨끈한 보양식, 삼계탕"},
    "🥵": {"meaning": "열이 남", "color": "#FF5722", "desc": "시원한 냉면, 이열치열 매콤한 요리"}
}

# 2. 세션 상태 초기화
if 'bg_color' not in st.session_state:
    st.session_state.bg_color = "#0E1117" 
if 'disliked_foods' not in st.session_state:
    st.session_state.disliked_foods = []
if 'current_mood' not in st.session_state:
    st.session_state.current_mood = None
if 'current_budget' not in st.session_state:
    st.session_state.current_budget = None 
if 'recommendation_result' not in st.session_state:
    st.session_state.recommendation_result = None
if 'recent_history' not in st.session_state:
    st.session_state.recent_history = [] 

# 3. 스타일 설정 함수
def apply_custom_style(hex_code):
    st.markdown(f"""
        <style>
        .stApp {{
            background-color: {hex_code}40; 
            transition: background-color 0.8s ease;
        }}
        .stButton>button {{
            border-radius: 15px;
            height: 5.5em !important;
            white-space: pre-line !important; 
            font-size: 16px !important;
            line-height: 1.3 !important;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .stButton>button:hover {{
            border: 1px solid white !important;
            transform: scale(1.02);
            transition: 0.2s;
        }}
        </style>
    """, unsafe_allow_html=True)
    
apply_custom_style(st.session_state.bg_color)

VALID_MODEL = "models/gemini-flash-latest"

# --- [SEO 최적화 1: 시맨틱 텍스트 타이틀 및 메타 설명] ---
st.markdown("""
    <h1>📍 실시간 위치 기반 내 주변 맛집 및 메뉴 추천 🍱</h1>
    <p style='color: #888888; font-size: 16px;'>
        Mood Food AI는 사용자의 <strong>실시간 GPS 좌표</strong>와 <strong>현재 심리 상태(기분)</strong>, 
        그리고 <strong>예산 범위</strong>를 분석하여 도보 15분(1km) 이내의 검증된 실제 식당과 가성비 메뉴를 맞춤 추천하는 고도화된 웹 서비스입니다.
    </p>
""", unsafe_allow_html=True)

# 4. 위치 설정 (사이드바)
with st.sidebar:
    st.write("### 🌍 위치 설정")
    manual_address = st.text_input("📍 현재 위치가 다른가요? 직접 입력하세요", placeholder="예: 혜화역, 성균관대 정문")
    st.write("---")
    st.write("🛰️ 자동 GPS 감지")
    location = streamlit_geolocation()
    
    if manual_address:
        location_context = manual_address
        curr_lat, curr_lon = 37.2937156, 126.974337
        st.info(f"검색어 기반 추천: {manual_address}")
    elif location['latitude'] and location['longitude']:
        curr_lat, curr_lon = location['latitude'], location['longitude']
        location_context = f"좌표 [{curr_lat}, {curr_lon}]"
        st.success(f"현재 GPS 감지 완료")
    else:
        curr_lat, curr_lon = 37.2937156, 126.974337
        location_context = "성균관대 자연과학캠퍼스 근처"
        st.warning("위치를 입력하거나 GPS를 허용해주세요.")

# 5. 레이아웃 정의
col1, col2 = st.columns([1, 1.2])

# 6. 기분 및 버젯 버튼 섹션 (col1)
with col1:
    st.subheader("지금 기분은 어떠신가요?")
    items = list(mood_data.items())
    for i in range(2):
        btn_cols = st.columns(5)
        for j in range(5):
            idx = i * 5 + j
            if idx < len(items):
                emoji, info = items[idx]
                button_label = f"{emoji}\n{info['meaning']}"
                
                if btn_cols[j].button(button_label, key=f"m_{idx}", use_container_width=True):
                    st.session_state.current_mood = info['meaning']
                    st.session_state.bg_color = info['color']
                    st.session_state.recommendation_result = None 
                    st.rerun()

    st.write("")
    st.subheader("💰 예산 범위를 선택해주세요")
    budget_options = ["₩10,000 이하", "₩10,000-15,000", "₩15,000-20,000", "₩20,000+"]
    budget_cols = st.columns(4)
    
    for b_idx, b_opt in enumerate(budget_options):
        if budget_cols[b_idx].button(b_opt, key=f"b_{b_idx}", use_container_width=True):
            st.session_state.current_budget = b_opt
            st.session_state.recommendation_result = None
            st.rerun()

    status_text = []
    if st.session_state.current_mood: status_text.append(f"기분: **{st.session_state.current_mood}**")
    if st.session_state.current_budget: status_text.append(f"예산: **{st.session_state.current_budget}**")
    if status_text:
        st.info(" | ".join(status_text))

# 7. 지도 표시 섹션 (col2)
with col2:
    st.write("### 📍 내 주변 맛집 지도")
    m = folium.Map(location=[curr_lat, curr_lon], zoom_start=15)
    folium.Marker([curr_lat, curr_lon], popup="현재 위치", icon=folium.Icon(color='red')).add_to(m)
    st_folium(m, width=600, height=450, key="dynamic_map")

# 8. 메뉴 추천 및 결과 표시 로직
if st.session_state.current_mood and st.session_state.current_budget:
    mood = st.session_state.current_mood
    budget = st.session_state.current_budget
    
    if st.session_state.recommendation_result is None:
        with st.spinner(f"'{mood}'에 맞고 {budget} 이내인 1km 이내 맛집을 엔진에서 탐색 중..."):
            try:
                avoid_list = list(set(st.session_state.disliked_foods + st.session_state.recent_history))
                avoid_str = ", ".join(avoid_list) if avoid_list else "없음"
                
                model = genai.GenerativeModel(VALID_MODEL)
                prompt = f"""
                사용자의 위치 '{location_context}'에서 '도보 15분(1km) 이내'에 있는 실제로 현재 운영 중인 유명 식당을 추천해줘.
                
                ⚠️ [필수 제약 규칙] ⚠️
                1. **가격대 제한**: 추천하는 대표 메뉴의 가격은 반드시 사용자가 선택한 가격대 범위인 [{budget}] 내에 명확히 들어와야 해.
                2. **실제 존재하는 식당**: 존재하지 않는 가짜 식당 이름은 절대 지어내지 마. 유명 프랜차이즈나 네이버 검색 검증 맛집을 골라줘.

                형식: [식당명 | 메뉴명]
                기분: {mood}에 어울리는 음식
                제외 목록: [{avoid_str}]
                
                답변에는 선택한 메뉴의 대략적인 가격과 왜 이 예산 범위 내에서 최고의 선택인지, 그리고 현재 위치에서 도보로 몇 분 걸리는지 사실에 기반해서 다정하게 설명해줘.
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

    if st.session_state.recommendation_result:
        res = st.session_state.recommendation_result
        with col1:
            st.write("---")
            st.success(f"### 📍 {res['place']}")
            st.info(f"🍴 **추천 메뉴:** {res['menu']} ({budget})")
            st.warning(f"🏃‍♂️ **검색 위치에서 1km 이내 (도보 권장)**")
            st.write(res['full_text'])
            
            search_url = f"https://map.naver.com/v5/search/{location_context} {res['place']}"
            st.link_button(f"🔗 {res['place']} 길찾기 & 가격 확인", search_url, use_container_width=True)
            
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
                    
elif st.session_state.current_mood or st.session_state.current_budget:
    with col1:
        st.info("💡 **기분**과 **예산 범위**를 모두 한 번씩 클릭하시면 AI가 맞춤 맛집 검색을 시작합니다!")

# 9. 제외 리스트
if st.session_state.disliked_foods:
    with st.expander("🚫 현재 제외된 메뉴 리스트"):
        st.write(", ".join(st.session_state.disliked_foods))

# --- [SEO 최적화 2: 검색엔진 인덱싱용 하단 텍스트 가이드] ---
st.write("---")
st.markdown("## 🔍 Mood Food AI 서비스 안내 및 주요 키워드 가이드")
seo_col1, seo_col2 = st.columns(2)

with seo_col1:
    st.markdown("""
    ### 🎯 기분별 맞춤 음식 추천 키워드
    우리 서비스는 심리학적 감정 상태에 매칭되는 푸드 테라피를 제공합니다.
    * **스트레스 해소**: 화끈하게 매운 떡볶이, 닭발, 불짬뽕 전문 식당 매칭
    * **우울할 때**: 마음을 채워주는 뜨끈한 국밥, 국수, 라멘 맛집 정보
    * **직장인/학생 집중력 강화**: 견과류, 연어, 아보카도 기반의 브런치 및 고단백 웰빙 식단
    * **다이어트 및 헬스 식단**: 주변에서 가장 가까운 가성비 샐러드 팩토리, 키토 김밥 전문점
    """)

with seo_col2:
    st.markdown("""
    ### 💰 지갑 사정을 고려한 합리적인 예산 필터
    지역 구내식당 수준의 초가성비 혼밥부터 파인 다이닝까지 명확한 인덱스를 제공합니다.
    * **1만원 이하**: 대학가 가성비 밥집, 분식, 간편식, 국밥 중심 추천
    * **1만원 ~ 2만원 사이**: 일반적인 직장인 점심/저녁 맛집, 이탈리안 파스타, 일식 돈카츠
    * **2만원 이상**: 특별한 날 기분 전환을 위한 고품격 다이닝, 스테이크, 오마카세 등
    """)
