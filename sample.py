#!/usr/bin/env python
import sys, skygate

if __name__ == "__main__":
    if len(sys.argv) >= 3:

        peer_id = str(sys.argv[1])
        api_key = str(sys.argv[2])
        try:
            peer = skygate.Peer(peer_id, api_key)
        except Exception as e:
            print(e)
            quit()
        else:
            print('Peer created as '+peer.id+': '+peer.token)

        try:
            while True:
                for data in peer.getDataConnections():
                    if not data.getQueue().empty():
                        mes = data.getQueue().get().decode()
                        print(mes)
        except KeyboardInterrupt:
            try:
                peer.close()
            except Exception as e:
                print(e)

