from odoo import models, fields, api

'''
在员工合同加如下字段，是直接跟员工相关的
    - 交通补贴
    - 语言补贴
    - 环境补贴
    - 是否通过考试 （基础工资有加成）


'''
# -*- coding: utf-8 -*-
from odoo import models, fields, api


class HrContract(models.Model):
    _inherit = 'hr.contract'

    # 交通补贴
    x_allowance_wage = fields.Monetary(
        string="交通补贴",
        currency_field='currency_id',
        help="每月的交通补助金额"
    )

    # 语言补贴
    x_language_allowance = fields.Monetary(
        string="语言补贴",
        currency_field='currency_id',
        help="每月的语言补助金额"
    )

    # 环境补贴
    x_environment_allowance = fields.Monetary(
        string="环境补贴",
        currency_field='currency_id',
        help="每月的环境补助金额"
    )

    # 是否通过考试
    x_exam_passed = fields.Boolean(
        string="是否通过考试",
        help="用于记录员工是否通过考试"
    )


    # 缴纳保险工资
    insurance_base_wage = fields.Monetary(
        string="缴纳保险工资",
        currency_field='currency_id',
        help="计算保险时的工资基数，可与合同工资不同"
    )

    # 个税起征金额（默认 11,000,000）
    personal_tax_threshold = fields.Monetary(
        string="个税起征金额",
        currency_field='currency_id',
        default=11000000.0,
        help="个税起征点，默认 11,000,000，有子女可调整"
    )

    # 让交通补贴默认跟工资一致
    @api.model
    def create(self, vals):
        if 'x_allowance_wage' not in vals and 'wage' in vals:
            vals['x_allowance_wage'] = vals['wage']
        return super().create(vals)

    def write(self, vals):
        # 如果工资改了，交通补贴保持同步（可选逻辑）
        if 'wage' in vals and 'x_allowance_wage' not in vals:
            vals['x_allowance_wage'] = vals['wage']
        return super().write(vals)
