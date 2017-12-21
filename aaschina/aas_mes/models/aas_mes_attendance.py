# -*-  coding: utf-8 -*-

"""
@version: 1.0
@author: luforn
@license: LGPL V3
@time: 2017-12-13 23:33
"""

from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_compare, float_is_zero
from odoo.exceptions import UserError, ValidationError

import logging

_logger = logging.getLogger(__name__)

class AASMESWorkAttendance(models.Model):
    _name = 'aas.mes.work.attendance'
    _description = 'AAS MES Work Attendance'
    _rec_name = 'employee_name'
    _order = 'attendance_start desc,attendance_finish desc'

    employee_id = fields.Many2one(comodel_name='aas.hr.employee', string=u'员工', ondelete='restrict', index=True)
    employee_name = fields.Char(string=u'员工名称', copy=False)
    employee_code = fields.Char(string=u'员工工号', copy=False)
    mesline_id = fields.Many2one(comodel_name='aas.mes.line', string=u'产线', ondelete='restrict', index=True)
    mesline_name = fields.Char(string=u'产线名称', copy=False)
    schedule_id = fields.Many2one(comodel_name='aas.mes.schedule', string=u'班次', ondelete='restrict', index=True)
    schedule_name = fields.Char(string=u'班次名称', copy=False)
    attendance_date = fields.Char(string=u'在岗日期')
    attendance_start = fields.Datetime(string=u'上岗时间', default=fields.Datetime.now, copy=False)
    attendance_finish = fields.Datetime(string=u'离岗时间', copy=False)
    attend_hours = fields.Float(string=u'总工时', default=0.0, copy=False)
    overtime_hours = fields.Float(string=u'加班工时', default=0.0, copy=False)
    attend_done = fields.Boolean(string=u'是否结束', default=False, copy=False)
    leave_id = fields.Many2one(comodel_name='aas.mes.work.attendance.leave', string=u'离岗原因', ondelete='restrict')
    worktime_min = fields.Float(string=u'最短工时')
    worktime_max = fields.Float(string=u'最长工时')
    worktime_standard = fields.Float(string=u'标准工时')
    worktime_advance = fields.Float(string=u'提前工时')
    company_id = fields.Many2one(comodel_name='res.company', string=u'公司', ondelete='restrict', index=True,
                                 default=lambda self: self.env.user.company_id)

    attend_lines = fields.One2many(comodel_name='aas.mes.work.attendance.line', inverse_name='attendance_id', string=u'出勤明细')



    @api.model
    def action_scanning(self, employee, mesline, workstation=None, equipment=None):
        """扫描上下岗
        :param employee:
        :param mesline:
        :param worstation:
        :return:
        """
        values = {'success': True, 'message': '', 'action': 'working'}
        tempdomain = [('employee_id', '=', employee.id), ('mesline_id', '=', mesline.id), ('attend_done', '=', False)]
        tattendance = self.env['aas.mes.work.attendance'].search(tempdomain, limit=1)
        if tattendance:
            values.update({'attendance_id': tattendance.id})
            linedomain = [('attendance_id', '=', tattendance.id), ('attend_done', '=', False)]
            if workstation:
                attenddomain = [('workstation_id', '=', workstation.id)]
                attenddomain += linedomain
                if self.env['aas.mes.work.attendance.line'].search_count(attenddomain) <= 0:
                    tvalues = self.action_attend(employee, mesline, workstation, tattendance, equipment=equipment)
                    values.update({'message': u'您已经在%s上岗，祝您工作愉快！'% workstation.name})
                    if not tvalues.get('success', False):
                        values.update(tvalues)
                        return values
                else:
                    attendancelines = self.env['aas.mes.work.attendance.line'].search(linedomain)
                    attendancelines.action_done()
                    values['action'] = 'leave'
                    return values
            else:
                attendancelines = self.env['aas.mes.work.attendance.line'].search(linedomain)
                if attendancelines and len(attendancelines) > 0:
                    attendancelines.action_done()
                    values['action'] = 'leave'
                    return values
                else:
                    values.update({'success': False, 'message': u'您还未选择上岗工位！'})
                    return values
        elif not workstation:
            values.update({'success': False, 'message': u'您还未选择上岗工位！'})
            return values
        else:
            tvalues = self.action_attend(employee, mesline, workstation, equipment=equipment)
            values.update({'message': u'您已经在%s上岗，祝您工作愉快！'% workstation.name})
            if not tvalues.get('success', False):
                values.update(tvalues)
                return values
            values['attendance_id'] = tvalues['attendance_id']
        return values



    @api.model
    def action_attend(self, employee, mesline, workstation, attendance=None, equipment=None):
        values = {'success': True, 'message': ''}
        if attendance and (employee.id != attendance.employee_id.id or mesline.id != attendance.mesline_id.id):
            values = {'success': False, 'message': u'出勤记录异常，请仔细检查！'}
            return values
        if not attendance:
            tvalues = self.action_addattendance(employee, mesline)
            if not tvalues.get('success', False):
                values.update(tvalues)
                return values
            attendance = tvalues['attendance']
        values.update({'attendance_id': attendance.id})
        linedomain = [('attendance_id', '=', attendance.id), ('employee_id', '=', employee.id)]
        linedomain.extend([('mesline_id', '=', mesline.id), ('workstation_id', '=', workstation.id)])
        linedomain.append(('attend_done', '=', False))
        if self.env['aas.mes.work.attendance.line'].search_count(linedomain) <= 0:
            self.env['aas.mes.work.attendance.line'].create({
                'attendance_id': attendance.id, 'employee_id': employee.id,
                'mesline_id': mesline.id, 'workstation_id': workstation.id,
                'equipment_id': False if not equipment else equipment.id
            })
        return values


    @api.model
    def action_addattendance(self, employee, mesline):
        """添加出勤
        :param employee:
        :param mesline:
        :return:
        """
        values = {'success': True, 'message': '', 'attendance': False}
        attendancevals = {
            'employee_id': employee.id, 'employee_name': employee.name,
            'mesline_id': mesline.id, 'mesline_name': mesline.name
        }
        worktime_min = self.env['ir.values'].sudo().get_default('aas.mes.settings', 'worktime_min')
        worktime_max = self.env['ir.values'].sudo().get_default('aas.mes.settings', 'worktime_max')
        worktime_advance = self.env['ir.values'].sudo().get_default('aas.mes.settings', 'worktime_advance')
        worktime_standard = self.env['ir.values'].sudo().get_default('aas.mes.settings', 'worktime_standard')
        attendancevals.update({
            'worktime_min': worktime_min, 'worktime_max': worktime_max,
            'worktime_advance': worktime_advance, 'worktime_standard': worktime_standard
        })
        if not mesline.schedule_lines and len(mesline.schedule_lines) <= 0:
            values.update({'success': False, 'message': u'产线%s还未设置班次，请联系管理员设置班次信息！'% mesline.name})
            return values
        if not mesline.workdate:
            mesline.sudo().action_refresh_schedule()
        timestart = fields.Datetime.now()
        attendancevals.update({'attendance_start': timestart, 'attendance_date': mesline.workdate})
        if mesline.schedule_id:
            attendancevals.update({'schedule_id': mesline.schedule_id.id, 'schedule_name': mesline.schedule_id.name})
        nextvalues = self.env['aas.mes.line'].loading_nextschedule(mesline)
        if not nextvalues.get('success', False):
            values.update(nextvalues)
            return values
        nextschedule = nextvalues['schedule']
        temptimes = fields.Datetime.from_string(nextschedule['actual_start']) - fields.Datetime.from_string(timestart)
        if (temptimes.total_seconds() / 3600.00) <= worktime_advance:
            attendancevals.update({'attendance_start': nextschedule['actual_start'], 'attendance_date': nextschedule['workdate']})
        values['attendance'] = self.env['aas.mes.work.attendance'].create(attendancevals)
        return values



    @api.model
    def action_trace_employees_equipments(self, mesline_id, schedule_id, workstation_id, attendance_date):
        """
        获取相应日期的产线班次上指定工位的员工和设备信息
        :param mesline_id:
        :param schedule_id:
        :param workstation_id:
        :param attendance_date:
        :return:
        """
        tracingdomain, tracevals = [], {'employeelist': '', 'equipmentlist': ''}
        if mesline_id:
            tracingdomain.append(('mesline_id', '=', mesline_id))
        if schedule_id:
            tracingdomain.append(('schedule_id', '=', schedule_id))
        if workstation_id:
            tracingdomain.append(('workstation_id', '=', workstation_id))
        if attendance_date:
            tracingdomain.append(('attendance_date', '=', attendance_date))
        if not tracingdomain or len(attendance_date) <= 0:
            return tracevals
        attendances = self.env['aas.mes.work.attendance'].search(tracingdomain)
        if attendances and len(tracingdomain) > 0:
            employeeids, employees, equipmentids, equipments = [], [], [], []
            for attendance in attendances:
                temployee, tequipment = attendance.employee_id, attendance.equipment_id
                if temployee and temployee.id not in employeeids:
                    employeeids.append(temployee.id)
                    employees.append(attendance.employee_name+'['+attendance.employee_code+']')
                if tequipment and tequipment.id not in equipmentids:
                    equipmentids.append(tequipment.id)
                    equipments.append(attendance.equipment_name+'['+attendance.equipment_code+']')
            if employees and len(employees) > 0:
                tracevals['employeelist'] = ','.join(employees)
            if equipments and len(equipments) > 0:
                tracevals['equipmentlist'] = ','.join(equipments)
        return tracevals


    @api.multi
    def action_done(self):
        """完成出勤，更闹心相关信息
        :return:
        """
        currentstr = fields.Datetime.now()
        currenttime = fields.Datetime.from_string(currentstr)
        for record in self:
            starttime = fields.Datetime.from_string(record.attendance_start)
            if ((currenttime - starttime).total_seconds() / 3600) <= record.worktime_max:
                continue
            linedomain = [('attendance_id', '=', record.id), ('attend_done', '=', False)]
            templines = self.env['aas.mes.work.attendance.line'].search(linedomain)
            if templines and len(templines) > 0:
                templines.action_done()
            attendancevals = {'attend_done': True}
            if not record.attendance_finish:
                finishtime = currenttime
                attendancevals['attendance_finish'] = currentstr
            else:
                finishtime = fields.Datetime.from_string(record.attendance_finish)
            totaltime = (finishtime - starttime).total_seconds() / 3600.0
            attendancevals['attend_hours'] = totaltime
            overtime = totaltime - record.worktime_standard
            if float_compare(overtime, 0.0, precision_rounding=0.000001) > 0.0:
                attendancevals['overtime_hours'] = overtime
            # 更新工作日和班次信息
            if record.attend_lines and len(record.attend_lines) > 0:
                linedict = {}
                for aline in record.attend_lines:
                    if not aline.schedule_id:
                        continue
                    akey = aline.attendance_date + '-' + str(aline.schedule_id.id)
                    if akey not in linedict:
                        linedict[akey] = {
                            'attendance_date': aline.attendance_date,
                            'schedule_id': aline.schedule_id.id, 'attend_hours': aline.attend_hours
                        }
                    else:
                        linedict[akey]['attend_hours'] += aline.attend_hours
                if linedict and len(linedict) > 0:
                    workdate, schedule_id, thours = False, False, 0.0
                    for lkey, lval in linedict.items():
                        if float_compare(lval['attend_hours'], thours, precision_rounding=0.000001) > 0.0:
                            thours = lval['attend_hours']
                            workdate, schedule_id = lval['attendance_date'], lval['schedule_id']
                    attendancevals.update({'attendance_date': workdate, 'schedule_id': schedule_id})
            record.write(attendancevals)

    @api.model
    def action_workstation_scanning(self, equipment_code, employee_barcode):
        """工控工位扫描员工卡
        :param equipment_code:
        :param employee_barcode:
        :return:
        """
        values = {'success': True, 'message': '', 'action': 'working'}
        if not equipment_code:
            values.update({'success': False, 'message': u'您确认已经设置了设备编码吗？'})
            return values
        equipment = self.env['aas.equipment.equipment'].search([('code', '=', equipment_code)], limit=1)
        if not equipment:
            values.update({'success': False, 'message': u'设备异常，请仔细检查系统是否存在此设备！'})
            return values
        if not equipment.mesline_id or not equipment.workstation_id:
            values.update({'success': False, 'message': u'当前设备可能还未设置产线工位！'})
            return values
        employee = self.env['aas.hr.employee'].search([('barcode', '=', employee_barcode)], limit=1)
        if not employee:
            values.update({'success': False, 'message': u'请确认是否有此员工存在，或许当前员已被删除，请仔细检查！'})
            return values
        mesline, workstation = equipment.mesline_id, equipment.workstation_id
        values = self.action_scanning(employee, mesline, workstation, equipment)
        if not values.get('success', False):
            return values
        values.update({'employee_name': employee.name, 'employee_code': employee.code})
        return values

# 出勤明细
class AASMESWorkAttendanceLine(models.Model):
    _name = 'aas.mes.work.attendance.line'
    _description = 'AAS MES Attendance Line'
    _rec_name = 'employee_id'
    _order = 'id desc'

    attendance_id = fields.Many2one(comodel_name='aas.mes.work.attendance', string=u'出勤', ondelete='cascade', index=True)
    mesline_id = fields.Many2one(comodel_name='aas.mes.line', string=u'产线', ondelete='restrict', index=True)
    schedule_id = fields.Many2one(comodel_name='aas.mes.schedule', string=u'班次', ondelete='restrict', index=True)
    employee_id = fields.Many2one(comodel_name='aas.hr.employee', string=u'员工', ondelete='restrict', index=True)
    workstation_id = fields.Many2one(comodel_name='aas.mes.workstation', string=u'工位', ondelete='restrict', index=True)
    equipment_id = fields.Many2one(comodel_name='aas.equipment.equipment', string=u'设备', ondelete='restrict', index=True)
    attendance_date = fields.Char(string=u'在岗日期', copy=False)
    attendance_start = fields.Datetime(string=u'开始时间', default=fields.Datetime.now)
    attendance_finish = fields.Datetime(string=u'结束时间')
    attend_done = fields.Boolean(string=u'出勤结束', default=False, copy=False)
    attend_hours = fields.Float(string=u'在岗工时', compute='_compute_attend_hours', store=True)
    leave_id = fields.Many2one(comodel_name='aas.mes.work.attendance.leave', string=u'离开原因', ondelete='restrict')
    company_id = fields.Many2one(comodel_name='res.company', string=u'公司', ondelete='restrict', default=lambda self:self.env.user.company_id)

    @api.depends('attendance_start', 'attendance_finish')
    def _compute_attend_hours(self):
        for record in self:
            if record.attendance_start and record.attendance_finish:
                temptimes = fields.Datetime.from_string(record.attendance_finish) - fields.Datetime.from_string(record.attendance_start)
                record.attend_hours = temptimes.total_seconds() / 3600.00
            else:
                record.attend_hours = 0.0

    @api.model
    def create(self, vals):
        record = super(AASMESWorkAttendanceLine, self).create(vals)
        record.action_after_create()
        return record

    @api.one
    def action_after_create(self):
        linevals = {}
        if self.mesline_id.schedule_id:
            linevals['schedule_id'] = self.mesline_id.schedule_id.id
        if self.mesline_id.workdate:
            linevals['attendance_date'] = self.mesline_id.workdate
        if linevals and len(linevals) > 0:
            self.write(linevals)
        self.env['aas.mes.workstation.employee'].create({
            'mesline_id': self.mesline_id.id, 'workstation_id': self.workstation_id.id,
            'employee_id': self.employee_id.id,
            'equipment_id': False if not self.equipment_id else self.equipment_id.id
        })
        self.employee_id.write({'state': 'working'})
        if self.attendance_id:
            self.attendance_id.write({'attendance_finish': False, 'leave_id': False})


    @api.multi
    def action_done(self, leaveid=None):
        """出勤结束
        :param leaveid:
        :return:
        """
        employeeids, attendanceids = [], []
        for record in self:
            if record.employee_id.id not in employeeids:
                employeeids.append(record.employee_id.id)
            if record.attendance_id and record.attendance_id.id not in attendanceids:
                attendanceids.append(record.attendance_id.id)
        currenttime = fields.Datetime.now()
        attendancevals = {'attendance_finish': currenttime, 'attend_done': True}
        if leaveid:
            attendancevals['leave_id'] = leaveid
        self.write(attendancevals)
        if attendanceids and len(attendanceids) > 0:
            attendancelist = self.env['aas.mes.work.attendance'].browse(attendanceids)
            attendancelist.write({
                'attendance_finish': currenttime, 'leave_id': False if not leaveid else leaveid
            })
        wsemployees = self.env['aas.mes.workstation.employee'].search([('employee_id', 'in', employeeids)])
        if wsemployees and len(wsemployees) > 0:
            wsemployees.unlink()
        employeelist = self.env['aas.hr.employee'].browse(employeeids)
        employeelist.write({'state': 'leave'})


    @api.multi
    def action_split(self):
        """
        出勤记录分割
        :return:
        """
        for record in self:
            if record.attend_done:
                continue
            attendancevals, mesline, workdate = {}, record.mesline_id, record.attendance_date
            oldscheduleid = False if not record.schedule_id else record.schedule_id.id
            if mesline.workdate != workdate:
                attendancevals['attendance_date'] = mesline.workdate
            newscheduleid = False if not mesline.schedule_id else mesline.schedule_id.id
            if newscheduleid != oldscheduleid:
                attendancevals['schedule_id'] = newscheduleid
            if attendancevals and len(attendancevals) > 0:
                attendancevals.update({
                    'attendance_id': record.attendance_id.id, 'mesline_id': mesline.id,
                    'employee_id': record.employee_id.id, 'workstation_id': record.workstation_id.id,
                    'company_id': record.company_id.id,
                    'equipment_id': False if not record.equipment_id else record.equipment_id.id
                })
                record.action_done()
                self.env['aas.mes.work.attendance.line'].create(attendancevals)





# 员工出勤离开原因
class AASMESWorkAttendanceLeave(models.Model):
    _name = 'aas.mes.work.attendance.leave'
    _description = 'AAS MES Attendance Leave'

    name = fields.Char(string=u'名称', required=True, copy=False, index=True)
    active = fields.Boolean(string=u'是否有效', default=True)
    operate_time = fields.Datetime(string=u'创建时间', default=fields.Datetime.now)
    operator_id = fields.Many2one(comodel_name='res.users', string=u'创建人', ondelete='restrict', default=lambda self: self.env.user)
    company_id = fields.Many2one(comodel_name='res.company', string=u'公司', ondelete='restrict', default=lambda self:self.env.user.company_id)