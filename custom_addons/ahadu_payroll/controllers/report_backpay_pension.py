# -*- coding: utf-8 -*-
import io
import logging
from odoo import http
from odoo.http import request
from odoo.tools.misc import xlsxwriter
from .common import AhaduReportCommon

_logger = logging.getLogger(__name__)

class BackpayPensionReport(AhaduReportCommon):
    
    @http.route('/ahadu_payroll/backpay_pension_report/<int:batch_id>', type='http', auth='user')
    def download_backpay_pension_report(self, batch_id, **kw):
        batch = request.env['ahadu.backpay.batch'].browse(batch_id)
        if not batch.exists():
            return request.not_found()
            
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Pension Report')
        
        # Formats
        title_fmt = workbook.add_format({'bold': True, 'size': 11, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'text_wrap': True})
        header_gray = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True, 'font_size': 9})
        border_fmt = workbook.add_format({'border': 1, 'font_size': 9, 'valign': 'vcenter'})
        money_fmt = workbook.add_format({'num_format': '#,##0.00', 'border': 1, 'font_size': 9, 'valign': 'vcenter'})
        date_fmt = workbook.add_format({'num_format': 'dd/mm/yyyy', 'border': 1, 'font_size': 9, 'valign': 'vcenter', 'align': 'center'})
        section_fmt = workbook.add_format({'bold': True, 'bg_color': '#f2f2f2', 'border': 1, 'font_size': 10})

        # Header Section
        worksheet.merge_range('A1:C3', "በአዲስ አበባ ከተማ አስተዳደር የአዲስ አበባ\nከፍተኛ ግብር ከፋዮች ቅርንጫፍ ጽሕፈት ቤት", title_fmt)
        worksheet.merge_range('D1:I3', "የግል ድርጅት ሠራተኞች የጡረታ መዋጮ ማሳወቂያ ቅጽ (Arrears/Backpay)\n(በግል ድርጅት ሠራተኞች የጡረታ አዋጅ ቁጥር 715/2003)\nቅጽ ቁጥር 2/2003 የተጨመረ ማሳወቂያ ቅጽ", title_fmt)
        
        worksheet.merge_range('A4:I4', "ክፍል -1 የጡረታ መዋጮውን የሚከፍለው ድርጅት ዝርዝር መረጃ", section_fmt)
        worksheet.merge_range('A5:D5', "1. የድርጅቱ ስም: Ahadu Bank S.C", border_fmt)
        worksheet.merge_range('E5:G5', "2. የድርጅቱ የግብር ከፋይ መለያ ቁጥር: 0067033716", border_fmt)
        
        month_label = dict(batch._fields['month'].selection).get(batch.month)
        worksheet.merge_range('H5:I5', f"3. የክፍያ ጊዜ: {month_label} {batch.year}", border_fmt)

        worksheet.merge_range('A6:I6', "ክፍል -2 ማሳወቂያ ዝርዝር መረጃ", section_fmt)

        # Table Headers
        headers = [
            'ሀ) ተ.ቁ', 
            'ለ) የቋሚ ሠራተኛው የግብር ከፋይ መለያ ቁጥር (TIN)', 
            'ሐ) የሠራተኛው ስም /ከአያት ስም ጋር/', 
            'መ) ለሪፖርቱ የተያዘው ወር', 
            'ሠ) የአረር መሰረታዊ ደሞዝ /ብር/', 
            'ረ) የሠራተኛው መዋጮ 7% /ብር/', 
            'ሰ) የአሰሪው መዋጮ 11% /ብር/', 
            'ሸ) በአጠቃላይ የሚገባ ጥቅል መዋጮ 18% /ብር/', 
            'ፊርማ'
        ]
        
        row = 7
        for col, h in enumerate(headers):
            worksheet.write(row, col, h, header_gray)
            column_width = [6, 20, 30, 20, 15, 15, 15, 18, 12][col]
            worksheet.set_column(col, col, column_width)
            
        row += 1; seq = 1; sum_basic = 0; sum_7 = 0; sum_11 = 0; sum_18 = 0
        
        for line in batch.line_ids:
            basic = line.diff_basic
            p7 = line.diff_pension_emp
            p11 = line.diff_pension_comp
            
            if (abs(p7) + abs(p11)) > 0.01:
                worksheet.write(row, 0, seq, border_fmt)
                worksheet.write(row, 1, line.employee_id.tin_number or '', border_fmt)
                worksheet.write(row, 2, line.employee_id.name, border_fmt)
                
                # Period
                month_year = line.payslip_id.date_from.strftime('%B %Y') if line.payslip_id else ''
                worksheet.write(row, 3, month_year, border_fmt)
                
                worksheet.write(row, 4, basic, money_fmt)
                worksheet.write(row, 5, p7, money_fmt)
                worksheet.write(row, 6, p11, money_fmt)
                worksheet.write(row, 7, p7 + p11, money_fmt)
                worksheet.write(row, 8, '', border_fmt) # Signature
                
                sum_basic += basic; sum_7 += p7; sum_11 += p11; sum_18 += (p7 + p11)
                row += 1; seq += 1
                
        # Totals
        worksheet.merge_range(row, 0, row, 3, "Total", workbook.add_format({'bold': True, 'border': 1, 'align': 'center'}))
        worksheet.write(row, 4, sum_basic, money_fmt)
        worksheet.write(row, 5, sum_7, money_fmt)
        worksheet.write(row, 6, sum_11, money_fmt)
        worksheet.write(row, 7, sum_18, money_fmt)
        worksheet.write(row, 8, '', border_fmt)
        
        # Footer
        row += 2
        worksheet.merge_range(row, 0, row, 2, "የድርጅቱ ተወካይ/አዘጋጁ ስም: __________________________", workbook.add_format({'font_size': 9}))
        worksheet.write(row, 3, "ፊርማ: _________", workbook.add_format({'font_size': 9}))
        worksheet.write(row, 4, "ቀን: ___________", workbook.add_format({'font_size': 9}))

        workbook.close(); output.seek(0)
        return self._make_excel_response(output, f'Backpay_Pension_Report_{batch.name}.xlsx')
