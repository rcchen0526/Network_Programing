import socket, sys
from pymongo import MongoClient
from bson.objectid import ObjectId
import uuid
import json
import stomp

myclient = MongoClient("mongodb://localhost:27017/")
db = myclient['NP_project3']
reg = db['reg']
token = db['token']
invite_friend = db['invite_friend']
post = db['post']
group = db['group']

class Server(object):
    """docstring for server"""
    def __init__(self, ip, port):
        global reg, token, invite_friend, post, group
        self.mytoken=None
        self.myname=None
        self.data=None
        self.queue_name = '/queue/'
        self.topic_name = '/topic/'
        self.POST=61613
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
        self.known = ['register', 'login', 'delete', 'logout', 'invite', 'list-invite', 'accept-invite', 'list-friend', 'post', 'receive-post',\
                        'send', 'create-group', 'list-group', 'list_joined', 'join-group', 'send-group']

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
            data = {'status': 0, 'token':'{}'.format(login_token), 'message': 'Success!', 'topic': self.list_joined(cmd[:2])['group']}
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
            data['message'] = '{}'.format('Success!' if cmd[0] == 'delete' else 'Bye!')
        return data

    def invite(self, cmd):
        data = {'status': 1}
        try:    #invite=0 -> invite, invite=1 -> friend
            q_already_invite = { 'send' : '{}'.format(cmd[1]), 'recv' : '{}'.format(cmd[2]), 'invite' : '0'}
            q_already_friend = { 'send' : '{}'.format(cmd[1]), 'recv' : '{}'.format(cmd[2]), 'invite' : '1'}
            q_myinvited = { 'send' : '{}'.format(cmd[2]), 'recv' : '{}'.format(cmd[1]), 'invite' : '0'}
            myname2 = reg.find_one({'name': '{}'.format(cmd[2])})
            already_invite = invite_friend.find_one(q_already_invite)
            already_friend = invite_friend.find_one(q_already_friend)
            myinvited = invite_friend.find_one(q_myinvited)
        except:
            data = None
        if data == None or len(cmd)!=3:
            data = {'status': 1, 'message': 'Usage: invite <user> <id>'}
        elif myname2 == None:
            data['message'] = '{} does not exist'.format(cmd[2])
        elif already_invite:
            data['message'] = 'Already invited'
        elif already_friend:
            data['message'] = '{} is already your friend'.format(cmd[2])
        elif myinvited:
            data['message'] = '{} has invited you'.format(cmd[2])
        elif cmd[1] == cmd[2]:
            data['message'] = 'You cannot invite yourself'
        else:
            data = {'status': 0, 'message': 'Success!'}
            mydict = { 'send':'{}'.format(cmd[1]),'recv':'{}'.format(cmd[2]), 'invite':'0'}
            invite_friend.insert_one(mydict)
        return data

    def list_invite(self, cmd):
        if len(cmd)!=2:
            data = {'status': 1, 'message': 'Usage: list-invite <user>'}
        else:
            myquery = { 'recv' : '{}'.format(cmd[1]), 'invite':'0'}
            mylist = invite_friend.find(myquery)
            invite_list=[]
            for x in mylist:
                invite_list.append(x['send'])
            data = {'status': 0, 'invite': invite_list}
        return data

    def accept_invite(self, cmd):
        if len(cmd)!=3:
            data = {'status': 1, 'message': 'Usage: accept-invite <user> <id>'}
        else:
            q_already_invite = { 'recv' : '{}'.format(cmd[1]), 'send' : '{}'.format(cmd[2]), 'invite' : '0'}
            already_invite = invite_friend.find_one(q_already_invite)
            if already_invite:
                newvalues = { '$set': { 'invite': '1' } }
                invite_friend.update_one(q_already_invite, newvalues)
                mydict = { 'send':'{}'.format(cmd[1]),'recv':'{}'.format(cmd[2]), 'invite':'1'}
                invite_friend.insert_one(mydict)
                data = {'status': 0, 'message': 'Success!'}
            else:
                data = {'status': 1, 'message': '{} did not invite you'.format(cmd[2])}
        return data

    def list_friend(self, cmd):
        if len(cmd)!=2:
            data = {'status': 1, 'message': 'Usage: list-friend <user>'}
        else:
            mysend = { 'send' : '{}'.format(cmd[1]), 'invite' : '1'}
            friend_list=[]
            mylist = invite_friend.find(mysend)
            for x in mylist:
                friend_list.append(x['recv'])
            data = {'status': 0, 'friend': friend_list}
        return data

    def post(self, cmd):
        if len(cmd)<3:
            data = {'status': 1, 'message': 'Usage: post <user> <message>'}
        else:
            post_string=''
            for i in range(2, len(cmd)):
                post_string = post_string + cmd[i] +' '
            mydict = { 'name':'{}'.format(cmd[1]),'post':'{}'.format(post_string[:-1])}
            post.insert_one(mydict)
            data = {'status': 0, 'message': 'Success!'}
        return data

    def receive_post(self, cmd):
        if len(cmd)!=2:
            data = {'status': 1, 'message': 'Usage: receive-post <user>'}
        else:
            mysend = { 'send' : '{}'.format(cmd[1]), 'invite' : '1'}
            friend_list=[]
            recv_post=[]
            mylist = invite_friend.find(mysend)
            for x in mylist:
                friend_list.append(x['recv'])
            for friend in friend_list:
                q_friend_post = { 'name' : '{}'.format(friend)}
                friend_post = post.find(q_friend_post)
                if friend_post:
                    for posts in friend_post:
                        recv_post.append({'id':'{}'.format(posts['name']), 'message':'{}'.format(posts['post'])})
            data = {'status': 0, 'post': recv_post}
        return data
    def send(self, cmd):
        if len(cmd)<4:
            data = {'status': 1, 'message': 'Usage: send <user> <friend> <message>'}
        else:
            user_exist = reg.find_one({'name': '{}'.format(cmd[2])})
            try:
                Friend_list = self.list_friend(cmd[:2])['friend']
            except:
                Friend_list=[]
            user_login = token.find_one({'name': '{}'.format(cmd[2])})
            if user_exist == None:
                data = {'status': 1, 'message': 'No such user exist'}
            elif cmd[2] not in Friend_list:
                data = {'status': 1, 'message': '{} is not your friend'.format(cmd[2])}
            elif user_login == None:
                data = {'status': 1, 'message': '{} is not online'.format(cmd[2])}
            else:
                send_string='<<<{}->{}: '.format(cmd[1], cmd[2])
                for i in range(3, len(cmd)):
                    send_string = send_string + cmd[i] +' '
                send_string = send_string[:-1]+'>>>'
                conn = stomp.Connection10([('127.0.0.1',self.POST)])
                conn.start()
                conn.connect()
                queue_name = self.queue_name+str(cmd[2])
                conn.send(queue_name, send_string)
                conn.disconnect()
                data = {'status': 0, 'message': 'Success!'}
        return data

    def create_group(self, cmd):
        if len(cmd) != 3:
            data = {'status': 1, 'message': 'Usage: create-group <user> <group>'}
        else:
            group_exist = group.find_one({'name': '{}'.format(cmd[2])})
            if group_exist:
                data = {'status': 1, 'message': '{} already exist'.format(cmd[2])}
            else:
                mygroup = { 'user':'{}'.format(cmd[1]),'name':'{}'.format(cmd[2])}
                group.insert_one(mygroup)
                data = {'status': 0, 'message': 'Success!'}
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
    def join_group(self, cmd):
        if len(cmd) != 3:
            data = {'status': 1, 'message': 'Usage: join_group <user> <group>'}
        else:
            Group_list = self.list_group(cmd[:2])['group']
            already_joined = self.list_joined(cmd[:2])['group']
            if not cmd[2] in Group_list:
                data = {'status': 1, 'message': '{} does not exist'.format(cmd[2])}
            elif cmd[2] in already_joined:
                data = {'status': 1, 'message': 'Already a member of {}'.format(cmd[2])}
            else:
                mygroup = { 'user':'{}'.format(cmd[1]),'name':'{}'.format(cmd[2])}
                group.insert_one(mygroup)
                data = {'status': 0, 'message': 'Success!'}
        return data

    def send_group(self, cmd):
        if len(cmd)<4:
            data = {'status': 1, 'message': 'Usage: send-group <user> <group> <message>'}
        else:
            group_exist = group.find_one({'name': '{}'.format(cmd[2])})
            try:
                joined_list = self.list_joined(cmd[:2])['group']
            except:
                joined_list=[]
            if group_exist == None:
                data = {'status': 1, 'message': 'No such group exist'}
            elif cmd[2] not in joined_list:
                data = {'status': 1, 'message': 'You are not the member of {}'.format(cmd[2])}
            else:
                send_string='<<<{}->GROUP<{}>: '.format(cmd[1], cmd[2])
                for i in range(3, len(cmd)):
                    send_string = send_string + cmd[i] +' '
                send_string = send_string[:-1]+'>>>'
                conn = stomp.Connection10([('127.0.0.1',self.POST)])
                conn.start()
                conn.connect()
                topic_name = self.topic_name+str(cmd[2])
                conn.send(topic_name, send_string)
                conn.disconnect()
                data = {'status': 0, 'message': 'Success!'}
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
                try:
                    if cmd[0] == 'register':
                        self.data = self.register(cmd)
                    elif cmd[0] == 'login':
                        self.data = self.login(cmd)
                    elif mytoken == None and any(item in self.known for item in cmd):
                        self.data = {'status': 1, 'message': 'Not login yet'}
                    elif cmd[0] == 'delete' or cmd[0] == 'logout':
                        self.data = self.delete_logout(cmd)
                    elif cmd[0] == 'invite':
                        self.data = self.invite(cmd)
                    elif cmd[0] == 'list-invite':
                        self.data = self.list_invite(cmd)
                    elif cmd[0] == 'accept-invite':
                        self.data = self.accept_invite(cmd)
                    elif cmd[0] == 'list-friend':
                        self.data = self.list_friend(cmd)
                    elif cmd[0] == 'post':
                        self.data = self.post(cmd)
                    elif cmd[0] == 'receive-post':
                        self.data = self.receive_post(cmd)
                    elif cmd[0] == 'send':
                        self.data = self.send(cmd)
                    elif cmd[0] == 'create-group':
                        self.data = self.create_group(cmd)
                    elif cmd[0] == 'list-group':
                        self.data = self.list_group(cmd)
                    elif cmd[0] == 'list-joined':
                        self.data = self.list_joined(cmd)
                    elif cmd[0] == 'join-group':
                        self.data = self.join_group(cmd)
                    elif cmd[0] == 'send-group':
                        self.data = self.send_group(cmd)
                    else:
                        self.data = {'status': 1, 'message': 'Unknown command {}'.format(cmd[0])}
                except:
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