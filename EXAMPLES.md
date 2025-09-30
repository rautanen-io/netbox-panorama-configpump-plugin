# NetBox Panorama ConfigPump Examples

This guide walks through a complete example of using the NetBox Panorama ConfigPump plugin to generate, diff, and push configuration to Palo Alto Networks Panorama.

If you have not enabled and configured the plugin yet, start with the [README](README.md) and [CONFIGURATION](CONFIGURATION.md) guides.

### Prerequisites
- Ensure the plugin is enabled and configured. See [CONFIGURATION.md](CONFIGURATION.md).
- Panorama API token(s) available via `PLUGINS_CONFIG["netbox_panorama_configpump_plugin"]["tokens"]`.
- Create NetBox `Device` objects for the firewalls you want to keep in sync.

1. Create the devices in NetBox.
<div align="center">
<img src="images/devices.png" alt="NetBox devices list" style="max-width: 100%; height: auto;" />
</div>

2. Create a Config Template that defines the Panorama API payload using XML and Jinja. This template generates an XML configuration tailored to each firewall. See the [sample template](examples/v11.1.6/template_example.xml.j2) for reference. The template typically iterates over device interfaces to build the XML required by Panorama. Later, associate this Config Template with a NetBox object that is also related to your devices (e.g., a `Platform` such as PAN-OS).
<div align="center">
<img src="images/editing_config_template.png" alt="Editing a Config Template in NetBox" style="max-width: 100%; height: auto;" />
</div>

3. Assign the Config Template to a NetBox object associated with the firewalls (in this example, the PAN-OS `Platform`). Ensure this platform is assigned to the firewall devices you created. Note: Config Templates can also be assigned to `Device Roles` or directly to individual `Device` objects.
<div align="center">
<img src="images/editing_platform.png" alt="Assigning Config Template to Platform" style="max-width: 100%; height: auto;" />
</div>

4. Create a Connection Template to define how to connect to a Panorama instance.
<div align="center">
<img src="images/editing_connection_template.png" alt="Editing a Connection Template" style="max-width: 100%; height: auto;" />
</div>

5. Create a Connection and assign NetBox devices (firewalls) to it via the Connection Template.
<div align="center">
<img src="images/editing_connection.png" alt="Creating a Connection and assigning devices" style="max-width: 100%; height: auto;" />
</div>

6. Open the Connection. You should see generated XML ready to upload to Panorama. Pull the current candidate configuration from Panorama to refresh the diff.
<div align="center">
<img src="images/new_connection.png" alt="Viewing pending changes for the Connection" style="max-width: 100%; height: auto;" />
</div>

7. After the pull, some lines may show as updated (not only new lines). Open the diff view to understand the changes.
<div align="center">
<img src="images/first_pull.png" alt="Pulling candidate configuration from Panorama" style="max-width: 100%; height: auto;" />
</div>

8. The diff view may reveal empty `template` and `device-group` elements in Panorama. The plugin updates these XML elements as needed.
<div align="center">
<img src="images/first_diff.png" alt="Diff view showing empty template and device-group" style="max-width: 100%; height: auto;" />
</div>

9. Push the configuration to Panorama. This stages changes in Panorama’s candidate configuration.
<div align="center">
<img src="images/first_push.png" alt="Initiating a push to Panorama" style="max-width: 100%; height: auto;" />
</div>

10. Confirm the push operation. After you confirm, the candidate configuration in Panorama is updated—changes are staged but not yet committed or active. Commit in Panorama to apply.

For each device included in the connection, the plugin performs the following steps:
   1. Uploads an XML file to Panorama named `<prefix>_<device_name>.xml` (for example, `netbox-panorama_firewall1.xml`).
   2. For every `template` element in the XML, it partially updates the configuration at the XPath: `devices/entry[@name='localhost.localdomain']/template/entry[@name='<template name>']`.
   3. For every `device-group` element in the XML, it partially updates the configuration at the XPath: `devices/entry[@name='localhost.localdomain']/device-group/entry[@name='<device-group name>']`.
   4. Retrieves (pulls) the updated candidate configuration from Panorama to ensure the changes were applied as expected.

<div align="center">
<img src="images/confirm_push.png" alt="Confirming the push to Panorama" style="max-width: 100%; height: auto;" />
</div>

11. If everything worked as expected, you should see no remaining diff.
<div align="center">
<img src="images/after_push.png" alt="No diff after successful push" style="max-width: 100%; height: auto;" />
</div>

12. Make a change in NetBox, for example by deleting a sub-interface from a firewall.
<div align="center">
<img src="images/delete_sub_interface.png" alt="Adding a sub-interface in NetBox" style="max-width: 100%; height: auto;" />
</div>

13. The change is reflected in the diff view.
<div align="center">
<img src="images/delete_sub_interface_diff.png" alt="Diff showing the new sub-interface" style="max-width: 100%; height: auto;" />
</div>

14. Push the update to Panorama again.
<div align="center">
<img src="images/second_push.png" alt="Pushing incremental updates to Panorama" style="max-width: 100%; height: auto;" />
</div>

15. After the update, there should be no diff.
<div align="center">
<img src="images/after_second_push.png" alt="No diff after second push" style="max-width: 100%; height: auto;" />
</div>

16. Verify the results in Panorama. You should see the new file under: Panorama → Operations → Export named Panorama configuration snapshot.
<div align="center">
<img src="images/panorama_files.png" alt="Panorama snapshots files" style="max-width: 100%; height: auto;" />
</div>

17. Under Network → Interfaces, you should see the uploaded Templates and configuration matching the data in NetBox.
<div align="center">
<img src="images/panorama_template.png" alt="Templates applied in Panorama" style="max-width: 100%; height: auto;" />
</div>

18. Under Objects → Addresses, you should see the uploaded Device Groups and configuration matching the Config Template data (dynamic data from NetBox can be mapped here as needed).
<div align="center">
<img src="images/panorama_device_group.png" alt="Device Groups applied in Panorama" style="max-width: 100%; height: auto;" />
</div>
