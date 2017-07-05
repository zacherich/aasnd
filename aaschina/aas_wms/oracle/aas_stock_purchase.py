# -*-  coding: utf-8 -*-

"""
@version: 1.0
@author: luforn
@license: LGPL V3
@time: 2017-7-5 11:30
"""

from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_compare, float_is_zero
from odoo.exceptions import UserError, ValidationError

import logging

_logger = logging.getLogger(__name__)


class AASEBSPurchaseOrder(models.Model):
    _auto = False
    _log_access = False
    _name = 'aas.ebs.purchase.order'
    _description = 'AAS EBS Purchase Order'
    _order = 'id desc'

    name = fields.Char(string=u'订单号')
    partner_id = fields.Integer(string=u'供应商')
    created_by = fields.Integer(string='created_by')
    creation_date = fields.Datetime(string=u'创建日期')
    last_update_date = fields.Datetime(string=u'修改日期')
    last_updated_by = fields.Integer(string='last_updated_by')



class AASEBSPurchaseOrderLine(models.Model):
    _auto = False
    _log_access = False
    _name = 'aas.ebs.purchase.order.line'
    _description = 'AAS EBS Purchase Order Line'


    order_id = fields.Many2one(comodel_name='aas.ebs.purchase.order', string=u'采购订单')
    product_id = fields.Integer(string=u'产品')
    product_qty = fields.Float(string=u'数量')
    created_by = fields.Integer(string='created_by')
    creation_date = fields.Datetime(string=u'创建日期')
    last_update_date = fields.Datetime(string=u'修改日期')
    last_updated_by = fields.Integer(string='last_updated_by')



class AASStockPurchaseOrder(models.Model):
    _name = 'aas.stock.purchase.order'
    _description = 'AAS Stock Purchase Order'
    _order = 'id desc'

    name = fields.Char(string=u'订单号')
    partner_id = fields.Many2one(comodel_name='res.partner', string=u'供应商')
    created_by = fields.Integer(string='created_by')
    creation_date = fields.Datetime(string=u'创建日期')
    last_update_date = fields.Datetime(string=u'修改日期')
    last_updated_by = fields.Integer(string='last_updated_by')
    order_lines = fields.One2many(comodel_name='aas.stock.purchase.order.line', inverse_name='order_id', string=u'采购明细')
    ebs_order_id = fields.Integer(string=u'EBS采购订单ID')
    ebsorder = fields.Boolean(string=u'Oracle订单', default=False, copy=False)

    @api.model
    def action_import_order(self, order_number):
        """
        导入采购订单
        :param order_number:
        :return:
        """
        values = {'success': True, 'message': ''}
        if self.env['aas.stock.purchase.order'].search_count([('name', '=', order_number)]) > 0:
            values.update({'success': False, 'message': u'订单%s已存在，请不要重复导入！'% order_number})
            return values
        ebsorder = self.env['aas.ebs.purchase.order'].search([('name', '=', order_number)], limit=1)
        if not ebsorder:
            values.update({'success': False, 'message': u'订单%s不存在，请不要导入！'% order_number})
            return values
        ordervals = {
            'name': ebsorder.name, 'partner_id': ebsorder.partner_id, 'ebs_order_id': ebsorder.id,'created_by': ebsorder.created_by,
            'creation_date': ebsorder.creation_date, 'last_updated_by': ebsorder.last_updated_by, 'last_update_date': ebsorder.last_update_date
        }
        ebsorderlines = self.env['aas.ebs.purchase.order.line'].search([('order_id', '=', ebsorder.id)])
        if ebsorderlines and len(ebsorderlines) > 0:
            productdict = {}
            for eline in ebsorderlines:
                pkey = 'P'+str(eline.product_id)
                if pkey in productdict:
                    productdict[pkey]['product_qty'] += eline.product_qty
                else:
                    tproduct = self.env['product.product'].browse(eline.product_id)
                    if not tproduct:
                        values.update({'success': False, 'message': u'请仔细检查，可能有Oracle产品未同步到当前系统！'})
                        return values
                    productdict[pkey] = {
                        'product_id': eline.product_id, 'product_uom': tproduct.uom_id.id, 'product_qty': eline.product_qty,
                        'order_name': ebsorder.name, 'partner_id': ebsorder.partner_id,'creation_date': ebsorder.creation_date,
                        'last_update_date': ebsorder.last_update_date, 'created_by': ebsorder.created_by, 'last_updated_by': ebsorder.last_updated_by
                    }
            ordervals['order_lines'] = [(0, 0, pval) for pkey, pval in productdict.items()]
        ordervals['ebsorder'] = True
        self.env['aas.stock.purchase.order'].create(ordervals)
        return values


    @api.multi
    def action_synchronize(self):
        """
        同步采购订单
        :return:
        """
        self.ensure_one()
        if self.ebs_order_id:
            ebsorder = self.env['aas.ebs.purchase.order'].browse(self.ebs_order_id)
        else:
            ebsorder = self.env['aas.ebs.purchase.order'].search([('name', '=', self.name)], limit=1)
        if not ebsorder:
            raise UserError(u"Oracle中未搜索到此采购订单！")
        ebs_purchase_dict, aas_purchase_dict = {}, {}
        ebs_order_lines = self.env['aas.ebs.purchase.order.line'].search([('order_id', '=', ebsorder.id)])
        if ebs_order_lines and len(ebs_order_lines) > 0 :
            for ebsline in ebs_order_lines:
                product_key = 'P'+str(ebsline.product_id)
                if product_key in ebs_purchase_dict:
                    ebs_purchase_dict[product_key]['product_qty'] += ebsline.product_qty
                else:
                    tproduct = self.env['product.product'].browse(ebsline.product_id)
                    if not tproduct:
                        raise UserError(u'请仔细检查，可能有Oracle产品未同步到当前系统！')
                    ebs_purchase_dict[product_key] = {
                        'product_id': ebsline.product_id,
                        'product_qty': ebsline.product_qty,
                        'product_uom': tproduct.uom_id.id,
                        'creation_date': ebsline.creation_date,
                        'last_update_date': ebsline.last_update_date,
                        'created_by': ebsline.created_by,
                        'last_updated_by': ebsline.last_updated_by,
                        'order_name': ebsline.order_name,
                        'partner_id': ebsline.partner_id.id
                    }
        if self.order_lines and len(self.order_lines) > 0:
            for aasline in self.order_lines:
                product_key = 'P'+str(aasline.product_id.id)
                aas_purchase_dict[product_key] = {
                    'id': aasline.id,
                    'product_id': aasline.product_id.id,
                    'product_code': aasline.product_id.default_code,
                    'product_qty': aasline.product_qty,
                    'receipt_qty': aasline.receipt_qty,
                    'rejected_qty': aasline.rejected_qty
                }
        aas_line_list = []
        if len(ebs_purchase_dict) > 0:
            for pkey in ebs_purchase_dict:
                ebs_line = ebs_purchase_dict[pkey]
                if pkey not in aas_purchase_dict:
                    aas_line_list.append((0, 0, ebs_line))
                    continue
                aas_line = aas_purchase_dict[pkey]
                if float_compare(ebs_line['product_qty'], aas_line['product_qty'], precision_rounding=0.000001) != 0:
                    if float_compare(ebs_line['product_qty'], aas_line['receipt_qty'], precision_rounding=0.000001) < 0:
                        raise UserError(u'订单数量不能小于已收货数量')
                    aas_line_list.append((1, aas_line['id'], {'product_qty': ebs_line['product_qty']}))
                del aas_purchase_dict[pkey]
        if len(aas_purchase_dict) > 0:
            for pkey in aas_purchase_dict:
                aas_line = aas_purchase_dict[pkey]
                if float_compare(aas_line['receipt_qty'], aas_line['rejected_qty'], precision_rounding=0.000001) != 0:
                    raise UserError(u"产品：%s已有收货,不可以清除！"% aas_line['product_code'])
                else:
                    aas_line_list.append((2, aas_line['id'], False))
        if len(aas_line_list) > 0:
            self.write({'order_lines': aas_line_list})
        return {"type": "ir.actions.client", "tag": "reload"}

    @api.multi
    def action_purchase_receipt(self):
        """
        生成采购收货单
        :return:
        """
        self.ensure_one()



class AASStockPurchaseOrderLine(models.Model):
    _name = 'aas.stock.purchase.order.line'
    _description = 'AAS Stock Purchase Order Line'
    _rec_name = 'product_id'

    order_id = fields.Many2one(comodel_name='aas.purchase.order', string=u'采购订单', ondelete='cascade')
    order_name = fields.Char(string=u'订单号')
    partner_id = fields.Many2one(comodel_name='res.partner', string=u'供应商')
    product_id = fields.Many2one(comodel_name='product.product', string=u'产品')
    product_uom = fields.Many2one(comodel_name='product.uom', string=u'单位')
    product_qty = fields.Float(string=u'订单数量', digits=dp.get_precision('Product Unit of Measure'), default=0.0)
    receipt_qty = fields.Float(string=u'收货数量', digits=dp.get_precision('Product Unit of Measure'), default=0.0)
    rejected_qty = fields.Float(string=u'退货数量', digits=dp.get_precision('Product Unit of Measure'), default=0.0)
    creation_date = fields.Datetime(string=u'创建日期')
    last_update_date = fields.Datetime(string=u'修改日期')
    created_by = fields.Integer(string='created_by')
    last_updated_by = fields.Integer(string='last_updated_by')




class AASStockPurchaseReceiptWizard(models.TransientModel):
    _name = 'aas.stock.purchase.receipt.wizard'
    _description = 'AAS Stock Purchase Receipt Wizard'

    partner_id = fields.Many2one(comodel_name='res.partner', string=u'供应商', ondelete='restrict')

    purchase_orders = fields.One2many(comodel_name='aas.stock.purchase.receipt.order.wizard', inverse_name='wizard_id', string=u'订单明细')
    purchase_lines = fields.One2many(comodel_name='aas.stock.purchase.receipt.line.wizard', inverse_name='wizard_id', string=u'采购明细')




class AASStockPurchaseReceiptOrderWizard(models.TransientModel):
    _name = 'aas.stock.purchase.receipt.order.wizard'
    _description = 'AAS Stock Purchase Receipt Order Wizard'

    wizard_id = fields.Many2one(comodel_name='aas.stock.purchase.receipt.wizard', string=u'采购收货', ondelete='cascade')
    purchase_id = fields.Many2one(comodel_name='aas.stock.purchase.order', string=u'采购订单', ondelete='cascade')


class AASStockPurchaseReceiptLineWizard(models.TransientModel):
    _name = 'aas.stock.purchase.receipt.line.wizard'
    _description = 'AAS Stock Purchase Receipt Line Wizard'


    wizard_id = fields.Many2one(comodel_name='aas.stock.purchase.receipt.wizard', string=u'采购收货', ondelete='cascade')
    line_id = fields.Many2one(comodel_name='aas.stock.purchase.order.line', string=u'收货明细', ondelete='cascade')
    order_name = fields.Char(string=u'订单号')
    receipt_qty = fields.Float(string=u'可收货数量', digits=dp.get_precision('Product Unit of Measure'), default=0.0)
    product_qty = fields.Float(string=u'收货数量', digits=dp.get_precision('Product Unit of Measure'), default=0.0)