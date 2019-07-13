#!/usr/bin/python3
import os, pwd, grp
import subprocess
import docker
import json
from pathlib import Path
from pyfiglet import Figlet

challs = {}
uid = pwd.getpwnam("cappit").pw_uid
gid = grp.getgrnam("cappit").gr_gid

get_assigned_port = lambda name : challs[name]["port"]
get_port = lambda c : c.ports['31000/tcp'][0]['HostPort']
is_alive = lambda c : c.status == "running"

def is_built(client,name):
    try:
        client.images.get(name)
        return True
    except:
        return False

def is_assigned(name):
    if name in challs.keys():
        return True
    else:
        return False

def set_perm_recursive(path):
    for root,_,files in os.walk(path):
        for momo in files:
            os.chown(str(Path(root,momo)),uid,gid)
    return

def check_uid():
    uid = os.getuid()
    if uid!=0:
        print("[!]Execute it with root permission")
        quit()
    return

def check_path():
    cur_path = Path.cwd().stem
    if cur_path != 'supplier':
        print("[!]Excute it in 'supplier' directory")
        quit()
    return

def check_json():
    global uid
    global gid

    fPath = Path('.','challs.json')
    if not fPath.exists():
        with open('challs.json','w') as f:
            json.dump('{}',f)
            f.close()

        os.chown('challs.json',uid,gid)

def load_json():
    global challs
    with open('challs.json','r') as f:
        challs = json.load(f)

def find_avail_port():
    global challs

    ports = sorted([int(challs[name]["port"]) for name in challs.keys()])

    for port in range(31000,32000):
        if port not in ports:
            break

    return str(port)

def list_chall(client,filters=None,quiet=False): 
    containers=[]
    for container in client.containers.list(all=True,filters=filters):
        if container.name.startswith('cappit'):
            containers.append(container)

    if not quiet:
        print("[Challenge list]") 
        print("{:^5}{:^25}{:^5}{:^10}".format("idx","name","port","status"))
        containers = sorted(containers,key=lambda container : get_assigned_port(container.name[7:]))
        for idx,container in enumerate(containers):
            port = get_assigned_port(container.name[7:])
            name = container.name
            status = container.status
            print("{:^5}{:^25}{:^5}{:^10}".format(str(idx+1),name,port,status))
        for name in challs.keys():
            if challs[name]["manual"] == "true":
                print("{:^5}{:^25}{:^5}".format("M",name,challs[name]["port"]))
        
    return containers

def run_chall(client):
    print("[Run challenge]")
    print("[0]Input default information")
    name = input("name: ")
    ver = input("version: ")
    print()
    if ver != "16.04" and ver != "18.04":
        print("[!]Support only 16.04 and 18.04\n")
        return

    if is_assigned(name):
        port = get_assigned_port(name)
    else:
        choice=input("Do you want to bind port manually?(y/n)")
        if choice.lower() == "y":
            port = input("port: ")
        else:
            port = find_avail_port()

    fpath = Path(".","dock_"+name)

    print("[1]Generate Dockerfile...")
    if fpath.exists() and fpath.is_dir():
        os.chdir(str(fpath))
        if not Path("flag").exists() or not Path("bin").exists():
            print("[!]Some files missed (flag or bin).\n")
            os.chdir("..")
            return
        choice = input("Do you want to generate Dockerfile manually?(y/n)")
        if choice.lower() == 'y':
            print("Input contents of Dockerfile after '>>'")
            dock_cont=input(">>\n")
            os.system("gendock -m {} {} {}".format(dock_cont,name,port))
            print("[+]Generate Dockerfile succeed!\n")
        else:
            os.system("gendock {} {} {}".format(ver,name,port))
            print("[+]Generate Dockerfile succeed!\n")
    else:
        print("[!]Target directury not exists\n")
        return

    print("[2]Build Dockerfile")
    try:
        subprocess.call("./build.sh",shell=True)
    except:
        print("[!]Build error occured!\n")
        os.chdir("..")
        return
    print("[+]Build complete\n")

    print("[3]Run image")
    try:
        subprocess.call("./run.sh",shell=True)
    except:
        print("[!]Run error occured!\n")
        os.chdir("..")
        return
    print("[+]Challenge is now running on {}.\n".format(port))

    os.chdir("..")
    set_perm_recursive(str(fpath))
    challs.update({name:{"port":port,"manual":"false"}})
    with open("challs.json","w") as f:
        json.dump(challs,f)
        f.close()

def restart_chall(client):
    print("[Restart challenge]")
    containers = list_chall(client)

    idx=input("which?(idx)> ")
    if int(idx) > len(containers) or int(idx) < 1:
        print("[!]Wrong idx\n")
        return

    name = containers[int(idx)-1].name[7:]

    print("[1]Restart")
    subprocess.call("dock_{}/run.sh".format(name),shell=True)    

    print("[+]Restart cappit_{} complete".format(name))

def manually_bind():
    print("[Port binding]")
    name=input("name :")
    port=input("port :")

    challs.update({name:{"port":port,"manual":"true"}})
    with open("challs.json","w") as f:
        json.dump(challs,f)
        f.close()

    print("[+]Manual port binding succeed")

def stop_chall(client):
    print("[Stop challenge]")
    containers = list_chall(client,filters={"status":"running"})
    if not len(containers):
        print("[!]No challenge is running now")
        return 

    idx=input("which?(idx)> ")
    if int(idx) > len(containers) or int(idx) < 1:
        print("[!]Wrong idx")
        return

    container = containers[int(idx)-1]
    name = container.name[7:]
    container.stop()
    print("[+]cappit_{} stopped".format(name))

def remove_chall(client):
    global challs
    print("[remove challenge]")

    containers = list_chall(client)

    idx=input("which?(idx)> ")
    if int(idx) > len(containers):
        print("[!]Wrong idx")
        return
    
    container = containers[int(idx)-1]
    name = container.name[7:]

    print("[1]Remove container")
    container.remove(force=True)
    print("[+]cappit_{} is removed.".format(name))

    print("[2]Unbind port")
    del(challs[name])
    with open("challs.json","w") as f:
        json.dump(challs,f)
        f.close()
    print("[+]cappit_{}'s port is unbinded".format(name))

    print("[+]Removing cappit_{} complete.".format(name))

def clear_all(client):
    global challs
    print("[clear all]")

    print("[1]Remove all")
    containers = list_chall(client,quiet=True)
    for container in containers:
        container.remove(force=True)
    
    print("[2]Unbind all")
    with open("challs.json","w") as f:
        challs={}
        f.close()

    print("[+]clear complete.")

def menu():
    check_uid()
    check_path()
    check_json()
    load_json()
    client = docker.from_env()
    f = Figlet(font='slant')
    print(f.renderText('PAPA_WHALE'))
    while 1:
        print()
        print("[Main menu]")
        print("[1]list challenges")
        print("[2]run challenge")
        print("[3]restart challenge")
        print("[4]bind port-challege manually")
        print("[5]stop challenge")
        print("[6]remove challenge")
        print("[7]clear all")
        print("[8]quit")
        choice = input("> ")
        print()

        if choice == str(1):
            list_chall(client)
        elif choice == str(2):
            run_chall(client)
        elif choice == str(3):
            restart_chall(client)
        elif choice == str(4):
            manually_bind()
        elif choice == str(5):
            stop_chall(client)
        elif choice == str(6):
            remove_chall(client)
        elif choice == str(7):
            clear_all(client)
        elif choice == str(8):
            quit()
        else:
            print("[!]Wrong choice\n")

if __name__=='__main__':
    menu()
