import streamlit as st
from openai import OpenAI

# 1. 페이지 기본 설정
st.set_page_config(page_title="AI 정보 선생님", page_icon="🤖", layout="centered")

# 비밀 금고(secrets)에서 API 키를 꺼내 접속 준비
client = OpenAI(
    api_key=st.secrets.get("SOLAR_API_KEY", ""),
    base_url="https://api.upstage.ai/v1",
)

# AI의 성격
SYSTEM_PROMPT = (
    "너는 중고등학생에게 설명하는 친절한 정보 선생님이야. "
    "어려운 용어는 예시를 들어 쉬운 말로 바꿔 주고, 따뜻한 어조로 답해줘."
)

# 2. 대화 기록 관리 및 초기 인사말 설정
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "assistant", "content": "안녕하세요! 궁금한 정보 분야 지식이 있나요? 무엇이든 물어보세요! 😊"}
    ]

# 3. 사이드바 구성
with st.sidebar:
    st.title("⚙️ 설정 및 안내")
    st.info("이 앱은 Upstage Solar 모델을 활용하여 학생들에게 정보 교과 내용을 쉽게 설명해 줍니다.")
    
    # 대화 리셋 버튼
    if st.button("🔄 대화 내용 초기화"):
        st.session_state.messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "assistant", "content": "대화 내용이 초기화되었습니다. 새로운 질문을 해주세요! 😊"}
        ]
        st.rerun()

st.title("🤖 AI 정보 선생님")
st.caption("컴퓨터, 인공지능, 프로그래밍에 대해 무엇이든 질문해보세요!")

# 4. 대화 기록 화면 출력 (성격 문장 제외)
for msg in st.session_state.messages:
    if msg["role"] != "system":
        # 학생과 선생님 이모지 지정
        avatar = "🤖" if msg["role"] == "assistant" else "🧑‍🎓"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

# 5. 채팅 입력창
user_input = st.chat_input("궁금한 것을 물어보세요! (예: 인공지능이 뭐야?)")

if user_input:
    # 사용자 입력 저장 및 표시
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="🧑‍🎓"):
        st.markdown(user_input)

    # AI 답 받아오기
    with st.chat_message("assistant", avatar="🤖"):
        try:
            stream = client.chat.completions.create(
                model="solar-open2",
                messages=st.session_state.messages,
                reasoning_effort="none",
                stream=True,
            )
            answer = st.write_stream(
                chunk.choices[0].delta.content or ""
                for chunk in stream if chunk.choices
            )
            st.session_state.messages.append({"role": "assistant", "content": answer})
        except Exception as e:
            st.error("응답을 받지 못했습니다. API 키 설정이나 네트워크 연결을 확인해 주세요.")
