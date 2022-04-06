# Map Islandora metadata to METS

This script takes a list of Islandora node IDs as input and returns a METS XML file for each node.

## Usage

The script has two required arguments: `--repo_url` is the base url for the Islandora repository, and `--node_ids` is a comma-separated list of node IDs to be processed. 

Optionally, an output directory can be specified with `--outputdir` where the XML files will be written to.

If using Drupal UUIDs for constructing ARKs, specify the institutional NAAN using the `--ark_naan` argument and shoulders using the `--ark_shoulder` argument to include the ARK in the FLocat element. Otherwise Flocat will point to the object's Islandora URL.


Run the script from the command line as follows:
`python build_xml.py --repo_url=linktorepo --node_ids=1111,1234,2222,3333 --outputdir=path/to/directory`