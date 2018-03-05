# -*-  coding: utf-8 -*-

"""
@version: 1.0
@author: luforn
@license: LGPL V3
@time: 2018-3-5 23:16
"""

import logging
import werkzeug

from odoo import http, fields
from odoo.http import request
from odoo.tools.float_utils import float_compare, float_is_zero
from odoo.exceptions import AccessDenied, UserError, ValidationError

logger = logging.getLogger(__name__)


class AASWechatQualityOQCCheckingController(http.Controller):

    @http.route('/aaswechat/quality/oqcchecking/validatelabel', type='json', auth="user")
    def aas_wechat_quality_oqcchecking_validatelabel(self, barcode):
        values = {'success': True, 'message': ''}
        label = request.env['aas.product.label'].search([('name', '=', barcode)], limit=1)
        if not label:
            values.update({'success': False, 'message': u'标签异常，仔细检查是否是有效标签'})
            return values
        if label.oqcpass:
            values.update({'success': False, 'message': u'标签已通过质检，请不要重复操作！'})
            return values
        checkdomain = [('label_id', '=', label.id), ('checked', '=', False)]
        checklabel = request.env['aas.quality.oqcorder.label'].search(checkdomain, limit=1)
        if not checklabel:
            values.update({'success': False, 'message': u'标签已通过质检或还未报检！'})
            return values
        values['oqclabelid'] = checklabel.id
        return values

    @http.route('/aaswechat/quality/oqclabel/<int:oqclabelid>', type='http', auth="user")
    def aas_wechat_quality_oqcchecking_label(self, oqclabelid):
        values = {'success': True, 'message': ''}
        checklabel = request.env['aas.quality.oqcorder.label'].browse(oqclabelid)
        return request.render('aas_quality.wechat_quality_oqcchecking_label', values)
