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
        help='Type of attribute, e.g. Numeric, OneOfMany, Boolean.',
    )
    sample_count = fields.Integer(
        string='Sample Count',
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

    # OneOfMany / Categorical aggregation (Normalized relational model)
    popular_value_ids = fields.One2many(
        comodel_name='talenthub.attribute.popular.value',
        inverse_name='attribute_result_id',
        string='Popular Values',
    )
    popular_values_display = fields.Text(
        string='Popular Values Summary',
        compute='_compute_popular_values_display',
        help='Human-readable summary of popular values for table view.',
    )

    @api.depends('popular_value_ids.value', 'popular_value_ids.count')
    def _compute_popular_values_display(self):
        for record in self:
            if not record.popular_value_ids:
                record.popular_values_display = ''
            else:
                items = [f"{pv.value} ({pv.count})" for pv in record.popular_value_ids]
                record.popular_values_display = ', '.join(items)


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
