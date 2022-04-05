import json
import requests
import argparse
import os
import getpass
from lxml import etree, isoschematron
import xml.etree.ElementTree as ET

parser = argparse.ArgumentParser()
parser.add_argument('--repo_url', required=True, help='The base url of the islandora repository.')
parser.add_argument('--node_ids', required = True, help = 'Comma separated list of node IDs to create METS from.')
parser.add_argument('--outputdir', required=False, help='Specify output directory for METS files. Otherwise will save to same folder as script.')
args = parser.parse_args()

# Register namespaces
ET.register_namespace('xlink', "http://www.w3.org/1999/xlink")
ET.register_namespace('mets', "http://www.loc.gov/METS/")
xlink="{http://www.w3.org/1999/xlink}"
mets="{http://www.loc.gov/METS/}"
# have user enter base url for repo
repo_url = args.repo_url
# List of node ids
node_ids = []
for nid in args.node_ids.split(","):
    node_ids.append(nid)

def get_node_json(nid):
    n_url = repo_url + "/node/" + nid + "?_format=json"
    r = requests.get(n_url)
    if r.status_code==200:
        nodejson = json.loads(r.content.decode('utf-8'))
        return nodejson
    else:
        return "invalid url"

def get_members(nid, user, pw):
    mem_url = repo_url + "/node/" + nid + "/members?_format=json"
    r = requests.get(mem_url, auth=(user,pw))
    if r.status_code == 200:
        membersjson = json.loads(r.content.decode('utf-8'))
        return membersjson
    else:
        return "invalid url"

def get_field_model(url):
    r = requests.get(url)
    if r.status_code == 200:
        taxonomy = json.loads(r.content.decode('utf-8'))
        model = taxonomy['field_external_uri'][0]['uri']
        return model
    else:
        return "invalid url"

user = input("Enter rest client username: ")
pw = getpass.getpass()

for nid in node_ids:
    # Create main sections and root
    root = ET.Element(mets + 'mets')
    filesec = ET.SubElement(root, mets + "fileSec")
    structmap = ET.SubElement(root, mets + "structMap", attrib={"TYPE": "logical"})
    main_level = ET.SubElement(structmap, mets + "div")
    # get main metadata for each nid
    node = get_node_json(nid)
    members = get_members(nid, user, pw)
    node_uuid = "uuid_" + node['uuid'][0]['value']
    node_ark = "ark:/19837/" + node['uuid'][0]['value']
    # Use external URI for field_model for fileGrp/type. Need secondary lookup for taxonomy json.
    model_url = repo_url + node['field_model'][0]['url'] + "?_format=json"
    node_model = get_field_model(model_url)
    # Build node element tree
    node_grp = ET.SubElement(filesec, mets + "fileGrp", attrib={"USE": node_model})
    node_file = ET.SubElement(node_grp, mets + "file", attrib={"ID": node_uuid})
    node_flocat = ET.SubElement(node_file, mets + "FLocat", attrib={xlink + "href": node_ark, "LOCTYPE": "ARK"})
    node_fptr = ET.SubElement(main_level, mets + "fptr", attrib={"FILEID": node_uuid})
    # Keep dictionary of file groups to avoid repeated top-level sections
    grp = {node_model:node_grp}
    if len(members)>0: # members will be length 0 if there are no child objects
        child_level = ET.SubElement(main_level, mets+"div", attrib={"TYPE":"http://purl.org/dc/terms/hasPart"})
        # members will come out as a list of dictionaries if there are multiple children. Otherwise it is a dictionary.
        if isinstance(members, list):
            for i in range(len(members)):
                child_uuid = members[i]['uuid'][0]['value']
                fptr = ET.SubElement(child_level, mets+"fptr", attrib={"FILEID":"uuid_"+child_uuid})
                child_ark = "ark:/19837/"+child_uuid
                # get ext url for model
                c_url = repo_url + members[i]['field_model'][0]['url'] + "?_format=json"
                fgrp_type = get_field_model(c_url)
                if fgrp_type not in grp.keys():
                    fgrp = ET.SubElement(filesec, mets+'fileGrp', attrib={"USE":fgrp_type})
                    file = ET.SubElement(fgrp, mets+"file", attrib={"ID":"uuid_"+child_uuid})
                    flocat = ET.SubElement(file, mets+"FLocat", attrib={xlink+"href":child_ark, "LOCTYPE":"ARK"})
                    grp[fgrp_type] = fgrp
                else:
                    parent = grp[fgrp_type]
                    file = ET.SubElement(parent, mets+"file", attrib={"ID":child_uuid})
                    flocat = ET.SubElement(file, mets+'FLocat', attrib={xlink+"href":child_ark, "LOCTYPE":"ARK"})
        else:  # If there is only one child
            child_uuid = members['uuid'][0]['value']
            fptr = ET.SubElement(child_level, mets + "fptr", attrib={"FILEID": "uuid_" + child_uuid})
            child_ark = "ark:/19837/" + child_uuid
            c_url = repo_url + members['field_model'][0]['url'] + "?_format=json"
            fgrp_type = get_field_model(c_url)
            if fgrp_type not in grp.keys():
                fgrp = ET.SubElement(filesec, mets + 'fileGrp', attrib={"USE": fgrp_type})
                file = ET.SubElement(fgrp, mets + "file", attrib={"ID": "uuid_" + child_uuid})
                flocat = ET.SubElement(file, mets + "FLocat", attrib={xlink + "href": child_ark, "LOCTYPE": "ARK"})
                grp[fgrp_type] = fgrp
            else:
                parent = grp[fgrp_type]
                file = ET.SubElement(parent, mets + "file", attrib={"ID": child_uuid})
                flocat = ET.SubElement(file, mets + 'FLocat', attrib={xlink + "href": child_ark, "LOCTYPE": "ARK"})
    if len(node['field_member_of'])>0:
        parent_level = ET.SubElement(main_level, mets+"div", attrib={"TYPE":"http://purl.org/dc/terms/isPartOf"})
        # if there are multiple parents:
        if isinstance(node['field_member_of'], list):
            p_url = []
            for i in range(len(node['field_member_of'])):
                url = repo_url + node['field_member_of'][i]['url']+'?_format=json'
                p_url.append(url)
            for j in range(len(p_url)):
                #get node.json for parent objects
                r = requests.get(p_url[j])
                if r.status_code == 200:
                    parent_node = json.loads(r.content.decode('utf-8'))
                    uuid = parent_node['uuid'][0]['value']
                    fptr = ET.SubElement(parent_level, mets+"fptr", attrib={"FILEID":"uuid_"+uuid})
                    parent_ark = "ark:/19837/" + uuid
                    # Get parent model type for file grp from taxonomy json
                    model_url = repo_url + parent_node['field_model'][0]['url'] + "?_format=json"
                    model = get_field_model(model_url)
                    if model not in grp.keys():
                        pgrp = ET.SubElement(filesec, mets + 'fileGrp', attrib={"USE": model})
                        pfile = ET.SubElement(pgrp, mets+'file', attrib={'ID':"uuid_"+uuid})
                        pflocat = ET.SubElement(pfile, mets+'FLocat', attrib={xlink+"href":parent_ark, "LOCTYPE":"ARK"})
                        grp[model]=pgrp
                    else:
                        filegroup = grp[model]
                        pfile = ET.SubElement(filegroup, mets+"file", attrib={'ID':"uuid_"+uuid})
                        pflocat = ET.SubElement(pfile, mets+"FLocat", attrib={xlink+"href":parent_ark, "LOCTYPE":"ARK"})
        else:
            p_url = repo_url + node['field_member_of'] + "?_format=json"
            r = requests.get(p_url)
            if r.status_code == 200:
                parent_node = json.loads(r.content.decode('utf-8'))
                uuid = parent_node['uuid'][0]['value']
                fptr = ET.SubElement(parent_level, mets+"fptr", attrib={"FILEID":"uuid_"+uuid})
                parent_ark = "ark:/19837/" + uuid
                # Get parent model type for file grp from taxonomy json
                model_url = repo_url + parent_node['field_model'][0]['url'] + "?_format=json"
                model = get_field_model(model_url)
                if model not in grp.keys():
                    pgrp = ET.SubElement(filesec, mets + 'fileGrp', attrib={"USE": model})
                    pfile = ET.SubElement(pgrp, mets + 'file', attrib={'ID': "uuid_" + uuid})
                    pflocat = ET.SubElement(pfile, mets + 'FLocat', attrib={xlink + "href": parent_ark, "LOCTYPE": "ARK"})
                    grp[model] = pgrp
                else:
                    filegroup = grp[model]
                    pfile = ET.SubElement(filegroup, mets + "file", attrib={'ID': "uuid_" + uuid})
                    pflocat = ET.SubElement(pfile, mets + "FLocat", attrib={xlink + "href": parent_ark, "LOCTYPE": "ARK"})
    tree = ET.ElementTree(root)
    ET.indent(tree, space='\t')
    if args.outputdir is not None and os.path.exists(args.outputdir):
        filename = os.path.join(args.outputdir, nid+"_mets.xml")
    else:
        filename = nid + "_mets.xml"
    tree.write(filename, xml_declaration=False, encoding='utf-8')

# validate METS
# schema = etree.XMLSchema(etree.parse("mets.xsd"))
# parser = etree.XMLParser(schema=schema)
# val = etree.parse('mets.xml', parser)