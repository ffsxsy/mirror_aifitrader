from playwright.sync_api import sync_playwright
import os
from datetime import datetime
import re, pathlib
import time, json


class CustomError(Exception):
    """自定义异常类，用于处理未定义的错误状态"""

    pass


class Browser_operation:
    def __init__(
        self,
        url="https://web.ninjatrader.com/",
        headless=False,
        ui_language: str = "English",
    ):
        self.url = url
        self.headless = headless
        self.ui_language = ui_language
        self._elements = None  # 界面元素文本字典
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    @property
    def elements(self):
        """读取 JSON 文件并缓存网页元素文本,json文件固定放在当前目录ui_text_config.json"""

        if self._elements is None:  # 如果未缓存，则读取文件
            script_path = os.path.abspath(__file__)
            script_dir = os.path.dirname(script_path)
            target_json_path = os.path.join(script_dir, "ui_text_config.json")
            with open(target_json_path, "r", encoding="utf-8") as f:
                self._elements = json.load(f)
        return self._elements

    # 根据界面语言获取文本
    def get_text(self, key):
        return self.elements.get(self.ui_language, {}).get(
            key, f"Missing text for key: {key}"
        )

    def initialize_browser_page(
        self,
        session_storage_path: str = None,
        persistent_context_dir: str | pathlib.Path = None,
    ):
        """初始化浏览器实例"""
        try:
            user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

            # 设置浏览器启动参数
            args = [
                "--start-maximized",
            ]
            # 启动 Playwright 和浏览器,上下文
            self.playwright = sync_playwright().start()
            # 使用持久化上下文
            if persistent_context_dir:
                self.context = self.playwright.chromium.launch_persistent_context(
                    headless=self.headless,
                    args=args,
                    # user_agent=user_agent,
                    user_data_dir=persistent_context_dir,
                    no_viewport=True,
                    locale=self.get_text("locale"),
                )
                # 打开一个新页面
                self.page = self.context.new_page()
            else:
                # 使用session_storage
                self.browser = self.playwright.chromium.launch(
                    headless=self.headless,
                    args=args,
                )
                self.context = self.browser.new_context(
                    no_viewport=True,
                    storage_state=session_storage_path
                )
                self.page = self.context.new_page()

            print("浏览器page初始化成功")
            self.page.goto(self.url)
        except Exception as e:
            print(f"浏览器page初始化失败: {e}")
            self.close_browser()  # 确保资源被清理

    def select_language_and_login(
        self, username: str, password: str, accept_cookie: bool = False
    ):
        self.page.select_option("#language-select", label=self.ui_language)
        self.page.get_by_label(self.get_text("username_label")).fill(username)
        self.page.get_by_label(self.get_text("password_label")).fill(password)
        if accept_cookie:
            self.page.locator(
                f"button:has-text('{self.get_text('accept_cookies')}')"
            ).click()
        self.page.get_by_role("button", name=self.get_text("login_button")).click()

    def select_trading_mode(self, Live: bool = False):
        """
        click to select trading mode.
        param:
            trading_mode_unique_str:unique_str, which can distinguish the two buttons
                "Simulation" or "Simu" for "Access Simulation"
                "Live", for "Login to the Live Environment"
        return:
            None
        """
        self.page.wait_for_load_state()  # 等待页面完全加载（包括所有资源，如图片、脚本、样式表等）
        if Live:
            target_text = self.get_text("live_button")
        else:
            target_text = self.get_text("simulation_button")
        self.page.locator(f"button:has-text('{target_text}')").click()

    def login_and_select_trading_mode(
        self, username: str, password: str, Live: bool = False
    ):
        """判断是否登录成功"""
        self.page.wait_for_load_state()  # 等待页面完全加载（包括所有资源，如图片、脚本、样式表等）

        # 使用 locator.or_ 同时查找两个元素:
        # 1. 加载模板按钮
        # 2. 登录按钮
        element = self.page.locator("div.btn-wrap.add-module").or_(
            self.page.get_by_role("button", name=self.get_text("login_button"))
        )
        print(f"{element.inner_html()=}")
        if element.is_visible():
            if element == self.page.locator("div.btn-wrap.add-module"):
                print("找到加载模板按钮")
            else:
                print("找到登录按钮")
                self.select_language_and_login(username, password)
                self.select_trading_mode(Live)
        else:
            raise CustomError("未找到登录按钮和加载模板按钮")

    def load_template(self, template_file_name: str):
        script_path = os.path.abspath(__file__)
        script_dir = os.path.dirname(script_path)
        template_file_path = os.path.join(script_dir, template_file_name)
        self.page.locator("div.btn-wrap.add-module").click(timeout=10000)
        file_input = self.page.locator("input[type='file']")
        file_input.set_input_files(template_file_path)
        print(f"已导入配置模板: {template_file_path}")

    def take_screenshot(
        self, screenshot_path: pathlib.Path | str, selected_element: str = None
    ):
        """
        截图，如果selected_element不为空，则只截取该元素，否则截取整个页面;
        例如，selected_element=".chart-inner-wrapper",则只截取这个元素
        """
        if selected_element:
            self.page.locator(selected_element).screenshot(path=screenshot_path)
        else:
            self.page.screenshot(path=screenshot_path, full_page=True)

    def get_active_tab(self) -> tuple[str, str]:
        """
        获取当前激活的标签,返回tuple(激活的标签名,刷新时间)
        """
        lm_tabs = self.page.locator(".lm_header .lm_tabs")
        avtive_tab = lm_tabs.locator(".lm_active")
        lm_tabs_text = avtive_tab.inner_text()

        # span_locator = avtive_tab.locator("span.lm_title > span")
        # lm_tabs_text = span_locator.inner_text()
        print(f"{lm_tabs_text=}", flush=True)
        result = lm_tabs_text.rsplit(" ", 1)
        print(f"{result=}", flush=True)
        return result

    def click_tab(self, tab_name):
        active_trade_name, _ = self.get_active_tab()
        if active_trade_name == tab_name:
            pass
        else:
            lm_tabs = self.page.locator(".lm_header .lm_tabs")
            lm_tabs.locator(f":has-text('{tab_name}')").nth(0).click(timeout=1000)

    def get_market_data(self):
        """
        获取市场数据,即在active_tab的scroll_view中获取数据，包括合约代码、合约名称、最新价、价格变动、买一价、买一量、卖一价、卖一量、持仓量、持仓成本价，存储在字典返回
        """
        data_dict = {}
        # LAST_locator = self.page.get_by_text("LAST")
        # # 获取祖父节点
        # target_scroll_view = LAST_locator.locator("xpath=../..")
        target_scroll_view = self.page.locator(".lm_items .gm-scroll-view")

        first_div = target_scroll_view.locator("> div").nth(0)  # 使用 nth(0)
        future_code, future_serries_name = first_div.inner_text().split("\n")
        print(f"{future_code=}, {future_serries_name=}", flush=True)
        data_dict["future_code"] = future_code
        data_dict["future_serries_name"] = future_serries_name

        first_div = target_scroll_view.locator("> div").nth(1)
        LAST_label, last_price, price_change = first_div.inner_text().split("\n")
        print(f"{LAST_label=}, {last_price=}, {price_change=}", flush=True)
        data_dict["LAST_label"] = LAST_label
        data_dict["last_price"] = float(last_price)
        data_dict["price_change"] = price_change

        first_div = target_scroll_view.locator("> div").nth(2)
        BID_label, bid_price, bid_volume = first_div.inner_text().split("\n")
        print(f"{BID_label=}, {bid_price=}, {bid_volume=}", flush=True)
        data_dict["BID_label"] = BID_label
        data_dict["bid_price"] = float(bid_price)
        data_dict["bid_volume"] = int(bid_volume)

        first_div = target_scroll_view.locator("> div").nth(3)
        ASK_label, ask_price, ask_volume = first_div.inner_text().split("\n")
        print(f"{ASK_label=}, {ask_price=}, {ask_volume=}", flush=True)
        data_dict["ASK_label"] = ASK_label
        data_dict["ask_price"] = float(ask_price)
        data_dict["ask_volume"] = int(ask_volume)

        first_div = target_scroll_view.locator("> div").nth(4)
        POSITION_label, position_str, profit_str = first_div.inner_text().split("\n")
        if position_str == "0":
            contract_volume = 0
            cost_price = 0
        else:
            contract_volume, cost_price = position_str.split("@")

        print(f"{POSITION_label=}, {contract_volume=}, {cost_price=}", flush=True)
        data_dict["POSITION_label"] = POSITION_label
        data_dict["contract_volume"] = int(contract_volume)
        data_dict["cost_price"] = float(cost_price)

        return data_dict

    def trade_action(self, action_type):
        """
        执行交易操作（市价买入、市价卖出、竞买价买入、卖出出价等）
        :param action_type: 操作类型，如 "Buy Mkt", "Sell Mkt", "Buy Bid", "Sell Ask"
        """
        self.page.get_by_text(action_type).click()
        self.page.wait_for_timeout(2000)  #

    def get_notification_text(self):
        notification_locator = self.page.locator(".notification-ticker")
        notification_text = notification_locator.inner_text()
        print(f"{notification_text=}", flush=True)
        return notification_text

    def check_trade_status(self, get_notification_func):
        pattern = r"\b(2[0-3]|[01]?[0-9]):([0-5][0-9]):([0-5][0-9])\b"
        Filled_text = self.get_text("trade_status")["filled"]
        Rejected_text = self.get_text("trade_status")["rejected"]

        while True:
            msg = get_notification_func()
            if re.search(pattern, msg):
                time.sleep(1)
                continue
            else:
                print(msg)
                if Rejected_text in msg:
                    return "fail"
                elif Filled_text in msg:

                    return "success"
                else:
                    # 未定义的返回值，抛出自定义异常
                    raise CustomError(f"未定义的交易状态: {msg}")

    def close_browser(self):
        """关闭浏览器"""
        if self.context:
            self.context.close()


if __name__ == "__main__":
    username = os.getenv("TRADER_USERNAME")
    password = os.getenv("TRADER_PASSWORD")
    # print(f"{username=}, {password=}")
    robot = Browser_operation(url="https://web.ninjatrader.com/")
    robot.initialize_browser_page(persistent_context_dir=".")
    robot.login_and_select_trading_mode(
        username=username, password=password, Live=False
    )

    # load template
    robot.load_template(template_file_name="test_mode.json")
    time.sleep(5)
    robot.take_screenshot(
        screenshot_path=os.path.join(".", "screenshot.png"),
        selected_element=".chart-inner-wrapper",
    )
    print(f"截图成功,保存于{os.path.join('.', 'screenshot.png')}")

    robot.trade_action("Buy Mkt")
    time.sleep(1)
    robot.trade_action("Sell Mkt")

    input("Press Enter to close the browser...")
    robot.close_browser()
