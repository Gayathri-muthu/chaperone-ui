#
#  Copyright 2015 VMware, Inc.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
#
# get_foos() returns a dict of the foo objects keyed by name. Used to populate
# options for fields with attribute "options: foos".
from __future__ import division
import fcntl
import inspect
import logging
import os
import sys
import yaml
import paramiko
import re
from requests import exceptions as requests_exceptions

from django.conf import settings

from pyVmomi import vim, vmodl
from pyVim import connect
from pyVim.connect import SmartConnect, SmartConnectNoSSL

import json, time

LOG = logging.getLogger(__name__)

COMP_VC_CLUSTER = 'comp_vc_cluster'
COMP_VC_DATACENTER = 'comp_vc_datacenter'
COMP_VC_DATASTORES = 'comp_vc_datastores'
COMP_VC_HOSTS = 'comp_vc_hosts'
COMP_VC_NETWORKS = 'comp_vc_networks'
COMP_VC_PASSWORD = 'comp_vc_password'
COMP_VC_USERNAME = 'comp_vc_username'
COMP_VC = 'comp_vc'

MGMT_VC_CLUSTER = 'mgmt_vc_cluster'
MGMT_VC_DATACENTER = 'mgmt_vc_datacenter'
MGMT_VC_DATASTORES = 'mgmt_vc_datastores'
MGMT_VC_HOSTS = 'mgmt_vc_hosts'
MGMT_VC_NETWORKS = 'mgmt_vc_networks'
MGMT_VC_PASSWORD = 'mgmt_vc_password'
MGMT_VC_USERNAME = 'mgmt_vc_username'
MGMT_VC = 'mgmt_vc'

answerfilepath='/var/lib/chaperone/answerfile.yml'
answer_file_dictionary = yaml.load(answerfilepath)

adminfilepath='/var/lib/chaperone-admin/answerfile.yml'
admin_answer_file_dictionary = yaml.load(adminfilepath)



def _get_vcenter_data():
    filename = settings.VCENTER_SETTINGS
    if not os.path.exists(filename):
        LOG.info('No file %s' % filename)
        return {}

    with open(filename, 'r') as fp:
        fcntl.flock(fp, fcntl.LOCK_SH)
        file_contents = fp.read()
        fcntl.flock(fp, fcntl.LOCK_UN)
    return yaml.load(file_contents)


def vcenter_connection(vcenter, username, password):
    """Returns a vCenter service instance, connected with the given login
    information.
    """
    if not all([vcenter, username, password]):
        LOG.error('vCenter host, username, and password required')
        return None
    try:
        service_instance = connect.SmartConnect(host=vcenter, user=username,
                                                pwd=password,
                                                port=settings.VCENTER_PORT)
    except vim.fault.InvalidLogin as e:
        LOG.error('Could not connect to %s: %s' % (vcenter, e.msg))
        return None
    except requests_exceptions.ConnectionError as e:
        LOG.error('Could not connect to %s: %s' % (vcenter, e.message))
        return None
    return service_instance


def get_comp_vc():
    """Returns valid value for compute vCenter."""
    vcenter_data = _get_vcenter_data()
    return { vcenter_data.get(COMP_VC, ''): None }


def get_mgmt_vc():
    """Returns valid value for management vCenter."""
    vcenter_data = _get_vcenter_data()
    return { vcenter_data.get(MGMT_VC, ''): None }


def get_comp_vc_username():
    """Returns valid value for compute vCenter login username."""
    vcenter_data = _get_vcenter_data()
    return { vcenter_data.get(COMP_VC_USERNAME, ''): None }


def get_mgmt_vc_username():
    """Returns valid value for management vCenter login username."""
    vcenter_data = _get_vcenter_data()
    return { vcenter_data.get(MGMT_VC_USERNAME, ''): None }


def get_comp_vc_password():
    """Returns valid value for compute vCenter login password."""
    vcenter_data = _get_vcenter_data()
    return { vcenter_data.get(COMP_VC_PASSWORD, ''): None }


def get_mgmt_vc_password():
    """Returns valid value for management vCenter login password."""
    vcenter_data = _get_vcenter_data()
    return { vcenter_data.get(MGMT_VC_PASSWORD, ''): None }


def _get_datacenters(content=None, vcenter_field=None, username_field=None,
                     password_field=None, datacenter_field=None, vcenter=None,
                     username=None, password=None, datacenter=None):
    if not content:
        LOG.debug('_get_datacenters: %s, %s, %s, %s' % (vcenter, username,
                                                        password, datacenter))
        if not all([vcenter, username, password, datacenter]):
            vcenter_data = _get_vcenter_data()
        if vcenter is None:
            vcenter = vcenter_data.get(vcenter_field)
        if username is None:
            username = vcenter_data.get(username_field)
        if password is None:
            password = vcenter_data.get(password_field)
        if datacenter is None:
            datacenter = vcenter_data.get(datacenter_field)

        service_instance = vcenter_connection(vcenter, username, password)
        if not service_instance:
            return None
        content = service_instance.RetrieveContent()
        connect.Disconnect

    dcview = content.viewManager.CreateContainerView(content.rootFolder,
                                                     [vim.Datacenter], True)
    datacenters = dcview.view
    dcview.Destroy()

    datacenters_by_name = {}
    for dc in datacenters:
        if datacenter and dc.name != datacenter:
            continue
        datacenters_by_name[dc.name] = dc
    return datacenters_by_name


def get_comp_vc_datacenter(vcenter=None, username=None, password=None,
                           datacenter=None):
    """Returns a dict of datacenters in the compute vCenter, keyed by name,
    optionally limited to only the given datacenter. Pass in empty string for
    'datacenter' to get all datacenters.
    """
    LOG.debug('get_comp_vc_datacenters caller: %s', inspect.stack()[1][3])
    return _get_datacenters(
        vcenter_field=COMP_VC, username_field=COMP_VC_USERNAME,
        password_field=COMP_VC_PASSWORD, datacenter_field=COMP_VC_DATACENTER,
        vcenter=vcenter, username=username, password=password,
        datacenter=datacenter)


def get_mgmt_vc_datacenter(vcenter=None, username=None, password=None,
                           datacenter=None):
    """Returns a dict of datacenters in the management vCenter, keyed by
    name, optionally limited to only the given datacenter. Pass in empty string
    for 'datacenter' to get all datacenters.
    """
    LOG.debug('get_mgmt_vc_datacenters caller: %s', inspect.stack()[1][3])
    return _get_datacenters(
        vcenter_field=MGMT_VC, username_field=MGMT_VC_USERNAME,
        password_field=MGMT_VC_PASSWORD, datacenter_field=MGMT_VC_DATACENTER,
        vcenter=vcenter, username=username, password=password,
        datacenter=datacenter)


def _get_clusters(content=None, vcenter_field=None, username_field=None,
                  password_field=None, datacenter_field=None,
                  cluster_field=None, vcenter=None, username=None,
                  password=None, datacenter=None, cluster=None):
    if not content:
        LOG.debug('_get_clusters: %s, %s, %s, %s' % (vcenter, username,
                                                     password, datacenter))
        if not all([vcenter, username, password, datacenter]):
            vcenter_data = _get_vcenter_data()
        if vcenter is None:
            vcenter = vcenter_data.get(vcenter_field)
        if username is None:
            username = vcenter_data.get(username_field)
        if password is None:
            password = vcenter_data.get(password_field)
        if datacenter is None:
            datacenter = vcenter_data.get(datacenter_field)
        if cluster is None:
            cluster = vcenter_data.get(cluster_field)

        service_instance = vcenter_connection(vcenter, username, password)
        if not service_instance:
            return None
        content = service_instance.RetrieveContent()
        connect.Disconnect

    datacenters = _get_datacenters(content=content, datacenter=datacenter)
    clusters_by_name = {}
    for dc_name, dc in datacenters.items():
        if datacenter and dc_name != datacenter:
            continue
        clusterview = content.viewManager.CreateContainerView(
            dc, [vim.ClusterComputeResource], True)
        clusters = clusterview.view
        clusterview.Destroy()

        for cl in clusters:
            if cluster and cl.name != cluster:
                continue
            clusters_by_name[cl.name] = cl
    return clusters_by_name


def get_comp_vc_cluster(vcenter=None, username=None, password=None,
                        datacenter=None, cluster=None):
    """Returns a dict of clusters in the compute vCenter, optionally only from
    the given datacenter and limited to only the given cluster. Pass in empty
    string for 'datacenter'/'cluster' to get all datacenters/clusters.
    """
    LOG.debug('get_comp_vc_clusters caller: %s', inspect.stack()[1][3])
    return _get_clusters(
        vcenter_field=COMP_VC, username_field=COMP_VC_USERNAME,
        password_field=COMP_VC_PASSWORD, datacenter_field=COMP_VC_DATACENTER,
        cluster_field=COMP_VC_CLUSTER, vcenter=vcenter, username=username,
        password=password, datacenter=datacenter, cluster=cluster)


def get_mgmt_vc_cluster(vcenter=None, username=None, password=None,
                        datacenter=None, cluster=None):
    """Returns a dict of clusters in the management vCenter, optionally only
    from the given datacenter and limited to only the given cluster. Pass in
    empty string for 'datacenter'/'cluster' to get all datacenters/clusters.
    """
    LOG.debug('get_mgmt_vc_clusters caller: %s', inspect.stack()[1][3])
    return _get_clusters(
        vcenter_field=MGMT_VC, username_field=MGMT_VC_USERNAME,
        password_field=MGMT_VC_PASSWORD, datacenter_field=MGMT_VC_DATACENTER,
        cluster_field=MGMT_VC_CLUSTER, vcenter=vcenter, username=username,
        password=password, datacenter=datacenter, cluster=cluster)


def _get_hosts(vcenter_field=None, username_field=None, password_field=None,
               datacenter_field=None, cluster_field=None, vcenter=None,
               username=None, password=None, datacenter=None, cluster=None):
    if not all([vcenter, username, password, datacenter, cluster]):
        vcenter_data = _get_vcenter_data()
    if vcenter is None:
        vcenter = vcenter_data.get(vcenter_field)
    if username is None:
        username = vcenter_data.get(username_field)
    if password is None:
        password = vcenter_data.get(password_field)
    if datacenter is None:
        datacenter = vcenter_data.get(datacenter_field)
    if cluster is None:
        cluster = vcenter_data.get(cluster_field)

    service_instance = vcenter_connection(vcenter, username, password)
    if not service_instance:
        return None
    content = service_instance.RetrieveContent()
    connect.Disconnect

    clusters = _get_clusters(content=content, datacenter=datacenter,
                             cluster=cluster)
    hosts_by_name = {}
    for cl_name, cl in clusters.items():
        if cluster and cl_name != cluster:
            continue
        hostsview = content.viewManager.CreateContainerView(
            cl, [vim.HostSystem], True)
        hosts = hostsview.view
        hostsview.Destroy()

        for host in hosts:
            hosts_by_name[host.name] = host
    return hosts_by_name


def get_comp_vc_hosts(vcenter=None, username=None, password=None,
                      datacenter=None, cluster=None):
    """Returns a dict of hosts in the saved compute vCenter cluster."""
    return _get_hosts(
        vcenter_field=COMP_VC, username_field=COMP_VC_USERNAME,
        password_field=COMP_VC_PASSWORD, datacenter_field=COMP_VC_DATACENTER,
        cluster_field=COMP_VC_CLUSTER, vcenter=vcenter, username=username,
        password=password, datacenter=datacenter, cluster=cluster)


def get_mgmt_vc_hosts(vcenter=None, username=None, password=None,
                      datacenter=None, cluster=None):
    """Returns a dict of hosts in the saved management vCenter cluster."""
    return _get_hosts(
        vcenter_field=MGMT_VC, username_field=MGMT_VC_USERNAME,
        password_field=MGMT_VC_PASSWORD, datacenter_field=MGMT_VC_DATACENTER,
        cluster_field=MGMT_VC_CLUSTER, vcenter=vcenter, username=username,
        password=password, datacenter=datacenter, cluster=cluster)


def _get_datastores(vcenter_field=None, username_field=None,
                    password_field=None, datacenter_field=None,
                    cluster_field=None, vcenter=None, username=None,
                    password=None, datacenter=None, cluster=None):
    hosts = _get_hosts(
        vcenter_field=vcenter_field, username_field=username_field,
        password_field=password_field, datacenter_field=datacenter_field,
        cluster_field=cluster_field, vcenter=vcenter, username=username,
        password=password, datacenter=datacenter, cluster=cluster)
    if not hosts:
        return None
    datastores_by_name = {}

    for host in hosts.values():
        for datastore in host.datastore:
            datastores_by_name[datastore.name] = datastore
    return datastores_by_name


def get_comp_vc_datastores(vcenter=None, username=None, password=None,
                           datacenter=None, cluster=None):
    """Returns a dict of datastores in the saved compute vCenter cluster."""
    LOG.debug('get_comp_vc_datastores caller: %s', inspect.stack()[1][3])
    return _get_datastores(
        vcenter_field=COMP_VC, username_field=COMP_VC_USERNAME,
        password_field=COMP_VC_PASSWORD, datacenter_field=COMP_VC_DATACENTER,
        cluster_field=COMP_VC_CLUSTER, vcenter=vcenter, username=username,
        password=password, datacenter=datacenter, cluster=cluster)


def get_mgmt_vc_datastores(vcenter=None, username=None, password=None,
                           datacenter=None, cluster=None):
    """Returns a dict of datastores in the saved management vCenter."""
    LOG.debug('get_mgmt_vc_datastores caller: %s', inspect.stack()[1][3])
    return _get_datastores(
        vcenter_field=MGMT_VC, username_field=MGMT_VC_USERNAME,
        password_field=MGMT_VC_PASSWORD, datacenter_field=MGMT_VC_DATACENTER,
        cluster_field=MGMT_VC_CLUSTER, vcenter=vcenter, username=username,
        password=password, datacenter=datacenter, cluster=cluster)


def _get_networks(vcenter_field=None, username_field=None, password_field=None,
                  datacenter_field=None, cluster_field=None, vcenter=None,
                  username=None, password=None, datacenter=None, cluster=None):
    hosts = _get_hosts(
        vcenter_field=vcenter_field, username_field=username_field,
        password_field=password_field, datacenter_field=datacenter_field,
        cluster_field=cluster_field, vcenter=vcenter, username=username,
        password=password, datacenter=datacenter, cluster=cluster)
    if not hosts:
        return None
    networks_by_name = {}

    for host in hosts.values():
        for network in host.network:
            networks_by_name[network.name] = network
    return networks_by_name


def get_comp_vc_networks(vcenter=None, username=None, password=None,
                         datacenter=None, cluster=None):
    """Returns a dict of networks in the saved compute vCenter cluster."""
    LOG.debug('get_comp_vc_networks caller: %s', inspect.stack()[1][3])
    return _get_networks(
        vcenter_field=COMP_VC, username_field=COMP_VC_USERNAME,
        password_field=COMP_VC_PASSWORD, datacenter_field=COMP_VC_DATACENTER,
        cluster_field=COMP_VC_CLUSTER, vcenter=vcenter, username=username,
        password=password, datacenter=datacenter, cluster=cluster)


def get_mgmt_vc_networks(vcenter=None, username=None, password=None,
                         datacenter=None, cluster=None):
    """Returns a dict of networks in the saved management vCenter cluster."""
    LOG.debug('get_mgmt_vc_networks caller: %s', inspect.stack()[1][3])
    return _get_networks(
        vcenter_field=MGMT_VC, username_field=MGMT_VC_USERNAME,
        password_field=MGMT_VC_PASSWORD, datacenter_field=MGMT_VC_DATACENTER,
        cluster_field=MGMT_VC_CLUSTER, vcenter=vcenter, username=username,
        password=password, datacenter=datacenter, cluster=cluster)


def get_comp_vc_value():
    """Returns saved name or IP address of compute vCenter."""
    vcenter_data = _get_vcenter_data()
    return vcenter_data.get(COMP_VC, '')


def get_mgmt_vc_value():
    """Returns saved name or IP address of management vCenter."""
    vcenter_data = _get_vcenter_data()
    return vcenter_data.get(MGMT_VC, '')


def get_comp_vc_username_value():
    """Returns saved login username for compute vCenter."""
    vcenter_data = _get_vcenter_data()
    return vcenter_data.get(COMP_VC_USERNAME, '')


def get_mgmt_vc_username_value():
    """Returns saved login username for management vCenter."""
    vcenter_data = _get_vcenter_data()
    return vcenter_data.get(MGMT_VC_USERNAME, '')


def get_comp_vc_password_value():
    """Returns saved login password for compute vCenter."""
    vcenter_data = _get_vcenter_data()
    return vcenter_data.get(COMP_VC_PASSWORD, '')


def get_mgmt_vc_password_value():
    """Returns saved login password for management vCenter."""
    vcenter_data = _get_vcenter_data()
    return vcenter_data.get(MGMT_VC_PASSWORD, '')


def get_comp_vc_datacenter_value():
    """Returns saved name of compute vCenter datacenter."""
    vcenter_data = _get_vcenter_data()
    return vcenter_data.get(COMP_VC_DATACENTER, '')


def get_mgmt_vc_datacenter_value():
    """Returns saved name of management vCenter datacenter."""
    vcenter_data = _get_vcenter_data()
    return vcenter_data.get(MGMT_VC_DATACENTER, '')


def get_comp_vc_cluster_value():
    """Returns saved name of compute vCenter cluster."""
    vcenter_data = _get_vcenter_data()
    return vcenter_data.get(COMP_VC_CLUSTER, '')


def get_mgmt_vc_cluster_value():
    """Returns saved name of management vCenter cluster."""
    vcenter_data = _get_vcenter_data()
    return vcenter_data.get(MGMT_VC_CLUSTER, '')

def get_disk1_size():
    return get_disk_size(answer_file_dictionary["esxi_host1_ip"])
    
def get_disk2_size():
    return get_disk_size(answer_file_dictionary["esxi_host2_ip"])
    
def get_disk3_size():
    return get_disk_size(answer_file_dictionary["esxi_host3_ip"])
    
def get_disk4_size():
    
    return get_disk_size(answer_file_dictionary["esxi_host4_ip"])

    
def get_disk_size(hostip):
    """Returns disk size .""" 
       
    username= answer_file_dictionary["esxi_host1_username"]
    password= answer_file_dictionary["esxi_host1_password"]
    try:
        ssh = paramiko.SSHClient()
        ssh.load_system_host_keys()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostip, 22, username, password)
        LOG.debug('SSH connection to the host %s is succesfull' % hostip)
    except Exception as e:
        changed = False
        LOG.debug('SSH conection to the remote host failed.') 
    devices = {}
    test_cmd = "esxcli storage core device list | grep -E 'Devfs Path:'"
    tstdin, tstdout, tstderr = ssh.exec_command(test_cmd)
    toutput  = tstdout.read()
    
    LOG.debug('Physical {}-{}'.format(toutput, type(toutput)))
    if 'mpx' in toutput:
        cmd = "esxcli storage core device list | grep -E 'Size:|Is SSD:|mpx'"
        LOG.debug('Executing %s for host %s' %(cmd,hostip))
        
        stdin, stdout, stderr = ssh.exec_command(cmd)
        if len(stderr.read()) != 0:
            changed = False
        else:
            output  = stdout.read()
            output = output.replace("\n","")
            LOG.debug("the command output is {0}".format(output))
            list = output.split("(")
            list.pop(0)
            LOG.debug("the list is {0}".format(list))
            for i in list:
                m = re.match("(mpx\.\w+(\:\w+)+)\)\s+Size:\s(\d+)", i)
                if m and int(m.group(3)) > 1024:
                    in_gb = int(m.group(3))/1024
                    club = str(in_gb)+'GB('+m.group(1)+')'
                    devices[club] = m.group(3)

    if 'naa' in toutput:
        cmd = "esxcli storage core device list | grep -E 'Size:|Is SSD:|naa'"
        LOG.debug('Executing %s for host %s' %(cmd,hostip))
        devices = {}
        stdin, stdout, stderr = ssh.exec_command(cmd)
        if len(stderr.read()) != 0:
            changed = False
        else:
            output  = stdout.read()
            output = output.replace("\n","")
            list = output.split("(")            
            for i in list:
                m = re.match("(naa\.\w+)\)\s+Size:\s(\d+)",i)                
                if m:
                    in_gb = int(m.group(2))/1024
                    club = str(round(in_gb))+'GB('+m.group(1)+')'
                    devices[club] = m.group(2)
    
    LOG.debug('The device id with their sizes are')
    LOG.debug(devices)
    return devices

def get_mgmt_az():
    az = {}
    az[answer_file_dictionary["mgmt_az_name"]] = ""
    return az

def get_compute_az():
    az = {}
    for count in range(1, int(admin_answer_file_dictionary["compute_az"])+1):
        az[answer_file_dictionary["compute_az_{}_name".format(count)]] = ""
    return az
def get_compute_hosts():
    hosts = {}
    for count in range(1, int(admin_answer_file_dictionary["no_compute_cluster_name"])+1):
        for host_number in range(1, int(admin_answer_file_dictionary["no_hosts_per_compute_cluster"])+1):
            hosts[answer_file_dictionary["esxi_compute{}_host{}_ip".format(count,host_number)]] = ""
    return hosts
def get_edge_hosts():
    host= {}
    host[answer_file_dictionary["nsx_edge_ips"]] = ""
    return host

def get_datastore_objs():
    content = get_vcenter_connection()
    obj = {}
    ds_obj = {}
    container = content.viewManager.CreateContainerView(content.rootFolder,
                                                         [vim.Datastore], True)
    LOG.debug("Connected to container  !")

    for managed_object_ref in container.view:
        obj.update({managed_object_ref: managed_object_ref.name})
    LOG.debug("Got DS obj {} !".format(obj))

    datastores = obj.values()
    for value in datastores:
        ds_obj[value] = ""
    return ds_obj

def get_datacenter_objs():
    content = get_vcenter_connection()
    obj = {}
    dc_obj = {}
    container = content.viewManager.CreateContainerView(content.rootFolder,
                                                         [vim.Datacenter], True)
    LOG.debug("Connected to container  !")

    for managed_object_ref in container.view:
        obj.update({managed_object_ref: managed_object_ref.name})
    LOG.debug("Got DC obj {} !".format(obj))

    datacenters = obj.values()
    for value in datacenters:
        dc_obj[value] = ""
    return dc_obj

def get_network_objs():
    content = get_vcenter_connection()
    obj = {}
    nw_obj = {}
    container = content.viewManager.CreateContainerView(content.rootFolder,
                                                         [vim.dvs.DistributedVirtualPortgroup, vim.Network], True)
    LOG.debug("Connected to container  !")

    for managed_object_ref in container.view:
        obj.update({managed_object_ref: managed_object_ref.name})
    LOG.debug("Got Network obj {} !".format(obj))

    network = obj.values()
    for value in network:
        nw_obj[value] = ""
    return nw_obj

def get_cluster_objs():    
    content = get_vcenter_connection()
    obj = {}
    cl_obj = {}
    container = content.viewManager.CreateContainerView(content.rootFolder,[vim.ClusterComputeResource], True)
    LOG.debug("Connected to container  !")

    for managed_object_ref in container.view:
        obj.update({managed_object_ref: managed_object_ref.name})
    LOG.debug("Got Cluster obj {} !".format(obj))

    clusters = obj.values()
    for value in clusters:
        cl_obj[value] = ""
    return cl_obj

def get_resource_pool_objs():    
    content = get_vcenter_connection()
    obj = {'vim.ResourcePool:dummy': ''}
    pool_obj = {}
    container = content.viewManager.CreateContainerView(content.rootFolder,[vim.ResourcePool], True)
    LOG.debug("Connected to container  !")

    for managed_object_ref in container.view:
        obj.update({managed_object_ref: managed_object_ref.name})
    LOG.debug("Got Resource Pool obj {} !".format(obj))

    pools = obj.values()
    for value in pools:
        pool_obj[value] = ""
    return pool_obj


def get_host_objs():    
    content = get_vcenter_connection()
    obj = {}
    host_obj = {}
    container = content.viewManager.CreateContainerView(content.rootFolder,[vim.HostSystem], True)
    LOG.debug("Connected to container  !")

    for managed_object_ref in container.view:
        obj.update({managed_object_ref: managed_object_ref.name})
    LOG.debug("Got ESXi obj {} !".format(obj))

    hosts = obj.values()
    for value in hosts:
        host_obj[value] = ""
    return host_obj

def get_vcenter_connection():
    """Returns vCenter connection obj .""" 
    vcenter_ip = answer_file_dictionary["vcenter_host_ip"]
    vcenter_username= answer_file_dictionary["vcenter_user"]
    vcenter_password= answer_file_dictionary["vcenter_pwd"]

    try:
        LOG.debug("Trying to connect to VCENTER SERVER . . .")
        si = SmartConnectNoSSL(host=vcenter_ip, user=vcenter_username, pwd=vcenter_password, port=443)
        LOG.debug("Connected to VCENTER SERVER !")
    except IOError, e:
        #pass
	#atexit.register(Disconnect, si)
	LOG.debug("Connection failed {0}")
        module.fail_json(chagned=False, msg="Failed to connect vCenter")
    return si.RetrieveContent()
