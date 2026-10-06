FROM odoo:19.0

USER root

# Ensure requests and psycopg2 libraries are available
RUN pip3 install --no-cache-dir requests psycopg2-binary --break-system-packages 2>/dev/null || true

# Copy custom addon into Odoo extra-addons directory
COPY addons/talenthub_integration /mnt/extra-addons/talenthub_integration

# Ensure data directory and permissions are set for filestore & web assets
RUN mkdir -p /var/lib/odoo/filestore /var/lib/odoo/sessions \
    && chown -R odoo:odoo /var/lib/odoo /mnt/extra-addons /etc/odoo

# Copy and set execution permissions for the custom entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER odoo

EXPOSE 8069

ENTRYPOINT ["/entrypoint.sh"]
CMD ["odoo"]
