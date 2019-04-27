#!/usr/bin/env python
import sys, skygate, subprocess, mido
# グローバル
MyMessage = '' # メッセージバッファ
CharBuf = '' # 数字バッファ


def midiToNumber(mido_message):
    number_list = ('1','2','3','4','5','6','7','8','9','0','*','#')
    if mido_message.type != 'note_on':
        return None
    n = mido_message.note % 12
    return number_list[n]


def numberToChar(couple_of_chars):
    convert_list = {
        '11':'あ','12':'い','13':'う','14':'え','15':'お','16':'A','17':'B','18':'C','19':'D','10':'1',
        '21':'か','22':'き','23':'く','24':'け','25':'こ','26':'E','27':'F','28':'G','29':'H','20':'2',
        '31':'さ','32':'し','33':'す','34':'せ','35':'そ','36':'I','37':'J','38':'K','39':'L','30':'3',
        '41':'た','42':'ち','43':'つ','44':'て','45':'と','46':'M','47':'N','48':'O','49':'P','40':'4',
        '51':'な','52':'に','53':'ぬ','54':'ね','55':'の','56':'Q','57':'R','58':'S','59':'T','50':'5',
        '61':'は','62':'ひ','63':'ふ','64':'へ','65':'ほ','66':'U','67':'V','68':'W','69':'X','60':'6',
        '71':'ま','72':'み','73':'む','74':'め','75':'も','76':'Y','77':'Z','78':'?','79':'!','70':'7',
        '81':'や','82':'(','83':'ゆ','84':')','85':'よ','86':'#','87':'*','88':'@','89':'❤︎','80':'8',
        '91':'ら','92':'り','93':'る','94':'れ','95':'ろ','96':'↓','97':'↑','98':':','99':';','90':'9',
        '01':'わ','02':'を','03':'ん','04':'ﾞ','05':'ﾟ','06':'/','07':'ｰ','08':'&','09':' ','00':'0'
        }
    return convert_list.get(str(couple_of_chars))


if __name__ == "__main__":
    if len(sys.argv) >= 3:

        peer_id = str(sys.argv[1])
        api_key = str(sys.argv[2])
        gstreamer_processes = []
        midi_inputs = mido.get_input_names() # MIDI入力一覧
        midi_in = mido.open_input(midi_inputs[1])

        try:
            peer = skygate.Peer(peer_id, api_key, dumpMessage=True)
        except Exception as e:
            print(e)
            quit()
        else:
            print('Peer created as '+peer.id+': '+peer.token)

        try:
            # Ctrl+Cが押されるまでループ
            while True:
                # データコネクション
                for data in peer.getDataConnections():
                    # データコネクションのキューをそれぞれチェックして
                    # 何か到着していたら画面に表示します。
                    if not data.getQueue().empty():
                        mes = data.getQueue().get().decode(encoding='utf-8', errors='ignore')
                        print('メッセージを受信しました:', mes)
                # メディアコネクション
                for media in peer.getMediaConnections():
                    # 新しいメディアコネクションで、まだメディアシンクを取得していないものがあれば
                    # 取得してgstreamerソースを流し込みます。
                    if not media.isRedirectedOutgoing():
                        media_id, video_ipv4, video_port = media.getSinkToAnswer()
                        print('Video sink is', video_ipv4, 'at port', video_port)
                        gstreamer_cmd = "gst-launch-1.0 -e rpicamsrc ! video/x-raw,width=640,height=480,framerate=30/1 ! videoconvert ! vp8enc deadline=1 ! rtpvp8pay pt=96 ! udpsink host="+video_ipv4+" port="+str(video_port)+" sync=false"
                        gstreamer_processes.append(subprocess.Popen(gstreamer_cmd, shell=True))
                # MIDIキーボードからの入力
                midi_msg = midi_in.poll()
                if midi_msg is not None:
                    n = midiToNumber(midi_msg) # ノート番号から2タッチ入力数字へ変換
                    if n is not None: # nがNoneでない(=ノートオン命令のときのみ)
                        if len(CharBuf) == 0:
                            CharBuf = n
                        else:
                            CharBuf += n
                            new_char = numberToChar(CharBuf) # 2数字を文字に変換
                            CharBuf = ''
                            if new_char is not None:
                                # 変換可能な2数字であれば送信文に追加
                                MyMessage += new_char
                                print('現在のメッセージバッファ:', MyMessage)
                            else:
                                # 変換不可(##など)であれば送信してバッファクリア
                                print('メッセージを送信しました:', MyMessage)
                                for data in peer.getDataConnections():
                                    data.send(MyMessage)
                                MyMessage = ''

        except KeyboardInterrupt:
            try:
                for gstreamer_process in gstreamer_processes:
                    gstreamer_process.kill()
                peer.close()
                midi_in.close()
            except Exception as e:
                print(e)
