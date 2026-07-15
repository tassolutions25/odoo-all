from odoo import http, fields
from odoo.http import request
import json
from datetime import date, timedelta

class RiskDashboardController(http.Controller):

    @http.route('/api/risk_dashboard/data', type='json', auth='user')
    def get_dashboard_data(self, **kw):
        domain = []
        filters = kw.get('filters', {})
        
        if filters.get('time') == '30_days':
            domain.append(('date_identified', '>=', fields.Date.to_string(date.today() - timedelta(days=30))))
        elif filters.get('time') == '90_days':
            domain.append(('date_identified', '>=', fields.Date.to_string(date.today() - timedelta(days=90))))
        elif filters.get('time') == 'this_year':
            domain.append(('date_identified', '>=', fields.Date.to_string(date.today().replace(month=1, day=1))))
            
        if filters.get('branch') and filters['branch'] != 'all':
            domain.append(('branch_id', '=', int(filters['branch'])))
            
        if filters.get('department') and filters['department'] != 'all':
            domain.append(('department_id', '=', int(filters['department'])))
            
        if filters.get('category') and filters['category'] != 'all':
            domain.append(('risk_category_id', '=', int(filters['category'])))
            
        if filters.get('rating') and filters['rating'] != 'all':
            domain.append(('residual_risk_rating', '=', filters['rating']))

        risks = request.env['risk.register'].search(domain)
        
        inherent_matrix = self._generate_heatmap(risks, 'likelihood', 'impact', 5, 5)
        control_matrix = self._generate_heatmap(risks, 'control_adequacy', 'control_effectiveness', 5, 5)
        
        # Residual is inherent_risk_rating (y) vs control_strength_rating (x)
        ratings = ['very_low', 'low', 'medium', 'high', 'very_high']
        control_ratings = ['very_weak', 'weak', 'moderate', 'strong', 'very_strong']
        residual_matrix = {r: {c: 0 for c in control_ratings} for r in ratings}
        for risk in risks:
            if risk.inherent_risk_rating in ratings and risk.control_strength_rating in control_ratings:
                residual_matrix[risk.inherent_risk_rating][risk.control_strength_rating] += 1
        
        # Chart Data
        status_counts = self._get_status_counts(risks)
        category_counts = self._get_category_counts(risks)
        branch_counts = self._get_branch_counts(risks)
        department_counts = self._get_department_counts(risks)
        
        # Category Heatmap (Category vs Residual Rating)
        category_heatmap = {}
        for risk in risks:
            cat = risk.risk_category_id.name if risk.risk_category_id else 'Uncategorized'
            r_rating = risk.residual_risk_rating or 'medium'
            if cat not in category_heatmap:
                category_heatmap[cat] = {r: 0 for r in ratings}
            if r_rating in ratings:
                category_heatmap[cat][r_rating] += 1
        
        # Available Filters
        branches = request.env['hr.branch'].search_read([], ['id', 'name'])
        departments = request.env['hr.department'].search_read([], ['id', 'name'])
        categories = request.env['risk.category'].search_read([], ['id', 'name'])
        
        # Mitigations
        mitigations = request.env['risk.mitigation'].search([])
        mitigation_status = self._get_mitigation_status(mitigations)

        return {
            'total_risks': len(risks),
            'open_risks': len(risks.filtered(lambda r: r.state in ['draft', 'waiting_leader', 'waiting_rcmd'])),
            'approved_risks': len(risks.filtered(lambda r: r.state == 'approved')),
            'inherent_heatmap': inherent_matrix,
            'control_heatmap': control_matrix,
            'residual_heatmap': residual_matrix,
            'category_heatmap': category_heatmap,
            'status_counts': status_counts,
            'category_counts': category_counts,
            'branch_counts': branch_counts,
            'department_counts': department_counts,
            'mitigation_status': mitigation_status,
            'availableFilters': {
                'branches': branches,
                'departments': departments,
                'categories': categories,
            }
        }

    def _generate_heatmap(self, risks, y_field, x_field, y_max, x_max):
        matrix = {y: {x: 0 for x in range(1, x_max + 1)} for y in range(1, y_max + 1)}
        for risk in risks:
            y = int(getattr(risk, y_field, 0))
            x = int(getattr(risk, x_field, 0))
            if 1 <= y <= y_max and 1 <= x <= x_max:
                matrix[y][x] += 1
        return matrix

    def _get_status_counts(self, risks):
        counts = {}
        for risk in risks:
            counts[risk.state] = counts.get(risk.state, 0) + 1
        return counts

    def _get_category_counts(self, risks):
        counts = {}
        for risk in risks:
            cat_name = risk.risk_category_id.name if risk.risk_category_id else 'Uncategorized'
            counts[cat_name] = counts.get(cat_name, 0) + 1
        return counts

    def _get_branch_counts(self, risks):
        counts = {}
        for risk in risks:
            branch_name = risk.branch_id.name if risk.branch_id else 'Head Office'
            counts[branch_name] = counts.get(branch_name, 0) + 1
        return counts

    def _get_department_counts(self, risks):
        counts = {}
        for risk in risks:
            dept_name = risk.department_id.name if risk.department_id else 'General'
            counts[dept_name] = counts.get(dept_name, 0) + 1
        return counts

    def _get_mitigation_status(self, mitigations):
        counts = {}
        for m in mitigations:
            status = m.progress_status if m.progress_status else 'pending'
            counts[status] = counts.get(status, 0) + 1
        return counts
