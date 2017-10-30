# -*-  coding: utf-8 -*-

"""
@version: 1.0
@author: luforn
@license: LGPL V3
@time: 2017-9-21 14:47
"""

from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_compare, float_is_zero
from odoo.exceptions import UserError, ValidationError
from . import MESLINETYPE

import logging

_logger = logging.getLogger(__name__)

# 子工单

ORDERSTATES = [('draft', u'草稿'), ('confirm', u'确认'), ('producing', u'生产'), ('pause', u'暂停'), ('done', u'完成')]

class AASMESWorkorder(models.Model):
    _name = 'aas.mes.workorder'
    _description = 'AAS MES Work Order'

    name = fields.Char(string=u'名称', required=True, copy=False, index=True)
    barcode = fields.Char(string=u'条码', compute='_compute_barcode', store=True, index=True)
    product_id = fields.Many2one(comodel_name='product.product', string=u'产品', required=True, index=True)
    product_uom = fields.Many2one(comodel_name='product.uom', string=u'单位', ondelete='restrict')
    input_qty = fields.Float(string=u'投入数量', digits=dp.get_precision('Product Unit of Measure'), default=1.0)
    aas_bom_id = fields.Many2one(comodel_name='aas.mes.bom', string=u'物料清单', ondelete='restrict', index=True)
    routing_id = fields.Many2one(comodel_name='aas.mes.routing', string=u'工艺路线', ondelete='restrict', index=True)
    mesline_id = fields.Many2one(comodel_name='aas.mes.line', string=u'产线', ondelete='restrict', index=True)
    time_create = fields.Datetime(string=u'创建时间', default=fields.Datetime.now, copy=False)
    time_finish = fields.Datetime(string=u'完成时间', copy=False)
    creator_id = fields.Many2one(comodel_name='res.users', string=u'创建人', ondelete='restrict', default=lambda self: self.env.user)
    state = fields.Selection(selection=ORDERSTATES, string=u'状态', default='draft', copy=False)
    produce_start = fields.Datetime(string=u'开始生产', copy=False)
    produce_finish = fields.Datetime(string=u'结束生产', copy=False)
    date_code = fields.Char(string='DateCode')
    mainorder_id = fields.Many2one(comodel_name='aas.mes.mainorder', string=u'主工单', ondelete='cascade', index=True)
    mesline_type = fields.Selection(selection=MESLINETYPE, string=u'产线类型', compute='_compute_mesline', store=True)
    mesline_name = fields.Char(string=u'名称', compute='_compute_mesline', store=True)
    mainorder_name = fields.Char(string=u'主工单', compute='_compute_mainorder', store=True)
    product_code = fields.Char(string=u'产品编码', copy=False)
    workcenter_id = fields.Many2one(comodel_name='aas.mes.workticket', string=u'当前工序', ondelete='restrict')
    workcenter_name = fields.Char(string=u'当前工序名称', copy=False)
    workcenter_start = fields.Many2one(comodel_name='aas.mes.workticket', string=u'开始工序', ondelete='restrict')
    workcenter_finish = fields.Many2one(comodel_name='aas.mes.workticket', string=u'结束工序', ondelete='restrict')
    isproducing = fields.Boolean(string=u'正在生产', default=False, copy=False, help=u'当前工单在相应的产线上正在生产')
    output_qty = fields.Float(string=u'产出数量', digits=dp.get_precision('Product Unit of Measure'), compute='_compute_output_qty', store=True)

    workticket_lines = fields.One2many(comodel_name='aas.mes.workticket', inverse_name='workorder_id', string=u'工票明细')
    product_lines = fields.One2many(comodel_name='aas.mes.workorder.product', inverse_name='workorder_id', string=u'成品明细')
    consume_lines = fields.One2many(comodel_name='aas.mes.workorder.consume', inverse_name='workorder_id', string=u'消耗明细')




    _sql_constraints = [
        ('uniq_name', 'unique (name)', u'子工单名称不可以重复！')
    ]

    @api.depends('mesline_id')
    def _compute_mesline(self):
        for record in self:
            record.mesline_type = record.mesline_id.line_type
            record.mesline_name = record.mesline_id.name

    @api.depends('name')
    def _compute_barcode(self):
        for record in self:
            record.barcode = 'AQ'+record.name

    @api.depends('mainorder_id')
    def _compute_mainorder(self):
        for record in self:
            record.mainorder_name = record.mainorder_id.name

    @api.depends('product_lines.product_qty')
    def _compute_output_qty(self):
        for record in self:
            tempqty = 0.0
            if record.product_lines and len(record.product_lines) > 0:
                tempqty = sum([pline.product_qty for pline in record.product_lines])
            record.output_qty = tempqty


    @api.one
    @api.constrains('aas_bom_id', 'input_qty')
    def action_check_mainorder(self):
        if not self.input_qty or float_compare(self.input_qty, 0.0, precision_rounding=0.000001) <= 0.0:
            raise ValidationError(u'投入数量必须是一个有效的正数！')
        if self.aas_bom_id and self.aas_bom_id.product_id.id != self.product_id.id:
            raise ValidationError(u'请仔细检查，当前物料清单和产品不匹配！')

    @api.onchange('product_id')
    def action_change_product(self):
        if not self.product_id:
            self.product_code = False
            self.product_uom, self.aas_bom_id, self.routing_id = False, False, False
        else:
            self.product_uom = self.product_id.uom_id.id
            self.product_code = self.product_id.default_code
            aasbom = self.env['aas.mes.bom'].search([('product_id', '=', self.product_id.id)], order='create_time desc', limit=1)
            if aasbom:
                self.aas_bom_id = aasbom.id
                if aasbom.routing_id:
                    self.routing_id = aasbom.routing_id.id

    @api.model
    def create(self, vals):
        self.action_before_create(vals)
        return super(AASMESWorkorder, self).create(vals)

    @api.model
    def action_before_create(self, vals):
        product = self.env['product.product'].browse(vals.get('product_id'))
        if not vals.get('product_code', False):
            vals['product_code'] = product.default_code
        if not vals.get('product_uom', False):
                vals['product_uom'] = product.uom_id.id
        if not vals.get('aas_bom_id', False):
            bomdomain = [('product_id', '=', self.product_id.id), ('state', '=', 'normal')]
            aasbom = self.env['aas.mes.bom'].search(bomdomain, order='create_time desc', limit=1)
            if aasbom:
                vals['aas_bom_id'] = aasbom.id
                if aasbom.routing_id:
                    vals['routing_id'] = aasbom.routing_id.id
        if not vals.get('routing_id', False):
            if vals.get('aas_bom_id', False):
                aasbom = self.env['aas.mes.bom'].browse(vals.get('aas_bom_id'))
                if aasbom.routing_id:
                    vals['routing_id'] = aasbom.routing_id.id

    @api.multi
    def write(self, vals):
        if vals.get('product_id', False):
            raise UserError(u'您可以删除并重新创建工单，但是不要修改产品信息！')
        return super(AASMESWorkorder, self).write(vals)

    @api.multi
    def unlink(self):
        for record in self:
            if record.state not in ['draft', 'confirm']:
                raise UserError(u'工单%s已经开始执行或已经完成，请不要删除！'% record.name)
        return super(AASMESWorkorder, self).unlink()

    @api.one
    def action_pause(self):
        self.write({'state': 'pause'})

    @api.one
    def action_confirm(self):
        """
        确认工单；工位式生产工单需要生成首道工序工票；生成物料消耗清单
        :return:
        """
        self.write({'state': 'confirm'})
        self.action_build_first_workticket()
        self.action_build_consumelist()


    @api.one
    def action_build_first_workticket(self):
        """
        工位式生产的工单生成首道工序的工票
        :return:
        """
        if not self.routing_id or self.mesline_type != 'station':
            return
        domain = [('routing_id', '=', self.routing_id.id)]
        routline = self.env['aas.mes.routing.line'].search(domain, order='sequence', limit=1)
        workticket = self.env['aas.mes.workticket'].create({
            'name': self.name+'-'+str(routline.sequence), 'sequence': routline.sequence,
            'workcenter_id': routline.id, 'workcenter_name': routline.name,
            'product_id': self.product_id.id, 'product_uom': self.product_uom.id,
            'input_qty': self.input_qty, 'state': 'waiting', 'time_wait': fields.Datetime.now(),
            'workorder_id': self.id, 'workorder_name': self.name, 'mesline_id': self.mesline_id.id,
            'mesline_name': self.mesline_name, 'routing_id': self.routing_id.id,
            'mainorder_id': False if not self.mainorder_id else self.mainorder_id.id,
            'mainorder_name': False if not self.mainorder_name else self.mainorder_name
        })
        self.write({
            'workcenter_id': workticket.id, 'workcenter_name': routline.name, 'workcenter_start': workticket.id
        })

    @api.one
    def action_build_consumelist(self):
        """
        生成物料消耗清单
        :return:
        """
        if not self.aas_bom_id:
            raise UserError(u'请先设置工单成品的BOM清单，否则无法计算原料消耗！')
        if not self.aas_bom_id.workcenter_lines or len(self.aas_bom_id.workcenter_lines) <= 0:
            raise UserError(u'请先仔细检查BOM清单是否正确设置！')
        consumelist = []
        bomlines = self.aas_bom_id.workcenter_lines
        for bomline in bomlines:
            tempmaterial = bomline.product_id
            if tempmaterial.virtual_material:
                virtualbom = self.env['aas.mes.bom'].search([('product_id', '=', tempmaterial.id), ('active', '=', True)], limit=1)
                if not virtualbom:
                    raise UserError(u'虚拟物料%s还未设置有效BOM清单，请通知相关人员设置BOM清单！'% tempmaterial.default_code)
                if not virtualbom.bom_lines or len(virtualbom.bom_lines) <= 0:
                    raise UserError(u'请先仔细检查虚拟物料%s的BOM清单是否正确设置！'% tempmaterial.default_code)
                for virtualbomline in virtualbom.bom_lines:
                    consume_unit = virtualbomline.product_qty / virtualbom.product_qty
                    consumelist.append((0, 0, {
                        'product_id': tempmaterial.id, 'material_id': virtualbomline.product_id.id,
                        'consume_unit': consume_unit, 'input_qty': self.input_qty * consume_unit,
                        'workcenter_id': False if not bomline.workcenter_id else bomline.workcenter_id.id
                    }))
            else:
                consume_unit = bomline.product_qty / self.aas_bom_id.product_qty
                consumelist.append((0, 0, {
                    'product_id': self.product_id.id, 'material_id': tempmaterial.product_id.id,
                    'consume_unit': consume_unit, 'input_qty': self.input_qty * consume_unit,
                    'workcenter_id': False if not bomline.workcenter_id else bomline.workcenter_id.id
                }))
        if not consumelist or len(consumelist) <= 0:
            raise UserError(u'请仔细检查BOM清单设置，无法生成消耗明细清单')
        self.write({'consume_lines': consumelist})





    @api.one
    def action_done(self):
        self.write({'state': 'done', 'produce_finish': fields.Datetime.now()})
        if self.mainorder_id:
            if self.env['aas.mes.workorder'].search_count([('mainorder_id', '=', self.mainorder_id.id), ('state', '!=', 'done')]) <= 0:
               self.mainorder_id.write({'state': 'done', 'produce_finish': fields.Datetime.now()})


    @api.multi
    def action_producing(self):
        """
        设置当前工单为相应产线的即将生产的工单
        :return:
        """
        self.ensure_one()
        if self.mesline_type == 'station':
            return False
        action_message = u"您确认接下来开始生产当前工单吗？"
        if self.mesline_id.workorder_id:
            action_message = u"当前产线上工单：%s正在生产，您确认切换到当前工单吗？"% self.mesline_id.workorder_id.name
        wizard = self.env['aas.mes.workorder.producing.wizard'].create({'workorder_id': self.id, 'action_message': action_message})
        view_form = self.env.ref('aas_mes.view_form_aas_mes_workorder_producing_wizard')
        return {
            'name': u"工单开工",
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'aas.mes.workorder.producing.wizard',
            'views': [(view_form.id, 'form')],
            'view_id': view_form.id,
            'target': 'new',
            'res_id': wizard.id,
            'context': self.env.context
        }

    @api.model
    def get_product_lot(self, product_id, lot_name):
        productlot = self.env['stock.production.lot'].search([('product_id', '=', product_id), ('name', '=', lot_name)], limit=1)
        if not productlot:
            productlot = self.env['stock.production.lot'].create({
                'name': lot_name, 'product_id': product_id, 'create_date': fields.Datetime.now()
            })
        return productlot


    @api.model
    def action_output(self, workorder_id, product_id, output_qty, serialnumber=None):
        """
        工单产出
        :param workorder_id:
        :param product_id:
        :param output_qty:
        :param serialnumber:
        :return:
        """
        workorder = self.env['aas.mes.workorder'].browse(workorder_id)
        if not workorder.aas_bom_id:
            raise UserError(u'工单未设置BOM清单，请仔细检查！')
        if product_id != workorder.product_id.id:
            tempbomlines = self.env['aas.mes.bom.line'].search([('bom_id', '=', workorder.aas_bom_id.id), ('product_id', '=', product_id)])
            if not tempbomlines or len(tempbomlines) <= 0:
                raise UserError(u'成品产出异常，可能不是当前工单产物！')
        output_date = self.env['aas.mes.workorder.product'].get_output_date()
        # todo 成品批次生成算法
        product_lot = False
        outputdomain = [('workorder_id', '=', workorder_id), ('output_date', '=', output_date)]
        outputdomain.extend([('product_id', '=', product_id), ('product_lot', '=', product_lot)])
        outputdomain.append(('mesline_id', '=', workorder.mesline_id.id))
        if workorder.mesline_id.schedule_id:
            outputdomain.append(('schedule_id', '=', workorder.mesline_id.schedule_id.id))
        outputrecord = self.env['aas.mes.workorder.product'].search(outputdomain, limit=1)
        if not outputrecord:
            outputvals = {'workorder_id': workorder_id, 'product_id': product_id, 'product_lot': product_lot}
            outputvals.update({'output_date': output_date, 'mesline_id': workorder.mesline_id.id})
            if workorder.mesline_id.schedule_id:
                outputvals['schedule_id'] = workorder.mesline_id.schedule_id.id
            outputrecord = self.env['aas.mes.workorder.product'].create(outputvals)
        outputrecord.write({'waiting_qty': outputrecord.waiting_qty + output_qty})
        if serialnumber:
            serialrecord = self.env['aas.mes.serialnumber'].search([('name', '=', serialnumber)], limit=1)
            if not serialrecord:
                return True
            serialrecord.write({
                'output_time': fields.Datetime.now(), 'outputuser_id': self.env.user.id,
                'workorder_id': workorder_id, 'outputrecord_id': outputrecord.id
            })
        return True

    @api.model
    def action_consume(self, workorder_id, product_id):
        """
        工单消耗
        :param workorder_id:
        :param product_id:
        :return:
        """
        values = {'success': True, 'message': ''}
        outputdomain = [('workorder_id', '=', workorder_id), ('product_id', '=', product_id)]
        outputdomain.append(('waiting_qty', '>', 0.0))
        outputlist = self.env['aas.mes.workorder.product'].search(outputdomain)
        if outputlist and len(outputlist) > 0:
            values.update(outputlist.action_consume())
        return values


# 工单产出
class AASMESWorkorderProduct(models.Model):
    _name = 'aas.mes.workorder.product'
    _description = 'AAS MES Work Order Product'
    _rec_name = 'product_id'

    @api.model
    def get_output_date(self):
        return fields.Datetime.to_timezone_string(fields.Datetime.now(), 'Asia/Shanghai')[0:10]

    workorder_id = fields.Many2one(comodel_name='aas.mes.workorder', string=u'工单', ondelete='cascade', index=True)
    mesline_id = fields.Many2one(comodel_name='aas.mes.line', string=u'产线', ondelete='restrict', index=True)
    schedule_id = fields.Many2one(comodel_name='aas.mes.schedule', string=u'班次', ondelete='restrict', index=True)
    product_id = fields.Many2one(comodel_name='product.product', string=u'产品', ondelete='restrict', index=True)
    product_lot = fields.Many2one(comodel_name='stock.production.lot', string=u'批次', ondelete='restrict', index=True)
    product_qty = fields.Float(string=u'已产出数量', digits=dp.get_precision('Product Unit of Measure'), default=0.0)
    waiting_qty = fields.Float(string=u'待消耗数量', digits=dp.get_precision('Product Unit of Measure'), default=0.0)
    output_date = fields.Char(string=u'产出日期', copy=False, default=get_output_date)


    @api.multi
    def action_consume(self):
        """
        产出物料消耗
        :return:
        """
        values = {'success': True, 'message': ''}
        for record in self:
            if float_is_zero(record.waiting_qty, precision_rounding=0.000001):
                return values

            waiting_qty, mesline, workorder = record.waiting_qty, record.mesline_id, record.workorder_id
            tempdomain = [('workorder_id', '=', workorder.id), ('product_id', '=', record.product_id.id)]
            workorder_consume_list = self.env['aas.mes.workorder.consume'].search(tempdomain)
            if not workorder_consume_list or len(workorder_consume_list) <= 0:
                return values
            consumelist, movedict, feedlist = [], {}, []
            tempcompany = self.env.user.company_id
            # 生产库位
            destlocation = self.env.ref('stock.location_production')
            for consumerecord in workorder_consume_list:
                consume_qty = waiting_qty * consumerecord.consume_unit
                consumelist.append((1, consumerecord.id, {'consume_qty': consumerecord.consume_qty+consume_qty}))
                material, workstation = consumerecord.material_id, False
                feeddomain = [('mesline_id', '=', mesline.id)]
                feeddomain.append(('material_id', '=', material.id))
                if consumerecord.workcenter_id and consumerecord.workcenter_id.workstation_id:
                    workstation = consumerecord.workcenter_id.workstation_id
                    feeddomain.append(('workstation_id', '=', workstation.id))
                # 检查投料明细
                feedmateriallist = self.env['aas.mes.feedmaterial'].search(feeddomain)
                if not feedmateriallist or len(feedmateriallist) <= 0:
                    message = u'原料%s还没有投料记录！'% material.default_code
                    if workstation:
                        message = (u'工位%s,'% workstation.name) + message
                    values.update({'success': False, 'message': message})
                    return values
                feed_qty, quantlist = 0.0, []
                for feedmaterial in feedmateriallist:
                    # 刷新线边库库存
                    quants = feedmaterial.action_checking_quants()
                    if quants and len(quants) > 0:
                        quantlist.extend([tempquant for tempquant in quants])
                    feed_qty += feedmaterial.material_qty
                    feedlist.append(feedmaterial)
                if float_compare(feed_qty, consume_qty, precision_rounding=0.000001) < 0.0:
                    message = u'原料%s投入量不足！'% material.default_code
                    if workstation:
                        message = (u'工位%s,'% workstation.name) + message
                    values.update({'success': False, 'message': message})
                    return values
                # 扣减库存
                for tempquant in quantlist:
                    if float_compare(consume_qty, 0.0, precision_rounding=0.000001) <= 0.0:
                        break
                    if float_compare(consume_qty, tempquant.qty, precision_rounding=0.000001) >= 0.0:
                        tempqty = tempquant.qty
                    else:
                        tempqty = consume_qty
                    tkey = 'P'+str(tempquant.product_id.id)+'-'+str(tempquant.lot_id.id)+'-'+str(tempquant.location_id.id)
                    if tkey not in movedict:
                        movedict[tkey] = {
                            'name': record.workorder_id.name, 'product_id': tempquant.product_id.id,
                            'product_uom': tempquant.product_uom_id.id, 'create_date': fields.Datetime.now(),
                            'restrict_lot_id': tempquant.lot_id.id, 'product_uom_qty': tempqty,
                            'location_id': tempquant.location_id.id, 'location_dest_id': destlocation.id, 'company_id': tempcompany.id
                        }
                    else:
                        movedict[tkey]['product_uom_qty'] += tempqty
                    consume_qty -= tempqty
            productlines = [(1, record.id, {'product_qty': record.product_qty+waiting_qty, 'waiting_qty': 0.0})]
            # 库存移动
            movelist = self.env['stock.move']
            for mkey, mval in movedict.items():
                movelist |= self.env['stock.move'].create(mval)
            movelist.action_done()
            # 更新产出和消耗信息
            workorder.write({'product_lines': productlines, 'consume_lines': consumelist})
            # 更新上料记录的当前库存
            for feedmaterial in feedlist:
                feedmaterial.action_refresh_stock()
        return values



class AASMESWorkorderConsume(models.Model):
    _name = 'aas.mes.workorder.consume'
    _description = 'AAS MES Work Order Consume'

    workorder_id = fields.Many2one(comodel_name='aas.mes.workorder', string=u'工单', ondelete='cascade')
    workcenter_id = fields.Many2one(comodel_name='aas.mes.routing.line', string=u'工序', ondelete='restrict')
    product_id = fields.Many2one(comodel_name='product.product', string=u'成品', ondelete='restrict')
    material_id = fields.Many2one(comodel_name='product.product', string=u'原料', ondelete='restrict')
    consume_unit = fields.Float(string=u'单位消耗', digits=dp.get_precision('Product Unit of Measure'), default=0.0)
    input_qty = fields.Float(string=u'投入数量', digits=dp.get_precision('Product Unit of Measure'), default=0.0)
    consume_qty = fields.Float(string=u'已消耗量', digits=dp.get_precision('Product Unit of Measure'), default=0.0)
    leave_qty = fields.Float(string=u'剩余数量', digits=dp.get_precision('Product Unit of Measure'), compute='_compute_leave_qty', store=True)

    @api.depends('input_qty', 'consume_qty')
    def _compute_leave_qty(self):
        for record in self:
            record.leave_qty = record.input_qty - record.consume_qty



################################## 向导 #################################

class AASMESWorkorderProducingWizard(models.TransientModel):
    _name = 'aas.mes.workorder.producing.wizard'
    _description = 'AAS MES Workorder Producing Wizard'

    workorder_id = fields.Many2one(comodel_name='aas.mes.workorder', string=u'工单', ondelete='cascade')
    action_message = fields.Char(string=u'提示信息', copy=False)

    @api.one
    def action_done(self):
        workorder = self.workorder_id
        mesline = workorder.mesline_id
        if mesline.workorder_id:
            mesline.workorder_id.write({'isproducing': False})
        mesline.write({'workorder_id': workorder.id})
        workorder.write({'isproducing': True})