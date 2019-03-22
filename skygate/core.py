#!/usr/bin/env python
import requests, threading, time, json, sys, socket, random
from queue import Queue


class AsyncRequest(object):
    def __init__(self, gateway_addr='127.0.0.1', gateway_port=8000):
        self.gateway_addr = gateway_addr
        self.gateway_port = gateway_port
        self.base_url = 'http://' + gateway_addr + ':' + str(gateway_port)
        self.onDict = {}
        self.thread_run_async_request = True

    def _request_thread(self, uri, params={}, expected_code=200):
        while self.thread_run_async_request:
            res = requests.get(uri, params=params) # http request (blocking)
            json_dict = res.json()
            event = json_dict.get('event')
            # run callback by event
            if res.status_code == expected_code and event is not None and self.onDict.get(event.lower()) is not None:
                func = self.onDict.get(event.lower())
                func(json_dict)
                
    def async_get(self, uri, params={}, expected_code=200):
        thread = threading.Thread(target=self._request_thread, args=(uri, params, expected_code))
        thread.start()

    def close(self):
        self.thread_run_async_request = False

    def on(self, event, callback):
        self.onDict[event] = callback






class Data(AsyncRequest):
    def __init__(self, redirect_port, data_connection_id=None):
        super().__init__()
        self.connection_id = data_connection_id
        self.redirect_addr = self.gateway_addr
        self.redirect_port = redirect_port
        self.queue = None
        self.thread_run_data = True

        res = requests.post(
            self.base_url + '/data',
            json.dumps({}),
            headers={'Content-Type': 'application/json'}
            )
        if res.status_code == 201:
            body_data = res.json()
            self.id = body_data['data_id']
            self.ipv4_addr = body_data['ip_v4']
            self.port = body_data['port']
            if self.connection_id is None:
                # As "Data Connect"
                # WIP.
                pass
            else:
                # As "Data Answer"
                self.async_get(self.base_url + '/data/connections/' + self.connection_id + '/events')
                self._setRedirect()
        else:
            raise Exception('Gateway returns code '+str(res.status_code)+' on opening data port')

    def close(self):
        # Close async get thread (at super class)
        super().close()
        # Close udp listener thread (on here)
        self.thread_run_data = False
        # Free data_connection_id
        if self.connection_id is not None:
            res = requests.delete(self.base_url + '/data/connections/' + self.connection_id)
            if res.status_code != 204:
                raise Exception('Gateway returns code '+str(res.status_code)+' on closing data connection')
        # Free data_id
        if self.id is not None:
            res = requests.delete(self.base_url + '/data/' + self.id)
            if res.status_code != 204 and res.status_code != 404: # 404 is disconnection from another peer
                raise Exception('Gateway returns code '+str(res.status_code)+' on closing data port')

    def _setRedirect(self):
        params = {
            'feed_params': {'data_id': self.id},
            'redirect_params': {'ip_v4': self.redirect_addr, 'port': self.redirect_port}
            }
        res = requests.put(
            self.base_url + '/data/connections/' + self.connection_id,
            json.dumps(params),
            headers={'Content-Type': 'application/json'}
            )
        if res.status_code != 200:
            raise Exception('Gateway returns code '+str(res.status_code)+' on setting redirection of data connection')

    def _udp_receive_thread(self, queue):
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp.settimeout(0.5)
        try:
            udp.bind(('127.0.0.1', self.redirect_port))
        except socket.timeout:
            pass
        while self.thread_run_data:
            try:
                data = udp.recv(128)
            except socket.timeout:
                pass
            else:
                queue.put(data)
        udp.close()

    def getQueue(self):
        if self.queue is None:
            queue = Queue() 
            thread = threading.Thread(target=self._udp_receive_thread, args=([queue]), name='UDP-Listener-'+str(self.redirect_port))
            thread.start()
            self.queue = queue
        return self.queue

    def getStatus(self):
        res = requests.get(self.base_url + '/data/connections/' + self.connection_id + '/status')
        j = res.json()
        if res.status_code == 200 and j.get('open') is True:
            return True
        else:
            return False

    def send(self, message):
        if type(message) is not bytes:
            message = str(message).encode()
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp.sendto(message, (self.ipv4_addr, self.port))
        udp.close()






class Peer(AsyncRequest):
    def __init__(self, peer_id, api_key, turn=False):
        super().__init__()
        self.id = peer_id
        self.token = None
        self.dataInstances = []

        # Connect to SkyWay server
        params = {'key': api_key, 'domain': 'localhost', 'turn':turn, 'peer_id': self.id}
        res = requests.post(
            self.base_url + '/peers',
            json.dumps(params),
            headers={'Content-Type': 'application/json'}
            )
        if res.status_code == 201:
            body_data = res.json()
            self.token = body_data['params']['token']
            self.async_get(
                self.base_url + '/peers/' + self.id + '/events',
                {'token': self.token}
                )
            self.on('connection', self._createDataInstance) # fire when receive data connection
        else:
            raise Exception('Gateway returns code '+str(res.status_code)+' on creating peer')

    def close(self):
        # Close async get thread (at super class)
        super().close()
        # Free data instances
        for data in self.dataInstances:
            data.close()
        # Free peer_id
        if self.token is not None:
            res = requests.delete(
                self.base_url + '/peers/' + self.id,
                params={'token': self.token}
                )
            if res.status_code != 204:
                raise Exception('Gateway returns code '+str(res.status_code)+' on closing peer')

    def _createDataInstance(self, response):
        # find an unused port
        used_ports = []
        for data in self.dataInstances:
            used_ports.append(data.redirect_port)
        while True:
            redirect_port = random.randint(32768, 60999)
            if redirect_port not in used_ports:
                break
        # get connection_id from incoming packet and generate data instance
        data_connection_id = response['data_params']['data_connection_id']
        data = Data(redirect_port, data_connection_id)
        self.dataInstances.append(data)

    def getDataConnections(self, check_alive=False):
        # check connection
        if check_alive:
            for i, data in enumerate(self.dataInstances):
                if not data.getStatus():
                    dead = self.dataInstances.pop(i)
                    try:
                        dead.close()
                    except Exception as e:
                        print(e)
                time.sleep(0.1)
        return self.dataInstances
