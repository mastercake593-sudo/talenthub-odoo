# -*- coding: utf-8 -*-
from odoo import models, fields, api


class TalentHubAttributeResult(models.Model):
    _name = 'talenthub.attribute.result'
    _description = 'TalentHub Attribute Aggregated Result'
    _order = 'name asc, id asc'

    position_id = fields.Many2one(
        comodel_name='talenthub.position',
        string='Position',
        required=True,
        ondelete='cascade',
        index=True,
    )
    external_attribute_id = fields.Char(
        string='External Attribute ID',
        help='Attribute ID in TalentHub.',
    )
    name = fields.Char(
        string='Attribute Name',
        required=True,
    )
    data_type = fields.Char(
        string='Data Type',
        required=True,
        help='Type of attribute, e.g. Numeric, Dropdown, Boolean, Date, Period.',
    )
    aggregation_kind = fields.Char(
        string='Aggregation Kind',
        help='Kind of aggregation received from TalentHub (e.g. numeric, topValues, boolean, date, period).',
    )
    sample_count = fields.Integer(
        string='Non-Empty Count',
        default=0,
        help='Total number of candidate responses or values aggregated.',
    )

    # Numeric aggregation
    average_value = fields.Float(
        string='Average',
        digits=(16, 2),
    )
    min_value = fields.Float(
        string='Minimum',
        digits=(16, 2),
    )
    max_value = fields.Float(
        string='Maximum',
        digits=(16, 2),
    )

    # Boolean aggregation
    true_count = fields.Integer(
        string='True Count',
        default=0,
    )
    false_count = fields.Integer(
        string='False Count',
        default=0,
    )
    true_percentage = fields.Float(
        string='True %',
        digits=(16, 1),
    )

    # Date / Period aggregation
    date_min = fields.Char(
        string='Min Date / Start',
    )
    date_max = fields.Char(
        string='Max Date / End',
    )
    summary_info = fields.Char(
        string='Summary Info',
    )

    # Categorical aggregation (topValues / Dropdown / OneOfMany)
    popular_value_ids = fields.One2many(
        comodel_name='talenthub.attribute.popular.value',
        inverse_name='attribute_result_id',
        string='Popular Values',
    )
    popular_values_display = fields.Text(
        string='Aggregation Summary',
        compute='_compute_popular_values_display',
        help='Human-readable summary of aggregation values for table view.',
    )

    @api.depends('popular_value_ids.value', 'popular_value_ids.count', 'aggregation_kind', 'date_min', 'date_max', 'summary_info', 'true_percentage')
    def _compute_popular_values_display(self):
        for record in self:
            kind = (record.aggregation_kind or '').lower()
            if record.popular_value_ids:
                items = [f"{pv.value} ({pv.count})" for pv in record.popular_value_ids]
                record.popular_values_display = ', '.join(items)
            elif kind in ('date', 'period') and (record.date_min or record.date_max):
                record.popular_values_display = f"{record.date_min or '—'} .. {record.date_max or '—'}"
            elif kind == 'boolean' and record.true_percentage:
                record.popular_values_display = f"{record.true_percentage:.1f}% True"
            elif record.summary_info:
                record.popular_values_display = record.summary_info
            else:
                record.popular_values_display = ''


class TalentHubAttributePopularValue(models.Model):
    _name = 'talenthub.attribute.popular.value'
    _description = 'TalentHub Attribute Popular Value'
    _order = 'count desc, value asc'

    attribute_result_id = fields.Many2one(
        comodel_name='talenthub.attribute.result',
        string='Attribute Result',
        required=True,
        ondelete='cascade',
        index=True,
    )
    value = fields.Char(
        string='Value',
        required=True,
    )
    count = fields.Integer(
        string='Count',
        default=0,
    )
