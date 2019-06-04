import sys
import socket
import json
import os
import threading
import stomp
import time

class Listener(object):
    def on_message(self, headers, message):
        print ('message: %s' % message)

class Subs(object):
    def __init__(self, ip):
        self.stop=[]
        self.task=[]
        self.cont=0
        self.queue_name = '/queue/'
        self.topic_name = '/topic/'
        self.listener_name = 'Listener'
        self.ip=ip
        self.post=61613

    def set_stop(self):
        self.stop.append(1)
        return len(self.stop)-1

    def stop_num(self, num):
        self.stop[num] = 0

    def stop_all(self):
        self.stop=[0] * len(self.stop)

    def listening(self, index, user_name, topic):
        conn = stomp.Connection10([(self.ip, self.post)])
        conn.set_listener(self.listener_name, Listener())
        conn.start()
        conn.connect()
        conn.subscribe(self.queue_name+str(user_name))
        for item in topic:
            conn.subscribe(self.topic_name+str(item))
        self.cont=0
        while(self.stop[index]):
            try:
                if len(self.task) and self.task[0]['index'] == index:
                    group_dict = self.task[0]
                    conn.subscribe(self.topic_name+str(group_dict['group']))
                    self.task.remove(group_dict)
                    self.cont=0
            except:
                pass
            time.sleep(0.1)
        conn.disconnect()


class Client(object):
    def __init__(self, ip, port):
        self.user_dict = {}
        self.thread = []
        self.user_ip={}
        try:
            socket.inet_aton(ip)
            if 0 < int(port) < 65535:
                self.login_ip = ip
                self.login_server_post=int(port)
                self.application_server_port = 25563
                self.subs = Subs(ip)
            else:
                raise Exception('Port value should between 1~65535')
            self.cookie = {}
        except Exception as e:
            print(e, file=sys.stderr)
            sys.exit(1)

    def run(self):
        while True:
            cmd = sys.stdin.readline()
            if cmd == 'exit' + os.linesep:
                self.subs.stop_all()
                for i in range(len(self.thread)):
                    self.thread[i].join()
                return
            if cmd != os.linesep:
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        self.port=self.login_server_post if cmd.split()[0] in \
                        ['register', 'login', 'logout', 'delete'] else self.application_server_port
                        try:
                            self.ip=self.login_ip if cmd.split()[0] in \
                        ['register', 'login', 'logout', 'delete'] else self.user_ip[cmd.split()[1]]
                        except:
                            pass
                        s.connect((self.ip, self.port))
                        cmd = self.__attach_token(cmd)
                        s.send(cmd.encode())
                        resp = s.recv(4096).decode()
                        self.__show_result(json.loads(resp), cmd)
                except Exception as e:
                    print(e, file=sys.stderr)

    def __show_result(self, resp, cmd=None):
        if 'message' in resp:
            print(resp['message'])

        if 'invite' in resp:
            if len(resp['invite']) > 0:
                for l in resp['invite']:
                    print(l)
            else:
                print('No invitations')

        if 'friend' in resp:
            if len(resp['friend']) > 0:
                for l in resp['friend']:
                    print(l)
            else:
                print('No friends')

        if 'post' in resp:
            if len(resp['post']) > 0:
                for p in resp['post']:
                    print('{}: {}'.format(p['id'], p['message']))
            else:
                print('No posts')

        if 'group' in resp:
            if len(resp['group']) > 0:
                for l in resp['group']:
                    print(l)
            else:
                print('No groups')

        if cmd:
            command = cmd.split()
            if resp['status'] == 0 and command[0] == 'login':
                self.cookie[command[1]] = resp['token']
                self.subs.cont=1
                index = self.subs.set_stop()
                self.user_dict[resp['token']] = index
                self.user_ip[command[1]]=resp['ip']
                self.thread.append(threading.Thread(target = self.subs.listening, args = (index, command[1], resp['topic'], )))
                self.thread[index].start()
                while self.subs.cont:
                    time.sleep(0.01)

            if resp['status'] == 0 and any(item in ['delete', 'logout'] for item in command):
                index = self.user_dict[command[1]]
                self.subs.stop_num(index)
                self.thread[index].join()

            if resp['status'] == 0 and any(item in ['create-group', 'join-group'] for item in command):
                self.subs.cont=1
                index = self.user_dict[command[1]]
                self.subs.task.append({'index':index, 'group':command[2]})
                while self.subs.cont:
                    time.sleep(0.01)


    def __attach_token(self, cmd=None):
        if cmd:
            command = cmd.split()
            if len(command) > 1:
                if command[0] != 'register' and command[0] != 'login':
                    if command[1] in self.cookie:
                        command[1] = self.cookie[command[1]]
                    else:
                        command.pop(1)
            return ' '.join(command)
        else:
            return cmd


def launch_client(ip, port):
    c = Client(ip, port)
    c.run()
    #c.testing()

if __name__ == '__main__':
    if len(sys.argv) == 3:
        launch_client(sys.argv[1], sys.argv[2])
    else:
        print('Usage: python3 {} IP PORT'.format(sys.argv[0]))
