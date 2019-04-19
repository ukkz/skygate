#!/usr/bin/env python
import sys, skygate, subprocess

if __name__ == "__main__":
    if len(sys.argv) >= 3:

        peer_id = str(sys.argv[1])
        api_key = str(sys.argv[2])
        gstreamer_processes = []

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
                for media in peer.getMediaConnections():
                    if not media.isRedirectedOutgoing():
                        video_connection_id, video_ipv4, video_port = media.getSourceToSend()
                        gstreamer_cmd = "gst-launch-1.0 -e rpicamsrc ! video/x-raw,width=640,height=480,framerate=30/1 ! videoconvert ! vp8enc deadline=1  ! rtpvp8pay pt=96 ! udpsink port="+video_port+" host="+video_ipv4+" sync=false"
                        gstreamer_processes.append(subprocess.Popen(gstreamer_cmd, shell=True))

        except KeyboardInterrupt:
            try:
                for gstreamer_process in gstreamer_processes:
                    gstreamer_process.kill()
                peer.close()
            except Exception as e:
                print(e)
