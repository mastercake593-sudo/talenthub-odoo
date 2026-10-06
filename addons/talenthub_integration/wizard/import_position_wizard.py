# -*- coding: utf-8 -*-
import logging
import requests
from dateutil import parser as dt_parser
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
        help='Base URL of the TalentHub service, e.g. https://cvsystem-jtnh.onrender.com',
    )
    api_token = fields.Char(
        string='Position API Token',
        required=True,
        help='Per-Position API token issued by TalentHub (e.g. th_pos_...).',
    )

    def action_import_position(self):
        """Fetches position aggregates from TalentHub API and upserts into local Odoo database."""
        self.ensure_one()

        raw_url = (self.base_url or '').strip()
        api_token = (self.api_token or '').strip()

        if not raw_url:
            raise UserError(_("Please provide a valid TalentHub Base URL."))
        if not api_token:
            raise UserError(_("Please provide a Position API Token."))

        # Clean up base URL if the user pasted a full endpoint or has trailing slashes
        clean_url = raw_url.rstrip('/')
        if '/api/integrations/odoo' in clean_url:
            clean_url = clean_url.split('/api/integrations/odoo')[0]
        elif clean_url.endswith('/api'):
            clean_url = clean_url[:-4]
        base_url = clean_url.rstrip('/')

        masked_token = f"{api_token[:4]}***" if len(api_token) > 4 else "***"
        _logger.info("Importing TalentHub position from %s with token prefix %s", base_url, masked_token)

        # Standard headers according to contract
        headers = {
            'X-API-Token': api_token,
            'Authorization': f'Bearer {api_token}',
            'Accept': 'application/json',
            'User-Agent': 'Odoo-TalentHub-Integration/19.0',
        }

        # Build primary target endpoint
        target_endpoint = f"{base_url}/api/integrations/odoo/position-results"
        fallback_endpoint = f"{base_url}/api/integrations/odoo/position"

        response = None
        for endpoint in [target_endpoint, fallback_endpoint]:
            try:
                resp = requests.get(endpoint, headers=headers, timeout=TIMEOUT_SECONDS)
                if resp.status_code == 404 and endpoint != fallback_endpoint:
                    continue
                response = resp
                break
            except requests.exceptions.Timeout:
                _logger.error("Timeout connecting to TalentHub at %s", endpoint)
                raise UserError(_("Connection timed out while reaching TalentHub at %s.") % base_url)
            except requests.exceptions.RequestException as exc:
                _logger.error("Network error reaching TalentHub at %s: %s", endpoint, str(exc))
                raise UserError(_("Network failure communicating with TalentHub: %s") % str(exc))

        if response is None:
            raise UserError(_("Failed to establish connection with TalentHub at %s.") % base_url)

        # Validate HTTP status codes
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
            _logger.error("Invalid JSON response received from %s (HTTP %s): %s", response.url, response.status_code, response.text[:500])
            snippet = response.text[:300].strip() or '[Empty response body]'
            raise UserError(_(
                "Invalid JSON response received from TalentHub.\n\n"
                "Endpoint: %s\n"
                "HTTP Status: %s (%s)\n"
                "Content-Type: %s\n\n"
                "Response: %s"
            ) % (
                response.url,
                response.status_code,
                response.reason,
                response.headers.get('content-type', 'unknown'),
                snippet
            ))

        if not isinstance(data, dict):
            raise UserError(_("Invalid response structure: expected a JSON object."))

        # Extract top-level or nested position data
        # Contract: { "positionId": "...", "title": "...", "cvCount": 5, "generatedAt": "...", "attributes": [...] }
        ext_id = str(
            data.get('positionId') or
            (data.get('position') and data['position'].get('id')) or
            data.get('id') or
            ''
        ).strip()

        title = str(
            data.get('title') or
            (data.get('position') and data['position'].get('title')) or
            data.get('name') or
            ''
        ).strip()

        if not ext_id or not title:
            raise UserError(_("Invalid position response: 'positionId' and 'title' are required."))

        cv_count = self._safe_int(data.get('cvCount'))
        generated_at = self._parse_iso_datetime(data.get('generatedAt'))

        attributes_data = data.get('attributes') or data.get('attributeResults') or []
        if not isinstance(attributes_data, list):
            attributes_data = []

        # Upsert Position
        position_env = self.env['talenthub.position']
        position = position_env.search([
            ('external_position_id', '=', ext_id),
            ('source_base_url', '=', base_url),
        ], limit=1)

        position_vals = {
            'name': title,
            'external_position_id': ext_id,
            'source_base_url': base_url,
            'cv_count': cv_count,
            'generated_at': generated_at,
            'imported_at': fields.Datetime.now(),
        }

        if position:
            position.write(position_vals)
            # Remove old attribute results to refresh completely
            position.attribute_result_ids.unlink()
        else:
            position = position_env.create(position_vals)

        # Parse and build attribute records
        attribute_records = []
        for attr in attributes_data:
            if not isinstance(attr, dict):
                continue

            attr_id = str(attr.get('attributeId') or attr.get('id') or '').strip()
            attr_title = (attr.get('title') or attr.get('name') or 'Unnamed Attribute').strip()
            attr_type = (attr.get('type') or attr.get('dataType') or 'Unknown').strip()
            sample_count = self._safe_int(
                attr.get('nonEmptyCount') if attr.get('nonEmptyCount') is not None
                else attr.get('sampleCount')
            )

            agg = attr.get('aggregation') or attr.get('aggregate') or {}
            if not isinstance(agg, dict):
                agg = {}

            agg_kind = str(agg.get('kind') or '').strip().lower()

            # Numeric metrics
            avg_val = None
            min_val = None
            max_val = None

            # Boolean metrics
            true_count = 0
            false_count = 0
            true_pct = 0.0

            # Date / Period metrics
            date_min = None
            date_max = None
            summary_info = None

            popular_vals_commands = []

            # 1. Numeric aggregation
            if agg_kind == 'numeric' or attr_type.lower() == 'numeric':
                avg_val = self._safe_float(agg.get('average') if agg.get('average') is not None else agg.get('averageValue'))
                min_val = self._safe_float(agg.get('min') if agg.get('min') is not None else agg.get('minimum'))
                max_val = self._safe_float(agg.get('max') if agg.get('max') is not None else agg.get('maximum'))

            # 2. TopValues / Categorical aggregation
            elif agg_kind in ('topvalues', 'top_values', 'values') or attr_type.lower() in ('dropdown', 'oneofmany', 'string'):
                vals_list = agg.get('values') or agg.get('popularValues') or []
                if isinstance(vals_list, list):
                    for v in vals_list:
                        if isinstance(v, dict):
                            val_str = str(v.get('value') or v.get('name') or '').strip()
                            if val_str:
                                val_cnt = self._safe_int(v.get('count'))
                                popular_vals_commands.append((0, 0, {
                                    'value': val_str,
                                    'count': val_cnt,
                                }))

            # 3. Boolean aggregation
            elif agg_kind == 'boolean' or attr_type.lower() == 'boolean':
                true_count = self._safe_int(agg.get('trueCount'))
                false_count = self._safe_int(agg.get('falseCount'))
                true_pct = self._safe_float(agg.get('truePercentage'))

            # 4. Date aggregation
            elif agg_kind == 'date' or attr_type.lower() == 'date':
                date_min = str(agg.get('min') or '')
                date_max = str(agg.get('max') or '')

            # 5. Period aggregation
            elif agg_kind == 'period' or attr_type.lower() == 'period':
                date_min = str(agg.get('minStart') or '')
                date_max = str(agg.get('maxEnd') or '')

            # 6. TextSummary aggregation
            elif agg_kind in ('textsummary', 'text_summary'):
                ne_cnt = self._safe_int(agg.get('nonEmptyCount'))
                if ne_cnt and not sample_count:
                    sample_count = ne_cnt
                summary_info = f"Non-Empty: {sample_count}"

            # 7. Image aggregation
            elif agg_kind == 'image' or attr_type.lower() == 'image':
                up_cnt = self._safe_int(agg.get('uploadedCount'))
                summary_info = f"Uploaded: {up_cnt}"

            # Fallback for any other metric structure
            else:
                if agg.get('average') is not None:
                    avg_val = self._safe_float(agg.get('average'))
                if agg.get('min') is not None:
                    min_val = self._safe_float(agg.get('min'))
                if agg.get('max') is not None:
                    max_val = self._safe_float(agg.get('max'))

            attr_dict = {
                'position_id': position.id,
                'external_attribute_id': attr_id,
                'name': attr_title,
                'data_type': attr_type,
                'aggregation_kind': agg_kind or attr_type.lower(),
                'sample_count': sample_count,
                'average_value': avg_val if avg_val is not None else 0.0,
                'min_value': min_val if min_val is not None else 0.0,
                'max_value': max_val if max_val is not None else 0.0,
                'true_count': true_count,
                'false_count': false_count,
                'true_percentage': true_pct,
                'date_min': date_min or False,
                'date_max': date_max or False,
                'summary_info': summary_info or False,
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

    @staticmethod
    def _parse_iso_datetime(val):
        if not val:
            return None
        try:
            dt = dt_parser.parse(val)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            return None
