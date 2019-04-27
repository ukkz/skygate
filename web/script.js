'use strict';


function getQueryParams() {
  if (1 < document.location.search.length) {
    const query = document.location.search.substring(1);
    const params = query.split('&');
    const result = {};
    for (var param of params) {
      const element = param.split('=');
      const key = decodeURIComponent(element[0]);
      const value = decodeURIComponent(element[1]);
      result[key] = value;
    }
    return result;
  }
  return null;
}

const Peer = window.Peer;

(async function main() {
  const localVideo = document.getElementById('js-local-stream');
  const localId = document.getElementById('js-local-id');
  const localText = document.getElementById('js-local-text');
  const callTrigger = document.getElementById('js-call-trigger');
  const closeTrigger = document.getElementById('js-close-trigger');
  const sendTrigger = document.getElementById('js-send-trigger');
  const remoteVideo = document.getElementById('js-remote-stream');
  const remoteId = document.getElementById('js-remote-id');
  const messages = document.getElementById('js-messages');

  const localStream = await navigator.mediaDevices
    .getUserMedia({
      audio: true,
      video: true,
    })
    .catch(console.error);

  // Render local stream
  localVideo.muted = true;
  localVideo.srcObject = localStream;
  await localVideo.play().catch(console.error);

  const query = getQueryParams();
  const key = query['key'];
  const peer = new Peer({
    key: key,
    debug: 3,
  });

  // Register caller handler
  callTrigger.addEventListener('click', () => {
    // Note that you need to ensure the peer has connected to signaling server
    // before using methods of peer instance.
    if (!peer.open) {
      return;
    }

    const mediaConnection = peer.call(remoteId.value, localStream);
    const dataConnection = peer.connect(remoteId.value);

    mediaConnection.on('stream', async stream => {
      // Render remote stream for caller
      remoteVideo.srcObject = stream;
      await remoteVideo.play().catch(console.error);
    });

    mediaConnection.once('close', () => {
      remoteVideo.srcObject.getTracks().forEach(track => track.stop());
      remoteVideo.srcObject = null;
    });

    dataConnection.once('open', async () => {
      messages.textContent = `=== DataConnection has been opened ===\n` + messages.textContent;
      sendTrigger.addEventListener('click', onClickSend);
    });

    dataConnection.on('data', data => {
      messages.textContent = `Remote: ${data}\n` + messages.textContent;
      console.log(data);
    });
  
    dataConnection.once('close', () => {
      messages.textContent = `=== DataConnection has been closed ===\n` + messages.textContent;
      sendTrigger.removeEventListener('click', onClickSend);
    });

    closeTrigger.addEventListener('click', () => {
      mediaConnection.close();
      callTrigger.innerText = 'Call';
      callTrigger.disabled = '';
    });

    function onClickSend() {
      const data = localText.value;
      dataConnection.send(data);
      messages.textContent = `You: ${data}\n` + messages.textContent;
      localText.value = '';
    }
  });

  peer.on('open', myId => {
    localId.textContent = myId;
    peer.listAllPeers(peers => {
      console.log(peers);
      if (peers.length <= 1) {
        callTrigger.innerText = 'No peers';
        callTrigger.disabled = 'disabled';
      } else {
        for (var i=0;i<peers.length;i++) {
          if (peers[i] != myId) {
            let plist = document.createElement("option");
            plist.value = peers[i];  //value値
            plist.text = peers[i];   //テキスト値
            remoteId.appendChild(plist);
          }
        }
      }
    });
  });

  // Register callee handler
  peer.on('call', mediaConnection => {
    mediaConnection.answer(localStream);

    mediaConnection.on('stream', async stream => {
      // Render remote stream for callee
      remoteVideo.srcObject = stream;
      await remoteVideo.play().catch(console.error);
    });

    mediaConnection.once('close', () => {
      remoteVideo.srcObject.getTracks().forEach(track => track.stop());
      remoteVideo.srcObject = null;
    });

    closeTrigger.addEventListener('click', () => {
      mediaConnection.close();
      callTrigger.innerText = 'Call';
      callTrigger.disabled = '';
    });
  });

  peer.on('error', console.error);
})();
