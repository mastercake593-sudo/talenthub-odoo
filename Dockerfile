FROM odoo:19.0

USER root

# Ensure requests library is installed for HTTP API integrations
RUN pip3 install --no-cache-dir requests --break-system-packages 2>/dev/null || true

# Copy custom addon into Odoo extra-addons directory
COPY addons/talenthub_integration /mnt/extra-addons/talenthub_integration

# Copy and set execution permissions for the custom entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && chown -R odoo:odoo /mnt/extra-addons

USER odoo

EXPOSE 8069

ENTRYPOINT ["/entrypoint.sh"]
CMD ["odoo"]
