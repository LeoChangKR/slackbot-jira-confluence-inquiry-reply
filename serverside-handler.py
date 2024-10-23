import re
import os
import ssl
import certifi
from slack_sdk import WebClient
# from slack_sdk.errors import SlackApiError
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import odin_openai_wrapper as openai 
#import openai ###local
import json

ssl_context = ssl.create_default_context(cafile=certifi.where())
slack_bot_token = os.environ['SLACK_BOT_TOKEN'] 
slack_app_token = os.environ['SLACK_APP_TOKEN'] 
# Initialize the OpenAI API with your API key
api_key = "" 
#openai.api_key = '$YOUR OPENAI API KEY$' 

ignored_users = ["$USERID$", "$USERID$", "$USERID$"]  # Replace with the actual user IDs you want to ignore

client = WebClient(token=slack_bot_token, ssl=ssl_context)
app = App(client = client)

# 질문에 대한 답변을 위한 딕셔너리
qna_dict = {
    "jira_pw": "안녕하세요! <@{user_id}>님\n$YOUR POLICY INFO$",
    "slack_alarm": "안녕하세요! <@{user_id}>님\n$YOUR POLICY INFO$",
    "issue_create": "안녕하세요! <@{user_id}>님\n$YOUR POLICY INFO$",
    "jira_sprint": "안녕하세요! <@{user_id}>님\n$YOUR POLICY INFO$",
    "jira_close": "안녕하세요! <@{user_id}>님\n$YOUR POLICY INFO$"
}

#JIRA/WIKI PW 초기화 요청
@app.message(re.compile(r"(?=.*jira|지라|위키|wiki)(?=.*(?:password|pw|로그인|login|비밀번호|비번|패스워드))", re.IGNORECASE))
def jira_pw(message, say):
    if message["user"] not in ignored_users:
        send_response_common("jira_pw", message, say)

#Slack 알람 관련
@app.message(re.compile(r"(?=.*슬랙|slack)(?=.*(?:alarm|알람|알림|IAMS|notification))", re.IGNORECASE))
def slack_alarm(message, say):
    if message["user"] not in ignored_users:
        send_response_common("slack_alarm", message, say)

#Jobs that need jira issue creation
@app.message(re.compile(r"(?=.*jira|지라|위키|wiki|프로젝트|project|space|공간|이슈타입|이슈 타입|issue type|issuetype)(?=.*(?:생성|변경|수정|create|추가|add))", re.IGNORECASE))
def issue_create(message, say):
    if message["user"] not in ignored_users:
        send_response_common("issue_create", message, say)

#Inquiries related to sprint creation
@app.message(re.compile(r"(?=.*sprint|스프린트)(?=.*(?:add|create|edit|추가|생성|수정))", re.IGNORECASE))
def jira_sprint(message, say):
    if message["user"] not in ignored_users:
        send_response_common("jira_sprint", message, say)

#Inquiries related to jira issue resolving
@app.message(re.compile(r"(?=.*지라|jira|이슈|issue)(?=.*(?:리졸브|resolve|클로즈|close|종료))", re.IGNORECASE))
def jira_close(message, say):
    if message["user"] not in ignored_users:
        send_response_common("jira_close", message, say)

@app.message(re.compile(r".*", re.IGNORECASE))
def chatgpt_based_response(message, say):
    global responded_threads

    # Check if the message is part of a thread
    if check_thread(message) == False:
        return

    if message["user"] in ignored_users:
        return

    # You can extract the user's message from 'message' object
    user_message = message.get("text", "")

    # Call the 'handle' function to get a chatbot response
    chatbot_response = get_chatbot_response(user_message)
    chatbot_response = chatbot_response + "\n\n해당 답변은 Chatgpt 답변이라 부정확할 수 있습니다. 답변에 대해 추가 질문이 있다면 담당자<@$ADMIN ID$>를 멘션해주세요"

    # 응답을 보냅니다.
    send_response(say, message, chatbot_response)


def get_chatbot_response(user_message):
    # Replace keywords in the user's message
    user_message = user_message.replace("위키", "confluence").replace("Wiki", "confluence")

    data = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant for Jira and Confluence."},
            {"role": "system", "content": "Answer only in Korean language."},
            {"role": "system", "content": "We use Jira Server version $VERSION$ with scriptrunner for Jira version $VERSION$ and Confluence Server version $VERSION$. Only answer based on these versions."},
            {"role": "system", "content": "JQL functions available using scriptrunner are $LIST$. Only answer using these scriptrunner JQLs and the built in JQLs for jira server version $VERSION$"},
            {"role": "system", "content": "Please answer using two categories : 1.사용자가 확인 가능한 작업 2.관리자가 확인해야할 작업"},
            {"role": "system", "content": "The steps that the user can check himself will go under 1.사용자가 확인 가능한 작업. the steps that jira or confluence admin must check will go to 2.관리자가 확인해야할 작업."},
            {"role": "system", "content": "Please limit the answer to maximum 3 lines only for 2.관리자가 확인해야할 작업. I don't want to see the detailed process and steps"},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.1
    }
  

    response = openai.ChatCompletion.create(data, api_key) 
    # TestOnly - Use "gpt-3.5-turbo" as the model name
    #response = openai.ChatCompletion.create(
    #    model="gpt-3.5-turbo",
    #    messages=data["messages"]  # Pass only the "messages" part of the data
    #)

    response_dict = json.loads(response)

    # Access the "content" field
    chatbot_reply = response_dict['data']['choices'][0]['message']['content'] 
    #chatbot_reply = response['choices'][0]['message']['content'] ###local
    # Check if the response contains steps that need administrator access

    return chatbot_reply
    
# Define and initialize the set
#responded_threads = set()
    
# 스레드 체크
def check_thread(message):
    # Check if the message is part of a thread
    is_thread = "thread_ts" in message
    if is_thread:
        thread_ts = message["thread_ts"]

        # Check if the thread has already been responded to
        if thread_ts in responded_threads:
            return False

        # Check if the message is in the same thread as the main message
        if thread_ts != message["ts"]:
            return False
        
    return True

# 응답 보내기
def send_response(say, message, response):
    is_thread = "thread_ts" in message
    #print(message)
    # Send the chatbot's response using 'say'
    say(text=response, channel=message["channel"], thread_ts=message["ts"])

    # If it's a thread message, record that you've responded to this thread
    if is_thread:
        responded_threads.add(message.get("thread_ts"))

# 응답 보내기 (공통)
def send_response_common(key, message, say):
    global responded_threads

    # Check if the message is part of a thread
    if check_thread(message) == False:
        return
    
    # 응답을 보냅니다.
    send_response(say, message, qna_dict[key].format(user_id=message["user"]))

def run_bot():
    bot_handler = SocketModeHandler(app, slack_app_token)
    bot_handler.start()

run_bot()
