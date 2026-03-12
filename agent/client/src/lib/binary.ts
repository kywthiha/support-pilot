export const MSG_TYPE = {
  VIDEO: 1,
  AUDIO: 2,
};

export function buildBinaryMessage(type: number, payloadBuffer: ArrayBuffer) {
  const typeArray = new Uint8Array([type]);
  const payload = new Uint8Array(payloadBuffer);

  const message = new Uint8Array(typeArray.length + payload.length);
  message.set(typeArray, 0);
  message.set(payload, 1);

  return message.buffer;
}

export async function sendVideoFrame(socket: WebSocket, blob: Blob) {
  const buffer = await blob.arrayBuffer();
  const message = buildBinaryMessage(MSG_TYPE.VIDEO, buffer);
  socket.send(message);
}

export function sendAudioChunk(socket: WebSocket, audioBuffer: ArrayBuffer) {
  const message = buildBinaryMessage(MSG_TYPE.AUDIO, audioBuffer);
  socket.send(message);
}
