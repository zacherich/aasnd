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

BOMSTATE = [('draft', u'草稿'), ('normal', u'正常'), ('override', u'失效')]

# 物料清单
class AASMESBOM(models.Model):
    _name = 'aas.mes.bom'
    _description = 'Bill of Material'
    _rec_name = 'product_id'

    product_id = fields.Many2one(comodel_name='product.product', string=u'产品', required=True, ondelete='restrict')
    product_uom = fields.Many2one(comodel_name='product.uom', string=u'单位', ondelete='restrict')
    product_qty = fields.Float(string=u'数量', digits=dp.get_precision('Product Unit of Measure'), default=1.0)
    routing_id = fields.Many2one(comodel_name='aas.mes.routing', string=u'工艺', ondelete='restrict')
    active = fields.Boolean(string=u'是否有效', default=True, copy=False)
    version = fields.Char(string=u'版本', copy=False)
    note = fields.Text(string=u'描述')
    state = fields.Selection(selection=BOMSTATE, string=u'状态', default='draft', copy=False)
    create_time = fields.Datetime(string=u'创建时间', default=fields.Datetime.now, copy=False)
    mesline_id = fields.Many2one(comodel_name='aas.mes.line', string=u'产线', ondelete='restrict')
    origin_id = fields.Many2one(comodel_name='aas.mes.bom', string=u'源BOM', ondelete='restrict')
    owner_id = fields.Many2one(comodel_name='res.users', string=u'负责人', default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', string=u'公司', default=lambda self: self.env.user.company_id)
    bom_lines = fields.One2many(comodel_name='aas.mes.bom.line', inverse_name='bom_id', string=u'BOM明细')
    workcenter_lines = fields.One2many(comodel_name='aas.mes.bom.workcenter', inverse_name='bom_id', string=u'工序明细')

    @api.one
    @api.constrains('product_qty')
    def action_check_product_qty(self):
        if not self.product_qty or float_compare(self.product_qty, 0.0, precision_rounding=0.000001) <= 0.0:
            raise ValidationError(u'数量必须是一个正数！')

    @api.one
    @api.constrains('product_id')
    def action_check_product(self):
        productcount = self.env['aas.mes.bom'].search_count([('product_id', '=', self.product_id.id)])
        if productcount > 1:
            raise ValidationError(u'同一产品只能有一个有效的物料清单！')

    @api.model
    def action_checking_version(self):
        tz_name = self.env.user.tz or self.env.context.get('tz') or 'Asia/Shanghai'
        utctime = fields.Datetime.from_string(fields.Datetime.now())
        utctime = pytz.timezone('UTC').localize(utctime, is_dst=False)
        currenttime = utctime.astimezone(pytz.timezone(tz_name))
        return currenttime.strftime('%Y%m%d')

    @api.onchange('product_id')
    def action_change_product(self):
        if not self.product_id:
            self.product_uom = False
        else:
            self.product_uom = self.product_id.uom_id.id


    @api.model
    def create(self, vals):
        self.action_before_create(vals)
        return super(AASMESBOM, self).create(vals)

    @api.model
    def action_before_create(self, vals):
        if vals.get('product_id', False):
            product = self.env['product.product'].browse(vals.get('product_id'))
            vals['product_uom'] = product.uom_id.id
        vals['version'] = self.action_checking_version()

    @api.multi
    def write(self, vals):
        if vals.get('product_id', False):
            product = self.env['product.product'].browse(vals.get('product_id'))
            vals['product_uom'] = product.uom_id.id
        return super(AASMESBOM, self).write(vals)


    @api.multi
    def action_change_bom(self):
        self.ensure_one()
        wizard = self.env['aas.mes.bom.wizard'].create({
            'bom_id': self.id, 'product_id': self.product_id.id, 'product_uom': self.product_uom.id,
            'product_qty': self.product_qty,
            'mesline_id': False if not self.mesline_id else self.mesline_id.id,
            'routing_id': False if not self.routing_id else self.routing_id.id,
            'wizard_lines': [(0, 0, {
                'product_id': wline.product_id.id, 'product_uom': wline.product_uom.id, 'product_qty': wline.product_qty,
                'workcenter_id': False if not wline.workcenter_id else wline.workcenter_id.id
            }) for wline in self.workcenter_lines]
        })
        view_form = self.env.ref('aas_mes.view_form_aas_mes_bom_wizard')
        return {
            'name': u"变更清单",
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'aas.mes.bom.wizard',
            'views': [(view_form.id, 'form')],
            'view_id': view_form.id,
            'target': 'new',
            'res_id': wizard.id,
            'context': self.env.context
        }




class AASMESBOMLine(models.Model):
    _name = 'aas.mes.bom.line'
    _description = 'Bill of Material Line'

    bom_id = fields.Many2one(comodel_name='aas.mes.bom', string='BOM', required=True, ondelete='cascade')
    product_id = fields.Many2one(comodel_name='product.product', string=u'产品', required=True, ondelete='restrict')
    product_uom = fields.Many2one(comodel_name='product.uom', string=u'单位', ondelete='restrict')
    product_qty = fields.Float(string=u'数量', digits=dp.get_precision('Product Unit of Measure'), default=1.0)
    workcenter_lines = fields.One2many(comodel_name='aas.mes.bom.workcenter', inverse_name='bom_line_id', string=u'工序明细')

    _sql_constraints = [
        ('uniq_product', 'unique (bom_id, product_id)', u'请不要重复添加同一个产品清单！')
    ]

    @api.onchange('product_id')
    def action_change_product(self):
        if not self.product_id:
            self.product_uom = False
        else:
            self.product_uom = self.product_id.uom_id.id


    @api.model
    def create(self, vals):
        if vals.get('product_id', False):
            product = self.env['product.product'].browse(vals.get('product_id'))
            vals['product_uom'] = product.uom_id.id
        return super(AASMESBOMLine, self).create(vals)

    @api.multi
    def write(self, vals):
        if vals.get('product_id', False):
            product = self.env['product.product'].browse(vals.get('product_id'))
            vals['product_uom'] = product.uom_id.id
        return super(AASMESBOMLine, self).write(vals)

class AASMESBOMWorkcenter(models.Model):
    _name = 'aas.mes.bom.workcenter'
    _description = 'Bill of Material Workcenter'

    bom_id = fields.Many2one(comodel_name='aas.mes.bom', string='BOM', ondelete='cascade')
    bom_line_id = fields.Many2one(comodel_name='aas.mes.bom.line', string='BOMLine', ondelete='cascade')
    product_id = fields.Many2one(comodel_name='product.product', string=u'产品', required=True, ondelete='restrict')
    product_uom = fields.Many2one(comodel_name='product.uom', string=u'单位', ondelete='restrict')
    product_qty = fields.Float(string=u'数量', digits=dp.get_precision('Product Unit of Measure'), default=1.0)
    workcenter_id = fields.Many2one(comodel_name='aas.mes.routing.line', string=u'工艺工序', ondelete='restrict')

    _sql_constraints = [
        ('uniq_product_workcenter', 'unique (bom_id, product_id, workcenter_id)', u'请不要在同一工序上重复添加同一产品！')
    ]

    @api.one
    @api.constrains('product_qty', 'workcenter_id')
    def action_check_bomworkcenter(self):
        if not self.product_qty or float_compare(self.product_qty, 0.0, precision_rounding=0.000001) <= 0.0:
            raise ValidationError(u'数量必须是一个正数！')
        if self.workcenter_id and self.workcenter_id.routing_id.id != self.bom_id.routing_id.id:
            raise ValidationError(u'请检查工序%s与工艺%s不匹配！', (self.workcenter_id.name, self.bom_id.routing_id.name))



    @api.onchange('product_id')
    def action_change_product(self):
        if not self.product_id:
            self.product_uom = False
        else:
            self.product_uom = self.product_id.uom_id.id

    @api.model
    def create(self, vals):
        self.action_before_create(vals)
        record = super(AASMESBOMWorkcenter, self).create(vals)
        record.action_after_create()
        return record

    @api.one
    def action_before_create(self, vals):
        if vals.get('product_id', False):
            product = self.env['product.product'].browse(vals.get('product_id'))
            vals['product_uom'] = product.uom_id.id

    @api.one
    def action_after_create(self):
        bomline = self.env['aas.mes.bom.line'].search([('bom_id', '=', self.bom_id.id), ('product_id', '=', self.product_id.id)], limit=1)
        if bomline:
            bomline.write({'product_qty': bomline.product_qty + self.product_qty})
        else:
            bomline = self.env['aas.mes.bom.line'].create({
                'bom_id': self.bom_id.id, 'product_id': self.product_id.id,
                'product_uom': self.product_uom.id, 'product_qty': self.product_qty
            })
        self.write({'bom_line_id': bomline.id})



    @api.multi
    def write(self, vals):
        if vals.get('product_id', False):
            raise UserError(u'产品信息不可以修改！')
        return super(AASMESBOMWorkcenter, self).write(vals)

    @api.multi
    def unlink(self):
        productlinedict = {}
        for record in self:
            lkey = 'L'+str(record.bom_line_id.id)
            if lkey in productlinedict:
                productlinedict[lkey]['product_qty'] += record.product_qty
            else:
                productlinedict[lkey] = {'line': record.bom_line_id, 'product_qty': record.product_qty}
        result = super(AASMESBOMWorkcenter, self).unlink()
        for tkey, tval in productlinedict.items():
            bomline, product_qty = tval['line'], tval['product_qty']
            product_qty = bomline.product_qty - product_qty
            if float_compare(product_qty, 0.0, precision_rounding=0.000001) <= 0.0:
                bomline.unlink()
            else:
                bomline.write({'product_qty': product_qty})




#############################################向导#############################################

class AASMESBOMWizard(models.TransientModel):
    _name = 'aas.mes.bom.wizard'
    _description = 'AAS MES BOM Wizard'

    bom_id = fields.Many2one(comodel_name='aas.mes.bom', string='BOM', ondelete='cascade')
    product_id = fields.Many2one(comodel_name='product.product', string=u'产品', ondelete='restrict')
    product_uom = fields.Many2one(comodel_name='product.uom', string=u'单位', ondelete='restrict')
    product_qty = fields.Float(string=u'数量', digits=dp.get_precision('Product Unit of Measure'), default=1.0)
    routing_id = fields.Many2one(comodel_name='aas.mes.routing', string=u'工艺', ondelete='restrict')
    mesline_id = fields.Many2one(comodel_name='aas.mes.line', string=u'产线', ondelete='restrict')
    wizard_lines = fields.One2many(comodel_name='aas.mes.bom.workcenter.wizard', inverse_name='wizard_id', string=u'明细清单')

    @api.onchange('product_id')
    def action_change_product(self):
        if not self.product_id:
            self.product_uom = False
        else:
            self.product_uom = self.product_id.uom_id.id

    @api.one
    @api.constrains('product_qty')
    def action_check_product_qty(self):
        if not self.product_qty or float_compare(self.product_qty, 0.0, precision_rounding=0.000001) <= 0.0:
            raise ValidationError(u'数量必须是一个正数！')


    @api.model
    def create(self, vals):
        if vals.get('product_id', False) and not vals.get('product_uom', False):
            product = self.env['product.product'].browse(vals.get('product_id'))
            vals['product_uom'] = product.uom_id.id
        return super(AASMESBOMWizard, self).create(vals)

    @api.multi
    def write(self, vals):
        if vals.get('product_id', False) and not vals.get('product_uom', False):
            product = self.env['product.product'].browse(vals.get('product_id'))
            vals['product_uom'] = product.uom_id.id
        return super(AASMESBOMWizard, self).write(vals)

    @api.multi
    def action_done(self):
        self.ensure_one()
        if not self.wizard_lines or len(self.wizard_lines) <= 0:
            raise UserError(u'请先添加明细清单！')
        self.bom_id.write({'state': 'override', 'active': False})
        tempvals = {
            'product_id': self.product_id.id, 'product_uom': self.product_uom.id,
            'mesline_id': False if not self.mesline_id else self.mesline_id.id,
            'routing_id': False if not self.routing_id else self.routing_id.id,
            'origin_id': self.bom_id.id, 'product_qty': self.product_qty,
            'workcenter_lines': [(0, 0, {
                'product_id': wline.product_id.id, 'product_uom': wline.product_uom.id, 'product_qty': wline.product_qty,
                'workcenter_id': False if not wline.workcenter_id else wline.workcenter_id.id
            }) for wline in self.wizard_lines]
        }
        tempbom = self.env['aas.mes.bom'].create(tempvals)
        view_form = self.env.ref('aas_mes.view_form_aas_mes_bom')
        return {
            'name': u"新物料清单",
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'aas.mes.bom',
            'views': [(view_form.id, 'form')],
            'view_id': view_form.id,
            'target': 'self',
            'res_id': tempbom.id,
            'context': self.env.context
        }



class AASMESBOMWorkcenterWizard(models.TransientModel):
    _name = 'aas.mes.bom.workcenter.wizard'
    _description = 'AAS MES BOM Workcenter Wizard'

    wizard_id = fields.Many2one(comodel_name='aas.mes.bom.wizard', string=u'向导', ondelete='cascade')
    product_id = fields.Many2one(comodel_name='product.product', string=u'产品', required=True, ondelete='restrict')
    product_uom = fields.Many2one(comodel_name='product.uom', string=u'单位', ondelete='restrict')
    product_qty = fields.Float(string=u'数量', digits=dp.get_precision('Product Unit of Measure'), default=1.0)
    workcenter_id = fields.Many2one(comodel_name='aas.mes.routing.line', string=u'工艺工序', ondelete='restrict')

    @api.onchange('product_id')
    def action_change_product(self):
        if not self.product_id:
            self.product_uom = False
        else:
            self.product_uom = self.product_id.uom_id.id

    @api.one
    @api.constrains('product_qty', 'workcenter_id')
    def action_check_bomworkcenter(self):
        if not self.product_qty or float_compare(self.product_qty, 0.0, precision_rounding=0.000001) <= 0.0:
            raise ValidationError(u'数量必须是一个正数！')
        if self.workcenter_id and self.workcenter_id.routing_id.id != self.wizard_id.routing_id.id:
            raise ValidationError(u'请检查工序%s与工艺%s不匹配！', (self.workcenter_id.name, self.wizard_id.routing_id.name))

    @api.model
    def create(self, vals):
        if vals.get('product_id', False) and not vals.get('product_uom', False):
            product = self.env['product.product'].browse(vals.get('product_id'))
            vals['product_uom'] = product.uom_id.id
        return super(AASMESBOMWorkcenterWizard, self).create(vals)

    @api.multi
    def write(self, vals):
        if vals.get('product_id', False) and not vals.get('product_uom', False):
            product = self.env['product.product'].browse(vals.get('product_id'))
            vals['product_uom'] = product.uom_id.id
        return super(AASMESBOMWorkcenterWizard, self).write(vals)





