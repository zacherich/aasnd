# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_compare
from odoo.exceptions import UserError
from odoo.tools.sql import drop_view_if_exists

import logging
_logger = logging.getLogger(__name__)


class Warehouse(models.Model):
    _inherit = 'stock.warehouse'

    wh_wip_stock_loc_id = fields.Many2one(comodel_name='stock.location', string='WIP Location')


    @api.model
    def create(self, vals):
        warehouse = super(Warehouse, self).create(vals)
        warehouse.action_after_create()
        return warehouse

    @api.one
    def action_after_create(self):
        locations = self.env['stock.location']
        locations |= self.wh_input_stock_loc_id
        locations |= self.wh_output_stock_loc_id
        locations.write({'active': True})
        wipvals = {'name': 'WIP', 'active': True, 'usage': 'wip', 'location_id': self.view_location_id.id, 'company_id': self.company_id.id}
        wipacation = self.env['stock.location'].create(wipvals)
        self.write({'wh_wip_stock_loc_id': wipacation.id})

    @api.model
    def action_upgrade_aas_stock_warehouse(self):
        warehouses = self.env['stock.warehouse'].search([('wh_wip_stock_loc_id', '=', False)])
        if not warehouses or len(warehouses) <= 0:
            return
        for warehouse in warehouses:
            warehouse.action_after_create()

    @api.model
    def get_default_warehouse(self):
        return self.env['stock.warehouse'].search([('company_id', '=', self.env.user.company_id.id)], order='id', limit=1)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    need_warranty = fields.Boolean(string=u'质保期', default=False, help=u"收货时是否需要设置质保期")
    stock_age = fields.Integer(string=u"库龄", default=0, help=u'物料在仓库保存时间，超过时间要给出提醒')
    push_location = fields.Many2one(comodel_name='stock.location', string=u'推荐库位', help=u'最近上架库位')



class AASProductProduct(models.Model):
    _inherit = 'product.product'

    @api.multi
    def name_get(self):
        if len(self) <= 0:
            return []
        return [(record.id, record.default_code) for record in self]


class Location(models.Model):
    _inherit = 'stock.location'

    usage = fields.Selection(selection_add=[('sundry', u'杂项'), ('wip', u'线边库')])
    mrblocation = fields.Boolean(string=u'MRB库位', default=False, copy=False)

    @api.model
    def create(self, vals):
        vals['barcode'] = 'AA'+vals.get('name')
        return super(Location, self).create(vals)


    @api.multi
    def write(self, vals):
        if vals.get('name'):
            vals['barcode'] = 'AA'+vals.get('name')
        return super(Location, self).write(vals)



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
            locationdomain = [('id', 'in', ids)]
        else:
            locationdomain = domain
        records = self.search_read(domain=locationdomain, fields=field_list)
        if not records or len(records) <= 0:
            values.update({'success': False, 'message': u'未搜索到需要打印的标签！'})
            return values
        records = printer.action_correct_records(records)
        values['records'] = records
        return values



class AASStockQuantReport(models.Model):
    _auto = False
    _name = 'aas.stock.quant.report'
    _description = u'库存报表'

    product_id = fields.Many2one(comodel_name='product.product', string=u'产品', readonly=True)
    product_uom = fields.Many2one(comodel_name='product.uom', string=u'单位', related='product_id.uom_id', readonly=True)
    product_qty = fields.Float(string=u'数量', digits=dp.get_precision('Product Unit of Measure'), readonly=True)
    location_id = fields.Many2one(comodel_name='stock.location', string=u'库位',  readonly=True)
    company_id = fields.Many2one(comodel_name='res.company', string=u'公司', readonly=True)

    def _select(self):
        select_str = """
        SELECT min(asq.id) as id,
        asq.product_id as product_id,
        sum(asq.qty) as product_qty,
        asq.company_id as company_id,
        asq.location_id as location_id
        """
        return select_str


    def _from(self):
        from_str = """
        stock_quant asq
        """
        return from_str


    def _group_by(self):
        group_by_str = """
        GROUP BY asq.product_id,asq.company_id,asq.location_id
        """
        return group_by_str


    @api.model_cr
    def init(self):
        drop_view_if_exists(self._cr, self._table)
        self._cr.execute("""CREATE or REPLACE VIEW %s as ( %s FROM %s %s )""" % (self._table, self._select(), self._from(), self._group_by()))

