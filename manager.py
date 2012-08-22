import os
import random

from OpenSSL import crypto

import common
common.extend_path()

from conpaas.core.controller import Controller
from conpaas.core.misc import file_get_contents

def gen_rsa_keypair():
    pkey = crypto.PKey()
    pkey.generate_key(crypto.TYPE_RSA, 2048)
    return pkey
    
def create_x509_req(req_key, uid, sid, org, email, cn, role):
    req = crypto.X509Req()
    subj = req.get_subject()

    subj.O = org
    subj.CN = cn
    subj.emailAddress = email
    subj.userId = uid
    subj.serviceLocator = sid
    subj.role = role

    req.set_pubkey(req_key)
    req.sign(req_key, "md5")
    return req

def create_x509_cert(cert_dir, x509_req):
    # Load the CA cert
    ca_cert = crypto.load_certificate(crypto.FILETYPE_PEM, 
        file_get_contents(os.path.join(cert_dir, "ca_cert.pem")))
    
    # Load private key
    key = crypto.load_privatekey(crypto.FILETYPE_PEM, 
        file_get_contents(os.path.join(cert_dir, "ca_key.pem")))

    # Create new certificate
    newcert = crypto.X509()

    # Generate serial number
    serial = random.randint(1, 2048)
    newcert.set_serial_number(serial)
    
    # Valid for one year starting from now 
    newcert.gmtime_adj_notAfter(60 * 60 * 24 * 365)
    newcert.gmtime_adj_notBefore(0)

    # Issuer, subject and public key
    newcert.set_issuer(ca_cert.get_subject())
    newcert.set_subject(x509_req.get_subject())
    newcert.set_pubkey(x509_req.get_pubkey())

    # Sign
    newcert.sign(key, "md5")

    return crypto.dump_certificate(crypto.FILETYPE_PEM, newcert)

def generate_certificate(cert_dir, uid, sid, role, email, cn, org):
    """Generates a new x509 certificate for a manager from scratch.

    Creates a key, a request and then the certificate."""

    # Get CA cert
    ca_cert = file_get_contents(os.path.join(cert_dir, "ca_cert.pem"))

    # Generate keypair
    req_key  = gen_rsa_keypair()

    # Generate certificate request
    x509_req = create_x509_req(req_key, uid, sid, org, email, cn, role)

    # Sign the request
    certificate = create_x509_cert(cert_dir, x509_req)

    return { 'ca_cert': ca_cert, 
             'key': crypto.dump_privatekey(crypto.FILETYPE_PEM, req_key), 
             'cert': certificate }

class ManagerController(Controller):

    def _get_certificate(self, email, cn, org):
        config_parser = self._Controller__config_parser

        user_id = config_parser.get("manager", "FE_USER_ID")
        service_id = config_parser.get("manager", "FE_SERVICE_ID")
        cert_dir = config_parser.get('conpaas', 'CERT_DIR')

        return generate_certificate(cert_dir, user_id, service_id, 
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

    # Only useful for testing purposes if the director is not running on a
    # public IP
    controller._Controller__deduct_credit = lambda x: True

    # FIXME: test_manager(ip, port) not implemented yet. Just return True.
    node = controller.create_nodes(1, lambda ip, port: True, None)

    # Stop the reservation timer or the call will not return
    for reservation_timer in controller._Controller__reservation_map.values():
        reservation_timer.stop()

    return node

if __name__ == "__main__":
    print start("php", "1", "1")
    #cert = generate_certificate(cert_dir="/var/tmp/certs", uid="1", sid="1",
    # role="manager", email="info@conpaas.eu", cn="ConPaaS", org="Contrail")
    #print cert['cert']
