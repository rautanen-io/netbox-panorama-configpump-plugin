# Netbox Panorama ConfigPump Configuration

This document provides detailed information about the Netbox Panorama ConfigPump Plugin configuration options.

## Plugin Configuration

The plugin is configured through NetBox's `PLUGINS_CONFIG` setting. Here's a detailed explanation of each configuration option:
```python
PLUGINS_CONFIG = {
    "netbox_panorama_configpump_plugin": {
        "default_request_timeout": 60,  # seconds
        "default_filename_prefix": "netbox-panorama",
        "ignore_ssl_warnings": True,
        "tokens": {
            "PANO1_TOKEN": os.environ.get("PANO1_TOKEN"),
            "PANO2_TOKEN": os.environ.get("PANO2_TOKEN"),
        },
        "top_level_menu": True,  # How plugin menu is displayed
    }
}
```

### Configuration Fields

| Setting                   | Default             | Description |
|---------------------------|---------------------|-------------|
| `default_request_timeout` | 60                  | The default timeout (in seconds) for Panorama API requests. |
| `default_filename_prefix` | `'netbox-panorama'` | The default prefix for configuration files generated and uploaded by the plugin. File names will follow the format `<prefix>_<device_name>.xml` (for example, `netbox-panorama_firewall1.xml`). |
| `ignore_ssl_warnings`     | False               | If set to `True`, SSL certificate warnings will be ignored when communicating with the Panorama API. Use with caution, especially in production environments. |
| `tokens`                  | `{}`                | A dictionary containing Panorama authentication tokens as key-value pairs. The keys correspond to token names referenced in the Connection Template edit and create views. **Note:** For security, do not store sensitive tokens directly in `configuration.py`. Instead, set them as environment variables and load them securely at runtime (e.g., using Kubernetes secrets, AWS Parameter Store, or a vault service). |
| `top_level_menu`          | False               | If `True`, the plugin will appear in the top-level NetBox navigation menu. |
