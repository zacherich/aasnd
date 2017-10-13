# -*-  coding: utf-8 -*-

"""
@version: 1.0
@author: luforn
@license: LGPL V3
@time: 2017-9-18 15:05
"""

from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_compare, float_is_zero
from odoo.exceptions import UserError, ValidationError

import pytz
import logging

_logger = logging.getLogger(__name__)

ROUTSTATE = [('draft', u'草稿'), ('normal', u'正常'), ('override', u'失效')]


# 工艺
class AASMESRouting(models.Model):
    _name = 'aas.mes.routing'
    _description = 'AAS MES Routing'

    name = fields.Char(string=u'名称', required=True, copy=False)
    active = fields.Boolean(string=u'有效', default=True, copy=False)
    version = fields.Char(string=u'版本', copy=False)
    note = fields.Text(string=u'描述')
    state = fields.Selection(selection=ROUTSTATE, string=u'状态', default='draft', copy=False)
    create_time = fields.Datetime(string=u'创建时间', default=fields.Datetime.now, copy=False)
    mesline_id = fields.Many2one(comodel_name='aas.mes.line', string=u'产线', ondelete='restrict')
    origin_id = fields.Many2one(comodel_name='aas.mes.routing', string=u'源工艺', ondelete='restrict')
    owner_id = fields.Many2one(comodel_name='res.users', string=u'负责人', default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', string=u'公司', default=lambda self: self.env.user.company_id)
    routing_lines = fields.One2many(comodel_name='aas.mes.routing.line', inverse_name='routing_id', string=u'工艺工序')

    @api.model
    def action_checking_version(self):
        tz_name = self.env.user.tz or self.env.context.get('tz') or 'Asia/Shanghai'
        utctime = fields.Datetime.from_string(fields.Datetime.now())
        utctime = pytz.timezone('UTC').localize(utctime, is_dst=False)
        currenttime = utctime.astimezone(pytz.timezone(tz_name))
        return currenttime.strftime('%Y%m%d')

    @api.model
    def create(self, vals):
        vals['version'] = self.action_checking_version()
        vals['state'] = 'normal'
        return super(AASMESRouting, self).create(vals)

    @api.multi
    def action_change_routing(self):
        self.ensure_one()
        wizard = self.env['aas.mes.routing.wizard'].create({
            'routing_id': self.id, 'name': self.name, 'note': self.note,
            'mesline_id': False if not self.mesline_id else self.mesline_id.id,
            'wizard_lines': [(0, 0, {
                'name': rline.name, 'sequence': rline.sequence, 'note': rline.note,
                'workstation_id': False if not rline.workstation_id else rline.workstation_id.id
            }) for rline in self.routing_lines]
        })
        view_form = self.env.ref('aas_mes.view_form_aas_mes_routing_wizard')
        return {
            'name': u"变更工艺",
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'aas.mes.routing.wizard',
            'views': [(view_form.id, 'form')],
            'view_id': view_form.id,
            'target': 'new',
            'res_id': wizard.id,
            'context': self.env.context
        }


# 工艺工序
class AASMESRoutingLine(models.Model):
    _name = 'aas.mes.routing.line'
    _description = 'AAS MES Routing Line'
    _order = 'routing_id desc,sequence'

    routing_id = fields.Many2one(comodel_name='aas.mes.routing', string=u'工艺', required=True, ondelete='cascade')
    name = fields.Char(string=u'名称', required=True, copy=False)
    sequence = fields.Integer(string=u'序号')
    note = fields.Text(string=u'描述')
    mesline_id = fields.Many2one(comodel_name='aas.mes.line', string=u'产线', ondelete='restrict')
    workstation_id = fields.Many2one(comodel_name='aas.mes.workstation', string=u'工位', ondelete='restrict')
    company_id = fields.Many2one('res.company', string=u'公司', default=lambda self: self.env.user.company_id)
    badmode_lines = fields.One2many(comodel_name='aas.mes.routing.badmode', inverse_name='workcenter_id', string=u'不良模式')

    _sql_constraints = [
        ('uniq_sequence', 'unique (routing_id, sequence)', u'同一工艺的工序序号不可以重复！')
    ]

    @api.model
    def create(self, vals):
        if vals.get('routing_id', False) and not vals.get('mesline_id', False):
            routing = self.env['aas.mes.routing'].browse(vals.get('routing_id'))
            if routing.mesline_id:
                vals['mesline_id'] = routing.mesline_id.id
        return super(AASMESRoutingLine, self).create(vals)


# 工序不良模式
class AASMESRoutingBadmode(models.Model):
    _name = 'aas.mes.routing.badmode'
    _description = 'AAS MES Routing Bad Mode'
    _rec_name = 'badmode_name'

    workcenter_id = fields.Many2one(comodel_name='aas.mes.routing.line', string=u'工序', ondelete='cascade')
    badmode_id = fields.Many2one(comodel_name='aas.mes.badmode', string=u'不良模式', ondelete='restrict')
    badmode_name = fields.Char(string=u'不良名称', copy=False)

    @api.model
    def create(self, vals):
        if vals.get('badmode_id', False):
            badmode = self.env['aas.mes.badmode'].browse(vals.get('badmode_id'))
            vals['badmode_name'] = badmode.name
        return super(AASMESRoutingBadmode, self).create(vals)


    @api.multi
    def write(self, vals):
        if vals.get('badmode_id', False):
            badmode = self.env['aas.mes.badmode'].browse(vals.get('badmode_id'))
            vals['badmode_name'] = badmode.name
        return super(AASMESRoutingBadmode, self).write(vals)






#############################################向导#############################################



class AASMESRoutingWizard(models.TransientModel):
    _name = 'aas.mes.routing.wizard'
    _description = 'AAS MES Routing Wizard'

    routing_id = fields.Many2one(comodel_name='aas.mes.routing', string=u'工艺', required=True, ondelete='cascade')
    name = fields.Char(string=u'名称')
    note = fields.Text(string=u'描述')
    mesline_id = fields.Many2one(comodel_name='aas.mes.line', string=u'产线', ondelete='restrict')
    wizard_lines = fields.One2many(comodel_name='aas.mes.routing.line.wizard', inverse_name='wizard_id', string=u'工艺工序')

    @api.multi
    def action_done(self):
        self.ensure_one()
        if not self.wizard_lines or len(self.wizard_lines) <= 0:
            raise UserError(u'请先添加工艺工序！')
        routing = self.env['aas.mes.routing'].create({
            'name': self.name, 'note': self.note, 'origin_id': self.routing_id.id,
            'mesline_id': False if not self.mesline_id else self.mesline_id.id,
            'routing_lines': [(0, 0, {
                'name': wline.name, 'sequence': wline.sequence, 'note': wline.note,
                'workstation_id': False if not wline.workstation_id else wline.workstation_id.id
            }) for wline in self.wizard_lines]
        })
        self.routing_id.write({'active': False, 'state': 'override'})
        view_form = self.env.ref('aas_mes.view_form_aas_mes_routing')
        return {
            'name': u"生产工艺",
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'aas.mes.routing',
            'views': [(view_form.id, 'form')],
            'view_id': view_form.id,
            'target': 'self',
            'res_id': routing.id,
            'context': self.env.context
        }


class AASMESRoutingLineWizard(models.TransientModel):
    _name = 'aas.mes.routing.line.wizard'
    _description = 'AAS MES Routing Line Wizard'
    _order = 'sequence,id'

    wizard_id = fields.Many2one(comodel_name='aas.mes.routing.wizard', string=u'工艺', ondelete='cascade')
    name = fields.Char(string=u'名称')
    sequence = fields.Integer(string=u'序号')
    note = fields.Text(string=u'描述')
    workstation_id = fields.Many2one(comodel_name='aas.mes.workstation', string=u'工位', ondelete='restrict')