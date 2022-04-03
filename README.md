## Dynamic Ansible invntory plugin for Cloudsigma
---
## Installation notes

* Clone the repository

* Set environment variables so that Ansible will recognize the plugin
  * ```export ANSIBLE_INVENTORY_PLUGINS=/full/path/to/gatewayfm/ansible-inventory-cloudsigma/```
  * ```export ANSIBLE_LIBRARY=/full/path/to/ansible-inventory-cloudsigma```
  * ```export ANSIBLE_INVENTORY_ENABLED=cloudsigma_inventory```

Credentials are provided by CLOUDSIGMA_USERNAME and CLOUDSIGMA_PASSWORD environment variables.
This can be overriden by explicitry specifying cloudsigma_username and cloudsigma_password in an inventory file.
