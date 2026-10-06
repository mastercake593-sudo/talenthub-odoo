# -*- coding: utf-8 -*-
{
    'name': 'TalentHub Integration',
    'version': '19.0.1.0.0',
    'summary': 'Read-only viewer for Position aggregate results from TalentHub',
    'description': """
TalentHub Integration for Odoo 19
=================================
This module provides a read-only viewer for Position aggregate results imported
from the TalentHub/CVSystem ASP.NET platform.

Features:
- Import Position aggregate statistics using a per-Position API token.
- Secure, token is not stored in the database.
- Idempotent upsert: updating a position refreshes attribute aggregates.
- Aggregation support: Numeric (avg, min, max), Boolean (true/false counts), OneOfMany (popular values).
    """,
    'category': 'Human Resources',
    'author': 'TalentHub',
    'license': 'LGPL-3',
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/talenthub_position_views.xml',
        'views/import_position_wizard_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
