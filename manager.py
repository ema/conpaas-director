import os

import common
common.extend_path()

from conpaas.core.controller import Controller
from conpaas.core.misc import file_get_contents

class ManagerController(Controller):

    def _get_context_file(self, service_name, cloud):
        """Override default _get_context_file. Here we generate the context
        file for managers rather than for agents."""
        config_parser = self._Controller__config_parser

        frontend = config_parser.get('director', 'DIRECTOR_URL')
        conpaas_home = config_parser.get('conpaas', 'ROOT_DIR')
        cloud_scripts_dir = conpaas_home + '/scripts/cloud'
        cloud_cfg_dir = conpaas_home + '/config/cloud'
        mngr_cfg_dir = conpaas_home + '/config/manager/'
        mngr_scripts_dir = conpaas_home + '/scripts/manager/'

        # Values to be passed to the context file template
        tmpl_values = {}

        # Get contextualization script for the cloud
        tmpl_values['cloud_script'] = file_get_contents(
            cloud_scripts_dir + '/' + cloud)

        # Get manager setup file
        mngr_setup = file_get_contents(mngr_scripts_dir + '/manager-setup')
        tmpl_values['mngr_setup'] = mngr_setup.replace('%FRONTEND_URL%', 
            frontend)

        # Get cloud config file 
        tmpl_values['cloud_cfg'] = file_get_contents(
            cloud_cfg_dir + '/' + cloud + '.cfg')

        # Get manager config file 
        mngr_cfg = file_get_contents(mngr_cfg_dir + '/default-manager.cfg')

        # Add service-specific config file (if any)
        mngr_service_cfg = mngr_cfg_dir + '/' + service_name + '-manager.cfg'
        if os.path.isfile(mngr_service_cfg):
            mngr_cfg += file_get_contents(mngr_service_cfg)

        # Modify manager config file setting the required variables
        mngr_cfg = mngr_cfg.replace('%FRONTEND_URL%', frontend)
        mngr_cfg = mngr_cfg.replace('%CONPAAS_SERVICE_TYPE%', service_name)
        mngr_cfg = mngr_cfg.replace('%CONPAAS_SERVICE_ID%', 
            config_parser.get("manager", "FE_SERVICE_ID"))
        mngr_cfg = mngr_cfg.replace('%CONPAAS_USER_ID%', 
            config_parser.get("manager", "FE_USER_ID"))
        tmpl_values['mngr_cfg'] = mngr_cfg

        # Add default manager startup script
        tmpl_values['mngr_start_script'] = file_get_contents(
            mngr_scripts_dir + '/default-manager-start')
        # Or the service-specific one (if any)
        mngr_startup_scriptname = mngr_scripts_dir + '/' + service_name + '-manager-start'
        if os.path.isfile(mngr_startup_scriptname):
            tmpl_values['mngr_start_script'] = file_get_contents(
                mngr_startup_scriptname)

        # Get key and a certificate from CA
        #mngr_certs = self._get_certificate()
        tmpl_values['mngr_certs_cert'] = "foo"
        tmpl_values['mngr_certs_key'] = "bar"
        tmpl_values['mngr_certs_ca_cert'] = "foo_bar"
        
        # Concatenate the files
        return """%(cloud_script)s

cat <<EOF > /tmp/ca_cert.pem
%(mngr_certs_cert)s
EOF

cat <<EOF > /tmp/key.pem
%(mngr_certs_key)s
EOF

cat <<EOF > /tmp/ca_cert.pem
%(mngr_certs_ca_cert)s
EOF

%(mngr_setup)s

cat <<EOF > $ROOT_DIR/config.cfg
%(cloud_cfg)s
%(mngr_cfg)s
EOF

%(mngr_start_script)s""" % tmpl_values

def start(service_name, service_id, user_id):
    """Start a manager for the given service_name, service_id and user_id"""
    # Add manager configuration
    config_parser = common.config
    config_parser.add_section("manager")
    config_parser.set("manager", "FE_SERVICE_ID", service_id)
    config_parser.set("manager", "FE_USER_ID", user_id)
    config_parser.set("manager", "FE_CREDIT_URL", 
        config_parser.get('director', 'DIRECTOR_URL') + "/credit")
    config_parser.set("manager", "FE_TERMINATE_URL", 
        config_parser.get('director', 'DIRECTOR_URL') + "/terminate")
    config_parser.set("manager", "FE_CA_URL", 
        config_parser.get('director', 'DIRECTOR_URL') + "/ca")

    # Create a new controller
    controller = ManagerController(config_parser)
    # Create a context file for the specific service
    controller.generate_context(service_name)

if __name__ == "__main__":
    start("php", "1", "1")

#def is_dummy(config_parser):
#    return config_parser.get("iaas", "DRIVER") == "dummy"
#
#if True or is_dummy(config_parser):
#    controller._Controller__deduct_credit = lambda x: True
#
## test_manager(ip, port) not implemented yet. Just return True.
#controller.create_nodes(1, lambda ip, port: True, None)
#
#for vm in controller.list_vms().values():
#    print vm
#
#if is_dummy(config_parser):
#    for reservation_timer in controller._Controller__reservation_map.values():
#        reservation_timer.stop()
