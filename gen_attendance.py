#!/usr/bin/env python3
import odoo
import odoo.tools.config as config
from datetime import datetime, time, date, timedelta
import calendar
import pytz


def generate_attendance(env, employee_name: str, year: int, month: int):
    """根据员工名字生成考勤（7月6-20白班，其余夜班，周日休息）"""
    employee = env['hr.employee'].search([('name', '=', employee_name)], limit=1)
    if not employee:
        print(f"❌ 未找到员工: {employee_name}")
        return

    _, days_in_month = calendar.monthrange(year, month)
    all_days = [date(year, month, d) for d in range(1, days_in_month + 1)]

    # 删除旧考勤
    start_dt = datetime(year, month, 1, 0, 0, 0)
    end_dt = datetime(year, month, days_in_month, 23, 59, 59)
    old_records = env['hr.attendance'].search([
        ('employee_id', '=', employee.id),
        ('check_in', '>=', start_dt),
        ('check_in', '<=', end_dt),
    ])
    if old_records:
        print(f"🗑️ 删除旧考勤 {len(old_records)} 条记录")
        old_records.unlink()

    print(f"=== 开始生成 {year}-{month:02d} 考勤，员工: {employee.name} (ID={employee.id}) ===")

    for d in all_days:
        weekday = d.weekday()  # 0=周一, 6=周日

        if weekday == 6:
            # 周日休息
            print(f"🛑 {d} 周日休息")
            continue

        if 6 <= d.day <= 20:
            # 白班
            check_in = datetime.combine(d, time(7, 0))
            check_out = datetime.combine(d, time(19, 0))
            print(f"☀️ {d} 白班: 上班 07:00 下班 19:00")
        else:
            # 夜班
            check_in = datetime.combine(d, time(19, 0))
            check_out = datetime.combine(d + timedelta(days=1), time(7, 0))
            print(f"🌙 {d} 夜班: 上班 19:00 下班 次日07:00")

        env['hr.attendance'].create({
            'employee_id': employee.id,
            'check_in': to_utc(env, check_in),
            'check_out': to_utc(env, check_out),
        })

    print(f"✅ 考勤生成完成: {year}-{month:02d} 员工 {employee.name}")


def to_utc(env, naive_dt):
    """将 naive datetime (本地时间) 转换为 UTC naive datetime"""
    user_tz = env.user.tz or 'UTC'
    tz = pytz.timezone(user_tz)
    localized = tz.localize(naive_dt)
    utc_dt = localized.astimezone(pytz.utc)
    return utc_dt.replace(tzinfo=None)  # ORM 期望 naive UTC datetime


def main(db_name: str, employee_name: str, year: int, month: int):
    """Odoo 17 main 入口"""
    config['db_name'] = db_name
    odoo.tools.config.parse_config([])

    registry = odoo.modules.registry.Registry(db_name)
    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        generate_attendance(env, employee_name, year, month)
        cr.commit()


if __name__ == "__main__":
    db_name = 'oddo'  # 改成你的数据库名
    employee_name = '范文光'
    year = 2025
    month = 5
    main(db_name, employee_name, year, month)
