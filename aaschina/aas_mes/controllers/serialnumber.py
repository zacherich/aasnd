# -*-  coding: utf-8 -*-

"""
@version: 1.0
@author: luforn
@license: LGPL V3
@time: 2017-10-12 14:34
"""

import logging
import werkzeug

from odoo import http, fields
from odoo.http import request
from odoo.exceptions import AccessDenied, UserError, ValidationError

logger = logging.getLogger(__name__)


class AASMESSerialnumberController(http.Controller):

    def checking_serialnumber_information(self):
        values = {
            'success': True, 'message': '', 'serial_count': 0,
            'product_id': 0, 'product_code': '', 'customer_code': '',
            'mesline_id': 0, 'mesline_name': '', 'lastserialnumber': '',
            'serial_supplier': '2', 'serial_extend': '0', 'serial_type': '8'
        }
        isocalendar = fields.Datetime.to_timezone_time(fields.Datetime.now(), 'Asia/Shanghai').isocalendar()
        year, weeknumber, weekday = isocalendar[0], isocalendar[1], isocalendar[2]
        if weekday == 7:
            weekday = 0
            if weeknumber == 52:
                weeknumber = 1
                year += 1
            else:
                weeknumber += 1
        values.update({
            'serial_year': str(year)[2:], 'serial_week': str(100+weeknumber)[1:], 'serial_weekday': str(weekday)
        })
        login = request.env.user
        values['checker'] = login.name
        lineuser = request.env['aas.mes.lineusers'].search([('lineuser_id', '=', login.id)], limit=1)
        if not lineuser or lineuser.mesrole != 'serialnumber':
            values['success'] = False
            values['message'] = u'当前登录用户并非序列号创建用户；如果确实需要创建序列号，请联系领班为其配置权限！'
            return values
        mesline = lineuser.mesline_id
        workorder = mesline.workorder_id
        values.update({'mesline_id': mesline.id, 'mesline_name': mesline.name})
        if not workorder:
            values.update({'success': False, 'message': u'当前产线还未绑定需要生产的工单，请联系领班设置本产线需要生产的工单！'})
            return values
        else:
            temproduct = workorder.product_id
            product_code, customer_code = temproduct.default_code, temproduct.customer_product_code
            if not customer_code:
                values.update({
                    'success': False, 'message': u'产品%s还未设置客户方的编码，请联系领班设置客户编码！'% product_code
                })
                return values
            values.update({'product_id': temproduct.id, 'product_code': product_code, 'customer_code': customer_code})
        regular_code = values['serial_supplier'] + values['serial_year'] + values['serial_week'] + values['serial_weekday']
        regular_code += values['serial_type'] + values['serial_extend']
        values['regular_code'] = regular_code
        serialdomain = [('regular_code', '=', regular_code), ('mesline_id', '=', mesline.id)]
        maxserialnumber = request.env['aas.mes.serialnumber'].search(serialdomain, order='sequence desc', limit=1)
        if maxserialnumber:
            values['lastserialnumber'] = maxserialnumber.name
        values['serial_count'] = request.env['aas.mes.serialnumber'].search_count(serialdomain)
        return values


    @http.route('/aasmes/serialnumber', type='http', auth="user")
    def aasmes_serialnumber(self):
        values = self.checking_serialnumber_information()
        return request.render('aas_mes.aas_serialnumber_creation', values)


    @http.route('/aasmes/serialnumber/checkingmesline', type='json', auth="user")
    def aasmes_serialnumber_checkingmesline(self):
        return self.checking_serialnumber_information()


    @http.route('/aasmes/serialnumber/adddone', type='json', auth="user")
    def aasmes_serialnumber_addone(self, serialcount):
        values = self.checking_serialnumber_information()
        if not values.get('success', False):
            return values
        regular_code = values.get('regular_code')
        serialdomain = [('regular_code', '=', regular_code)]
        maxserialnumber = request.env['aas.mes.serialnumber'].search(serialdomain, order='sequence desc', limit=1)
        if maxserialnumber:
            sequence = maxserialnumber.sequence
        else:
            sequence = 0
        if serialcount + sequence > 9999:
            values.update({'success': False, 'message': u'序列号已超出最大数9999，请确认调整后继续操作！'})
            return values
        customercode = values['customer_code'].replace('-', '')
        current_date = fields.Datetime.to_timezone_string(fields.Datetime.now(), 'Asia/Shanghai')[0:10]
        lastserialnumber = values['lastserialnumber']
        for index in range(0, serialcount):
            sequence += 1
            sequencestr = str(10000+sequence)[1:]
            sequence_code = regular_code + sequencestr
            temp_name = customercode + sequence_code
            tserialnumber = request.env['aas.mes.serialnumber'].create({
                'regular_code': regular_code, 'sequence': sequence,
                'name': temp_name, 'product_id': values.get('product_id', False),
                'sequence_code': sequence_code, 'mesline_id': values.get('mesline_id', False),
                'internal_product_code': values['product_code'], 'customer_product_code': values['customer_code']
            })
            lastserialnumber = tserialnumber.name
        values.update({'lastserialnumber': lastserialnumber})
        countdoamin = [('regular_code', '=', regular_code), ('mesline_id', '=', values.get('mesline_id', False))]
        values['serial_count'] = request.env['aas.mes.serialnumber'].search_count(countdoamin)
        return values



    @http.route('/aasmes/serialnumber/loadingserialnumbers', type='json', auth="user")
    def aasmes_serialnumber_loadingserialnumbers(self, printerid, serialids):
        values = {'success': True, 'message': ''}
        login = request.env.user
        tempdomain = [('lineuser_id', '=', login.id), ('mesrole', '=', 'serialnumber')]
        lineuser = request.env['aas.mes.lineusers'].search(tempdomain, limit=1)
        if not lineuser:
            values.update({'success': False, 'message': u'当前登录用户还未分配序列号的权限！'})
            return values
        mesline, todaydate = lineuser.mesline_id, fields.Datetime.to_china_today()
        serialdomain = [('operation_date', '=', todaydate), ('mesline_id', '=', mesline.id)]
        serialdomain += [('id', 'in', serialids), ('printed', '=', False)]
        serialnumberlist = request.env['aas.mes.serialnumber'].search(serialdomain)
        if not serialnumberlist or len(serialnumberlist) <= 0:
            values.update({'success': False, 'message': u'当前标签已经全部打印，不可以批量重复打印！'})
            return values
        pvals = request.env['aas.mes.serialnumber'].action_print_label(printerid, serialnumberlist.ids)
        serialnumberlist.write({'printed': True})
        values.update(pvals)
        return values


    @http.route('/aasmes/serialnumber/reprint', type='json', auth="user")
    def aasmes_serialnumber_reprint(self, printerid, serialnumber):
        values = {'success': True, 'message': '', 'record': ''}
        serialnumber = serialnumber.strip()
        if not serialnumber:
            values.update({'success': False, 'message': u'请检查是否输入有效条码！'})
            return values
        tserialnumber = request.env['aas.mes.serialnumber'].search([('name', '=', serialnumber)], limit=1)
        if not tserialnumber:
            values.update({'success': False, 'message': u'请检查是否输入有效条码！'})
            return values
        lvals = request.env['aas.mes.serialnumber'].action_print_label(int(printerid), ids=[tserialnumber.id])
        return lvals



    @http.route('/aasmes/serialnumber/loadingmore', type='json', auth="user")
    def aasmes_serialnumber_loadingmore(self, page=1, limit=200):
        values = {
            'success': True, 'message': '', 'recordlist': [], 'page': page, 'limit': limit, 'total': 0, 'count': limit
        }
        login = request.env.user
        tempdomain = [('lineuser_id', '=', login.id), ('mesrole', '=', 'serialnumber')]
        lineuser = request.env['aas.mes.lineusers'].search(tempdomain, limit=1)
        if not lineuser:
            values.update({'success': False, 'message': u'当前登录用户还未分配创建序列号的权限！'})
            return values
        mesline, todaydate = lineuser.mesline_id, fields.Datetime.to_china_today()
        serialdomain = [('operation_date', '=', todaydate), ('mesline_id', '=', mesline.id)]
        values['total'] = request.env['aas.mes.serialnumber'].search_count(serialdomain)
        offset = (page - 1) * limit
        serialnumberlist = request.env['aas.mes.serialnumber'].search(serialdomain, offset=offset, order='id desc', limit=limit)
        if serialnumberlist and len(serialnumberlist) > 0:
            values['recordlist'] = [{
                'serialnumber_id': tserialnumber.id,
                'serialnumber_name': tserialnumber.name,
                'sequence_code': tserialnumber.sequence_code,
                'customer_code': tserialnumber.customer_product_code, 'product_code': tserialnumber.internal_product_code
            } for tserialnumber in serialnumberlist]
            values['count'] = len(serialnumberlist)
        return values



    @http.route('/aasmes/serialnumber/autoprint', type='json', auth="user")
    def aasmes_serialnumber_autoprint(self, printerid):
        values = {'success': True, 'message': ''}
        login = request.env.user
        tempdomain = [('lineuser_id', '=', login.id), ('mesrole', '=', 'serialnumber')]
        lineuser = request.env['aas.mes.lineusers'].search(tempdomain, limit=1)
        if not lineuser:
            values.update({'success': False, 'message': u'当前登录用户还未分配序列号的权限！'})
            return values
        mesline, todaydate = lineuser.mesline_id, fields.Datetime.to_china_today()
        serialdomain = [('operation_date', '=', todaydate), ('mesline_id', '=', mesline.id), ('printed', '=', False)]
        serialnumberlist = request.env['aas.mes.serialnumber'].search(serialdomain)
        if not serialnumberlist or len(serialnumberlist) <= 0:
            values.update({'success': False, 'message': u'当前标签已经全部打印，不可以批量重复打印！'})
            return values
        pvals = request.env['aas.mes.serialnumber'].action_print_label(printerid, serialnumberlist.ids)
        serialnumberlist.write({'printed': True})
        values.update(pvals)
        return values



