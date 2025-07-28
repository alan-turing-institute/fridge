#!/bin/python3

#import something to handel yaml files
from curses import echo
import yaml
import random
from getpass import getpass
import subprocess
import string

import signal
import sys

starting_wd = subprocess.run(['pwd'], capture_output=True, text=True).stdout.strip()

def signal_handler(signal, frame):
  sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

with open('/workspace/infra/fridge/Pulumi.template.yaml', 'r') as file:
    data = yaml.safe_load(file)

#print as yaml
#print(yaml.dump(data))

print(f"this script will run you through updating all the values in {file.name}")
print(f"NOTE: This will overwrite any existing values.")
response=subprocess.run(["gum", "confirm", "do you want to continue? (y/n)"], stdout=subprocess.PIPE, text=True)
if response.returncode == 1:
    print("Aborting...")
    exit(0)
for key, value in data['config'].items():
    #if they key has a child called 'secure'
    if 'secure' in value:
        #generate random string for secure value
        new_secure_value = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
        print(f"would you like to update the secure value for {key}? leave blank for {new_secure_value}")
        response = getpass().strip()
        if response:
            data['config'][key]['secure'] = response
        else:
            data['config'][key]['secure'] = new_secure_value
        print(f"updating value for {key}")
        print(f"pulumi config set --secret {key} **********")
        subprocess.run(['pulumi', 'config', 'set', '--secret', '--path', f"{key}", f"{data['config'][key]['secure']}", '--cwd=/workspace/infra/fridge', '--config-file=/workspace/infra/fridge/Pulumi.dev.yaml'])
    #if value is an array
    elif isinstance(value, list):
        print(f"would you like to update the array value for {key} (as comma-separated list)? (current value: {value})")
        response = input().strip()
        if response:
            #split the response by comma and strip whitespace
            new_value = [item.strip() for item in response.split(',')]
            data['config'][key] = new_value
            print(f"updating value for {key}")
            print(f"pulumi config set {key} {', '.join(new_value)}")
            subprocess.run(['pulumi', 'config', 'set', '--path', f"{key}", ','.join(new_value), '--cwd=/workspace/infra/fridge', '--config-file=/workspace/infra/fridge/Pulumi.dev.yaml'])

    #if value is a string
    elif isinstance(value, str):
        print(f"would you like to update the value for {key}? (current value: {value})")
        response = input().strip()
        if response:
            data['config'][key] = response
            print(f"updating value for {key}")
            print(f"pulumi config set {key} {response}")
            #print the command to be run
            print(f"pulumi config set {key} {response} --cwd=/workspace/infra/fridge --config-file=/workspace/infra/fridge/Pulumi.dev.yaml")
            subprocess.run(['pulumi', 'config', 'set', '--path', f"{key}", f"{response}", '--cwd=/workspace/infra/fridge', '--config-file=/workspace/infra/fridge/Pulumi.dev.yaml'])