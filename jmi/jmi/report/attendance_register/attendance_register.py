# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from functools import total_ordering
from itertools import count
import frappe
from frappe import permissions
from frappe.utils import cstr, cint, getdate, get_last_day, get_first_day, add_days
from frappe.utils import cstr, add_days, date_diff, getdate, format_date
from math import floor
from frappe import msgprint, _
from calendar import month, monthrange
from datetime import date, timedelta, datetime,time
from numpy import true_divide

import pandas as pd

status_map = {
    'Permission Request' :'PR',
    'On Duty':'OD',
    'Half Day':'HD',
    "Absent": "A",
	"Half Day": "HD",
	"Holiday": "HH",
	"Weekly Off": "WW",
    "Present": "P",
    "None" : "",
    "Leave Without Pay": "LOP",
    "Casual Leave": "CL",
    "Earned Leave": "EL",
    "Sick Leave": "SL",
    "Emergency -1": 'EML-1',
    "Emergency -2": 'EML-2',
    "Paternal Leave": 'PL',
    "Marriage Leave":'ML',
    "Paternity Leave":'PTL',
    "Education Leave":'EL',
    "Maternity Leave":'MTL',
    "Covid -19": "COV-19",
    "Privilege Leave": "PVL",
    "Compensatory Off": "C-OFF",
    "BEREAVEMENT LEAVE":'BL'
}
def execute(filters=None):
    columns = get_columns(filters)
    data = get_data(filters)
    return columns, data

def get_columns(filters):
    columns = []
    columns += [
        _("Employee ID") + ":Data/:150",_("Employee Name") + ":Data/:200",_("Contractor") + ":Data/:150",_("Designation") + ":Data/:150",_("Branch") + ":Data/:150",_("DOJ") + ":Date/:100",_("") + ":Data/:150",
    ]
    dates = get_dates(filters.from_date,filters.to_date)
    for date in dates:
        date = datetime.strptime(date,'%Y-%m-%d')
        day = datetime.date(date).strftime('%d')
        month = datetime.date(date).strftime('%b')
        columns.append(_(day + '/' + month) + ":Data/:70")
    columns.append(_("Present") + ":Data/:100")
    columns.append(_('Half Day') +':Data/:100')
    columns.append(_("Absent") + ":Data/:100")
    columns.append(_('Weekoff')+ ':Data/:100')
    columns.append(_('OT Hours')+ ':Data/:100')
    return columns

def get_data(filters):
    data = []
    emp_status_map = []
    employees = get_employees(filters)
    for emp in employees:
        dates = get_dates(filters.from_date,filters.to_date)
        row1 = [emp.name,emp.employee_name,emp.contractor,emp.designation,emp.branch,emp.date_of_joining,"Status"]
        row2 = ["","","","","","","In Time"]
        row3 = ["","","","","","","Out Time"]
        row4 = ["","","","","","","Shift"]
        row5 = ["","","","","","","Overtime"]
        row6 = ["","","","","","","Total Working Hours"]

        total_present = 0
        total_half_day = 0
        total_absent = 0
        total_holiday = 0
        total_weekoff = 0
        total_ot = 0
        total_wot =0
        total_hot =0
        total_od = 0
        total_lop = 0
        total_paid_leave = 0
        total_combo_off = 0
        c_shift = 0
        over_time_hours = 0
        total_late = timedelta(0,0,0)
        total_late_deduct = timedelta(0,0)
        ww = 0
        twh = 0
        ot = 0
        total_days = 0
        for date in dates:
            att = frappe.db.get_value("Attendance",{'attendance_date':date,'employee':emp.name},['status','in_time','out_time','shift','employee','attendance_date','name','over_time_hours','total_working_hours','leave_type']) or ''
            if att:
                status = status_map.get(att[0], "")
                if status == 'P':
                    hh = check_holiday(date,emp.name)
                    if hh :
                        if hh == 'WW':
                            total_weekoff +=1
                            row1.append('P/WW')
                
                        else:
                            row1.append('P/HH')
                    else:  
                        row1.append(status or "-")
                        total_present = total_present + 1  
                        # total_days = total_present+total_holiday+total_weekoff
                # elif hh == 'WW' and status == 'p':
                #     row1.append('P/WW')   
                elif status == 'HD':
                    hh = check_holiday(date,emp.name)
                    if hh :
                        if hh == 'WW':
                            total_weekoff +=1
                            row1.append(hh) 
                        else:
                            row1.append('HD/HH')
                    else:  
                        row1.append(status or "-")
                        total_half_day = total_half_day + 1  
                        # total_days = total_present+total_holiday+total_weekoff  
                elif status == 'A':
                    hh = check_holiday(date,emp.name)
                    if hh:
                        if hh == 'WW':
                            total_weekoff += 1
                        row1.append(hh)
                    else: 
                        row1.append(status or '-') 
                        total_absent = total_absent + 1                         
                if att[1] is not None:
                    row2.append(att[1].strftime('%H:%M'))
                else:
                    row2.append('M')
                if att[2] is not None:
                    row3.append(att[2].strftime('%H:%M'))
                else:
                    row3.append('M')
                if att[3]:
                    row4.append(att[3])
                else:
                    row4.append('-')
                if att[3] == 'C':
                    c_shift += 1  
                if att[7]:
                    row5.append(att[7])
                    over_time_hours += att[7]
                else:
                    row5.append('-')
                if att[8]:
                    row6.append(att[8])
                else:
                    row6.append('-') 
            else:
                hh = check_holiday(date,emp.name)
                if hh :
                    if hh == 'WW': 
                        total_weekoff += 1
                        row1.append(hh)
                    else:
                        row1.append(hh)
                else:
                    row1.append('-')
    
                row2.append('-')
                row3.append('-')
                row4.append('-')
                row5.append('-')
                row6.append('-')

        # permission_hours = frappe.db.sql("""select sum(hours) as sum from `tabPermission Request` where permission_date between '%s' and '%s' and employee_id = '%s' and docstatus = '1' """%(filters.from_date,filters.to_date,emp.name),as_dict=True)[0].sum or 0
        row1.extend([total_present,total_half_day,total_absent,total_weekoff,over_time_hours])
        row2.extend(['-','-','-','-','-'])
        row3.extend(['-','-','-','-','-'])
        row4.extend(['-','-','-','-','-'])
        row5.extend(['-','-','-','-','-'])
        row6.extend(['-','-','-','-','-'])
        
        data.append(row1)
        data.append(row2)
        data.append(row3)
        data.append(row4)
        data.append(row5)
        data.append(row6)
       
    return data

def get_dates(from_date,to_date):
    no_of_days = date_diff(add_days(to_date, 1), from_date)
    dates = [add_days(from_date, i) for i in range(0, no_of_days)]
    return dates

def get_employees(filters):
    conditions = ''
    left_employees = []
    if filters.employee:
        conditions += "and employee = '%s' " % (filters.employee)
    if filters.branch:
        conditions += "and branch = '%s' " % (filters.branch)
    if filters.contractor:
        conditions+="and contractor = '%s' "%(filters.contractor)
           
    employees = frappe.db.sql("""select name, employee_name, contractor,department, designation, branch ,date_of_joining,holiday_list from `tabEmployee` where status = 'Active' %s """ % (conditions), as_dict=True)
    left_employees = frappe.db.sql("""select name, employee_name,contractor, department, designation, date_of_joining from `tabEmployee` where status = 'Left' and relieving_date >= '%s' %s """ %(filters.from_date,conditions),as_dict=True)
    employees.extend(left_employees)
    return employees

def check_holiday(date,emp):
    holiday_list = frappe.db.get_value('Employee',{'name':emp},'holiday_list')
    holiday = frappe.db.sql("""select `tabHoliday`.holiday_date,`tabHoliday`.weekly_off from `tabHoliday List` 
    left join `tabHoliday` on `tabHoliday`.parent = `tabHoliday List`.name where `tabHoliday List`.name = '%s' and holiday_date = '%s' """%(holiday_list,date),as_dict=True)
    doj= frappe.db.get_value("Employee",{'name':emp},"date_of_joining")
    status = ''
    if holiday :
        if doj < holiday[0].holiday_date:
            if holiday[0].weekly_off == 1:
                status = "WW"      
            else:
                status = "HH"
        else:
            status = 'Not Joined'
    return status
    
                                                        



