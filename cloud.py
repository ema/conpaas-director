import os

import x509cert
import common
common.extend_path()

from conpaas.core.controller import Controller
from conpaas.core.misc import file_get_contents

class ManagerController(Controller):

    def _get_certificate(self, email, cn, org):
        config_parser = self._Controller__config_parser

        user_id = config_parser.get("manager", "FE_USER_ID")
        service_id = config_parser.get("manager", "FE_SERVICE_ID")
        cert_dir = config_parser.get('conpaas', 'CERT_DIR')

        return x509cert.generate_certificate(cert_dir, user_id, service_id, 
                                             "manager", email, cn, org)

    def _get_context_file(self, service_name, cloud):
        """Override default _get_context_file. Here we generate the context
        file for managers rather than for agents."""
        config_parser = self._Controller__config_parser

        conpaas_home = config_parser.get('conpaas', 'ROOT_DIR')

        cloud_scripts_dir = os.path.join(conpaas_home, 'scripts', 'cloud')
        mngr_scripts_dir  = os.path.join(conpaas_home, 'scripts', 'manager')
        mngr_cfg_dir      = os.path.join(conpaas_home, 'config', 'manager')

        frontend = config_parser.get('director', 'DIRECTOR_URL')

        # Values to be passed to the context file template
        tmpl_values = {}

        # Get contextualization script for the cloud
        tmpl_values['cloud_script'] = file_get_contents(
            os.path.join(cloud_scripts_dir, cloud))

        # Get manager setup file
        mngr_setup = file_get_contents(
            os.path.join(mngr_scripts_dir,'manager-setup'))

        tmpl_values['mngr_setup'] = mngr_setup.replace('%FRONTEND_URL%', 
            frontend)

        # Get cloud config values from director.cfg
        tmpl_values['cloud_cfg'] = "[iaas]\n"
        for key, value in config_parser.items("iaas"):
            tmpl_values['cloud_cfg'] += key.upper() + " = " + value + "\n"

        # Get manager config file 
        mngr_cfg = file_get_contents(
            os.path.join(mngr_cfg_dir, 'default-manager.cfg'))

        # Add service-specific config file (if any)
        mngr_service_cfg = os.path.join(mngr_cfg_dir, 
            service_name + '-manager.cfg')

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
            os.path.join(mngr_scripts_dir, 'default-manager-start'))

        # Or the service-specific one (if any)
        mngr_startup_scriptname = os.path.join(
            mngr_scripts_dir, service_name + '-manager-start')

        if os.path.isfile(mngr_startup_scriptname):
            tmpl_values['mngr_start_script'] = file_get_contents(
                mngr_startup_scriptname)

        # Get key and a certificate from CA
        mngr_certs = self._get_certificate(email="info@conpaas.eu", 
                                           cn="ConPaaS", 
                                           org="Contrail")

        tmpl_values['mngr_certs_cert']    = mngr_certs['cert']
        tmpl_values['mngr_certs_key']     = mngr_certs['key']
        tmpl_values['mngr_certs_ca_cert'] = mngr_certs['ca_cert']

        # Concatenate the files
        return """%(cloud_script)s

cat <<EOF > /tmp/cert.pem
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

def __get_config(service_id, user_id):
    """Add manager configuration"""
    config_parser = common.config

    if not config_parser.has_section("manager"):
        config_parser.add_section("manager")

    config_parser.set("manager", "FE_SERVICE_ID", service_id)
    config_parser.set("manager", "FE_USER_ID", user_id)
    config_parser.set("manager", "FE_CREDIT_URL", 
        config_parser.get('director', 'DIRECTOR_URL') + "/credit")
    config_parser.set("manager", "FE_TERMINATE_URL", 
        config_parser.get('director', 'DIRECTOR_URL') + "/terminate")
    config_parser.set("manager", "FE_CA_URL", 
        config_parser.get('director', 'DIRECTOR_URL') + "/ca")

    return config_parser

def __stop_reservation_timer(controller):
    for reservation_timer in controller._Controller__reservation_map.values():
        reservation_timer.stop()

def start(service_name, service_id, user_id):
    """Start a manager for the given service_name, service_id and user_id"""
    config_parser = __get_config(str(service_id), str(user_id))
    # Create a new controller
    controller = ManagerController(config_parser)
    # Create a context file for the specific service
    controller.generate_context(service_name)

    # Only useful for testing purposes if the director is not running on a
    # public IP
    controller._Controller__deduct_credit = lambda x: True

    # FIXME: test_manager(ip, port) not implemented yet. Just return True.
    node = controller.create_nodes(1, lambda ip, port: True, None)[0]

    # Stop the reservation timer or the call will not return
    __stop_reservation_timer(controller)

    return node.ip, node.id

def stop(vmid):
    config_parser = __get_config(vmid, "")
    # Create a new controller
    controller = ManagerController(config_parser)
    
    cloud = controller._Controller__default_cloud
    cloud._connect()
    
    class Node: pass
    n = Node()
    n.id = vmid
    cloud.kill_instance(n)

    __stop_reservation_timer(controller)

