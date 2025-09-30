"""Template code for device config sync status extra buttons."""

DEVICE_CONFIG_SYNC_STATUS_ACTIONS = """
{% load helpers %}
{% if perms.netbox_panorama_configpump_plugin.change_deviceconfigsyncstatus %}
  <a href="{% url 'plugins:netbox_panorama_configpump_plugin:deviceconfigsyncstatus_pull_config' pk=record.pk %}"
     class="btn btn-primary btn-sm"
     title="Pull configuration from Panorama">
    <i class="mdi mdi-download" aria-hidden="true"></i>
  </a>
  <a href="{% url 'plugins:netbox_panorama_configpump_plugin:deviceconfigsyncstatus_push_config' pk=record.pk %}"
     class="btn btn-success btn-sm"
     title="Push configuration to Panorama">
    <i class="mdi mdi-upload" aria-hidden="true"></i>
  </a>
{% endif %}
"""

SYNC_JOB_STATUS_BADGE = """
{% load helpers %}
{% if record.sync_job %}
  <a href="{{ record.sync_job.get_absolute_url }}" class="text-decoration-none">
    {% badge record.sync_job.get_status_display bg_color=record.sync_job.get_status_color %}
  </a>
{% else %}
  <span class="text-muted">No job</span>
{% endif %}
"""
