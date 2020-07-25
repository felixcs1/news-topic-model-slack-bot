
import argparse
from os import path
import configparser
import sys
import json
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def get_cert_path():
    if path.exists(path.expanduser("~") + '/certificate.pem'):
        return path.expanduser("~") + '/certificate.pem'
    else:
        raise Exception('Unable to locate a certificate')


def get_session_tokens(account):
    try:
        print('requesting Wormhole access for account: ' + account)
        response = requests.get('https://wormhole.api.bbci.co.uk/account/' +
                                account + '/credentials', verify=False, cert=get_cert_path())
        session_json = json.loads(response.content)
        session = dict()
        session['accessKeyId'] = session_json['accessKeyId']
        session['secretAccessKey'] = session_json['secretAccessKey']
        session['sessionToken'] = session_json['sessionToken']
        return session
    except:
#        res
        raise Exception(
            'Unable to reach https://wormhole.api.bbci.co.uk/account/' + account + '/credentials')


def get_credentials_file():
    if path.exists(path.join(path.expanduser("~"), '.aws/credentials')):
        return open(path.join(path.expanduser("~"), '.aws/credentials'), 'w')
    else:
        raise Exception(
            'Unable to locate aws credentials file - have u installed aws-cli?')


def update_credential_file(account, profile_name):
    session = get_session_tokens(account)
    config = configparser.ConfigParser()
    config.read([path.join(path.expanduser("~"), '.aws/credentials')])
    if profile_name not in config.sections():
        config.add_section(profile_name)

    try:
        config.set(profile_name, 'aws_access_key_id', session['accessKeyId'])
        config.set(profile_name, 'aws_secret_access_key',
                   session['secretAccessKey'])
        config.set(profile_name, 'aws_session_token', session['sessionToken'])
        config.set(profile_name, 'region', 'eu-west-1')
    except configparser.ParsingError:
        print('Error parsing config file')
        raise

    config_file = get_credentials_file()
    config.write(config_file)
    config_file.close()
    print('Updated credentials with wormhole values for profile: ' + profile_name)


def main(account='301790081969', profile='wormhole'):
    update_credential_file(account, profile)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Lets Wormhole')
    parser.add_argument('-a', action='store', dest='account',
                        help='AWS account requiring wormhole access', default='301790081969')
    parser.add_argument('-p', action='store', dest='profile',
                        help='Credentials profile', default='wormhole')
    arguments = parser.parse_args()
    main(arguments.account, arguments.profile)