import io
import os
import sys, time

import os

os.system("playwright install --with-deps chromium")

# 将项目根目录添加到 sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.append(project_root)

import streamlit as st
# from playwright.sync_api import sync_playwright
from multiprocessing import Process, Queue
import os
from module_broswer_sync import Browser_operation

# Initialize session_state
if "browser_process" not in st.session_state:
    st.session_state.browser_process = None
if "command_queue" not in st.session_state:
    st.session_state.command_queue = Queue()
if "response_queue" not in st.session_state:
    st.session_state.response_queue = Queue()

script_path = os.path.abspath(__file__)
script_dir = os.path.dirname(script_path)
state_json = os.path.join(script_dir, "state.json")
persistent_context_dir = os.path.join(script_dir, "persistent_context_dir")


def playwright_process(command_queue, response_queue):
    # username = os.getenv('TRADER_USERNAME')
    # password = os.getenv('TRADER_PASSWORD')
    username = st.secrets["TRADER_USERNAME"]
    password = st.secrets['TRADER_PASSWORD']
    robot = Browser_operation(url="https://web.ninjatrader.com/", headless=False)
    # 使用state_json
    # robot.initialize_browser_page(session_storage_path=state_json)
    #使用persistent_context_dir
    robot.initialize_browser_page(persistent_context_dir=persistent_context_dir)
    robot.page.set_default_timeout(10000)

    while True:
        command = command_queue.get()
        if command == "open":
            robot.select_language_and_login(username=username, password=password, accept_cookie=False)
            time.sleep(10)
            # Save storage state into the file.
            storage = robot.context.storage_state(path=state_json)
            robot.page.wait_for_load_state()  # 等待页面完全加载（包括所有资源，如图片、脚本、样式表等）
            robot.page.screenshot(path="screenshot.png", full_page=True)
            robot.select_trading_mode(Live=False)
            # load template,假设模板文件都在当前目录下
            robot.page.wait_for_load_state()  # 等待页面完全加载（包括所有资源，如图片、脚本、样式表等）
            robot.load_template(template_file_name=os.path.join(script_dir, "test_mode.json"))
            time.sleep(5)
            response_queue.put("Webpage opened and logged in")
        elif command == "get_data":
            market_data = robot.get_market_data()
            response_queue.put(market_data)
        elif command == "screenshot":
            robot.take_screenshot(screenshot_path=os.path.join(".", "screenshot.png"),
                                  selected_element=".chart-inner-wrapper")
            screenshot_bytes = robot.page.locator(".chart-inner-wrapper").screenshot()
            # image_stream = io.BytesIO(screenshot_bytes)
            response_queue.put(screenshot_bytes)
        elif command == "close":
            robot.close_browser()
            response_queue.put("Browser closed")
            break


def open_browser():
    if st.session_state.browser_process is None:
        st.session_state.browser_process = Process(target=playwright_process, args=(
        st.session_state.command_queue, st.session_state.response_queue))
        st.session_state.browser_process.start()
        st.session_state.command_queue.put("open")
        response = st.session_state.response_queue.get()
        st.success(response)
    else:
        st.error("Browser already opened")


def get_data():
    if st.session_state.browser_process is not None:
        st.session_state.command_queue.put("get_data")
        response = st.session_state.response_queue.get()
        st.write(response)
    else:
        st.error("Please open the browser first")


def take_screenshot():
    if st.session_state.browser_process is not None:
        st.session_state.command_queue.put("screenshot")
        screenshot_bytes = st.session_state.response_queue.get()
        image_stream = io.BytesIO(screenshot_bytes)
        st.image(image_stream, caption="Screenshot")
    else:
        st.error("Please open the browser first")


def close_browser():
    if st.session_state.browser_process is not None:
        st.session_state.command_queue.put("close")
        response = st.session_state.response_queue.get()
        st.session_state.browser_process.join()
        st.session_state.browser_process = None
        st.success(response)
    else:
        st.error("Browser not opened")


# 页面布局
st.sidebar.title("按钮区")
# 右边的主要显示区
st.markdown("# Output")
# 在左边放置几个按钮
if st.sidebar.button("Setup(open/login)"):
    open_browser()
st.sidebar.markdown("---")
if st.sidebar.button("Action1:获取市场数据"):
    get_data()

if st.sidebar.button("Action2:截图"):
    take_screenshot()

if st.sidebar.button("Action3:截图发给AI分析"):
    st.write("还没有做好")

if st.sidebar.button("Action4:买卖操作"):
    st.write("还没有做好")
st.sidebar.markdown("---")
if st.sidebar.button("TearDown(close)"):
    close_browser()
