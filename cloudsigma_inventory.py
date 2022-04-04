from typing import Any, List, Mapping
from ansible.errors import AnsibleError
from ansible.plugins.inventory import BaseInventoryPlugin
from ansible.plugins.inventory import Cacheable
from ansible.plugins.inventory import Constructable

import cloudsigma


DOCUMENTATION = r"""
    name: cloudsigma_inventory
    plugin_type: inventory
    short_description: Cloudisgma inventory source
    requirements:
        - pycloudsigma
    extends_documentation_fragment:
        - inventory_cache
        - constructed
    description:
        - Get inventory hosts from Cloudsigma cloud.
        - Uses a YAML configuration file that ends with C(cloudsigma.{yml|yaml}).
    author:
        - Ivan Zubok
    options:
        plugin:
            description: Token that ensures this is a source file for the plugin
            required: true
            choices: ['cloudsigma_inventory']
        cloudsigma_region:
            description: >
                Cloudsigma L(region code,https://docs.cloudsigma.com/en/latest/general.html\#api-endpoint)
            type: string
            required: True
        cloudsigma_username:
            description: Cloudsigma account username
            type: string
            env:
                - name: CLOUDSIGMA_USERNAME
        cloudsigma_password:
            description: Cloudsigma account password
            type: string
            env:
                - name: CLOUDSIGMA_PASSWORD
        group_tag_prefix:
            required: False
            description: >
                The plugin will create groups from tags starting with C(group_tag_prefix)
                and add hosts labelled with these tags. The prefix group will be removed
                from the resulting group name. Example: C(group_tag_prefix) is set to C("role_")
                and there are tags named C("role_bastion") and C("role_load_balancer"),
                this will result in C("bastion") and C("load_balancer") groups created.
                A host labelled with multiple role tags will be added to multiple groups
                If omitted, no groups will be created, all hosts will be added to C(all)
        include_running_only:
            type: bool
            default: Yes
            description: >
                When set to C(Yes), only running instances will be added to the inventory.
        include_tags:
            type: list
            elements: string
            description: >
                If specified, only hosts tagged with specific tags will be added to the inventory.
        exclude_tags:
            type: list
            elements: string
            description: >
                If specified, hosts tagged with specific tags will be excluded from the inventory.

"""


_CLOUDSIGMA_REGIONS = {
    "crk": {"location": "Clark, Philippines", "http_endpoint": "https://crk.cloudsigma.com/api/2.0/"},
    "dub": {"location": "Dublin, Ireland", "http_endpoint": "https://ec.servecentric.com/api/2.0/"},
    "fra": {"location": "Frankfurt, Germany", "http_endpoint": "https://fra.cloudsigma.com/api/2.0/"},
    "gva": {"location": "Geneva, Switzerland", "http_endpoint": "https://gva.cloudsigma.com/api/2.0/"},
    "hnl": {"location": "Honolulu, United States", "http_endpoint": "https://hnl.cloudsigma.com/api/2.0/"},
    "lla": {"location": "Boden, Sweden", "http_endpoint": "https://cloud.hydro66.com/api/2.0/"},
    "mel": {"location": "Melbourne, Australia", "http_endpoint": "https://mel.cloudsigma.com/api/2.0/"},
    "mnl": {"location": "Manila, Philippines", "http_endpoint": "https://mnl.cloudsigma.com/api/2.0/"},
    "mnl2": {"location": "Manila-2, Philippines", "http_endpoint": "https://mnl2.cloudsigma.com/api/2.0/"},
    "per": {"location": "Perth, Australia", "http_endpoint": "https://per.cloudsigma.com/api/2.0/"},
    "ruh": {"location": "Riyadh, Saudi Arabia", "http_endpoint": "https://ruh.cloudsigma.com/api/2.0/"},
    "sjc": {"location": "San Jose, United States", "http_endpoint": "https://sjc.cloudsigma.com/api/2.0/"},
    "tyo": {"location": "Tokyo, Japan", "http_endpoint": "https://tyo.cloudsigma.com/api/2.0/"},
    "wdc": {"location": "Washington DC, United States", "http_endpoint": "https://wdc.cloudsigma.com/api/2.0/"},
    "zrh": {"location": "Zurich, Switzerland", "http_endpoint": "https://zrh.cloudsigma.com/api/2.0/"},
}


class InventoryModule(BaseInventoryPlugin, Constructable, Cacheable):
    NAME = "cloudsigma_inventory"

    def __init__(self):
        self._tags_uuid_map: Mapping
        super(InventoryModule, self).__init__()

    def verify_file(self, path: str):
        """return true/false if this is possibly a valid file for this plugin to consume"""
        return super(InventoryModule, self).verify_file(path) and path.endswith(("cloudsigma.yaml", "cloudsigma.yml"))

    def _get_server_tag_names(self, server: Any) -> List[str]:
        return [self._tags_uuid_map[tag["uuid"]]["name"] for tag in server["tags"]]

    def parse(self, inventory, loader, path, cache=True):

        # call base method to ensure properties are available for use with other helper methods
        super(InventoryModule, self).parse(inventory, loader, path, cache)

        # this method will parse 'common format' inventory sources and
        # update any options declared in DOCUMENTATION as needed
        self._read_config_data(path)

        region = self.get_option("cloudsigma_region").lower()
        if not region in _CLOUDSIGMA_REGIONS:
            raise (AnsibleError(f"Invalid region: {region}"))

        endpoint = _CLOUDSIGMA_REGIONS[region]["http_endpoint"]
        username = self.get_option("cloudsigma_username")
        password = self.get_option("cloudsigma_password")

        group_tag_prefix = self.get_option("group_tag_prefix")
        include_running_only = self.get_option("include_running_only")

        include_tags = self.get_option("include_tags")
        exclude_tags = self.get_option("exclude_tags")

        servers = cloudsigma.resource.Server(api_endpoint=endpoint, username=username, password=password)
        tags = cloudsigma.resource.Tags(api_endpoint=endpoint, username=username, password=password)

        tag_list = tags.list()
        self._tags_uuid_map = {tag["uuid"]: tag for tag in tag_list}

        server_list = servers.list_detail()

        if group_tag_prefix is not None:
            for tag in tag_list:
                tag_name = tag["name"]
                if tag_name.startswith(group_tag_prefix):
                    inventory.add_group(tag_name[len(group_tag_prefix) :])

        server: cloudsigma.resource.Server
        for server in server_list:
            if include_running_only and server["status"] != "running":
                continue
            hostname = server["name"]
            tag_names = self._get_server_tag_names(server)

            if include_tags is not None:
                if not any(tag in include_tags for tag in tag_names):
                    continue

            if exclude_tags is not None:
                if any(tag in exclude_tags for tag in tag_names):
                    continue

            group_assigned = False
            for tag_name in tag_names:
                if tag_name.startswith(group_tag_prefix):
                    inventory.add_host(hostname, group=tag_name[len(group_tag_prefix) :])
                    group_assigned = True
            if not group_assigned:
                inventory.add_host(hostname)

            host_vars = {}
            host_vars["public_ip_address"] = server["nics"][0]["runtime"]["ip_v4"]["uuid"]
            host_vars["tags"] = tag_names
            host_vars["server_name"] = hostname
            if server["meta"]:
                host_vars["meta"] = server["meta"]

            for var_name, var_value in host_vars.items():
                self.inventory.set_variable(hostname, var_name, var_value)

            # Determines if composed variables or groups using nonexistent variables is an error
            strict = self.get_option("strict")

            # Add variables created by the user's Jinja2 expressions to the host
            self._set_composite_vars(self.get_option("compose"), host_vars, hostname, strict=True)

            # The following two methods combine the provided variables dictionary with the latest host variables
            # Using these methods after _set_composite_vars() allows groups to be created with the composed variables
            self._add_host_to_composed_groups(self.get_option("groups"), host_vars, hostname, strict=strict)
            self._add_host_to_keyed_groups(self.get_option("keyed_groups"), host_vars, hostname, strict=strict)
