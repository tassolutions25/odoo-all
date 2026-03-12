# -*- coding: utf-8 -*-
import io
from odoo import http
from odoo.http import request
from odoo.tools.misc import xlsxwriter
from .common import AhaduReportCommon

class PensionReport(AhaduReportCommon):
    
    @http.route('/ahadu_payroll/pension_report/<int:batch_id>', type='http', auth='user')
    def download_pension_report(self, batch_id, **kw):
        batch = request.env['hr.payslip.run'].browse(batch_id)
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

        # Check if the report is for Addis Ababa region
        is_aa_region = any(r.name == 'Addis Ababa' for r in batch.region_ids)
        
        # Also check if branch(es) belong to Addis Ababa
        if not is_aa_region:
            if batch.branch_id and batch.branch_id.region_id.name == 'Addis Ababa':
                is_aa_region = True
            elif batch.branch_ids and any(b.region_id.name == 'Addis Ababa' for b in batch.branch_ids):
                is_aa_region = True
                
        aa_header_text = "በአዲስ አበባ ከተማ አስተዳደር የአዲስ አበባ ከፍተኛ ግብር ከፋዮች ቅርንጫፍ ጽሕፈት ቤት" if is_aa_region else ""
        
        # Header Section 1
        worksheet.merge_range('A1:C3', aa_header_text, title_fmt)
        worksheet.merge_range('D1:I3', "የግል ድርጅት ሠራተኞች የጡረታ መዋጮ ማሳወቂያ ቅጽ\n(በግል ድርጅት ሠራተኞች የጡረታ አዋጅ ቁጥር 715/2003)\nቅጽ ቁጥር 2/2003 የተጨመረ ማሳወቂያ ቅጽ", title_fmt)
        
        worksheet.merge_range('A4:I4', "ክፍል -1 የጡረታ መዋጮውን የሚከፍለው ድርጅት ዝርዝር መረጃ", section_fmt)
        worksheet.merge_range('A5:D5', "1. የድርጅቱ ስም: Ahadu Bank S.C", border_fmt)
        worksheet.merge_range('E5:G5', "2. የድርጅቱ የግብር ከፋይ መለያ ቁጥር: 0067033716", border_fmt)
        
        month_year = batch.date_start.strftime('%m/%Y') if batch.date_start else ''
        worksheet.merge_range('H5:I5', f"3. የክፍያ ጊዜ: {month_year}", border_fmt)

        worksheet.merge_range('A6:I6', "ክፍል -2 ማሳወቂያ ዝርዝር መረጃ", section_fmt)

        # Table Headers
        headers = [
            'ሀ) ተ.ቁ', 
            'ለ) የቋሚ ሠራተኛው የግብር ከፋይ መለያ ቁጥር (TIN)', 
            'ሐ) የሠራተኛው ስም /ከአያት ስም ጋር/', 
            'መ) የተቀጠረበት ቀን /ቀን/ወር/ዓ.ም/', 
            'ሠ) የወር ደሞዝ /ብር/', 
            'ረ) የሠራተኛው መዋጮ መጠን 7% /ብር/', 
            'ሰ) የአሰሪው መዋጮ መጠን 11% /ብር/', 
            'ሸ) በአጠቃላይ የሚገባ ጥቅል መዋጮ 18% /ብር/', 
            'ፊርማ'
        ]
        
        row = 7
        for col, h in enumerate(headers):
            worksheet.write(row, col, h, header_gray)
            column_width = [6, 20, 30, 15, 15, 15, 15, 18, 12][col]
            worksheet.set_column(col, col, column_width)
            
        row += 1; seq = 1; sum_basic = 0; sum_7 = 0; sum_11 = 0; sum_18 = 0
        
        for slip in self._get_payslip_lines(batch):
            # Skip contract employees without pension
            if slip.contract_id.pay_group_id.code == 'CONTEMPWOP':
                continue

            # Pension is calculated on (Basic - Penalty - LOP)
            # We show this effective basic to the external party
            # Penalty is stored as a negative value, so we add it. LOP is positive, so we subtract it.
            penalty = self._get_rule_total(slip, 'PENALTY')
            lop = self._get_rule_total(slip, 'LOP_LEAVE')
            basic = self._get_rule_total(slip, 'BASIC') + penalty - lop
            
            p7 = self._get_rule_total(slip, 'PENSION_EMP')
            p11 = self._get_rule_total(slip, 'PENSION_COMP')
            
            if basic > 0:
                worksheet.write(row, 0, seq, border_fmt)
                worksheet.write(row, 1, slip.employee_id.tin_number or '', border_fmt)
                worksheet.write(row, 2, slip.employee_id.name, border_fmt)
                worksheet.write(row, 3, slip.contract_id.date_start if slip.contract_id.date_start else '', date_fmt)
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
        # worksheet.merge_range(row, 7, row, 8, f"{sum_18:,.2f}", workbook.add_format({'bold': True, 'align': 'right'}))

        workbook.close(); output.seek(0)
        return self._make_excel_response(output, f'Pension_Report_{batch.name}.xlsx')
