{
    'name': 'Attendance Payroll Extension',
    'version': '1.0',
    'depends': ['payroll', 'hr_attendance'],  # 社区版 payroll 模块依赖
    'author': 'Your Company',
    'category': 'Human Resources',
    'data': [
        'views/hr_attendance_payroll_views.xml',  # 加载你的视图扩展
    ],
    'installable': True,
    'application': False,
}
