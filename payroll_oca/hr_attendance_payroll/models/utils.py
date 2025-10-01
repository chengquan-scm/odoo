from datetime import datetime, timedelta, time
from enum import Enum
import pytz

# ⚡ 固定越南时区
VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")

# ⚡ 固定班次时间定义（带时区）
# ⚡ 固定班次时间定义（不带 tzinfo）
WHITE_START_T = time(7, 0)   # 白班开始 07:00
WHITE_END_T   = time(19, 0)  # 白班结束 19:00
NIGHT_START_T = time(19, 0)  # 夜班开始 19:00
NIGHT_END_T   = time(7, 0)   # 夜班结束次日 07:00


class ShiftType(Enum):
    """班次类型枚举"""
    WHITE = "white_shift"
    NIGHT = "night_shift"


class HrPayslipUtils:
    """
    工资单工具类，用于判定班次、修正打卡时间、校验考勤边界等。
    输入必须是 tz-aware 的越南本地时间。
    """
    def __init__(self, check_in_local: datetime, check_out_local: datetime):
        if check_in_local.tzinfo is None or check_out_local.tzinfo is None:
            raise ValueError("必须传入 tz-aware 的越南本地时间")
        self.check_in_local = check_in_local
        self.check_out_local = check_out_local
        print(f"[初始化] 打卡区间: {self.check_in_local} ~ {self.check_out_local}")
        self.shift_type = self.detect_shift_by_hours_distribution()

    @staticmethod
    def _make_local_dt(d, t):
        """把 date + time 组装成 tz-aware 越南本地时间"""
        return VN_TZ.localize(datetime.combine(d, t))

    def detect_shift_by_hours_distribution(self):
        """
        根据考勤时间在白班和夜班区间的分布情况来判定班次。
        """
        white_shift_hours = self._calculate_white_shift_hours()
        night_shift_hours = self._calculate_night_shift_hours()

        print(
            f"[班次判定] 统计区间 {self.check_in_local} ~ {self.check_out_local} | "
            f"白班累计: {white_shift_hours:.2f}h | 夜班累计: {night_shift_hours:.2f}h"
        )

        # 获取打卡开始日期（本地时间）
        shift_date = self.check_in_local.date()

        if white_shift_hours >= night_shift_hours:
            print(f"[班次判定] {shift_date} ✅ 判定为白班")
            return ShiftType.WHITE
        else:
            print(f"[班次判定] {shift_date} 🌙 判定为夜班")
            return ShiftType.NIGHT


    def _calculate_white_shift_hours(self):
        """
        计算当前考勤区间内，落入白班时间段的总时长（小时）。
        """
        total_hours = 0.0
        current_date = self.check_in_local.date()
        end_date = self.check_out_local.date()

        while current_date <= end_date:
            white_start = self._make_local_dt(current_date, WHITE_START_T)
            white_end = self._make_local_dt(current_date, WHITE_END_T)
            hours = self._calculate_hours_interval(
                self.check_in_local, self.check_out_local, white_start, white_end
            )
            print(f"[白班计算] {white_start} ~ {white_end} 覆盖时长: {hours:.2f}h")
            total_hours += hours
            current_date += timedelta(days=1)

        print(f"[白班计算] 总时长: {total_hours:.2f}h")
        return total_hours

    def _calculate_night_shift_hours(self):
        """
        计算当前考勤区间内，落入夜班时间段的总时长（小时）。
        """
        total_hours = 0.0
        current_date = self.check_in_local.date()
        end_date = self.check_out_local.date()

        while current_date <= end_date:
            night_start = self._make_local_dt(current_date, NIGHT_START_T)
            night_end = self._make_local_dt(current_date + timedelta(days=1), NIGHT_END_T)

            hours = self._calculate_hours_interval(
                self.check_in_local, self.check_out_local, night_start, night_end
            )
            print(f"[夜班计算] {night_start} ~ {night_end} 覆盖时长: {hours:.2f}h")
            total_hours += hours
            current_date += timedelta(days=1)

        print(f"[夜班计算] 总时长: {total_hours:.2f}h")
        return total_hours

    @staticmethod
    def _calculate_hours_interval(ci, co, interval_start, interval_end):
        """
        工具函数：计算 [ci, co] 与 [interval_start, interval_end] 的交集时长（小时）。
        """
        start = max(ci, interval_start)
        end = min(co, interval_end)
        if start >= end:
            return 0.0
        hours = (end - start).total_seconds() / 3600.0
        print(f"[DEBUG] ci={ci} ({ci.tzinfo}), interval_start={interval_start} ({interval_start.tzinfo})")
        return hours

    def validate_attendance_bounds(self):
        """
        校验考勤打卡时间是否在合理范围内：
        - 上班不能早于班次开始前 1 小时
        - 下班不能晚于班次结束后 1 小时
        """
        if self.shift_type == ShiftType.WHITE:
            official_start = self._make_local_dt(self.check_in_local.date(), WHITE_START_T)
            official_end = self._make_local_dt(self.check_out_local.date(), WHITE_END_T)
        elif self.shift_type == ShiftType.NIGHT:
            official_start = self._make_local_dt(self.check_in_local.date(), NIGHT_START_T)
            official_end = self._make_local_dt(self.check_in_local.date() + timedelta(days=1), NIGHT_END_T)
        else:
            raise ValueError(f"未知班次类型: {self.shift_type}")

        earliest_check_in = official_start - timedelta(hours=1)
        latest_check_out = official_end + timedelta(hours=1)

        print(f"[边界校验] 班次: {self.shift_type.value} | 合法范围: {earliest_check_in} ~ {latest_check_out}")

        if self.check_in_local < earliest_check_in:
            raise ValueError(f"[考勤异常] 上班打卡过早: {self.check_in_local}, 允许最早 {earliest_check_in}")
        if self.check_out_local > latest_check_out:
            raise ValueError(f"[考勤异常] 下班打卡过晚: {self.check_out_local}, 允许最晚 {latest_check_out}")

        print(f"[边界校验] ✅ 打卡时间合法")
        return True

    def normalize_attendance(self, step: int = 30):
        """
        规范化考勤时间：
        - 上班：小于等于班次开始 → 取班次开始；否则按 step 分钟向上取整。
        - 下班：大于等于班次结束 → 取班次结束；否则按 step 分钟向下取整。
        """
        if self.shift_type == ShiftType.WHITE:
            start = self._make_local_dt(self.check_in_local.date(), WHITE_START_T)
            end = self._make_local_dt(self.check_in_local.date(), WHITE_END_T)
        else:  # 夜班
            start = self._make_local_dt(self.check_in_local.date(), NIGHT_START_T)
            end = self._make_local_dt(self.check_in_local.date() + timedelta(days=1), NIGHT_END_T)

        # ---- 上班处理 ----
        ci = self.check_in_local
        if ci <= start:
            print(f"[上班修正] 打卡 {ci} 早于/等于班次开始 {start} → 修正为 {start}")
            ci = start
        else:
            new_ci = self._round_with_step(start, ci, step=step, direction="ceil")
            print(f"[上班修正] 打卡 {ci} 晚于班次开始 {start} → 向上取整为 {new_ci}")
            ci = new_ci

        # ---- 下班处理 ----
        co = self.check_out_local
        if co >= end:
            print(f"[下班修正] 打卡 {co} 晚于/等于班次结束 {end} → 修正为 {end}")
            co = end
        else:
            new_co = self._round_with_step(end, co, step=step, direction="floor")
            print(f"[下班修正] 打卡 {co} 早于班次结束 {end} → 向下取整为 {new_co}")
            co = new_co

        print(f"[规范化结果] 上班: {ci} | 下班: {co}")
        return ci, co


    @staticmethod
    def _round_with_step(base_time: datetime, actual: datetime, step: int = 30, direction: str = "ceil") -> datetime:
        """
        工具函数：根据 step 分钟对齐时间。
        - direction="ceil": 向上取整
        - direction="floor": 向下取整
        """
        delta = (actual - base_time).total_seconds() / 60
        if delta == 0:
            return base_time

        if direction == "ceil":
            steps = (delta + step - 1) // step
        else:
            steps = delta // step

        rounded_time = base_time + timedelta(minutes=int(steps * step))
        return rounded_time


    def calculate_white_shift_hours(self, step: int = 30):
        """
        计算白班工时拆分
        - 标准工时：07:00–16:00 （强制扣除午休 12:00–13:00）
        - 加班工时：16:00–19:00
        """
        # 先调用 normalize_attendance 去皮
        ci, co = self.normalize_attendance(step=step)

        # 白班时间段
        std_start = self._make_local_dt(ci.date(), WHITE_START_T)  # 07:00
        std_end = self._make_local_dt(ci.date(), time(16, 0))  # 16:00
        rest_start = self._make_local_dt(ci.date(), time(12, 0))  # 午休开始
        rest_end = self._make_local_dt(ci.date(), time(13, 0))  # 午休结束
        ot_start = self._make_local_dt(ci.date(), time(16, 0))  # 加班开始
        ot_end = self._make_local_dt(ci.date(), WHITE_END_T)  # 19:00

        # ---- 标准工时（07:00–16:00 扣除午休） ----
        work_std = self._calculate_hours_interval(ci, co, std_start, std_end)
        rest = self._calculate_hours_interval(ci, co, rest_start, rest_end)
        white_standard = max(0.0, work_std - rest)

        # ---- 白班加班（16:00–19:00） ----
        white_ot = self._calculate_hours_interval(ci, co, ot_start, ot_end)

        result = {
            "worked_hours": round(white_standard, 2),
            "ot_weekday": round(white_ot, 2),
        }

        print(f"[白班工时] 标准工时 {white_standard:.2f}h (已扣午休{rest:.2f}h)，加班工时 {white_ot:.2f}h")
        print(f"[白班工时结果] {result}")
        return result


    def calculate_night_shift_hours(self, step: int = 30):
        """
        计算夜班工时拆分
        - 正常夜班：19:00–22:00
        - 深夜夜班：22:00–03:00
        - 夜班加班：03:00–07:00
        - 夜宵补贴：当次夜班 >= 8.5h → True，否则 False
        """
        # 先调用 normalize_attendance 去皮
        ci, co = self.normalize_attendance(step=step)

        # 夜班时间段
        normal_start = self._make_local_dt(ci.date(), NIGHT_START_T)             # 19:00
        normal_end   = self._make_local_dt(ci.date(), time(22, 0)) # 22:00
        deep_start   = self._make_local_dt(ci.date(), time(22, 0)) # 22:00
        deep_end     = self._make_local_dt(ci.date() + timedelta(days=1), time(3, 0)) # 03:00
        ot_start     = self._make_local_dt(ci.date() + timedelta(days=1), time(3, 0)) # 03:00
        ot_end       = self._make_local_dt(ci.date() + timedelta(days=1), NIGHT_END_T)  # 07:00

        # ---- 分段计算 ----
        night_normal = self._calculate_hours_interval(ci, co, normal_start, normal_end)
        night_deep   = self._calculate_hours_interval(ci, co, deep_start, deep_end)
        night_ot     = self._calculate_hours_interval(ci, co, ot_start, ot_end)

        # ---- 计算总工时 & 夜宵补贴 ----
        total_hours = (co - ci).total_seconds() / 3600.0
        night_full = 1 if total_hours > 8 else 0

        result = {
            "night_regular": round(night_normal, 2),
            "night_deep": round(night_deep, 2),
            "night_ot": round(night_ot, 2),
            "night_full_days": night_full,
        }

        print(f"[夜班工时] 正常夜班 {night_normal:.2f}h | 深夜夜班 {night_deep:.2f}h | 夜班加班 {night_ot:.2f}h")
        print(f"[夜班工时] 总工时 {total_hours:.2f}h → 夜宵补贴 night_full={night_full}")
        print(f"[夜班工时结果] {result}")
        return result
