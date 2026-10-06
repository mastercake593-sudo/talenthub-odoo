# -*- coding: utf-8 -*-
from odoo import models, fields, api


class TalentHubPosition(models.Model):
    _name = 'talenthub.position'
    _description = 'TalentHub Position'
    _order = 'imported_at desc, id desc'

    name = fields.Char(
        string='Position Title',
        required=True,
        help='The title of the position in TalentHub.',
    )
    external_position_id = fields.Char(
        string='External Position ID',
        required=True,
        index=True,
        help='Unique identifier of the position in TalentHub.',
    )
    source_base_url = fields.Char(
        string='Source Base URL',
        help='Base URL of the TalentHub instance from which this position was imported.',
    )
    imported_at = fields.Datetime(
        string='Imported At',
        default=fields.Datetime.now,
        help='Timestamp when the position aggregate data was last imported.',
    )
    attribute_result_ids = fields.One2many(
        comodel_name='talenthub.attribute.result',
        inverse_name='position_id',
        string='Attribute Results',
        help='Aggregated attribute results imported for this position.',
    )

    _sql_constraints = [
        (
            'uniq_external_pos_source',
            'unique(external_position_id, source_base_url)',
            'A position with this External ID and Source Base URL already exists.',
        ),
    ]

    def action_reimport(self):
        """Opens the import wizard pre-filled with this position's source base URL."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Re-import from TalentHub',
            'res_model': 'talenthub.import.position.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_base_url': self.source_base_url,
            },
        }
