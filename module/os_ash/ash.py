from datetime import datetime, timedelta

import module.config.server as server

from module.base.utils import image_left_strip
from module.combat.combat import BATTLE_PREPARATION, Combat
from module.config.utils import DEFAULT_TIME
from module.logger import logger
from module.ocr.ocr import DigitCounter
from module.os_ash.assets import *
from module.os_handler.map_event import MapEventHandler
from module.ui.assets import BACK_ARROW
from module.ui.ui import UI


class DailyDigitCounter(DigitCounter):
    def pre_process(self, image):
        image = super().pre_process(image)
        image = image_left_strip(image, threshold=120, length=35)
        return image


class AshBeaconFinished(Exception):
    pass


class AshCombat(Combat):
    def handle_battle_status(self, drop=None):
        """
        Args:
            drop (DropImage):

        Returns:
            bool:
        """
        if self.is_combat_executing():
            return False
        if self.appear(BATTLE_STATUS, offset=(120, 20), interval=self.battle_status_click_interval):
            if drop:
                drop.handle_add(self)
            else:
                self.device.sleep((0.25, 0.5))
            self.device.click(BATTLE_STATUS)
            return True
        if self.appear(BATTLE_PREPARATION, offset=(30, 30), interval=2):
            self.device.click(BACK_ARROW)
            return True
        if super().handle_battle_status(drop=drop):
            return True

        return False

    def handle_battle_preparation(self):
        
        if super().handle_battle_preparation():
            return True

        if self.appear_then_click(ASH_START, offset=(30, 30), interval=2):
            return True

        if self.handle_get_items():
            return True
        if self.appear(BEACON_REWARD):
            logger.info("Ash beacon already finished.")
            raise AshBeaconFinished
        if self.appear(BEACON_EMPTY, offset=(20, 20)):
            logger.info("Ash beacon already empty.")
            raise AshBeaconFinished
        if self.appear(ASH_SHOWDOWN, offset=(20, 20)):
            logger.info("Ash beacon already at ASH_SHOWDOWN.")
            raise AshBeaconFinished

        return False
    def combat_preparation(self, balance_hp=False, emotion_reduce=False, auto='combat_auto', fleet_index=1):
        META_NEED_PRE = False
        COMBAT_ALL_PRE = False
        ADD_BOAT_COUNT = 0
        ADD_BOAT_IN_META = Button(area=(137, 139, 187, 213), color=(), button=(137, 139, 187, 213))
        self.device.stuck_record_clear()
        self.device.click_record_clear()
        skip_first_screenshot = True
        while 1:
            if skip_first_screenshot:
                skip_first_screenshot = False
            else:
                self.device.screenshot()
            if META_NEED_PRE is True:
                if self.appear_then_click(META_PRE_1, offset=(30, 30), interval=2):
                    continue
                if self.appear_then_click(META_PRE_2, offset=(30, 30), interval=2):
                    continue
                if self.appear_then_click(META_PRE_3, offset=(30, 30), interval=2):
                    continue
                if self.appear_then_click(META_PRE_4, offset=(30, 30), interval=2):
                    continue
                if self.appear_then_click(META_PRE_5, offset=(30, 30), interval=2):
                    continue
                if self.appear_then_click(META_PRE_6, offset=(30, 30), interval=2):
                    logger.info("Ash beacon all pred.")
                    COMBAT_ALL_PRE = True
                    self.device.sleep(2)
                    continue
                if self.appear_then_click_nocheck(ADD_BOAT_ENSURE, offset=(30, 30), interval=2):
                    continue
                if self.appear(ADD_BOAT_STATUS, interval=2):
                    self.device.click(ADD_BOAT_IN_META)
                    ADD_BOAT_COUNT += 1
                    continue

                if  COMBAT_ALL_PRE is True and ADD_BOAT_COUNT >=6:
                    if self.appear_then_click(META_PRE_SAVE, offset=(30, 30), interval=2):
                        META_NEED_PRE = False
                        break
            else:
                if self.appear(META_PRE_SAVE, offset=(30, 30), interval=0, similarity=0.85,threshold=30):
                    META_NEED_PRE = True
                    logger.info("Ash beacon no pre.")
                    continue
                if self.appear_then_click(ASH_START, offset=(30, 30), interval=2):
                    continue
                if self.appear(META_TEAM_READY):
                    logger.info("Ash beacon ready.")
                    break
        super().combat_preparation(balance_hp=balance_hp, emotion_reduce=emotion_reduce, auto=auto, fleet_index=fleet_index)
            
    def combat(self, *args, expected_end=None, **kwargs):
        try:
            super().combat(*args, expected_end=expected_end, **kwargs)
        except AshBeaconFinished:
            pass


class OSAsh(UI, MapEventHandler):

    _ash_fully_collected = False

    def ash_collect_status(self):
        """
        Returns:
            int: 0 to 100.
        """
        if self._ash_fully_collected:
            return 0
        if self.image_color_count(ASH_COLLECT_STATUS, color=(235, 235, 235), threshold=221, count=20):
            logger.info('Ash beacon status: light')
            if server.server != 'jp':
                ocr_collect = DigitCounter(
                    ASH_COLLECT_STATUS, letter=(235, 235, 235), threshold=160, name='OCR_ASH_COLLECT_STATUS')
                ocr_daily = DailyDigitCounter(
                    ASH_DAILY_STATUS, letter=(235, 235, 235), threshold=160, name='OCR_ASH_DAILY_STATUS')
            else:
                ocr_collect = DigitCounter(
                    ASH_COLLECT_STATUS, letter=(201, 201, 201), threshold=128, name='OCR_ASH_COLLECT_STATUS')
                ocr_daily = DailyDigitCounter(
                    ASH_DAILY_STATUS, letter=(193, 193, 193), threshold=160, name='OCR_ASH_DAILY_STATUS')
        elif self.image_color_count(ASH_COLLECT_STATUS, color=(140, 142, 140), threshold=221, count=20):
            logger.info('Ash beacon status: gray')
            ocr_collect = DigitCounter(
                ASH_COLLECT_STATUS, letter=(140, 142, 140), threshold=160, name='OCR_ASH_COLLECT_STATUS')
            ocr_daily = DailyDigitCounter(
                ASH_DAILY_STATUS, letter=(140, 142, 140), threshold=160, name='OCR_ASH_DAILY_STATUS')
        else:
            # If OS daily mission received or finished, the popup will cover beacon status.
            logger.info('Ash beacon status is covered, will check next time')
            return 0

        status, _, _ = ocr_collect.ocr(self.device.image)
        daily, _, _ = ocr_daily.ocr(self.device.image)

        if daily >= 200:
            logger.info('Ash beacon fully collected today')
            self._ash_fully_collected = True
        elif status >= 200:
            logger.info('Ash beacon data reached the holding limit')
            self._ash_fully_collected = True

        if status < 0:
            status = 0
        return status

    def _support_call_ash_beacon_task(self):
        # AshBeacon next run
        next_run = self.config.cross_get(keys="OpsiAshBeacon.Scheduler.NextRun", default=DEFAULT_TIME)
        # Between the next execution time and the present time is more than 30 minutes
        if next_run - datetime.now() > timedelta(minutes=30):
            return True
        return False

    def handle_ash_beacon_attack(self):
        """
        Returns:
            bool: If attacked.

        Pages:
            in: is_in_map
            out: is_in_map
        """
        if self.ash_collect_status() >= 100 \
                and self._support_call_ash_beacon_task():
            self.config.task_call(task='OpsiAshBeacon')
            return True

        return False
