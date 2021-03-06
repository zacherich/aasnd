# -*-  coding: utf-8 -*-

"""
@version: 1.0
@author: luforn
@license: LGPL V3
@time: 2017-11-1 17:04
"""

from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_compare, float_is_zero
from odoo.exceptions import UserError, ValidationError

import math
import logging
from datetime import timedelta

_logger = logging.getLogger(__name__)

WIREBOMSTATE = [('draft', u'草稿'), ('normal', u'正常'), ('override', u'失效')]

# 线材BOM
class AASMESWirebom(models.Model):
    _name = 'aas.mes.wirebom'
    _description = 'AAS MES Wire BOM'
    _rec_name = 'product_id'

    product_id = fields.Many2one(comodel_name='product.product', string=u'产品', ondelete='restrict')
    product_uom = fields.Many2one(comodel_name='product.uom', string=u'单位', ondelete='restrict')
    product_qty = fields.Float(string=u'数量', digits=dp.get_precision('Product Unit of Measure'), default=1.0)
    active = fields.Boolean(string=u'是否有效', default=True, copy=False)
    note = fields.Text(string=u'描述')
    version = fields.Char(string=u'版本', copy=False)
    state = fields.Selection(selection=WIREBOMSTATE, string=u'状态', default='draft', copy=False)
    operation_time = fields.Datetime(string=u'制单时间', default=fields.Datetime.now, copy=False)
    operator_id = fields.Many2one(comodel_name='res.users', string=u'制单人', ondelete='restrict')
    origin_id = fields.Many2one(comodel_name='aas.mes.wirebom', string=u'源BOM', ondelete='restrict')
    company_id = fields.Many2one('res.company', string=u'公司', default=lambda self: self.env.user.company_id)
    material_lines = fields.One2many(comodel_name='aas.mes.wirebom.line', inverse_name='wirebom_id', string=u'原料明细')

    @api.onchange('product_id')
    def action_change_product(self):
        if self.product_id:
            self.product_uom = self.product_id.uom_id.id
        else:
            self.product_uom = False

    @api.model
    def create(self, vals):
        product = self.env['product.product'].browse(vals['product_id'])
        vals['product_uom'] = product.uom_id.id
        return super(AASMESWirebom, self).create(vals)


    @api.one
    def action_confirm(self):
        self.write({'state': 'normal'})



# 线材BOM明细
class AASMESWirebomLine(models.Model):
    _name = 'aas.mes.wirebom.line'
    _description = 'AAS MES Wire BOM Line'

    wirebom_id = fields.Many2one(comodel_name='aas.mes.wirebom', string=u'线材BOM', ondelete='cascade')
    material_id = product_id = fields.Many2one(comodel_name='product.product', string=u'原料', ondelete='restrict')
    material_uom = fields.Many2one(comodel_name='product.uom', string=u'单位', ondelete='restrict')
    material_qty = fields.Float(string=u'数量', digits=dp.get_precision('Product Unit of Measure'), default=1.0)

    _sql_constraints = [
        ('uniq_material', 'unique (wirebom_id, material_id)', u'请不要重复添加同一个物料！')
    ]

    @api.onchange('material_id')
    def action_change_material(self):
        if self.material_id:
            self.material_uom = self.material_id.uom_id.id
        else:
            self.material_uom = False

    @api.model
    def create(self, vals):
        material = self.env['product.product'].browse(vals['material_id'])
        vals['material_uom'] = material.uom_id.id
        return super(AASMESWirebomLine, self).create(vals)

    @api.one
    @api.constrains('material_id')
    def action_check_material(self):
        if not self.material_id:
            return
        materialbom = self.env['aas.mes.bom'].search([('product_id', '=', self.material_id.id), ('active', '=', True)], limit=1)
        if not materialbom:
            raise ValidationError(u'物料%s还未设置BOM清单，请先设置好BOM清单再继续线材BOM设置！'% self.material_id.default_code)



WIREORDERSTATES = [('draft', u'草稿'), ('wait', u'等待'), ('producing', u'生产'), ('done', u'完成')]

# 线材工单
class AASMESWireOrder(models.Model):
    _name = 'aas.mes.wireorder'
    _description = 'AAS MES Wire Order'
    _order = 'id desc'

    name = fields.Char(string=u'名称', copy=False)
    product_id = fields.Many2one(comodel_name='product.product', string=u'产品', ondelete='restrict')
    product_uom = fields.Many2one(comodel_name='product.uom', string=u'单位', ondelete='restrict')
    product_code = fields.Char(string=u'编码')
    product_qty = fields.Float(string=u'数量', digits=dp.get_precision('Product Unit of Measure'), default=1.0)
    mesline_id = fields.Many2one(comodel_name='aas.mes.line', string=u'产线', ondelete='restrict', index=True)
    mesline_name = fields.Char(string=u'产线名称')
    state = fields.Selection(selection=WIREORDERSTATES, string=u'状态', default='draft', copy=False)
    wirebom_id = fields.Many2one(comodel_name='aas.mes.wirebom', string=u'线材BOM', ondelete='restrict')


    plan_date = fields.Date(string=u'投产日期')
    plan_schedule = fields.Many2one(comodel_name='aas.mes.schedule', string=u'投产班次')
    schedule_start = fields.Datetime(string=u'班次开始', compute='_compute_plan_schedule_time', store=True)
    schedule_finish = fields.Datetime(string=u'班次结束', compute='_compute_plan_schedule_time', store=True)
    plan_start = fields.Datetime(string=u'计划开工时间', copy=False)
    plan_finish = fields.Datetime(string=u'计划完工时间', copy=False)
    produce_start = fields.Datetime(string=u'开始生产', copy=False)
    produce_finish = fields.Datetime(string=u'结束生产', copy=False)


    operator_id = fields.Many2one('res.users', string=u'制单人', default=lambda self:self.env.user)
    operation_time = fields.Datetime(string=u'制单时间', default=fields.Datetime.now, copy=False)
    pusher_id = fields.Many2one(comodel_name='res.users', string=u'投产人', ondelete='restrict')
    push_time = fields.Datetime(string=u'投产时间', copy=False)
    push_date = fields.Char(string=u'投产日期')
    workorder_lines = fields.One2many(comodel_name='aas.mes.workorder', inverse_name='wireorder_id', string=u'工单明细')

    closer_id = fields.Many2one(comodel_name='res.users', string=u'关单人', ondelete='restrict')


    @api.onchange('product_id')
    def action_change_product(self):
        product = self.product_id
        if product:
            self.product_uom = product.uom_id.id
            wirebomdomain = [('product_id', '=', product.id), ('active', '=', True)]
            wirebom = self.env['aas.mes.wirebom'].search(wirebomdomain, limit=1)
            if wirebom:
                self.wirebom_id = wirebom.id
        else:
            self.product_uom, self.wirebom_id = False, False


    @api.one
    @api.constrains('plan_date')
    def action_check_plandate(self):
        plandate, mesline = self.plan_date, self.mesline_id
        workdate = False if not mesline or not mesline.workdate else mesline.workdate
        if plandate and workdate and plandate < workdate:
            raise ValidationError(u'投产日期不能早于%s'% workdate)

    @api.one
    @api.constrains('plan_start', 'plan_finish')
    def action_check_plan_production_times(self):
        if not self.schedule_start or not self.schedule_finish:
            raise ValidationError(u'请检查是否设置了投产日期和班次信息！')
        if self.plan_start and self.plan_finish:
            if self.plan_finish < self.plan_start:
                raise ValidationError(u'计划结束时间必须大于计划开始时间！')
            if self.plan_start < self.schedule_start or self.plan_finish > self.schedule_finish:
                tempstart = fields.Datetime.to_china_string(self.schedule_start)
                tempfinish = fields.Datetime.to_china_string(self.schedule_finish)
                raise ValidationError(u'计划开工和完工时间必须在%s和%s之间！'% (tempstart, tempfinish))


    @api.onchange('mesline_id')
    def action_change_mesline(self):
        self.plan_schedule = False


    @api.onchange('plan_schedule')
    def action_change_plan_schedule(self):
        self.plan_start, self.plan_finish = False, False

    @api.depends('plan_date', 'plan_schedule')
    def _compute_plan_schedule_time(self):
        for record in self:
            if not record.plan_date or not record.plan_schedule:
                record.schedule_start, record.schedule_finish = False, False
            else:
                scheduletimes = self.action_compute_workorder_schedule_time(record)
                record.schedule_start, record.schedule_finish = scheduletimes[0], scheduletimes[1]

    @api.model
    def action_compute_workorder_schedule_time(self, wireorder):
        mesline, schedule, scheduletimes = wireorder.mesline_id, wireorder.plan_schedule, []
        tempstatus = [mesline.workdate == wireorder.plan_date, schedule.id == mesline.schedule_id.id]
        if all(tempstatus):
            scheduletimes = [schedule.actual_start, schedule.actual_finish]
            return scheduletimes
        odootime = fields.Datetime.now()
        currenttimestr = wireorder.plan_date + odootime[10:]
        currenttime = fields.Datetime.to_china_time(currenttimestr)
        start_hour = int(math.floor(schedule.work_start))
        start_minutes = int(math.floor((schedule.work_start - start_hour) * 60))
        starttime = currenttime.replace(hour=start_hour, minute=start_minutes, second=0)
        finish_hour = int(math.floor(schedule.work_finish))
        finish_minutes = int(math.floor((schedule.work_finish - finish_hour) * 60))
        if schedule.work_finish >= schedule.work_start:
            finishtime = currenttime.replace(hour=finish_hour, minute=finish_minutes, second=0)
        else:
            temptime = currenttime + timedelta(days=1)
            finishtime = temptime.replace(hour=finish_hour, minute=finish_minutes, second=0)
        scheduletimes.append(fields.Datetime.to_utc_string(starttime, 'Asia/Shanghai'))
        scheduletimes.append(fields.Datetime.to_utc_string(finishtime, 'Asia/Shanghai'))
        return scheduletimes



    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('aas.mes.wireorder')
        product = self.env['product.product'].browse(vals['product_id'])
        vals.update({'product_uom': product.uom_id.id, 'product_code': product.default_code})
        if vals.get('mesline_id', False):
            mesline = self.env['aas.mes.line'].browse(vals['mesline_id'])
            vals['mesline_name'] = mesline.name
        return super(AASMESWireOrder, self).create(vals)


    @api.multi
    def write(self, vals):
        productid = vals.get('product_id', False)
        if productid:
            product = self.env['product.product'].browse(productid)
            vals.update({'product_uom': product.uom_id.id, 'product_code': product.default_code})
        meslineid = vals.get('mesline_id', False)
        if meslineid:
            mesline = self.env['aas.mes.line'].browse(vals['mesline_id'])
            vals['mesline_name'] = mesline.name
        return super(AASMESWireOrder, self).write(vals)

    @api.multi
    def unlink(self):
        for record in self:
            if record.state in ['producing', 'done']:
                raise UserError(u'工单%s已经开始执行，不可以删除！'% record.name)
        return super(AASMESWireOrder, self).unlink()


    @api.model
    def action_print_label(self, printer_id, ids=[], domain=[]):
        values = {'success': True, 'message': ''}
        printer = self.env['aas.label.printer'].browse(printer_id)
        if not printer.field_lines or len(printer.field_lines) <= 0:
            values.update({'success': False, 'message': u'请联系管理员标签打印未指定具体打印内容！'})
            return values
        values.update({'printer': printer.name, 'serverurl': printer.serverurl})
        field_list = [fline.field_name for fline in printer.field_lines]
        if ids and len(ids) > 0:
            labeldomain = [('id', 'in', ids)]
        else:
            labeldomain = domain
        if not labeldomain or len(labeldomain) <= 0:
            return {'success': False, 'message': u'您可能已经选择了所有工单或未选择任何工单，请选中需要打印的工单！'}
        records = self.search_read(domain=labeldomain, fields=field_list)
        if not records or len(records) <= 0:
            values.update({'success': False, 'message': u'未搜索到需要打印的工单！'})
            return values
        records = printer.action_correct_records(records)
        values['records'] = records
        return values


    @api.one
    def action_produce(self):
        """
        投产；拆分子工单
        :return:
        """
        if self.state != 'draft' or (self.workorder_lines and len(self.workorder_lines) > 0):
            return
        wirebom = self.wirebom_id
        tempindex, tempname = 1, self.name[2:]
        for tempmaterial in wirebom.material_lines:
            material = tempmaterial.material_id
            input_qty = (tempmaterial.material_qty / wirebom.product_qty) * self.product_qty
            aasbom = self.env['aas.mes.bom'].search([('product_id', '=', material.id), ('active', '=', True)], limit=1)
            workorder = self.env['aas.mes.workorder'].create({
                'name': tempname+'-'+str(tempindex), 'product_id': material.id,
                'product_uom': material.uom_id.id, 'aas_bom_id': aasbom.id,
                'mesline_id': self.mesline_id.id, 'wireorder_id': self.id, 'input_qty': input_qty,
                'plan_date': self.plan_date, 'plan_schedule': self.plan_schedule.id,
                'plan_start': self.plan_start, 'plan_finish': self.plan_finish, 'output_manner': 'container'
            })
            workorder.action_confirm()
            tempindex += 1
        self.write({
            'pusher_id': self.env.user.id, 'state': 'wait',
            'push_time': fields.Datetime.now(), 'push_date': fields.Datetime.to_china_today()
        })



    @api.model
    def action_wirecutting_output(self, workorder, output_qty, container, workstation, employee, equipment):
        """
        线材工单产出
        :param workorder:
        :param output_qty:
        :param container:
        :param employee:
        :param equipment:
        :return:
        """
        values = {'success': True, 'message': ''}
        product = workorder.product_id
        if not workorder.output_manner or (workorder.output_manner != 'container'):
            workorder.write({'output_manner': 'container'})
        tempvals = self.env['aas.production.product'].action_production_output(workorder, product, output_qty,
                                                                            equipment=equipment, employee=employee,
                                                                        workstation=workstation, container=container,
                                                                        finaloutput=True, tracing=True, cutting=True)
        if not tempvals.get('success', False):
            values.update(tempvals)
            return values
        wireorder = workorder.wireorder_id
        if wireorder.state not in ['producing', 'done']:
            wireorder.write({'state': 'producing', 'produce_start': fields.Datetime.now()})
        if all([temporder.state == 'done' for temporder in wireorder.workorder_lines]):
            wireorder.write({'state': 'done', 'produce_finish': fields.Datetime.now()})
        return values



    @api.model
    def action_wirecutting_scrap(self, workorder_id, scrap_qty, workstation_id, employee_id, equipment_id):
        """
        线材工单报废
        :param workorder_id:
        :param scrap_qty:
        :param container_id:
        :param employee_id:
        :param equipment_id:
        :return:
        """
        values = {'success': True, 'message': ''}
        workorder = self.env['aas.mes.workorder'].browse(workorder_id)
        cresult = workorder.action_validate_consume(workorder.id, workorder.product_id.id, scrap_qty)
        if not cresult['success']:
            values.update(cresult)
            return values
        scresult = self.action_workorder_scrapconsume(workorder, scrap_qty, workstation_id)
        if not scresult['success']:
            values.update(scresult)
            return values
        self.env['aas.mes.scrap'].create({
            'product_id': workorder.product_id.id, 'product_uom': workorder.product_id.uom_id.id,
            'product_qty': scrap_qty, 'mesline_id': workorder.mesline_id.id, 'workorder_id': workorder.id,
            'workstation_id': workstation_id, 'equipment_id': equipment_id, 'operator_id': employee_id
        })
        workorder.write({'scrap_qty': workorder.scrap_qty + scrap_qty})
        return values



    def action_workorder_scrapconsume(self, workorder, product_qty, workstation_id):
        """
        线材工单报废消耗
        :param workorder:
        :param product_qty:
        :param workstation_id:
        :return:
        """
        values = {'success': True, 'message': ''}
        mesline, workstation = workorder.mesline_id, self.env['aas.mes.workstation'].browse(workstation_id)
        consumeresult = self.action_build_workorder_consumerecords(workorder, product_qty, mesline, workstation)
        if not consumeresult['success']:
            values.update(consumeresult)
            return values
        consumerecords = consumeresult['records']
        if not consumerecords or len(consumerecords) <= 0:
            return values
        companyid = self.env.user.company_id.id
        destlocationid = self.env.ref('stock.location_production').id
        movelist = self.env['stock.move']
        for crecord in consumerecords:
            for cmove in crecord['movelines']:
                movelist |= self.env['stock.move'].create({
                    'name': workorder.name, 'product_id': crecord['material_id'], 'company_id': companyid,
                    'product_uom': crecord['material_uom'], 'create_date': fields.Datetime.now(),
                    'location_id': cmove['location_id'], 'location_dest_id': destlocationid,
                    'restrict_lot_id': cmove['material_lot'], 'product_uom_qty': cmove['product_qty']
                })
        movelist.action_done()
        return values

    @api.model
    def action_build_workorder_consumerecords(self, workorder, product_qty, mesline, workstation):
        """
        编译消耗清单
        :param workorder:
        :param product_qty:
        :param mesline:
        :param workstation:
        :return:
        """
        values = {'success': True, 'message': '', 'records': []}
        product = workorder.product_id
        consumedomain = [('workorder_id', '=', workorder.id), ('product_id', '=', product.id)]
        workorder_consume_list = self.env['aas.mes.workorder.consume'].search(consumedomain)
        if not workorder_consume_list or len(workorder_consume_list) <= 0:
            return values
        materiallines = []
        for tempconsume in workorder_consume_list:
            material, want_qty = tempconsume.material_id, product_qty * tempconsume.consume_unit
            feeddomain = [('mesline_id', '=', mesline.id), ('material_id', '=', material.id)]
            feeddomain.append(('workstation_id', '=', workstation.id))
            feedmateriallist = self.env['aas.mes.feedmaterial'].search(feeddomain)
            if not feedmateriallist or len(feedmateriallist) < 0:
                values.update({
                    'success': False,
                    'message': u'工位%s的原料%s还未上料，请先上料再进行其他操作！'% (workstation.name, material.default_code)
                })
                return values
            feed_qty, quantdict = 0.0, {}
            for feedmaterial in feedmateriallist:
                # 刷新线边库库存
                quants = feedmaterial.action_checking_quants()
                if quants and len(quants) > 0:
                    for tempquant in quants:
                        qkey = 'Q-'+str(tempquant.lot_id.id)+'-'+str(tempquant.location_id.id)
                        if qkey in quantdict:
                            quantdict['qkey']['product_qty'] += tempquant.qty
                        else:
                            quantdict['qkey'] = {
                                'location_id': tempquant.location_id.id, 'product_qty': tempquant.qty,
                                'material_lot': tempquant.lot_id.id, 'material_lot_name': tempquant.lot_id.name
                            }
                feed_qty += feedmaterial.material_qty
            if float_compare(feed_qty, want_qty, precision_rounding=0.000001) < 0.0:
                values.update({
                    'success': False,
                    'message': u'工位%s的原料%s投料不足，请先继续投料再进行其他操作！'% (workstation.name, material.default_code)
                })
                return values
            # 库存分配
            tempmovedict = {}
            for qkey, qval in quantdict.items():
                if float_compare(want_qty, 0.0, precision_rounding=0.000001) <= 0.0:
                    break
                lkey = 'L-'+str(qval['material_lot'])+'-'+str(qval['location_id'])
                if float_compare(want_qty, qval['product_qty'], precision_rounding=0.000001) >= 0.0:
                    tempqty = qval['product_qty']
                else:
                    tempqty = want_qty
                if lkey in tempmovedict:
                    tempmovedict[lkey]['product_qty'] += tempqty
                else:
                    tempmovedict[lkey] = {
                        'location_id': qval['location_id'], 'product_qty': tempqty,
                        'material_lot': qval['material_lot'], 'material_lot_name': qval['material_lot_name']
                    }
                want_qty -= tempqty
            materialvals = {'material_id': material.id, 'material_uom': material.uom_id.id, 'movelines': tempmovedict.values()}
            materiallines.append(materialvals)
        values['records'] = materiallines
        return values


    @api.multi
    def action_close(self):
        """
        关闭线材工单
        :return:
        """
        self.ensure_one()
        wizard = self.env['aas.mes.wireorder.close.wizard'].create({
            'wireorder_id': self.id,
            'action_message': u'当前工单还未生成完成，您确认要关闭此工单吗？'
        })
        view_form = self.env.ref('aas_mes.view_form_aas_mes_wireorder_close_wizard')
        return {
            'name': u"关闭工单",
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'aas.mes.wireorder.close.wizard',
            'views': [(view_form.id, 'form')],
            'view_id': view_form.id,
            'target': 'new',
            'res_id': wizard.id,
            'context': self.env.context
        }


    @api.multi
    def action_auto_done(self):
        """系统切换班次自动关闭线材工单
        :return:
        """
        for record in self:
            tempdomain = [('wireorder_id', '=', record.id), ('state', 'not in', ['draft', 'done'])]
            workorderlist = self.env['aas.mes.workorder'].search(tempdomain)
            if not workorderlist or len(workorderlist) <= 0:
                continue
            workorderlist.action_auto_done()
        self.write({'produce_finish': fields.Datetime.now(), 'state': 'done'})





class AASMESWireorderCloseWizard(models.TransientModel):
    _name = 'aas.mes.wireorder.close.wizard'
    _description = 'AAS MES Workorder Close Wizard'

    wireorder_id = fields.Many2one(comodel_name='aas.mes.wireorder', string=u'工单', ondelete='cascade')
    action_message = fields.Char(string=u'提示信息', copy=False)

    @api.one
    def action_done(self):
        wireorder = self.wireorder_id
        if wireorder.workorder_lines and len(wireorder.workorder_lines) > 0:
            for workorder in wireorder.workorder_lines:
                if workorder.state == 'done':
                    continue
                workorder.action_done()
                workorder.write({'time_finish': fields.Datetime.now(), 'closer_id': self.env.user.id})
        wireorder.write({'state': 'done', 'produce_finish': fields.Datetime.now(), 'closer_id': self.env.user.id})


