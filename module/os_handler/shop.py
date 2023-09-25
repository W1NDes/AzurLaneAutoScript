from module.base.button import ButtonGrid
from module.base.decorator import cached_property
from module.combat.assets import GET_ITEMS_1, GET_ITEMS_2, GET_ITEMS_3
from module.exception import ScriptError
from module.logger import logger
from module.map_detection.utils import Points
from module.ocr.ocr import DigitYuv
from module.os_handler.assets import *
from module.os_handler.map_event import MapEventHandler
from module.os_handler.os_status import OSStatus
from module.os_handler.ui import OSShopUI
from module.os_handler.selector import Selector
from module.base.decorator import Config
from module.statistics.item import ItemGrid
from module.ui.scroll import Scroll
from module.shop.assets import AMOUNT_MAX, AMOUNT_MINUS, AMOUNT_PLUS, SHOP_BUY_CONFIRM_AMOUNT, SHOP_BUY_CONFIRM as OS_SHOP_BUY_CONFIRM
from module.shop.clerk import OCR_SHOP_AMOUNT

OS_SHOP_SCROLL = Scroll(OS_SHOP_SCROLL_AREA, color=(156, 182, 239))
OS_SHOP_SCROLL.edge_threshold = 0.15
OS_SHOP_SCROLL.drag_threshold = 0.15
TEMPLATE_YELLOW_COINS = Template('./assets/shop/os_cost/YellowCoins_1.png')
TEMPLATE_PURPLE_COINS = Template('./assets/shop/os_cost/PurpleCoins_1.png')
TEMPLATE_YELLOW_COINS_SOLD_OUT = Template('./assets/shop/os_cost_sold_out/YellowCoins.png')
TEMPLATE_PURPLE_COINS_SOLD_OUT = Template('./assets/shop/os_cost_sold_out/PurpleCoins.png')


class OSShopPrice(DigitYuv):
    def after_process(self, result):
        result = result.replace('I', '1').replace('D', '0').replace('S', '5')
        result = result.replace('B', '8')

        prev = result
        if result.startswith('0'):
            result = '1' + result
            logger.warning(f'OS shop amount {prev} is revised to {result}')

        result = super().after_process(result)
        return result


class OSShopHandler(OSStatus, OSShopUI, Selector, MapEventHandler):
    _shop_yellow_coins = 0
    _shop_purple_coins = 0

    def os_shop_get_coins(self):
        self._shop_yellow_coins = self.get_yellow_coins()
        self._shop_purple_coins = self.get_purple_coins()
        logger.info(f'Yellow coins: {self._shop_yellow_coins}, purple coins: {self._shop_purple_coins}')

    @cached_property
    @Config.when(SERVER='tw')
    def os_shop_items(self) -> ItemGrid:
        """
        Returns:
            ItemGrid:
        """
        shop_grid = ButtonGrid(
            origin=(238, 220), delta=(188, 225), button_shape=(98, 98), grid_shape=(4, 2), name='SHOP_GRID')
        shop_items = ItemGrid(
            shop_grid, templates={}, amount_area=(60, 74, 96, 95), price_area=(52, 132, 132, 165))
        shop_items.price_ocr = OSShopPrice([], letter=(255, 223, 57), threshold=32, name='Price_ocr')
        shop_items.load_template_folder('./assets/shop/os')
        shop_items.load_cost_template_folder('./assets/shop/os_cost')
        return shop_items

    @cached_property
    @Config.when(SERVER='en')
    def os_shop_items(self) -> ItemGrid:
        """
        Returns:
            ItemGrid:
        """
        shop_grid = ButtonGrid(
            origin=(231, 222), delta=(190, 224), button_shape=(98, 98), grid_shape=(4, 2), name='SHOP_GRID')
        shop_items = ItemGrid(
            shop_grid, templates={}, amount_area=(60, 74, 96, 95), price_area=(52, 132, 132, 165))
        shop_items.price_ocr = OSShopPrice([], letter=(255, 223, 57), threshold=32, name='Price_ocr')
        shop_items.load_template_folder('./assets/shop/os')
        shop_items.load_cost_template_folder('./assets/shop/os_cost')
        return shop_items

    @cached_property
    @Config.when(SERVER=None)
    def os_shop_items(self) -> ItemGrid:
        """
        Returns:
            ItemGrid:
        """
        shop_grid = ButtonGrid(
            origin=(233, 224), delta=(193.2, 228), button_shape=(98, 98), grid_shape=(4, 2), name='SHOP_GRID')
        shop_items = ItemGrid(
            shop_grid, templates={}, amount_area=(60, 74, 96, 95), price_area=(52, 132, 132, 165))
        shop_items.price_ocr = OSShopPrice([], letter=(255, 223, 57), threshold=32, name='Price_ocr')
        shop_items.load_template_folder('./assets/shop/os')
        shop_items.load_cost_template_folder('./assets/shop/os_cost')
        return shop_items

    def os_shop_get_items_in_akashi(self, name=True) -> list:
        """
        Args:
            name (bool): If detect item name. True if detect akashi shop, false if detect port shop.

        Returns:
            list[Item]:
        """
        if self.config.SHOP_EXTRACT_TEMPLATE:
            self.os_shop_items.extract_template(self.device.image, './assets/shop/os')
        self.os_shop_items.predict(self.device.image, name=name, amount=name, cost=True, price=True)

        items = self.os_shop_items.items
        if len(items):
            min_row = self.os_shop_items.grids[0, 0].area[1]
            row = [str(item) for item in items if item.button[1] == min_row]
            logger.info(f'Shop row 1: {row}')
            row = [str(item) for item in items if item.button[1] != min_row]
            logger.info(f'Shop row 2: {row}')
            return items
        else:
            logger.info('No shop items found')
            return []

    def _get_os_shop_cost(self) -> list:
        """
        Returns the coordinates of the upper left corner of each coin icon.

        Returns:
            list:
        """
        result = TEMPLATE_YELLOW_COINS.match_multi(self.image_crop((360, 320, 410, 720)))
        result += TEMPLATE_PURPLE_COINS.match_multi(self.image_crop((360, 320, 410, 720)))
        result += TEMPLATE_YELLOW_COINS_SOLD_OUT.match_multi(self.image_crop((360, 320, 410, 720)))
        result += TEMPLATE_PURPLE_COINS_SOLD_OUT.match_multi(self.image_crop((360, 320, 410, 720)))
        logger.info(f'Costs: {result}')

        return Points([(0., m.area[1]) for m in result]).group(threshold=5)

    def _get_shop_grid(self, cost) -> ButtonGrid:
        """
        Returns shop grid.

        Args:
            cost: The coordinates of the upper left corner of coin icon.

        Returns:
            ButtonGris:
        """
        y = 320 + cost[1] - 130

        return ButtonGrid(
            origin=(356, y), delta=(160, 0), button_shape=(98, 98), grid_shape=(5, 1), name='OS_SHOP_GRID')

    def _get_os_shop_items(self, cost) -> ItemGrid:
        """
        Returns shop items.

        Args:
            cost: The coordinates of the upper left corner of coin icon.

        Returns:
            ItemGrid:
        """
        os_shop_items = ItemGrid(
            self._get_shop_grid(cost), templates={}, amount_area=(77, 77, 96, 96), price_area=(52, 132, 130, 165))
        os_shop_items.price_ocr = OSShopPrice([], letter=(255, 223, 57), threshold=32, name='Price_ocr')
        os_shop_items.load_template_folder('./assets/shop/os')
        os_shop_items.load_cost_template_folder('./assets/shop/os_cost')

        return os_shop_items

    @Config.when(SERVER='tw')
    def os_shop_get_items(self, name=True) -> list:
        """
        Args:
            name (bool): If detect item name. True if detect akashi shop, false if detect port shop.

        Returns:
            list[Item]:
        """
        if self.config.SHOP_EXTRACT_TEMPLATE:
            self.os_shop_items.extract_template(self.device.image, './assets/shop/os')
        self.os_shop_items.predict(self.device.image, name=name, amount=name, cost=True, price=True)

        items = self.os_shop_items.items
        if len(items):
            min_row = self.os_shop_items.grids[0, 0].area[1]
            row = [str(item) for item in items if item.button[1] == min_row]
            logger.info(f'Shop row 1: {row}')
            row = [str(item) for item in items if item.button[1] != min_row]
            logger.info(f'Shop row 2: {row}')
            return items
        else:
            logger.info('No shop items found')
            return []

    @Config.when(SERVER=None)
    def os_shop_get_items(self, name=True) -> list:
        """
        Args:
            name (bool): If detect item name. True if detect akashi shop, false if detect port shop.

        Returns:
            list[Item]:
        """
        costs = self._get_os_shop_cost()
        items = []
        for cost in costs:
            shop_items = self._get_os_shop_items(cost)
            if self.config.SHOP_EXTRACT_TEMPLATE:
                shop_items.extract_template(self.device.image, './assets/shop/os')
            shop_items.predict(self.device.image, name=name, amount=name, cost=True, price=True)
            shop_items = shop_items.items

            if len(shop_items):
                row = [str(item) for item in shop_items]
                logger.info(f'Shop items found: {row}')
                items += shop_items
            else:
                logger.info('No shop items found')

        return items

    def os_shop_get_item_to_buy_in_akashi(self) -> list:
        """
        Returns:
            list[Item]:
        """
        self.os_shop_get_coins()
        items = self.os_shop_get_items_in_akashi(name=True)
        # Shop supplies do not appear immediately, need to confirm if shop is empty.
        for _ in range(2):
            if not len(items):
                logger.info('Empty akashi shop, confirming')
                self.device.sleep(0.5)
                self.device.screenshot()
                items = self.os_shop_get_items_in_akashi(name=True)
                continue
            else:
                break

        return self.items_filter_in_os_shop(items)

    def os_shop_get_item_to_buy_in_port(self) -> list:
        """
        Returns:
            list[Item]:
        """
        self.os_shop_get_coins()
        items = self.os_shop_get_items(name=True)
        logger.attr('CL1 enabled', self.is_cl1_enabled)

        for _ in range(2):
            if not len(items):
                logger.info('Empty OS shop, confirming')
                self.device.sleep(0.5)
                self.device.screenshot()
                items = self.os_shop_get_items(name=True)
                continue
            else:
                self.os_shop_items.items = self.items_filter_in_os_shop(items)
                return self.os_shop_items.items

        return []

    def os_shop_buy_execute(self, button, skip_first_screenshot=True) -> bool:
        """
        Args:
            button: Item to buy
            skip_first_screenshot:

        Pages:
            in: PORT_SUPPLY_CHECK
        """
        success = False
        enough_coins = True
        self.interval_clear(PORT_SUPPLY_CHECK)
        self.interval_clear(SHOP_BUY_CONFIRM)
        self.interval_clear(SHOP_BUY_CONFIRM_AMOUNT)
        self.interval_clear(OS_SHOP_BUY_CONFIRM)

        while True:
            if skip_first_screenshot:
                skip_first_screenshot = False
            else:
                self.device.screenshot()

            if self.handle_map_get_items(interval=1):
                self.interval_reset(PORT_SUPPLY_CHECK)
                success = True
                continue

            if self.appear(OS_SHOP_BUY_CONFIRM, offset=(20, 20), interval=3) or \
                    self.appear(SHOP_BUY_CONFIRM, offset=(20, 20), interval=3) or \
                    self.appear(SHOP_BUY_CONFIRM_AMOUNT, offset=(20, 20), interval=3):
                if not enough_coins:
                    self.device.click(CLICK_SAFE_AREA)
                    continue

                enough_coins = self.shop_buy_exec(button)
                self.interval_reset(PORT_SUPPLY_CHECK)
                continue

            if enough_coins and not success and self.appear(PORT_SUPPLY_CHECK, offset=(20, 20), interval=5):
                self.device.click(button)
                continue

            # End
            if not enough_coins or (success and self.appear(PORT_SUPPLY_CHECK, offset=(20, 20))):
                break

        return success

    def os_shop_buy(self, select_func) -> int:
        """
        Args:
            select_func:

        Returns:
            int: Items bought.

        Pages:
            in: PORT_SUPPLY_CHECK
        """
        count = 0
        for _ in range(2):
            buttons = select_func()

            if buttons is None or len(buttons) == 0:
                logger.info('No items need to be purchased')
                continue
            for button in buttons:
                if count >= 10:
                    logger.info('Shop buy finished')
                    return count
                else:
                    if not self.os_shop_buy_execute(button):
                        logger.warning('Failed to buy item')
                        return count
                    self.os_shop_get_coins()
                    count += 1
                    continue

        logger.warning('Too many items to buy, stopped')
        return count

    def shop_buy_exec(self, item, skip_first_screenshot=True) -> bool:
        """
        Execute shop buy amount and buy item.

        Args:
            item: Item to buy.

        Raises:
            ScriptError:

        Returns:
            bool: True if buy success, False if not enough coins.
        """
        currency = self._shop_yellow_coins - (self.config.OS_CL1_YELLOW_COINS_PRESERVE if self.is_cl1_enabled else 0) \
            if item.cost == 'YellowCoins' else self._shop_purple_coins
        if (currency < item.price):
            return False

        self.interval_clear(SHOP_BUY_CONFIRM)
        self.interval_clear(OS_SHOP_BUY_CONFIRM)
        self.interval_clear(SHOP_BUY_CONFIRM_AMOUNT)
        amount_fin = False
        success = False

        while True:
            if skip_first_screenshot:
                skip_first_screenshot = False
            else:
                self.device.screenshot()

            if self.appear(GET_ITEMS_1, interval=1) or \
                    self.appear(GET_ITEMS_2, interval=1) or \
                    self.appear(GET_ITEMS_3, interval=1):
                success = True
                break

            if not amount_fin:
                amount_fin = self.amount_handler(currency, item.price)
                continue

            if amount_fin and self.appear_then_click(SHOP_BUY_CONFIRM, offset=(20, 20), interval=1):
                self.interval_reset(SHOP_BUY_CONFIRM)
                continue

            if amount_fin and self.appear_then_click(OS_SHOP_BUY_CONFIRM, offset=(20, 20), interval=1):
                self.interval_reset(OS_SHOP_BUY_CONFIRM)
                continue

            if amount_fin and self.appear_then_click(SHOP_BUY_CONFIRM_AMOUNT, offset=(20, 20), interval=1):
                self.interval_reset(SHOP_BUY_CONFIRM_AMOUNT)
                continue

        return success

    def amount_handler(self, currency, price, skip_first_screenshot=True) -> bool:
        """
        Handler item amount to buy.

        Args:
            currency (int): Coins currently had.
            price (int): Item price.
            skip_first_screenshot (bool, optional): Defaults to True.

        Raises:
            ScriptError: OCR_SHOP_AMOUNT

        Returns:
            bool: True if amount handler finished.
        """
        if self.appear(AMOUNT_MAX, offset=(50, 50)):
            limit = None
            for _ in range(3):
                self.appear_then_click(AMOUNT_MAX, offset=(50, 50))
                self.device.sleep((0.3, 0.5))
                self.device.screenshot()
                limit = OCR_SHOP_AMOUNT.ocr(self.device.image)
                if limit and limit > 1:
                    break
            if not limit:
                logger.critical('OCR_SHOP_AMOUNT resulted in zero (0); '
                                'asset may be compromised')
                raise ScriptError
            if limit == 1:
                return True
            
            total = int(currency // price)
            diff = limit - total
            if diff > 0:
                limit = total
            self.ui_ensure_index(limit, letter=OCR_SHOP_AMOUNT, prev_button=AMOUNT_MINUS, next_button=AMOUNT_PLUS,
                skip_first_screenshot=skip_first_screenshot)
            
        return True

    @Config.when(SERVER='tw')
    def handle_port_supply_buy(self) -> bool:
        """
        Returns:
            bool: True if success to buy any or no items found.
                False if not enough coins to buy any.

        Pages:
            in: PORT_SUPPLY_CHECK
        """
        count = self.os_shop_buy(select_func=self.os_shop_get_item_to_buy_in_port)
        return count > 0 or len(self.os_shop_items.items) == 0

    @Config.when(SERVER=None)
    def handle_port_supply_buy(self) -> bool:
        """
        Returns:
            bool: True if success to buy any or no items found.
                False if not enough coins to buy any.

        Pages:
            in: PORT_SUPPLY_CHECK
        """
        _count = 0
        for i in range(4):
            count = 0
            self.os_shop_side_navbar_ensure(bottom=i + 1)
            OS_SHOP_SCROLL.set_bottom(main=self)

            while True:
                count += self.os_shop_buy(select_func=self.os_shop_get_item_to_buy_in_port)
                if count >= 10:
                    break
                elif OS_SHOP_SCROLL.at_top(main=self):
                    logger.info('OS shop reach bottom, stop')
                    break
                else:
                    OS_SHOP_SCROLL.prev_page(main=self, page=0.66)
                    continue
            _count += count

        return _count > 0 or len(self.os_shop_items.items) == 0

    def handle_akashi_supply_buy(self, grid):
        """
        Args:
            grid: Grid where akashi stands.

        Pages:
            in: is_in_map
            out: is_in_map
        """
        self.ui_click(grid, appear_button=self.is_in_map, check_button=PORT_SUPPLY_CHECK,
                      additional=self.handle_story_skip, skip_first_screenshot=True)
        self.os_shop_buy(select_func=self.os_shop_get_item_to_buy_in_akashi)
        self.ui_back(appear_button=PORT_SUPPLY_CHECK, check_button=self.is_in_map, skip_first_screenshot=True)
