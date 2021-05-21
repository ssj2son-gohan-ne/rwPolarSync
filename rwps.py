#! /usr/bin/python3
# -*- coding: utf-8 -*-

"""
File:               rwps.py
Original Author:    Robert Weiss (https://github.com/rowe182/)
Date:               October 20, 2018
Description:        This script will export fitness data from Polar Flow
"""

import os
import sys
import requests
import json
import base64
import datetime
import dicttoxml
import xml
import argparse

SCRIPTVERSION = '1.0.0'

parser = argparse.ArgumentParser()
parser.add_argument('-v', '--verbose', help="debug mode", action="store_true")
parser.add_argument('--version', help="print version and exit", action="store_true")
parser.add_argument('-i', '--clientid', help="your Polar Accesslink API Client id (otherwise, you will be prompted)", nargs='?')
parser.add_argument('-s', '--clientsecret', help="your Polar Accesslink API Client Secret (otherwise, you will be prompted)", nargs='?')
parser.add_argument('-t', '--accesstoken', help="your Polar Accesslink API ACCESSTOKEN (otherwise, you will be prompted)", nargs='?')
parser.add_argument('-u', '--userid', help="your Polar Accesslink API User id (otherwise, you will be prompted)", nargs='?')
parser.add_argument('-f', '--format', nargs='?', default='js', help="output format of activity data (default: 'js')", choices=['js', 'xml'])
parser.add_argument('-d', '--directory', nargs='?', default='./polar_flow_export', help="the directory to export to (default: './polar_flow_export')")
parser.add_argument('-o', '--owner', nargs='?', default='', help="to chown and chmod(rwX------) the complete directory if set")
args = parser.parse_args()

if args.version:
    print(argv[0] + ", version " + SCRIPTVERSION)
    exit(0)

# Polar Settings
APIURL = "https://www.polaraccesslink.com"
CLIENTID = args.clientid if args.clientid else input('Polar Accesslink API Client id: ')
CLIENTSECRET = args.clientsecret if args.clientsecret else input('Polar Accesslink API Client Secret')
ACCESSTOKEN = args.accesstoken if args.accesstoken else input('Polar Accesslink API ACCESSTOKEN')
USERID = args.userid if args.userid else input('Polar Accesslink API User id')

def jdump(dict):
    print(json.dumps(dict, indent=4))

def d2x(d):
    return xml.dom.minidom.parseString(dicttoxml.dicttoxml(d, attr_type=False)).toprettyxml()

def d2j(d):
    return json.dumps(d, indent=4)

def req_get_token(url, accesstoken, debug = False, rawreturn = False, accept = 'application/json'):
    if debug: print(url)
    r = requests.get(url, params={}, headers = {'Authorization': 'Bearer '+accesstoken,'Accept': accept})
    if r.status_code not in [200,201,204]:
        if debug: print('HTTP-Code: '+str(r.status_code))
        raise Exception(url+' Exception, HTTP-Code: '+str(r.status_code))
    elif r.status_code == 204:
        if rawreturn: return ""
        else:         return {}
    elif rawreturn:
        if debug: print(r.text)
        return r.text
    else:
        if debug: jdump(r.json())
        return r.json()

def req_post_token(url, accesstoken, debug = False):
    if debug: print(url)
    r = requests.post(url, params={}, headers = {'Authorization': 'Bearer '+accesstoken,'Accept': 'application/json'})
    if r.status_code not in [200,201,204]:
        if debug: print('HTTP-Code: '+str(r.status_code))
        raise Exception(url+' Exception, HTTP-Code: '+str(r.status_code))
    elif r.status_code == 204:
        return {}
    else:
        if debug: jdump(r.json())
        return r.json()

def req_put_token(url, accesstoken):
    r = requests.put(url, params={}, headers = {'Authorization': 'Bearer '+accesstoken})
    if r.status_code not in [200,201,204]:
        raise Exception(url+' Exception, HTTP-Code: '+str(r.status_code))

def req_get_client(url, clientid, clientsecret, debug = False):
    if debug: print(url)
    s = clientid+':'+clientsecret
    r = requests.get(url, params={}, headers = {'Authorization': 'Basic '+base64.b64encode(s.encode('utf-8')).decode('utf-8'),'Accept': 'application/json'})
    if r.status_code not in [200,201,204]:
        if debug: print('HTTP-Code: '+str(r.status_code))
        raise Exception(url+' Exception, HTTP-Code: '+str(r.status_code))
    elif r.status_code == 204:
        return {}
    else:
        if debug: jdump(r.json())
        return r.json()

print("### starting RW-Polar-Sync v"+SCRIPTVERSION+" at "+datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')+' ###')

user = req_get_token(APIURL+'/v3/users/'+str(USERID), ACCESSTOKEN)
data = {}
opentrans = {}

available_data = req_get_client(APIURL+'/v3/notifications', CLIENTID, CLIENTSECRET, args.verbose)
if 'available-user-data' in available_data:
    for item in available_data["available-user-data"]:
        if 'url' in item:
            trans = req_post_token(item['url'], ACCESSTOKEN, args.verbose)
            opentrans.update({item['data-type']: {'ID': trans['transaction-id'], 'todo': 0, 'done': 0, 'errors': 0, 'url': item['url']}})
            if 'resource-uri' in trans:
                tlist = req_get_token(trans['resource-uri'], ACCESSTOKEN, args.verbose);
                for typ, links in tlist.items():
                    for link in links:
                        r = req_get_token(link, ACCESSTOKEN, args.verbose);
                        opentrans[item['data-type']]['todo'] += 1
                        if item['data-type'] not in data: data.update({item['data-type']: {}})
                        data[item['data-type']].update({r['id']: r})
                        data[item['data-type']][r['id']].update({'_url_': link})

for typ, items in data.items():
    for id, item in items.items():
        try:
            print("Reading "+typ+" ...")
            if typ == 'EXERCISE':
                path = args.directory+'/'+typ+'/'+item['sport']+'/'+item['detailed-sport-info']
                datum = datetime.datetime.strptime(item['start-time'],'%Y-%m-%dT%H:%M:%S.%f')
                fn = path+'/'+user['first-name']+'_'+user['last-name']+'_'+datum.strftime('%Y-%m-%d_%H-%M-%S')
                if not os.path.exists(path): os.makedirs(path)

                hrzones = req_get_token(item['_url_']+'/heart-rate-zones', ACCESSTOKEN);
                print('writing '+fn+'.'+args.format)
                if args.format == 'xml':
                    with open (fn+'.xml', 'w') as f: f.write (d2x({'USER': user, typ: item, 'HEART-RATE-ZONES': hrzones}))
                elif args.format == 'js':
                    with open (fn+'.js', 'w') as f: f.write (d2j({'USER': user, typ: item, 'HEART-RATE-ZONES': hrzones}))

                print('writing '+fn+'.gpx')
                gpx = req_get_token(item['_url_']+'/gpx', ACCESSTOKEN, False, True, 'application/gpx+xml')
                if len(gpx) == 0:
                    print("No data available")
                else:
                    with open (fn+'.gpx', 'w') as f: f.write (gpx)
            
                print('writing '+fn+'.tcx')
                tcx = req_get_token(item['_url_']+'/tcx', ACCESSTOKEN, False, True, 'application/vnd.garmin.tcx+xml')
                if len(tcx) == 0:
                    print("No data available")
                else:
                    with open (fn+'.tcx', 'w') as f: f.write (tcx)
            elif typ == 'ACTIVITY_SUMMARY':
                path = args.directory+'/'+typ
                datum = datetime.datetime.strptime(item['created'],'%Y-%m-%dT%H:%M:%S.%f')
                fn = path+'/'+user['first-name']+'_'+user['last-name']+'_'+datum.strftime('%Y-%m-%d_%H-%M-%S')+'_'+str(item['id'])
                if not os.path.exists(path): os.makedirs(path)
            
                steps = req_get_token(item['_url_']+'/step-samples', ACCESSTOKEN);
                zones = req_get_token(item['_url_']+'/zone-samples', ACCESSTOKEN);
                print('writing '+fn+'.'+args.format)
                if args.format == 'xml':
                    with open (fn+'.xml', 'w') as f: f.write (d2x({'USER': user, typ: item, 'STEP-SAMPLES': steps, 'ZONE-SAMPLES': zones}))
                elif args.format == 'js':
                    with open (fn+'.js', 'w') as f: f.write (d2j({'USER': user, typ: item, 'STEP-SAMPLES': steps, 'ZONE-SAMPLES': zones}))
            elif typ == 'PHYSICAL_INFORMATION':
                path = args.directory+'/'+typ
                datum = datetime.datetime.strptime(item['created'],'%Y-%m-%dT%H:%M:%S.%f')
                fn = path+'/'+user['first-name']+'_'+user['last-name']+'_'+datum.strftime('%Y-%m-%d_%H-%M-%S')
                if not os.path.exists(path): os.makedirs(path)
            
                print('writing '+fn+'.'+args.format)
                if args.format == 'xml':
                    with open (fn+'.xml', 'w') as f: f.write (d2x({'USER': user, typ: item}))
                elif args.format == 'js':
                    with open (fn+'.js', 'w') as f: f.write (d2j({'USER': user, typ: item}))
        except:
            print(sys.exc_info()[0])
            opentrans[typ]['errors'] += 1
        else:
            print("OK")
            opentrans[typ]['done'] += 1

if len(args.owner) > 0:
    os.system('chown -R '+args.owner+' "'+args.directory+'"')
    os.system('chmod -R 0600 "'+args.directory+'"')
    os.system('chmod -R u+X "'+args.directory+'"')

for typ, item in opentrans.items():
    if item['todo'] > 0 and item['todo'] == item['done'] and item['errors'] == 0:
        print(typ+': '+str(item['done'])+' done of '+str(item['todo'])+', '+str(item['errors'])+' errors, commit transaction')
        req_put_token(item['url']+'/'+str(item['ID']), ACCESSTOKEN)
    else:
        print(typ+': '+str(item['done'])+' done of '+str(item['todo'])+', '+str(item['errors'])+' errors, no commit')

print("### finished RW-Polar-Sync v"+SCRIPTVERSION+" at "+datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')+' ###')
