# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime, timedelta, time
import pytz

from odoo.exceptions import ValidationError
from payroll_oca.hr_attendance_payroll.models.utils import HrPayslipUtils, ShiftType, VN_TZ


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'
    import time
    print(time.tzname)
    # 白班字段
    standard_hours = fields.Float("标准工时")
    worked_hours = fields.Float("实际工时")
    ot_weekday = fields.Float("工作日加班")  # 16:00-19:00
    ot_weekend = fields.Float("周末加班")
    ot_holiday = fields.Float("节假日加班")

    # 夜班字段
    night_regular = fields.Float("夜班 19-22")
    night_deep = fields.Float("深夜班 22-03")
    night_ot = fields.Float("夜班加班 03-07")

    # 新增字段
    attendance_rate = fields.Float("出勤率")
    remaining_paid_leave_hours = fields.Float("带薪休假剩余小时数")
    night_full_days = fields.Integer("夜班满勤天数", compute="_compute_night_full_days", store=True)


    def compute_sheet(self):
        """覆盖 compute_sheet，先计算工时和加班（小时数），再走原计算"""
        print(f"[HrPayslip][{self.employee_id.name}] >>> 调用 compute_sheet，开始计算工时和加班")
        self.compute_attendance_hours()
        return super().compute_sheet()

    # -----------------------------------------------------------
    # 工时计算主函数
    # -----------------------------------------------------------
    def compute_attendance_hours(self):
        standard_hours = 0 # self.standard_hours
        for slip in self:
            emp = slip.employee_id
            emp_name = emp.name
            tz = pytz.timezone(emp.user_id.tz or self.env.user.tz or "Asia/Ho_Chi_Minh")
            print(f"\n[HrPayslip][{emp_name}] === 开始计算工时: {slip.date_from} ~ {slip.date_to} ===")

            # 公共假期（按 employee 提供的方法）
            holiday_dates = set()
            try:
                public_holidays_data = emp.get_public_holidays_data(slip.date_from, slip.date_to)
                for bh in public_holidays_data:
                    try:
                        start = datetime.fromisoformat(bh['start']).date()
                        end = datetime.fromisoformat(bh['end']).date()
                        for dd in range((end - start).days + 1):
                            holiday_dates.add(start + timedelta(days=dd))
                    except Exception:
                        continue
            except Exception as e:
                print(f"[HrPayslip][{emp_name}] ❌ 获取公共假期失败: {e}")
                holiday_dates = set()

            print(f"[HrPayslip][{emp_name}] 公共假日: {sorted(list(holiday_dates))}")

            # 计算白班标准工时（周一～周六，排除周日和公共假日）
            day_count = (slip.date_to - slip.date_from).days + 1
            for i in range(day_count):
                d = slip.date_from + timedelta(days=i)
                if d.weekday() != 6:
                    standard_hours += 8.0
            print(f"[HrPayslip][{emp.name}] 白班标准工时(周期内): {standard_hours}h")


            # 2. 初始化统计
            totals = dict(
                worked_hours=0,
                ot_weekday=0, ot_weekend=0, ot_holiday=0,
                night_regular=0, night_deep=0, night_ot=0,
                night_full_days=0
            )

            # 3. 遍历考勤
            attendances = self.env["hr.attendance"].search([
                ("employee_id", "=", emp.id),
                ("check_in", "<=", slip.date_to),
                ("check_out", ">=", slip.date_from),
            ])

            for att in attendances:
                # 转换到本地时区一次
                check_in_utc = att.check_in  # Odoo 存储的 UTC
                check_out_utc = att.check_out
                # 转换为 tz-aware 越南本地时间
                ci_local = check_in_utc.astimezone(VN_TZ)
                co_local = check_out_utc.astimezone(VN_TZ)


                # 使用工具类计算工时分布
                utils = HrPayslipUtils(ci_local, co_local)
                if utils.shift_type == ShiftType.WHITE:
                    result = utils.calculate_white_shift_hours()
                elif utils.shift_type == ShiftType.NIGHT:
                    result = utils.calculate_night_shift_hours()

                # 判断节假日/周末
                day = ci_local.date()
                is_holiday = day in holiday_dates  # 是否节假日
                is_weekend = (day.weekday() == 6)  # 是否周日

                if is_holiday:
                    if utils.shift_type == ShiftType.NIGHT:
                        ValidationError(f"考勤数据有误，节假日不能有晚班{day}")
                    else:
                        totals["ot_holiday"] += sum(result.values())
                elif is_weekend:
                    if utils.shift_type == ShiftType.NIGHT:
                        ValidationError(f"考勤数据有误，周日不能有晚班{day}")
                    else:
                        totals["ot_weekend"] += sum(result.values())
                else:
                    for k, v in result.items():
                        if k in totals:
                            totals[k] += v

                # # 额外：夜班满勤天数
                # if utils.shift_type == ShiftType.NIGHT and result.get("night_full", False):
                #     totals["night_full_days"] += 1

            # 计算总出勤小时数和出勤率
            totals["worked_hours"] = totals["worked_hours"] + len(holiday_dates) * 8  # 这里加上节假日自动补8小时
            total_attendance_hours = totals["worked_hours"] + totals["night_regular"] + totals["night_deep"]

            # 计算需要带薪休假补齐的小时数
            if total_attendance_hours < standard_hours:
                paid_leave_hours_used = min(8.0, standard_hours - total_attendance_hours)
                total_attendance_hours += paid_leave_hours_used
                remaining_paid_leave_hours = 8.0 - paid_leave_hours_used
                print(f"[HrPayslip][{emp.name}] 💼 使用带薪休假补齐: {round(paid_leave_hours_used, 2)}h")
            else:
                paid_leave_hours_used = 0.0
                remaining_paid_leave_hours = 8.0

            # 计算出勤率
            if standard_hours > 0:
                attendance_rate = min(100.0, (total_attendance_hours / standard_hours) * 100)
            else:
                attendance_rate = 0.0

            # 4. 赋值到 slip
            slip.standard_hours = standard_hours
            slip.worked_hours = totals["worked_hours"]
            slip.ot_weekday = totals["ot_weekday"]
            slip.ot_weekend = totals["ot_weekend"]
            slip.ot_holiday = totals["ot_holiday"]

            slip.night_regular = totals["night_regular"]
            slip.night_deep = totals["night_deep"]
            slip.night_ot = totals["night_ot"]

            slip.night_full_days = totals["night_full_days"]

            # 出勤率（实际工时 / 标准工时）
            slip.attendance_rate =  attendance_rate

            # 带薪休假剩余小时数（假设已有字段 contract_id.leave_hours_total）
            slip.remaining_paid_leave_hours = remaining_paid_leave_hours

            # 最终日志汇总
            print(
                f"[HrPayslip][{emp.name}] 计算完成 => 标准: {slip.standard_hours}h, 白班: {slip.worked_hours}h, "
                f"工作日加班: {slip.ot_weekday}h, 周末加班: {slip.ot_weekend}h, 节假日加班: {slip.ot_holiday}h, "
                f"夜班: {slip.night_regular}h, 夜班深夜: {slip.night_deep}h, 夜班加班: {slip.night_ot}h"
            )
            print(
                f"[HrPayslip][{emp.name}] 实际出勤：{total_attendance_hours} 出勤率: {slip.attendance_rate}%={total_attendance_hours}/{standard_hours},  带薪休假剩余小时数: {slip.remaining_paid_leave_hours}h")

    # --------- --------------------------------------------------
    # 夜班满勤天数 (备用，存储用)
    # -----------------------------------------------------------
    @api.depends("worked_hours", "night_regular", "night_deep", "night_ot")
    def _compute_night_full_days(self):
        for slip in self:
            # 这里逻辑已经在 compute_attendance_hours 填充
            slip.night_full_days = slip.night_full_days
