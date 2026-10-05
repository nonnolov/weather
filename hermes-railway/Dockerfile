FROM nousresearch/hermes-agent:latest

# Run after upstream volume setup and before profile reconciliation.
COPY bootstrap.sh /etc/cont-init.d/010-weather-bootstrap
RUN chmod 0755 /etc/cont-init.d/010-weather-bootstrap

# Preserve the upstream ENTRYPOINT/s6 lifecycle.
CMD ["gateway", "run"]
