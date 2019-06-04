import boto3
import time
import socket, sys
from pymongo import MongoClient
from bson.objectid import ObjectId
import uuid
import json
import stomp
import csv

myclient = MongoClient("mongodb://localhost:27017/")
db = myclient['NP_project']
reg = db['reg']
token = db['token']
invite_friend = db['invite_friend']
post = db['post']
group = db['group']

class Listener(object):
    def __init__(self):
        self.check=1
    def on_message(self, headers, message):
        if message=='ok':
            self.check=0
def create_ins():
    with open('./run.sh', 'r') as f:
        run_data = f.read()
    with open('credentials.csv') as csvfile:
        rows = csv.DictReader(csvfile)
        for row in rows:
            Access_key, Secret_access_key=row["Access key ID"], row["Secret access key"]
    ec2 = boto3.resource('ec2',  region_name="ap-northeast-1",\
    aws_access_key_id=Access_key,  aws_secret_access_key=Secret_access_key)
    instance = ec2.Instance('i-07f3f475c0807d71a')
    new_instance=ec2.create_instances(ImageId='ami-06c43a7df16e8213c', InstanceType='t2.micro', \
        MaxCount=1, MinCount=1, Placement={'AvailabilityZone': 'ap-northeast-1a'}, \
        SecurityGroupIds=['sg-090fff042b0b9b76f'], KeyName='np', UserData = run_data)[0]
    print(new_instance.instance_id)
    new_instance.wait_until_running()
    conn = stomp.Connection10([('52.68.108.247', 61613)])
    check_listen=Listener()
    conn.set_listener('Listener', check_listen)
    conn.start()
    conn.connect()
    conn.subscribe('/queue/app2login')
    while check_listen.check:
        time.sleep(1)
    conn.disconnect()
    new_instance.reload()
    print(new_instance.public_ip_address)
    return new_instance

class Server(object):
    """docstring for server"""
    def __init__(self, ip, port):
        global reg, token, invite_friend, post, group
        self.mytoken=None
        self.myname=None
        self.data=None
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            #except socket.error, msg:
        except :
            sys.stderr.write("[ERROR] %s\n" % msg[1])
            sys.exit(1)
        HOST, PORT = ip, port
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) #reuse tcp
        self.sock.bind((HOST, PORT))
        self.sock.listen(5)
        self.known = ['register', 'login', 'delete', 'logout']
        self.instance_list=[]
        self.instance_list.append(create_ins())
        self.ctrl_login=[0]
        self.user_ins_num={}

    def register(self, cmd):
        data = {'status': 1, 'message': ''}
        if len(cmd) != 3:
            data['message'] = 'Usage: register <username> <password>'
        elif reg.find_one({'name': '{}'.format(cmd[1])}):
            data['message'] = '{} is already used'.format(cmd[1])
        else:
            mydict = { 'name': '{}'.format(cmd[1]), 'password': '{}'.format(cmd[2])}
            reg.insert_one(mydict)
            data = {'status': 0, 'message': 'Success!'}
        return data

    def login(self, cmd):
        data = {'status': 1, 'message': ''}
        if len(cmd) == 3:
            myname = reg.find_one({'name': '{}'.format(cmd[1])})
        else:
            pass
        if len(cmd) != 3:
            data['message'] = 'Usage: login <id> <password>'
        elif myname == None or myname['password'] != cmd[2]:
            data['message'] = 'No such user or password error'
        else:
            mytoken = token.find_one({'name': '{}'.format(cmd[1])})
            if mytoken == None:
                login_token = uuid.uuid4()
                mytoken = { 'name': '{}'.format(cmd[1]), 'token': '{}'.format(login_token)}
                token.insert_one(mytoken)
            else:
                login_token = mytoken['token']
            index=0
            for item in self.ctrl_login:
                if item<10 and item>=0:
                    self.ctrl_login[index]+=1
                    self.user_ins_num[cmd[1]]=index
                    login_ip=self.instance_list[index].public_ip_address
                    break
                index+=1
            if index==len(self.ctrl_login):
                self.instance_list.append(create_ins())
                self.user_ins_num[cmd[1]]=index
                self.ctrl_login.append(1)
                login_ip=self.instance_list[-1].public_ip_address
            data = {'status': 0, 'token':'{}'.format(login_token), 'message': 'Success!',\
             'topic': self.list_joined(cmd[:2])['group'], 'ip': '{}'.format(login_ip)}
        return data

    def delete_logout(self, cmd):
        data = {'status': 1, 'message': ''}
        if len(cmd) != 2:
            data['message'] = 'Usage: {} <user>'.format('delete' if cmd[0] == 'delete' else 'logout')
        else:
            token.delete_one(self.myname)
            if cmd[0] == 'delete':
                reg.delete_one(self.myname)
                invite_friend.delete_many({ 'send': '{}'.format(self.mytoken['name'])})
                invite_friend.delete_many({ 'recv': '{}'.format(self.mytoken['name'])})
                post.delete_many(self.myname)
                group.delete_many({ 'user': '{}'.format(self.mytoken['name'])})
            data['status'] = 0
            index=self.user_ins_num[self.mytoken['name']]
            self.ctrl_login[index]-=1
            if not self.ctrl_login[index]:
                self.instance_list[index].terminate()
                self.ctrl_login[index]=-1
            data['message'] = '{}'.format('Success!' if cmd[0] == 'delete' else 'Bye!')
        return data

    def list_group(self, cmd, query=None):
        if len(cmd) != 2:
            data = {'status': 1, 'message': 'Usage: list-group <user>'}
        else:
            group_list=[]
            mylist = group.find(query) if query else group.find({})
            [group_list.append(x['name']) for x in mylist if not x['name'] in group_list]
            data = {'status': 0, 'group': group_list}
        return data

    def list_joined(self, cmd):
        if len(cmd) != 2:
            data = {'status': 1, 'message': 'Usage: list-joined <user>'}
        else:
            data = self.list_group(cmd, {'user':cmd[1]})
        return data

    def run(self):
        while True:
            (csock, adr) = self.sock.accept()
            #print "Client Info: ", csock, adr
            msg = csock.recv(1024).decode()
            if not msg:
                pass
            else:
                print ("Client send: " + msg)
                cmd = msg[:].split(' ')
                try:
                    mytoken = token.find_one({'token':'{}'.format(cmd[1])})
                    myname = { 'name': '{}'.format(mytoken['name'])}
                    cmd[1] = myname['name']
                    self.mytoken = mytoken
                    self.myname = myname
                    print(mytoken)
                except:
                    mytoken = None
                if True:#try:
                    if cmd[0] == 'register':
                        self.data = self.register(cmd)
                    elif cmd[0] == 'login':
                        self.data = self.login(cmd)
                    elif mytoken == None and any(item in self.known for item in cmd):
                        self.data = {'status': 1, 'message': 'Not login yet'}
                    elif cmd[0] == 'delete' or cmd[0] == 'logout':
                        self.data = self.delete_logout(cmd)
                    else:
                        self.data = {'status': 1, 'message': 'Unknown command {}'.format(cmd[0])}
                else:#except:
                    self.data = {'status': 1, 'message': 'Unknown command {}'.format(msg)}
                self.data = json.dumps(self.data)
                print (self.data)
                csock.sendall(self.data.encode())
            csock.close()


def launch_server(ip, port):
    server = Server(str(ip), int(port))
    server.run()


if __name__ == '__main__':
    if len(sys.argv) == 3:
        launch_server(sys.argv[1], sys.argv[2])
    else:
        print('Usage: python3 {} IP PORT'.format(sys.argv[0]))