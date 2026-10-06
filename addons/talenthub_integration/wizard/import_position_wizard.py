# -*- coding: utf-8 -*-
import logging
import requests
from odoo import models, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 15


class TalentHubImportPositionWizard(models.TransientModel):
    _name = 'talenthub.import.position.wizard'
    _description = 'Import TalentHub Position Wizard'

    base_url = fields.Char(
        string='TalentHub Base URL',
        required=True,
        help='Base URL of the TalentHub service, e.g. https://talenthub.example.com',
    )
    api_token = fields.Char(
        string='Position API Token',
        required=True,
        help='Per-Position API token issued by TalentHub for accessing aggregated statistics.',
    )

    def action_import_position(self):
        """Fetches position aggregates from TalentHub API and upserts into local Odoo database."""
        self.ensure_one()

        base_url = (self.base_url or '').strip().rstrip('/')
        api_token = (self.api_token or '').strip()

        if not base_url:
            raise UserError(_("Please provide a valid TalentHub Base URL."))
        if not api_token:
            raise UserError(_("Please provide a Position API Token."))

        masked_token = f"{api_token[:4]}***" if len(api_token) > 4 else "***"
        _logger.info("Importing TalentHub position from %s with token prefix %s", base_url, masked_token)

        # Send both X-API-Token and Authorization headers for maximum compatibility
        headers = {
            'X-API-Token': api_token,
            'Authorization': f'Bearer {api_token}',
            'Accept': 'application/json',
            'User-Agent': 'Odoo-TalentHub-Integration/19.0',
        }

        # Candidate endpoints: try /position-results first, fallback to /position
        endpoints = [
            f"{base_url}/api/integrations/odoo/position-results",
            f"{base_url}/api/integrations/odoo/position",
        ]

        response = None
        last_error = None
        for endpoint in endpoints:
            try:
                resp = requests.get(endpoint, headers=headers, timeout=TIMEOUT_SECONDS)
                if resp.status_code == 404 and endpoint != endpoints[-1]:
                    # Try next candidate endpoint
                    continue
                response = resp
                break
            except requests.exceptions.Timeout:
                last_error = _("Connection timed out while reaching TalentHub at %s.") % base_url
            except requests.exceptions.RequestException as exc:
                last_error = _("Network failure communicating with TalentHub: %s") % str(exc)

        if response is None:
            raise UserError(last_error or _("Failed to reach TalentHub API."))

        # Handle HTTP status codes according to requirements
        if response.status_code in (401, 403):
            raise UserError(_("Invalid or unauthorized API token. Access was rejected by TalentHub (HTTP %s).") % response.status_code)
        elif response.status_code == 404:
            raise UserError(_("Position not found. TalentHub could not find any position for this token (HTTP 404)."))
        elif response.status_code >= 500:
            raise UserError(_("TalentHub server error (HTTP %s). Please check the TalentHub server status.") % response.status_code)
        elif not response.ok:
            raise UserError(_("TalentHub returned unexpected status (HTTP %s): %s") % (response.status_code, response.text[:200]))

        # Validate JSON response
        try:
            data = response.json()
        except Exception:
            _logger.error("Invalid JSON response received from TalentHub")
            raise UserError(_("Invalid JSON response received from TalentHub. Please ensure the endpoint returns valid JSON."))

        if not isinstance(data, dict):
            raise UserError(_("Invalid response structure: expected a JSON object."))

        # Support both wrapped { "position": { ... } } and direct { "id": ..., "title": ... } formats
        position_data = data.get('position')
        if not isinstance(position_data, dict):
            if 'id' in data and ('title' in data or 'name' in data):
                position_data = data
            else:
                raise UserError(_("Invalid response structure: missing or malformed 'position' object."))

        ext_id = str(position_data.get('id') or position_data.get('positionId') or '').strip()
        title = (position_data.get('title') or position_data.get('name') or position_data.get('positionTitle') or '').strip()

        if not ext_id or not title:
            raise UserError(_("Invalid position data: 'id' and 'title' are required in position response."))

        attributes_data = data.get('attributes') or data.get('attributeResults') or []
        if not isinstance(attributes_data, list):
            attributes_data = []

        # Find or create Position (Upsert logic)
        position_env = self.env['talenthub.position']
        position = position_env.search([
            ('external_position_id', '=', ext_id),
            ('source_base_url', '=', base_url),
        ], limit=1)

        position_vals = {
            'name': title,
            'external_position_id': ext_id,
            'source_base_url': base_url,
            'imported_at': fields.Datetime.now(),
        }

        if position:
            position.write(position_vals)
            # Remove existing attribute results to avoid stale or duplicated aggregates
            position.attribute_result_ids.unlink()
        else:
            position = position_env.create(position_vals)

        # Build attribute records safely
        attribute_records = []
        for attr in attributes_data:
            if not isinstance(attr, dict):
                continue

            attr_name = (attr.get('name') or attr.get('title') or 'Unnamed Attribute').strip()
            attr_type = (attr.get('type') or attr.get('dataType') or 'Unknown').strip()
            attr_id = str(attr.get('id') or attr.get('attributeId') or '').strip()
            agg = attr.get('aggregation') or attr.get('aggregate') or attr.get('aggregatedResult') or {}
            if not isinstance(agg, dict):
                agg = {}

            # Parse safe counts and metrics
            sample_count = self._safe_int(agg.get('count') or agg.get('sampleCount'))

            # Numeric metrics
            avg_val = self._safe_float(agg.get('average') if agg.get('average') is not None else agg.get('averageValue'))
            min_val = self._safe_float(agg.get('minimum') if agg.get('minimum') is not None else agg.get('minValue'))
            max_val = self._safe_float(agg.get('maximum') if agg.get('maximum') is not None else agg.get('maxValue'))

            # Boolean metrics
            true_count = self._safe_int(agg.get('trueCount'))
            false_count = self._safe_int(agg.get('falseCount'))

            # Popular values (OneOfMany / Dropdown / String)
            popular_vals_commands = []
            popular_list = agg.get('popularValues') or agg.get('distribution') or agg.get('popular_values')
            if isinstance(popular_list, list):
                for item in popular_list:
                    if isinstance(item, dict):
                        val_str = str(item.get('value') or item.get('key') or '').strip()
                        if val_str:
                            val_cnt = self._safe_int(item.get('count'))
                            popular_vals_commands.append((0, 0, {
                                'value': val_str,
                                'count': val_cnt,
                            }))
            elif isinstance(popular_list, dict):
                # In case backend returns { "B2": 2, "C1": 1 }
                for val_str, val_cnt in popular_list.items():
                    popular_vals_commands.append((0, 0, {
                        'value': str(val_str),
                        'count': self._safe_int(val_cnt),
                    }))

            attr_dict = {
                'position_id': position.id,
                'external_attribute_id': attr_id,
                'name': attr_name,
                'data_type': attr_type,
                'sample_count': sample_count,
                'average_value': avg_val,
                'min_value': min_val,
                'max_value': max_val,
                'true_count': true_count,
                'false_count': false_count,
                'popular_value_ids': popular_vals_commands,
            }
            attribute_records.append(attr_dict)

        if attribute_records:
            self.env['talenthub.attribute.result'].create(attribute_records)

        # Return action to navigate directly to the imported position
        return {
            'type': 'ir.actions.act_window',
            'name': position.name,
            'res_model': 'talenthub.position',
            'res_id': position.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @staticmethod
    def _safe_int(val):
        try:
            return int(val) if val is not None else 0
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _safe_float(val):
        try:
            return float(val) if val is not None else 0.0
        except (ValueError, TypeError):
            return 0.0
